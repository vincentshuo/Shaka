#!/usr/bin/env python3
"""Generate and revise one offline candidate using a native Codex session."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import tomllib
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INTENT = "Locate the yellow button, contact it once with the designated right index fingertip, then withdraw. Keep both feet planted."
RESPONSE_FIELDS = (
    "input_preprocessor",
    "implementation",
    "configuration_json",
    "change_summary",
)
RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": list(RESPONSE_FIELDS),
    "properties": {name: {"type": "string"} for name in RESPONSE_FIELDS},
}


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_process(
    command: list[str],
    cwd: Path,
    timeout: float,
    prompt: str = "",
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env=env,
    )
    try:
        stdout, stderr = process.communicate(prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        return subprocess.CompletedProcess(
            command, 124, stdout, stderr + "\nprocess deadline exceeded"
        )
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def freeze_context(path: Path, output: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text())
    if manifest.get("schema_version") != 1 or manifest.get("evidence_kind") not in (
        "historical",
        "synthetic",
    ):
        raise ValueError(
            "context requires schema_version 1 and historical or synthetic evidence_kind"
        )
    if not isinstance(manifest.get("source"), str) or not manifest["source"].strip():
        raise ValueError("context source must describe observation provenance")
    inputs = output / "inputs"
    inputs.mkdir()
    context = {"evidence_kind": manifest["evidence_kind"], "source": manifest["source"]}
    for key, name in (
        ("body", "body.md"),
        ("observation", "observation.json"),
        ("control_contract", "control.json"),
    ):
        ref = manifest[key]
        source = (path.parent / ref["path"]).resolve()
        content = source.read_bytes()
        if hashlib.sha256(content).hexdigest() != ref["sha256"]:
            raise ValueError(f"{key} input digest does not match")
        (inputs / name).write_bytes(content)
        context[key] = content.decode() if key == "body" else json.loads(content)
    write_json(inputs / "context.json", manifest)
    return context


def freeze_package(
    response: dict[str, Any], directory: Path, action: dict[str, Any], source: str
) -> Path:
    if set(response) != set(RESPONSE_FIELDS) or any(
        not isinstance(response[key], str) for key in RESPONSE_FIELDS
    ):
        raise ValueError(
            "model response must contain exactly the four candidate text fields"
        )
    configuration = json.loads(response["configuration_json"])
    if not isinstance(configuration, dict):
        raise TypeError("candidate configuration must be an object")
    bundle = directory / "candidate"
    bundle.mkdir()
    (bundle / "preprocess.py").write_text(response["input_preprocessor"])
    (bundle / "implementation.py").write_text(response["implementation"])
    write_json(bundle / "configuration.json", configuration)
    write_json(bundle / "action.json", action)
    package = {
        "schema_version": 1,
        "candidate_id": f"offline-{uuid.uuid4().hex}-{directory.name}",
        "source_version": source,
        "artifacts": {
            key: {"path": name, "sha256": digest(bundle / name)}
            for key, name in (
                ("input_preprocessor", "preprocess.py"),
                ("implementation", "implementation.py"),
                ("configuration", "configuration.json"),
                ("action_definition", "action.json"),
            )
        },
        "runtime": {
            "kind": "python-callable-v1",
            "preprocess": {"artifact": "input_preprocessor", "callable": "preprocess"},
            "inference": {"artifact": "implementation", "callable": "infer"},
        },
    }
    path = bundle / "candidate-package.json"
    write_json(path, package)
    return path


def replay(
    package: Path, observation: Path, control: Path, directory: Path
) -> dict[str, Any]:
    # Reuse the existing admission rules and isolated replay. No candidate is
    # imported into this process and the independent evaluator is never invoked.
    from _offline_invocation_adapter import candidate
    from run_single_invocation import (
        VerifiedArtifact,
        _candidate_artifacts,
        _validated_action_definition,
    )

    try:
        value = json.loads(package.read_text())
        trusted = _validated_action_definition(
            json.loads(control.read_text())["control_contract"], "control contract"
        )
        verified = VerifiedArtifact(
            package, digest(package), package.read_bytes(), value
        )
        _candidate_artifacts(verified, trusted)
        runtime = {**value, "candidate_package_sha256": digest(package)}
        runtime_path = package.parent / "candidate-runtime.json"
        write_json(runtime_path, runtime)
        saved_observation = package.parent / "candidate-observation.json"
        saved_observation.write_bytes(observation.read_bytes())
        return candidate(
            argparse.Namespace(
                runtime_package=runtime_path,
                observation=saved_observation,
                control_contract=control,
                timeout_s=15,
                controller_trace=directory / "controller-trace.json",
            )
        )
    except Exception as error:  # noqa: BLE001 - preserve structured admission failure
        return {
            "deployment_status": "rejected",
            "failure_class": "admission_rejection",
            "reason": str(error),
            "command_publishers_created": 0,
            "writes": 0,
            "physical_rollout_attempts_consumed": 0,
        }


def replay_command(output: Path, directory: Path, image: str | None) -> list[str]:
    script = Path(__file__).resolve()
    root = output
    prefix = [sys.executable, str(script)]
    if image:
        root = Path("/run-data")
        prefix = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--security-opt",
            "seccomp=unconfined",
            "--security-opt",
            "systempaths=unconfined",
            "--mount",
            f"type=bind,src={ROOT},dst=/work,readonly",
            "--mount",
            f"type=bind,src={output},dst={root}",
            image,
            "python",
            "/work/scripts/run_offline_candidate_cycle.py",
        ]
    return [*prefix, "replay", "--output", str(root), "--round", directory.name]


def provider_connection(path: Path | None) -> tuple[list[str], dict[str, str]]:
    if path is None:
        return [], {}
    configuration = tomllib.loads(path.read_text())
    provider = configuration["model_providers"][configuration["model_provider"]]
    # Import only transport settings, never user tools, hooks or MCP servers.
    selected = {
        key: provider[key]
        for key in ("name", "base_url", "wire_api", "requires_openai_auth")
        if key in provider
    }
    if selected.get("wire_api") != "responses":
        raise ValueError("selected Codex provider must use the responses wire API")
    token = provider.get("experimental_bearer_token")
    if token is None and provider.get("env_key"):
        token = os.environ.get(provider["env_key"])
        if not token:
            raise RuntimeError(
                "selected provider credential environment variable is absent"
            )
    environment = {}
    if token:
        selected["env_key"] = "SHAKA_CODEX_PROVIDER_TOKEN"
        environment["SHAKA_CODEX_PROVIDER_TOKEN"] = token
    inline = ", ".join(
        f"{key} = {json.dumps(value)}" for key, value in selected.items()
    )
    return [
        "-c",
        'model_provider="shaka"',
        "-c",
        "model_providers.shaka={" + inline + "}",
    ], environment


def model_turn(
    runtime: str,
    model: str,
    directory: Path,
    prompt: str,
    session: str | None,
    timeout: float,
    connection: tuple[list[str], dict[str, str]],
) -> dict[str, Any]:
    schema = directory / "response-schema.json"
    write_json(schema, RESPONSE_SCHEMA)
    response_path = directory / "response.json"
    (directory / "prompt.txt").write_text(prompt)
    command = [runtime, "exec"]
    if session:
        command += ["resume", session]
    command += [
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "-c",
        'sandbox_mode="read-only"',
        "-c",
        'approval_policy="never"',
        "-c",
        "features.shell_tool=false",
        "-c",
        "features.multi_agent=false",
        "-c",
        "features.apps=false",
        "-c",
        "features.plugins=false",
        "-c",
        'web_search="disabled"',
        "-c",
        'model_reasoning_effort="medium"',
        *connection[0],
        "--model",
        model,
        "--json",
        "--output-schema",
        str(schema),
        "--output-last-message",
        str(response_path),
        "-",
    ]
    write_json(directory / "command.json", command)
    started = time.monotonic()
    result = run_process(
        command, directory, timeout, prompt, {**os.environ, **connection[1]}
    )
    for secret in connection[1].values():
        result.stdout = result.stdout.replace(secret, "[REDACTED]")
        result.stderr = result.stderr.replace(secret, "[REDACTED]")
    (directory / "events.jsonl").write_text(result.stdout)
    (directory / "stderr.txt").write_text(result.stderr)
    receipt: dict[str, Any] = {
        "elapsed_s": time.monotonic() - started,
        "exit_code": result.returncode,
        "session_id": session,
        "usage": None,
        "usage_scope": "raw Codex turn.completed counters; resumed counters may be session-cumulative; do not sum",
    }
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started":
            receipt["session_id"] = event.get("thread_id")
        if event.get("type") == "turn.completed":
            receipt["usage"] = event.get("usage")
    write_json(directory / "receipt.json", receipt)
    if result.returncode or not response_path.is_file():
        raise RuntimeError(
            f"model runtime failed (exit {result.returncode}); see round receipt and stderr"
        )
    if not receipt["session_id"] or not isinstance(receipt["usage"], dict):
        raise RuntimeError(
            "model runtime omitted session identity or accountable token usage"
        )
    uuid.UUID(receipt["session_id"])
    if session and receipt["session_id"] != session:
        raise RuntimeError("model runtime resumed a different session")
    return receipt


def cycle(
    args: argparse.Namespace, output: Path, report: dict[str, Any], runtime: str
) -> None:
    context = freeze_context(args.context.resolve(), output)
    report["input_sha256"] = {
        path.name: digest(path) for path in (output / "inputs").iterdir()
    }
    report["evidence_kind"] = context["evidence_kind"]
    report["source"] = context["source"]
    report["runtime_sha256"] = digest(Path(runtime).resolve())
    report["reuse_kind"] = (
        "Codex CLI product runtime; native exec/resume; no vendored upstream source"
    )
    report["model_version_boundary"] = (
        "requested deployment identifier; provider weight revision is not exposed by CLI"
    )
    image = args.replay_image
    if image:
        inspected = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image],
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        if inspected.returncode:
            raise RuntimeError(
                "replay image unavailable; build the documented offline image first"
            )
        image = inspected.stdout.strip()
    elif not shutil.which("bwrap"):
        raise RuntimeError(
            "isolated replay requires Linux bubblewrap or --replay-image; unisolated execution is forbidden"
        )
    report["replay_image"] = image
    connection = provider_connection(args.provider_config)
    session = None
    feedback = None
    prompt = (
        f"Task intent: {INTENT}\n"
        "Generate an executable Python candidate, not a task-success verdict. "
        "Return only the schema fields. Both preprocess(observation, configuration) and "
        "infer(model_input, configuration) take exactly two arguments. "
        "Top level permits only function definitions and docstrings; import inside functions if needed. "
        "infer returns action_definition_id, timestamp_ns from the observation, joint_names in contract order, "
        "and a finite numeric values list. No hardware, network, file writes, evaluator access or self-judged success. "
        "This is offline replay, not a new physical trial. Do not invent target coordinates or missing calibration. "
        "If observations are insufficient for contact, make that limitation explicit in change_summary and use a "
        "non-moving diagnostic candidate rather than claiming a usable contact policy. "
        "The host freezes the action contract and packages your text.\n"
        + json.dumps(context, ensure_ascii=False)
    )
    for number in (1, 2):
        directory = output / f"round-{number}"
        directory.mkdir()
        if number == 2:
            prompt = (
                "Review the actual frozen admission/replay feedback below and revise the previous candidate once. "
                "Keep the task and action contract fixed. Return all four candidate text fields, "
                "and explain the change and any remaining physical evidence limitations in change_summary.\n"
                + json.dumps(feedback, ensure_ascii=False)
            )
        try:
            receipt = model_turn(
                runtime,
                args.model,
                directory,
                prompt,
                session,
                args.timeout_s,
                connection,
            )
        except Exception:
            if (directory / "receipt.json").is_file():
                report["rounds"].append(
                    {
                        "round": number,
                        **json.loads((directory / "receipt.json").read_text()),
                    }
                )
            raise
        session = receipt["session_id"]
        item: dict[str, Any] = {"round": number, **receipt}
        report["rounds"].append(item)
        try:
            response = json.loads((directory / "response.json").read_text())
            package = freeze_package(
                response,
                directory,
                context["control_contract"]["control_contract"],
                f"{args.model}/{report['runtime_version']}/{session}/round-{number}",
            )
            item["package"] = str(package.relative_to(output))
            item["package_sha256"] = digest(package)
            item["candidate_content_sha256"] = hashlib.sha256(
                json.dumps(
                    {
                        name: response[name]
                        for name in RESPONSE_FIELDS
                        if name != "change_summary"
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            result = run_process(replay_command(output, directory, image), output, 60)
            (directory / "replay-stderr.txt").write_text(result.stderr)
            if result.returncode not in (0, 2):
                raise RuntimeError(
                    f"replay process failed with exit {result.returncode}"
                )
            feedback = json.loads(result.stdout)
        except (ValueError, TypeError, KeyError) as error:
            feedback = {
                "deployment_status": "rejected",
                "failure_class": "invalid_candidate",
                "reason": str(error),
            }
        write_json(directory / "feedback.json", feedback)
        item["feedback"] = feedback
        write_json(output / "report.json", report)
    if feedback is None or feedback.get("deployment_status") != "admitted":
        raise RuntimeError(
            "revised candidate was rejected; see preserved admission feedback"
        )
    if report["rounds"][0].get("candidate_content_sha256") == report["rounds"][1].get(
        "candidate_content_sha256"
    ):
        raise RuntimeError(
            "candidate implementation and configuration are unchanged; no revision was demonstrated"
        )
    report["status"] = "completed"
    report["session_id"] = session
    report["historical_observation_acceptance"] = (
        "operator-declared historical input replayed"
        if context["evidence_kind"] == "historical"
        else "pending; synthetic input only"
    )


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "replay":
        parser = argparse.ArgumentParser()
        parser.add_argument("--output", type=Path, required=True)
        parser.add_argument("--round", choices=("round-1", "round-2"), required=True)
        args = parser.parse_args(sys.argv[2:])
        directory = args.output.resolve() / args.round
        result = replay(
            directory / "candidate" / "candidate-package.json",
            args.output / "inputs" / "observation.json",
            args.output / "inputs" / "control.json",
            directory,
        )
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("deployment_status") == "admitted" else 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--codex", default="codex")
    parser.add_argument(
        "--replay-image",
        help="Linux Docker image with bubblewrap, Python, Pillow and pydantic",
    )
    parser.add_argument("--timeout-s", type=float, default=300)
    parser.add_argument(
        "--provider-config",
        type=Path,
        help="read only the selected provider transport from a Codex TOML config",
    )
    args = parser.parse_args()
    if not 0 < args.timeout_s <= 1800:
        parser.error("timeout-s must be in (0, 1800]")
    output = args.output.resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error("output already exists; historical runs cannot be overwritten")
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "failed",
        "rounds": [],
        "physical_rollout_attempts_consumed": 0,
        "robot_runtime_consumed_s": 0,
        "command_publishers_created": 0,
        "writes": 0,
        "task_result": None,
        "requested_model": args.model,
    }
    try:
        runtime = shutil.which(args.codex)
        if runtime is None:
            raise RuntimeError("Codex runtime is unavailable")
        runtime = str(Path(runtime).resolve())
        version_result = subprocess.run(
            [runtime, "--version"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if version_result.returncode:
            raise RuntimeError("Codex runtime version check failed")
        report["runtime_version"] = version_result.stdout.strip()
        cycle(args, output, report, runtime)
    except Exception as error:  # noqa: BLE001 - always publish the terminal failure
        report["reason"] = str(error)
    write_json(output / "report.json", report)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
