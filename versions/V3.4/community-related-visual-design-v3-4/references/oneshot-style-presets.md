# 一键风格预设

**风格库共12种，在 `assets/oneshot-styles.json`**（简约扁平、手绘暖调插画、国潮水彩水墨、2.5D三维立体、复古版画拼贴、剪纸窗花、清新水彩、复古海报印刷、线描单色、几何构成、摄影拼贴手写、绘本童话）。已去掉不适合老年受众的儿童蜡笔涂鸦、波普漫画、夜色霓虹灯牌。每次用 `scripts/pick_styles.py` 随机抽5种给用户选，`--id` 查看某一种的关键词、标题字、正文字和色板。

下面是 S01–S05 的详细写法，作为其余风格写提示词的范例；新增风格只需在 JSON 里加一条（id、name、family、pitch、keywords、type、palette、suits）。

参考编号：本地库 A/B/C/D/E/H 组见 `assets/reference-posters/`；WP 开头的见[网络提示词参考库](web-prompt-library.md)。

---

## 1. 简约扁平

**一句话**：干净的平面色块和简洁图形，信息清楚、像政务服务指引。

- **风格**：`clean flat vector poster, bold simple shapes, 2–3 tone flat fills, crisp edges, generous white space, Swiss-style grid, modern public-service design`
- **标题字**：粗黑体/方黑，字重 Heavy，可做局部笔画替换（如“安”字的宝盖换成屋顶图形）；不加描边投影。
- **正文字**：黑体 Medium/Bold，小标题放在实色圆角标签里。
- **图标与装饰**：同一套实心面性图标，统一圆形或圆角方底座；分隔用粗细两种直线；大编号 01/02/03。
- **色板起点**：背景#F5F7FA 主色#1F6FEB 辅色#12B886 强调#FF8A00 字#1F2933
- **适合**：办事指引、通知公告、政务服务、垃圾分类。
- **参考**：A组政务类、WP02、WP08、H组扁平类。

## 2. 手绘暖调插画

**一句话**：米色纸底上的手绘插画，标题、图标、数字都是同一支笔画的，温暖亲切、有生活感（像“银龄手机课堂”）。

- **风格**：`warm hand-drawn illustrated poster on cream textured paper, gouache and colored-pencil texture, slightly imperfect ink outlines, cozy storybook feeling, all lettering, icons, numbers and doodles drawn with the same brush as the illustration`
- **标题字**：粗壮手写毛笔/马克笔字，字大小错落、略有倾斜，可加一层浅色错位投影或描边；标题与插画的某个物件穿插（如手机线框从标题后穿出）。
- **正文字**：圆润手写体或圆黑体，关键词用荧光笔底色/手绘下划线/圈注。
- **图标与装饰**：手绘线描图标，**图标当容器**（房子线框里写地点、日历里写日期、对话气泡里写电话）；虚线箭头串起各信息；1个倾斜贴纸（“开课啦！”“免费”）；撕纸边提示框。
- **色板起点**：背景#F6EBD6 主色#E8642C（暖橙）辅色#5B8C3A（草绿，主色的对比色）强调#F2B233 字#4A3426
- **适合**：老年课堂、亲子活动、邻里节、健康讲座、志愿招募。
- **参考**：D01（银龄手机课堂）、D组手绘类、WP09。

## 3. 国潮水彩/水墨

**一句话**：宣纸质感的水彩或水墨山水，配书法标题和印章，郑重有文化气息，适合节日和敬老。

- **风格**：`Chinese watercolor and ink wash poster on rice paper, soft wet edges, layered misty mountains, gold accents, elegant negative space, New Chinese style, restrained and refined`
- **标题字**：行书/行草或粗宋，竖排或两行错位，旁配红色印章（印文只用母本已有的词）。
- **正文字**：宋体/楷体，信息模块用深色胶囊小标题＋短行（参考WP01），模块后可透出淡墨山景。
- **图标与装饰**：细线描图标或印章形底座；云纹端头分隔线；红日圆作标题后衬。
- **色板起点**：背景#F7EBD9 主色#D9452B 辅色#2F5D50（黛青）强调#C9A45C（金）字#2B2B2B；蓝调方案：#EEF4F7/#1F4E8C/#D9452B
- **适合**：重阳、敬老、春节、中秋、传统文化、非遗。
- **参考**：C01–C08、WP01、WP07。

## 4. 2.5D/三维立体

**一句话**：圆润的立体小场景或等距小模型，像城市微缩模型，现代、科技感、亲和。

- **风格**：`soft 3D clay render poster, isometric 2.5D miniature community scene, rounded friendly shapes, soft studio lighting, pastel gradients, gentle shadows, C4D style, clean and modern`
- **标题字**：立体厚字（带侧面厚度和柔和阴影）或白色粗圆体压在色块上；标题可以“立”在场景里。
- **正文字**：圆黑体，信息放在半透明玻璃卡片或圆角浮层卡片里。
- **图标与装饰**：3D小图标（立体定位针、日历、电话），放在同一种圆角底座上；场景中的道路/轨道作动线。
- **色板起点**：背景#EAF3FF 主色#3B82F6 辅色#34D399 强调#FFB020 字#1E293B
- **适合**：数字服务、智慧社区、反诈宣传、防灾演练、政务办事。
- **参考**：A组2.5D政务门牌、H组三维类。
- **注意**：三维风格对老年人可能显得“电子化”，敬老题材慎用；正文卡片要实底，避免玻璃透出复杂背景。

## 5. 复古版画/拼贴

**一句话**：丝网印刷、木刻或纸张拼贴的颗粒质感，限色、有手作温度，像文艺展览海报。

- **风格**：`risograph / screen-print poster, limited 3-color palette, visible paper grain, slight ink misregistration, bold carved shapes, torn-paper collage elements, hand-made print texture`
- **标题字**：粗衬线/粗宋或木刻感大字，可压在色块上、可被主体局部遮挡；也可以纯字做主视觉（参考WP08）。
- **正文字**：等宽字体或粗宋小字，用细线分栏；信息条用“—”分隔排成一行（参考WP07底部横带）。
- **图标与装饰**：单色线描图标，侧边信息栏“图标＋短句＋虚线分隔”（参考WP03）；撕纸、胶带、印章、套色错位。
- **色板起点**：背景#F2EBDD 主色#243447 辅色#C65D48 强调#D6A14B（黑哥库常用组合）
- **适合**：读书会、修补集市、旧物交换、文化倡议、环保主题。
- **参考**：WP03–WP07、D组版画类。

---

## 用户说“你定”时

| 题材 | 推荐 |
|---|---|
| 敬老、重阳、传统节日 | 3 国潮水彩（郑重）或 2 手绘暖调（亲切） |
| 老年课堂、健康讲座、邻里活动 | 2 手绘暖调 |
| 办事指引、通知公告 | 1 简约扁平 |
| 数字服务、反诈、安全 | 4 三维 或 1 扁平 |
| 文化、环保、倡议 | 5 版画拼贴 |

## 老年受众的通用补充（任何风格都加）

`large high-contrast text for elderly readers, key information (date, place, phone) noticeably larger than body text, no thin light-gray text, no text over busy texture`

正文与底色对比 ≥4.5:1；电话、日期、地点用最大的一档正文字号；不用细体、不用浅灰字。
