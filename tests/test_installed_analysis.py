"""Installed-distribution acceptance: supported analysis runs from a built wheel, outside the checkout.

The wheel is built into temporary storage and installed offline into a clean temporary environment from
already available dependency archives (uv's local cache); nothing here reaches a package index. The installed
child processes run from a temporary directory with a sanitised environment and temporary data, userdata and
home roots, and receive only serialized synthetic evidence (Lua snapshot files) and validated methodology JSON.
No real game, mod, network or player directory is touched.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from conftest import YEAR
from methodology_helpers import FREIGHT, Net
from tf3companion import luadata

pytestmark = pytest.mark.slow

REPO = Path(__file__).resolve().parent.parent
EXAMPLE_ID = "local-feeder-intercity-trunk"
MONTHS = 37
COAL, IRON = 3, 4
# Evidence the synthetic collector never provides, which a view must disclose rather than treat as zero.
MISSING_EVIDENCE = {"towns": ["cargo-supply-missing", "pollution-noise-missing"]}
VIEWS = ["bottlenecks", "expansion", "lines-history", "history", "industries", "vehicle-roi", "towns"]

# ---- synthetic evidence (parent side only; the child sees serialized Lua snapshot files) --------------------


def tick(i: int) -> int:
    return 10 * YEAR + round(i * YEAR / 12)


def industry(id_: int, name: str, kind: str, x: int, y: int, inputs=(), outputs=()) -> dict[str, Any]:
    return {"id": id_, "name": name, "type": f"::/industries/{kind}/{kind}.con", "position": [x, y, 0],
            "inputs": [dict(i) for i in inputs], "outputs": [dict(o) for o in outputs], "closureTimeStamp": 0}


def flow(cargo: int, produced: int, shipped: int) -> dict[str, int]:
    return {"cargo": cargo, "producedYear": produced, "shippedYear": shipped, "maxProductionYear": produced}


def catalog(label: str) -> list[dict[str, Any]]:
    return [{"id": 1, "name": f"{label} Small", "res": "t1", "carrier": "ROAD", "available": True,
             "capacity": [{"cargo": COAL, "capacity": 20}], "price": 1000, "runningCosts": 60, "yearFrom": 1970, "yearTo": 2000},
            {"id": 2, "name": f"{label} Big", "res": "t2", "carrier": "ROAD", "available": True,
             "capacity": [{"cargo": COAL, "capacity": 40}], "price": 3000, "runningCosts": 200, "yearFrom": 1970, "yearTo": 2000}]


def sample(i: int) -> dict[str, Any]:
    """Month `i` of a small company whose line, town and station names follow no personal convention."""
    net = Net(game_time=tick(i))
    net.data["meta"]["date"] = {"year": 1980 + i // 12, "month": i % 12 + 1, "day": 1}
    net.data["cargos"] = [{"id": 0, "name": "Passengers", "res": "::/cargos/passengers/passengers.cargo"},
                          {"id": COAL, "name": "Coal", "res": "::/cargos/coal/coal.cargo"},
                          {"id": IRON, "name": "Iron", "res": "::/cargos/iron_ore/iron_ore.cargo"}]
    for number, name, town, town_name in [(501, "Cedar Halt", 901, "Oakridge"), (502, "Fern Cross", 902, "Brightwater"),
                                          (503, "Kestrel Field", 903, "Kestrel"), (504, "Marlow Field", 904, "Marlow"),
                                          (505, "Dunmore Field", 905, "Dunmore"), (506, "Haze Field", 906, "Hazelton")]:
        net.station(number, name, town, town_name)
    for position, town in zip([(0, 0, 0), (30_000, 0, 0), (0, 60_000, 0), (5_000, 5_000, 0), (6_000, 5_000, 0), (7_000, 5_000, 0)],
                              net.data["towns"]):
        town["position"] = list(position)
    # Known facts at every month: a heavy passenger loss, a healthy one, a freight loss and a rising line.
    net.line(100, "Maple Express", [501, 502], profit=-150_000, load=(95, 100), vehicles=2)
    net.line(101, "Quartz", [501, 502], profit=40_000, load=(50, 100), vehicles=1)
    net.line(102, "Heron", [501, 502], profit=-20_000, cargo=FREIGHT, load=(10, 100), age=3.0, vehicles=1)
    net.line(103, "Lantern", [501, 502], profit=100_000 + 20_000 * i, load=(60, 100), vehicles=1)
    # Aircraft per terminal: 3.5, 3.0 and 2.5 used terminals; Gull's stops carry no terminal at all.
    net.line(130, "Falcon", [503, 503], carrier="AIR", vehicles=7, terminals=[0, 1])
    net.line(131, "Swift", [504, 504], carrier="AIR", vehicles=6, terminals=[0, 1])
    net.line(132, "Wren", [505, 505], carrier="AIR", vehicles=5, terminals=[0, 1])
    net.line(133, "Gull", [506, 506], carrier="AIR", vehicles=4)
    for line in net.data["lines"]:
        line.setdefault("capacity", [])
    for vehicle in net.data["vehicles"]:
        vehicle["loadConfig"] = [{"cargo": 1, "capacity": 100}]
        vehicle["purchaseTime"] = 10 * YEAR          # bought at the first recorded anchor: a stable identity over time
        if vehicle["line"] == 100:
            vehicle["maintenanceState"] = 0.60
    data = net.data
    data["industries"] = [
        industry(1, "Greywater Pit", "coal_mine", 0, 0, outputs=[flow(COAL, 200, 0)]),
        industry(4, "Stonebridge Pit", "coal_mine", 0, 3000, outputs=[flow(COAL, 150, 0)]),
        industry(5, "Redfall Pit", "coal_mine", 0, 6000, outputs=[flow(COAL, 300, 150)]),
        industry(2, "Ironworks", "steel_mill", 8000, 0,
                 inputs=[{"cargo": COAL, "maxConsumptionYear": 250, "deliveredYear": 0, "consumedYear": 0}],
                 outputs=[flow(7, 0, 0)]),
        industry(3, "Ore Hollow", "iron_ore_mine", 9000, 4000, outputs=[{"cargo": IRON}]),      # flows not collected
    ]
    data["stocks"] = ([{"kind": "industry", "owner": 5, "ownerName": "Redfall Pit", "stockId": 1, "cargos": [COAL],
                        "count": 400, "capacity": 400}] if i >= MONTHS - 3 else [])
    if i % 12 == 0 or i == MONTHS - 1:
        data["catalog"] = catalog(f"Stored@{i}")
    return data


def write_acquisition(folder: Path) -> list[Path]:
    """Serialize the synthetic months as Lua snapshot files, as the bridge would."""
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for i in range(MONTHS):
        data = sample(i)
        path = folder / f"tf3c_snap_{data['meta']['gameTime']:015d}.lua"
        path.write_text(luadata.dumps(data), encoding="utf-8")
        written.append(path)
    return written


# ---- name-free policies: classified by facts only, tolerances differ --------------------------------------------


def factual_policy(policy_id: str, loss_alert: int, maintenance_limit: float) -> dict[str, Any]:
    return {
        "schema": "tf3c-methodology/1", "id": policy_id, "version": "1.0.0", "name": policy_id,
        "description": "Factual-field policy: no name patterns, no personal conventions.",
        "parameters": {
            "loss_alert": {"value": loss_alert, "description": "Passenger loss per year above which a line is a problem."},
            "maintenance_limit": {"value": maintenance_limit, "description": "Maintenance state below which a vehicle is a problem."},
        },
        "markers": {"ok": {"symbol": "+", "label": "ok"},
                    "watch": {"symbol": "~", "label": "watch", "finding": "low"},
                    "problem": {"symbol": "!", "label": "problem", "finding": "high"}},
        "roles": {"line": [{"id": "passenger-line", "select": {"field": "line.is_passenger_only", "op": "eq", "value": True}},
                           {"id": "cargo-line", "select": {"field": "line.is_passenger_only", "op": "eq", "value": False}}]},
        "rules": [
            {"id": "passenger-loss", "label": "Passenger loss", "entity": "line", "role": "passenger-line",
             "outcomes": [
                 {"when": {"field": "line.loss_year", "op": "gt", "value": {"param": "loss_alert"}}, "marker": "problem",
                  "message": "{line.name} loses {line.loss_year|money} a year, above {param.loss_alert|money}."},
                 {"when": {"field": "line.profit_year", "op": "lt", "value": 0}, "marker": "watch",
                  "message": "{line.name} loses {line.loss_year|money} a year, within tolerance."}],
             "default": {"marker": "ok"}},
            {"id": "vehicle-maintenance", "label": "Vehicle maintenance", "entity": "vehicle",
             "outcomes": [{"when": {"field": "vehicle.maintenance_state", "op": "lt", "value": {"param": "maintenance_limit"}},
                           "marker": "problem", "message": "{vehicle.name} maintenance {vehicle.maintenance_state|pct}."}],
             "default": {"marker": "ok"}},
        ],
        "reports": {"kinds": ["company", "lines"]},
    }


STRICT = factual_policy("installed-strict", 100_000, 0.7)
LENIENT = factual_policy("installed-lenient", 200_000, 0.5)
LADDER_DRAFT = {   # needs station positions, which the collector does not emit yet
    "schema": "tf3c-methodology/1", "id": "installed-ladder", "version": "0.1.0", "name": "Ladder draft",
    "description": "Distance-band draft that cannot run without station geometry.",
    "markers": {"ok": {"symbol": "+", "label": "ok"}},
    "roles": {"line": [{"id": "passenger-line", "select": {"field": "line.is_passenger_only", "op": "eq", "value": True}}]},
    "rules": [{"id": "passenger-lines", "entity": "line", "role": "passenger-line",
               "outcomes": [{"when": {"field": "line.vehicle_count", "op": "ge", "value": 0}, "marker": "ok"}]}],
    "ladders": [{"id": "mode-by-distance", "entity": "line", "role": "passenger-line", "metric": "line.route_km",
                 "bands": [{"max_km": 40, "mode": "ROAD"}, {"max_km": 150, "mode": "RAIL"}, {"mode": "AIR"}],
                 "text": "{line.name} spans {line.route_km|km}; the band suggests {band.mode}."}],
}

# ---- scripts run by the installed interpreter (they import nothing from this checkout) --------------------------

SITECUSTOMIZE = """
import socket


