# TF3 Companion brand identity

This guide defines the look and voice of TF3 Companion: colours, type, logo, cover and writing. Every colour and typeface comes from one file, [`assets/brand/tokens.json`](../../assets/brand/tokens.json). If this guide and the file disagree, the file wins and this guide is the defect.

## Concept: metro map meets circuit board

Lines are the product's central entity and the game's own vocabulary. A transit map turns them into a mark and a palette. A transit map and a printed circuit board share one grammar: routing at 0, 45 and 90 degrees, rounded bends and round nodes. So the same line reads as a track and as a trace: game data travelling to an AI agent.

Technology motifs are limited to three: the chip, the database cylinder and the speech bubble. Small chip-shaped "trains" may ride the lines. Numbers are set in tabular figures, like a ledger, because the product is an analyst.

Not used: brains, robots, sparkles, thought bubbles, split-flap boards, blueprint or ledger looks, low-poly landscapes.

### What the three stations mean

The mark is a route drawn as a "C" through three stations, ending in an upward arrow.

| Station | Shape | Meaning |
| --- | --- | --- |
| Top | Round | The game (Transport Fever 3 and its bridge mod) |
| Left, in the middle of the "C" | Square with pins (a chip) | The Companion: the local analyst and its MCP server |
| Bottom | Round | The AI agent that reads the data |

The mod is only the first stop. The arrow shows the journey continuing.

## Where the colours come from

The base and accent colours are the values Transport Fever 3's interface derives from one hue, 210 in HSV. Matching the game is what makes the Companion feel native, so the palette is not shifted away from it. Resemblance to the official product is handled by an original mark and the disclaimer below.

- Panel and accent colours come from the interface theme in `base/content/gui.zip:gui/main/default_colors.gres.lua`: a base ramp at low saturation and an accent ramp at higher saturation, both at hue 210. Named colours are in `gui/main/color_internal.lua`.
- The game's `Positive` and `Negative` colours (light blue and light coral) give profit and loss their colours.
- The game has no colour per transport mode. Line colours are a generic grid in `gui/line_vehicle_mgmt/line_colors.gres.lua` and chart series use generic named colours in `gui/main/chart_colors.gres.lua`. The mode palette is therefore our own, built from the hues the semantic colours leave free.
- The interface typeface is Lato, shipped under `base/content/locale.zip:locale/Lato2OFL/`.

The tokens are a snapshot of game build 40420 and stay fixed if a later patch changes the game's values.

## Colour tokens

Dark is the default theme. A surface that supports one theme only uses dark. Light uses the same roles with values derived from the same hue.

**Contrast** is the WCAG ratio against the theme's `canvas` / `surface`. Text tokens must reach 4.5:1 against both. Graphic tokens (icons, badges, chart series, lines) must reach 3:1. Tokens below 4.5:1 are not for text.

### Dark theme

Backgrounds and decoration (no contrast requirement):

| Token | Hex | Role |
| --- | --- | --- |
| `canvas` | `#171B1F` | Page and cover background |
| `surface` | `#1D2126` | Cards, tables |
| `surface-raised` | `#22282E` | Headers, panels |
| `border` | `#343C45` | Dividers |
| `border-strong` | `#434E59` | Focus, hover |
| `accent-deep` | `#345373` | Selection, bands |

Text tokens:

| Token | Hex | Role | vs canvas | vs surface |
| --- | --- | --- | --- | --- |
| `text` | `#E6E6E6` | Body text | 13.87:1 | 12.97:1 |
| `text-muted` | `#B3B3B3` | Captions | 8.26:1 | 7.72:1 |
| `accent` | `#6DB0F2` | Links, the logo's route line | 7.54:1 | 7.04:1 |
| `positive` | `#8AB9F1` | Profit, money in | 8.48:1 | 7.93:1 |
| `negative` | `#F08080` | Loss, critical finding text | 6.68:1 | 6.24:1 |

Graphic tokens (never text):

| Token | Hex | Role | vs canvas | vs surface |
| --- | --- | --- | --- | --- |
| `signal` | `#FFC40C` | Logo arrow, marketing only | 10.84:1 | 10.14:1 |
| `ok` | `#4CBB17` | Status badge | 6.95:1 | 6.49:1 |
| `warning` | `#DAA520` | Status badge, warning finding | 7.74:1 | 7.23:1 |
| `error` | `#D02029` | Icon or badge | 3.23:1 | 3.02:1 |
| `info` | `#2D69C6` | Icon or badge | 3.25:1 | 3.04:1 |
| `mode-rail` | `#C38FFF` | RAIL | 7.17:1 | 6.70:1 |
| `mode-road` | `#FF8C00` | ROAD | 7.42:1 | 6.94:1 |
| `mode-tram` | `#D86FC6` | TRAM | 5.78:1 | 5.40:1 |
| `mode-water` | `#39C6C6` | WATER | 8.30:1 | 7.76:1 |
| `mode-air` | `#FFFF73` | AIR (planes and helicopters) | 16.33:1 | 15.26:1 |
| `mode-other` | `#999999` | OTHER, NO VEHICLE | 6.08:1 | 5.68:1 |

