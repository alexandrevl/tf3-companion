# Design

## Context

See proposal.md for motivation. Observed state that shapes the identity:

- Transport Fever 3's interface theme (`base/content/gui.zip:gui/main/default_colors.gres.lua`) derives every panel and
  accent colour from one hue, 210, in HSV: a base ramp at saturation 0.25, value 0.12 to 0.35, and an accent ramp at
  saturation 0.55, value 0.35 to 0.95. Named colours live in `gui/main/color_internal.lua`.
- The game maps `Positive` to light blue `#8AB9F1` and `Negative` to light coral `#F08080`. `Ok`, `Warning`, `Error`
  and `Info` are `#4CBB17`, `#DAA520`, `#CE2029` and `#2D68C4`. `Highlight` is yellow.
- The game has no colour per transport mode. Line colours are a generic 10x5 grid (`gui/line_vehicle_mgmt/line_colors.gres.lua`),
  and chart series use six generic named colours (`gui/main/chart_colors.gres.lua`).
- The interface typeface is Lato (`base/content/locale.zip:locale/Lato2OFL/`), licensed under the SIL OFL.
- The official site (transportfever3.com) uses `#22282E` as its theme colour, the game's `BaseDarkMedium`, and writes copy
  in a short tycoon register ("Run your company like a true tycoon", "Steam and jetstream").
- Carriers in the game API (`api/tealdef/api/type.d.tl`, `Carrier`) are `ROAD`, `RAIL`, `TRAM`, `AIR` (planes and
  helicopters), `WATER` and `OTHER`. The companion groups lines with no vehicle as "NO VEHICLE".
- Current surfaces: HTML reports already use CSS custom properties `--c1..--c6` and a dark media query, the XLSX export
  uses Arial 12, and Markdown reports use mermaid charts.

Colours below are values, not code. They are cited with their source names so a reviewer can check them against the game
files.

## Goals / Non-Goals

**Goals:**
- A player who knows the game should see the Companion as part of that world at a glance.
- The logo explains the product journey: the mod is only the first stop.
- Every colour decision is reproducible from the token file and checkable for contrast.

**Non-Goals:**
- Pixel-identical copies of game UI components or screens.
- A design system with components, spacing scales or iconography. Tokens stop at colour, type and voice.
- Animated or motion branding.

## Decisions

**D1. Direction: metro map meets circuit board, with ledger details.** Lines are the product's central entity and the
game's own vocabulary, and a metro-map style turns them into a mark and a series palette. Transit maps and printed
circuit boards share one grammar (0/45/90-degree routing, rounded bends, round nodes), so the same line reads as a track
and as a trace: game data travelling to an AI agent. The chip, the database and small chip-shaped "trains" are the only
technology motifs. Numbers are set in tabular figures, like a ledger, because the product is an analyst. Rejected
alternatives: a split-flap departure board (strong but kitsch, weak at small sizes), a pure blueprint or ledger look
(reads as accounting software, not transport), a low-poly night landscape (pretty, but says nothing about agents), and
thought bubbles, sparkles, brains or robots (AI clichés that contradict the evidence-first voice).

**D2. Base and accent are the game's ramps, not lookalikes.** Matching the game exactly is what makes the product feel
native. Resemblance to an official product is managed through the mark and the disclaimer (D9), not by shifting hues.
Rejected alternative: our own navy and amber palette, which looks good but foreign beside the game.

Dark theme (default):

| Token | Hex | Source | Role |
| --- | --- | --- | --- |
| `canvas` | `#171B1F` | BaseVeryDark | page and cover background |
| `surface` | `#1D2126` | BaseDark | cards, tables |
| `surface-raised` | `#22282E` | BaseDarkMedium | headers, panels |
| `border` | `#343C45` | BaseLight | dividers |
| `border-strong` | `#434E59` | BaseVeryLight | focus, hover |
| `text` | `#E6E6E6` | gray90 | body text (13.9:1 on canvas) |
| `text-muted` | `#B3B3B3` | gray70 | captions (8.3:1) |
| `accent` | `#6DB0F2` | AccentVeryLight | links, the logo's route line |
| `accent-deep` | `#345373` | AccentDark | selection, bands |
| `signal` | `#FFC40C` | schoolBus | logo arrow, marketing only |

Light theme: same hue, inverted.

