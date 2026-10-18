# Source art

Rendered artwork lives here. The vector sources are in `assets/brand/`; see the [brand guide](../../docs/brand/identity.md). Nothing in this folder is shipped directly; `scripts/make_assets.py` derives the shipped files.

| File | Required | Spec |
| --- | --- | --- |
| `cover.png` | yes | PNG, exactly 1920x1080, rendered from `assets/brand/cover.svg`. Original artwork with no Urban Games or Paradox artwork or marks. The central 1080x1080 square holds the MCP chip. |
| `logo-source.png` | yes for this identity | 1024x1024 PNG, the brand mark on the dark canvas. It is resized to the logo instead of cropping the cover. |

Then run from the repository root:

```sh
uv run python scripts/make_assets.py
uv run python scripts/check_listing.py
```

`make_assets.py` writes `mod/tf3_companion_bridge/_metadata/0.png` (the cover, RGBA) and `assets/logo.png` (512x512). See [docs/publishing-mod.md](../../docs/publishing-mod.md).