### Light theme

Backgrounds and decoration:

| Token | Hex | Role |
| --- | --- | --- |
| `canvas` | `#F2F6FA` | Page background |
| `surface` | `#E4EAF0` | Cards, tables |
| `surface-raised` | `#FFFFFF` | Headers, panels |
| `border` | `#CCCCCC` | Dividers |
| `border-strong` | `#B3B3B3` | Focus, hover |
| `accent-deep` | `#B9D9EB` | Selection, bands (fill only) |

Text tokens:

| Token | Hex | Role | vs canvas | vs surface |
| --- | --- | --- | --- | --- |
| `text` | `#171B1F` | Body text | 15.94:1 | 14.28:1 |
| `text-muted` | `#4D4D4D` | Captions | 7.78:1 | 6.97:1 |
| `accent` | `#345373` | Links, the logo's route line | 7.35:1 | 6.59:1 |
| `positive` | `#2D67C2` | Profit, money in | 5.05:1 | 4.52:1 |
| `negative` | `#C40234` | Loss, critical finding text | 5.68:1 | 5.09:1 |

Graphic tokens (never text):

| Token | Hex | Role | vs canvas | vs surface |
| --- | --- | --- | --- | --- |
| `signal` | `#A87700` | Logo arrow, marketing only | 3.65:1 | 3.27:1 |
| `ok` | `#2E7D0F` | Status badge | 4.77:1 | 4.27:1 |
| `warning` | `#8A6100` | Status badge, warning finding | 5.10:1 | 4.57:1 |
| `error` | `#C40234` | Icon or badge | 5.68:1 | 5.09:1 |
| `info` | `#2D67C2` | Icon or badge | 5.05:1 | 4.52:1 |
| `mode-rail` | `#6F2DA8` | RAIL | 7.39:1 | 6.62:1 |
| `mode-road` | `#B85600` | ROAD | 4.43:1 | 3.97:1 |
| `mode-tram` | `#A3308F` | TRAM | 5.73:1 | 5.13:1 |
| `mode-water` | `#007A7A` | WATER | 4.76:1 | 4.26:1 |
| `mode-air` | `#7A6A00` | AIR (planes and helicopters) | 4.97:1 | 4.46:1 |
| `mode-other` | `#666666` | OTHER, NO VEHICLE | 5.29:1 | 4.74:1 |

### Where we departed from the game

The game's `Ok`, `Warning`, `Error`, `Info`, `Positive` and `Negative` colours are `#4CBB17`, `#DAA520`, `#CE2029`, `#2D68C4`, `#8AB9F1` and `#F08080`. Three of our tokens are the game values nudged in lightness by the smallest step that reaches the contrast target, because the game values fell just short on `surface`:

- Dark `error`: `#D02029` (game `#CE2029`).
- Dark `info`: `#2D69C6` (game `#2D68C4`).
- Light `positive`: `#2D67C2`, nudged from the game's blue to pass 4.5:1 for text on a light background.

The dark base and accent ramp values match the game's theme. Mode colours are our own selections and adaptations from its named colours; they are not an official per-carrier palette.

### Colour-role rules

1. **Semantic and mode colours stay separate.** Semantic tokens (`positive`, `negative`, `ok`, `warning`, `error`, `info`) say how something is going. Mode tokens (`mode-*`) say which carrier it is. Never use a semantic token as a series or mode colour, and never use a mode token to say good or bad.
2. **Mode colours on art vs data.** On marketing art (cover, README illustrations) mode colours may colour illustrative lines. On data surfaces (reports, charts, exports) they mean carriers only. Vehicles with no carrier, or an unknown one, use `mode-other`. Rail (violet) and tram (magenta) are the closest pair, so legends always label them.
3. **Profit is blue, loss is coral.** `positive` for money in and profitable lines, `negative` for losses. This follows the game, where players already read blue as positive. Green means `ok` status only, never profit.
4. **Signal is reserved.** `signal` appears only in the brand mark and on marketing surfaces (cover, listing art, README banner). It never marks warnings, highlights or data. Warnings use `warning`.
5. **`error` and `info` are never text.** They sit just above 3:1 on dark. Use `negative` for error text and `text` or `accent` for informational text. `error` and `info` colour only an icon or a badge.
6. **Generic charts.** A multi-series chart that is not grouped by mode takes the mode tokens in table order (rail, road, tram, water, air, other).
7. **Dark by default.** If no preference is expressed, use the dark values.
8. **No stray colours.** A branded surface that shows a colour outside the token set is a defect.

## Typography

| Use | Typeface | Notes |
| --- | --- | --- |
| Brand, HTML, documents | Lato: Bold 700 for headings, Regular 400 for body | Stack: `Lato, "Segoe UI", "Helvetica Neue", Arial, sans-serif`. If Lato is missing, fall back along this stack, never to an unrelated display face. |
| Tool names, code, identifiers | System monospace | Stack: `ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace` |
| Spreadsheet (XLSX) export | Arial | A font missing on the player's machine is silently replaced, so spreadsheets keep Arial. |

