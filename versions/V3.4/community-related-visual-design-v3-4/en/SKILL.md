---
name: community-related-visual-design-v3-4
description: Create, revise, and review community visuals and posters, including public announcements, service guides, risk notices, event recruitment, and requests for help. Develop candidates and PNG/PDF deliverables from verified copy, the audience, and reference images. Default to one-shot full-image generation when the copy is short. Not intended for community software interfaces or standalone commercial advertising.
metadata:
  short-description: Community-Related Visual Design 3.4
---

# Community-Related Visual Design 3.4

This English entry shares the single resource set in the parent folder. Run all script commands from that parent skill root; resource paths in inline code are relative to it. The links below navigate directly to those shared reference cards.

Use this skill when creating, revising, or reviewing community visuals and posters. When only discussing the skill's rules, answer directly without starting production. Default to A3 portrait; follow the user's choice of landscape or another size. Before starting, lock the orientation, aspect ratio, and dimensions. All language versions share the same canvas, background image, and layout regions. The user's latest explicit requirements take priority.

## ⚠️ Required step for one-shot generation: let the user choose a style first (do not skip)

For one-shot generation, **before writing any prompt or generating any image**, first ask the user to choose a style and **wait for their answer**. Ask even when all source material is available. Skip this step only if the user has explicitly specified a style for this request or said “you decide.”

