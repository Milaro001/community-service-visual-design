# 社区相关视觉设计 V3.4

Community-Related Visual Design · **V3.4** · Git tag: **`v3.4`**

完整的社区海报设计技能交付包，包含中文和英文 `SKILL.md`、配套规则卡、脚本、参考图库，以及「银龄数字生活服务日」中英文海报成品。

## 下载与版本

- [V3.4 发布页与完整 ZIP](https://github.com/Milaro001/community-service-visual-design/releases/tag/v3.4)
- 交付文件名：`社区相关视觉设计 3.4 版本.zip`
- `VERSION`、`TAG` 和 `release.json` 标记本包版本；`checksums.sha256` 可校验包内文件。

## 文件与安装

| 内容 | 路径 |
|---|---|
| 中文入口 | [SKILL.md](SKILL.md) |
| English entry | [en/SKILL.md](en/SKILL.md) |
| 中英文海报成品 PNG | [posters/](posters/) |

把整个 `community-related-visual-design-v3-4` 文件夹放入平台的技能目录。默认入口是根目录的中文 `SKILL.md`；英文入口位于 `en/SKILL.md`，其中的相对链接直接跳转到共用规则卡。`scripts/`、`references/`、`assets/` 与 `agents/` 均只保留一份，不再按语言重复备份。使用英文入口时也从技能根目录执行脚本命令。

英文版完整翻译了入口 `SKILL.md`；配套规则卡、索引和素材保留原始语言及文件名。实际生图、联网、选择组件和导出能力取决于使用的平台。Python 脚本通常只需标准库；像素处理的可选依赖见各技能目录的 `scripts/requirements-pixel-audit.txt`，校验所需 YAML 已随包附带。

海报按现有成品 PNG 原样收录。技能文件夹内的海报是参考素材，来源登记和原有版权说明随包保留；第三方作品的权利归原权利人，本次打包未为这些素材另行授予开源许可。

## English

This V3.4 delivery contains Chinese `SKILL.md` and English `en/SKILL.md`, with one shared set of scripts, reference cards, assets and platform metadata, plus finished Chinese/English poster PNGs. Copy the entire `community-related-visual-design-v3-4` folder into your platform's skill directory. The English entry links directly to the shared reference cards; run script commands from the skill root. Supporting references and asset metadata retain their original languages. Runtime capabilities depend on the host platform.

Use the release tagged **`v3.4`** for this delivery. `VERSION`, `TAG`, `release.json` and `checksums.sha256` identify and verify the package. Existing third-party source and copyright notices are preserved; no additional license is granted for third-party artwork.
