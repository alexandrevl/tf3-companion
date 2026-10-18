# Disposition of the research dossiers

Where each dossier section landed, or why it was dropped (task 9.1). Verification outcomes of adopted claims are in `verification.md`. Open-question sections are carried as `[UNVERIFIED]` items or `[DISCREPANCY]` entries in the topics named below; the check for each is written next to the item.

Reasons for dropping, used throughout: multiplayer-only mechanics, source-mod diagnostics, build-specific addresses and offsets (design decision 5), and anything that would read as a procedure to alter the game (design decision 7).

## native-engine.md

| Dossier section | Disposition |
|---|---|
| 1. Builds, executable identity, signature approach | engine.md Studied builds; addresses and signature approach dropped (design decision 5) |
| 2. Threads, timing, step length | engine.md E1, E2 |
| 3. Command kinds and the command pipeline | engine.md E5 (facts only, no procedures) |
| 4. Game-state replication (two states) | engine.md E2 |
| 5. The local-player word (+0x20C) | engine.md E2 and E8 (interface-only versus simulation reading; hooks dropped) |
| 6. ECS: add/remove ordering and id reuse | engine.md E3; snapshot_schema.md Identity and timing caveats |
| 7. Lua runtime and the hash seed | engine.md E4; snapshot_schema.md caveats |
| 8. Transport network: node/port rules and the AreAllNodesEmpty assertion | engine.md E6 |
| 9. Terrain tool behaviour | engine.md E6; mechanics.md M16 |
| 10. Per-company ownership model (census component catalogue, separate-companies) | engine.md E8; api_catalog.md section 3 |
| 11. File locations, logs, crash artifacts, save naming, language detection | engine.md E7; docs/troubleshooting.md |
| 12. Optional engine-tuning knobs (diagnostic; facts about the engine) | Dropped: optional engine-tuning knobs of the source mod (diagnostic switches, not game facts) |
| 13. Determinism evidence tables (verbatim data, paraphrased) | engine.md E8 (prose, no tables of raw data) |
| 14. Co-op vs separate-companies sync table (what the game computes vs what is input) | engine.md E8 |
| 15. The 13 supported languages (launcher/Core.cs:26-34; lang.json; tests/test_lang.py:21) | engine.md E7 (language codes and detection) |
| 16. Miscellaneous game facts found in the slice | engine.md (distributed by theme); minor items dropped: source-mod internals |
| 17. Appendix (build-specific): engine places, build 40420 (PE stamp 0x6ac50427) unless marked 40408 (stamp 0x6ab69fe5) | Dropped by design decision 5: build-specific addresses, offsets and hook sites |
| Open questions / things to verify in the game files | engine.md E9 (Known unknowns); api_catalog.md section 7 |

## changelog.md

| Dossier section | Disposition |
|---|---|
| 1. Game build, game files, save/crash/log artifacts | engine.md E7; docs/troubleshooting.md |
| 2. Engine / runtime model (threads, time, ordering, randomness) | engine.md E1 to E4 |
| 3. Construction, road, track, station, depot behaviour (what builds do) | engine.md E6; mechanics.md M16 |
| 4. Economy: money, companies, loans, subsidies, ranks | mechanics.md M7 see-also, M14, M15, M16 |
| 5. Towns, passengers, cargo, industries (simulation behaviour) | cargo_economy.md section 5; mechanics.md M13, M16 |
| 6. Time, calendar and pacing | engine.md E1; mechanics.md M10 see-also and M16 (DISCREPANCY) |
| 7. Vehicles, lines, stops (behaviour facts) | engine.md E5, E6; mechanics.md M16 |
| 8. Dedicated server / host observations that expose game facts | engine.md E7 (save, backup, watchdog facts only); dedicated-server operation dropped (multiplayer) |
| 9. Instrumentation / API facts for our collector (api_catalog.md candidates) | api_catalog.md; snapshot_schema.md Collector gaps |
| 10. Strategy-relevant observations | strategy.md items H12b, H17b, H20 to H22 (all [?]) |
| 11. Entry-by-entry coverage index (every version entry in CHANGELOG.txt) | Index only; no knowledge content |
| Open questions / things to verify in the game files | engine.md E9; api_catalog.md section 7; mechanics.md Sources and gaps |

## bridge-first-half.md

