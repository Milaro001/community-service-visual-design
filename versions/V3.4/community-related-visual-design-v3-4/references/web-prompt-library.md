# 网络提示词参考库（整图出字）

收集日期：2026-10-15。提示词版权归原作者；本文件和 `assets/web-prompt-examples/` 中的示例图**仅供私人研究参考**，不作成品素材。一键出图写提示词时，先用[提示词模板](prompt-templates.md)第9节，再从这里借写法。

来源：
- awesome-gpt-image（MIT许可的整理仓库，提示词原作者见各条）：https://github.com/ZeroLu/awesome-gpt-image
- 黑哥AI海报提示词库：https://www.heigeai.com/en/prompts/posters/
- Apiyi 海报实测指南：https://help.apiyi.com/en/gpt-image-2-poster-cover-prompts-guide-en.html
- Evolink 提示词集：https://evolink.ai/gpt-image-2-prompts
- YouMind 海报分类（页面为动态加载，未取到可用条目）：https://youmind.com/gpt-image-2-prompts?categories=poster-flyer

## 一、整图出字技巧（归纳）

| # | 技巧 | 来源 |
|---|---|---|
| 1 | **要上图的字全部用引号包住**，一条一行列出，并写“must accurately display the following exact Chinese copy”。不加引号、只描述意思时，模型会自己编字 | Apiyi、黑哥、awesome |
| 2 | **开头先说画幅和用途**（“3:4 vertical poster”“16:9 placard for public participation”）；画幅决定所有后续构图 | 黑哥、Apiyi |
| 3 | **色彩只给“1主色＋1强调色＋1中性色”**（最多4个HEX）；超过3–4色画面会发灰发糊 | 黑哥 |
| 4 | **中文要点名字体类别和字重**：黑体/宋体/楷体/隶书/手写体＋粗细；只写“中文字体”会退化成普通无衬线 | 黑哥 |
| 5 | **加“no pseudo-text, no placeholder text, no extra slogan”**，防止模型加假字、假标语、lorem ipsum | 黑哥 |
| 6 | **整体描述用自然语言，不堆形容词**（8K、masterpiece 之类反而分散注意力，让字更容易错）；氛围词1个即可 | Apiyi |
| 7 | **按区域从上到下描述版面**：顶部写什么、左栏写什么、底部条写什么；信息模块写成“小标题＋若干条” | awesome（博物馆信息图、山川茶事） |
| 8 | **点明要重视的难点**：“Pay special attention to small text, numbers, prices, info modules” | awesome（山川茶事） |
| 9 | **给一个核心视觉点子**（one memorable idea），其他元素都为它服务；缩略图大小时轮廓仍能传达主题 | 黑哥 |
| 10 | **让图和字共享一条阅读路径**：“make image and typography share a reading path; do not park text outside the artwork” | 黑哥 |
| 11 | **关键信息离裁切边留安全距离**：“keep headline and venue within trim safety / protect 5% around the sheet” | 黑哥 |
| 12 | **只要一张成品**：“Return exactly one finished image; no variants, mockup frame, split panels” —— 否则可能出样机、拼板 | 黑哥 |
| 13 | **改字用蒙版局部编辑**：只涂白要改的区域，提示词只写“把标题改为‘…’”，蒙版外保持不变 | Apiyi |
| 14 | **最多可附5张（部分平台16张）参考图**，写明“use the palette and typography from the reference images” | Apiyi、YouMind |
| 15 | **不能锁定具体字体**，只能指定风格；必须用某款字体时，整图出完后再替换文字层 | Apiyi |
| 16 | **质量档位**：印刷/重要字用 high；横版4K单张约2–5分钟；一次出多张再挑 | Apiyi |
| 17 | **挑图顺序**：先看引号里的字是否全对（不对直接淘汰）→ 再看主体清晰度 → 再看配色/字体是否合要求 | Apiyi |
| 18 | **竖排中文**写“vertical Chinese text”，并给出每列内容 | Apiyi |