def _blocked(*args, **kwargs):
    raise OSError("network access is blocked by the installed-analysis acceptance test")


socket.socket.connect = _blocked
socket.socket.connect_ex = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked
"""

SERVICE_CHILD = """
import hashlib
import json
import sys
from importlib.resources import files

import tf3companion
from tf3companion.service import Companion

spec = json.loads(sys.argv[1])
service = Companion.open_stored()
try:
    results = {name: service.evaluate(request.get("methodology"), views=request.get("views", ()))
               for name, request in spec.items()}
finally:
    service.close()
example = files("tf3companion").joinpath(
    "methodology/examples/local-feeder-intercity-trunk.tf3c-methodology.json").read_bytes()
print(json.dumps({"module": tf3companion.__file__, "prefix": sys.prefix, "results": results,
                  "exampleSha256": hashlib.sha256(example).hexdigest()}))
"""

MCP_CHILD = """
import json
import os
import sys

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

spec = json.loads(sys.argv[1])
params = StdioServerParameters(command=sys.executable, env=dict(os.environ), cwd=os.getcwd(),
                               args=["-c", "import sys; from tf3companion.cli import main; sys.exit(main(['mcp']))"])


def payload(result):
    data = result.structured_content or json.loads(result.content[0].text)
    return data.get("result", data) if isinstance(data, dict) and set(data) == {"result"} else data


