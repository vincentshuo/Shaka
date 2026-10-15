from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_offline_candidate_cycle.py"


class OfflineCandidateCycleTest(unittest.TestCase):
    def fixture(self, root: Path) -> Path:
        action = {
            "schema_version": 1,
            "action_definition_id": "fixture-arm-v1",
            "command_type": "joint_position",
            "joint_names": ["right_elbow_joint"],
            "value_dimension": 1,
            "maximum_output_age_ns": 100,
        }
        files = {
            "body": (
                "body.md",
                "G1 + BrainCo. Designated fingertip: right index. Feet stationary.",
            ),
            "observation": (
                "observation.json",
                json.dumps(
                    {
                        "captured_at_ns": 1000,
                        "robot_state": {
                            "joint_names": ["right_elbow_joint"],
                            "positions": [0.2],
                        },
                    }
                ),
            ),
            "control_contract": (
                "control.json",
                json.dumps({"control_contract": action}),
            ),
        }
        manifest = {
            "schema_version": 1,
            "evidence_kind": "synthetic",
            "source": "CLI regression fixture",
        }
        for key, (name, content) in files.items():
            (root / name).write_text(content)
            manifest[key] = {
                "path": name,
                "sha256": hashlib.sha256(content.encode()).hexdigest(),
            }
        path = root / "context.json"
        path.write_text(json.dumps(manifest))
        return path

    def run_cycle(
        self, root: Path, context: Path, runtime: Path, *extra: str
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--context",
                str(context),
                "--output",
                str(root / "run"),
                "--model",
                "fixture-model",
                "--codex",
                str(runtime),
                *extra,
            ],
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )

    def test_unavailable_model_runtime_fails_without_physical_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_cycle(root, self.fixture(root), root / "missing-codex")
            self.assertEqual(result.returncode, 2, result.stderr)
            report = json.loads((root / "run" / "report.json").read_text())
            self.assertEqual(report["status"], "failed")
            self.assertIn("runtime", report["reason"])
            self.assertEqual(report["physical_rollout_attempts_consumed"], 0)
            self.assertEqual(report["writes"], 0)
            self.assertEqual(report["rounds"], [])

    def runtime(self, root: Path, response_override: str = "") -> Path:
        path = root / "codex-fixture"
        path.write_text(
            "#!"
            + sys.executable
            + "\n"
            + """
import json, sys
from pathlib import Path
if '--version' in sys.argv:
    print('codex-cli fixture-only')
    raise SystemExit(0)
prompt = sys.stdin.read()
revision = 'resume' in sys.argv
if revision and 'deployment_status' not in prompt:
    raise SystemExit('revision did not receive admission feedback')
response = {
    'input_preprocessor': 'def preprocess(observation, configuration):\\n    return observation\\n',
    'implementation': 'def infer(observation, configuration):\\n    return {"action_definition_id": "fixture-arm-v1", "timestamp_ns": observation["captured_at_ns"], "joint_names": ["right_elbow_joint"], "values": [configuration["value"]]}\\n',
    'configuration_json': json.dumps({'value': 0.1 if revision else 0.2}),
    'change_summary': 'reduce displacement after reviewing offline diagnostics' if revision else 'initial candidate',
}
"""
            + response_override
            + """
Path(sys.argv[sys.argv.index('--output-last-message') + 1]).write_text(json.dumps(response))
print(json.dumps({'type': 'thread.started', 'thread_id': '11111111-1111-4111-8111-111111111111'}))
print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 100, 'cached_input_tokens': 0, 'output_tokens': 40}}))
"""
        )
        path.chmod(0o755)
        return path

    def test_native_session_revises_a_candidate_using_real_replay_feedback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_cycle(root, self.fixture(root), self.runtime(root))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((root / "run" / "report.json").read_text())
            self.assertEqual(report["status"], "completed")
            self.assertEqual(len(report["rounds"]), 2)
            self.assertEqual(report["task_result"], None)
            for item in report["rounds"]:
                self.assertEqual(item["feedback"]["deployment_status"], "admitted")
                self.assertEqual(item["usage"]["input_tokens"], 100)
                package = json.loads((root / "run" / item["package"]).read_text())
                self.assertTrue(package["source_version"])
            self.assertNotEqual(
                report["rounds"][0]["package_sha256"],
                report["rounds"][1]["package_sha256"],
            )
            self.assertEqual(report["physical_rollout_attempts_consumed"], 0)
            self.assertEqual(report["command_publishers_created"], 0)
            self.assertEqual(report["writes"], 0)

    def test_invalid_candidate_text_is_returned_as_revision_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self.runtime(
                root, "if not revision: response = ['not a candidate object']\n"
            )
            result = self.run_cycle(root, self.fixture(root), runtime)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((root / "run" / "report.json").read_text())
            self.assertEqual(
                report["rounds"][0]["feedback"]["failure_class"], "invalid_candidate"
            )
            self.assertEqual(
                report["rounds"][1]["feedback"]["deployment_status"], "admitted"
            )

    def test_malformed_json_is_preserved_and_can_be_revised(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self.runtime(root)
            runtime.write_text(
                runtime.read_text().replace(
                    "write_text(json.dumps(response))",
                    'write_text(json.dumps(response) if revision else "invalid JSON")',
                )
            )
            result = self.run_cycle(root, self.fixture(root), runtime)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                (root / "run/round-1/response.json").read_text(), "invalid JSON"
            )
            report = json.loads((root / "run/report.json").read_text())
            self.assertEqual(
                report["rounds"][0]["feedback"]["failure_class"], "invalid_candidate"
            )

    def test_selected_provider_credentials_are_not_saved_in_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            provider = root / "provider.toml"
            provider.write_text(
                'model_provider="custom"\n[model_providers.custom]\n'
                'name="Local"\nbase_url="http://127.0.0.1:9999/v1"\n'
                'wire_api="responses"\nrequires_openai_auth=false\n'
                'experimental_bearer_token="fixture-secret-never-retain"\n'
            )
            runtime = self.runtime(
                root,
                'import os\nassert os.environ["SHAKA_CODEX_PROVIDER_TOKEN"] == "fixture-secret-never-retain"\n',
            )
            result = self.run_cycle(
                root, self.fixture(root), runtime, "--provider-config", str(provider)
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for path in (root / "run").rglob("*"):
                if path.is_file():
                    self.assertNotIn(
                        b"fixture-secret-never-retain", path.read_bytes(), str(path)
                    )

    def test_unchanged_candidate_is_not_reported_as_a_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self.runtime(
                root, "response['configuration_json'] = '{\"value\": 0.2}'\n"
            )
            result = self.run_cycle(root, self.fixture(root), runtime)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            report = json.loads((root / "run/report.json").read_text())
            self.assertIn("unchanged", report["reason"])

    def test_admission_rejection_cannot_be_overridden_by_model_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self.runtime(
                root,
                "response['implementation'] = 'import socket\\n' + response['implementation']\n",
            )
            result = self.run_cycle(root, self.fixture(root), runtime)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            report = json.loads((root / "run/report.json").read_text())
            for item in report["rounds"]:
                self.assertEqual(
                    item["feedback"]["failure_class"], "admission_rejection"
                )
            self.assertEqual(report["task_result"], None)
            self.assertFalse(list((root / "run").rglob("controller-trace.json")))

    def test_model_failure_retains_receipt_and_does_not_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self.runtime(
                root,
                "print('authentication unavailable', file=sys.stderr)\nraise SystemExit(1)\n",
            )
            result = self.run_cycle(root, self.fixture(root), runtime)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            receipt = json.loads((root / "run/round-1/receipt.json").read_text())
            self.assertEqual(receipt["exit_code"], 1)
            self.assertIsNone(receipt["usage"])
            self.assertFalse(list((root / "run").rglob("candidate-package.json")))


if __name__ == "__main__":
    unittest.main()
