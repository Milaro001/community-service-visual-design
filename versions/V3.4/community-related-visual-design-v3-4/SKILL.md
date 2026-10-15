---
name: community-related-visual-design-v3-4
description: 社区视觉/海报设计的制作、修改和检查，包括宣传公告、服务指引、风险提示、活动招募与求助；依据真实文案、受众和参考图完成候选与PNG/PDF。文字不多时默认一键整图出图。社区软件界面或独立商业广告不适用。
metadata:
  short-description: 社区相关视觉设计3.4
---

# 社区相关视觉设计3.4

制作、修改或检查社区视觉/海报时启用；只讨论技能规则时直接回答，不启动制作。默认A3竖版；用户指定横版或其他尺寸时照做，开工前锁定方向、比例和尺寸，各语言共用同一画布、底图和分区。用户最新的明确要求优先。

## ⚠️ 一键出图的必经一步：先让用户选风格（不能跳过）

一键出图在**写任何提示词、生成任何图片之前**，必须先让用户选风格并**等回答**。资料再齐全也要问；只有用户这次已经明确指定了风格（或说“你定”）时才跳过。

1. 运行 `python -I scripts/pick_styles.py --topic "<主题关键词>"`。风格库共12种（`assets/oneshot-styles.json`），脚本每次随机抽5种：至少2种贴合主题，其余跨度拉开，同一大类最多2种。
2. **必须用平台的选择题工具提问，让用户直接点选**，不要只发一段文字：Claude Code 用 `AskUserQuestion`，Codex 用 `request_user_input`（或当前平台等价的单选组件）。每个选项：标签＝风格名，说明＝脚本给的 `pitch`（一句话含色调）。
   - 工具一题最多4个选项时，运行时加 `--count 4`，抽4种做选项；平台自带的“其他/Other”输入框留给用户写“你定”“换一批”或自己描述。
   - 用户选“换一批”时加 `--exclude` 上次的编号再抽，再问一次。
   - 只有当前平台确实没有任何选择题工具时，才退回发文字列表（脚本输出的 `message`）。
   缺失的日期、地点、电话等事实，作为同一次提问里的另一道题一起问。
3. 用户选定后用 `--id S06` 取出该风格的完整预设（关键词、标题字、正文字、色板），写进 `state.md`，再按[一键出图卡](references/oneshot-mode.md)继续。用户自己描述的风格不在库里时照描述做，借最接近的一种的写法。

## 怎么读规则

每个阶段只读对应的**一张卡**，卡里已包含该阶段需要的全部规则，读完直接执行。

**一键出图**（默认）：阶段卡1 → [一键出图卡](references/oneshot-mode.md)（风格库见 `assets/oneshot-styles.json`，写法细节见[一键风格预设](references/oneshot-style-presets.md)）。

**分步模式**（常规/快速）：

| 阶段 | 阶段卡 | 用户选择 |
|---|---|---|
| 1 开工：资料、母本、定模式 | [stage-1-setup](references/stage-1-setup.md) | —（按字数自动定模式） |
| 2 底图 | [stage-2-background](references/stage-2-background.md) | 选底图 |
| 3 主题字（直接写在底图上） | [stage-3-title-type](references/stage-3-title-type.md) | 选主题字 |
| 4 正文与排版（在底图＋标题上直接排） | [stage-4-body-layout](references/stage-4-body-layout.md) | 选排版 |
| 5 精修、导出、交付 | [stage-5-finish-export](references/stage-5-finish-export.md) | 确认成品、选交付格式 |

横版或老年受众另查[横版与适老版面速查](references/horizontal-and-elderly-layout.md)。全程配合工具卡：写任何生图提示词前用[提示词模板](references/prompt-templates.md)（一键出图用第9节整图模板），需要更多写法时查[网络提示词参考库](references/web-prompt-library.md)；所有模式都执行[串联与装饰系统](references/linking-and-decoration.md)，特别是第7节字图交互手法。

其他编号文件（01–31）是细则档案，只在排错、遇到阶段卡没写到的特殊情况时查阅；与阶段卡冲突时以阶段卡为准。

