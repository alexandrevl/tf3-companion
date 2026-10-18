# Design

## Context

See `proposal.md` for motivation. This change depends on `visual-identity` being applied first: it needs `assets/brand/tokens.json` (`themes.dark`, `themes.light`, `roles`, `modes`, `typography`), the logo SVGs in `assets/brand/` and `docs/brand/identity.md`.

Observed state of each surface (code read for this change):

- **HTML reports** (`src/tf3companion/reports.py`, `render_html`, lines 174-250): one inline `<style>` block with a Tailwind slate palette, light by default (`body { background: #ffffff }`) and a `@media (prefers-color-scheme: dark)` block (lines 198-207). A `:root` block defines `--c1..--c6` (line 182), but `_render_svg` uses them only for line series and pie slices (lines 286, 307); bar charts use fixed `#3b82f6` (>= 0) and `#ef4444` (< 0) (line 262). Text uses `currentColor`. The document model (`Chart(kind, title, categories, series)`, lines 56-61) has no notion of what a series groups by. Tables (`Table(columns, rows, align)`) carry no money or sign semantics. The existing test `test_html_escapes_entity_markup_and_has_no_external_dependencies` asserts the HTML has no `src`/`href` attributes and no `script` tag; an inline SVG satisfies it.
- **Markdown reports**: `render_markdown` emits ` ```mermaid ` blocks starting `pie title ...` or `xychart-beta` (lines 155-165) with no initialisation directive.
- **XLSX** (`src/tf3companion/export.py`): `FONT_NAME = "Arial"`, size 12; `_apply_font` rewrites every cell font (line 235); `_table` bolds the header row with no fill (line 62); charts (`LineChart`, `BarChart`, `PieChart`, lines 104-163) use openpyxl default colours. Chart categories on the data sheet are carrier names (`_charts_sheet`, line 195-197).
- **CLI** (`cli.py`): plain `print`; findings use emoji icons (line 30); everything else is `json.dumps` (line 18).
- **Agent voice**: `agent_instructions.md` already says "Cite the snapshot's game date, the numbers behind each conclusion", "use full entity names", "distinguish facts from uncertainty" and "Keep answers practical". It has no explicit ban on promotional wording.
- **MCP**: `src/tf3companion/mcp_server.py:18` builds `MCPServer(name=..., instructions=...)`. Installed `mcp` 2.3.0 (`uv.lock`; `.venv/lib/python3.14/site-packages/mcp/server/mcpserver/server.py`) accepts `website_url` and `icons: list[Icon]` on the server; `mcp_types.Icon` takes `src` (`http(s):` or `data:`), `mime_type`, `sizes`.
- **Packaging** (`pyproject.toml`): wheel force-includes `mod/tf3_companion_bridge` as `tf3companion/_mod/...`; `setup_tools.bundled_mod` reads the wheel resource first and falls back to the source checkout (`setup_tools.py:20-31`).
- **Tests**: no test pins a colour, CSS string, font or mermaid text (grep of `tests/` for hex values, `prefers-color`, `--c1`, `Arial`, `mermaid` finds only unrelated hits). Nothing needs deleting; new tests must assert behaviour.

## Goals / Non-Goals

**Goals:**

- Every surface takes colours and typefaces from the token file through one loader.
- Sign and mode colours follow `brand-identity` semantics (blue positive, coral negative, mode tokens for carriers).
- No new dependency, no network access, HTML stays self-contained.

**Non-Goals:**

- Colouring table cells by sign (tables have no money semantics; adding them is a report-model change).
- Pixel-matching the mock-ups of the game UI; bundling fonts; ANSI output.

## Decisions

**D1. One loader, `src/tf3companion/brand.py`.** It exposes: `tokens()` (parsed, cached JSON, validated for the keys the surfaces need), `theme(name)`, `mode_token(carrier)` (unknown or missing carrier -> `mode-other`), `mode_series(n)` (mode tokens in table order, cycling), and `logo_svg(variant)` returning the SVG text. It reads files with the same wheel-first, checkout-fallback strategy as `setup_tools.bundled_mod`. Missing file or key raises `ConfigError` naming the file and token (spec: no silent fallback). Alternative: each surface parses the JSON itself (rejected: breaks the single-source rule). Alternative: generate Python constants at build time (rejected: extra build step, drift risk).

**D2. Packaging.** The source of truth stays `assets/brand/` (created by `visual-identity`). `pyproject.toml` adds force-includes `assets/brand/tokens.json` and the logo SVGs the runtime reads (`logo-mark.svg`, `logo-mark-light.svg`) into `tf3companion/_brand/`. Alternative: move the files under `src/tf3companion/` (rejected: `visual-identity` and `mod-listing-assets`/`scripts/make_assets.py` already reference `assets/brand/`). A test builds nothing; it asserts the loader resolves in the checkout, and the verification task inspects a built wheel listing for `_brand/tokens.json`.

**D3. HTML.** `render_html` builds the `<style>` block from the loader: `:root` holds the dark theme variables (`--canvas`, `--surface`, `--border`, `--text`, `--text-muted`, `--accent`, `--positive`, `--negative`, `--mode-*`), followed by `@media (prefers-color-scheme: light) { :root { ... } }` for the light values. Existing rules switch from literal hex to `var(--...)`. `font-family` is the `typography` sans stack (Lato first) and `font-variant-numeric: tabular-nums` applies to `td`, `.header` and SVG text. Dark default matches the spec and reverses today's light default; this is deliberate. Alternative: `light-dark()` CSS (rejected: no default-dark control and weaker browser support). `Chart` gains an optional `group: str | None` (`"mode"` when categories or series labels are carrier names; default `None`). `_render_svg` then picks: bar sign colour `var(--positive)`/`var(--negative)` when `group` is `None` and values are signed; `var(--mode-x)` per category when `group == "mode"`; line and pie series use mode tokens in table order otherwise. Carrier callers set `group="mode"` (the "Annual profit by mode" / "Vehicle Mix by Mode" charts in `reports.py`, around line 395). The old `--c1..--c6` variables are deleted (clean cutover). The logo: the header gets an inline `<svg>` of the dark mark plus one of the light mark, each wrapped in an element toggled by the same `prefers-color-scheme` media query, so no JS and no `<img>`/`href`. The header shows only logo + title, no tagline (analytic register, D6).

**D4. Spreadsheet theme: Proposed default, confirm with the player.** `visual-identity` says a single-theme surface uses dark. A dark-filled workbook prints badly, inflates ink use and is unusual to read in Excel/Sheets. Proposed default: body cells and chart areas keep the light theme values (white/`surface` background, `text` font colour), while every table header row gets the dark `canvas` fill with dark-theme `text` (and `accent` bottom border), so the brand reads at the top of each sheet. Chart series use light-theme mode tokens; sign colouring uses light `positive`/`negative`. Typeface stays Arial 12 (spec D5 of `visual-identity`). This is recorded as a requirement in this change's `surface-branding` spec, not as an open question, because it changes the tasks. Coordination: when both changes are archived, `visual-identity`'s requirement "Dark theme is the default" should gain one sentence "except spreadsheets, see surface-branding"; this change cannot edit it (not in main specs yet). Needs the player's confirmation before implementation: dark header + light body vs fully dark vs fully light. Alternative rejected: fully dark workbook.

**D5. CLI: no ANSI.** Terminal output is 90% JSON (`cli.py:18`) intended for piping; findings use emoji icons. Adding colour would need `NO_COLOR`, `isatty` and Windows console handling for little brand value. Spec requires plain output. Revisit only if the player asks; honouring `NO_COLOR`/pipes would then be mandatory.

**D6. Agent voice.** The analytic register is largely satisfied. Minimal edit: append one sentence to "Safety and style" in `agent_instructions.md`: "State the figure and the full entity name first, then the judgement; never use promotional wording." No other change. `tests/test_agent_experience.py` does not pin that paragraph (grep for `Safety`/`practical` returns nothing), and the new test only asserts the instructions load.

**D7. Mermaid.** For each block, `render_markdown` writes before the diagram keyword a directive such as `%%{init: {"theme": "base", "themeVariables": {...}}}%%`, using dark-theme token values: for `pie`, `pie1..pieN` from mode tokens in table order plus `pieTitleTextColor`, `pieSectionTextColor`, `pieLegendTextColor` from `text`; for `xychart-beta`, `xyChart.plotColorPalette` from the same tokens plus `backgroundColor`, `titleColor` and axis colours from the dark theme (`canvas`, `text`) so the chart carries its own dark background on a light page. Caveats (recorded in `docs/reports.md`): GitHub, VS Code and Obsidian support `%%{init}%%` to different degrees and versions; `xychart-beta` colour variables are version-dependent; mermaid may order pie slices by value, so slice colours may not follow table order. Because renderers can ignore the directive, every slice or series keeps its text label, and the Markdown stays valid mermaid. Alternative: a frontmatter `---config:---` block (rejected: newer, less portable). Alternative: no styling (rejected: Markdown is the default report format).

**D8. XLSX mechanics.** `export.py` imports the loader. Header rows: `PatternFill` from dark `canvas`, `Font(color=text)` bold. Chart series: `series.graphicalProperties.solidFill` from light mode tokens; for carrier-grouped single-series bar charts, per-point `DataPoint` fills by category; for signed bars, `invertIfNegative` plus `negative`/`positive` data points. `_apply_font` must not overwrite header font colour (today it resets every cell font to Arial bold/regular, line 235); it keeps name and size but preserves colour. Pie charts: one `DataPoint` per slice in mode-token order.

**D9. README banner.** `scripts/make_assets.py` (owned by `visual-identity`/`mod-listing-assets`) renders the logo PNG; this change only references the PNG already produced in `assets/brand/` (or `assets/art/logo-source.png`; the task picks whichever exists after `visual-identity`, preferring a dedicated banner export if the guide defines one) and links `docs/brand/identity.md`. The README keeps its non-affiliation paragraph.

**D10. MCP icon.** Pass `website_url` (the repository URL already in project metadata or the README) and `icons=[Icon(src="data:image/svg+xml;base64,...", mime_type="image/svg+xml", sizes=["any"])]` to `MCPServer`, built from `brand.logo_svg("dark")`. `data:` avoids a network URL (no-network rule). Risk: the library docstring warns consumers about SVG scripts; our SVG has none, and a test asserts that. Support in clients varies; the field is optional metadata.

**D11. `modinfo.json` untouched.** `mod-listing-assets` owns that copy; this change adds no edit there and no dependency on its cover assets.

## Risks / Trade-offs

- [Dark HTML default surprises users used to light reports] -> `prefers-color-scheme: light` still gives light; documented in `docs/reports.md` and the changelog.
- [Mermaid theming differs by renderer] -> text labels always present; caveats documented; player checks one real renderer (task 7.2).
- [Dark header over light spreadsheet body looks inconsistent] -> proposed default needs player confirmation (D4); switching means changing only the fill tokens used in one helper.
- [Lato not installed, layout shifts] -> documented fallback stack; tabular numerals only where supported.
- [Token file grows keys the loader does not know] -> loader validates only required keys; extra keys ignored.
- [Wheel omits brand files] -> force-include plus a wheel-listing check in the final task.
- [Mode colour rail/tram closeness] -> legends and labels always name the series (inherited from `visual-identity`).

## Migration Plan

Nothing to migrate: reports and exports are regenerated on demand; old files are unaffected. Rollback is reverting the commit; `--c1..--c6` disappear with it. After archive, add the one-sentence spreadsheet exception to `brand-identity`'s theme requirement (see D4).

## Open Questions

- Which README banner file name `visual-identity` ends up producing; decided at task 6.1 by reading `assets/brand/` and `scripts/make_assets.py`. Does not change specs or the task breakdown.
