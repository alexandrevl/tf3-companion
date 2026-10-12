## Context

Analyses live in `analysis.py` as pure functions of `Snapshot` (plus previous snapshots) returning `Finding`s; `Companion` (`service.py`) wraps them; `mcp_server.py` and `cli.py` expose them; the SQLite store keeps every snapshot as JSON plus a `line_history` table. After changes 1–2 findings have `code`, English text, per-save stores and schema v2. Today's snapshot (see `knowledge/snapshot_schema.md`, written from `dados.md`) already holds: line `capacity[]` (instant), `stops[]` (stationGroup, name, station, terminal, loadMode), `vehicles[]` with `loadConfig[]`, `canCarry[]`, `depot`, `daysInDepot`, `value`, `purchaseTime`, `models[]`; `stocks[]` (kind station/industry/warehouse, `count`, `capacity`, `cargos`); `depots[]`; `industries[]` with `inputs/outputs` flows and `position`; `catalog[]` (only in `start`/`request` snapshots). Not in the snapshot: station-group positions and which industries/towns a station group serves; stops carry no coordinates. The new fields added to the mod in 1983-03 (`loadConfig`, `stocks`, `depots`, `catalog`) are marked "not yet validated in-game".

## Goals / Non-Goals

**Goals**
- Eight analyses (plus the `transportedYear` investigation) with stable codes and evidence, deterministic and explainable.
- Use stored history (not just the latest snapshot) where an analysis needs it.
- Say precisely which analysis depends on new mod data and validate it in-game.

**Non-Goals**
- Report rendering (change `basic-reports`), MCP prompts (change `agent-experience`), town growth analysis.
- Automatic fixes or any write to the game; the mod stays read-only.
- Depending on any line-naming mod.

## Decisions

### D1. Data sources and mod needs per analysis

| Analysis | Data | New mod data? |
|---|---|---|
| Cargo mismatch | `vehicles[].loadConfig`, line `stops[].station/stationGroup`, **station → served industries/towns**, industry `inputs/outputs`, town cargo | **Yes** |
| Full stocks | `stocks[]`, industry `outputs`/`shippedYear` | No |
| Load trend | `lines[].capacity[]` from history | No (store change) |
| Fleet fit | `vehicles[].models/capacity/purchaseTime`, `models[]` (lifespan, runningCosts), `catalog[]` | No (needs a snapshot with catalog in history) |
| Idle capital | `vehicles[]` (`state`, `line`, `daysInDepot`, `depot`, `value`), `depots[]` | No |
| Empty/orphan lines | `lines[].vehicles/stops` | No |
| Scope economics | **station-group positions**, `lines[].stops`, `profitYear`, vehicles | **Yes** |
| Decision follow-up | stored snapshots, `decisions` | No (small store change) |

