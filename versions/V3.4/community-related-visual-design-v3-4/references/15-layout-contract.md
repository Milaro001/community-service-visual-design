> **细则档案**：日常制作按 SKILL.md 和 stage-1～5 阶段卡执行，本文件只在排错或阶段卡没写到的特殊情况时查阅。与阶段卡冲突时以阶段卡为准。当前版本的变化：开工先选常规/快速模式；主题字常规3款（2横＋1竖）、快速2款；正文派生后直接排版，不单独确认；排版只做普通字体初排一次审查；不做配色A/B；不写检查记录，只维护 state.md；参考库现为布局155份（新增C组横版敬老8张）、字体TG01–TG65。

# 排版验收契约

## 约束归属与阶段

优先级：当前用户要求/已选状态→内容保真、受众可读性和画布→本技能通用规则→适用风格→第三方启发。评分不能删事实、改号码/语言/画布、缩主体或推定发布授权。

唯一硬项来源：母本/证据[02](02-master-copy-rules.md)、语言[03](03-line-parity.md)、位置/真实留白/主体保护[10](10-position-and-whitespace.md)、文字库实际匹配[24](24-type-generation-references.md)、当前设计偏好[25](25-mandatory-design-preferences.md)、全量艺术字与适用图标实际入图/许可[18](18-full-art-type-and-required-icons.md)、正文/日期/语义小标题[21](21-body-type-size-and-spacing.md)、换行/序号/净空[26](26-linebreak-and-whitespace.md)、实际编号总览[22](22-selection-overview.md)、新底图3款覆盖[29](29-background-style-and-position-coverage.md)、精修配色/局部对比[19](19-final-color-and-readability.md)、导出规格[08](08-thinking-prompts.md)。未设置机构/Logo不扣品牌分或补造。

按[13](13-layout-workflow.md)分两次实际审查：首次仅查清楚字体内部初排适用的文本、容量、几何、层级和保护；尚未生成的艺术字、未发生选择/配色保持待执行/unknown，不阻断初排。第二次查生成资产和实际合成，每语言每候选独立判断，初审通过不传递为终审通过；最终交付查全部适用硬项。

## 状态、证据与工具边界

每项初始unknown，记录`check_id / applies / status / evidence / asset_version / measured_value / threshold / repair / dependencies`。状态仅`pass / fail / unknown / not_applicable`；不适用须给当前原因，工具受限或缺证据是unknown，不能自动通过。

证据绑定实际成图文件/版本。计划、提示词、名义字号、源文和focal标签不证明渲染；OCR/模型可能误判，数字、否定、条件和号码结合母本逐项核对。副本比对不证明画面显示；bbox须含真实完整字形/描边/投影，不只量透明框。

有真实测量可按[17](17-layout-measurements.md)用`check_layout.py`检查提交的几何、容量、最小尺寸、颜色样本；它不读图、不做OCR或评价审美，也不证明全背景覆盖。换行记录/像素检查分别按26/19的输入边界；无代码按同一契约看图并记限制。目标尺寸实际检查和当前版本回归见[20](20-internal-review-and-current-state.md)，AI看图不冒充真人/印刷验证。

硬项记录保留既有ID并新增`layout_reference_survey_current`：绑定09模块当前完整库版本、实际看完的巡览页/源图及未读项；未读/看不清结构未补看则unknown，默认3条短名单不证明全库阅读。其他项：`type_library_match_and_context_fusion_current`绑定当前用途的TG编号/子图、实际查看、提取与情境融合、提示/资产；它只证明设计依据，生成和渲染另查。`type_pair_approval_current`绑定当前主题字/正文字组版本、实际同图合览和用户明确满意/下一步答复；缺批准不能进入完整排版。`background_candidate_set_current`绑定当前3张底图、风格/位置覆盖及A–C总览；后续引用已选底图记录，不重复生成。

`no_unapproved_body_panels`保留历史ID，按10当前正文承托授权检查；形状本身不判失败，也不需要额外框形批准，当前用户明确禁止的处理才按其要求判定。`localized_background_softening_current`仅在当前版实际采用环境淡化/柔化时适用，按25绑定周边处理范围与主体/视觉中心保护证据；中心被模糊、整图减透明度或处理侵入主体判失败，没有采用则记not_applicable及原因。`subject_preserved`同时检查相对画布的主图尺度/宽高比/完整轮廓，不能只看是否还在图中。图文可读性仍由局部对比、视觉阅读、容量及主体保护项独立核验，不能用这两项替代。

## 修复与回归

先修根因：容量不足重排；图底冲突利用真实留白并按10/25处理实际覆盖区；字形错误定向修复；真实遮字恢复图层。不以删锁定文案或缩小正文/主体掩盖。两轮同策略失败按18更换拆分/排版/生成策略，仍失败保留失败/未验证，不退回普通字体或无图标成稿。

修改文本、字体/行距、生成资产、描边、位置、背景、缩放或输出时仅重查受影响依赖，证据绑定新版本；未变且可核对的记录复用。最终导出每语言仍实际打开查看。缺生成证据、遗漏字组、普通字体残留或仅检索未入图按18判失败/unknown。

## 评分与呈现

`layout-rubric.json`为带证据的评审建议：1–5锚点按权重换算，排除有理由的非适用类后归一到100；适用类缺分则总分unknown。硬项有fail先修，关键unknown不能标正式通过；85分是建议精修目标，不保证审美或放行。用户保留否决/修改权，像素对比也不能驳回其暗沉/难读反馈。

不继承上游62/76总分错配、默认true闸门或恒通过基线；没有实现的颜色梯度检测、OCR、分割或DOM校验不写已验证，不要求安装整套第三方体系。