1. Run `python -I scripts/pick_styles.py --topic "<主题关键词>"`. The style library contains 12 styles (`assets/oneshot-styles.json`). Each run randomly draws 5: at least 2 should fit the topic, the rest should span different directions, and no more than 2 may belong to the same broad category.
2. **Use the platform's multiple-choice question tool so the user can click an option**, rather than sending only a block of text: use `AskUserQuestion` in Claude Code, and `request_user_input` in Codex (or the current platform's equivalent single-choice component). For each option, the label is the style name and the description is the script's `pitch` (one sentence that includes the color palette).
   - If the tool allows at most 4 options per question, add `--count 4` when running the script and use the 4 selected styles as the options. Leave the platform's built-in “其他/Other” field available for “you decide,” “show another set,” or the user's own description.
   - If the user chooses “show another set,” add `--exclude` with the previously shown IDs, draw again, and ask again.
   - Fall back to a text list (the script's `message` output) only when the current platform truly has no multiple-choice tool.
   Ask for missing facts, such as the date, location, or phone number, as another question in the same interaction.
3. After the user chooses, use `--id S06` to retrieve the chosen style's full preset (keywords, title lettering, body lettering, and palette), write it into `state.md`, and continue with the [one-shot generation card](../references/oneshot-mode.md). If the user's own style description is not in the library, follow that description and borrow the phrasing of the nearest preset.

## How to read the rules

At each stage, read only the **one corresponding card**. It already contains all rules needed for that stage; execute them directly after reading.

**One-shot generation** (default): Stage 1 card → [one-shot generation card](../references/oneshot-mode.md) (the style library is in `assets/oneshot-styles.json`; detailed phrasing is in [one-shot style presets](../references/oneshot-style-presets.md)).

**Step-by-step modes** (standard/quick):

| Stage | Stage card | User choice |
|---|---|---|
| 1 Setup: source material, master copy, and mode selection | [stage-1-setup](../references/stage-1-setup.md) | — (select the mode automatically by character count) |
| 2 Background image | [stage-2-background](../references/stage-2-background.md) | Choose a background |
| 3 Theme lettering (written directly onto the background) | [stage-3-title-type](../references/stage-3-title-type.md) | Choose theme lettering |
| 4 Body copy and layout (arranged directly on the background + title) | [stage-4-body-layout](../references/stage-4-body-layout.md) | Choose a layout |
| 5 Refinement, export, and delivery | [stage-5-finish-export](../references/stage-5-finish-export.md) | Confirm the finished design and choose delivery formats |

For landscape layouts or older audiences, also consult the [landscape and older-audience layout quick reference](../references/horizontal-and-elderly-layout.md). Use the tool cards throughout: before writing any image-generation prompt, use the [prompt templates](../references/prompt-templates.md) (for one-shot generation, use the full-image template in Section 9). Consult the [online prompt reference library](../references/web-prompt-library.md) when more phrasing examples are needed. Apply the [linking and decoration system](../references/linking-and-decoration.md) in all modes, especially the text–image interaction techniques in Section 7.

The other numbered files (01–31) are detailed archives. Consult them only when troubleshooting or handling a special case not covered by a stage card. If they conflict with a stage card, the stage card takes priority.

## Three modes

**Do not begin by asking which mode to use.** First read the source material, write the master copy, and count the text that will appear in the image (`scripts/count_copy.py`). When the user has not specified a mode, use one-shot generation directly for ≤160 characters; for >160 characters, ask once which mode to use. Use a step-by-step mode if the user says “let's do this step by step” or “I want to choose at each step.”

| Item | One-shot generation | Quick mode | Standard mode |
|---|---|---|---|
| Initial questions | Style (randomly draw 5 of 12 styles as clickable options) + missing facts | Missing facts | Missing facts |
| Reference library | Search by style + browse unfiltered reference-pool overview sheets + optionally supplement online | Search for a shortlist and open 1–2 original images | View all overview sheets and study 2–3 images closely |
| Background image | Not generated separately | 2 images in two styles | 3 images in three styles |
| Theme lettering | Not generated separately | 2 treatments, written directly onto the background | 3 treatments, written directly onto the background |
| Body copy | Generate **in the same pass** as the title, illustrations, and icons (do not split into two steps) | Add through image editing on the background + title | Same as quick mode |
| Layout candidates | Automatically generate 2 and automatically choose 1 | 1 treatment | 3 treatments |
| User choices during production | None | Background, theme lettering, and layout | Background, theme lettering, and layout |
| Review | Blind-read and compare the text + check clarity, color tone, and hierarchy | Once | Once |
| Printing/source files/other sizes | Ask after generating the image | Ask after generating the image | Ask after generating the image |
| Estimated time | About 8–12 minutes | About 20–25 minutes | Longer |

All modes retain: verified copy (do not change a single character of the master copy), generated artistic lettering for the main title, necessary icons, the linking and decoration system, text–image interaction techniques, and no solid rectangular backing box behind the main title. By default, body copy also uses artistic lettering drawn with the same pen as the title (draw it in during the second step of one-shot generation). Except for minimalist flat designs, text may be arranged freely with varied positioning; see Section 9 of the [linking and decoration system](../references/linking-and-decoration.md).

## Records

Maintain only one `state.md`: mode, current stage, master copy, selected IDs, latest file paths, and the prompt for every image generation (to support recreation and continuation). Perform checks internally and explain the result in one or two sentences in chat; do not write a separate check log. When resuming, read `state.md` first, continue from the current stage, and retain the selected content.

## Tools

- `scripts/count_copy.py`: Count the characters in copy that will appear in the image to select the mode (`state.md` or `--text`; `--body-only` counts only body copy).
- `scripts/find_reference.py`: Browse the layout-library catalog and search it (`--catalog-layout` for the entire library; examples include `--library posters --query "横版 敬老"` and `--query "手绘暖调插画"`). The reference library adds Group D (style references), Group E (information posters for older audiences), and Group H (16:9 landscape).
- `scripts/patch_text.py`: Repair a single remaining text error with a real font after redrawing, or use when the user requests body copy in a standard font (not the default).
- `scripts/pick_styles.py`: Randomly draw 5 of 12 styles (`--count 4` draws 4) for the user to click; use `--id` to view a full preset.
- `scripts/extra_refs.py`: Numbered overview sheets for the reference pool (200 built-in images, organized by D01–D15). Use `--domain D03 --grade A` to view only Grade A references for the topic (**use only for one-shot generation**; do not read in step-by-step modes).
- `scripts/export_print.py`: Convert the finished design to print dimensions (A3 at 300 dpi, bleed, and canvas extension to fit the aspect ratio).
- `scripts/build_editable_svg.py`: Text-free background + text-layer descriptions → an SVG with editable text.
- `scripts/select_type_references.py`: Browse the lettering-library catalog and produce a semantic shortlist (`--catalog --semantics "重阳 敬老"`).
- `scripts/verify_copy.py / check_linebreaks.py / check_layout.py / audit_poster_readability.py`: Use as needed; run `--help` on first use to view parameters.
- Execution: use `python -I` for scripts that use only the standard library; use `python -P` for pixel-processing scripts that need Pillow/NumPy (`-I` hides Pillow installed in the user directory).
- `visual_review.py`: Optional browser-based review with Label Studio, disabled by default. When enabling it, read [30](../references/30-human-review-and-feedback.md).
- `scripts/vendor/yaml` is a script dependency; keep it unchanged.
