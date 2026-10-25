"""MCP tool lifecycle: repeated and concurrent calls, connection release, stored-only tools, serialisation."""
from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import pytest

from conftest import base_snapshot, write_snapshot
from tf3companion import mcp_server
from tf3companion.service import Companion
from tf3companion.store import Store

INGESTING_READ_TOOLS: list[tuple[str, dict[str, Any]]] = [
    ("status", {}),
    ("company_overview", {}),
    ("list_lines", {}),
    ("line_detail", {"line": "Train A"}),
    ("list_vehicles", {}),
    ("list_industries", {}),
    ("list_towns", {}),
    ("findings", {}),
    ("opportunities", {}),
    ("company_history", {}),
    ("list_stocks", {}),
    ("list_depots", {}),
    ("list_decisions", {}),
    ("save_notes", {}),
]


@pytest.fixture
def isolated(paths, monkeypatch):
    """An isolated store with one exported snapshot; nothing here can reach a real player directory."""
    monkeypatch.setenv("TF3C_DATA_DIR", str(paths.data))
    monkeypatch.setenv("TF3C_USERDATA_DIR", str(paths.userdata))
    write_snapshot(paths.snapshot_folder, base_snapshot())
    return paths


@pytest.fixture
def parked() -> Any:
    """Finished worker threads stay alive until the test ends.

    The operating system reuses the id of an exited thread, and SQLite's thread-affinity check compares ids,
    so a call on a recycled id would wrongly look like the creating thread.
    """
    release = threading.Event()
    threads: list[threading.Thread] = []

    def run_in_new_thread(fn: Callable[[], Any]) -> tuple[Any, BaseException | None]:
        box: list[tuple[Any, BaseException | None]] = []
        done = threading.Event()

        def target() -> None:
            try:
                box.append((fn(), None))
            except BaseException as exc:  # noqa: BLE001 - the test reports whatever the tool raised
                box.append((None, exc))
            done.set()
            release.wait(timeout=120)

        thread = threading.Thread(target=target)
        threads.append(thread)
        thread.start()
        assert done.wait(timeout=60), "tool call did not finish"
        return box[0]

    yield run_in_new_thread
    release.set()
    for thread in threads:
        thread.join(timeout=60)


def tool(name: str, arguments: dict[str, Any]) -> Callable[[], Any]:
    return lambda: getattr(mcp_server, name)(**arguments)


def test_every_ingesting_tool_works_when_each_call_runs_on_a_different_thread(isolated, parked):
    for round_number in range(3):
        for name, arguments in INGESTING_READ_TOOLS:
            _, error = parked(tool(name, arguments))
            assert error is None, f"{name} failed in round {round_number}: {error!r}"


def test_twenty_repeated_calls_from_separate_threads_all_return_data(isolated, parked):
    for _ in range(20):
        overview, error = parked(tool("company_overview", {}))
        assert error is None
        assert overview["balance"] == 5_000_000
        lines, error = parked(tool("list_lines", {}))
        assert error is None
        assert [row["name"] for row in lines] == ["Train A"]


def test_concurrent_calls_see_the_same_latest_snapshot(isolated):
    results: list[Any] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(8)

    def worker(name: str) -> None:
        barrier.wait()
        try:
            results.append((name, getattr(mcp_server, name)()))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    names = ["company_overview", "list_lines", "company_history", "status"] * 2
    threads = [threading.Thread(target=worker, args=(name,)) for name in names]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not errors, errors
    assert len(results) == len(names)
    dates = {item["latest"]["date"] for name, item in results if name == "status"}
    assert len(dates) == 1


def test_connections_are_closed_after_success_and_after_failure(isolated, monkeypatch):
    opened: list[Store] = []
    original = Store.__init__

    def tracking(self, *args, **kwargs):
        original(self, *args, **kwargs)
        opened.append(self)

    monkeypatch.setattr(Store, "__init__", tracking)
    mcp_server.list_lines()
    with pytest.raises(LookupError):
        mcp_server.line_detail("No such line")
    assert opened
    for store in opened:
        with pytest.raises(Exception, match="closed"):
            store.conn.execute("SELECT 1")


def test_stored_only_tools_never_ingest_or_create_files(isolated):
    before = sorted(p.name for p in isolated.snapshot_folder.iterdir())
    assert not isolated.database.exists()
    mcp_server.list_methodologies()
    mcp_server.methodology_detail("default")
    mcp_server.validate_methodology(methodology="default")
    mcp_server.knowledge()
    assert sorted(p.name for p in isolated.snapshot_folder.iterdir()) == before
    assert not isolated.database.exists()


def test_evaluate_works_on_a_read_only_store_and_never_ingests_pending_snapshots(isolated):
    first = Companion()
    first.ingest()
    first.close()
    write_snapshot(isolated.snapshot_folder, base_snapshot(game_time=11_000))
    isolated.database.chmod(0o444)
    try:
        result = mcp_server.evaluate()
    finally:
        isolated.database.chmod(0o644)
    assert result["findings"] is not None
    again = Companion.open_stored()
    try:
        assert again.store.snapshot_count() == 1
    finally:
        again.close()


def test_overlapping_record_decision_calls_each_store_one_decision(isolated):
    names = [f"Decision {i}" for i in range(6)]
    barrier = threading.Barrier(len(names))
    errors: list[BaseException] = []

    def worker(title: str) -> None:
        barrier.wait()
        try:
            mcp_server.record_decision(title, "because")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in names]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not errors, errors
    stored = mcp_server.list_decisions(limit=50)
    assert sorted(d["title"] for d in stored) == sorted(names)


def test_overlapping_ingesting_tools_ingest_a_pending_snapshot_once(isolated):
    barrier = threading.Barrier(4)
    errors: list[BaseException] = []

    def worker() -> None:
        barrier.wait()
        try:
            mcp_server.list_lines()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not errors, errors
    check = Companion.open_stored()
    try:
        assert check.store.snapshot_count() == 1
    finally:
        check.close()


def test_empty_store_error_names_the_next_step(isolated):
    for path in isolated.snapshot_folder.glob("tf3c_snap_*.lua"):
        path.unlink()
    import anyio
    from mcp.server.mcpserver.exceptions import ToolError

    async def go():
        return await mcp_server.server.call_tool("company_overview", {})

    with pytest.raises(ToolError, match="tf3c ingest|refresh"):
        anyio.run(go)


def test_status_reports_the_running_package_version(isolated):
    from importlib.metadata import version

    import tf3companion

    reported = mcp_server.status()["version"]
    assert reported == tf3companion.__version__ == version("tf3-companion")
