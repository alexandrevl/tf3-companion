# Tasks

## 1. Listing text and publishing doc

- [x] 1.1 Rewrite `summary` (one line, at most 120 characters) and `description` in `mod/tf3_companion_bridge/_metadata/modinfo.json` per the mod-listing spec: what the Companion does, what the mod writes, read-only and offline, Companion app required, unofficial disclaimer naming Urban Games and Paradox Interactive. Verify: `python -c "import json;d=json.load(open('mod/tf3_companion_bridge/_metadata/modinfo.json'));print(len(d['summary']),d['description'])"` shows the copy and a length of 120 or less.
- [x] 1.2 Write `docs/publishing-mod.md`: Mod Hub flow (staging area, validate, set details, logo and gallery, publish, remote id into `_metadata/mod.io_fileid.txt`), `modinfo.json` field reference, the final listing text, gallery shot list with captions (01 mod list with the bridge enabled, 02 agent answering a company question with findings, 03 a report or exported spreadsheet, 04 a loss-making line next to its finding), art brief (1920x1080, subject inside the central 1080x1080, original art, no Urban Games or Paradox marks), and the pre-upload in-game checklist. Mark thumbnail behaviour "unverified" until task 4.2. Verify: every command and path in the file exists (`grep` each against `scripts/`, `assets/`, `tf3c --help`).
- [x] 1.3 Add a "Mod listing" line to `CHANGELOG.md` under Unreleased (revision bump is added in 3.3). Verify: file renders the entry under the Unreleased heading.

## 2. Asset slots, scripts and tests

- [x] 2.1 Add Pillow to the `dev` dependency group in `pyproject.toml` only and run `uv sync`. Verify: `uv run python -c "import PIL"` exits 0 and `uv build` wheel metadata does not list Pillow as a runtime requirement.
- [x] 2.2 Create `assets/art/README.md`, `assets/gallery/README.md` listing exact filenames, size, subject and caption per slot (D5 names `01-mod-list`, `02-company-findings`, `03-report`, `04-line-problem`). Verify: `scripts/check_listing.py` (2.3) prints these same slot names in its failure output.
- [x] 2.3 Implement `scripts/check_listing.py`: validates `modinfo.json` (summary one line at most 120 characters, description contains the disclaimer, read-only statement and Companion requirement), `_metadata/0.png` (PNG, 1920x1080, RGBA), `assets/logo.png` (PNG, 512x512), and four `assets/gallery/NN-*.png` (PNG, 1920x1080); exit 1 with one line per problem. Add `tests/test_listing_check.py` that drives the check against temporary directories covering: valid set passes, missing disclaimer, long summary, wrong cover size, wrong format, missing gallery slot named in output. Verify: `uv run pytest tests/test_listing_check.py` passes; running the script on the repo before art exists exits 1 and names the missing slots.
- [x] 2.4 Implement `scripts/make_assets.py`: centre-crop `assets/art/cover.png` to square, resize to 512x512 with a fixed filter, save `assets/logo.png` without timestamp metadata, copy the cover to `mod/tf3_companion_bridge/_metadata/0.png` after validating size and mode (convert RGB to RGBA), skip the crop when `assets/art/logo-source.png` exists. Add a test that two runs on a synthetic cover produce byte-identical files and that an RGB cover becomes RGBA. Verify: `uv run pytest tests/test_listing_check.py` includes and passes the determinism and RGBA tests.

## 3. Art delivery (needs the player)

- [ ] 3.1 After `visual-identity` tasks 3.3 and 4.2 have rendered `assets/art/cover.png` and `assets/art/logo-source.png`, run `uv run python scripts/make_assets.py`. Verify: `file mod/tf3_companion_bridge/_metadata/0.png assets/logo.png` reports PNG 1920x1080 RGBA and PNG 512x512, and `open assets/logo.png` shows the brand mark, not a cover crop.
- [ ] 3.2 Confirm the cover contains no Urban Games or Paradox artwork or marks (visual check, recorded in `docs/publishing-mod.md` pre-upload checklist). Verify: the checklist row is ticked with the date.
- [ ] 3.3 Bump `mod/tf3_companion_bridge/mod.json` `revision` from 2 to 3 and add the revision line to `CHANGELOG.md`. Verify: `uv run pytest tests/test_setup.py` passes and `tf3c mod install` reports `"revision": 3`.

## 4. In-game validation (needs the player)

- [ ] 4.1 Run `tf3c mod install`, restart the game, open the mod list. Verify: `ls "<staging_area>/tf3_companion_bridge/_metadata"` shows `0.png` and `modinfo.json`, and the mod entry shows the new name, summary and description with no red error.
- [ ] 4.2 Observe whether the mod list renders the cover. Record "verified on build 40420, macOS" or "not rendered" in `docs/publishing-mod.md`. If not rendered, generate `image_00.tga` (uncompressed 32-bit) from the same cover into the mod root, repeat 4.1, and record the result; if still not rendered, state that the image is shown only through Mod Hub media. Verify: the document states the observed outcome, not an assumption.
- [ ] 4.3 Enable the mod on an existing save and confirm the bridge still works. Verify: `tf3c refresh` returns a fresh snapshot and `tf3c doctor` shows `installed_mod` ok with revision 3.
- [ ] 4.4 Run Mod Hub `validate` on the staging copy and record any limits on description length or accepted tags. Verify: the outcome is written in `docs/publishing-mod.md`; trim the description and re-run if validation reports an error.

## 5. Gallery and close-out

- [ ] 5.1 Player supplies the four gallery screenshots as `assets/gallery/01-mod-list.png` to `04-line-problem.png` (1920x1080). Verify: `uv run python scripts/check_listing.py` exits 0.
- [x] 5.2 Mark `release-readiness` tasks 5.x mod-description items and 6.2 to 6.5 as superseded by `mod-listing-assets`. Verify: `openspec validate release-readiness` and `openspec validate mod-listing-assets` both pass.
- [ ] 5.3 Full gate: `uv run pytest`, `uv run python scripts/check_listing.py` (exit 0), `openspec validate mod-listing-assets`, and the pre-upload checklist in `docs/publishing-mod.md` fully ticked on the author's build. Verify: all commands exit 0 and the checklist has no unticked row.
