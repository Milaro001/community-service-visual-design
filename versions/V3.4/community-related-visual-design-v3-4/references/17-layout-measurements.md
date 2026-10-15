> **细则档案**：日常制作按 SKILL.md 和 stage-1～5 阶段卡执行，本文件只在排错或阶段卡没写到的特殊情况时查阅。与阶段卡冲突时以阶段卡为准。当前版本的变化：开工先选常规/快速模式；主题字常规3款（2横＋1竖）、快速2款；正文派生后直接排版，不单独确认；排版只做普通字体初排一次审查；不做配色A/B；不写检查记录，只维护 state.md；参考库现为布局155份（新增C组横版敬老8张）、字体TG01–TG65。

# 可选测量工具：输入与边界

有代码、当前成图和真实测量时，从技能根运行`python scripts/check_layout.py 当前测量记录.json`。输出JSON；退出0为提交项通过，1有失败，2未验证/无效。脚本不读图、不做OCR/测字体/审美、不放行作品；无代码按15检查。宽高统一canvas.unit（px/design_px/mm），pt按真实画布比例换算。

| 字段 | 含义 |
|---|---|
| asset_version | 当前初稿/艺术化合成图的文件名与版本或哈希，必填 |
| canvas.width / height / unit | 真实画布尺寸与统一单位 |
| canvas.safe_rect | 安全矩形[x,y,w,h]，缺少则该项unknown |
| expected_group_ids | 应测量的全部母本文字组ID，非空且唯一；缺少则清单完整性unknown |
| groups[].id / measurement | 母本对应ID；只有rendered代表调用者提供当前实测，estimate不能通过 |
| visible_bounds | 包含可见字形及装饰边缘的[x,y,w,h]，不能只测空框 |
| required_height / available_height | 实际换行后所需高与连续可用区高度 |
| glyph_height / min_glyph_height | 实际主字形高度与本次受众/媒介最低高度，非通用阈值 |
| contrast_samples | 实际合成图中foreground/background不透明#RRGGBB颜色对列表 |
| contrast_min | 当前组最低比值，默认4.5；重点目标可提高 |
| contrast_region_verified | 调用者已检查区域覆盖才填true；少量抽样未验证则false或不填 |

空组、缺测量、未覆盖颜色区均为unknown；清单缺组为fail。不达标真实样本会失败，区域覆盖由调用者保证，脚本只能验证提交的颜色。

## 教学例（估计输入，运行应为unknown）

例中estimate和false明确表示未测量/未验证。实际任务只能在真实测量后填写rendered，不能复制示例改标签冒充证据。

```json
{
  "asset_version": "example-only-v1",
  "canvas": {"width": 1080, "height": 1527, "unit": "design_px", "safe_rect": [55, 55, 970, 1417]},
  "expected_group_ids": ["body-01"],
  "groups": [{
    "id": "body-01", "measurement": "estimate",
    "visible_bounds": [70, 600, 440, 180],
    "required_height": 170, "available_height": 180,
    "glyph_height": 28, "min_glyph_height": 26,
    "contrast_min": 4.5, "contrast_region_verified": false,
    "contrast_samples": [{"foreground": "#17202B", "background": "#F5F3EE"}]
  }]
}
```

几何/容量不证明实际遮字、字形或阅读，最终按13两次渲染和08导出检查；源文另用verify_copy.py。
