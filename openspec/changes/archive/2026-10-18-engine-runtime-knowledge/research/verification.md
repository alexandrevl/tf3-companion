# Verification of adopted claims against the installed game (tasks 8.1 and 8.2)

Read-only. Scripts were read with `unzip -l` / `unzip -p` style access (members were unpacked to a scratch directory outside the repository, never into it). Citations use the legends of `mechanics.md`: `GM:` = `game_mechanics.zip:game_mechanics/`, `ECO:` = `economy.zip:economy/`, `SCR:` = `scripts.zip:scripts/`, `BASE:` = `base.zip:base/`, `TEAL:` = `api/tealdef/api/`. Line numbers are those of the installed files.

## 8.1 Archives and game build

Install: `<home>/Library/Application Support/Steam/steamapps/common/Transport Fever 3/` (macOS).

| Archive (`base/content/`) | Present | Files | Notes |
|---|---|---|---|
| `game_mechanics.zip` | yes | 793 | `.tl`, `.lua`, `.gs.lua`, `.res.lua`, textures |
| `economy.zip` | yes | 14 | `cargotype.script.lua`, `*.eco.lua` |
| `scripts.zip` | yes | 89 | `journal.d.tl`, `util/town_growth_function.tl` |
| `base.zip` | yes | 27 | `difficulty_util.tl`, `mod.script.tl` |
| `gui.zip` | yes | 2559 | `gui/main/game.tl`, `gui/game_bar/*`, `gui/line_vehicle_mgmt/vehicle_util.tl` |
| `mission.zip` | yes (extra) | n/a | holds `mission/mission.gs.lua` |
| `api/tealdef/` | yes | (directory) | `api/*.d.tl` plus `app.d.tl`, `main.d.tl` |

Build evidence found:

