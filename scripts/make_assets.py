"""Generate the mod cover, the logo and the repository social preview from the supplied source art.

assets/art/cover.png  ->  mod/tf3_companion_bridge/_metadata/0.png  (1920x1080 RGBA PNG)
assets/art/cover.png  ->  assets/logo.png                           (512x512 PNG, centre crop)
assets/art/cover.png  ->  assets/social-preview.png                 (1280x640 PNG, whole cover on the canvas colour)

If assets/art/logo-source.png exists it is resized instead of cropping the cover.
Output is deterministic: fixed resampling filter, no timestamp metadata.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, UnidentifiedImageError

COVER_SIZE = (1920, 1080)
LOGO_SIZE = (512, 512)
SOCIAL_SIZE = (1280, 640)  # GitHub's recommended repository social preview
SOCIAL_CANVAS = (23, 27, 31, 255)  # the dark `canvas` token, #171B1F (assets/brand/tokens.json)


class AssetError(Exception):
    pass


def _load(path: Path) -> Image.Image:
    if not path.is_file():
        raise AssetError(f"missing {path}")
    try:
        with Image.open(path) as image:
            image.load()
            return image.copy()
    except (UnidentifiedImageError, OSError) as exc:
        raise AssetError(f"{path} is not a readable image: {exc}") from exc


def _save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=False, compress_level=9)


def _square_crop(image: Image.Image) -> Image.Image:
    width, height = image.size
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def build(root: Path) -> list[Path]:
    root = Path(root)
    cover = _load(root / "assets" / "art" / "cover.png")
    if cover.size != COVER_SIZE:
        raise AssetError(f"cover is {cover.size[0]}x{cover.size[1]}, expected {COVER_SIZE[0]}x{COVER_SIZE[1]}")
    cover = cover.convert("RGBA")
    logo_source = root / "assets" / "art" / "logo-source.png"
    logo = _load(logo_source).convert("RGBA") if logo_source.is_file() else _square_crop(cover)
    if logo.size[0] != logo.size[1]:
        raise AssetError(f"logo source is {logo.size[0]}x{logo.size[1]}, expected a square image")
    logo = logo.resize(LOGO_SIZE, Image.Resampling.LANCZOS)

    cover_out = root / "mod" / "tf3_companion_bridge" / "_metadata" / "0.png"
    logo_out = root / "assets" / "logo.png"
    _save_png(cover, cover_out)
    _save_png(logo, logo_out)
    return [cover_out, logo_out]


def build_social_preview(root: Path) -> Path:
    """Fit the whole cover into the 2:1 repository social preview (1280x640) on the dark canvas colour.

    The cover is 16:9, so it is scaled to the preview's height and centred; nothing is cropped, which keeps the
    non-affiliation sentence in the cover's corner visible.
    """
    root = Path(root)
    cover = _load(root / "assets" / "art" / "cover.png").convert("RGBA")
    if cover.size != COVER_SIZE:
        raise AssetError(f"cover is {cover.size[0]}x{cover.size[1]}, expected {COVER_SIZE[0]}x{COVER_SIZE[1]}")
    height = SOCIAL_SIZE[1]
    width = round(COVER_SIZE[0] * height / COVER_SIZE[1])
    canvas = Image.new("RGBA", SOCIAL_SIZE, SOCIAL_CANVAS)
    canvas.alpha_composite(cover.resize((width, height), Image.Resampling.LANCZOS), ((SOCIAL_SIZE[0] - width) // 2, 0))
    out = root / "assets" / "social-preview.png"
    _save_png(canvas.convert("RGB"), out)
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else Path(__file__).resolve().parent.parent
    try:
        written = build(root) + [build_social_preview(root)]
    except AssetError as exc:
        print(f"make_assets: {exc}")
        return 1
    for path in written:
        print(f"wrote {path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