New mod data, collected in the existing station collector with `pcall` like the others: `stations[].position` ([x,y,z] metres from the station group's stations; [INFERENCE] same unit as industry positions) and `stations[].industries[]` / `stations[].towns[]` (ids of industries/towns whose cargo this station group can load or unload). The exact game API for the served-industry/town link is **not yet known**; the investigation task searches the game scripts' station/industry APIs first. Only if the game exposes no direct link do we fall back to proximity (industry position within a catchment radius of a station position, radius taken from the game's station catchment constant), flagged `linkSource: "proximity"` in the snapshot and in finding evidence. Because this data was never collected, it MUST be validated in-game (task 1.3) before the analyses are enabled; `meta.schemaVersion` becomes 3 (additive). Older snapshots simply lack the fields → `analysis_data_missing`.

### D2. Thresholds (single frozen `Thresholds` dataclass, all overridable in tests)

| Name | Default | Used by |
|---|---|---|
| `full_stock_ratio` | 0.90 | full stocks |
| `trend_snapshots` | 6 | load trend window |
| `trend_min_samples` | 3 | trend findings |
| `trend_high` / `trend_low` | 0.90 / 0.30 | trend findings (low also needs ≥2 vehicles) |
| `fit_improvement` | 0.25 | better model available |
| `end_of_life_fraction` | 0.80 | near end of life |
| `idle_depot_days` | 30 (existing) | idle capital |
| `scope_local_max_m` / `scope_regional_max_m` | 5 000 / 25 000 | scope bands |
| `scope_weak_ratio` / `scope_min_lines` | 0.25 / 3 | `scope_band_weak` |
| `mature_years` | 1.0 (existing) | scope, follow-up lines |
| `followup_provisional` / `followup_mature` | 0.25 / 1.0 year | follow-up maturity |

The band limits are initial hypotheses to validate against player-approved real route observations (task 7.3), not calibrated constants.

### D3. Cargo mismatch
Per line, `handled` = union of cargos produced by served industries at any stop (outputs), accepted by them (inputs), plus passengers/mail for stops with a served town. For each vehicle, mismatch when its `loadConfig` cargo set is non-empty and disjoint from `handled`. Partially overlapping configs (multi-cargo vehicles) are not flagged. Aggregate per (line, cargo set). `canCarry` is not used for the verdict (it lists what the model *could* carry) but is shown in evidence so the suggestion can say "switch to X".

### D4. Full stocks
An industry stock is an output stock when its cargos intersect the industry's `outputs[]` cargos (input stocks are ignored). Served = any output `shippedYear > 0`. Warehouse and station stocks use count/capacity directly. Stocks with missing count are skipped. Unserved industries are summarised, because 62/108 individual findings would drown the rest; `list_stocks(only_full)` remains the full list.

### D5. Load trend
New columns `load_used`, `load_capacity` on `line_history` (additive migration at store open). When migrating, existing rows are backfilled by iterating the stored snapshot JSON once. Samples are taken from `line_history` ordered by game time, thinned to at most one per game month, last N. Slope = least-squares slope of load on sample index. This replaces `snapshot.lines[].capacity` as the only load source for trend; instant findings stay for short history (decision: keep instant behaviour as fallback instead of removing it). This changes which codes appear for the same line once history is long enough; the proposal calls this out.

### D6. Fleet fit
`score = capacity_for_main_cargo × topSpeed ÷ runningCosts` (running cost per year, as in the snapshot). Main cargo = cargo with most capacity on the line (`capacity[]`), falling back to the vehicle's first `loadConfig`. Current model matched to a catalog entry by model name (catalog entries carry `name`; fall back to `res` if both exist); no match → `unmatched`. Alternatives: same `carrier`, `available`, catalog capacity for that cargo > 0, price shown as context (not in the score). Catalog comes from `Store.latest_with_catalog()`, so monthly snapshots work. End of life: `age / lifespan` where age uses `yearDuration`; `lifespan` is believed to be in days (36525 = 100 years × 365.25, [INFERENCE] in `mechanics`) so lifespan in game time = lifespan_days × yearDuration / 365.25. Unit and effect of exceeding lifespan are validated in-game (task 1.4) before the finding ships. Out of production = no catalog entry with `available` true for the model's name at the current year and `yearTo` < current year.

### D7. Idle capital
Extends the existing aggregated finding: one per depot (name + town from `depots[]` and `stations`/town lookup), with per-vehicle rows (id, name, model, days, value) and `totalIdleValue`. Value comes from the vehicle `value`.

### D8. Empty/orphan lines
Pure line facts: `vehicles == 0`, `stops < 2`. `line_orphan` replaces the other two when both hold. The existing single-purpose finding for vehicle-less lines is absorbed (code reuse from change 1: `line_no_vehicles`).

### D9. Scope economics
Distance = Euclidean on x/y of consecutive stop positions; round-trip lines are not doubled (the band is about one-way reach). Profit per vehicle = `line.profitYear / len(vehicles)` for lines with ≥1 vehicle and age ≥ `mature_years`. Median uses the lower middle for even counts (deterministic). Lines with any missing stop position are `unclassified`.

### D10. Decision follow-up
Entity refs `{kind,id,name}` stored in the existing `entities` JSON column (strings of earlier entries stay valid and are treated as unresolved notes). New nullable column `done_game_time`. Baseline snapshot via a new `Store.snapshot_at_or_before(game_time)`. Mean load for lines uses the three samples nearest each point. Maturity from elapsed game time ÷ `yearDuration`. A decision without game time, and `planned` decisions, use creation game time; planned decisions are labeled `not_applied` in the result since nothing may have changed. Follow-up is read-only.

### D11. Surfaces
- Service (`Companion`): `load_trend(line=None, n=6)`, `fleet_fit(line=None)`, `scope_economics()`, `decision_followup(decision_id=None)`; `findings(code=…)`.
- MCP tools (new): `line_load_trend`, `fleet_fit`, `scope_economics`, `decision_followup`; `findings` gains `code`. Full stocks, mismatch, idle capital and empty lines are findings only (`list_stocks`/`list_vehicles` already give raw views).
- CLI: `tf3c findings --code`, `tf3c insights load-trend|fleet-fit|scope`, `tf3c decisions followup [id]`.
- XLSX: the findings sheet includes `code`.

### D12. `transportedYear`
Investigation only: compare for a few lines the snapshot value against the in-game line window, against the sum of vehicle-level counts and the company `cargoTransported`/`passengersTransported`, over one month of play; hypotheses: it is a per-cargo-unit or per-trip count, or it excludes a window. Findings documented in `knowledge/mechanics.md` and `snapshot_schema.md`. Nothing consumes the field until then.

## Risks / Trade-offs

- **Unvalidated mod APIs** (station links, positions, loadConfig, lifespan unit): mitigated by the validation tasks and by `analysis_data_missing` instead of wrong output.
- **False positives in mismatch** if a station serves an industry the link misses (e.g. proximity radius too small): evidence shows the link source and handled cargos so the user can judge; severity high only when `linkSource` is the game's own link, medium for `proximity`.
- **Alert noise**: aggregation (stocks, fleet fit per line/model, idle per depot) bounds the count; thresholds are centralised.
- **History thinning vs retention** (change 2 prunes files, not stored rows): trend reads from the store, which is unaffected.
- **Instant-load findings replaced by trend ones** may surprise: documented in the proposal and tests.

## Migration Plan

Store migration is additive and idempotent at open (`ALTER TABLE ... ADD COLUMN` guarded by a column check, then backfill). No data is deleted. The mod change is additive; old snapshots stay readable. Rollback: ignore the new columns and fields.

## Open Questions

- Which game API gives the station-group → industry/town link (direct vs proximity)? Resolved by task 1.2 before collector work.
- Exact meaning of `transportedYear` (task 8).
- Whether `lifespan` is in days and what happens past it (task 1.4).