## 二、精选提示词（原文照录）

### WP01 山川茶事·新品海报（密集中文整图，约100字全部正确）
来源：awesome-gpt-image「Chinese Tea Drink Product Launch Poster」；示例图 `assets/web-prompt-examples/WP01_山川茶事_密集中文整图.png`
风格：国潮水彩水墨　画幅：竖3:4
可借鉴：信息模块＝深色胶囊小标题＋短行；价格数字放大；水墨山景从模块后面穿过，字和图同一张纸。
```text
Design a 3:4 vertical poster for a new Chinese trendy tea launch. Use a New Chinese visual style that feels light-luxury and restrained. The palette should be dark green, off-white, and gold, with rice-paper texture, elegant negative space, landscape accents, and modern layout design.

Main subject:
a visually appealing cold-brew tea with tea leaves, citrus, ice cubes, and touches of gold foil.

The poster must accurately display the following exact Chinese copy:
"山川茶事"
"山柚观音"
"冷泡系列"
"新品上市"
"一口清醒，半城入夏"
"限定尝鲜价"
"中杯 16 元"
"大杯 19 元"
"门店活动"
"第二杯半价"
"加 3 元升级轻乳版"
"每日前 100 名赠限定杯套"
"推荐风味"
"观音茶底 / 西柚果香 / 轻乳云顶 / 冰感回甘"
"活动时间 4月20日 至 5月10日"
"扫码点单"
"SHANCHUAN TEA"

Fine print:
"图片仅供参考，请以门店实际售卖为准"

Maintain a clear promotional hierarchy while keeping the overall feeling sophisticated rather than cheap or overly e-commerce-like. Pay special attention to small text, numbers, prices, info modules, and Chinese typography aesthetics.
```

### WP02 咖啡旅程信息图（编号模块＋箭头动线）
来源：awesome-gpt-image「Coffee Journey Infographic」；示例图 `WP02_咖啡信息图_编号模块.png`
风格：简约扁平　画幅：竖
可借鉴：01–05 编号沿箭头排列，适合“步骤流程”类社区海报（S2骨架）。
```text
Create a Chinese infographic poster themed "一杯咖啡 如何来到你手里" ("How a Cup of Coffee Reaches You"). Use a premium information-design style with both educational clarity and commercial appeal. The layout should include directional flow, arrows, data boxes, icons, simple illustrations, and modular cards. Use coffee brown, milk white, ink black, and copper accents.

The infographic must include:
- 01 Planting: elevation 1200-2200m, suitable temperature 18-24C, picking season Nov-March
- 02 Processing: sun-dried, washed, honey process
- 03 Roasting: light roast = brighter, medium roast = balanced, dark roast = richer
- 04 Grinding: pour-over = coarse, espresso = fine, cold brew = medium-coarse
- 05 Extraction: powder-water ratio, water temperature, and time all affect flavor
- flavor keywords: floral / citrus / nutty / caramel / chocolate / smoky

Use this exact fine print:
"适合用于咖啡入门科普与门店展示"

The composition should balance text and visuals while keeping the design elegant. Focus on long infographic handling, numeric information, temperatures, numbered sections, concise descriptions, slash-separated flavor words, and modular layout. It should look like a premium display board, not a classroom slide deck.
```

