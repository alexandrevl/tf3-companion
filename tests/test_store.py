import os
import threading
import time

import pytest

from conftest import YEAR, base_snapshot, write_snapshot
from tf3companion import luadata
from tf3companion.paths import load_paths
from tf3companion.service import Companion, NoSnapshotError
from tf3companion.store import Store


def test_ingest_is_idempotent_and_prunes_old_files(paths):
    folder = paths.snapshot_folder
    for year in range(1, 5):
        write_snapshot(folder, base_snapshot(game_time=year * YEAR))
    (folder / "tf3c_snap_000000000999999.lua").write_text("function data() return { broken", encoding="utf-8")
    store = Store(paths.database)
    first = store.ingest_folders([folder], keep_files=2)
    assert len(first.ingested) == 4
    assert list(first.failed) == ["tf3c_snap_000000000999999.lua"]
    assert len(first.pruned) == 2
    assert sorted(p.name for p in folder.iterdir()) == [
        "tf3c_snap_000000000003000.lua",
        "tf3c_snap_000000000004000.lua",
        "tf3c_snap_000000000999999.lua",
    ]
    second = store.ingest_folders([folder], keep_files=2)
    assert second.ingested == [] and len(second.skipped) == 2
    assert store.snapshot_count() == 4
    store.close()


def test_ingest_reimports_rewritten_files_and_ignores_other_exports(paths):
    write_snapshot(paths.snapshot_folder, base_snapshot(game_time=5 * YEAR))
    (paths.snapshot_folder / "my_export.lua").write_text("function data() return {} end", encoding="utf-8")
    (paths.snapshot_folder / "tf3_bridge_snap_000000000006000.lua").write_text(
        "function data() return {} end", encoding="utf-8"
    )
    store = Store(paths.database)
    assert store.ingest_folders([paths.snapshot_folder]).ingested == ["tf3c_snap_000000000005000.lua"]
    data = base_snapshot(game_time=5 * YEAR)
    data["company"]["balance"] = 1
    path = write_snapshot(paths.snapshot_folder, data)
    os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 5))
    assert store.ingest_folders([paths.snapshot_folder]).ingested == [path.name]
    assert store.latest().company["balance"] == 1
    assert store.snapshot_count() == 1
    store.close()


def test_previous_snapshot_and_histories(paths):
    store = Store(paths.database)
    for year, balance in [(1, 100), (2, 200), (3, 150)]:
        data = base_snapshot(game_time=year * YEAR)
        data["company"]["balance"] = balance
        data["lines"][0]["profitYear"] = balance * 10
        write_snapshot(paths.snapshot_folder, data)
    store.ingest_folders([paths.snapshot_folder])
    latest = store.latest()
    assert latest.game_time == 3 * YEAR
    assert store.previous_of(latest).game_time == 2 * YEAR
    assert [r["balance"] for r in store.company_history()] == [100, 200, 150]
    assert [r["profit_year"] for r in store.line_history(100)] == [1000, 2000, 1500]
    store.close()


def test_decision_journal_lifecycle(paths):
    store = Store(paths.database)
    decision = store.add_decision("Double trains on line A", "Crowded in three snapshots", ["line:100"])
    assert decision["status"] == "planned" and decision["entities"] == ["line:100"]
    done = store.update_decision(decision["id"], "done", "Load fell to 70%")
    assert done["status"] == "done" and done["outcome"] == "Load fell to 70%"
    assert [item["id"] for item in store.list_decisions("done")] == [decision["id"]]
    with pytest.raises(ValueError):
        store.update_decision(decision["id"], "maybe")
    with pytest.raises(KeyError):
        store.update_decision(999, "done")
    store.close()


def test_service_requires_a_snapshot(paths):
    companion = Companion(paths)
    with pytest.raises(NoSnapshotError):
        companion.overview()
    companion.close()


def test_refresh_writes_request_and_waits_for_matching_snapshot(paths):
    companion = Companion(paths)

    def fake_game():
        deadline = time.monotonic() + 5
        while not paths.request_file.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        request = luadata.loads(paths.request_file.read_text(encoding="utf-8"))
        data = base_snapshot(game_time=7 * YEAR)
        data["meta"]["reason"] = "request"
        data["meta"]["requestId"] = request["id"]
        write_snapshot(paths.snapshot_folder, data)

    game = threading.Thread(target=fake_game)
    game.start()
    result = companion.refresh(timeout_s=5, poll_s=0.05)
    game.join()
    assert result["ok"] is True
    assert result["file"] == "tf3c_snap_000000000007000.lua"
    assert companion.overview()["balance"] == 5_000_000
    companion.close()


def test_refresh_times_out_without_game(paths):
    companion = Companion(paths)
    result = companion.refresh(timeout_s=0.2, poll_s=0.05)
    assert result["ok"] is False and paths.request_file.exists()
    companion.close()


def test_line_lookup_by_name_or_id(paths):
    write_snapshot(paths.snapshot_folder, base_snapshot())
    companion = Companion(paths)
    assert companion.line_detail("train a")["id"] == 100
    assert companion.line_detail("100")["name"] == "Train A"
    with pytest.raises(LookupError):
        companion.line_detail("bus")
    companion.close()


