# Tasks

## 1. Shared calendar clock and evidence selection

- [x] 1.1 Implement the pure `game_time.py` API and `TimeMeasure`/`CalendarEstimate`/`timeBasis` serialization from design D1-D3, including strict Gregorian dates, 365.25 normalization, exact anchors, deterministic >=7-day enclosing interpolation, no extrapolation, stable unknown reasons and anchor hash; add `tests/test_game_time.py` covering the spec's numerical examples, leap/calendar crossing, zero versus unknown, invalid dates, insufficient samples, old/future purchases and varying local rates. Verify those cases assert explicit values/methods/reasons rather than accepting nominal fallbacks.
- [x] 1.2 Add `Store.time_context(snapshot)` using the selected history's compact anchors and ingestion ordering, bounded by evaluation tick; consume verified save/branch context when available and conservatively expose legacy-unverified scope otherwise. Add store regressions for future exclusion, identity conflict, last-ingestion rewind, calendar reversal and conflicting tick dates, while preserving raw JSON and decision rows. Verify no new SQL schema/backfill and no invented lineage; document the store's untraceable legacy-merge limitation in the API docstring.
- [x] 1.3 Change `Snapshot.age_years` to use an explicit clock and remove context-free nominal conversion; add snapshot tests for supported zero, supported interpolation and unknown standalone/past/future dates. Update `knowledge/snapshot_schema.md` and the time-unit section of `knowledge/mechanics.md` to distinguish calendar GAME-YEAR, nominal query ticks, wall time and unresolved lifespan/day units; verify the documented formulas match `test_game_time.py`.

## 2. Core facts and all existing public consumers

- [x] 2.1 Thread one shared context through `analysis.line_age_years`, line/vehicle rows, built-in age-dependent findings and their callers; retain oldest-current-vehicle proxy and keep first-observed spans separate. Add `ageTime` metadata with `ageYears`, null-last sorting and truthful unknown-maturity findings. Verify regression cases where replacing vehicles does not inherit line-history age and a missing age never yields a claimed mature/young fact.
- [x] 2.2 Wire service/CLI/MCP list/detail, JSON findings evidence and XLSX to the same context, preserving list response shapes and adding `timeBasis` as described in D5. Extend consumer and export tests to compare unrounded ages/context hash across every existing age-bearing surface and to inspect XLSX's GAME-YEAR/provenance and blank unknown cells. Update the existing CLI/MCP and export documentation where these fields are described; verify no wall-clock freshness or raw finance values change.
- [x] 2.3 Replace the duplicated time arithmetic in `reports.py`, `report_history.py`, `report_lines_history.py`, `report_vehicle_roi.py`, `report_industries.py`, `report_towns.py` and any remaining report age/history consumers with the shared context. Remove nominal fallback calibrators, day-28 clamping and approximate ordinal substitutes; keep whole-span tick/day diagnostics explicitly separate. Extend report tests for positive-span-only annualization, null age rows, period coverage, known zero spans and identical Markdown/HTML numeric/provenance content; preserve the existing deliberate mismatch between fixture nominal duration and dated time.
- [x] 2.4 Replace company year-ago tick subtraction with the D5 calendar baseline selection and separate decision `elapsedGameYears` from a clearly labelled nominal query-window diagnostic; remove unqualified claims that the profit window is complete. Verify company/decision/annual report tests preserve raw rolling profits, baseline dates, partial coverage and no summing across snapshots. Update `docs/reports.md` with concrete known/unknown and financial-clock examples. Keep basic-reports' annual grouping/orchestration and analysis-insights' unimplemented geometry/fleet/follow-up features out of scope; record that their future age/duration callers must use this clock.

## 3. Methodology cutover, provenance and backwards behavior

- [x] 3.1 Pass the shared context into methodology `Facts`, inherited line/vehicle fields, engine evaluations and built-in finding overrides. Keep numeric maturity parameters unchanged in GAME-YEAR and prohibit methodology-dependent physical conversion. Extend methodology tests for 3-versus-4 policy thresholds on age exactly 3, explicit missing outcomes, unknown tri-state propagation and default-versus-built-in equivalence after the new basis.
- [x] 3.2 Add `timeBasis` and conversion/anchor provenance to methodology summaries, verdicts and generated manifests; update field sources/caveats in `fields.py` and `catalog_doc.py`, then regenerate the existing catalog with `uv run python -m tf3companion.methodology.catalog_doc`. Update packaged example descriptions, `docs/methodologies.md` fidelity notes and the existing release/changelog location to announce the numerical break and unsupported-old-purchase behavior. Verify generated catalog equality and two methodologies producing identical ages and context hashes from the same evidence.
- [x] 3.3 Add backwards-compatibility integration tests opening existing schema-1/2/3 histories with dated, date-less, mixed and legacy-unverified contexts. Verify no raw snapshot JSON, decisions, purchase timestamps or user methodology bytes change; no automatic report rewrite occurs; new outputs carry game-calendar-v1; old provenance-less files remain legacy/unknown-basis. Test that normal explicit report regeneration still follows the existing overwrite contract and that no model-lifespan ratio is silently asserted when its unit remains unverified.

## 4. Integrated acceptance and non-mutating real-data smoke

