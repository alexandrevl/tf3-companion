"""End-to-end smoke of the stored-evidence analysis views through service, CLI and MCP.

Only pytest temporary directories and synthetic snapshots are used; the Steam userdata directory
deliberately does not exist, so any game discovery would fail the run.
"""
from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import anyio
import pytest

from conftest import YEAR, base_snapshot
from tf3companion import mcp_server, reports
from tf3companion.analysis_views import VIEW_NAMES, EvaluationContext, evaluate_views
from tf3companion.analysis_views.models import plain
from tf3companion.cli import main
from tf3companion.methodology.library import Library
from tf3companion.report_policy import resolve_context
from tf3companion.service import Companion
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store

FIXTURES = Path(__file__).parent / "fixtures" / "methodologies"
COAL, IRON = 3, 4
MONTHS = 37                       # three years of monthly samples: lines need a year window of history
FULL_FROM = MONTHS - 3            # the output stock is full in exactly the last three samples


def tick(i: int) -> int:
    return 10 * YEAR + round(i * YEAR / 12)


def industry(id_, name, kind, x, y, inputs=(), outputs=()):
    return {"id": id_, "name": name, "type": f"::/industries/{kind}/{kind}.con", "position": [x, y, 0],
            "inputs": [dict(i) for i in inputs], "outputs": [dict(o) for o in outputs], "closureTimeStamp": 0}


def output(cargo, produced, shipped):
    return {"cargo": cargo, "producedYear": produced, "shippedYear": shipped, "maxProductionYear": produced}


def line_and_vehicles(lid, name, profit, count, now, load=0.5):
    ids = [lid * 100 + k for k in range(count)]
    line = {"id": lid, "name": name, "vehicles": ids, "stops": [{"stationGroup": 500}, {"stationGroup": 501}],
            "profitYear": profit, "transportedYear": 1000, "rate": 100,
            "capacity": [{"cargo": 1, "used": int(100 * load), "capacity": 100}], "issues": []}
    vehicles = [{"id": v, "name": f"V{v}", "carrier": "ROAD", "state": "EN_ROUTE", "line": lid, "profitYear": 0,
                 "purchaseTime": 10 * YEAR, "models": [7], "value": 1000,       # bought at the first recorded anchor
                 "loadConfig": [{"cargo": 1, "capacity": 100}]} for v in ids]
    return line, vehicles


def catalog(label: str):
    return [{"id": 1, "name": f"{label} Small", "res": "t1", "carrier": "ROAD", "available": True,
             "capacity": [{"cargo": COAL, "capacity": 20}], "price": 1000, "runningCosts": 60, "yearFrom": 1970, "yearTo": 2000},
            {"id": 2, "name": f"{label} Big", "res": "t2", "carrier": "ROAD", "available": True,
             "capacity": [{"cargo": COAL, "capacity": 40}], "price": 3000, "runningCosts": 200, "yearFrom": 1970, "yearTo": 2000}]


