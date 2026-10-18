# Tasks

## 1. Tokens

- [x] 1.1 Write `assets/brand/tokens.json` with `themes.dark`, `themes.light` (every token in design D2 to D4) and `typography` (D5); verify with a throwaway script that every colour token exists in both themes as a 6-digit hex and that dark `surface-raised` is `#22282E`
- [x] 1.2 Compute WCAG contrast for every token against `canvas` and `surface` in both themes with a throwaway script; verify that text tokens reach 4.5:1 and graphic tokens 3:1, and record the measured ratios in the brand guide (2.1)

## 2. Brand guide and voice

- [x] 2.1 Write `docs/brand/identity.md`: the metro-and-circuit concept, station meanings (game, Companion chip, agent), token tables with roles and contrast, colour-role rules (semantic vs mode, mode colours on marketing art, signal reserved, error not for text), typography and fallback stack, logo usage (clear space, minimum size, variants, do/don't), the cover map and its line/station table, voice registers with examples, and the non-affiliation rule; verify every token in the guide matches `assets/brand/tokens.json`
- [x] 2.2 Link the guide from `README.md` (contributor section) and `CONTRIBUTING.md`; verify both links resolve to the file

## 3. Logo

- [x] 3.1 Draw `assets/brand/logo-mark.svg` (dark), `assets/brand/logo-mark-light.svg`, `assets/brand/logo-mono.svg` and `assets/brand/logo-lockup.svg` per design D6, with circle stations for game and agent and the square chip station for the Companion, using token colours only; verify each file parses as SVG and uses no colour outside the token file
- [x] 3.2 Draw `assets/brand/logo-mark-32.svg` (no pins, no rings, thicker stroke); verify a 32x32 render still shows the C, the square station, both round stations and the arrow
- [x] 3.3 Render the mark to `assets/art/logo-source.png` (1024x1024, dark canvas) with a headless browser or rsvg-convert; verify the file is a 1024x1024 PNG and that `scripts/make_assets.py` prefers it over cropping the cover

## 4. Cover

- [x] 4.1 Draw `assets/brand/cover.svg` (1920x1080) per design D11: four workflow lines at 0/45/90 degrees, the central MCP chip inside the central 1080x1080 square, database, game and agent termini, chip-shaped trains, two-level station labels (Lato name, mono tool name), the "TF3 Companion Bridge" lockup, tagline and disclaimer, token colours only; verify with a throwaway script that every tool name in the SVG exists in the MCP server's tool list and that no colour falls outside the token file
- [x] 4.2 Render the cover to `assets/art/cover.png` (1920x1080 PNG) and run `uv run python scripts/make_assets.py`; verify `mod/tf3_companion_bridge/_metadata/0.png` and `assets/logo.png` are written and `uv run python scripts/check_listing.py` no longer reports the cover or logo slots
- [x] 4.3 Downscale the rendered cover to 320x180 and 1280x720 and inspect both; verify that at 180p the lines, chip and termini read, and at 720p every station label is legible
- [x] 4.4 Update `docs/publishing-mod.md`: the cover is produced from `assets/brand/cover.svg`, not supplied by the player, and the pre-upload checklist includes "cover station tool names still exist"; verify the cover request section links to `docs/brand/identity.md`

## 5. Generative art prompts

- [x] 5.1 Write `docs/brand/prompts.md` with prompts for text-free illustrations (README section art, social preview background) in the metro-and-circuit style, each stating palette hex values, composition and the exclusion list from design D8; verify every prompt contains the exclusions and none asks for text

## 6. Verification

- [x] 6.1 Run `openspec validate visual-identity --strict` and the token, contrast and cover tool-name scripts from 1.1, 1.2 and 4.1; verify all pass
- [ ] 6.2 In-game check by the player: install the mod with the new `_metadata/0.png`, open the game's mod list and confirm that the cover renders, reads as part of the same world as the game's UI, and is clearly distinct from the Transport Fever logo; record the result in `docs/brand/identity.md` and `docs/publishing-mod.md`