## 三种模式

**开工不先问模式。** 先读资料、写母本、数上图文案（`scripts/count_copy.py`）：用户没指定时，≤160字直接一键出图；>160字问一次模式。用户说“一步步来”“想自己每步选”时走分步模式。

| 项目 | 一键出图 | 快速模式 | 常规模式 |
|---|---|---|---|
| 开头提问 | 风格（12种里随机抽5种，选项可点选）＋缺失事实 | 缺失事实 | 缺失事实 |
| 参考库 | 按风格检索＋未筛选参考池巡览页＋可联网补充 | 检索短名单，开1–2张原图 | 看完全部巡览页，精读2–3张 |
| 底图 | 不单独出 | 2张，两种风格 | 3张，三种风格 |
| 主题字 | 不单独出 | 2款，直接写在底图上 | 3款，直接写在底图上 |
| 正文 | 与标题、插画、图标**同一次**生成（不分两步） | 在底图＋标题上图像编辑排入 | 同左 |
| 排版候选 | 自动生成2张、自动挑1张 | 1款 | 3款 |
| 中途让用户选 | 无 | 底图、主题字、排版 | 底图、主题字、排版 |
| 审查 | 盲读对照文字＋清晰/色调/主次三项 | 一次 | 一次 |
| 印刷/源文件/其他尺寸 | 出图后再问 | 出图后再问 | 出图后再问 |
| 预计耗时 | 约8–12分钟 | 约20–25分钟 | 更长 |

所有模式都保留：真实文案（母本一字不改）、主标题为生成艺术字、必要图标、串联装饰系统、字图交互手法、主标题不加整块矩形底框。正文默认也用与标题同一支笔的艺术字（一键出图第二步画进去）；版面除简约扁平外允许文字自由错落，见[串联与装饰系统](references/linking-and-decoration.md)第9节。

## 记录

只维护一个 `state.md`：模式、当前阶段、母本、已选编号、最新文件路径、每次生图的提示词（方便重做和续做）。检查在内部完成，结果用一两句话在聊天里说明，不另写检查记录文件。续做时先读 `state.md`，从当前阶段继续，沿用已选内容。

## 工具

- `scripts/count_copy.py`：数上图文案字数，决定模式（`state.md` 或 `--text`；`--body-only` 只数正文）。
- `scripts/find_reference.py`：布局库目录与检索（`--catalog-layout` 全库；`--library posters --query "横版 敬老"`、`--query "手绘暖调插画"` 等）。参考库新增 D组（风格参考）、E组（适老信息海报）、H组（横版16:9）。
- `scripts/patch_text.py`：重画后仍错的单处用真实字体补救，或用户要求标准字体正文时使用（不作默认）。
- `scripts/pick_styles.py`：从12种风格里随机抽5种（`--count 4` 抽4种）给用户点选；`--id` 看完整预设。
- `scripts/extra_refs.py`：参考池（内置200张，按D01–D15分类）的编号巡览页，`--domain D03 --grade A` 只看本主题A级（**只在一键出图时用**，分步模式不读）。
- `scripts/export_print.py`：成品转印刷尺寸（A3 300dpi、出血、扩边适配比例）。
- `scripts/build_editable_svg.py`：无字底图＋文字层描述 → 文字可编辑的 SVG。
- `scripts/select_type_references.py`：字体库目录与语义短名单（`--catalog --semantics "重阳 敬老"`）。
- `scripts/verify_copy.py / check_linebreaks.py / check_layout.py / audit_poster_readability.py`：按需使用，首次用 `--help` 看参数。
- 运行方式：纯标准库脚本用 `python -I`；需要 Pillow/NumPy 的像素脚本用 `python -P`（`-I` 会屏蔽用户目录里安装的 Pillow）。
- `visual_review.py`：可选的 Label Studio 网页评审，默认关闭，启用时看[30](references/30-human-review-and-feedback.md)。
- `scripts/vendor/yaml` 是脚本依赖，保持原样。