def sample(i: int, *, future: bool = False) -> Snapshot:
    data = base_snapshot(game_time=tick(i) if not future else tick(MONTHS - 1) + 50)
    month = i if not future else MONTHS
    data["meta"]["date"] = {"year": 1980 + month // 12, "month": month % 12 + 1, "day": 1}
    data["cargos"] = [{"id": 0, "name": "Passengers", "res": "::/cargos/passengers/passengers.cargo"},
                      {"id": COAL, "name": "Coal", "res": "::/cargos/coal/coal.cargo"},
                      {"id": IRON, "name": "Iron", "res": "::/cargos/iron_ore/iron_ore.cargo"}]
    now = data["meta"]["gameTime"]
    specs = [(100, "Rising", 100_000 + 20_000 * i, 2), (101, "Falling", 2_000_000 - 30_000 * i, 2),
             (102, "Flat", 500_000 + (5_000 if i % 2 else -5_000), 2)]
    lines, vehicles = [], []
    for lid, name, profit, count in specs:
        line, vs = line_and_vehicles(lid, name, profit, count, now)
        lines.append(line)
        vehicles += vs
    sparse, vs = line_and_vehicles(103, "Sparse", 10_000 if i >= MONTHS - 3 else None, 1, now)
    if sparse["profitYear"] is None:
        del sparse["profitYear"]
    lines.append(sparse)
    vehicles += vs
    if future:
        extra, vs = line_and_vehicles(199, "Future Line", 1, 1, now)
        lines.append(extra)
        vehicles += vs
    data["lines"], data["vehicles"] = lines, vehicles
    data["stations"] = [{"id": 500, "name": "Alpha Central", "town": 901, "townName": "Alpha", "lines": [100, 101, 102, 103]},
                        {"id": 501, "name": "Beta Port", "town": 902, "townName": "Beta", "lines": [100, 101, 102, 103]},
                        {"id": 502, "name": "Gamma Yard", "town": 903, "townName": "Gamma", "lines": []}]
    data["towns"] = [{"id": 901, "name": "Alpha", "capacities": [500 + i, 300, 200], "lineUsage": 0.6, "position": [0, 0, 0]},
                     {"id": 902, "name": "Beta", "capacities": [400, 300, 100], "lineUsage": 0.4, "position": [30000, 0, 0]},
                     {"id": 903, "name": "Gamma", "capacities": [300, 200, 100], "lineUsage": 0.0, "position": [0, 60000, 0]}]
    data["industries"] = [
        industry(1, "Mine A", "coal_mine", 0, 0, outputs=[output(COAL, 200, 0)]),
        industry(4, "Mine B", "coal_mine", 0, 3000, outputs=[output(COAL, 150, 0)]),
        industry(5, "Mine D", "coal_mine", 0, 6000, outputs=[output(COAL, 300, 150)]),
        industry(2, "Steel Mill", "steel_mill", 8000, 0,
                 inputs=[{"cargo": COAL, "maxConsumptionYear": 250, "deliveredYear": 0, "consumedYear": 0}],
                 outputs=[output(7, 0, 0)]),
        industry(3, "Iron Mine", "iron_ore_mine", 9000, 4000, outputs=[{"cargo": IRON}]),      # flows not collected
    ]
    data["stocks"] = ([{"kind": "industry", "owner": 5, "ownerName": "Mine D", "stockId": 1, "cargos": [COAL],
                        "count": 400, "capacity": 400}] if i >= FULL_FROM else [])
    if i % 12 == 0 or i == MONTHS - 1:
        data["catalog"] = catalog(f"Stored@{i}")
    if future:
        data["catalog"] = catalog("FutureOnly")
    return Snapshot(data, source=f"smoke-{i}-{'f' if future else 'n'}.lua")


def seed(directory: Path, *, future: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    store = Store(directory / "companion.db")
    for i in range(MONTHS):
        store.add_snapshot(sample(i))
    if future:
        store.add_snapshot(sample(MONTHS - 1, future=True))
    store.close()
    return directory


def inventory(root: Path) -> dict[str, str | None]:
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None for p in sorted(root.rglob("*"))}


def tool_payload(arguments: dict[str, Any]) -> Any:
    async def go():
        return await mcp_server.server.call_tool("evaluate", arguments)
    result = anyio.run(go)
    return result.structured_content if result.structured_content is not None else json.loads(result.content[0].text)


def cli_views(capsys, *args: str) -> dict[str, Any]:
    capsys.readouterr()
    assert main(["evaluate", *args, "--json"]) == 0
    return json.loads(capsys.readouterr().out)


class Text(HTMLParser):
    """Visible text of table cells (charts are drawn from the same tables)."""

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.cell = False

    def handle_starttag(self, tag, attrs):
        self.cell = self.cell or tag in ("td", "th")

    def handle_endtag(self, tag):
        self.cell = self.cell and tag not in ("td", "th")

    def handle_data(self, data):
        if self.cell:
            self.parts.append(data)


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\d[\d,]*(?:\.\d+)?", text))


def test_stored_views_end_to_end(tmp_path, monkeypatch, capsys):
    data = seed(tmp_path / "data")
    library = Library(data)
    library.import_file(FIXTURES / "report-policy-neutral.tf3c-methodology.json")
    strict = json.loads((FIXTURES / "report-policy-priorities.tf3c-methodology.json").read_text())
    strict.update(id="smoke-strict", report_policies={"expansion": {"weight_volume": 10, "weight_distance": 40},
                                                      "lines-history": {"relative_change_ratio": 1.0, "noise_factor": 10.0}})
    strict_path = tmp_path / "strict.tf3c-methodology.json"
    strict_path.write_text(json.dumps(strict))
    library.import_file(strict_path)
    (data / "preferences.json").write_text('{"sentinel": true}')
    (data / "reports").mkdir()
    (data / "reports" / "sentinel.md").write_text("keep")
    monkeypatch.setenv("TF3C_DATA_DIR", str(data))
    monkeypatch.setenv("TF3C_USERDATA_DIR", str(tmp_path / "no-steam"))
    before = inventory(tmp_path)

    # ---- one request, three adapters, identical stored-only structured results -----------------
    names = list(VIEW_NAMES)
    service = Companion.open_stored()
    try:
        neutral = service.evaluate("report-policy-neutral", views=names)
        default_only = service.evaluate("report-policy-neutral")
        subset = service.evaluate("report-policy-neutral", views=["towns", "bottlenecks", "towns"])
        strict_result = service.evaluate("smoke-strict", views=names)
        with pytest.raises(ValueError, match="Unknown view 'bogus'"):
            service.evaluate("report-policy-neutral", views=["bogus"])
    finally:
        service.close()
    assert list(neutral["analysisViews"]) == names                 # fixed family order, exactly the requested names
    assert default_only["analysisViews"] == {} and list(subset["analysisViews"]) == ["bottlenecks", "towns"]
    assert neutral["findings"] == default_only["findings"]         # views never replace the base envelope
    cli = cli_views(capsys, "--methodology", "report-policy-neutral", *[a for n in names for a in ("--view", n)])
    mcp = tool_payload({"methodology": "report-policy-neutral", "views": names})
    assert cli["analysisViews"] == neutral["analysisViews"] == mcp["analysisViews"]
    capsys.readouterr()
    assert main(["evaluate", "--methodology", "report-policy-neutral", "--view", "bogus"]) == 1
    assert "Unknown view" in capsys.readouterr().err and cli_views(capsys)["analysisViews"] == {}
    json.dumps(neutral)                                            # serialisable: no Store, document or Snapshot inside
    assert not (tmp_path / "no-steam").exists() and not (data / "reports" / "latest.md").exists()
    assert inventory(tmp_path) == before                           # database, preferences and report sentinels untouched

    store = Store(data / "companion.db", read_only=True)
    try:
        latest = store.latest()
        context = EvaluationContext(latest, resolve_context(), store.time_context(latest), None, store.previous_of(latest))
        views = evaluate_views(store, context, tuple(names))
    finally:
        store.close()
    plain_views = views.to_dict()
    assert plain_views == {k: v for k, v in neutral["analysisViews"].items()}

    # ---- bottlenecks: three flagged of three eligible samples, never counting uncollected stocks as healthy
    stock = next(i for i in views.bottlenecks.items if i.code == "stock_output_full")
    assert (stock.observations, stock.eligible, stock.streak, stock.status) == (3, 3, 3, "persistent")
    assert views.bottlenecks.stocks.samples_with_stocks == 3

    # ---- lines-history: robust classes and insufficient evidence --------------------------------
    classes = {t.name: t.trend_class for t in views.lines_history.trajectories}
    assert classes["Rising"] == "improving" and classes["Falling"] == "deteriorating"
    assert classes["Flat"] == "stable" and classes["Sparse"] in ("insufficient data", "too new")
    rising = next(t for t in views.lines_history.trajectories if t.name == "Rising")
    assert rising.threshold == max(rising.relative_term, rising.noise_term, rising.floor_term)

    # ---- expansion: conserved shared demand and score-part arithmetic ---------------------------
    candidates = views.expansion.candidates
    steel = [c for c in candidates if c.consumer.name == "Steel Mill"]
    assert len(steel) >= 2 and {c.producer.name for c in steel} >= {"Mine A", "Mine B"}
    for earlier, later in zip(steel, steel[1:]):
        assert later.unmet_available == pytest.approx(earlier.unmet_available - earlier.volume)
    assert sum(c.volume for c in steel) <= steel[0].consumer_capacity + 1e-9
    for c in candidates:
        p = c.parts
        assert c.score == pytest.approx(p.volume + p.distance + p.urgency + p.pull + p.chain + p.proven - c.penalty_total, abs=0.051)

    # ---- industries: known and missing flows ------------------------------------------------------
    assert views.industries.status == "ok" and views.industries.industry_count == 5 and views.industries.unknown_flow_count == 1

    # ---- towns: one passenger graph gap -----------------------------------------------------------
    pairs = views.towns.pairs
    assert (pairs.linked_pairs, pairs.separate_networks) == (1, 2)
    assert {(p.town_a, p.town_b, p.status) for p in pairs.pairs} == {(901, 903, "no-passenger-link"),
                                                                     (902, 903, "no-passenger-link")}
    assert next(p for p in pairs.pairs if p.town_a == 901).distance_km == pytest.approx(60.0)
    assert views.towns.rows and {r.name for r in views.towns.rows} >= {"Alpha", "Beta", "Gamma"}

    # ---- vehicle-roi and history: stored catalog candidates, calendar-anchored maturity -------------
    assert views.vehicle_roi.catalog.sample.tick == tick(MONTHS - 1) and views.vehicle_roi.catalog.models == 2
    assert views.history.status == "ok" and views.history.usable_samples == MONTHS
    ages = {o.age for o in views.vehicle_roi.observations}
    assert {o.maturity for o in views.vehicle_roi.observations} == {"mature"}
    assert all(age == pytest.approx(3.0, abs=0.01) for age in ages)    # from the recorded anchors, not extrapolated

    # ---- policy changes judgments, never the measured facts ---------------------------------------
    n_cand, s_cand = neutral["analysisViews"]["expansion"]["candidates"], strict_result["analysisViews"]["expansion"]["candidates"]
    key = lambda c: (c["producer"]["name"], c["consumer"]["name"])
    n_by, s_by = {key(c): c for c in n_cand}, {key(c): c for c in s_cand}
    assert n_by.keys() == s_by.keys()
    for k in n_by:
        for fact in ("produced", "shipped", "unshipped", "distanceKm", "consumerCapacity"):
            assert n_by[k][fact] == s_by[k][fact]
    assert any(n_by[k]["parts"] != s_by[k]["parts"] and n_by[k]["score"] != s_by[k]["score"] for k in n_by)
    n_lines = {t["name"]: t for t in neutral["analysisViews"]["lines-history"]["trajectories"]}
    s_lines = {t["name"]: t for t in strict_result["analysisViews"]["lines-history"]["trajectories"]}
    for name in ("Rising", "Falling"):
        for fact in ("early", "recent", "mad", "delta"):
            assert n_lines[name][fact] == s_lines[name][fact]
        assert n_lines[name]["threshold"] != s_lines[name]["threshold"]
    assert (s_lines["Rising"]["trendClass"], s_lines["Falling"]["trendClass"]) == ("stable", "stable")

    # ---- Markdown and HTML show the same analytical numbers as the view -----------------------------
    store = Store(data / "companion.db", read_only=True)
    try:
        for kind in ("expansion", "lines-history", "bottlenecks"):
            document = reports.compose_report(store, kind)
            md, html = reports.render_markdown(document), reports.render_html(document)
            surface = Text()
            surface.feed(html)
            table_lines = "\n".join(line for line in md.splitlines() if line.startswith("|"))
            assert numbers(table_lines) == numbers(" ".join(surface.parts))
            top = views.expansion.candidates[0]
            if kind == "expansion":
                assert f"{top.score:.1f}" in table_lines and f"{top.score:.1f}" in " ".join(surface.parts)
    finally:
        store.close()

    # ---- historical endpoint: future entity and catalog stay out --------------------------------------
    historic = seed(tmp_path / "branch", future=True)
    branch = Store(historic / "companion.db")
    try:
        endpoint = branch.hydrate(tick(MONTHS - 1))
        assert branch.latest().game_time > endpoint.game_time                  # the retained future row exists
        before_bytes = (historic / "companion.db").read_bytes()
        at_endpoint = EvaluationContext(endpoint, resolve_context(), branch.time_context(endpoint), None,
                                        branch.previous_of(endpoint))
        selected = evaluate_views(branch, at_endpoint, tuple(names))
        assert "Future Line" not in json.dumps(selected.to_dict()) and "FutureOnly" not in json.dumps(selected.to_dict())
        assert selected.vehicle_roi.catalog.sample.tick == endpoint.game_time
        assert max(r.tick for v in (selected.lines_history, selected.history, selected.vehicle_roi)
                   for r in v.coverage.sampled) <= endpoint.game_time
        for name in names:
            assert getattr(selected, name.replace("-", "_")).coverage.endpoint.tick == endpoint.game_time
        assert (historic / "companion.db").read_bytes() == before_bytes
    finally:
        branch.close()
