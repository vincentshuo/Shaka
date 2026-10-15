# 强代理离线候选闭环（#28）

一个公开入口完成：任务意图 → Codex 原生会话生成候选文本 → 宿主封存候选 → 既有静态准入与 Bubblewrap 回放 → 恢复同一会话读取真实诊断 → 一次修订与再次准入。

这复用的是已安装的 **Codex CLI 产品运行时**，不是源码 Grabbism。没有新增多代理角色、模型路由、训练框架或通用工作流服务。原生 `exec/resume` 承担会话管理；宿主只固定本任务的两次候选提交协议。

## 使用

需要 Python 3.11+、可调用的 Codex CLI，以及 Linux 非 root 用户下可用的 Bubblewrap。macOS 使用断网 Linux 容器运行同一回放代码：

```sh
docker build -t shaka-offline-replay:issue28 deploy/offline-candidate
python3 scripts/run_offline_candidate_cycle.py \
  --context configs/offline-candidate-demo-v001/context.json \
  --output /tmp/shaka-offline-demo-001 \
  --model gpt-6-astra \
  --replay-image shaka-offline-replay:issue28
```

`--model` 必须由操作者明确指定当前账号可访问的部署标识。直接 OpenAI 登录可通过现有 Codex 认证使用；使用已配置的 Responses 代理时增加：

```sh
--provider-config /absolute/path/to/codex/config.toml
```

该选项只读取选定 provider 的连接字段，不载入用户的 MCP、工具、插件或 hooks；配置中的 bearer token 转为子进程环境变量，不写入命令工件。没有凭证或模型不可用会失败，不回退到模拟模型。可用 `--codex` 指定受信任的 CLI 可执行文件；测试以此替代外部模型边界，生产验收必须核对运行时来源。

原生 Linux 环境可省略 `--replay-image`，但必须满足现有隔离回放环境：Pillow、pydantic、Bubblewrap 与可被绑定的自包含 Python 前缀。建议复用上述容器，避免环境差异。容器以当前非 root UID 运行，断网且没有硬件设备或 Docker socket；只读挂载项目、读写挂载本次输出。`seccomp=unconfined` 和 `systempaths=unconfined` 用于允许 Bubblewrap 创建嵌套命名空间，候选内部仍由 Bubblewrap 的只读文件、独立 PID/网络和清空环境隔离；不是给候选宿主写权限。嵌套隔离不可用就拒绝，不提供未隔离模式。

## 输入与事实边界

上下文清单采用 `schema_version: 1`，包含 `evidence_kind`（`historical` 或 `synthetic`）、来源说明 `source`，以及三个带 `path` 和 `sha256` 的引用：

- `body`：操作者冻结的本体说明。
- `observation`：已有候选回放接受的 JSON 观测，含原始 `captured_at_ns` 和必要状态；候选不访问未显式提供的外部文件。
- `control_contract`：含冻结的 `control_contract` 动作定义，与既有准入格式一致。

任务意图固定为右食指单次接触黄色按钮并撤离、双脚不移动。调用者不提供按钮坐标或准备好的运动目标。宿主核对输入摘要，复制本次输入，记录摘要；原始来源不能被候选修改。

示例是 **synthetic 诊断观测**：关节姿态取自已记录的标准起始配置，但回放时间戳是合成的，而且没有原始相机或状态流。它可以检验接口，却不能算历史原始观测验收。`historical` 是操作者声明，工具验证的是字节摘要与回放行为，不会自动证明数据确为真机采集。

输入缺少视觉、运动学或标定时，代理应说明缺口，可以生成保持当前姿态的诊断候选；这不意味着得到了可部署的接触策略。此入口暂不自动取回图像路径或重建完整历史 episode。原始历史观测可用后，再按其真实来源制作清单并单独验收。

## 输出与验收

- `report.json`：运行状态、输入摘要、模型部署标识、CLI 版本与可执行文件摘要、容器镜像 ID、两轮候选与诊断引用。`task_result` 始终为空，物理尝试和机器人时间始终为零。
- 每轮保存提示、原始响应、CLI JSONL、stderr、调用回执、候选包及全部源码/配置摘要、真实准入与回放反馈。
- 无效模型响应、静态准入拒绝和部署错误进入第二轮反馈；模型不可用、运行时故障或超时停止。第二轮仍拒绝时退出码为 2。
- `completed` 仅表示第二版通过离线准入且源码或配置文本发生变化，不证明行为改善、接触能力或任务成功；不可把候选身份变化冒充修订。
- 模型不可用时保留失败回执。输出目录不可复用；每次候选身份独立，不覆盖旧运行。
- CLI `turn.completed` 用量按原样保留，resume 的计数可能是会话累计值，**不能把两轮原始计数直接相加**。费用未知时不写成零。部署名称可能是厂商可更新别名；CLI 没有提供的权重 revision 不会被伪造为已冻结。

模型只返回四个文本字段，宿主构造候选包并冻结动作定义。模型命令关闭 shell、多代理、apps、plugins 和 web search，采用只读 sandbox；候选代码只在既有双层 Bubblewrap 中执行。候选返回的成功声明由既有适配器忽略，独立评估器不会被调用或向候选开放。提供 `--codex`、provider 配置和回放镜像的操作者属于受信任边界。

## 验证

在断网的 Linux 容器运行公开 CLI 回归；模型客户端可替代，但候选准入和执行隔离使用真实实现：

```sh
docker run --rm --network none \
  --security-opt seccomp=unconfined --security-opt systempaths=unconfined \
  -v "$PWD:/work:ro" -w /work shaka-offline-replay:issue28 \
  python -m unittest discover -s tests -p test_run_offline_candidate_cycle.py -v
```

这是 #28 的离线入口，连接 G1 的当前观测验收归 #29，物理金丝雀仍受 #27 与 #31 约束。没有真机和原始历史数据时，不能据此关闭“真实历史观测回放”的验收项。

官方运行时依据：[非交互运行、结构化输出和恢复会话](https://developers.openai.com/codex/noninteractive)、[配置参考](https://developers.openai.com/codex/config-reference)。
