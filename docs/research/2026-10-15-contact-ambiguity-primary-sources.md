# 接触歧义研究：一手来源与反例附录

对应 [issue #32](https://github.com/vincentshuo/Shaka/issues/32)。核验日期：2026-10-15。本文只记录文献、作者材料和公开源码的静态阅读；未运行机器人、模拟实验或任何仓库 demo。论文实验结果均是作者报告，不是本项目复现结果。

## 核心判断

“遇到不确定性时选择更有信息的触碰，并节省观测成本”已有非常直接的先例。[S2] 不仅选择触碰，而且明确以最小成本达到信息阈值，在线更新假设，并与随机、人工固定动作比较。[S3] 已区分预先选定观测集合与依赖观测结果的条件计划。[S4] 已将动作改变物理世界与改变知识状态放在同一控制问题中。[S6] 更直接比较相同平均传输率的事件触发与周期策略。因此，这些机制的命名、组合或移植到代码代理，单独不足以构成研究新意。

尚可研究的差异是：在强模型、原始证据访问、工具、传感器和总预算一致时，特定接触任务上的选择策略是否仍降低**通过外部真值检验的成功成本**。上述论文没有替 Shaka 回答这一受限问题，也没有证明 LLM 置信度能判定接触真相。

## 来源矩阵

标记：**正文**表示读取论文相关章节；**源码**表示阅读实际代码但未执行；**作者说明**表示项目页或 README 的自述。没有核实代码，不等于代码不存在。

| ID / 来源 | 已读取范围 | 原始材料确立的机制 | 公开实现核验及适用边界 |
| --- | --- | --- | --- |
| S1 Bohg et al., *Interactive Perception: Leveraging Action in Perception and Perception in Action*, T-RO 2017 | [arXiv 页面](https://arxiv.org/abs/1604.03670)、[正文](https://arxiv.org/pdf/1604.03670)：摘要、主动交互分类、触觉/对象姿态段落及参考文献 | 交互产生原本没有的感知信号；动作与感知联合解释；列出触觉定位、下一次触碰、信息增益等先例 | 作者综述是领域框架来源，不能代替被引原始研究的实验；S2 已单独取得正文。未将综述当作可执行系统 |
| S2 Javdani et al., *Efficient Touch Based Localization through Submodularity*, ICRA 2013 | [CMU 机构页](https://www.ri.cmu.edu/publications/efficient-touch-based-localization-through-submodularity/)、[作者扩展正文](https://www.ri.cmu.edu/pub_files/2012/8/TouchLocalizationSubmodularity_extended.pdf)：§III–VI、实验表格与模型假设 | 给定对象姿态假设、动作与观测，按成本选择自适应触碰序列，达到效用阈值；利用次模性解释贪心信息收集 | 正文报告仿真和 Barrett 实机门把手实验；此次未找到并核验其配套源码。已知对象网格、粒子先验、接触模型与力矩传感器是必要资源，不能默认为无成本 |
| S3 Krause & Guestrin, *Optimal Value of Information in Graphical Models*, JAIR 35, 2009 | [全文](https://arxiv.org/pdf/1401.3474)：§1–2 问题、奖励与预算定义，§3–4 适用结构概述 | 对昂贵观测选择集合或条件计划；收益可以是熵，也可以是观测后最优决策的期望效用；显式计入观测成本/预算 | 正文限定图结构与复杂度结果，不是一般机器人问题的免费最优求解器。此次未核验配套代码 |
| S4 Klenske & Hennig, *Dual Control for Approximate Bayesian Reinforcement Learning*, JMLR 17, 2016 | [期刊页](https://jmlr.org/papers/v17/15-162.html)、[正文](https://jmlr.org/papers/volume17/15-162/15-162.pdf)：§1、§2–4 的问题、谨慎控制/探测对比与近似构造 | 动作同时影响状态与未来对动力学的认识；考虑未来学习价值。仅因不确定而减小动作的谨慎策略可能阻止学习 | 作者报告模拟系统，非接触机器人实机保证。近似依赖动力学/概率模型；此次未核验作者实现。作者将双重控制起源追溯至 Feldbaum，但本文未直接读取其原文 |
| S5 Heemels, Johansson & Tabuada, *An Introduction to Event-triggered and Self-triggered Control*, CDC 2012 | [作者正文](https://heemels.tue.nl/assets/content/papers/HeeJoh_CDC12a.pdf)：摘要、§I–III 的定义与监测成本，输出反馈限制段落 | 事件触发根据当前测量反应，自触发依据已知模型预测下一次更新；二者早已以节省采样/通信/计算为目标 | 本文为作者教程/综述，正文也指出持续监测、全状态可用性与输出反馈困难；不能把触发器本身当零成本，更不能把稳定性结论改写成成功语义认证 |
| S6 Antunes, Heemels & Tabuada, *Dynamic Programming Formulation of Periodic Event-Triggered Control: Performance Guarantees and Co-Design*, CDC 2012 | [作者正文](https://heemels.tue.nl/assets/content/papers/AntHee_CDC12a.pdf)：摘要、引言中的比较约束与方法范围 | 在线选择传输和控制输入；在线性系统、二次折扣代价框架下，相同平均传输率优于或等于周期策略；另一构造用更少传输取得性能界 | 这是事件触发类直接原始研究。此次未逐条复核证明或复现实验，未核验代码；平均传输率相同并不等于所有计算和物理成本相同 |
| S7 Liang et al., *Code as Policies: Language Model Programs for Embodied Control*, 2022/ICRA 2023 | [作者项目页](https://code-as-policies.github.io/)、[正文](https://arxiv.org/pdf/2209.07753)：讨论/限制、Appendix F；[官方目录](https://github.com/google-research/google-research/tree/master/code_as_policies)及 Reactive Controllers notebook 源码 | LLM 生成处理感知输出的程序与反馈控制；递归定义函数；包括 cartpole 与末端阻抗控制示例 | **源码**已读 notebook 中控制器生成、仿真状态访问和力矩执行结构；不是只看演示。示例控制器能力不等于自行构建接触真值或已实施成本敏感消歧策略 |
| S8 Huang et al., *VoxPoser: Composable 3D Value Maps for Robotic Manipulation with Language Models*, 2023 | [项目页](https://voxposer.github.io/)、[官方 README](https://github.com/huangwl18/VoxPoser/blob/main/README.md)、[interfaces.py](https://github.com/huangwl18/VoxPoser/blob/main/src/interfaces.py) 的 `execute` | 语言模型生成可组合三维价值图，实际执行循环重新读取对象观测和地图、规划、执行、检查终止/重规划 | **源码**确认闭环，不能描述为纯一次性开环。README 明确是 RLBench demo，不含实机感知管线，使用模拟器提供的对象 mask；未核实接触消歧与等总成本收益 |
| S9 Huang et al., *ReKep: Spatio-Temporal Reasoning of Relational Keypoint Constraints for Robotic Manipulation*, 2024 | [项目页](https://rekep-robot.github.io/)、[官方 README](https://github.com/huangwl18/ReKep/blob/main/README.md)、[main.py](https://github.com/huangwl18/ReKep/blob/main/main.py) 的 `_execute` | 用生成的关键点约束进行闭环优化；路径约束违反时回退到此前可行阶段；支持扰动演示 | **源码**确认读取当前关键点/SDF、检查约束、回退与再次规划。README 明确缺少实机 keypoint/mask tracking 与 SDF reconstruction，示例直接从仿真读取；这不是独立任务成功认证器 |

## 最强最近邻：触觉定位已经回答了什么

S2 把动作成本定义为完整 guarded move 的时间加上移动到起始位姿的固定时间；动作遇到接触即停，接触时间作为观测，“没有接触”也是合法结果。目标是最小平均或最坏成本达到信息覆盖阈值，而不是无条件增加感知。

其比较有值得继承、也必须修正的地方：

- 仿真中 IG、HP、WHP、随机方法共享同一初始粒子集与候选动作集；作者报告随机也明显降低不确定性，但后续动作选择会影响收益。简单人工动作对钻机较有效，对门把手较差。不能先验宣称选择策略必胜。
- 各自动方法选五个动作，人工固定序列只有三个。结果不能直接视为所有组完全等物理成本的试验；测量主要是粒子协方差下降，也不是 Shaka 的可信成功成本。
- Table I 单次选动作时间约为 IG 47.17 秒、HP 8.41 秒、WHP 25.70 秒。这是该论文当时的实现和实验设定，不能用于预测现代系统速度；它说明**决策计算成本可能抵消少触碰的收益**。
- 实机报告使用力矩阈值判定接触；在人工加入视觉偏差的门把手例子中，不定位则抓取落空，三种定位策略均用两次消歧动作后开门。这是有限实验结果，不是跨接触任务普遍保证。
- 保证依赖效用的单调性、自适应次模性等假设，模型还给定对象网格和姿态假设。不能把这些保证转移给开放世界 VLM 自报置信度，或转移给会损坏/移动对象的任意试探。

因此，“根据歧义挑选独立试验”需要先明确它新增了什么：若只是用另一个观察器替换接触模型，通常是工程迁移；若主张跨模型错误、真实接触和预算约束下的增量效果，必须实际检验，当前没有证据。

## 对新颖性与有效性的反例

1. **降低不确定性不等于提高任务决策质量。** S3 明确容纳不同奖励。一个观测可以降低与任务无关的熵，却不改变该做什么；新增成本仍真实存在。“歧义分数下降”不能作为成功指标。
2. **已有强代码代理可自行写循环、重观测和回退。** S7–S9 已有这些结构。因此必须让原始证据强基线使用同样工具并允许自发探测；禁止基线探测会人为制造增益。以上来源没有证明它们已实现本票完整选择策略，也不支持把它们说成没有闭环。
3. **事件减少不代表总成本减少。** S5 的触发条件可能需要持续监测；S2 有显著选择计算成本。视频全量读取后只上报少数摘要，不自动等于少计算；额外推理、监测、复位和失败重试要计费。
4. **模型条件可能比选择器更有价值。** S2 的已知网格、S8 的模拟器 mask、S9 的模拟器关键点/SDF 都会减少歧义。若只给实验组这些信息，就测不到策略本身的收益。
5. **一个新试验不能自动验证旧事件。** S4 的信念更新依赖状态转移与观测模型；物理探测会改变状态。第二次执行成功，不能倒推第一次瞬时接触已经成功。这个结论是本报告依据问题结构的推论，不是所列论文给出的 Shaka 实验结果。
6. **先例削弱“创新”但不证明“没有价值”。** S2/S3/S6 已覆盖机制与预算思想，却没有同一强模型下接触语义误验收的直接结果。合理剩余问题是受限经验假设，不是宣布新理论。

## 阅读与检索边界

本次沿作者项目页、期刊页面、作者 PDF、机构出版页和官方 GitHub 进行定向检索，并由 S1 的参考文献追到 S2 原始全文。上述成功读取的 PDF、项目页、README 和代码响应为 HTTP 200，且检查了正文标题或内容；没有把状态码当作阅读证据。S7–S9 源码来自读取当天的默认分支，未固定 commit、未运行，其能力结论限于列出的文件。

失败/排除记录：Bajcsy 1988 的尝试下载地址不可用；Howard 1966 与 Bayesian Experimental Design Review 的尝试入口不可读或被访问防护阻挡，故没有据此声称读过原文，信息价值论证改用实际读到的 S3。若干凭记忆检索的 arXiv 标识对应无关论文，核对标题后排除，没有作为证据。CMU 机构页的 `/storage/publications/…` PDF 链接返回 404；移除失效 storage 前缀后取得列出的作者 PDF，并核对题目和作者。

这不是全量系统综述，也不是截至 2026-10-15 的所有最新工作的穷尽检索。未核验更多 2025–2026 接触代理的覆盖情况、未读所有被引原作、未核查模型排行榜或断言某款模型最新；本附录不给任何模型版本优势背书。无需等穷尽检索才能否定“选择性触碰/按需触发/代码反馈循环本身新颖”，但要宣布候选差异无人做过，目前证据不足。