| Token | Hex | Contrast on canvas |
| --- | --- | --- |
| `canvas` | `#F2F6FA` | - |
| `surface` | `#E4EAF0` | - |
| `surface-raised` | `#FFFFFF` | - |
| `border` | `#CCCCCC` | - |
| `border-strong` | `#B3B3B3` | - |
| `text` | `#171B1F` | 15.9:1 |
| `text-muted` | `#4D4D4D` | 7.8:1 |
| `accent` | `#345373` | 7.4:1 |
| `accent-deep` | `#B9D9EB` | - (fill only) |
| `signal` | `#A87700` | 3.7:1 (graphic only) |

**D3. Semantics follow the game.** Players already read blue as positive in the game, so profit is blue, not green.
Green is left for the `ok` status. Rejected alternative: green/red finance convention, which would contradict what
players see in the game.

| Token | Dark | Light | Use |
| --- | --- | --- | --- |
| `positive` | `#8AB9F1` | `#2D67C2` | profit, money in |
| `negative` | `#F08080` | `#C40234` | loss, critical finding text |
| `ok` | `#4CBB17` | `#2E7D0F` | status badge |
| `warning` | `#DAA520` | `#8A6100` | status badge, warning finding |
| `error` | `#D02029` | `#C40234` | icon or badge only on dark (3.0:1 on surface) |
| `info` | `#2D69C6` | `#2D67C2` | icon or badge only (3.0:1 on dark surface) |

`error` (dark), `info` (dark) and `positive` (light) are the game's colours nudged in lightness by the smallest step
that reaches 3:1 (graphics) or 4.5:1 (text) against both `canvas` and `surface`; the game values fell just short on
`surface`.

**D4. Mode palette uses the hues the semantics leave free.** Semantics occupy blue (210), coral (0), gold (45) and green
(100-150). Modes take orange, violet, magenta, cyan and lemon from the game's named and line colours, plus a neutral.

| Token | Dark | Light | Carrier |
| --- | --- | --- | --- |
| `mode-rail` | `#C38FFF` | `#6F2DA8` | RAIL |
| `mode-road` | `#FF8C00` | `#B85600` | ROAD |
| `mode-tram` | `#D86FC6` | `#A3308F` | TRAM |
| `mode-water` | `#39C6C6` | `#007A7A` | WATER |
| `mode-air` | `#FFFF73` | `#7A6A00` | AIR (planes and helicopters) |
| `mode-other` | `#999999` | `#666666` | OTHER, NO VEHICLE |

All mode tokens reach at least 3.9:1 on canvas and surface in both themes. Rail and tram are the closest pair (violet
and magenta), and legends must always label them. Generic multi-series charts that are not grouped by mode use the mode
tokens in table order.

**D5. Typography.** Lato for the brand and for HTML (Bold for headings, Regular for body), with the stack
`Lato, "Segoe UI", "Helvetica Neue", Arial, sans-serif`. Figures use tabular numerals where the medium supports them.
The XLSX export keeps Arial, because a font missing on the player's machine is silently replaced. The wordmark sets
"TF3 Companion" in Lato Bold, with "Bridge" as a Regular suffix for the mod. The font is never redistributed from the game
files; Lato is available from its upstream OFL release.

**D6. Mark geometry.** A 16-unit route stroke with rounded caps and joins traces a "C" from the top station (the game)
through the left station (the Companion) to the bottom station (the AI agent), then turns 45 degrees upward into a
chevron arrow in `signal`. The game and agent stations are filled circles in `text` with an `accent` ring, radius 12
units on a 200x200 canvas. The Companion station is a 36-unit rounded square in `text` with an `accent` ring and two
short pins on each side: an interchange on a metro map, a chip on a board. The 32 px variant drops the pins and rings and
thickens the stroke, keeping only the square-versus-circle contrast. The lockup places the mark left of the wordmark,
with the mark's height equal to two cap heights. The station meanings are part of the brand story told on the cover,
README and listing.

**D7. Voice.**

| Register | Surfaces | Rules | Example |
| --- | --- | --- | --- |
| Marketing | listing, README, cover | short lines, tycoon vocabulary, dash subtitles; no unsupported claims | "Ask your company anything - lines, loads and losses." |
| Analytic | reports, exports, agent answers | figure and entity first, evidence before judgement, no hype | "Coal Express lost 3,100 over the rolling year." |

The analytic register already matches `src/tf3companion/agent_instructions.md`. The follow-up application change decides
whether that file needs edits.