- [x] 4.1 After all implementation tasks land, run `uv run pytest` once for the complete integrated suite. Verify every scenario in `specs/game-calendar-time/spec.md`, including null-last sorting and cross-surface age equality; do not substitute a narrower fixture to recover the historical P-020 10-to-2 counts.
- [x] 4.2 Run the exact read-only-source real-data smoke below from the repository. It uses SQLite's online backup into a temporary directory, empty temporary game userdata to prevent auto-ingesting/pruning the player's exports, and only temporary report/XLSX outputs. Verify CLI exit success, game-calendar-v1 metadata/hash agreement, consistent null reasons and no nominal fallback. Record actual dated coverage, available versus unknown age counts and isolation warning; do not claim a reproduced P-020 rate/count unless the selected source really supports it. Source read failures or absent real data are an explicit unmet real-data acceptance gate, not permission to use the live store for a normal Companion run.

```bash
uv run python - <<'PY'
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile

# Set the authorized source database explicitly; no personal save path is stored here.
source = Path(os.environ['TF3C_GAME_YEAR_SOURCE_DB']).expanduser().resolve(strict=True)
assert source.is_file(), source

def facts(connection):
    snapshots = connection.execute(
        'SELECT game_time, data FROM snapshots ORDER BY game_time').fetchall()
    decisions = connection.execute('SELECT * FROM decisions ORDER BY id').fetchall()
    payload = json.dumps([snapshots, decisions], sort_keys=True, default=str).encode()
    return len(snapshots), len(decisions), hashlib.sha256(payload).hexdigest()

with tempfile.TemporaryDirectory(prefix='tf3c-game-year-') as tmp:
    root = Path(tmp)
    data = root / 'companion'
    userdata = root / 'userdata'
    data.mkdir()
    (userdata / 'towns_industries').mkdir(parents=True)
    # mode=ro prevents evidence writes and backup includes committed WAL content.
    original = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
    try:
        original.execute('BEGIN')
        before = facts(original)
        assert before[0] > 0, 'Real-data gate: selected store contains no snapshots'
        copied = sqlite3.connect(data / 'companion.db')
        try:
            original.backup(copied)
            assert facts(copied) == before
        finally:
            copied.close()
        original.rollback()
    finally:
        original.close()
    env = {**os.environ, 'TF3C_DATA_DIR': str(data),
           'TF3C_USERDATA_DIR': str(userdata)}
    def cli(*args):
        result = subprocess.run(['uv', 'run', 'tf3c', *args], env=env,
                                text=True, capture_output=True, check=True)
        print('$ tf3c ' + ' '.join(args))
        print(result.stdout)
        return result.stdout
    rows = json.loads(cli('lines', '--sort', 'ageYears', '--limit', '1000'))
    summary = json.loads(cli('analyse', '--methodology', 'default', '--json'))
    basis = summary['timeBasis']
    assert basis['version'] == 'game-calendar-v1'
    assert basis['daysPerYear'] == 365.25
    for row in rows:
        assert row['timeBasis']['anchorHash'] == basis['anchorHash']
        assert row['ageTime']['unit'] == 'GAME-YEAR'
        assert row['ageTime']['value'] == row['ageYears']
        if row['ageYears'] is None:
            assert row['ageTime']['method'] == 'unavailable'
            assert row['ageTime']['reason']
        else:
            assert row['ageTime']['method'] in ('calendar-dates', 'calendar-interpolation')
    seen_null = False
    for row in rows:
        seen_null |= row['ageYears'] is None
        assert not (seen_null and row['ageYears'] is not None), 'Unknown ages must sort last'
    cli('findings', '--json', '--methodology', 'default')
    for kind in ('history', 'lines-history', 'vehicle-roi', 'industries', 'towns', 'decisions', 'company'):
        cli('report', kind, '--html', '--methodology', 'default')
    cli('export')
    manifests = list(data.rglob('manifest.json'))
    assert manifests, 'Reports must record their time basis'
    for manifest in manifests:
        value = json.loads(manifest.read_text())
        assert value['timeBasis']['version'] == 'game-calendar-v1'
        assert value['timeBasis']['anchorHash'] == basis['anchorHash']
    assert list(data.rglob('*.xlsx')), 'XLSX must be written only under the temporary data root'
    copied = sqlite3.connect((data / 'companion.db').as_uri() + '?mode=ro', uri=True)
    try:
        assert facts(copied) == before, 'Analysis must not rewrite evidence or decisions'
    finally:
        copied.close()
    print(json.dumps({'source': str(source), 'sourceOpenedReadOnly': True,
                      'snapshots': before[0], 'decisions': before[1],
                      'knownLineAges': sum(r['ageYears'] is not None for r in rows),
                      'unknownLineAges': sum(r['ageYears'] is None for r in rows),
                      'timeBasis': basis}, indent=2))
PY
```

Privacy redaction before the first repository commit: the original machine-specific save default was removed from this archived command. Set `TF3C_GAME_YEAR_SOURCE_DB` explicitly to the authorized existing source store; the read-only backup and comparison procedure is otherwise unchanged. Do not run `refresh`, `mod install`, player-store ingestion or the retired local scripts as part of this smoke. All temporary output is automatically removed; record coverage/provenance only in an authorized verification record, never commit player data.

- [x] 4.3 Final acceptance: run `openspec validate consistent-game-year-accounting --strict` and confirm the full suite/smoke evidence meets the scenarios. No in-game change or bridge installation is required for this proposal's bounded interpolation contract. Any claim of exact historical purchase dates, speed-independent global calibration or verified save/branch identity remains unaccepted until player-controlled in-game evidence exists through the owning `cross-platform-and-saves` task 3.1/6.2; do not mark those claims passed using synthetic tests or the smoke. If collector changes become necessary, stop this implementation at that explicit unmet gate and seek a separately authorized proposal rather than expanding this change silently.