- No build or version file in the game folder (`base/mod.json` is a parameter file; `base/_content.json` carries no version). No version resource is shipped as text.
- Steam manifest `appmanifest_3493540.acf` of this install: `buildid` and `TargetBuildID` 25754343, `LastUpdated` 1791468998 (2026-10-08 16:16 CEST, equal to the executable's file time). This is Steam's id, not the label 40408 / 40420.
- The executable `TransportFever3` (Mach-O, 86 MB) contains the Lua template of `getBuildVersion` and the string **40420** next to the strings "steam", "64-bit" and "Mac Appstore". The label 40408 does not occur in it. Result recorded in `engine.md` (Studied builds, E9 item 1) and `api_catalog.md` (section 7). The run-time return value of `getBuildVersion()` was not observed (no game process was started): still [UNVERIFIED].
- `TEAL:util.d.tl:206` and `TEAL:main.d.tl:39` declare `getBuildVersion` as a string-returning global.

## 8.2 Outcome per claim

Outcome key: **Confirmed** (tag replaced by our own citation), **Contradicted / discrepancy** (both versions kept under `[DISCREPANCY]`), **Partly** (confirmed part cited, rest keeps its tag), **Not settled** (what was read is listed, tag kept).

### (a) Happiness and on-time rating formulas (M13)

| Claim | File read | Result |
|---|---|---|
| Happiness f = 1 − unhappy / max(total, 15) | `GM:towns/town_util.tl:479-503` | Confirmed. The game's total weights `travellingInside` twice and counts `travellingTo` and `travellingFrom` (resident and non-resident) once each; `atBuilding`, `byCar`, `walking`, `byLine` are unused there. |
| On-time f = 1 − late / max(delivered, 10) | `GM:towns/town_util.tl:505-519` | Confirmed. |
| Transform low = 1 − exp(−0.35667 sens), s clamp 0..1, high = −1.2 s² + 2.2 s, clamp((f − low)/(high − low)) | same | Confirmed for both ratings, constants identical. |
| Sensitivity ≤ 0 returns 1 (disabled) | same | Confirmed (also for reputation, traffic, noise, pollution). |
| Sensitivity scales | `BASE:difficulty_util.tl:44-49`, `GM:towns/town_ratings_sensitivity.res.lua`, `BASE:mod.script.tl:680-689` | New: happiness, delivery and traffic scale 0, 0.5, 0.75, 1, 1.5, 2, 3; default level Normal = 1; reputation scale {0, 1}, default On; the mod script writes the player's option over the `.res` levels. |
| Delivery window floor(yearDuration/2 + 0.5) | `GM:towns/town_util.tl:510` | Confirmed (`round(getDefaultYearDuration()/2)`). |
| Rating is per company (min of shared, happiness, on-time) | `GM:towns/town_util.tl:474-519,754-784` | Contradicted as a game rule: the game rates per town only; per-company ratings are MPFever's construction. `[DISCREPANCY]` in M13. |
| Shared rating = min of `urban_care`, `traffic_congestion`, `noise`, `pollution`, fallback `authorityScore` | `GM:towns/town_util.tl:754-784` | Contradicted in shape: the game's `authorityScore` is the min of all six cached ratings (no rating has `added`), clamped to 0..1. `[DISCREPANCY]` in M13. |
| Cached rating `{value, critical}`, `townStates`, `townEntity`, `cachedRatings`, `authorityScore` | `GM:towns/towns.d.tl:55-72`, `GM:towns/town_util.tl:339` | Confirmed; `townEntity` is an entity-and-revision table. |
| Sensitivity override event accepts `pollution`, `noise`, `traffic_congestion` | `GM:towns/towns.script.tl:345-373` | Partly: the event `setTownRatingSensitivity` (parameters `townEntity`, `rating`, `sensitivity`) stores any key; the six lookup keys are known. `resetTownRatingSensitivity` also exists. |
| "Parallel computation makes pollution, noise and traffic non-deterministic" | `GM:towns/town_util.tl:168-173,643-716` | Not settled: all six ratings have a parallel-script function; the noise and pollution random offset is seeded with the town entity (fixed per town). Tag kept, note added. |
| C-library random town development command | grep in `GM:towns/*` | Not settled: no stock script sends it; tag kept. |
| Delivery call arguments `(town, window, true, false)` | `TEAL:engine/util.d.tl:635-641`, `GM:towns/town_util.tl:510-512` | Settled: third and fourth arguments are `perLine`, `perCargoType`; the game passes `false, false` and reads `[-1][-1]` as {late, delivered}; MPFever's `true, false` yields line-keyed results. |
| Happiness call second argument 1000 | `TEAL:engine/util.d.tl:630-634` | Settled: `numTopLines`; the game passes 0. |
| `getTown2personCapacitiesMap` element [1] is residents | `TEAL:engine/system.d.tl:121-125`, `GM:company/company_util.tl:365-371` | Confirmed: array of three capacities {residential, commercial, industrial}; the game sums [1] as world population. `list_towns` sums three, a different quantity. |

### (b) Company experience and rank (M14)

| Claim | File read | Result |
|---|---|---|
| Experience = highest world population seen, never decreases | `GM:company/company_growth.script.tl:9-27`, `GM:company/company_util.tl:365-371` | Confirmed (set to current population only when higher; a debug event can add). |
| One company state for the savegame's company | `GM:company/company_growth.script.tl:94-110`, `GM:company/company_progression_util.tl:74-93` | Partly: state is keyed per company entity but the update loop runs for `getPlayer()` only. |
| Level = first result of `getLevelAndFraction(basePopulation, experience)`, positive base population required | `GM:company/company_progression_util.tl:6-23,95-120`, `GM:company/company_growth.script.tl:81-84` | Confirmed; maximum rank 15; thresholds interpolate the base population toward 725 with weight (15 − r)/14 and apply `SCR:util/town_growth_function.tl`. |
| Base population derivation (was `[UNVERIFIED]`) | `GM:company/company.script.tl:392-399`, `GM:company/company_util.tl:356-363` | Settled: world population at the `initNewGameFromMap` / `initMission` event. |
| `potentialLevel` = rank reached, `level` = rank taken, applied by event | `GM:company/company_growth.script.tl:36-62,153-157` | Confirmed: `applyLevel` accepts only a level above the current one and not above `potentialLevel`. New state starts at 1 and 1. |
| MPFever's field name `potential` mirrors a game field | same | Contradicted: the game field is `potentialLevel`. Tag kept on MPFever's record-name statement. |
| Whether inflation and perks read taken or reached (was `[UNVERIFIED]`) | `GM:company/company_growth.script.tl:36-53,159-170`, `GM:company/company_progression_util.tl:25-58`, `GM:company/company_util.tl:83-93,171-180`, `GM:company/company_growth_config.res.lua` | Settled for two effects: ticket-price multiplier uses the rank reached (`1 + (r − 1)(m − 1)/14`, m = 0.5, none at rank ≤ 1); construction unlocks, extra permits and permit counts use the rank taken. Rank-gated industries not traced: `[UNVERIFIED]` kept. |
| Company state helper returns rank 0 without state | `GM:company/company_util.tl:373-389` | Confirmed; the "most things locked" claim keeps its tag. |
| Permit table: per construction file or permit key `numBuilt`, plus `companyRank` | `GM:company/company_util.tl:83-169`, `GM:company/company_util.d.tl:29-35`, `TEAL:engine/system.d.tl:260-268` | Confirmed; entries have only `numBuilt`; counting is world-wide (no `playerOwnedOnly`); more fields in the table: `extraPermits`, `maximumPermits`, `consumedPermits`, `remainingPermitCooldown`. Which buildings are unique stays MPFever's description. |

### (c) Loan rules and the obtain flow (M7, M15)

| Claim | File read | Result |
|---|---|---|
| `Repay` books only remaining principal; interest block commented out (M7) | `GM:finance/loan.script.tl:167-195` | Confirmed. |
| Payback helper possibly returns principal plus interest (M15 question) | `GM:finance/loan_util.tl:169-176` | Settled: `getFullLoanAndInterestPayBack` returns two numbers (remaining principal, remaining interest); `Repay` books the first only. M7 stands, no discrepancy with MPFever (it books its own choice). Also noted: the loan is dropped from the list regardless of the asynchronous result. |
| Loan state fields `availableLoans`, `obtainedLoans`, `freeId`; offer fields; obtained-loan fields | `GM:finance/loan.script.tl:4-24`, `GM:finance/loan_util.tl:12-22,84-96` | Confirmed; after being taken an offer is a placeholder with `type` and `cooldownUntil` (now + random 4 to 8 default months); `birthDay` is not carried to the obtained loan. |
| Offer regenerates after half a year; cap four loans | `GM:finance/loan.script.tl:59-78,133-134`, `GM:finance/loan_util.tl:3-5` | Confirmed; also regenerates when `cooldownUntil` has passed; the cap is checked at `Obtain`. |
| Schedule months = round(duration / month), remainders on the last payment | `GM:finance/loan.script.tl:82-115`, `GM:finance/loan_util.tl:99-136` | Confirmed. |
| Bookkeeping `ACCOUNT` `balance` / `loan`, journal `OTHER`, `time = -1` | `TEAL:engine.d.tl:22-29`, `SCR:journal.d.tl:4-15`, `GM:finance/loan_util.tl:202-216` | Partly: the game books `LOAN` and `INTEREST` with `time = -1`; the meaning of -1 is not stated in the scripts, so "now" stays the author's assumption (tag kept). |
| Events `Loan`: `Obtain`, `Repay`; obtain carries the offer twice | `GM:finance/loan.script.tl:36-41,119-135` | Confirmed: parameter is {offer taken, loan as configured}. |
| Money above 2^31 occurred | not in scripts | Not settled; tag kept. |
| Contract and notification shapes | not read (outside this task) | Not settled; tags kept. |
| `.gs` script names and the `GAME_SCRIPT.state` read path | `GM:company/company_progression_util.tl:78-79`, archive listings, `TEAL:engine/system.d.tl:320-323`, `TEAL:engine.d.tl:401-412` | Confirmed (all eleven `.gs.lua` exist; the game's own call omits the slash after `::`); acceptance of both forms stays `[UNVERIFIED]`. |

### (d) Day length, `millisPerDay`, steps (M10, E1, M16)

| Claim | File read | Result |
|---|---|---|
| Game day is 4 s (wiki, M10) | all scripts in the five archives (grep `millisPerDay`, `getDefault*Duration`, `DayDuration`) | Not settled: no script holds a numeric day, month or year. Durations come from `api.util.getDefaultDayDuration/MonthDuration/YearDuration` ("game ticks", `TEAL:util.d.tl:110-120`) and from the live `GAME_SPEED.millisPerDay` (`TEAL:engine.d.tl:415-422`). |
| `millisPerDay` of 2000 in `ECO:cargotype.script.lua` | `ECO:cargotype.script.lua:3-47` | Confirmed as what the file holds: a local constant used only to turn milliseconds into days inside its price curves. It is not the game's day length. Its relation to the actual day stays `[UNVERIFIED]`; `[DISCREPANCY]` kept in M10, M16, E1. |
| Calendar-speed factor and the day | `gui/game_bar/game_bar_widgets.tl:321-351` (gui.zip) | New: factor = `getDefaultDayDuration() / millisPerDay`; offered factors 0, 0.25, 0.5, 1, 2, 4. |
| A month is about 30 days | `GM:subventions/subvention_util.tl:290` | [INFERENCE] only: contract code uses `getDefaultDayDuration() * (30 * months ± 30)`. |
| Step of 200 units; `dt` unit | `GM:industries/industries.script.tl:55,128` | Partly: `dt * 1000` against a year in milliseconds reads `dt` as seconds [INFERENCE]; no script states the step size. The 200 stays adopted. |
| `GAME_TIME` / `GAME_SPEED` field semantics | `TEAL:engine.d.tl:415-439`, `gui/main/game.tl:616-668` | Confirmed: `updateCount` stops when paused; `tickCount` ticks once per frame also when paused; `speedup` 0 = paused and can be throttled below the chosen speed (3 stands for 4 throttled). `gameTime` shares the unit of the default durations (`GM:finance/loan.script.tl:61,150`). |

### (e) Vehicle lifespan unit (M6, M9) — not edited in M6 / M9

| Claim | File read | Result |
|---|---|---|
| M6: lifespan probable unit "days" (36525 = 100 × 365.25) | `gui/line_vehicle_mgmt/vehicle_util.tl:31-52`, `gui/entity_window/line/line_eow.script.tl:126-146` (gui.zip) | **Contradicted as stated.** The interface multiplies `maintenance.lifespan` by 1000 before comparing it with `currentGameTime - purchaseTime`, i.e. the unit is seconds of game time (a millisecond clock). Days only if the default day is 1000 ms; with a 4 s day 36525 would be about 25 years. The M6 sentence is owned by another change and was left untouched; the finding is recorded as a `[DISCREPANCY]` bullet in `mechanics.md` "Sources and gaps". |
| M9 `transportedYear` sentence | not examined | Not touched. |

### (f) Rating keys and the six wiki ratings (M2, M13)

| Claim | File read | Result |
|---|---|---|
| `urban_care` is the Reputation rating | `GM:towns/town_util.tl:643-653` | Confirmed (display name "Reputation"; value from event factors and severed main connections, `:396-404`). |
| `traffic_congestion`, `noise`, `pollution`, `people_happiness`, `cargo_delivery` map to Traffic, Noise, Pollution, Happiness, Delivery | `GM:towns/town_util.tl:654-716`, `GM:towns/town_util.d.tl:1-8` | Confirmed; the enum `TownRatingKey` has exactly the six keys. |
| `authorityScore` | `GM:towns/town_util.tl:754-784` | Confirmed as min of the six (see (a)). |

### (g) API shapes settled by the TEAL definitions

Upgraded in `api_catalog.md` (tag replaced by `TEAL:` / `GM:` cites; residual adopted parts split and kept): `forEachEntityWithComponent` (args), `entityExists`, `getPlayer`, `getWorld` (GAME_TIME and GAME_SPEED holders), `getRevision` (signature), `getDefaultYearDuration`, `getDefaultMonthDuration`, `formatMoney`, `getBuildVersion`, `getPlayersBalance`, `JournalEntry.Type` members, `getTerrainAlignmentImpact`, `getAutoRemovalEntityImpact` (and `getTerrainBrushVolumeImpact`), `getLines`, `getLinesIssues`, `getVehicle2Cargo2SimEntitesMap`, `getConstructionEntityForDepot`/`Edge`/`Station`/`Subconstruction`, `forEachConstructionWithMetadata` (third boolean confirmed, fourth optional `playerOwnedOnly` found), `getStationGroup`, `getStock2SimEntityMap`, `getTown2personCapacitiesMap`, `getTownDeliveriesStats`, `getTownHappinessStats`, `getNode2SegmentMap`, `getEdgeObject2EdgeMap`, `getEdgeForEdgeObject`, `getBaseHeightAt`/`getHeightAt`, `getRefundableEntities`/`updateRefundableEntities` (signature), components `PLAYER` (field `headquarters`, not "existence only"), `ACCOUNT`, `COLOR`, `NAME`, `PLAYER_OWNED`, `MAINTENANCE_COST` (fields), `TOWN` (`sizeFactors` confirmed), `GAME_TIME`, `GAME_SPEED`, `GAME_SCRIPT`, section 4.1 text, the `.gs` table source line, and section 7 items (calculateBalance, getLineCapacityUsages, getLineIssues, getLinesIssues arguments; BASE_EDGE type labels; EdgeObject side names; loan.gs state; rank field names; sensitivity keys).

New discrepancy found: MPFever's self-test calls `getConstructionEntityForStation` on `streetConstructionSystem`; the definitions list no such system and put the call on `streetConnectorSystem` (`TEAL:engine/system.d.tl:252`). Recorded as `[DISCREPANCY]` in the call row.

Outcome of M16 reputation line: the game's `town_util.getProposalStats` scores more than two inputs (trees and rocks removed/added, buildings removed, district fraction removed, terrain brush volume, terrain alignment volume, tunnel volume), and only for player-initiated proposals; MPFever lists two inputs. `[DISCREPANCY]` recorded in M16.

### Left adopted (not settled by the scripts)

Everything about engine internals (threads, sync interval, entity-id behaviour, hashing, crash behaviour), the MPFever score, contracts and notification shapes, refunds and demolition costs, street upgrade costs, station-group expiry timing, Lua 5.2 facts and the mock-harness entries; no script or definition in the installed files addresses them.

## Counts of lines containing `ADOPTED` (legend line included)

| Topic | Before | After |
|---|---|---|
| `mechanics.md` | 58 | 46 |
| `engine.md` | 149 | 147 |
| `api_catalog.md` | 189 | 167 |

`uv run pytest tests/test_knowledge_evidence.py -q`: 15 passed after the edits.