**D8. Generated art is illustration only.** Generators cannot render reliable text or exact colours, so every asset
that carries names or labels (logo, cover, README banner) is vector, drawn from the tokens. External generators produce
text-free illustrations only, from prompts that state the canvas colour, the transit-map-and-circuit style and the
exclusions: no text, no logos, no game UI, no recognisable official vehicles or box art, no AI clichés. Exploration
images produced while choosing the direction were discarded once the vector cover was chosen.

**D9. Distinctness from official branding.** Same colours, different mark. The mark, wordmark layout and illustrations
are original, and every marketing surface carries the existing non-affiliation disclaimer. Rejected alternative:
shifting the palette away from the game, which would give up the native feel the player asked for.

**D10. Token file format.** One JSON file at `assets/brand/tokens.json` with `themes.dark` and `themes.light`, each
mapping token name to hex, plus `typography`. JSON is readable by Python without new dependencies and can be turned into
CSS custom properties, openpyxl colours and mermaid `themeVariables` by the follow-up change. Rejected alternatives: CSS
as the source, which is awkward to read from Python, and the W3C design-tokens format, which is heavier than this small
set needs.

**D11. Cover map.** The cover (`assets/brand/cover.svg`, 1920x1080, `canvas` background) is a transit map of the
product. The snapshot database is the left terminus, an agent speech bubble the right terminus, and the game the top
terminus. A chip labelled "MCP" with "TF3 Companion" beneath sits at the centre, inside the central 1080x1080 square, and
every line passes through its pins. Two or three small chip-shaped "trains" ride the lines. The lockup "TF3 Companion
Bridge", a one-line marketing tagline and the non-affiliation disclaimer sit outside the map's busy area. Lines follow
the working method in `src/tf3companion/agent_instructions.md`:

| Line | Colour | Stations: label / tool |
| --- | --- | --- |
| Diagnose | `accent` | Status / `status`, Findings / `findings`, Line detail / `line_detail`, Vehicle catalog / `vehicle_catalog` |
| Grow | `mode-road` | Industries / `list_industries`, Opportunities / `opportunities`, Stocks / `list_stocks` |
| Report | `mode-rail` | Your game (bridge mod), Refresh / `refresh`, Company history / `company_history`, Reports / `report`, Spreadsheet / `export_spreadsheet` |
| Decide | `mode-tram` | Decisions / `record_decision`, Notes / `save_notes` |

Labels are Lato for the human name and a monospaced face for the tool name beneath it. On marketing art, mode tokens
colour illustrative lines; on data surfaces they keep meaning carriers only. The logo source for the listing is rendered
from the mark, not cropped from the cover, so the cover's centre holds the chip rather than the logo. Rejected
alternatives: an empty centre for the logo (loses the hub that explains the product) and human labels only (loses the
authenticity that MCP users recognise).

## Risks / Trade-offs

- [Players may mistake the Companion for an official product, given the identical palette] → original mark and
  wordmark, the disclaimer on every marketing surface, and a review check for official marks in generated art.
- [Hue-210 values may change in a future game patch] → the tokens are a snapshot of build 40420 and stay fixed; game
  drift does not change the brand.
- [Rail violet and tram magenta can be confused by colour-blind readers] → legends always label series, and
  mode-grouped tables carry the carrier name. The follow-up change can add patterns if needed.
- [Lato missing on a player's machine] → documented fallback stack; the XLSX export keeps Arial.
- [Image generators produce text or lookalike marks] → prompts forbid them, and every image is reviewed against the
  "Distinct from official marks" requirement before use.
- [Signal yellow sits close to the warning gold] → signal never appears on data surfaces, so the two never meet.
- [A cover station names a tool that is later renamed or removed] → a throwaway check during apply compares every tool
  name in `assets/brand/cover.svg` with the MCP server's tool list, and the pre-upload checklist in
  `docs/publishing-mod.md` repeats it.
- [Fourteen labelled stations crowd a 1920x1080 cover, and the Mod Hub thumbnails it at 180p] → labels are sized for
  720p legibility; at 180p only the lines, chip and termini need to read, and the in-game check confirms it.

## Migration Plan

Nothing to migrate: no surface consumes the tokens yet. The follow-up application change replaces the HTML report
palette, mermaid defaults and XLSX chart colours with the tokens. Rollback is deleting the new files.
