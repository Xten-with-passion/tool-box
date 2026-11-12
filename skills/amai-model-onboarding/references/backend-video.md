# 视频模型接入参考

## 适用范围与证据基线

- 视频生成模型、视频供应商适配、输入素材或视频定价调整时读取。
- 基线：`amai-server` 的 `test@e8c29e52`，核查日期 `2026-11-11`。
- 当前仅完成源码核查；未据此证明人工接入、真实生成或端到端自测通过。
- 路径均相对仓库根目录；实施时按符号重新读取当前模型与供应商的实现。
- 交付范围、数据库操作与调用预算遵循主 [SKILL.md](../SKILL.md)；验证遵循 [verification.md](verification.md)。
- 第一版交付止于后端开发、自测、对账及移交资料，不默认执行前后端联调、合并或部署。

## 当前链路入口

| 入口 | 当前职责 |
| --- | --- |
| `internal/pkg/llm/video_model.go` / `IvideoAI`、`InitVideoAI` | 价格键、提交、查询接口及 client 注册 |
| `internal/types/video.go` | 视频请求、payload、素材引用与部分模型规则 |
| `internal/logic/video/createlogic.go` / `Create` | 批次规划、价格计算及任务创建 |
| `internal/logic/video/creditslogic.go` / `Credits` | 视频费用预估 |
| `internal/logic/video/post_task.go` / `PostGenVideoTask` | 转换素材、选择候选、提交上游任务 |
| `internal/logic/video/query_task.go` / `QueryTask` | 查找已提交任务并发送查询队列 |
| `internal/logic/video/queue.go` / `ConsumeItem` | 查询状态、处理超时、下载视频并落库 |
| `internal/logic/cron/cron.go` | 定时触发视频提交与查询 |
| `internal/logic/common/cost_config.go` / `IVCostConfig` | 通用和模型特定的费用计算 |
| `internal/logic/model/listlogic.go` / `List` | YAML 模型目录与 DB 前端参数合并 |

## 先决定复用还是扩展

- 已有 provider 支持同协议的新模型时，先评估配置、参数映射和价格差异，不默认新建 SDK。
- 新 provider 需要实现 `IvideoAI` 的三个方法，并加入 `InitVideoAI` 的注册。
- 核对提交与查询是否共用鉴权、模型标识和状态结构；提交能成功不等于查询能复用。
- 当前主流程围绕异步 TaskID；若上游仅同步返回结果，应识别适配缺口，不照搬 GPT 图片流程。
- 文生视频、首尾帧、多参考图与多模态参考可能共用外部入口，但转换和计费分支不同。
- 常规模型复用 `/v1/video/task`、`/v1/video/task/credits`、`/v1/video/query` 与 `/v1/model/list`；完整路由按 [前端移交](frontend-handoff.md) 复核。
- 若确需扩展 API，遵守仓库人工维护约定；不全量运行 `make api` 或 `goctl api go`。

## 最小改动触点

1. 确定 `model_id`、逻辑名称、前端展示名、供应商别名与 client 的对应关系。
2. 在指定开发环境 YAML 核对路由、OEM 分组、超时、批次、禁用开关与模型能力。
3. 在 `llm_model.config_detail` 中描述本次能力、参数选项、默认值与素材数量/类型约束。
4. 核对 `VideoTaskCreateRequest` 到保存 payload、再到 `LlmVideoTaskCreatePayload` 的完整传参。
5. 实现或复用 provider 的提交/查询、状态映射、错误分类和生成结果转换。
6. 如涉及引用素材或 prompt 语法，检查 `internal/types/video.go` 与素材转换逻辑。
7. 从实际 `GetVideoCostID` 生成应覆盖的价格组合，不手猜统一价格键格式。
8. 配置价格表并核对是否有按秒、token 或 ModelID 特定公式覆盖数据库顶层价格。
9. 验证预估、创建、提交、查询、终态与资产落库，并整理后端交付证据。

## 请求与异步生命周期

