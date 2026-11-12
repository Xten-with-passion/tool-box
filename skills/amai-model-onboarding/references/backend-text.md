# 文本模型接入参考

## 适用范围与证据基线

- 文本模型、已有文本模型参数调整，或文本模型供应商切换时读取。
- 基线：`amai-server` 的 `test@e8c29e52`，核查日期 `2026-11-11`。
- 当前仅完成源码核查；没有据此证明人工接入、真实调用或端到端自测通过。
- 路径均相对仓库根目录；实施时按文件与符号重新定位，不假定当前分支仍与基线相同。
- 第一版交付范围、数据库操作与调用预算遵循主 [SKILL.md](../SKILL.md)；验证遵循 [verification.md](verification.md)。
- 本参考止于后端开发交付，不把前后端联调、合并或部署视作必做步骤。

## 当前链路入口

| 入口 | 当前职责 |
| --- | --- |
| `internal/pkg/llm/text_models.go` / `InitTextModelClient` | 从 `TextModelClients` 初始化 client map |
| `internal/pkg/llm/openai.go` / `NewOpenAI` | 根据 API URL 与凭据创建 OpenAI SDK client |
| `internal/pkg/llm/model_init.go` / `InitModels` | 用 YAML `model_id` 建立逻辑模型目录 |
| `internal/config/model.go` / `ModelConf` | 模型名、client 分组、上下文、输出与多模态能力配置 |
| `internal/logic/model/listlogic.go` / `List` | 合并 YAML 模型目录与 `llm_model.config_detail` 返回前端 |
| `internal/handler/chat/streamhandler.go` / `StreamHandler` | 解析请求并输出 SSE |
| `internal/logic/chat/streamlogic.go` / `Stream`、`llmRequest` | 构造上下文、调用上游、处理流与保存输出 |
| `internal/logic/chat/resumestreamlogic.go` / `ResumeStream` | 根据已缓存事件恢复读取 |
| `internal/logic/common/chat.go` / `ChatTotalCredits` | 按实际 usage 查询与计算价格 |
| `internal/logic/common/chat.go` / `ChargeModelTokenUsage` | 扣减文本用量对应积分 |

## 先决定复用还是扩展

- 同一供应商、同一 Chat Completions 协议的新模型，先判断能否只增加 YAML 与数据库记录。
- 已有 client 的 API URL、凭据和请求协议符合要求时，复用 client，不另建同名封装。
- 新供应商兼容现有协议时，通常增加 `TextModelClients` 项与模型的 client 路由即可。
- “OpenAI 兼容”需核对具体字段、SSE 事件与 usage，不能仅凭接口路径或宣传认定。
- 不兼容的请求字段、鉴权、流事件或用量返回，需要针对性适配；先说明现有路径的具体缺口。
- 当前入口是 `Chat.Completions.NewStreaming`；只提供 Responses 或私有协议的模型不能直接套用。
- 普通模型接入复用 `/v1/chat/stream`、`/v1/chat/resume-stream` 与 `/v1/model/list`，不默认新增接口；完整路由按 [前端移交](frontend-handoff.md) 复核。
- 如确需扩展 API，遵守仓库 `CLAUDE.md` 的人工维护约定，不全量运行 `make api` 或 `goctl api go`。

## 最小改动触点

1. 确定产品 `model_id`、逻辑 `model_name`、前端展示名和供应商模型名的对应关系。
2. 在指定开发环境 YAML 中核对 `Models` 与 `TextModelClients`；凭据按项目现有方式提供。
3. 核对 `clients.default` 及本次涉及的 OEM 分组、权重和 client 模型别名。
4. 根据真实支持能力设置 context/output token 上限、temperature、vision/video 与输入格式。
5. 将前端字段、选项、默认值和能力说明落到对应的 `llm_model.config_detail`。
6. 核对 `ChatStreamRequest` 与 `llmContext` 是否能承载这次参数；有缺口时再修改类型或转换。
7. 核对实际流响应是否能解析正文、思考内容、结束事件与 usage；仅修改本次不兼容之处。
8. 配置 `cost_config` 后验证价格查询、usage 归一化和扣费，再形成开发交付证据。

## 价格键与用量契约

- `ChatTotalCredits` 以 YAML 逻辑 `ModelName` 同时匹配 `model_name` 与 `conf_id`，并筛选启用状态。
- 上游请求可由 client 的 `model_name` 覆盖；供应商别名不自动改变计费键。
- `config_detail` 解析为 `types.TextModelPricingConfig`，含 `cached`、`uncached` 与默认/分时价格。
- `types.CalcPrice` 按百万 token 单价缩放；单位、积分换算与取整必须从当前实现和定价要求核对。
- 实际价格还会经过渠道折扣；默认渠道与本次涉及 OEM 的验收要分别说明。
- 新供应商必须确认 usage 字段能落到 `internal/types/llm.go` 的 `Usage`，不能只验证正文生成。
- 价格来源缺失时按主 Skill 处理，不根据相近模型猜定价。

## 流式生命周期需要保留的行为

- `llmRequest` 从 `SelectChatClientInfos` 获取候选，并使用候选的供应商模型别名。
- 连接失败或尚未收到首块即失败时可以切换候选；已输出内容后的错误应按当前错误路径收尾。
- SSE 内容经 `sendStreamEventWithAppendCache` 缓存，供恢复接口按 `event_id` 继续读取。
- 当前 `NewStreamLogic` 使用保留请求值的独立超时上下文；用户断线不等同于上游立即取消。
- 正常流结束后调用 `ChatTotalCredits` 和扣费函数，并保存输出、usage 与价格记录。
- 新模型需要验证上述行为是否适用，不因新增模型顺手重构整个流式生命周期。

## 基线特例：实施时重新核对

- 请求当前发送 `MaxCompletionTokens`、`IncludeUsage` 和 `ReasoningEffortHigh`；新模型可能不接受这些字段。
- `ChatTotalCredits` 在 `TotalTokens == 0` 时返回零费用；需区分真实零用量与 usage 未解析。
- 基线对 `PromptCacheHitTokens` 调用 `CalcPrice` 时也传入 `isCached=false`。
- 因此配置了 `cached` 不代表这条业务路径会使用缓存价；若本次要求差异缓存计费，应明确验证并处理。
- `llmContext` 会结合 context/output 上限裁剪历史；长上下文能力不能只填展示参数。
- 上述是当前实现事实，不应在 Skill 中固化成所有后续模型都必须沿用的产品规则。

## 自测与完成证据

- 离线先验证 YAML 加载、ID/别名映射、价格 JSON、请求字段和模拟 SSE/usage。
- 可复用 `internal/config/config_load_test.go`、`internal/types/cost_config_test.go`。
- 路由参考 `internal/logic/common/model_client_test.go` 的 `TestSelectChatClients_*`。
- 多模态消息参考 `internal/pkg/chat/extended_message_test.go`；有输入能力变更才扩大相关验证。
- `internal/pkg/llm/main_test.go` 会加载 local 配置并初始化数据库；同目录 `openai_test.go` 含真实调用样例。
- 不将全量 `go test` 当作安全的离线验证，按 verification 选择具体目标。
- 真实自测在指定开发环境验证正文/思考、结束事件、usage、计费记录及本次涉及的错误或恢复行为。
- 交付记录区分已通过、失败与未运行；供应商组合或参数组合未实测时明确列出。
- 平台成本、用户实际扣费、供应商用量和实际采购扣款均有证据并核对通过，才可标接入完成；账单或对应关系缺失则保持待对账。业务 Skill／专家团只生成移交资料，具体要求见 [verification.md](verification.md)。