| Dossier section | Disposition |
|---|---|
| 1. Time, steps, speed, pause (GAME_TIME / GAME_SPEED / simulation step) | engine.md E1 |
| 2. Which Lua state can call what (engine/runtime model) | engine.md E2; api_catalog.md section 1 |
| 3. Entity lookup APIs and component inventory | api_catalog.md sections 2 and 3 |
| 4. Money, refund, maintenance, journal (finance behaviour) | engine.md E5; mechanics.md M15, M16 |
| 5. Vehicle purchase and entity creation behaviour (timing) | engine.md E5 |
| 6. Lines, shared stations, share fees (mod feature but exposes API usage) | Dropped: shared-station fee design of the source mod (multiplayer feature); API usage kept in api_catalog.md |
| 7. Native build behaviour (street/track/station/depot/airport) — game facts hidden in replay logic | engine.md E6; mechanics.md M16 |
| 8. Hashes of state ("what can drift") — the author's list of game state that diverges | engine.md E8 (what drifts, as a list of state that is simulation-computed) |
| 9. Debug environment variables and what they show | Dropped: debug environment variables of the source mod (diagnostics); facts they expose kept in engine.md |
| 10. Entity-reference and id facts | engine.md E3; snapshot_schema.md caveats |
| 11. Station/vehicle/other behaviours explicitly described in comments | engine.md E6; cargo_economy.md section 5 |
| 12. Skipped as multiplayer-only (consciously) | Dropped: multiplayer-only code paths, listed in the dossier |
| Open questions / things to verify in the game files | engine.md E9; api_catalog.md section 7 |

## bridge-second-half.md

| Dossier section | Disposition |
|---|---|
| 1. Script runtime / engine model (how a mod script is hosted) | engine.md E2; api_catalog.md section 1 |
| 2. Company, player entity, account, money | api_catalog.md section 4; mechanics.md M14, M15 |
| 3. Loans (contract with `loan.gs`) | mechanics.md M15; api_catalog.md section 4 |
| 4. Contracts ("Subvention") and notifications | mechanics.md M15; api_catalog.md section 4 |
| 5. Towns | mechanics.md M13; api_catalog.md section 2 |
| 6. Lines | api_catalog.md section 2; snapshot_schema.md Collector gaps |
| 7. Vehicles | api_catalog.md sections 2 and 3 |
| 8. Stations, station groups, depots, stops | api_catalog.md sections 2 and 3; engine.md E6 |
| 9. Infrastructure data (roads, tracks, terrain) — relevance mostly low | api_catalog.md section 3 (low relevance; names only) |
| 10. Build costs and refunds (economy) | mechanics.md M16; engine.md E5 |
| 11. Game scripts catalog (paths seen) | api_catalog.md section 4 |
| 12. Time, ids, bookkeeping | engine.md E3; api_catalog.md section 1 |
| 13. Skipped as multiplayer-only / harness-only (conscious skips) | Dropped: multiplayer-only and harness-only items, listed in the dossier |
| 14. Arithmetic / consistency checks usable for the existing M10 section | mechanics.md M10 see-also and engine.md E1 (day-length DISCREPANCY) |
| Open questions / things to verify in the game files | api_catalog.md section 7; mechanics.md Sources and gaps |

## support-lua.md

| Dossier section | Disposition |
|---|---|
| 1. Town rating formulas (happiness, on-time delivery) | mechanics.md M13 |
| 2. Passenger / cargo statistics APIs used to attribute service to a company | mechanics.md M13; api_catalog.md section 2 |
| 3. Company progression / rank / score | mechanics.md M14 (MPFever's score marked as its own design) |
| 4. Finance: loans, balance, new-company starting money | mechanics.md M15; M7 see-also |
| 5. Contracts / subventions ("subvention" system) | mechanics.md M15; api_catalog.md section 4 |
| 6. Permits (construction permits, headquarters, landmarks) | mechanics.md M14, M15 |
| 7. Entity ids and references (what differs across machines) | engine.md E3; snapshot_schema.md caveats |
| 8. Commands (api.cmd) and proposals — API shapes | api_catalog.md (names and shapes only; no recipes) |
| 9. Lua runtime and sandbox (what a mod can use) | engine.md E4; api_catalog.md section 1 |
| 10. UI hooks (react plugin / replacement / entry point) | api_catalog.md section 5 |
| 11. Companies, players and ownership | engine.md E8 |
| 12. Mod packaging and metadata | api_catalog.md section 5 |
| 13. Mocked engine API shapes (test_lockstep.py) | api_catalog.md section 6 |
| 14. Open questions / things to verify in the game files | api_catalog.md section 7; mechanics.md Sources and gaps |

## our-knowledge-map.md

| Dossier section | Disposition |
|---|---|
| 1. Knowledge files: structure and conventions | Working map for this change; its findings are applied in tasks 1 to 7 and not packaged |
| 2. How topics are discovered and served | Working map for this change; its findings are applied in tasks 1 to 7 and not packaged |
| 3. OpenSpec changes touching knowledge files or time units | Working map for this change; its findings are applied in tasks 1 to 7 and not packaged |
| 4. Lua bridge API usage (`mod/tf3_companion_bridge/content/tf3_companion/`) | Working map for this change; its findings are applied in tasks 1 to 7 and not packaged |
| 5. Places where our files assume things MPFever research might contradict | Working map for this change; its findings are applied in tasks 1 to 7 and not packaged |
| 6. Placement map (where each MPFever theme would land, no recommendations beyond this) | Working map for this change; its findings are applied in tasks 1 to 7 and not packaged |
| Open questions for the change author | Working map for this change; its findings are applied in tasks 1 to 7 and not packaged |
