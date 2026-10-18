# Proposal

## Why

`visual-identity` defines the TF3 Companion brand (tokens, logo, voice) but deliberately applies it nowhere. Today the HTML report ships a generic slate/Tailwind palette (`src/tf3companion/reports.py`, `render_html`), the XLSX export uses Arial 12 with default openpyxl chart colours (`src/tf3companion/export.py`), the Markdown reports emit unstyled mermaid charts, and the README opens with plain text. Until the surfaces consume the tokens, the identity is documentation only and the product still looks unrelated to the mod listing.

**Dependency:** this change MUST be applied after `visual-identity`. It consumes `assets/brand/tokens.json`, the logo SVGs in `assets/brand/` and `docs/brand/identity.md`, which that change creates. Nothing here can start until those files exist.

## What Changes

- Add one token loader module that every Python surface uses to read `assets/brand/tokens.json` (and the logo SVGs); package those files in the wheel.
- HTML reports: replace the slate palette with CSS custom properties generated from the tokens, dark by default with light under `prefers-color-scheme: light`, mode tokens for chart series, `positive`/`negative` for signed chart values (table cells carry no money semantics today and stay uncoloured), the Lato font stack with tabular numerals, and the logo mark inline in the report header (still fully offline).
- Markdown reports: add a token-derived mermaid `%%{init: ...}%%` configuration to `pie` and `xychart-beta` blocks.
- XLSX export: brand the header rows and chart series. Spreadsheets use light token values for cells with a dark branded header row (a proposed exception to "dark by default", see design D4); typeface stays Arial.
- README: logo banner at the top and a link to the brand guide.
- MCP server: expose the logo and website metadata as server `icons`/`website_url` (the installed `mcp` 2.3.0 supports both).
- Agent instructions: verify the analytic register and make at most a minimal edit.
- Replace nothing in tests that pins wording; add behaviour tests (dark default, colours sourced from tokens, loss uses the negative token).

## Capabilities

### New Capabilities

- `surface-branding`: how each product surface (HTML reports, Markdown reports, XLSX export, README, MCP server metadata, terminal output) applies the brand tokens, logo and voice from `brand-identity`, including the single token loader and the spreadsheet theme exception.

### Modified Capabilities

None. `brand-identity` exists only in the unarchived `visual-identity` change, so no main spec can be modified. The spreadsheet exception to its "Dark theme is the default" requirement is recorded as a requirement of `surface-branding`; see design D4 for the coordination note.

## Impact

- Code: new `src/tf3companion/brand.py`; edits to `reports.py` (HTML CSS and `_render_svg`, mermaid blocks), `export.py`, `mcp_server.py`, `pyproject.toml` (wheel force-include), possibly one sentence in `src/tf3companion/agent_instructions.md`.
- Docs: `README.md` (banner and link), `docs/reports.md` (themes, mermaid caveats), `CHANGELOG.md`.
- Tests: new behaviour tests in `tests/test_reports.py`, a new export test and a token-loader test; no existing test pins colours or CSS, so none are deleted.
- Dependencies: none added.
- Related: `mod-listing-assets` owns `mod/tf3_companion_bridge/_metadata/modinfo.json` copy; this change does not touch it.

## Out of Scope

- Any change to `mod/tf3_companion_bridge/_metadata/modinfo.json`, its copy or the cover slot (owned by `mod-listing-assets`).
- Redefining tokens, the logo, the cover or the voice registers (owned by `visual-identity`).
- ANSI colour or styling in CLI output (design D5: no change).
- Bridge mod, snapshot schema, analysis behaviour or finding wording.
- Web fonts: no font file is bundled or fetched; Lato is used only if already installed, otherwise the fallback stack applies.
- Gallery screenshots, social images, a website, translations.