- Figures use tabular numerals wherever the medium supports them, so columns of money line up.
- The wordmark sets "TF3 Companion" in Lato Bold, with "Bridge" as a Regular suffix for the mod.
- Lato is licensed under the SIL Open Font License. Obtain it from its upstream release. Never copy font files out of the game's files, and do not commit font files to this repository.

## Logo

Files in [`assets/brand/`](../../assets/brand/):

| File | Use |
| --- | --- |
| `logo-mark.svg` | Full-colour mark on dark backgrounds (transparent background) |
| `logo-mark-light.svg` | Full-colour mark on light backgrounds |
| `logo-mark-32.svg` | Simplified mark for 32 px and below: no pins or rings, thicker stroke |
| `logo-mono.svg` | Single colour, set with `currentColor`, for surfaces that cannot use colour |
| `logo-lockup.svg` | Mark left of the "TF3 Companion" wordmark, on dark |

Rendered references: [`assets/art/logo-source.png`](../../assets/art/logo-source.png) (listing logo, rendered from the mark) and [`assets/art/cover.png`](../../assets/art/cover.png) (the cover).

- **Clear space:** keep a margin around the logo at least as tall as the Companion's square station.
- **Minimum size:** 32 px. Use `logo-mark-32.svg` at 32 px and any size up to about 48 px. At 32 px the "C", the square station, the two round stations and the arrow must still be distinguishable.
- **One colour:** when colour is not available, use `logo-mono.svg`. Do not recolour a full-colour file.

Do:

- Use the file that matches the background (dark or light).
- Keep the mark's proportions and the lockup's layout.
- Put the non-affiliation disclaimer on every marketing surface that carries the logo.

Don't:

- Recolour, tint or swap token colours in the mark.
- Stretch, squash, rotate or crop it.
- Add shadows, glows, outlines, gradients or other effects.
- Place it next to, over or merged with the Transport Fever logo or any Urban Games or Paradox Interactive mark.
- Redraw the mark from memory; copy the SVG.

## The cover map

[`assets/brand/cover.svg`](../../assets/brand/cover.svg) is a 1920x1080 transit map of the product on the `canvas` colour. The snapshot database is the left terminus, the AI agent's speech bubble the right terminus and the game the top terminus. A chip labelled "MCP", with "TF3 Companion" beneath, sits at the centre inside the central 1080x1080 square, and every line passes through its pins. The lockup, a one-line tagline and the disclaimer sit outside the busy area. The Mod Hub thumbnails the cover small, so at tiny sizes only the lines, chip and termini need to read.

The four lines follow the working method the agent already uses (`src/tf3companion/agent_instructions.md`):

| Line | Colour | Stations: label / tool |
| --- | --- | --- |
| Diagnose | `accent` | Status / `status`, Findings / `findings`, Line detail / `line_detail`, Vehicle catalog / `vehicle_catalog` |
| Grow | `mode-road` | Industries / `list_industries`, Opportunities / `opportunities`, Stocks / `list_stocks` |
| Report | `mode-rail` | Your game (bridge mod), Refresh / `refresh`, Company history / `company_history`, Reports / `report`, Spreadsheet / `export_spreadsheet` |
| Decide | `mode-tram` | Decisions / `record_decision`, Notes / `save_notes` |

Labels use Lato for the human name and the monospace stack for the tool name beneath it. A reader who knows nothing about MCP should understand the map from the human labels alone.

**Rule: a station never names a tool that does not exist.** When an MCP tool is renamed or removed, update or remove its station before the next listing upload.

How to check: list the registered tool names from the server and confirm each monospace tool name in `cover.svg` is among them.

```sh
uv run python -c "import asyncio; from tf3companion.mcp_server import server; print(sorted(t.name for t in asyncio.run(server.list_tools())))"
```

Tool names are registered in `src/tf3companion/mcp_server.py`. The tool names on the cover are the monospace labels in `cover.svg`.

## Voice

Two registers.

| Register | Surfaces | Rules | Example |
| --- | --- | --- | --- |
| Marketing | Mod listing, README, cover | Short lines, tycoon vocabulary, dash subtitles. No claim the product cannot back. | "Ask your company anything - lines, loads and losses." |
| Analytic | Reports, exports, agent answers | Line or entity name and figure first, evidence before judgement, no hype or promotional adjectives. | "Coal Express lost 3,100 over the rolling year." |

Both registers are plain, concise English. The analytic register must state numbers and evidence before any judgement and treat missing data as unknown, not zero.

## Non-affiliation

The project looks like it belongs in the game, so it must never look like it is the game's publisher. The mark, wordmark layout and illustrations are original. Brand assets must not include or imitate the Transport Fever logo, wordmark, box art, icons or other Urban Games or Paradox Interactive artwork.

Every marketing surface (mod listing, README, cover, social preview, banner) carries this sentence:

> Not affiliated with or endorsed by Urban Games or Paradox Interactive.

Transport Fever is their trademark and is named only descriptively.

## In-game check

The cover and logo must still read when viewed in the Mod Hub. The player checks, in the game, that the 1920x1080 cover is legible at the listing's thumbnail size and that the logo source is crisp. Only the player can fill this in.

Result: Not yet verified.
