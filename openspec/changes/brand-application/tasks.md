# Tasks

Prerequisite: `visual-identity` is applied, so `assets/brand/tokens.json`, the logo SVGs and `docs/brand/identity.md` exist. Do not start group 1 until `ls assets/brand/tokens.json docs/brand/identity.md` succeeds.

## 1. Token loader and packaging

- [ ] 1.1 Add `src/tf3companion/brand.py` with `tokens()`, `theme(name)`, `mode_token(carrier)`, `mode_series(n)` and `logo_svg(variant)`, resolving files wheel-first then from `assets/brand/` (same strategy as `setup_tools.bundled_mod`); a missing file or token raises `ConfigError` naming it. Verify with `uv run pytest tests/test_brand.py` covering: both themes load, unknown carrier and `NO VEHICLE` map to the other-mode token, a missing token raises, `logo_svg` output parses as XML and contains no `<script>`.
- [ ] 1.2 Add `tests/test_brand.py` (behaviour only, no hex pinned beyond reading them from the token file) and add to `pyproject.toml` the wheel force-includes for `assets/brand/tokens.json` and the runtime logo SVGs into `tf3companion/_brand/`. Verify with `uv build --wheel` and `unzip -l dist/*.whl | grep _brand` listing the files.

## 2. HTML reports

- [ ] 2.1 In `reports.py` replace the hard-coded `<style>` palette with CSS variables generated from `brand.theme`, dark in `:root`, light inside `@media (prefers-color-scheme: light)`; switch rules to `var(--...)`, set the token sans stack, add `font-variant-numeric: tabular-nums`, and delete `--c1..--c6`. Verify with a new test in `tests/test_reports.py` that the output has dark token values in `:root`, a light media block and no `--c1`, and that `test_html_escapes_entity_markup_and_has_no_external_dependencies` still passes.
- [ ] 2.2 Add an optional `group` field to `Chart`; set `group="mode"` for carrier-based charts; make `_render_svg` use `positive`/`negative` for signed bars, mode tokens for carrier-grouped bars, and mode tokens in table order for lines and pies. Verify with new tests: a loss-making line bar uses `var(--negative)` and a profitable one `var(--positive)`; a carrier chart uses `var(--mode-*)` and none of the semantic tokens.
- [ ] 2.3 Add the inline dark and light logo marks to the report header, toggled by the colour-scheme media query, with no title tagline. Verify with the offline test (no `src`/`href`, no script) and a test that the header contains an inline `<svg>`; then run `uv run tf3c report lines --html` and open the file in a browser in dark and light modes.
- [ ] 2.4 Update `docs/reports.md` (dark default, light via system preference, Lato fallback, offline logo) and `CHANGELOG.md`. Verify the documented command `uv run tf3c report lines --html` runs as written.

## 3. Markdown reports

- [ ] 3.1 Emit the token-derived `%%{init: ...}%%` directive before each `pie` and `xychart-beta` block in `render_markdown` (design D7). Verify with a test that the directive is first in the block, its colours exist in the token file, and the diagram body is unchanged.
- [ ] 3.2 Document the renderer caveats (GitHub, VS Code, Obsidian, slice ordering, version-dependent `xychart-beta` variables) in `docs/reports.md`. Verify with `grep -n "xychart" docs/reports.md` showing the caveat section.

## 4. XLSX export

- [ ] 4.1 Confirm with the player the spreadsheet theme proposed in design D4 (dark header row, light body) versus fully dark or fully light. Verify by recording the answer in `design.md` D4; if it differs, adjust the `surface-branding` spreadsheet requirements before 4.2.
- [ ] 4.2 In `export.py` style every table header row with the dark `canvas` fill and dark `text` font colour, keep Arial 12 and make `_apply_font` preserve font colour. Verify with a new test that opens an exported workbook with openpyxl and asserts header fill/colour equal the loader's tokens, body cells have no fill, and every font name is Arial.
- [ ] 4.3 Set chart series and data-point colours from light-theme tokens: carrier bars and pie slices from mode tokens, signed bars from `positive`/`negative`, other series from mode tokens in table order. Verify with a test reading chart XML from the exported file for the expected `srgbClr` values, then `uv run tf3c export --open` and a visual check by the player.
- [ ] 4.4 Document the spreadsheet theme in `docs/reports.md` and `CHANGELOG.md`. Verify the text names the exception and links `docs/brand/identity.md`.

## 5. MCP server, CLI and agent voice

- [ ] 5.1 Pass `website_url` and a `data:image/svg+xml;base64` logo `Icon` to `MCPServer` in `mcp_server.py` (design D10). Verify with a test that the server object exposes one icon with a `data:` source and no `<script>`, and that `uv run tf3c mcp` still starts (`uv run pytest tests/test_service_boundaries.py`).
- [ ] 5.2 Append the one-sentence analytic-voice rule to `src/tf3companion/agent_instructions.md` (design D6). Verify with `uv run pytest tests/test_agent_experience.py` and by reading the packaged instructions through the MCP server once.

## 6. README

- [ ] 6.1 Add the logo banner (PNG rendered by `scripts/make_assets.py` from `assets/brand/`) at the top of `README.md` and a link to `docs/brand/identity.md`, keeping the non-affiliation paragraph. Verify that both paths resolve with `ls`, and the existing README link checks in `uv run pytest` still pass.

## 7. Verification

- [ ] 7.1 Run `uv run pytest` and `openspec validate brand-application --strict`; both must pass. Run `uv build --wheel` and `unzip -l dist/*.whl | grep -E "_brand/(tokens.json|logo)"` to confirm the brand files ship.
- [ ] 7.2 Generate real outputs with `uv run tf3c report lines --html --open`, `uv run tf3c report company` and `uv run tf3c export --open`; the player checks the dark and light HTML, one Markdown mermaid chart in the renderer they use, and the workbook header and chart colours, then records the result in `docs/reports.md`.
