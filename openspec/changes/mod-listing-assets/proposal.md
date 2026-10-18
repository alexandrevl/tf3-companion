## Why

The bridge mod has no public face. `mod/tf3_companion_bridge/_metadata/modinfo.json` has a one-line technical
`description` (it talks about snapshot files, not about what the player gets), an empty `url`, a single tag, no
unofficial/trademark disclaimer, and the mod folder ships no image at all. Anyone browsing the in-game mod list or
the mod.io page sees a nameless grey tile and no reason to install. The `visual-identity` change produces the cover and
the logo source; the player supplies the gallery screenshots. Everything else (text, slots, sizes, checks) must be ready
first so that delivering an image is a drop-in step.

This extracts the listing slice (tasks 6.x and the mod-text part of 5.x) from the unstarted `release-readiness`
change (0/41) so it can ship without CI, PyPI or fixture work.

## What Changes

- Rewrite `modinfo.json` `summary` and `description` as player-facing English copy: what the Companion does, what the
  mod does and does not do (read-only, no network), that the free Companion app is required, and the "unofficial,
  not affiliated with or endorsed by Urban Games or Paradox Interactive" disclaimer.
- Add the image slots under `assets/` with exact filenames, sizes and a `README.md` per folder saying what to drop
  there: `assets/art/cover.png` (1920x1080), `assets/gallery/01-*.png` to `04-*.png` (1920x1080, player-taken).
- Ship the cover as `mod/tf3_companion_bridge/_metadata/0.png` (1920x1080 RGBA PNG, the file stock mods
  `urbangames_tycoon` and `urbangames_sandbox` use). `tf3c mod install` already copies the whole mod tree, so no installer
  change is needed.
- Derive `assets/logo.png` (512x512) by a deterministic script `scripts/make_assets.py` instead of hand-exporting: from
  `assets/art/logo-source.png` (the brand mark rendered by `visual-identity`) when present, otherwise from a centre crop
  of the cover. The script also validates dimensions and format of every slot.
- Add `docs/publishing-mod.md`: Mod Hub upload flow, `modinfo.json` field reference, the final description text,
  the gallery shot list with captions, and the in-game checklist to run before each upload.
- Add `scripts/check_listing.py` (called out by the verification task) that fails while a required slot is empty,
  has the wrong size/format, or the description lacks the disclaimer.
- Bump `mod.json` `revision` from 2 to 3 when the metadata/image changes land, and note it in `CHANGELOG.md`.

Out of scope:

- Creating the artwork. `visual-identity` produces `cover.png` and `logo-source.png`; the player supplies the gallery
  screenshots.
- Any change to `bridge.gs.lua` / `bridge.script.lua`, to snapshot schema, or to the Python companion's behaviour.
- Portuguese or other localisations (English only; revisit if the player asks, the `modinfo.json` `localization`
  field is untested).
- Publishing: no GitHub repo, PyPI or mod.io upload happens here. The `url` field stays empty until a public repo exists.
- CI, wheel/zip release automation, anonymised fixtures and the README rewrite, which stay in `release-readiness`.
- Inventing tags: only tags the Mod Hub validates are used.

## Capabilities

### New Capabilities
- `mod-listing`: the metadata text and image assets that identify the bridge mod in the game's mod list and on
  mod.io, and the checks that keep them valid.

### Modified Capabilities
None. `installation-onboarding` is not affected: the installer already copies the full mod tree.

## Impact

- Touched: `mod/tf3_companion_bridge/_metadata/modinfo.json`, `mod/tf3_companion_bridge/mod.json` (revision 3),
  `CHANGELOG.md`, `.gitignore` only if source art must be excluded (not expected).
- New: `mod/tf3_companion_bridge/_metadata/0.png`, `assets/` (art, gallery, logo, READMEs), `scripts/make_assets.py`,
  `scripts/check_listing.py`, `docs/publishing-mod.md`, a small pytest for the listing check.
- Dev dependency: Pillow (dev group only) for image validation and logo crop; not a runtime dependency of the wheel.
- Wheel size grows by one PNG (the cover); acceptable.
- Overlaps `release-readiness` tasks 5.x/6.x. When this lands, those tasks are marked superseded in that change.
- Needs `visual-identity` applied for the cover and logo source. Needs the player: supply four screenshots, and confirm
  in the game's mod list that `0.png` renders (mod behaviour is only verifiable in game).