### WP03 Seed Swap Morning（横版16:9社区活动，右侧图标信息栏）
来源：黑哥AI heige-poster-484；示例图 `WP03_SeedSwap_横版图标侧栏.jpg`
风格：复古版画拼贴（双色丝印）　画幅：横16:9
可借鉴：标题左上→定位图标＋地点→主体斜穿中部→右侧四条“图标＋短句”用虚线分隔，是横版“左标题·中主体·右信息栏”的典型结构。
```text
Present "Seed Swap Morning" as an independently printed 16:9 placard for public participation. Keep a seed resting in a palm casting the oversized shadow of its future plant as the one memorable idea and prevent supporting elements from changing its reading direction. Build the image with A spiral reading path moves from the edge to the center, keeping supporting information beside its evidence. Write "Seed Swap Morning," "Begin a shared story with one old object," "the riverside observation deck," and "wear nonslip shoes and bring a pencil" accurately, with no pseudo-text or extra slogan. Use true-scale specimens, wind-direction lines, and moisture to explain scale and participation. Print on two-color screen printing with thin mineral-pigment layers, with local ink edges and folds, in rain blue, ink black, paper white, and rose red. Set illumination to a hooded overhead lamp, separating believable highlights from paper diffusion and avoiding theatrical bloom. Keep headline, secondary line, and venue within trim safety. Remove mockups, sponsor logos, public figures, character assets, and excess lighting. For the final rendering, anchor the image in a tactile object transformation: a seed resting in a palm casting the oversized shadow of its future plant. Show enough thickness at the cut edge to establish the material, while the background remains flat and quiet. Keep the title's baseline stable even where the hero approaches the letterforms. Final art direction: editorial poster design with a disciplined grid and material-aware composition. Use this controlled palette as the dominant visual system: #F2EBDD, #243447, #C65D48, #D6A14B; preserve believable local material colors within it. Preserve the requested text hierarchy and wording as part of the design, but do not invent extra slogans, pseudo-text, logos, or watermarks. Keep one unmistakable primary subject or information route and one readable visual action. Use disciplined negative space and avoid default perfect symmetry. Physical credibility is mandatory: correct gravity, contact shadows, material thickness, tool weight, joint loading, fabric tension, liquid direction, reflections, scale, and occlusion. Create an original visual with no resemblance to a public figure, copyrighted character, existing campaign, or living artist signature style. No unrelated decorative icons, floating objects, duplicated limbs, plastic gloss, waxy skin, synthetic collage artifacts, or AI watermarks. Return exactly one finished image composed for 16:9; no variants, process sheet, split panels, mockup frame, or contact sheet.
```

### WP04 Paper Umbrella Repair Fair（横版16:9邻里修补集市）
来源：黑哥AI heige-poster-521（网站示例图是一张无字照片，没有收录）
风格：复古版画拼贴　画幅：横16:9
```text
Present "Paper Umbrella Repair Fair" as an independently printed 16:9 placard for public participation. The core relationship is disassembled bamboo umbrella ribs laid out as a star chart, with repair patches forming a ring of seasons. Build causality through support, weight, and shadow rather than floating collage. Set an asymmetric vertical composition. The viewer encounters the object change before the headline and participation details. Use "Paper Umbrella Repair Fair" for the first level, "Small things also deserve to be remembered" for the idea, and "the neighborhood repair room" with "bring one repairable object" for practical detail. Allow only worn edges, repair stitches, and tool shadows in the background. Unify image and type through dyed fiber paper with real stitched thread, remaining within rain blue, ink black, paper white, and rose red. Build volume with a low work lamp, keeping the clearest shadow near the seam and the background quiet. Protect at least five percent around the sheet. Do not add frames, handheld mockups, logos, famous faces, landmark collages, or glowing 3D text. （后半段通用约束同WP03）
```

### WP05 Watch Repair Open Class（竖版3:4社区课堂）
来源：黑哥AI heige-poster-474（网站示例图是一张无字照片，没有收录）
风格：复古版画拼贴　画幅：竖3:4
可借鉴：“make image and typography share a spiral reading path; do not park text outside the artwork”——直接对应“字图没有交互”的问题。
```text
Present "Watch Repair Open Class" as an independently printed 3:4 placard for public participation. Let one missing tooth in an enlarged watch gear completed by the timetable of a repair class govern the image. Explain how the objects join before bending, occlusion, and shadow appear. Make image and typography share A spiral reading path moves from the edge to the center; do not park text outside the artwork. Write "Watch Repair Open Class," "Make the invisible process visible," "the neighborhood repair room," and "bring one repairable object" accurately, with no pseudo-text or extra slogan. Keep supporting objects within worn edges, repair stitches, and tool shadows. Combine dyed fiber paper with real stitched thread and rust red, platform gray, rice beige, and peacock blue without an all-over aging filter. Use a single projected beam of white light as the only key light. Contact shadows are harder, distant shadows soften, and every projection shares one direction. Show only the placard, with essential information protected from trim. Use no brand, celebrity, IP, HUD, QR code, or luxury display shortcut. （后半段通用约束同WP03，结尾为 composed for 3:4）
```