def test_environment_overrides_create_database_outside_package(tmp_path, monkeypatch):
    userdata = tmp_path / "game"
    userdata.mkdir()
    data = tmp_path / "companion"
    monkeypatch.setenv("TF3C_USERDATA_DIR", str(userdata))
    monkeypatch.setenv("TF3C_DATA_DIR", str(data))
    paths = load_paths()
    companion = Companion(paths)
    assert paths.userdata == userdata
    assert paths.database == data / "companion.db"
    assert paths.database.is_file()
    assert paths.request_file == userdata / "towns_industries" / "tf3c_request.lua"
    companion.close()


def test_newer_schema_fails_without_blocking_supported_snapshot(paths):
    newer = base_snapshot(game_time=11 * YEAR)
    from tf3companion.snapshot import READABLE_SCHEMA

    newer["meta"]["schemaVersion"] = READABLE_SCHEMA + 1
    failed = write_snapshot(paths.snapshot_folder, newer)
    write_snapshot(paths.snapshot_folder, base_snapshot())
    companion = Companion(paths)
    result = companion.ingest()
    assert "update TF3 Companion" in result["failed"][failed.name]
    assert len(result["ingested"]) == 1
    assert failed.exists()
    companion.close()


def test_notes_append_uses_latest_snapshot_date_and_preserves_history(paths):
    companion = Companion(paths)
    assert companion.save_notes() == ""
    companion.save_notes("Initial goal")
    data = base_snapshot()
    data["meta"]["date"] = {"year": 1983, "month": 7, "day": 17}
    write_snapshot(paths.snapshot_folder, data)
    notes = companion.save_notes("Trunk lines end at the steel mill")
    assert "## 1983-07-17\n\nTrunk lines end at the steel mill" in notes
    assert "Initial goal" in notes
    assert companion.save_notes() == notes
    companion.close()


def test_knowledge_rejects_private_notes_path_outside_repository(paths, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    companion = Companion(paths)
    with pytest.raises(LookupError):
        companion.knowledge("../notes")
    companion.close()


def test_ingest_retains_changing_and_failed_files(paths):
    folder = paths.snapshot_folder
    first = write_snapshot(folder, base_snapshot(game_time=1 * YEAR))
    broken = folder / "tf3c_snap_000000000002000.lua"
    broken.write_text("return { broken", encoding="utf-8")
    store = Store(paths.database)
    res = store.ingest_folders([folder], keep_files=1)
    assert res.ingested == [first.name]
    assert broken.name in res.failed
    assert broken.exists()
    assert first.exists()
    store.close()


def test_ingest_disambiguates_duplicate_filenames_across_folders(paths, tmp_path):
    f1 = paths.snapshot_folder
    f2 = tmp_path / "second"
    f2.mkdir()
    p1 = write_snapshot(f1, base_snapshot(game_time=1 * YEAR))
    p2 = write_snapshot(f2, base_snapshot(game_time=1 * YEAR))
    store = Store(paths.database)
    res = store.ingest_folders([f1, f2], keep_files=1)
    assert str(p1) in res.ingested or str(p2) in res.ingested
    assert len(res.skipped) + len(res.ingested) == 2
    store.close()


def test_single_store_rejects_foreign_or_conflicting_save_id(paths):
    s1 = base_snapshot(game_time=1 * YEAR)
    s1["meta"]["saveId"] = "save-alpha"
    write_snapshot(paths.snapshot_folder, s1)
    store = Store(paths.database)
    res1 = store.ingest_folders([paths.snapshot_folder])
    assert len(res1.ingested) == 1

    s2 = base_snapshot(game_time=2 * YEAR)
    s2["meta"]["saveId"] = "save-beta"
    p2 = write_snapshot(paths.snapshot_folder, s2)
    res2 = store.ingest_folders([paths.snapshot_folder])
    assert p2.name in res2.failed
    assert "single-store save identity mismatch" in res2.failed[p2.name]
    store.close()


def test_store_reporting_queries_and_bounds_validation(paths):
    store = Store(paths.database)
    for yr in (1980, 1981):
        data = base_snapshot(game_time=yr * YEAR)
        data["meta"]["date"] = {"year": yr, "month": 6, "day": 1}
        data["catalog"] = [{"id": yr, "name": f"Vehicle {yr}"}]
        write_snapshot(paths.snapshot_folder, data)
    store.ingest_folders([paths.snapshot_folder])

    assert store.available_years() == [1980, 1981]
    assert len(store.snapshots_for_year(1980)) == 1
    assert len(store.snapshots()) == 2
    assert [s.game_time for s in store.recent_snapshots(limit=2)] == [1980 * YEAR, 1981 * YEAR]
    assert store.latest_before(1981 * YEAR).game_time == 1980 * YEAR
    assert store.snapshot_at_or_before(1981 * YEAR).game_time == 1981 * YEAR
    assert store.latest_with_catalog(game_time=1980 * YEAR).game_time == 1980 * YEAR

    with pytest.raises(ValueError):
        store.recent_snapshots(limit=-1)
    with pytest.raises(ValueError):
        store.recent_snapshots(limit=True)
    with pytest.raises(ValueError):
        store.snapshots_for_year(-5)
    store.close()
