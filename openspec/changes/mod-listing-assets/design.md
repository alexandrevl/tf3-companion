# Design

## Context

See proposal.md for motivation. Observed state:

- `_metadata/modinfo.json` has `name`, a one-line `summary`, a technical `description`, one author, tag `Script Mod`, empty `url`. The mod root ships `mod.json` (revision 2), `_content.json` (two Lua files) and `content/`.
- `tf3c mod install` copies the entire bundled mod tree (`shutil.copytree`), and `pyproject.toml` force-includes `mod/tf3_companion_bridge` in the wheel, so any file added to the mod folder ships and installs without code changes.
- Stock mods in the game's `mods/release/`: `urbangames_tycoon` and `urbangames_sandbox` ship `_metadata/0.png` (1920x1080 RGBA PNG) beside `modinfo.json`. Campaign mods ship no image. No installed mod uses `image_00.tga`, although the string exists in the game binary (see `release-readiness` design). Which file the mod list actually renders for a user mod is therefore not settled by inspection.
- `release-readiness` (0/41 tasks) plans the same assets in D8 and tasks 6.1 to 6.5, bundled with CI and PyPI work.

## Goals / Non-Goals

**Goals:**
- Final listing text and every image slot exist with fixed names and sizes, so delivering art is "copy file, run check".
- One cover image feeds every derived asset.
- A failing check, not reviewer memory, enforces slots and disclaimer.

**Non-Goals:**
- Designing the artwork or generating images; `visual-identity` owns the cover and the logo source.
- Automating Mod Hub or mod.io upload.
- Resolving the TGA question beyond a cheap in-game test.

## Decisions

**D1. Ship `_metadata/0.png`, not `image_00.tga`, as the primary cover.** It is the only convention with on-disk evidence (two stock mods, exact size and mode). Alternative: `image_00.tga` at mod root, which appears only as a binary string; adopt only if the in-game test shows the PNG is ignored, as an additional file generated from the same cover.

**D2. Cover size 1920x1080 RGBA PNG.** Matches the stock files and 16:9 hub media. Alternative: smaller thumbnail sizes, rejected because the Mod Hub produces `GalleryThumb180p`/`720p` itself.

**D3. Derived assets by script, validated by script.** `scripts/make_assets.py` crops the cover centre to a square and resizes to 512x512 with a fixed resampling filter and fixed PNG save options (no timestamp metadata), giving reproducible bytes. `scripts/check_listing.py` imports nothing from the companion package; it reads files and `modinfo.json` and exits non-zero with one line per problem. Pillow is added to the dev dependency group only, so the wheel stays dependency-light. Alternative: hand-export the logo (unreproducible), or Pillow at runtime (needless dependency).

**D4. Logo source first, square crop as fallback.** A centre crop of a 16:9 cover loses the sides, and the brand cover holds a chip with labelled stations, not the logo, at its centre. The logo is therefore derived from `assets/art/logo-source.png`, the brand mark rendered by `visual-identity`; the script crops the cover only when that file is absent. Alternative: compose the cover around a central logo, rejected by `visual-identity` design D11.

**D5. Gallery lives outside the mod.** `assets/gallery/01..04-*.png` are uploaded manually through the Mod Hub and never enter the wheel or the mod zip; only `_metadata/0.png` is inside the mod. Slot names carry intent: `01-mod-list`, `02-company-findings`, `03-report`, `04-line-problem`. The check globs `NN-*.png` so the player can choose the suffix.

**D6. Placeholders fail loudly.** Until the cover, logo source and gallery exist, the check fails and prints the slot table. A committed fake image would pass silently and ship. The implementation sequence therefore delivers text and docs first, and the cover and gallery land in later commits; `mod.json` revision is bumped in the commit that adds the cover.

**D7. Description copy is data in the repo, checked by substring.** The check asserts the disclaimer phrase and the "read-only" and "Companion" statements are present in `modinfo.json`. It does not pin full wording (copy may evolve). Text is English only; the `localization` field is untested and unused.

**D8. Supersession, not duplication.** On landing, `release-readiness` tasks 6.2 to 6.5 and the mod-description part of 5.x are marked superseded by this change, so the two do not produce divergent files.

## Risks / Trade-offs

- [The mod list ignores `_metadata/0.png` for user mods] → in-game test with the real cover on build 40420 before upload; fall back to D1's alternative and record the result in `docs/publishing-mod.md` as verified or unverified.
- [Description over a Mod Hub length limit] → the Hub API limits are not known; run Mod Hub `validate` on the staging copy and trim if it reports an error; the 120-character summary cap is our own conservative bound.
- [Tags rejected by the Hub] → keep only `Script Mod` unless the Hub's accepted list (seen in the game UI) offers more.
- [Cover contains protected marks] → the doc asks for original art; the check cannot detect this, so the pre-upload checklist includes a manual look.
- [Wheel grows by a ~1 to 3 MB PNG] → accepted; compress with lossless optimisation in the script if above 3 MB.
- [Revision bump makes `doctor` call installed copies outdated] → intended; the player re-runs `tf3c mod install`.

## Migration Plan

1. Land text, `docs/publishing-mod.md`, slot READMEs and scripts (check fails on missing images by design).
2. Apply `visual-identity`, which renders `assets/art/cover.png` and `assets/art/logo-source.png`; run `make_assets.py` to write `_metadata/0.png` and `logo.png`; bump revision to 3.
3. Player runs the in-game check, then supplies gallery shots; the check goes green.
4. Rollback: revert the commit; revision 2 stays valid because no Lua changes.

## Open Questions

- Mod Hub accepted tags and field length limits (answerable only through the game's Hub UI).
- Whether to add `image_00.tga` (depends on the in-game result).
