# GPT Image2.5：代码核查参考案例

## 证据范围与状态

- 此案例用于说明接入触点、跨层契约与待验证项，不是已人工跑通的成功案例。
- 源码核查：`amai-server main@171e86591e9b387bc6b11b2ea970b2319a61fa3b`，`2026-11-12`。
- 核查时用户已有 `internal/logic/image/createlogic.go` 未提交排版改动及未跟踪 `.agents/`；均未修改。
- 目标 GPTProto 包、计费函数、ModelID、尺寸/质量表相对旧基线 `test@e8c29e52` 无 committed diff；下述两段 YAML 逐段比较也未变化。
- [流程文档《模型》](https://yanyanjiemo.feishu.cn/wiki/UUxDwbXDKisI6bk8GHvctwXMnPc)：revision `331`，document ID `HJ85dTBpnorJLMxyhcTcpYainLb`。
- [接口样例《GPT Image2.5 图片模型》](https://yanyanjiemo.feishu.cn/wiki/U30Dw40dXi39MkkV8OHcuofynSh)：revision `272`，document ID `EE0sd3JnGoh71NxsYIqcmqsGnJf`。
- 文档用于解释本次样例与流程；历史报价只能说明结构，不能充当当前采购价、预算或实际扣款依据。
- 本轮未改业务代码/数据库，未发起真实调用，未取得供应商账单；总体状态：**未完成，待真实自测与对账**。
- 路径相对仓库根目录，行号仅用于定位本次基线；未来按文件、符号与模型 ID 重新核对。

## 一、用户指定的模型与文件映射

| 项目 | Flare | Sunburst |
| --- | --- | --- |
| YAML 位置 | `config/amai-api-dev.yaml` 的 803–832 行模型段 | 同文件 833–862 行模型段 |
| `model_id` | `01M2MBMJHW93TADDK1D87ST8SA` | `01M2Q6TDPH53FXJTWQ1VBMB19V` |
| 逻辑 `model_name` | `gpt-image-2.5-flare` | `gpt-image-2.5-sunburst` |
| 展示名 | `GPT Image 2.5 Flare` | `GPT Image 2.5 Sunburst` |
| ModelID 常量 | `types.ModelIDGptImage2_5Flare` | `types.ModelIDGptImage2_5Sunburst` |
| 计费 SQL 的 `model_name` | `gpt-image-2.5-flare` | `gpt-image-2.5-sunburst` |
| 计费 SQL 的 `conf_id` | `i2i` | `i2i` |
| Maas 上游别名 | `gpt-image-2.5-flare-pool` | `gpt-image-2.5-sunburst-pool` |

两常量定义在 `internal/types/llm_model.go`。它们既对应 YAML/DB 模型身份，也用于选择 GPT2.5 计费系数；**ModelID 不是这里的 SQL `conf_id`**。

两段 YAML 的共同值：`vendor_name: GPT`、`is_sync: true`、`disable: false`、`model_disable: false`、`once_gen_image_num: 1`、`timeout_failed_minutes: 5`、`min_eta: 1`、`max_eta: 3`、`modality: image`、`type_tags: [image]`、`cost_type: 2`；`group_sort` 分别为 601、602。

`clients.default` 中均为：`gptproto_gpt` 权重 100；`we2ai_gpt`、`maas_gpt` 权重 0；三个 client 的 `ref_image_param_type` 均为 1（URL）。GPTProto 没有单独覆盖模型名，使用逻辑模型名；We2ai 覆盖为同名；Maas 使用上表的 `-pool` 别名。

| 必查代码 | 关键符号与作用 |
| --- | --- |
| `internal/pkg/llm/image_model.go` | `InitImageAI` 注册 `gptproto_gpt`、`we2ai_gpt`、`maas_gpt` 等 |
| `internal/pkg/llm/gptimage/client.go` | `New` 将 GPTProto/We2ai 分派到 gptproto，Maas 分派到 wanjie |
| `internal/pkg/llm/gptimage/gptproto/client.go` | `GetImageCostID` 固定返回 `i2i`，`PostGenImageTask` 调用 `GenImage` |
| `internal/pkg/llm/gptimage/gptproto/image.go` | 请求转换、上传、同步响应、usage 与重试 |
| `internal/logic/common/cost_config.go` | `IVCostConfig` 查表并按 ModelID 调 `CalGptImage2Cost` |
| `internal/types/gpt_image.go` | 尺寸表、两代质量系数和每参考图 token 常量 |

## 二、请求与结果闭环

1. 前端读取模型列表并提交 `/v1/image/task/credits` 或 `/v1/image/task`，以产品 `model_id` 选模型；本 Skill 可直接从后端发请求验证，不依赖前端实现。
2. `Credits` / `CreateLogic.llmGenImage` 用逻辑模型名与 `GetImageCostID` 查价并计算本次费用；创建时规划批次、保存任务和扣费数据。
3. `PostGenImageTask` 发现 `is_sync=true`，进入同步生成队列；这仍是后台任务，不是前端 HTTP 请求同步等待出图。
4. `internal/logic/image/sync_queue.go` / `ConsumeItem` 读取素材、处理 prompt、选 client、转换参考图，构造 `LlmImageTaskCreatePayload`。
5. GPTProto 无参考图时 POST `/v1/images/generations`，JSON body 包含 model/prompt/size 以及已提供的 quality/background。
6. 有参考图时 POST `/v1/images/edits`；`refimage.DownloadAll` 下载 URL，multipart 表单使用 `image[]` 上传文件，其他字段由 `SetFormData` 设置。
7. `GenImage` 从 `response.Data` 优先提取 `b64_json`，没有该值时取 URL，返回 `ImagePostTaskData{IsAsync:false}`。
8. 同步队列下载/转存图片、写资产并更新成功状态；`QueryImageTask` 在该 adapter 内返回 nil，不用于这条同步路径。

请求构造入口是 `internal/pkg/llm/gptimage/gptproto/image.go` / `buildGenImageRequest`：size 由 resolution/ratio 映射；quality 非 nil 才透传；background 从 `params` 取值。定义了字段类型不等于全部字段被实际发送，应以该函数与调用处为准。

## 三、价格查找、公式与默认值

`IVCostConfig` 先查询启用的 `cost_config`：`model_name = 逻辑名称`、`conf_id = i2i`。随后用两种 GPT2.5 ModelID 命中特殊分支，调用 `CalGptImage2Cost`；该函数读取 `config_detail.uncached.default_range.input/output` 中的 `cost_price` 和 `sale_credits`。

四项单价有任意一项为 0 时当前代码报配置缺失。数据库顶层价格可被此公式结果覆盖；仅检查顶层 `cost_price/sale_credits` 不足以验证实际生效价格。`cost_type:2` 的附加输入图片分支当前已注释，并非 GPT 公式的启用开关。

| 质量 | GPT Image2.5 系数 q | GPT Image2 系数（仅用于区分） |
| --- | ---: | ---: |
| low | 16 | 16 |
| medium | 24 | 48 |
| high | 48 | 96 |
| xhigh | 64 | 不在该系数表 |
| max | 96 | 不在该系数表 |

代码中的估算公式：

```text
输入 token = 参考图数量 × 1536
短边系数 = round(q × min(width, height) / max(width, height))
输出 token = ceil(q × 短边系数 × (2,000,000 + width × height) / 4,000,000)
平台公式成本 = 输入 token / 1,000,000 × 输入成本单价
             + 输出 token / 1,000,000 × 输出成本单价
公式销售积分 = ceil(输入 token / 1,000,000 × 输入销售积分单价
                 + 输出 token / 1,000,000 × 输出销售积分单价)
```

随后 `IVCostConfig` 应用渠道成本/售价系数，创建逻辑按数量与批次基数计算任务金额；对账时分别解释折前、折后与最终扣费，不能将以上中间值直接等同供应商扣款。

| 场景 | 费用估算 | 实际请求转换 |
| --- | --- | --- |
| 明确 resolution 和有效比例 | 从 `types.GptImage2SizeMap` 选尺寸 | GPTProto 使用自己的 `sizeMap` 选尺寸；两张表应保持一致 |
| 明确比例 `auto` | 遍历所有清晰度/比例，选输出 token 最大的尺寸，不局限所选 resolution | 发 size=auto |
| 比例字段未传 | 费用函数按空比例走最大 token 策略 | 同步队列先将空比例改为 1:1；若同时有 resolution，上游得到对应 1:1 尺寸 |
| resolution 未传 | 费用函数默认 4K | provider 默认 size=auto |
| quality 未传 | 费用函数默认 high | provider 不发送 quality，最终取上游默认 |

`CalGptImage2Cost` 附近注释仍写 2K/medium，与执行值不一致。本轮只记录差异，未裁决或修改业务默认值。显式 auto、未传字段和前端默认选择必须分开验收；不能据此直接断言显式正常传参路径有错。

样例中的质量、background 及尺寸约束用于核对能力契约；当前 provider 按预设尺寸表请求，通用 Width/Height 字段并未在该请求构造函数用于生成任意尺寸。不能因上游支持任意尺寸就声明项目已支持。

## 四、流程新增检查：`@`、画布与多语言

- `internal/logic/image/sync_queue.go` 在 MetaList 或 RefText 非空时调用 `types.GetPrompt`，再执行后续 prompt 处理。
- `internal/types/video.go` / `GetPrompt` 的模型允许分支包含 Flare 和 Sunburst，但 `{{Image N}}` 专门格式只命中 `ModelIDGptImage2`。
- 两个 GPT2.5 ID 当前走通用 `JimengMetaTypeMap[素材类型] + (MaterialIdx+1)`；需以确认的模型契约验证语法和素材顺序，不直接复制 GPT2 的语法。
- `GetPrompt` 对多模型请求有返回原 prompt 的分支；它不构成“禁止模型多选”的产品依据。流程文档已删除线标记的旧限制不得恢复成新要求。
- `internal/logic/model/listlogic.go` 从 YAML 模型目录读取 `llm_model.config_detail`；因此只加数据库记录不等于完整模型入口可见。
- 请求 `canvas_show=true` 时，config detail 必须有布尔 true 的 `canvas_show`，缺失、false 或字符串值均不通过该过滤。
- `internal/pkg/i18n/config_detail.go` / `ApplyLocaleOverride` 按 locale 做顶层覆盖，然后清除语言键；它不递归合并嵌套字段。
- 验证普通/画布入口及语言覆盖后的展示名、字段结构和参数选项，避免翻译块覆盖后漏掉必要配置。

## 五、候选供应商与实际调用次数

- `internal/logic/common/model_client.go` / `buildRestCandidates` 会剔除首选、排序、去重，但不排除权重 0 的 client。
- 因此当前两段 YAML 的 we2ai/maas 可能在 GPTProto 失败后被尝试；权重 0 不是禁用开关。
- `internal/pkg/llm/gptimage/gptproto/image.go` 的 adapter 单次 `GenImage` 最多尝试 3 次；部分网络错误和空 data 会进入重试。
- 外层同步队列还会切换候选 client；多张图片又可能分成多项任务。不能用“业务请求数”直接代表采购调用数。
- 当前 `response.Error` 会先直接转换为 FinalError 返回；后面的 `MatchError` 分支不是这一情况的实际处理路径。
- 自测前沿实际路由确定可能调用哪些供应商、参数和重试；预算与调用授权遵循主 Skill，不在此复制规则。

## 六、用量保存与四方对账

`internal/pkg/llm/gptimage/gptproto/image.go` 将上游 `Usage.TotalTokens` 和完整 usage JSON 放入 `ImagePostTaskData`。`internal/logic/image/sync_queue.go` 将其传给 `common.UpdateTaskByOID`，最终写 `task_message_output.account_id`、`total_tokens` 与 `usage_detail`。

创建时的 `credits`、`cost_credits`、`original_credits`、`original_cost_credits` 来自前置估算。上述成功更新函数没有用实际 usage 重新计算这些金额；**保存供应商 usage 不等于按 usage 重新结算用户或平台价格**。

| 对账项 | 需收集的证据 | 当前案例状态 |
| --- | --- | --- |
| 平台成本 | 价格配置、公式输入、渠道系数与任务 `cost_credits/original_cost_credits` | 只确认代码路径，未取得实测记录 |
| 用户扣费 | 报价、任务 `credits/original_credits` 与实际扣费流水 | 未实测 |
| 供应商 usage | 实际 response、`total_tokens/usage_detail` 与所用 client | 只确认保存路径，未实测 |
| 实际采购扣款 | 供应商后台账单/扣款，含失败、重试与候选切换的费用 | 未取得，待对账 |

对账关联同一模型、参数、时间、client、MsgOID 及可用的供应商请求标识。当前 GPTProto 响应结构未见稳定供应商 request ID 落库，不能承诺仅靠 MsgOID 自动一对一匹配后台记录；无法关联的扣款保留待核对。

商务确认的价格仍需开发再次核对币种、单位、计费维度与生效条件。实际账单未取得或四方差异未解释时，接入状态保持未完成/待对账，不能以返回 usage 或文档价格代替。

## 七、业务 Skill/专家团移交与后续验证

- 流程第 10 步的 Skill 指业务侧 Skill/专家团，不是本 Codex Skill。
- 仓库 `internal/logic/skill/skilllistlogic.go` 经 `skill.Client().TeamList` 读取独立服务模型；`internal/pkg/skill/list2.go` 与业务创建逻辑也消费其专家模型配置。
- 本任务只生成移交资料，包含上述模型身份/别名、参数能力、价格依据、验证与待对账状态；不通知或写入另一服务，不标记对方已经上线。
- 离线验证应覆盖两份尺寸表、质量系数、缺参/auto、价格键、请求 JSON/multipart、响应解析及 `@` 引用顺序。
- 可参考 `internal/config/config_load_test.go`、`internal/pkg/llm/gptimage/qiniu/image_test.go`、`internal/pkg/llm/gptimage/refimage/refimage_test.go`；七牛请求测试不能替代 GPTProto 实际协议测试。
- 当前案例未执行上述离线测试或真实自测；后续真实测试应通过业务 API 观察最终图片资产、用量、扣费与供应商采购账单。
- 人工实际操作、失败原因、四方对账和最终确认另按案例记录资产追加，不反向把本代码核查升级为人工通过。
