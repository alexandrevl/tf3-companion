# Tasks

## 1. Noncreating stored-evidence access

- [x] 1.1 Add explicit SQLite read-only Store construction without schema DDL/migration and `Companion.open_stored(data=None, save=None)` without Steam discovery or mkdir. Extend store/service regressions for absent roots, supported empty/readonly stores and unsupported schemas, asserting evidence/preferences/outputs remain unchanged and missing stores are not created. Update the existing storage/methodology guide with the stored-only construction contract.
- [x] 1.2 Add the operation-scoped consistent read selection from design D4, retaining `Store.latest()` semantics, endpoint-bounded historical reads, the shared clock and each consumer's sampling limits. Add deterministic regressions with a second connection committing newer evidence during an operation, future observations and legacy-unverified scope; verify the running result stays anchored while the next operation sees new evidence. Document snapshot freshness and isolation limitations.

## 2. Reusable analytical evaluation

- [x] 2.1 Implement `evaluation.py` and the version-1 result/serializer from D2 using existing prepared `Lens`, verdicts and findings. Extend evaluation regressions for more than ten findings/fifteen recommendations, complete rule evidence/roles/aggregates, stable deterministic ordering, policy changes over identical measured facts, unknown evidence and untrusted text labels. Verify no output folder or report parsing is needed; document the result fields in the existing methodology guide.
- [x] 2.2 Implement stored-only `Companion.evaluate` and the shared selected-evidence evaluation helper, consuming current activation/default/report-policy/calendar APIs without duplicate resolution or formulas. Add regressions proving newly available exports are not ingested, invalid effective overrides do not apply, file changes cannot mismatch validated hash/evaluated content, and no requests/reports/preferences/verdict history are written. Document explicit acquisition through ingest/refresh.

## 3. Composite application cutover

- [x] 3.1 Cut over `analyse`, `findings` and single-report orchestration to the shared evaluation and captured reader, preserving their existing checked ingestion and public response shapes. Extend `tests/test_methodology_layout.py` and existing report tests to verify selected methodology/outcomes/coverage agree across evaluation, findings and the bundle for unchanged evidence, including historical endpoints and exclusion of future observations. Update analyse/report examples without adding deprecated aliases.
- [x] 3.2 Separate document composition from rendering/publication so a dual-format single report composes once and consumes identical facts/results in Markdown and HTML. Retain atomic bundle replacement, latest-report semantics, escaped untrusted text and previous-output preservation on failure. Extend existing behavioral rendering/publication failure regressions; document that standalone evaluation still succeeds with an unwritable report destination. Do not extract report-local analysis algorithms in this change.
- [x] 3.3 Make bundle summary construction consume the evaluation rather than reevaluate policy, retaining folder/file fields and current display caps only at that summary boundary. Extend the bundle regression to compare complete evaluation results against correctly capped presentation summaries and matching methodology/time/policy provenance; update the existing changelog/release-note location with the additive evaluate operation and unchanged analyse convenience.

## 4. Peer interfaces

- [x] 4.1 Add `tf3c evaluate [--methodology ID|FILE] [--save ID] [--param NAME=VALUE ...] [--json]` through `open_stored`; keep human output free of report-written claims and machine output complete. Add CLI behavior coverage for absent Steam, explicit save scopes, one-off path selection, invalid overrides and no filesystem changes. Update README/CLI help and methodology examples with runnable stored-only commands.
- [x] 4.2 Add MCP `evaluate(methodology=None, save=None, parameters=None)` using a per-call read-only Companion owned and closed in that call's executing thread. Verify actual tool invocation returns the same factual outcomes/provenance as CLI, rejects methodology paths, and remains correct across repeated/concurrent calls with updated stored evidence; do not test only mock forwarding or tool registration. Update analyst guidance to use evaluate for no-report interpretation and distinguish it from analyse/report; leave unrelated MCP lifecycle work outside scope.

## 5. Integration verification

- [x] 5.1 Run `uv run pytest` after integration and `openspec validate separate-analysis-evaluation --strict`; run the exact synthetic CLI/MCP smoke below from the repository and observe complete analytical results without report writes, equivalent adapter results, then a successful existing analyse bundle. All setup/output is temporary and uses no live game data. No mod or in-game check is required.

```bash
uv run python - <<'PY'
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path('tests').resolve()))
from methodology_helpers import Net
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store
from tf3companion.service import Companion

with tempfile.TemporaryDirectory(prefix='tf3c-evaluate-') as temporary:
    root = Path(temporary)
    data = root / 'companion'
    data.mkdir()
    userdata = root / 'userdata'
    (userdata / 'towns_industries').mkdir(parents=True)
    net = Net().station(1, 'West stop', 10, 'West').station(2, 'East stop', 20, 'East')
    for number in range(20):
        net.line(100 + number, f'Line {number}', [1, 2], profit=-150_000)
    store = Store(data / 'companion.db')
    store.add_snapshot(Snapshot(net.data, source='synthetic.lua'))
    store.close()
    os.environ['TF3C_DATA_DIR'] = str(data)
    os.environ['TF3C_USERDATA_DIR'] = str(userdata)
    def inventory():
        return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob('*') if p.is_file()}
    before = inventory()
    command = ['uv', 'run', 'tf3c', 'evaluate', '--methodology', 'default', '--json']
    cli = json.loads(subprocess.run(command, text=True, capture_output=True, check=True).stdout)
    from tf3companion.mcp_server import evaluate as mcp_evaluate
    machine = mcp_evaluate(methodology='default')
    assert cli == machine
    assert cli['version'] == 1
    assert len([f for f in cli['findings'] if f['code'] == 'line_losing_money']) == 20
    assert cli['snapshot']['gameTime'] == net.now
    assert 'outputFolder' not in cli and 'files' not in cli
    assert inventory() == before, 'Evaluation changed stored evidence or wrote outputs'
    assert not (data / 'reports').exists()
    writable = Companion()
    try:
        bundle = writable.analyse('default')
    finally:
        writable.close()
    assert bundle['snapshot'] == cli['snapshot']
    assert bundle['methodology']['hash'] == cli['methodology']['hash']
    assert bundle['findings']['bySeverity'] == {
        severity: sum(f['severity'] == severity for f in cli['findings'])
        for severity in sorted({f['severity'] for f in cli['findings']})}
    manifest = json.loads((Path(bundle['outputFolder']) / 'manifest.json').read_text())
    assert manifest['snapshot'] == cli['snapshot']
    assert {'company.md', 'lines.md', 'fleet.md', 'cargo.md', 'methodology.md', 'manifest.json'} == set(bundle['files'])
    print(json.dumps({'snapshot': cli['snapshot'], 'completeFindings': len(cli['findings']),
                      'storedOnlyUnchanged': True, 'cliMcpEquivalent': True,
                      'bundleFiles': bundle['files']}, indent=2))
PY
```