- `post_task.go` 转换首尾帧、参考图、视频、音频等素材，再构造供应商 payload。
- `clientInfo.ModelName` 可覆盖 YAML 逻辑模型名用于上游请求，不能据此改写价格查询键。
- 提交失败按候选列表切换；成功后通过 `UpdateTaskSubmitted` 保存 client 与上游 TaskID。
- 查询阶段使用任务保存的 `AccountId` 选择原供应商，不重新按权重选择查询 client。
- `QueryTask` 将已提交任务送入队列，`ConsumeItem` 调用 `QueryVideoTask` 并处理终态。
- 临时错误、最终错误、等待中和超时需要映射到现有语义，不能统一视为成功或统一重提。
- 成功结果经 `DownloadVideo` 下载/转存、写入资产并更新任务状态，才能证明生成闭环完成。
- 后端自测要确认开发环境的任务提交/查询机制运行，不仅直接调用 SDK 方法。

## 价格键与计费分支

- 预估和创建从 provider 的 `GetVideoCostID` 得到 `conf_id`，逻辑 ModelName 作为 `model_name`。
- `IVCostConfig` 首先查启用记录，再处理按秒与模型特定公式，最后应用渠道折扣。
- 火山普通视频基线使用 `t2v/i2v + resolution + duration` 组合键。
- 火山 Seedance 基线按 resolution 与是否含参考视频生成价格键，随后走 token 估算。
- Wan2.7 及以上的百炼实现基线使用 `model_name + resolution`，Wan2.2 走另一种组合。
- 对每个模型只输出代码实际可能生成的价格键，逐项验证支持参数不会落到缺失价格记录。
- 同时核对时长单位、声音、参考视频输入、生成数量和批次基数对费用的影响。
- 价格来源不足时按主 Skill 处理，不能从相似模型或展示单价推定采购价。

## 基线特例：实施时重新核对

- Seedance 单价在 `types.Seedance_*_MillionTokenCostMap`，由 `CalSeedanceCost` 选择并计算。
- 该路径仍先经过数据库价格记录查询；“公式覆盖单价”不等于可以不配置价格记录。
- 仅写 `cost_config` 不能保证改变 Seedance 实际计费，应检查当前代码是否仍采用此路径。
- `ModelConf.CostTypeSecondsN` 将数据库规格单价乘以时长，不能同时填整段价格再重复乘秒。
- provider 内部可能按逻辑模型名或 ModelID 区分提交/查询协议，新增供应商别名时需检查分支命中。
- 这些是当前实现的检查线索，不是永久的模型定价或协议规则。

## 自测与完成证据

- 离线先验证配置、请求转换、素材顺序、价格键矩阵、公式和供应商状态映射。
- 可参考 `internal/config/config_load_test.go`、`internal/types/video_test.go`。
- client 路由与别名验证参考 `internal/logic/common/model_client_test.go` 的 `TestSelectVideoClients_*`。
- provider 响应解析可参考 `internal/pkg/llm/doubao/xiaren/video_test.go` 中的 JSON 解析测试；同文件也有真实调用。
- `internal/logic/video/main_test.go` 初始化 MySQL、Redis、OSS 和队列，不能视作纯离线测试。
- `internal/pkg/llm/main_test.go` 及若干 provider `TestMain` 加载 local 配置，运行前检查副作用。
- 不全量执行这些包；按 verification 选择具体离线测试和开发环境用例。
- 真实自测按本次能力覆盖输入模式、参数与价格，完整观察 TaskID、原 client 查询、终态和资产。
- 保存费用预估与实际任务价格的比较，记录失败/超时结果及未覆盖的供应商或参数组合。
- 人工跑通案例由后续案例资产沉淀；本参考本身不是已经跑通的证明。
- 平台成本、用户实际扣费、供应商用量和实际采购扣款均有证据并核对通过，才可标接入完成；账单或对应关系缺失则保持待对账。业务 Skill／专家团只生成移交资料，具体要求见 [verification.md](verification.md)。
