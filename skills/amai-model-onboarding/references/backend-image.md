# 图片模型接入参考

## 适用范围与证据基线

- 图片模型、图片供应商适配、参考图参数或图片计费调整时读取。
- 本轮源码核查基线：`amai-server main@171e86591`，`2026-11-12`；实施时重新定位当前文件与符号。
- 当前仅完成源码核查，不据此证明人工接入、真实出图或对账通过。
- 具体 GPT Image2.5 映射、公式、默认值与历史特例集中在 [GPT Image2.5 案例](cases/gpt-image-2.5.md)，只在相关接入时读取。
- 路径均相对仓库根目录；交付范围、数据库操作与预算遵循主 [SKILL.md](../SKILL.md)。
- 自测及完成标准遵循 [verification.md](verification.md)；前端移交遵循 [frontend-handoff.md](frontend-handoff.md)。

## 当前链路入口

| 入口 | 当前职责 |
| --- | --- |
| `internal/pkg/llm/image_model.go` / `IimageAI`、`InitImageAI` | 价格键、提交、查询接口及静态 client 注册 |
| `internal/config/model.go` / `ModelConf` | 同步模式、参考图格式、批次数量、client 路由等 |
| `internal/logic/common/model_client.go` / `SelectImageClientInfos` | 候选供应商、模型别名和失败切换 |
| `internal/logic/model/listlogic.go` / `List` | YAML 模型目录与 DB 前端参数、语言和画布展示合并 |
| `internal/logic/image/createlogic.go` / `Check`、`llmGenImage` | 请求检查、批次规划与创建计费 |
| `internal/logic/image/creditslogic.go` / `Credits` | 前置费用预估 |
| `internal/logic/image/post_task.go` / `PostGenImageTask` | 同步/异步路径选择与提交 |
| `internal/logic/image/sync_queue.go` / `ConsumeItem` | 同步上游调用、候选切换与结果落库 |
| `internal/logic/image/queue.go` | 异步模型查询与结果处理 |
| `internal/logic/common/cost_config.go` / `IVCostConfig` | 图片/视频等共享价格入口 |
| `internal/logic/common/task_update.go` / `UpdateTaskByOID` | 任务状态、供应商与用量记录更新 |

## 先决定复用还是扩展

- 同协议、同供应商新增模型，先判断能否复用 client，只补模型配置、前端参数与价格。
- 新 provider 需实现 `IimageAI` 并注册；兼容既有 adapter 时优先复用，核对每个协议差异。
- 同一模型品牌不代表供应商协议相同；参考图编码、上传形式、返回格式及错误结构需逐项确认。
- 判断上游同步返回图片还是异步返回 TaskID，并据此核对 `is_sync` 和实现方法。
- 项目中的同步图片模型仍通过后台任务队列执行，不等于前端请求同步等待图片。
- 常规新模型复用 `/v1/image/task`、`/v1/image/task/credits`、`/v1/image/query` 与 `/v1/model/list`；完整路由按 [前端移交](frontend-handoff.md) 复核。
- 若需新 API，按仓库人工维护约定处理；不全量运行 `make api` 或 `goctl api go`。

## 最小改动触点

1. 固定 `model_id`、逻辑模型名、展示名、供应商模型别名和 client 名的对应关系。
2. 在指定开发环境 YAML 核对同步模式、参考图格式、批次数量、超时、开关与实际候选路由。
3. 复用或增加 provider 实现，并核对 `InitImageAI` 和供应商分派是否覆盖实际 client。
4. 核对 `ImageTaskCreateRequest`、保存的 payload、队列转换与 provider 请求，包括默认和缺省行为。
5. 需要 ModelID 特判时核对 `internal/types/llm_model.go`，不要假定每个模型都必须增加常量。
6. 如涉及尺寸、质量或 `@` 引用图 prompt，核对对应 types 与转换逻辑，不只修改 provider 目录。
7. 配置 `llm_model.config_detail` 的字段、选项、画布展示及语言覆盖，并检查后端消费结果。
8. 根据实际 `GetImageCostID` 配置价格记录；特殊公式同时核对代码分支、输入和单位。
9. 验证预估、创建、上游请求与结果落库；完成规定对账后再标记接入完成。

## 参数、展示与供应商适配

- `ModelConf.GetClientRefImageParamType` 支持 client 覆盖模型级参考图格式。
- 背景、比例、分辨率、质量等字段核对“前端文档—DB—队列转换—上游请求—计费”，包括未传值。
- 对照请求构造函数确认支持字段；上游文档列出了参数，不代表本项目已完整透传。
- 检查 `internal/types/video.go` / `GetPrompt`：该文件也处理图片模型的 `@` 素材引用。
- 除了模型 ID 是否进入分支，还要核对最终引用语法、素材编号与上传顺序。
- `List` 对 `canvas_show=true` 请求只保留 DB 中该字段为布尔 true 的模型；缺失、类型错误也会被过滤。
- `internal/pkg/i18n/config_detail.go` / `ApplyLocaleOverride` 做顶层覆盖；不要把它当作嵌套对象递归合并。
- 检查语言覆盖后的字段结构、展示名和画布入口，避免基础配置正确而特定语言或入口缺项。
- 检查首选与备用 client 的实际筛选逻辑，不能只按权重字面推断某供应商不会被调用。
- 同步结果需转换为项目可处理的图片结果；异步结果需完整提供查询与状态映射。

## 价格、生成记录与对账

- `IVCostConfig` 按逻辑 `model_name + conf_id + status` 查表；`conf_id` 来自 provider 的 `GetImageCostID`。
- ModelID、供应商别名与价格键职责不同；特殊 ModelID 分支可能覆盖数据库顶层价格。
- 预估与创建共享计费入口，但还涉及数量、批次基数和渠道折扣，需比较最终金额。
- 公式计费要验证实际采用的参数、默认值和取整，不只验证价格 JSON 可解析。
- 通用计费入口也被视频、音频和其他业务使用；公共逻辑修改应验证实际受影响路径。
- 追踪供应商返回的 usage 是否保存、保存到哪里、是否参与结算；“保存用量”不等于“按用量重新扣费”。
- 将平台成本、用户扣费、供应商 usage、实际采购扣款关联到同一测试任务和尝试记录。
- adapter 重试、外层候选切换产生的实际调用也纳入对账；无法关联的费用保持待核对。
- 未取得实际采购账单或扣款证据时，状态为未完成/待对账，不把源码或返回 usage 当作账单证明。

## 自测与移交证据

- 离线验证 YAML、model/client 关联、参数枚举、默认值、请求体、响应解析和价格公式样例。
- 可复用 `internal/config/config_load_test.go`；供应商相关测试按实际 adapter 选择。
- 计费变化重点验证缺参、auto、质量/尺寸、参考图数量、单价缺失和预估/创建一致性。
- 检查目标包的 `TestMain` 与测试副作用，不全量运行包含真实上游样例的测试包。
- 真实自测按本次能力覆盖文生图、图生图及必要参数，观察最终图片资产与价格记录。
- 同步/异步、provider 候选、错误/超时只验证本次涉及范围，并明确未覆盖组合。
- 对比生成记录与供应商后台的实际扣款，按 verification 保存四方对账证据和差异解释。
- 业务侧 Skill/专家团的模型配置只生成移交资料，不通知或写入另一服务。
- 移交明确模型身份、能力/参数、价格、验证与待处理项，不把更新本 Codex Skill 当作业务服务已同步。
- 记录实际请求参数、结果标识、测试结论和未验证项；不要用“提交成功”替代“出图及对账完成”。
