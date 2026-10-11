## 1. Mod data and in-game validation

- [ ] 1.1 Re-read the (renamed) mod collectors for stations, vehicles, stocks, depots and catalog and list in a short note (kept in the change folder until archive) exactly which fields exist. Verify: note names the source line of each field used by design D1.
- [ ] 1.2 Search the game scripts (paths only, no code copied) and API for a direct station-group → served industry/town link and for station positions; decide direct vs proximity (design D1). Verify: the note records the API chosen or the proximity radius source and the evidence.
- [ ] 1.3 Add `stations[].position`, `stations[].industries[]`, `stations[].towns[]` (and `linkSource`) to the station collector inside `pcall`; bump `meta.schemaVersion` to 3; update `knowledge/snapshot_schema.md`. Verify in-game (macOS and, if available, Windows): `tf3c refresh`, then in the new snapshot check three known stations (a sawmill stop, a town bus stop, a depot-adjacent stop) show the right industry/town ids and plausible metre positions; `errors[]` has no `stations.*` entries; frame time unaffected on the large save.
- [ ] 1.4 Validate in-game `loadConfig` (change a truck's cargo in the line editor, refresh, check the snapshot) and the `lifespan` unit/after-lifespan behaviour (compare a vehicle's UI age % with `(gameTime - purchaseTime)/lifespan`). Verify: results written into `knowledge/mechanics.md` with `[INFERENCE]` removed or kept as justified.

## 2. Shared analysis plumbing

- [ ] 2.1 Extend `Thresholds` with all values from design D2 and add the `code` filter to `Companion.findings`. Verify: unit tests for defaults and for filtering by code.
- [ ] 2.2 Add the `analysis_data_missing` finding helper (one per analysis, evidence names analysis and missing fields). Verify: unit test with a snapshot lacking the field.
- [ ] 2.3 Store: additive migration adding `line_history.load_used/load_capacity` and `decisions.done_game_time` with backfill from stored snapshots; add `snapshot_at_or_before(game_time)` and a `line_load_samples(line_id, n)` query thinned to one per game month. Verify: tests open a pre-migration database, migrate twice (idempotent), and check backfilled values and sample thinning.

## 3. Stocks, idle capital, empty lines

- [ ] 3.1 Implement `industry_output_full`, `industries_output_full_unserved`, `warehouse_full`, `station_stock_full` (design D4). Verify: unit tests cover output vs input stock, served vs unserved, 0.90 boundary, missing count, and a 50-industry case yielding one summary finding.
- [ ] 3.2 Rework idle-in-depot into one `fleet_idle_in_depot` finding per depot with town, vehicle rows and `totalIdleValue` (D7). Verify: unit tests for two depots, 5-day vehicle excluded, vehicle without depot id grouped under an "unknown depot" entry.
- [ ] 3.3 Implement `line_no_vehicles`, `line_no_stops`, `line_orphan` (D8). Verify: unit tests for each of the three cases and that no duplicate is emitted for the orphan.

## 4. Load trend

- [ ] 4.1 Write the trend computation (mean, latest, samples, slope; ignore zero-capacity samples) and `line_load_persistently_high/low` findings; suppress instant findings when ≥3 samples (D5). Verify: unit tests for the scenarios in the spec (persistent high, single spike, two snapshots, line with zero-capacity samples).
- [ ] 4.2 Expose `Companion.load_trend`, MCP tool `line_load_trend` and `tf3c insights load-trend`. Verify: service test returns `insufficient_history` for short history; MCP tool listed by the server's tool registry test.

## 5. Cargo config mismatch

- [ ] 5.1 Implement handled-cargo derivation and `vehicle_cargo_mismatch` aggregated per (line, cargo set), severity by `linkSource` (D3). Verify: unit tests for Logs line with Planks trucks, Bricks line with Paper trucks, multi-cargo partial overlap (no finding), passenger stop in a town, missing station links (single `analysis_data_missing`).
- [ ] 5.2 Run against a real snapshot taken after 1.3 on the Hollanda II save (or equivalent). Verify: the two known misconfigurations are reported when re-created in-game and a corrected save yields none; record the result in the change notes.

## 6. Fleet fit

- [ ] 6.1 Implement the fit score, alternatives selection, `vehicle_better_model_available`, `vehicle_near_end_of_life`, `vehicle_model_out_of_production` and the `fleet_fit` view with `unmatched` handling (D6); use `latest_with_catalog`. Verify: unit tests for 40% improvement, 20% (no finding), 85% lifespan, out-of-production, unmatched model, no catalog in history.
- [ ] 6.2 Expose `Companion.fleet_fit`, MCP tool `fleet_fit` and `tf3c insights fleet-fit`. Verify: service test per line and for all lines; tool appears in the registry.

## 7. Line scope economics

- [ ] 7.1 Implement line length from stop positions, band classification and per-band statistics, plus `scope_band_weak` (D9). Verify: unit tests for band boundaries, even/odd medians, immature lines excluded, name-independence, `unclassified` when positions missing.
- [ ] 7.2 Expose `Companion.scope_economics`, MCP tool `scope_economics` and `tf3c insights scope`. Verify: service and registry tests.
- [ ] 7.3 Calibrate the band limits on the real save after 1.3. Verify: a note shows the line-length distribution; thresholds in D2 are kept or adjusted in code and design together.

## 8. `transportedYear` investigation

- [ ] 8.1 Run the in-game comparison described in design D12 over about one game month on at least three lines (one passenger, one cargo). Verify: a table of snapshot value vs in-game window vs vehicle sums is recorded.
- [ ] 8.2 Document the result in `knowledge/mechanics.md` and `knowledge/snapshot_schema.md`. Verify: both topics state meaning, unit, window and confidence; `rg transportedYear src/` shows no analysis consuming it.

## 9. Decision follow-up

- [ ] 9.1 Resolve entity references at `record_decision` (id or exact full name against the latest snapshot) and store `done_game_time` on `done` transitions. Verify: tests for resolved, unresolved-as-note and legacy string entities.
- [ ] 9.2 Implement follow-up metrics, baseline lookup and maturity states (D10) including `entity_missing`, `not_trackable`, `not_applied`. Verify: tests with three synthetic timelines (mature, provisional, too early), a deleted line, no baseline, a planned decision.
- [ ] 9.3 Add the `decision_followup_ready` finding. Verify: tests for ready, outcome already recorded, not yet mature.
- [ ] 9.4 Expose `Companion.decision_followup`, MCP tool `decision_followup` and `tf3c decisions followup [id]`. Verify: service/registry tests and CLI output test for one id and for all.

## 10. Surfaces and documentation

- [ ] 10.1 Add `code` to the XLSX findings sheet and to every CLI findings table. Verify: export test reads the sheet header.
- [ ] 10.2 Document every new code (code, severity, meaning, evidence keys, thresholds) in a knowledge section and the new tools/commands in the tool descriptions (English). Verify: a test asserts every code emitted by the analyses appears in the documentation table.

## 11. Final verification

- [ ] 11.1 Run `uv run pytest -q` and then `tf3c refresh && tf3c findings` on the large real save in-game, checking that each new code appears or is explained by `analysis_data_missing`, and the finding count remains readable (no more than one finding per line/model/depot). Then run `openspec validate analysis-insights`.
