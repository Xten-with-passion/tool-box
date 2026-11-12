# 人工接入流程与 Skill 检查项

依据用户指定的[模型接入流程](https://yanyanjiemo.feishu.cn/wiki/UUxDwbXDKisI6bk8GHvctwXMnPc)（文档标题“模型”，revision 331）。它描述完整上线流程；本 Skill 沿用已确认的后端开发边界，不据此取得部署、通知或其他服务的写权限。

另一份[GPT Image 2.5 接口文档](https://yanyanjiemo.feishu.cn/wiki/U30Dw40dXi39MkkV8OHcuofynSh)（revision 272）用于校准交付格式和图片案例。只读取了这两份文档，没有将其中其他文档链接、嵌入 Sheet 或截图 alt 当作已核验依据。

| 原流程步骤 | 本 Skill 的具体检查与产物 | 主要位置 |
|---|---|---|
| 1. 供应商价格确认：商务先确认，开发再次确认 | 分别记录商务报价来源与接入时复核结果；比较渠道/型号/单位/折扣/有效性，冲突再问，不自行决定售价 | [数据库与计费](database-pricing.md)、接入记录 |
| 2. 价格配置 cost_config | 用当前代码产生的键和真实计费源生成差异，查单位/公式/取整，执行后回读 | database-pricing.md、对应模态参考 |
| 3. 参数配置 llm_model | 记录 UI 字段→平台请求→provider 映射，默认/缺参/显式 auto 分开验证 | [前端移交](frontend-handoff.md) |
| 4. 禁止模型多选配置（原文已划掉） | 记为已废弃流程项；不要求新增该配置，也不据此更改现有请求校验或专家团单模型限制 | 案例说明，不新增必做操作 |
| 5. @ 功能配置 GetPrompt | 核查 YAML At、源码例外、引用替换语法、素材索引与实际发出的 prompt | 对应模态参考、图片案例 |
| 6. 是否开启画布展示 canvas_show | 明确本模型是否展示，检查生效值为 bool；普通列表和 canvas_show=true 的列表按约定返回 | frontend-handoff.md、参数校验脚本 |
| 7. 多语言配置 | 核对目标语言的名称、标签、枚举语义、默认值和画布可见性；按浅覆盖规则验证完整 field_map | frontend-handoff.md、database-pricing.md |
| 8. 供应商配置 | client/provider、鉴权引用、别名、路由/OEM、备用候选、素材格式、重试边界相互一致 | 对应模态参考 |
| 9. 生成记录与供应商后台对账 | 核对平台成本、用户实际扣费、供应商 usage、供应商实扣；无账单或差异未解释则未完成/待对账 | [验证与对账](verification.md) |
| 10. 通知 Skill 上线模型配置 | 用户已明确指业务侧 Skill/专家团；本版生成移交资料和待办，不发消息、不同步该服务、不标记已上线 | verification.md、接入记录 |

步骤编号用于追溯人工清单，不机械要求代码、文档、价格配置串行执行；按真实依赖安排，缺一项时继续独立部分。各项可记通过、待确认、未执行、失败或有依据的不适用；不能统一将整个案例标成通过。

## @、画布和多语言的现有入口

以当前仓库按符号复核，不能把下列基线当成永久行为：

- `internal/config/at_config.go::AtConfig`、`internal/config/model.go::ModelConf.At`：显式开关只是入口之一，`internal/types/video.go::GetPrompt` 还有 ModelID 例外及格式分支。
- `GetPrompt` 被图片同步/异步、视频提交及业务 Skill 创建调用；只检查常量列表不足以证明引用顺序与格式正确。
- `internal/logic/model/listlogic.go::List` 先应用语言覆盖再过滤画布；canvas_show 缺失、非 bool 或 false 均不能进入要求画布展示的结果。
- `internal/pkg/i18n/config_detail.go::ApplyLocaleOverride` 是顶层覆盖；locale 的 field_map 替换 root 同名对象，不做递归继承。
- 展示名有 YAML 默认与 JSON 覆盖，需验证实际返回。是否展示由本次产品要求或可核查的既有约定确定，不一律开启。

## 将人工事实沉淀为规则

使用[接入记录](../assets/case-record.md)中的步骤对照，每项记录“人工实际做法→代码/配置位置→验证范围→偏差→拟修订位置”。已核查的 [GPT Image 2.5 案例](cases/gpt-image-2.5.md)展示这种证据组织方式，但不是本 Skill 真实执行或供应商账单对账通过的证明。

修订时替换失效内容并保留来源/适用范围，避免在多个文件反复追加旧默认值。跨模态通用规则有相应依据才提升；GPT2.5 的质量系数、尺寸表、路由、计费键保留在该案例内。
