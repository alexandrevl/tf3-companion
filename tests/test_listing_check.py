from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
MOD_INFO = REPO / "mod" / "tf3_companion_bridge" / "_metadata" / "modinfo.json"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_listing = _load("check_listing")
make_assets = _load("make_assets")


def _png(path: Path, size=(1920, 1080), mode="RGBA", color=(10, 120, 200, 255)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, size, color[: len(mode)]).save(path, format="PNG")


@pytest.fixture
def listing(tmp_path: Path) -> Path:
    """A complete valid listing in a temporary repository root."""
    meta = tmp_path / "mod" / "tf3_companion_bridge" / "_metadata"
    meta.mkdir(parents=True)
    shutil.copy(MOD_INFO, meta / "modinfo.json")
    _png(meta / "0.png")
    _png(tmp_path / "assets" / "logo.png", (512, 512))
    for slot in ("01", "02", "03", "04"):
        _png(tmp_path / "assets" / "gallery" / f"{slot}-shot.png", mode="RGB")
    return tmp_path


def _edit_modinfo(root: Path, **changes) -> None:
    path = root / "mod" / "tf3_companion_bridge" / "_metadata" / "modinfo.json"
    info = json.loads(path.read_text(encoding="utf-8"))
    info.update(changes)
    path.write_text(json.dumps(info), encoding="utf-8")


def test_repository_modinfo_text_is_valid():
    assert check_listing._text_problems(MOD_INFO) == []


def test_complete_listing_passes(listing):
    assert check_listing.check(listing) == []


def test_missing_disclaimer_is_named(listing):
    _edit_modinfo(listing, description="Read-only export. Requires the TF3 Companion app.")
    problems = check_listing.check(listing)
    assert any("disclaimer" in line for line in problems)


def test_long_or_multiline_summary_fails(listing):
    _edit_modinfo(listing, summary="x" * 121)
    assert any("summary" in line for line in check_listing.check(listing))
    _edit_modinfo(listing, summary="two\nlines")
    assert any("summary" in line for line in check_listing.check(listing))


def test_wrong_cover_size_reports_expected_and_actual(listing):
    _png(listing / "mod" / "tf3_companion_bridge" / "_metadata" / "0.png", (1280, 720))
    problems = check_listing.check(listing)
    assert any("1280x720" in line and "1920x1080" in line for line in problems)


def test_cover_without_alpha_and_non_png_fail(listing):
    cover = listing / "mod" / "tf3_companion_bridge" / "_metadata" / "0.png"
    _png(cover, mode="RGB")
    assert any("RGBA" in line for line in check_listing.check(listing))
    Image.new("RGBA", (1920, 1080)).save(cover, format="BMP")
    assert any("expected PNG" in line for line in check_listing.check(listing))


def test_missing_gallery_slot_is_named_with_size(listing):
    (listing / "assets" / "gallery" / "02-shot.png").unlink()
    problems = check_listing.check(listing)
    assert len(problems) == 1
    assert "slot 02" in problems[0] and "1920x1080" in problems[0]


def test_empty_repository_lists_every_missing_image(tmp_path):
    problems = check_listing.check(tmp_path)
    joined = "\n".join(problems)
    for needle in ("modinfo", "cover", "logo", "slot 01", "slot 02", "slot 03", "slot 04"):
        assert needle in joined


def _art(root: Path, size=(1920, 1080), mode="RGB") -> None:
    image = Image.new(mode, size, (255, 0, 0)[: 3 if mode == "RGB" else 4])
    # distinguishable centre so a crop can be verified
    centre = Image.new(mode, (200, 200), (0, 255, 0)[:3] if mode == "RGB" else (0, 255, 0, 255))
    image.paste(centre, ((size[0] - 200) // 2, (size[1] - 200) // 2))
    path = root / "assets" / "art" / "cover.png"
    path.parent.mkdir(parents=True)
    image.save(path, format="PNG")


def test_make_assets_converts_rgb_cover_and_crops_logo(tmp_path):
    _art(tmp_path)
    cover_out, logo_out = make_assets.build(tmp_path)
    with Image.open(cover_out) as cover, Image.open(logo_out) as logo:
        assert cover.mode == "RGBA" and cover.size == (1920, 1080)
        assert logo.size == (512, 512)
        assert logo.getpixel((256, 256))[:3] == (0, 255, 0)
        assert logo.getpixel((5, 5))[:3] == (255, 0, 0)


def test_make_assets_output_is_byte_identical_across_runs(tmp_path):
    _art(tmp_path)
    first = [p.read_bytes() for p in make_assets.build(tmp_path)]
    second = [p.read_bytes() for p in make_assets.build(tmp_path)]
    assert first == second


def test_make_assets_prefers_logo_source_and_rejects_bad_input(tmp_path):
    _art(tmp_path)
    _png(tmp_path / "assets" / "art" / "logo-source.png", (300, 300), color=(0, 0, 255, 255))
    _, logo_out = make_assets.build(tmp_path)
    with Image.open(logo_out) as logo:
        assert logo.getpixel((256, 256))[:3] == (0, 0, 255)
    _png(tmp_path / "assets" / "art" / "logo-source.png", (300, 200))
    with pytest.raises(make_assets.AssetError, match="square"):
        make_assets.build(tmp_path)


def test_make_assets_rejects_wrong_cover_size(tmp_path):
    _art(tmp_path, (1280, 720))
    with pytest.raises(make_assets.AssetError, match="1280x720"):
        make_assets.build(tmp_path)
