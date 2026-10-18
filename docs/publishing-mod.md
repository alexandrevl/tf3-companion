# Publishing the bridge mod

This page covers the mod's public listing: the text, the cover, the gallery and the checks before each upload. It is maintainer documentation. Players install the mod with `tf3c mod install` (see [install-mod.md](install-mod.md)).

Nothing here uploads anything. The upload is a manual action in the game's Mod Hub.

## What is verified

| Behaviour | Status |
| --- | --- |
| Stock mods `urbangames_tycoon` and `urbangames_sandbox` ship `_metadata/0.png` as a 1920x1080 RGBA PNG | Observed on disk, game build 40420, macOS |
| The mod list renders `_metadata/0.png` for a user mod | **Unverified** until [In-game checks](#in-game-checks) is done |
| `image_00.tga` is used for mod list thumbnails | **Unverified**. The string exists in the game binary; no installed mod uses it |
| Mod Hub accepts the description length and tags below | **Unverified** until Mod Hub `validate` is run |

Update this table with the observed result and the build whenever a row is checked.

## Files

```text
mod/tf3_companion_bridge/
  mod.json                      revision, bump on every listing or code change
  _metadata/
    modinfo.json                name, summary, description, authors, tags, url
    0.png                       cover, 1920x1080 RGBA PNG (generated from assets/art/cover.png)
assets/
  brand/cover.svg               vector cover source (metro map of the MCP tools)
  brand/logo-mark.svg           vector brand mark
  art/cover.png                 rendered from brand/cover.svg
  art/logo-source.png           square brand mark render; takes precedence over a cover crop
  logo.png                      512x512 mod.io logo, generated
  gallery/NN-*.png              four 1920x1080 in-game screenshots, uploaded by hand
scripts/
  make_assets.py                cover -> _metadata/0.png and logo.png
  check_listing.py              validates text and images; exits 1 with one line per problem
```

`tf3c mod install` copies the whole mod folder, so `_metadata/0.png` is installed automatically. Gallery images and `assets/` are not part of the mod or the wheel.

## `modinfo.json` fields

| Field | Meaning |
| --- | --- |
| `name` | Title in the mod list. |
| `summary` | One line, at most 120 characters (our own bound; the Hub limit is unknown). |
| `description` | Long text. Must say the mod is read-only and offline, that the Companion app is required, and carry the unofficial disclaimer. |
| `authors` | Name and role (`CREATOR`). |
| `tags` | Only values the Mod Hub accepts. Currently `Script Mod`. |
| `url` | Project page. Empty until a public repository exists. |

Copy of the listing text lives in `modinfo.json`; that file is the source of truth. Text is English only.

## Cover and logo brief

- `assets/brand/cover.svg` is the cover source: a metro-and-circuit map with a central MCP chip, database and agent termini, and stations named after real tools. See the [brand guide](brand/identity.md).
- Render it to `assets/art/cover.png` at 1920x1080; keep the chip inside the central 1080x1080 square.
- Render `assets/brand/logo-mark.svg` on the dark canvas to `assets/art/logo-source.png` at 1024x1024. The listing logo is resized from this mark, not cropped from the cover.
- Use Lato Regular and Bold from the upstream OFL release when rendering the cover and wordmark. No fonts or external resources are embedded in the SVGs.
- RGB covers are converted to RGBA when `_metadata/0.png` is written.

Then run:

```sh
uv run python scripts/make_assets.py
uv run python scripts/check_listing.py
```

## Gallery shot list

Take these in the game at 1920x1080 and save them as `assets/gallery/NN-<name>.png`.

| Slot | File | Subject | Caption |
| --- | --- | --- | --- |
| 1 | `01-mod-list.png` | The game's mod list with TF3 Companion Bridge enabled | The bridge is a cosmetic, read-only script mod. |
| 2 | `02-company-findings.png` | An AI assistant answering a company question with findings and numbers | Findings with the numbers behind them. |
| 3 | `03-report.png` | A report or the exported spreadsheet | Reports built from your own snapshots. |
| 4 | `04-line-problem.png` | A loss-making line in the game beside its finding | Spot the line that loses money, then fix it yourself. |

## Mod Hub upload

The flow below uses the game's Mod Hub (API names `ModPublishHelper.validate`, `publish`, `addLogoImage`, `addGalleryImages`, `setModDetails`, `setRemoteModId` in the game's `api/tealdef/api/type/modhub.d.tl`).

1. Run `tf3c mod install` so the staging copy has the current revision.
2. Open the Mod Hub in the game and select `tf3_companion_bridge`.
3. Run validate. Record any reported limits in the table above.
4. Set the details from `modinfo.json`.
5. Add `assets/logo.png` as the logo and the four gallery images in slot order.
6. Publish. Copy the remote mod id into `_metadata/mod.io_fileid.txt`, commit it and bump `revision` for the next update.

## Updating

Change the files, raise `revision` in `mod.json`, update `CHANGELOG.md`, run the checklist, upload again from the Mod Hub. Players who already installed the mod see a `doctor` warning naming both revisions and run `tf3c mod install`.

## In-game checks

Run once per revision, on the build you list in the table.

1. `tf3c mod install`, restart the game, open the mod list. The entry shows the new name, summary and description with no red error.
2. Note whether the cover appears. If it does not, generate an uncompressed 32-bit `image_00.tga` from the same cover into the mod root, repeat, and note the result.
3. Enable the mod on an existing save, reload it and save.
4. `tf3c refresh` returns a fresh snapshot and `tf3c doctor` shows `installed_mod` ok with the new revision.
5. Mod Hub validate passes.

## Pre-upload checklist

- [ ] `uv run python scripts/check_listing.py` exits 0
- [ ] `uv run pytest` passes
- [ ] Cover reviewed by eye: original art, no Urban Games or Paradox artwork or marks
- [ ] Cover station tool names still exist: compare the monospace labels in `assets/brand/cover.svg` with the MCP tool list using the command in [the brand guide](brand/identity.md#the-cover-map)
- [ ] In-game checks above done and the verified table updated
- [ ] `revision` raised and `CHANGELOG.md` updated
- [ ] Mod Hub terms and mod.io terms re-read for the current version