async def main():
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = (await session.list_tools()).tools
        listed = {tool.name: sorted(tool.input_schema.get("properties", {})) for tool in tools}
        results = {name: payload(await session.call_tool("evaluate", request)) for name, request in spec.items()}
        return {"tools": listed, "results": results}


print(json.dumps(anyio.run(main)))
"""


class Installed:
    """A wheel built from this checkout and installed offline into a clean temporary environment."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.runtime = root / "runtime"
        self.data, self.userdata, self.home = self.runtime / "data", self.runtime / "userdata", self.runtime / "home"
        self.work = root / "outside-checkout"
        self.inputs = root / "inputs"
        self.acquisition = self.userdata / "towns_industries"
        for folder in (self.data, self.userdata, self.home, self.work, self.inputs):
            folder.mkdir(parents=True)
        self.venv = root / "venv"
        scripts = "Scripts" if os.name == "nt" else "bin"
        self.python = self.venv / scripts / ("python.exe" if os.name == "nt" else "python")
        self.tf3c = self.venv / scripts / ("tf3c.exe" if os.name == "nt" else "tf3c")
        self.env = self._child_env()

    def _child_env(self) -> dict[str, str]:
        keep = [entry for entry in os.environ.get("PATH", "").split(os.pathsep)
                if entry and not Path(entry).resolve().is_relative_to(REPO)]
        env = {"PATH": os.pathsep.join(keep)}
        for name in ("SYSTEMROOT", "SYSTEMDRIVE", "TMPDIR", "TEMP", "TMP"):
            if name in os.environ:
                env[name] = os.environ[name]
        env.update(HOME=str(self.home), USERPROFILE=str(self.home), LOCALAPPDATA=str(self.home / "AppData" / "Local"),
                   XDG_DATA_HOME=str(self.home / ".local" / "share"), XDG_CONFIG_HOME=str(self.home / ".config"),
                   PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1",
                   TF3C_DATA_DIR=str(self.data), TF3C_USERDATA_DIR=str(self.userdata))
        return env

    def provision(self) -> None:
        uv = shutil.which("uv")
        prerequisite = (
            "Offline provisioning of the installed-wheel acceptance test failed. Prerequisite: `uv` on PATH and uv's local "
            "cache already holding the build backend (hatchling) and the wheels of mcp, openpyxl and platformdirs with their "
            "dependencies (run `uv sync --locked` once with network access). This test never reaches a package index.")
        if uv is None:
            pytest.fail(prerequisite + " `uv` was not found.")
        offline = {**os.environ, "UV_OFFLINE": "1", "PYTHONNOUSERSITE": "1"}
        offline.pop("PYTHONPATH", None)
        wheelhouse = self.root / "wheelhouse"
        steps = [
            [uv, "build", "--offline", "--wheel", "--out-dir", str(wheelhouse), str(REPO)],
            [uv, "venv", "--offline", "--python", sys.executable, str(self.venv)],
        ]
        for command in steps:
            done = subprocess.run(command, cwd=self.root, env=offline, capture_output=True, text=True, timeout=300)
            if done.returncode:
                pytest.fail(f"{prerequisite}\nCommand: {' '.join(command)}\n{done.stdout}{done.stderr}")
        wheels = sorted(wheelhouse.glob("tf3_companion-*.whl"))
        assert len(wheels) == 1, wheels
        install = [uv, "pip", "install", "--offline", "--python", str(self.python), str(wheels[0])]
        done = subprocess.run(install, cwd=self.root, env=offline, capture_output=True, text=True, timeout=300)
        if done.returncode:
            pytest.fail(f"{prerequisite}\nCommand: {' '.join(install)}\n{done.stdout}{done.stderr}")
        purelib = subprocess.run([str(self.python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
                                 env=self.env, capture_output=True, text=True, check=True).stdout.strip()
        (Path(purelib) / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")

    def run(self, command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        done = subprocess.run(command, cwd=self.work, env=self.env, capture_output=True, text=True, timeout=180)
        if check and done.returncode:
            raise AssertionError(f"{' '.join(command)} exited {done.returncode}\n{done.stdout}\n{done.stderr}")
        return done

    def cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return self.run([str(self.tf3c), *args], check=check)

    def cli_json(self, *args: str) -> Any:
        return json.loads(self.cli(*args).stdout)

    def script(self, name: str, code: str, request: dict[str, Any]) -> Any:
        path = self.work / name
        path.write_text(code, encoding="utf-8")
        return json.loads(self.run([str(self.python), str(path), json.dumps(request)]).stdout)

    def inventory(self) -> dict[str, str]:
        """Content hash of every file in the runtime roots (data, userdata and home)."""
        return {str(p.relative_to(self.runtime)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.runtime.rglob("*")) if p.is_file()}


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.external: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        for name, value in attrs:
            if name in ("src", "href") and value and value.startswith(("http://", "https://", "//")):
                self.external.append(f"{tag}[{name}]={value}")
        if tag in ("script", "link", "iframe", "img"):
            self.external.append(f"<{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(self.parts)


def by_label(rule: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {group["group"]: group for group in rule["groups"]}


def hit_markers(result: dict[str, Any], rule_id: str) -> dict[str, str]:
    rule = next(r for r in result["ruleResults"] if r["id"] == rule_id)
    return {h["entity"]["name"]: h["marker"] for h in rule["hits"]}


def hit_evidence(result: dict[str, Any], rule_id: str, name: str) -> dict[str, Any]:
    rule = next(r for r in result["ruleResults"] if r["id"] == rule_id)
    return next(h["evidence"] for h in rule["hits"] if h["entity"]["name"] == name)


@pytest.fixture(scope="module")
def run(tmp_path_factory) -> SimpleNamespace:
    """One complete installed-package session; the tests below assert slices of what it observed."""
    box = Installed(tmp_path_factory.mktemp("installed"))
    box.provision()
    seen = SimpleNamespace(box=box)

    # ---- outside-checkout origin and a blocked network ------------------------------------------------------
    where = box.run([str(box.python), "-c", "import sys, tf3companion; print(tf3companion.__file__); print(sys.prefix)"])
    seen.origin = where.stdout.split()
    blocked = box.run([str(box.python), "-c",
                       "import socket; socket.create_connection(('127.0.0.1', 9), timeout=1)"], check=False)
    seen.network_probe = blocked

    # ---- explicit synthetic acquisition, ingest and methodology import ------------------------------------------
    write_acquisition(box.acquisition)
    seen.ingest = box.cli_json("ingest")
    for name, document in (("strict", STRICT), ("lenient", LENIENT), ("ladder", LADDER_DRAFT)):
        (box.inputs / f"{name}.tf3c-methodology.json").write_text(json.dumps(document, indent=1), encoding="utf-8")
    for name in ("strict", "lenient"):
        box.cli("methodology", "import", str(box.inputs / f"{name}.tf3c-methodology.json"))
    seen.ladder = box.cli_json("methodology", "validate", str(box.inputs / "ladder.tf3c-methodology.json"))
    seen.ladder_strict = box.cli("methodology", "validate", str(box.inputs / "ladder.tf3c-methodology.json"), "--strict",
                                 check=False)
    box.cli("methodology", "set-default", "installed-lenient")
    (box.data / "notes.md").write_text("# Player notes\n\nsentinel: do not touch\n", encoding="utf-8")
    historic = box.data / "reports" / "1979-12-31__historic@0.9.0"
    historic.mkdir(parents=True)
    (historic / "company.md").write_text("# Historical report written long before this run\n", encoding="utf-8")
    seen.protected = {k: v for k, v in box.inventory().items()
                      if not k.endswith(("companion.db", "companion.db-wal", "companion.db-shm"))
                      and not k.startswith("userdata")}

    # ---- stored-only evaluation through the service, the CLI and the MCP adapter ----------------------------------
    before = box.inventory()
    request = {
        "strict": {"methodology": "installed-strict", "views": VIEWS},
        "lenient": {"methodology": "installed-lenient", "views": VIEWS},
        "example": {"methodology": EXAMPLE_ID},
        "user_default": {},
    }
    seen.service = box.script("service_child.py", SERVICE_CHILD, request)
    view_args = [arg for name in VIEWS for arg in ("--view", name)]
    seen.cli = {
        "strict": box.cli_json("evaluate", "--json", "--methodology", "installed-strict", *view_args),
        "lenient": box.cli_json("evaluate", "--json", "--methodology", "installed-lenient", *view_args),
        "example": box.cli_json("evaluate", "--json", "--methodology", EXAMPLE_ID),
        "user_default": box.cli_json("evaluate", "--json"),
    }
    seen.mcp = box.script("mcp_child.py", MCP_CHILD, {
        "strict": {"methodology": "installed-strict", "views": VIEWS},
        "example": {"methodology": EXAMPLE_ID},
    })
    seen.unknown_view = box.cli("evaluate", "--json", "--view", "bogus", check=False)
    seen.evaluation_writes = {path: sha for path, sha in box.inventory().items() if before.get(path) != sha}
    seen.evaluation_removed = set(before) - set(box.inventory())

    # ---- explicit composition and publication of reports ----------------------------------------------------------
    seen.published = {
        "lines": box.cli_json("report", "lines", "--html", "--methodology", "installed-strict"),
        "methodology": box.cli_json("report", "methodology", "--html", "--methodology", "installed-strict"),
        "company": box.cli_json("report", "company", "--methodology", "installed-strict"),
    }

    # ---- a newer acquisition file stays pending until `analyse` ingests it explicitly -------------------------------------
    pending = sample(MONTHS)
    pending_file = box.acquisition / f"tf3c_snap_{pending['meta']['gameTime']:015d}.lua"
    pending_file.write_text(luadata.dumps(pending), encoding="utf-8")
    pending_state = box.inventory()
    seen.after_pending = box.cli_json("evaluate", "--json", "--methodology", "installed-strict")
    seen.pending_unchanged = box.inventory() == pending_state and pending_file.is_file()
    seen.analyse = box.cli_json("analyse", "--methodology", "installed-strict", "--json")
    seen.final = box.inventory()
    return seen


# ---- acceptance ---------------------------------------------------------------------------------------------------


def test_the_installed_package_runs_outside_the_checkout_without_a_network(run):
    module, prefix = run.origin
    installed, venv = Path(module).resolve(), run.box.venv.resolve()
    assert installed.is_relative_to(venv) and not installed.is_relative_to(REPO)
    assert Path(prefix).resolve() == venv and not run.box.work.resolve().is_relative_to(REPO)
    assert Path(run.service["module"]).resolve() == installed
    assert run.network_probe.returncode != 0 and "network access is blocked" in run.network_probe.stderr
    assert run.ingest["failed"] == {} and len(run.ingest["ingested"]) == MONTHS


def test_service_cli_and_mcp_return_the_same_evaluation(run):
    assert "evaluate" in run.mcp["tools"] and run.mcp["tools"]["evaluate"] == ["methodology", "parameters", "save", "views"]
    for name in ("strict", "example"):
        assert run.service["results"][name] == run.cli[name] == run.mcp["results"][name], name
    assert run.service["results"]["lenient"] == run.cli["lenient"]
    assert run.service["results"]["user_default"] == run.cli["user_default"]
    assert run.mcp["results"]["strict"]["analysisViews"].keys() == set(VIEWS)


def test_evaluation_provenance_is_bounded_to_the_selected_stored_endpoint(run):
    strict = run.cli["strict"]
    assert strict["snapshot"] == {"date": "1983-01-01", "gameTime": tick(MONTHS - 1)}
    basis = strict["timeBasis"]
    assert basis["version"] == "game-calendar-v1" and basis["selectedTick"] == tick(MONTHS - 1)
    assert basis["anchorBounds"] == [{"gameTime": tick(0), "date": "1980-01-01"}, {"gameTime": tick(MONTHS - 1), "date": "1983-01-01"}]
    assert strict["methodology"]["source"] == "user" and strict["methodology"]["parameters"] == {
        "loss_alert": 100_000, "maintenance_limit": 0.7}
    assert strict["methodology"]["sha256"] == hashlib.sha256((run.box.inputs / "strict.tf3c-methodology.json").read_bytes()).hexdigest()
    assert list(strict["analysisViews"]) == VIEWS
    for name, view in strict["analysisViews"].items():
        endpoint = view["coverage"]["endpoint"]
        assert endpoint == {"tick": tick(MONTHS - 1), "date": "1983-01-01"}, name
        assert view["coverage"]["eligible"] == MONTHS, name
        assert [u["code"] for u in view["coverage"]["unavailable"]] == MISSING_EVIDENCE.get(name, []), name
        assert max(sample_["tick"] for sample_ in view["coverage"]["sampled"]) <= tick(MONTHS - 1), name


def test_arbitrary_names_are_classified_by_facts_alone(run):
    roles = run.cli["strict"]["roles"]["line"]
    assert roles["roles"] == {"passenger-line": 7, "cargo-line": 1} and roles["unclassified"] == 0
    assert roles["assignments"]["102"] == "cargo-line" and roles["assignments"]["100"] == "passenger-line"
    assert run.cli["strict"]["coverage"]["counts"] == {"skipped": 0, "unsupported": 0, "notEvaluable": 0}


def test_a_different_policy_changes_verdicts_never_the_measured_facts(run):
    strict, lenient = run.cli["strict"], run.cli["lenient"]
    assert hit_markers(strict, "passenger-loss")["Maple Express"] == "problem"
    assert hit_markers(lenient, "passenger-loss")["Maple Express"] == "watch"       # 150,000 loss against 100,000 / 200,000
    assert hit_markers(strict, "passenger-loss")["Quartz"] == hit_markers(lenient, "passenger-loss")["Quartz"] == "ok"
    for result in (strict, lenient):                                                  # the measured numbers are identical
        evidence = hit_evidence(result, "passenger-loss", "Maple Express")
        assert evidence["line.loss_year"] == 150_000 and evidence["line.profit_year"] == -150_000
        assert hit_evidence(result, "vehicle-maintenance", "V1001")["vehicle.maintenance_state"] == 0.6
    assert hit_markers(strict, "vehicle-maintenance")["V1001"] == "problem"          # 0.60 is below 0.7 ...
    assert hit_markers(lenient, "vehicle-maintenance")["V1001"] == "ok"              # ... and not below 0.5
    identity = ("methodology", "methodology_hash", "methodology_selection")
    def engine(result):
        return [{k: v for k, v in f.items() if k not in identity}
                                 for f in result["findings"] if not f["code"].startswith("rule:")]
    assert engine(strict) == engine(lenient) and engine(strict)
    def severity(result):
        return {f["entity"]["name"]: f["severity"] for f in result["findings"] if f["code"] == "rule:passenger-loss"}
    assert severity(strict) == {"Maple Express": "high"} and severity(lenient) == {"Maple Express": "low"}
    assert strict["analysisViews"] != {} and [v for v in strict["analysisViews"]] == [v for v in lenient["analysisViews"]]


def test_the_user_default_applies_only_when_nothing_is_requested(run):
    chosen = run.cli["user_default"]["methodology"]
    assert chosen["id"] == "installed-lenient" and chosen["selection"]["origin"] != "request"
    assert run.cli["strict"]["methodology"]["selection"]["origin"] == "request"


def test_the_packaged_example_screens_aircraft_per_terminal_as_policy_not_congestion(run):
    example = run.cli["example"]
    packaged = REPO / "src" / "tf3companion" / "methodology" / "examples" / "local-feeder-intercity-trunk.tf3c-methodology.json"
    assert run.service["exampleSha256"] == example["methodology"]["sha256"] == hashlib.sha256(packaged.read_bytes()).hexdigest()
    assert example["methodology"]["source"] == "packaged"
    parameters = example["methodology"]["parameters"]
    assert (parameters["air_per_terminal_watch"], parameters["air_per_terminal_problem"]) == (3.0, 3.5)
    air = next(r for r in example["ruleResults"] if r["id"] == "air-station-pressure")
    groups = by_label(air)
    assert {name: groups[name]["measures"]["fleet_per_terminal"] for name in ("Dunmore Field", "Marlow Field", "Kestrel Field")} == {
        "Dunmore Field": 5 / 2, "Marlow Field": 6 / 2, "Kestrel Field": 7 / 2}
    assert {name: groups[name]["marker"] for name in ("Dunmore Field", "Marlow Field", "Kestrel Field")} == {
        "Dunmore Field": "ok", "Marlow Field": "watch", "Kestrel Field": "problem"}
    for name in ("Marlow Field", "Kestrel Field"):
        assert "Not capacity or queue" in groups[name]["message"] and "check the game" in groups[name]["message"]
    # no terminal data for Haze Field: unavailable, never a zero ratio or a marker
    assert groups["Haze Field"]["measures"] == {"vehicles": 4, "terminals": None, "fleet_per_terminal": None}
    assert groups["Haze Field"]["marker"] is None
    assert {"kind": "rule", "id": "air-station-pressure", "entities": 1, "excludedMembers": air["excludedMembers"]} in \
        example["coverage"]["notEvaluable"]
    advice = {r["id"] for r in example["recommendations"]}
    assert {"air-infrastructure-watch", "air-infrastructure-problem"} <= advice


def test_each_view_reports_the_synthetic_facts_and_its_missing_evidence(run):
    views = run.cli["strict"]["analysisViews"]
    trends = {t["name"]: t["trendClass"] for t in views["lines-history"]["trajectories"]}
    assert trends["Lantern"] == "improving" and trends["Maple Express"] == "stable"
    assert views["history"]["status"] == "ok" and views["history"]["usableSamples"] == MONTHS
    items = {(i["code"], i["name"]): i for i in views["bottlenecks"]["items"]}
    stock = items[("stock_output_full", "Redfall Pit")]
    assert (stock["observations"], stock["eligible"], stock["streak"], stock["status"]) == (3, 3, 3, "persistent")
    assert items[("line_load_high", "Maple Express")]["status"] == "persistent"
    assert {s["source"]: s["samples"] for s in views["bottlenecks"]["dataSources"]}["depots"] == 0   # depots never collected
    assert (views["industries"]["industryCount"], views["industries"]["unknownFlowCount"]) == (5, 1)
    candidates = {(c["producer"]["name"], c["consumer"]["name"]): c for c in views["expansion"]["candidates"]}
    assert candidates[("Greywater Pit", "Ironworks")]["unshipped"] == 200
    assert candidates[("Greywater Pit", "Ironworks")]["distanceKm"] == pytest.approx(8.0)
    catalog = views["expansion"]["catalog"]
    assert catalog["priceVerified"] is False and catalog["runningCostsVerified"] is False
    assert catalog["candidates"][0]["price"] is None and catalog["candidates"][0]["runningCosts"] is None
    roi = views["vehicle-roi"]
    assert roi["catalog"]["sample"]["tick"] == tick(MONTHS - 1) and roi["catalog"]["models"] == 2
    assert roi["catalog"]["topSpeedVerified"] is False and roi["catalog"]["runningCostVerified"] is False
    maple = [o for o in roi["observations"] if o["line"] == "Maple Express"]
    assert len(maple) == 2 and all(o["profit"] == -75_000 and o["condition"] == 0.6 for o in maple)
    assert all(o["age"] == pytest.approx(3.0, abs=0.01) and o["maturity"] == "mature" for o in maple)   # from calendar anchors
    assert views["towns"]["summary"]["towns"] == 6 and len(views["towns"]["rows"]) == 6
    assert views["towns"]["pairs"]["linkedPairs"] == 1


def test_geometry_dependent_policy_is_unavailable_without_station_positions(run):
    assert run.ladder["structurallyValid"] is True and run.ladder["activationEligible"] is False
    diagnostic = run.ladder["diagnostics"][0]
    assert diagnostic["category"] == "unsupported-capability" and "stations[].position" in diagnostic["message"]
    assert run.ladder_strict.returncode == 1
    assert list((run.box.data / "methodologies").glob("installed-ladder*")) == []
    assert "Unknown view" in run.unknown_view.stderr and run.unknown_view.returncode == 1


def test_evaluation_writes_nothing_and_never_ingests_pending_evidence(run):
    assert run.evaluation_writes == {} and run.evaluation_removed == set()
    assert run.pending_unchanged
    assert run.after_pending["snapshot"] == {"date": "1983-01-01", "gameTime": tick(MONTHS - 1)}   # newer file left alone


def test_reports_are_composed_and_published_with_the_evaluations_values_and_provenance(run):
    strict = run.cli["strict"]
    published = run.published
    lines_md = Path(published["lines"]["file"])
    folder = lines_md.parent
    assert folder.name == "1983-01-01__installed-strict@1.0.0" and folder.parent == run.box.data / "reports"
    assert {p.name for p in folder.iterdir()} == {"lines.md", "lines.html", "methodology.md", "methodology.html",
                                                  "company.md", "manifest.json"}
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["methodology"]["sha256"] == strict["methodology"]["sha256"]
    assert manifest["methodology"]["parameters"] == strict["methodology"]["parameters"]
    assert manifest["timeBasis"]["anchorHash"] == strict["timeBasis"]["anchorHash"] == published["lines"]["methodology"]["timeBasis"]["anchorHash"]
    assert manifest["snapshot"] == strict["snapshot"] and manifest["counts"] == strict["coverage"]["counts"]
    loss = hit_evidence(strict, "passenger-loss", "Maple Express")["line.loss_year"]
    message = next(h["untrusted"]["message"] for h in next(r for r in strict["ruleResults"] if r["id"] == "passenger-loss")["hits"]
                   if h["entity"]["name"] == "Maple Express")
    for stem in ("lines", "methodology"):
        markdown = (folder / f"{stem}.md").read_text(encoding="utf-8")
        parsed = VisibleText()
        parsed.feed((folder / f"{stem}.html").read_text(encoding="utf-8"))
        assert parsed.external == [], parsed.external                                  # no external asset, script or link
        assert "installed-strict" in markdown and strict["methodology"]["hash"] in markdown
        assert "installed-strict" in parsed.text and strict["methodology"]["hash"] in parsed.text
    lines_md_text = lines_md.read_text(encoding="utf-8")
    assert f"-{loss:,}" in lines_md_text and "95.0%" in lines_md_text
    assert message in (folder / "methodology.md").read_text(encoding="utf-8")
    html = VisibleText()
    html.feed((folder / "lines.html").read_text(encoding="utf-8"))
    assert f"-{loss:,}" in html.text and "95.0%" in html.text and "Maple Express" in html.text
    assert (run.box.data / "reports" / "latest.md").is_file()


def test_analyse_keeps_its_bundle_contract_over_an_explicit_acquisition_folder(run):
    summary = run.analyse
    assert summary["snapshot"] == {"date": "1983-02-01", "gameTime": tick(MONTHS)}    # ingested the pending file now
    assert summary["methodology"]["identity"] == "installed-strict@1.0.0"
    folder = run.box.data / "reports" / "1983-02-01__installed-strict@1.0.0"
    assert {p.name for p in folder.iterdir()} == {"company.md", "lines.md", "methodology.md", "manifest.json"}
    assert sorted(summary["files"]) == sorted(p.name for p in folder.iterdir())
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["snapshot"] == summary["snapshot"] and manifest["methodology"]["sha256"] == run.cli["strict"]["methodology"]["sha256"]
    assert "-150,000" in (folder / "lines.md").read_text(encoding="utf-8")


def test_player_owned_records_survive_every_step(run):
    final = run.final
    for path, digest in run.protected.items():
        assert final.get(path) == digest, path
    stray = [p for p in run.box.home.rglob("*") if p.is_file()]
    assert stray == []                                                                  # nothing written into the home root