### WP06 Rooftop Cinema and Cicadas（竖版4:5，面向普通社区居民）
来源：黑哥AI heige-poster-497；示例图 `WP06_RooftopCinema_竖版社区活动.jpg`
```text
Produce a 4:5 event poster for "Rooftop Cinema and Cicadas," aimed at ordinary community participants. Keep projector light turning the shadows of folding chairs into cicada wings as the one memorable idea and prevent supporting elements from changing its reading direction. Use an asymmetric vertical composition; the hero is the first focal point, followed by title and event copy. Use "Rooftop Cinema and Cicadas" as the headline, "Leave room for ordinary experience" as the secondary line, and "the small theater backstage area" plus "wear shoes suitable for movement" as event information. Treat movement footprints, beat marks, and folding chairs as evidence for the hero. Preserve stencil printing with localized hand rubbings texture and divide charcoal, ivory, verdigris, and coral pink into dominant, supporting, and accent roles. （后半段通用约束同WP03）
```

### WP07 蛍祭り（孔版三色·竖排书法·底部信息横带）
来源：黑哥AI japanese-matsuri-festival-poster-hotaru；示例图 `WP07_蛍祭り_孔版三色.jpg`（网站示例是中文版“萤火祭”，底部横带“七月二十日 | 山影村 | 18:00 开始”）
风格：复古版画拼贴（risograph）　画幅：竖
可借鉴：竖排书法标题＋底部一条横带放“日期—地点—时间”，非常适合节日类社区海报。
```text
A vertical festival poster for a fictional summer matsuri called "Hotaru-Matsuri" hosted by a small mountain village. B2 portrait format printed as if risograph in three colours on warm off-white paper. The composition shows a single tall, narrow wooden torii gate seen from below at dusk, drawn with confident flat shapes and a thin black ink outline. Behind it, a deep indigo sky is dotted with thirty or so glowing yellow fireflies, each rendered as a slightly imperfect dot with a soft halo. A river suggested by three horizontal blue lines runs across the lower fifth of the page. To the right of the torii, vertical Japanese calligraphy reads "蛍祭り" in confident black brushstrokes, large. Below the river, in a horizontal band, small Japanese and English text reads "七月二十日 — 山影村 — 18:00 開始" and "Hotaru-Matsuri — Yamakage Village — July 20". A small round logo of a firefly inside a circle sits in the lower-right corner. Paper grain and slight ink misregistration visible. Palette: paper F4EFE3, indigo 1F2C5A, firefly yellow E8C656, river blue 4A86A4.
```

### WP08 Thresholds 讲座系列（纯字体＋两栏信息）
来源：黑哥AI university-lecture-series-poster-thresholds；示例图 `WP08_Thresholds_瑞士字体讲座.jpg`（网站示例是中文版“界线”：巨字＋左侧6行讲座表＋右侧说明段，中文小字全部清楚，可作“课程表类”海报参考）
风格：简约扁平（瑞士风）　画幅：竖
可借鉴：上2/3巨字、下1/3两栏信息；适合“讲座/课程表”类、没有合适插画时的纯字方案。
```text
A bold academic lecture series poster for a fictional public-humanities programme titled "Thresholds". Vertical B1 format on warm newsprint-grey stock. Composition splits at the golden ratio: the upper two thirds is dominated by an enormous black slab serif word "THRESHOLDS" set in 380pt, letters touching the page edges and slightly clipped on the left and right, suggesting a doorframe. The lower third is a clean two-column information layout. Left column lists six lectures with date, speaker (fictional), and topic, e.g. "03.02 — Dr. Iona Marsh — Borders of attention", "03.16 — Prof. Hadi Karam — Thresholds of pain", in 12pt monospaced type. Right column holds a short paragraph in 14pt serif explaining the series, ending with the line "Free and open. No registration required." A small red square sits in the top-right corner with the host institution shorthand "DEPT. OF COMPARATIVE STUDIES — SPRING 2026" rotated ninety degrees, white text. Palette: newsprint grey D7D2C5, ink black 111111, signal red C8302B. No photography, all type and shape.
```

