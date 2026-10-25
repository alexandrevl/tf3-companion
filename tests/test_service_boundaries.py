import math

import pytest

from conftest import base_snapshot, write_snapshot
from tf3companion.service import Companion


@pytest.mark.parametrize("timeout", [-1, 0, math.nan, math.inf])
def test_invalid_refresh_timeout_does_not_publish_request(paths, timeout):
    companion = Companion(paths)
    try:
        with pytest.raises(ValueError):
            companion.refresh(timeout_s=timeout)
        assert not paths.request_file.exists()
    finally:
        companion.close()


def test_refresh_does_not_overwrite_another_running_request(paths):
    companion = Companion(paths)
    paths.snapshot_folder.mkdir()
    paths.request_file.write_text("function data() return { id = 123 } end")
    lock = paths.request_file.with_suffix(".lock")
    lock.write_text("")
    try:
        with pytest.raises(ValueError):
            companion.refresh(timeout_s=0.01)
        assert "123" in paths.request_file.read_text()
        assert lock.exists()
    finally:
        companion.close()


def test_log_tail_rejects_zero_instead_of_returning_the_entire_log(paths):
    companion = Companion(paths)
    paths.game_log.parent.mkdir(parents=True)
    paths.game_log.write_text("[tf3c] one\nother\n[tf3c] two\n[tf3c] three\n")
    try:
        with pytest.raises(ValueError):
            companion.log_tail(0)
        assert companion.log_tail(2) == ["[tf3c] two", "[tf3c] three"]
    finally:
        companion.close()


def test_queries_do_not_silently_use_stale_data_when_import_fails(paths):
    companion = Companion(paths)
    write_snapshot(paths.snapshot_folder, base_snapshot())
    try:
        assert companion.overview()["balance"] == 5_000_000
        bad = paths.snapshot_folder / "tf3c_snap_000000000011000.lua"
        bad.write_text("function data() return {")
        with pytest.raises(ValueError):
            companion.overview()
        assert companion.status()["lastIngest"]["failed"]
        assert bad.exists()
    finally:
        companion.close()


def test_export_preserves_file_and_reports_default_app_failure(paths, monkeypatch):
    from pathlib import Path

    from tf3companion import service

    def fail_open(path):
        raise OSError("No default handler")

    monkeypatch.setattr(service, "open_default", fail_open)
    companion = Companion(paths)
    write_snapshot(paths.snapshot_folder, base_snapshot())
    try:
        result = companion.export_spreadsheet(open_app=True)
        assert Path(result["file"]).is_file()
        assert result["opened"] is False
        assert "No default handler" in result["openError"]
    finally:
        companion.close()


@pytest.mark.parametrize("kind,year", [("../outside", None), ("annual", 1950), ("company", 1980)])
def test_invalid_report_does_not_create_report_files(paths, kind, year):
    companion = Companion(paths)
    write_snapshot(paths.snapshot_folder, base_snapshot())
    try:
        with pytest.raises(ValueError):
            companion.report(kind, year)
        assert not (paths.data / "reports").exists()
        assert not (paths.data / "outside.md").exists()
    finally:
        companion.close()