### WP09 小红书封面（手绘下划线、标签）
来源：Apiyi 海报指南 3.3（无示例图）
```text
Cozy lifestyle cover, warm morning light,
top-left pink tag says "AI 新手指南",
center large text "5 个技巧" with hand-drawn underline,
3:4 vertical, soft pastel colors
```

### WP10 横幅类短提示词（Apiyi，横版速写）
```text
WeChat article cover, 2.35:1 horizontal,
left side big text "AI Weekly · Issue 23" in bold sans-serif,
right side abstract tech illustration, gradient blue background
```
可借鉴：横版的字放左侧，避开右下角缩略图裁切。

### WP11 节日双语海报（Apiyi）
```text
Bilingual poster, 3:4 vertical,
top Chinese text "春节快乐",
below English text "Happy Spring Festival 2026",
red and gold festive palette
```

### WP12 百科知识卡（模块化信息、圆角卡片、小图标）
来源：awesome-gpt-image「Encyclopedia-Style Knowledge Card」
可借鉴：适合“健康知识/防诈知识”类信息量大的社区科普海报。
```text
Generate a high-quality vertical encyclopedia-style infographic for [topic].
This should not be a normal poster or a simple illustration. It should feel like a modular educational infographic that combines the clarity of a field guide, the structure of an encyclopedia page, the polish of a lifestyle knowledge card, and the shareability of a strong social-media explainer.
The image should include:
- a clear and appealing main visual of the topic
- several enlarged detail callouts
- multiple rounded modular information sections
- strong title hierarchy and highlighted key labels
- concise but information-rich educational content
- visual scoring, quick takeaways, or a Top 5 module
Visual requirements:
use a clean light background, soft colors, subtle shadows, refined small icons, rounded information cards, and neat layout. The information density should be high but not crowded, and the final image should feel publishable, collectible, and repeatable as a knowledge-card format rather than an advertisement.
```

### WP13 横版中文大片海报（Evolink，横版字放底部中央）
```text
Create a horizontal Chinese blockbuster movie poster for a fantasy adventure film titled "天机启明" with subtitle "失落的文明". ... The title "天机启明" is rendered in large stylized golden Chinese calligraphy at the bottom center, with the subtitle below. Include theatrical release information: "2025 大年初一", ... director and producer credits in small Chinese text along the sides. Dark cinematic color grading with warm amber highlights and deep teal shadows ...
```
可借鉴：横版“主体群像居中＋书法标题底部居中＋两侧小字”的结构；节日主视觉可用。

### WP14 复古旅行海报（Evolink，铅笔＋丝印质感）
```text
Modern pencil illustration of a vintage travel poster for the Amalfi Coast, Italy. Panoramic coastal cliff road scene, a classic 1960s white car driving along a curved seaside road, deep blue Mediterranean sea with small sailboats, pastel hillside village, bright blue sky, and lemon tree branches framing the foreground. Warm summer sunlight, bold vibrant colors, retro 1950s travel poster style, screen print texture, hand-drawn contours, and a decorative editorial finish.
```
可借鉴：“复古版画”方向的风格词：screen print texture, hand-drawn contours, retro travel poster。
