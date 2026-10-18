# Engine API and component catalogue

Name-level catalogue of the Lua calls, ECS components, game-script state, events, UI-hook and mod-packaging formats the game exposes to mods, with which ones the TF3 Companion bridge actually uses; look up a name here, read `engine` for behaviour.

> **Evidence legend (imported research).** `MPF:<file>` cites a file of MPFever (https://github.com/dkdknight/MPFever, MIT, studied at commit `ae5fc96`; paths relative to its repository root). `[ADOPTED: observed|code|assumed|claim]` marks a fact taken on the MPFever author's word and not verified by this project; the class is the author's own: observed = measured by the author, code = read by the author in game code or the engine, assumed = the author's assumption, claim = stated without evidence. Every statement is paraphrased. `[INFERENCE]`, `[UNVERIFIED]` and `[DISCREPANCY]` keep their existing meaning.

Conventions in this topic:
- **Our own calls are verified by this project.** A row or bullet that cites `bridge.script.lua:<line>` means the call is in `mod/tf3_companion_bridge/content/tf3_companion/bridge.script.lua` at that line (checked with a grep per call, 809-line file); those facts carry no adoption tag. A "no" in a "Used by bridge" column means a grep of that file found no occurrence of the name.
- A fact about a call we do not make is an MPFever fact: argument and return shapes there are the shapes MPFever's code relies on, not documented signatures. Absent a `TEAL:` citation, treat any shape as a hint to check against `api/tealdef/api/` before use.
- Builds: MPFever studied builds 40408 and 40420 (see `engine`). Where the author measured something, the build is not stated per item and is written "build not stated (studied 40408/40420)".
- Abbreviation in this topic only: a *call* is a Lua function reachable from a mod script; a *component* is an ECS record read through `api.engine.getComponent`; a *game script* is a savegame-persisted script (`.gs`) with a state table.
- This catalogue lists names. It carries no procedure to build, buy, command or otherwise change the simulation; the bridge is read-only (`AGENTS.md`).

## 1. Calling conventions and call-state restrictions

### 1.1 Reading components and entities

- Entities are plain integer ids. Our bridge reads a component with `api.engine.getComponent(entity, api.type.ComponentType.X)` and treats a nil or falsy result as "absent" (`bridge.script.lua:105-107`, `194-198`, `293-296`).
- Component reads are transient views: a later read can invalidate an earlier one, so fields must be copied out before the next read. [ADOPTED: claim] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7836)
- Struct properties return copies; a nested value read from a component is a copy, not a live reference. [ADOPTED: claim] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:5062-5076)
- Asking an entity for a component it does not have is slow: a failed read of an engine object costs about 0.1 s even under `pcall` and writes a crash dump (issue 21 in the author's tracker); build not stated (studied 40408/40420). [ADOPTED: observed] (MPF:mod/mpfever_1/content/mpfever_common.lua:204-207)
- The same remark appears for the transport network: a full text dump of one `TRANSPORT_NETWORK` component takes about a quarter of a second, so the author dumps only lane connections and `curSpeed`; a full census once took 26 minutes. [ADOPTED: observed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4528)
- Reading many members of a `Vec3f` value failed repeatedly because its members include functions (distance, lerp, dot and so on). [ADOPTED: observed] (MPF:mod/mpfever_1/content/mpfever_common.lua:204-207)
- Engine userdata expose a member-name list (`__members`) on the object or its metatable, and `tostring` yields `"TypeName: ..."`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_common.lua:177-188)
- Value types: `Vec2f`/`Vec3f`/`Vec4f` (fields `x`, `y`, `z`, `w`) and `Mat4f` (indexable 1..16; built from four `Vec4f` rows; translation in elements 13, 14, 15). Our bridge reads a construction position as `transf[13..15]` (`bridge.script.lua:417-418`, `576-577`). [ADOPTED: code] for the type list (MPF:mod/mpfever_1/content/mpfever_common.lua:228-242)
- Engine enums are tables reachable as `api.type.enum.Carrier`, `api.type.enum.TransportVehicleState`, `api.engine.Component.Line.LoadMode` and `api.type.LineIssue.Type`; our bridge maps a numeric value back to a name by comparing against a fixed name list, under `pcall`, and falls back to `tostring(value)` (`bridge.script.lua:65-95`).
- Every collector in our bridge runs under `pcall` through `try` and records failures in `snapshot.errors`, capped at `MAX_ERRORS=100` (`bridge.script.lua:23`, `37-51`).

### 1.2 Enumerating entities

- Our bridge enumerates with `api.engine.getEntitiesWithComponent(type)` for `INDUSTRY`, `TOWN` and `WAREHOUSE` (`bridge.script.lua:425`, `455`, `554`); lines, vehicles and station groups come from system or util calls (section 2).
- `api.engine.forEachEntityWithComponent(callback(entity), type)` lists entities with a component; the callback receives only the entity id. It refuses some component types with the error "Cannot loop over this component type" (street edges and nodes among them). We do not call it (no match in `bridge.script.lua`). [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_refs.lua:143-190)
- The author notes that not every component type can be listed, and uses `getEntitiesWithComponent(type)` as a fallback. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4517-4525)
- Enumeration cost: tree and emission-emitter entities (`ASSET_GROUP`, `EMISSION_EMITTER`) number over 100000 on a map and carry no other component; do not iterate them. [ADOPTED: observed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4526)
- Alternatives the author uses where listing is refused: the node-to-segments map and the line list (section 2, "Construction and network"). [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_refs.lua:143-190)
- Entity existence: `api.engine.entityExists(entity)` returns a boolean and is used to validate stale ids (for example a vehicle's `depot` field). We do not call it. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:447-449)
- Inside a build proposal, negative ids denote objects the proposal creates and real entities are positive; a placeholder of the form `-400000000 - k` stands for the k-th edge object a proposal adds. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:5660)
- Entity ids are valid only while the entity exists, are not stable between games and are drawn from one counter shared by all entity kinds; see `engine` (entities and ids) for the reuse caveat. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4902)

### 1.3 Lua states and what each can call

The game runs several separate Lua states; modules and the `package.loaded` table are shared per state, not across states. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_auto.lua:1-5)

| State | Entry points | What the author found callable there | Bridge relation |
|---|---|---|---|
| Game-script GUI half (per-frame interface side of a game script) | `guiUpdate(userParams, state, guiState)` every interface frame; `guiHandleEvent(userParams, state, guiState, src, id, name, param)` | `api.engine`, `api.res`, `api.gui`, `api.cmd`, the `app` table in some states, `ug_require`, `os.getenv`/`os.time`/`os.clock`; `guiState:get()` returns a plain table the simulation half published; `guiState:subscribeToAllEvents()` forwards all script events here [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:9551-9606) | Our collector runs here: `bridge.guiUpdate` (`bridge.script.lua:752`), exported by `data()` (`bridge.script.lua:807-809`) and registered by `bridge.gs.lua` as `guiUpdateScript = bridge.script@guiUpdate` |
| Game-script simulation half | `update(userParams, state, dt)` once per simulation step; `handleEvent(userParams, state, src, id, name, param)` | Same `api.engine` reads; command callbacks are disallowed while inside the update; a vehicle bought inside a step appears as an entity at the next step [ADOPTED: observed] (MPF:tests/test_lockstep.py:88) | Not used; `bridge.gs.lua` declares no `updateScript` or `handleEventScript` |
| UI state (windows, tools) | React-like plugin and replacement hooks (section 5) | `api.cmd.*` factories (wrapped by the mod), `api.engine`; its `api.engine` table is writable but `api.cmd` is userdata that takes no new members [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:42-60) | Not used |
| Main-menu UI state | Menu script hosted in its own state where mods are not loaded | Mods are not loaded in this state [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_menu.lua:1-6) | Not applicable |
| Application script state (`--script`) | Application script run from the command line | `app.*` save and load functions (section 2, "Application and files") [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_auto.lua:27-135) | Not used |

- The `app` table is reachable from the GUI half only in some states; our bridge guards `app == nil or app.saveUserdata == nil`, logs "app module is not available in the GUI state; bridge disabled" once and does nothing (`bridge.script.lua:756-762`).
- A game script's module is returned by `data()` with four hooks: `update` and `handleEvent` on the simulation side, `guiUpdate` and `guiHandleEvent` on the interface side; the game-script resource lists each as `{ fileName = "<file>@<function>" }`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:9729-9735)
- Hosting: `.script.lua` resources expose their exports through `data()`, not a return value (our own comment, `bridge.script.lua:806`).
- `state:get()` and `state:set(value)` hold the mod script's table; it is saved with the savegame, and after a load the GUI half reads the stored copy. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:923-925)
- Our guiUpdate keeps its own counters in that table (`state.frame`, `lastGameTime`, `lastRequestId`, `retryFrame`; `bridge.script.lua:753-803`).
- `update` is not strictly once per distinct game time: it can run repeatedly at one clock value while the engine is held. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:1019-1024)
- A command's callback arrives later, in a later interface frame, and the engine applies a queued command one frame after it is sent. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:5252)
- Module loader: `ug_require(path)` accepts a mod file as `"<modId>::/<file>"` or a relative name and a game file as `"::/..."` or `"/game_mechanics/..."`, `"/scripts/..."`, `"/gui/..."`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_common.lua:1432-1440)
- Game modules reachable that way, by name only: `/game_mechanics/finance/loan_util.tl`, `/game_mechanics/company/company_util.tl`, `company_progression_util.tl`, `company_metadata.tl`, `/game_mechanics/towns/town_util.tl`, `/game_mechanics/notifications/notification_util.tl`, `/scripts/entity_util.tl`, `/scripts/mathutil.lua`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:753-760)
- A game-script module is also reachable through the global `game` table, keyed by file name (for example the subventions script with `.handleEvent` and `.update`). [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:1098-1150)
- A Lua chunk or function holds at most 200 local variables; the author hit this repeatedly. [ADOPTED: observed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:164)
- Globals seen: `getBuildVersion()` (guarded in the author's code), `debugPrint(msg)` (writes to the game log), `toString(value)` (dumps an engine object). Our bridge calls `getBuildVersion` for `meta.buildVersion` (`bridge.script.lua:183`) and `print` for `[tf3c]` log lines (`bridge.script.lua:34`). [ADOPTED: code] for `debugPrint` and `toString` (MPF:mod/mpfever_1/content/mpfever_common.lua:77-137)

### 1.4 Reading the clock

- Our bridge reads `GAME_TIME.gameTime` from the world entity and `api.util.getDefaultYearDuration()` (`bridge.script.lua:504-507`).
- The GUI half sees the world only through a component copy that changes about 5 times per second of real time (every handshake), so a GUI-side reader can lag the simulation; see `engine` (clock) for the step, handshake and frame-counter discrepancies.

## 2. Call table by area

Columns: call, arguments, returns, restrictions, and whether our bridge uses it (with the line or the grep result). Lines are in `bridge.script.lua`. Rows used by us take shapes from our own code; rows we do not use carry the MPFever tag.

### 2.1 Entities, players, clock

| Call | Arguments | Returns | Restrictions | Used by bridge |
|---|---|---|---|---|
| `api.engine.getComponent` | entity, `api.type.ComponentType.X` | component table, or nil when absent | Transient copy; failed reads are slow (section 1.1) | yes: 106, 194, 225, 287, 293, 380, 413, 428, 458, 505, 515, 543, 556, 568, 573 |
| `api.engine.getEntitiesWithComponent` | component type | array of entity ids | Some types too large to list (section 1.2) | yes: 425, 455, 554 |
| `api.engine.forEachEntityWithComponent` | callback(entity), component type (`TEAL:engine.d.tl:1704`) | nothing | Refuses some types [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_refs.lua:143-190) | no (grep: 0) |
| `api.engine.entityExists` | entity | boolean (`TEAL:engine.d.tl:1723`) | none known | no (grep: 0) |
| `api.engine.util.getEntityName` | entity | name string | We wrap it in `pcall` | yes: 98 |
| `api.engine.util.getPlayer` | none | player entity of the calling state (`TEAL:engine/util.d.tl:1023`) | One company per game script; the game's loan script, company progression script and ticket-price handler ask it per event (`GM:finance/loan.script.tl:47`, `GM:company/company_growth.script.tl:110,156,161`) | yes: 694 |
| `api.engine.util.getWorld` | none | world entity (`TEAL:engine/util.d.tl:1026`); it holds `GAME_TIME` and `GAME_SPEED` (`GM:company/company_util.tl:89,211`); the holders of `GAME_SCRIPT`, `EMISSION_GRID` and `WORLD` are [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4559-4560) | none known | yes: 505 (for `GAME_TIME`) |
| `api.engine.getRevision` | entity (`TEAL:engine.d.tl:1718`) | revision object whose `.num` is a 3-number array; no revision can be built in Lua [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_common.lua:1417-1420) | none known | no (grep: 0) |
| `api.engine.util.getYear` | none | game year number | none known | yes: 184 |
| `api.engine.util.getCalendarDate` | game time | table with `year`, `month`, `day` | none known | yes: 185 |
| `api.util.getDefaultYearDuration` | none | one game year in game-time units, integer ("default game ticks per year", `TEAL:util.d.tl:118-120`; collector uses it for cadence and the profit window) | Same unit as `gameTime`: the game compares `birthDay + getDefaultYearDuration() / 2` with `gameTime` (`GM:finance/loan.script.tl:61`) | yes: 506 |
| `api.util.getDefaultMonthDuration` | none | one game month in game-time units, integer (`TEAL:util.d.tl:114-116`) | Used by the game for loan payments and loan cooldowns (`GM:finance/loan.script.tl:83,150`) | no (grep: 0) |
| `api.util.formatMoney` | integer | string, money formatted as the game shows it (`TEAL:util.d.tl:58`) | none known | no (grep: 0) |
| `getBuildVersion` (global) | none | build number as a string (`TEAL:util.d.tl:206`, `TEAL:main.d.tl:39`); the executable of the macOS Steam copy carries 40420 (see `engine`) | none known | yes: 183 |

### 2.2 Finance and company

| Call | Arguments | Returns | Restrictions | Used by bridge |
|---|---|---|---|---|
| `api.engine.util.finance.calculateEarnings` | player | earnings value | none known | yes: 199 |
| `api.engine.util.finance.calculateBalance` | list of entity ids, from time, to time, `maintenanceIncomeOnly` boolean (we pass `true`) | balance over the window | Our window is `fromTime = max(now - yearDuration, 0)`; with `true` only maintenance and income entries count and an optional maintenance type narrows further (`TEAL:engine/util.d.tl:842-848`) | yes: 242 (line), 329 (vehicle) |
| `api.engine.util.finance.getPlayersBalance` | player (`TEAL:engine/util.d.tl:861`) | balance integer, or nil | Nil with infinite money: the game's loan script tests for nil to freeze loan accounting (`GM:finance/loan.script.tl:47-50`; existing `mechanics.md` M9) | no (grep: 0) |
| `api.engine.util.headquarters.getCompaniesValue` | none | table with `totalScore`, `railVehicles`, `trams`, `roadVehicles`, `aircrafts`, `ships`, `trackTotalLength`, `trackElectricLength` | none known | yes: 200 (fields 203-210) |
| `api.engine.util.headquarters.getTransportedData` | none | table with `passengersTransported`, `cargoTransported` | none known | yes: 213 |
| `api.engine.util.logbook.getLogValuePerYear` | entity, key string (we pass `"itemsTransported"`) | yearly logged value | Key set not enumerated here | yes: 243 |
| `api.type.JournalEntry.new` and `api.type.JournalEntry.Type` | none | entry with `amount`, `time`, `category.type`; `Type` members `LOAN`, `INTEREST`, `CONSTRUCTION`, `ACQUISITION`, `MAINTENANCE`, `INCOME`, `OTHER`, `SUBSIDY` (`SCR:journal.d.tl:4-15`) | Writing side (a book command); catalogued by name only. The game's loan postings use `time = -1` (`GM:finance/loan.script.tl:94-98`); the meaning of -1 is unverified (section 7) | no (grep: 0) |
| `api.engine.util.town.getTerrainAlignmentImpact` and `getAutoRemovalEntityImpact` (also `getTerrainBrushVolumeImpact`) | a build's proposal data (`ProposalData`; the brush call takes a `Proposal`) | `{Engine.Entity : {number, number}}`: per town {volume added, volume removed} reputation impacts; auto removal is that of trees and rocks (`TEAL:engine/util.d.tl:646-657`) | none known | no (grep: 0) |

### 2.3 Lines and line statistics

| Call | Arguments | Returns | Restrictions | Used by bridge |
|---|---|---|---|---|
| `api.engine.system.lineSystem.getLinesForPlayer` | player | array of line entities | none known | yes: 276 |
| `api.engine.system.lineSystem.getLines` | none | all line entities, `{Engine.Entity}` (`TEAL:engine/system.d.tl:14`) | none known | no (grep: 0) |
| `api.engine.system.lineSystem.getLinesForStationGroup` | station group | array of line entities | none known | yes: 385 |
| `api.engine.util.line.calcLineStationThroughput` | line | per-line rate value (stored as `rate`) | none known | yes: 244 |
| `api.engine.util.line.getMaxFrequency` | line | maximum frequency value | none known | yes: 245 |
| `api.engine.util.line.getLineCapacityUsages` | line, `allCapacities` boolean (we pass `false`: the capacities of the vehicles' current load config, `TEAL:engine/util.d.tl:194-198`) | map cargo id to `{used, capacity}` | none known | yes: 247 (fields 253-254) |
| `api.engine.util.line.getLineIssues` | line, `allIssues` boolean (we pass `false`, `TEAL:engine/util.d.tl:239-243`) | array of issues with `type`, `stopIndex`, `cargoType` | none known | yes: 259 (fields 264-266) |
| `api.engine.util.line.getLinesIssues` | player, `allIssues` boolean (author passes `false`) | map line entity to the issues of all the player's lines, `{Engine.Entity : {LineIssue}}` | The second argument is `allIssues`, "whether to return all issues" (`TEAL:engine/util.d.tl:244-248`) | no (grep: 0) |
| `api.engine.system.transportVehicleSystem.getLineVehicles` | line | array of vehicle entities | none known | yes: 241 |

### 2.4 Vehicles

| Call | Arguments | Returns | Restrictions | Used by bridge |
|---|---|---|---|---|
| `api.engine.util.vehicle.getVehicles` | none | array of vehicle entities (all owners; we filter by `PLAYER_OWNED`) | none known | yes: 362 |
| `api.engine.util.vehicle.getVehicleMaintenanceState` | vehicle | maintenance state value | none known | yes: 326 |
| `api.engine.util.vehicle.getDepreciatedValue` | vehicle | current value | none known | yes: 327 |
| `api.engine.util.vehicle.getRunningCost` | vehicle | running cost | none known | yes: 328 |
| `api.engine.util.vehicle.getVehicleCapacities` | vehicle | map of capacities (our code sums the values) | none known | yes: 330 |
| `api.engine.system.transportVehicleSystem.getNoPathVehicles` | none | array of vehicles without a route | none known | yes: 490 |
| `api.engine.system.simEntityAtVehicleSystem.getVehicle2Cargo2SimEntitesMap` | none | `{Engine.Entity : {CargoTypeId : {Engine.Entity}}}`: vehicle to cargo type to the simulated entities on board; summing list lengths gives the load (`TEAL:engine/system.d.tl:203-206`) | Same system has a count call for one vehicle | no (grep: 0) |

### 2.5 Stations, depots and construction links

| Call | Arguments | Returns | Restrictions | Used by bridge |
|---|---|---|---|---|
| `api.engine.system.stationSystem.getTown` | station entity (we pass the group's first station) | town entity | none known | yes: 382 |
| `api.engine.util.maintenance.calcMaintenanceForStationGroup` | station group | maintenance value | none known | yes: 386 |
| `api.engine.util.construction.getConstructionEntity` | depot (or station-like entity) | construction entity | none known | yes: 572 |
| `api.engine.system.streetConnectorSystem.getConstructionEntityForDepot`, `...ForStation`, `...ForSubconstruction` | depot, station or subconstruction entity | construction entity (`TEAL:engine/system.d.tl:237,252,249`) | none known | no (grep: 0) |
| `api.engine.system.streetConnectorSystem.getConstructionEntityForEdge` | edge | the construction that "owns" the edge (`TEAL:engine/system.d.tl:240`); for example a depot or station entrance | none known | no (grep: 0) |
| `api.engine.system.streetConnectorSystem.forEachConstructionWithMetadata` | metadata key, `constructionDescMeta` boolean, `constructionInstanceMeta` boolean, callback(entity, construction, constructionIdIfDescMatch), optional `playerOwnedOnly` | nothing; `construction.fileName` and `construction.persistentMetadata` available | The second argument checks static metadata and the third instance metadata; the optional fourth skips constructions of other players (`TEAL:engine/system.d.tl:260-268`); the game calls it without the fourth when counting permits (`GM:company/company_util.tl:164`) | no (grep: 0) |
| `api.engine.system.stationGroupSystem.getStationGroup` | station entity | its station group (`TEAL:engine/system.d.tl:97`) | none known | no (grep: 0) |

### 2.6 Industries and stock calls

| Call | Arguments | Returns | Restrictions | Used by bridge |
|---|---|---|---|---|
| `api.engine.util.stock.getProductionRating` | stock list entity | production rating | none known | yes: 441 |
| `api.engine.util.stock.getInputsOutputsFromRules` | stock list entity | pair: input cargo ids, output cargo ids | none known | yes: 442 (used at 444-445) |
| `api.engine.util.stock.getCargoProducedPerYear`, `getCargoMaxProductionPerYear`, `getCargoTypeShippedPerYear` | stock list entity, cargo id | per-year output numbers | none known | yes: 399-401 |
| `api.engine.util.stock.getCargoConsumedPerYear`, `getCargoMaxConsumptionPerYear`, `getCargoTypeDeliveredPerYear` | stock list entity, cargo id | per-year input numbers | none known | yes: 403-405 |
| `api.engine.util.industry.getClosingIndustries` | none | industries scheduled to close | none known | yes: 491 |
| `api.engine.util.stock.getStockCargoTypes` | stock owner entity, 0-based stock id | array of cargo ids | Stock ids are 0-based (our comment, `bridge.script.lua:513`, `520`) | yes: 523 |
| `api.engine.system.simEntityAtStockSystem.getStockCount` | stock owner entity, 0-based stock id | count of simulated entities (cargo) waiting | Same 0-based id | yes: 534 |
| `api.engine.system.simEntityAtStockSystem.getStock2SimEntityMap` | none | `{{Engine.Entity, StockId} : {Engine.Entity}}`: the key is the pair (stock-holding entity, stock id), the value the simulated entities waiting there; list length is the amount waiting (`TEAL:engine/system.d.tl:162-164`) | Alternative route to `getStockCount` (`TEAL:engine/system.d.tl:168`) | no (grep: 0) |

### 2.7 Towns

| Call | Arguments | Returns | Restrictions | Used by bridge |
|---|---|---|---|---|
| `api.engine.system.townBuildingSystem.getLandUsePersonCapacities` | town | `{residential, commercial, industrial}` person capacities (our comment, `bridge.script.lua:467`) | none known | yes: 468 |
| `api.engine.system.townBuildingSystem.getCargoSupplyAndLimit` | town | map cargo id to `{supply, limit, extra}` (read at `bridge.script.lua:474-478`) | none known | yes: 470 |
| `api.engine.util.town.getTownLineUsage` | town | line-usage value | none known | yes: 469 |
| `api.engine.system.townBuildingSystem.getTown2personCapacitiesMap` | none | `{Engine.Entity : {integer}}`: town to an array of three capacities in the order residential, commercial, industrial (`TEAL:engine/system.d.tl:121-125`) | Element 1 is residential; the game sums it as world population (`GM:company/company_util.tl:365-371`) | no (grep: 0) |
| `api.engine.util.town.getTownDeliveriesStats` | town, `interval` in milliseconds, `perLine` boolean, `perCargoType` boolean | `{Engine.Entity : {CargoTypeId : {integer, integer}}}`; cargo key `-1` means all cargo; each pair is {late, delivered} (`TEAL:engine/util.d.tl:635-641`; the game reads `[-1][-1]` with both flags false, `GM:towns/town_util.tl:510-512`) | MPFever passes `true, false` and so gets line entities as outer keys [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:170-207) | no (grep: 0) |
| `api.engine.util.town.getTownHappinessStats` | town, `numTopLines` | `TownHappinessStats` with `travellingInside`, `travellingTo`, `travellingFrom`, `atBuilding`, `byCar`, `walking` and `byLine` (entries {line entity, `resident` / `nonResident` pairs}); pairs are {unhappy, total} (`TEAL:engine/util.d.tl:585-597,630-634`) | The game passes 0 for its rating (`GM:towns/town_util.tl:475`); MPFever passes 1000 [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:208-222) | no (grep: 0) |

Formulas and constants built on the two statistics calls are in `mechanics.md` (M13), not here.

### 2.8 Resources (repositories)

| Call | Arguments | Returns | Restrictions | Used by bridge |
|---|---|---|---|---|
| `api.res.cargoTypeRep.get` | cargo id | cargo record (we read `.name`) | none known | yes: 119 |
| `api.res.cargoTypeRep.getName` | cargo id | resource name | none known | yes: 123 |
| `api.res.cargoTypeRep.forEachCargoType` | cargo type set, callback(cargoId) | nothing | none known | yes: 596 |
| `api.res.modelRep.get` | model id | model record with `metadata` (`maintenance`, `cost`, `description`, `transportVehicle`, `availability`, `landVehicle`, `waterVehicle`, `airVehicle`) | none known | yes: 143, 613 |
| `api.res.modelRep.getName` | model id | resource name | none known | yes: 139 |
| `api.res.modelRep.find` | resource name | model id (negative or nil when missing) | none known | yes: 609 |
| `api.res.modelRep.isVisible` | model id | boolean | none known | yes: 626 |
| `api.res.modelRep.forEachModelWithMetadata` | metadata key (we pass `"transportVehicle"`), callback(resName) | nothing | Same key family the author uses for `"tree"` [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:8074) | yes: 677 |
| `api.res.constructionRep.find` and `.get` | name, or id | id (>= 0 when found); `.get(id).metadata` | Resource-name forms: see 5.4 [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4334-4345) | no (grep: 0) |
| `api.res.streetTemplateRep.getAll`, `.get`, `.getName`, `.find` | none, index, or name | template names; `.get(i).laneConfigs` [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:9059-9076) | none known | no (grep: 0) |
| `api.res.genericRep.getAllOfType` and `.get` (simulation); `api.gui.genericRep.find` (UI) | type string, id; or resource name | ids; `.data` tables (for example contract types with `data.scriptFile`) [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_co.lua:337-346) | State split: `api.res` in the simulation, `api.gui` in the UI | no (grep: 0) |

### 2.9 Application and files (GUI half)

| Call | Arguments | Returns | Restrictions | Used by bridge |
|---|---|---|---|---|
| `app.saveUserdata` | directory, file name, Lua table | nothing | The only output sink; the map editor's town and industry export directory is accepted (`bridge.script.lua:723-724`) | yes: 789 |
| `app.getAllUserdata` | directory | array of file names | Used to check existence first | yes: 730 |
| `app.loadUserdata` | directory, file name | Lua table | Raises a visible in-game error on a missing file even under `pcall` (`bridge.script.lua:727-728`) | yes: 744 |
| `app.saveGame`, `app.SaveGameNamespace.getSavegame`, `app.findAllSavegames`, `app.loadGame`, `api.type.SavegameId.new` | name, callback, flags; namespace; namespace; id, flag; none | entries with `saveName`, `timestamp`, `path`; id with `path`, `saveGameName`, `saveGameNamespace` | Application state only in some states; a save is callback-based and the file is final after the callback [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4455-4495) | no (grep: 0) |
| `app.getSavegameInfo`, `api.type.SaveGameDetails.new`, `api.type.ModId.new`, `app.isWaitForStartReadyGame`, `app.getProgressMonitor`, `app.startReadyGame` | id; info; none; none; none; none | save info with `info.mods` (list of `{name}`); progress 0..1 | Application-script state; savegames record the mods they used [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_auto.lua:27-135) | no (grep: 0) |

### 2.10 Construction, network and terrain reads

| Call | Arguments | Returns | Restrictions | Used by bridge |
|---|---|---|---|---|
| `api.engine.system.streetSystem.getNode2SegmentMap` | none | `{Engine.Entity : {Engine.Entity}}`: node to its segment entities (`TEAL:engine/system.d.tl:300`) | Workaround for components that cannot be listed; a node whose segments carry no `BASE_EDGE_STREET` is a track node [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:2847) | no (grep: 0) |
| `api.engine.system.streetSystem.getEdgeObject2EdgeMap` | none | `{Engine.Entity : Engine.Entity}`: edge-object entity to edge; its size counts stops and signals on the map (`TEAL:engine/system.d.tl:298`) | none known | no (grep: 0) |
| `api.engine.system.streetSystem.getEdgeForEdgeObject` | edge-object entity | edge entity (`TEAL:engine/system.d.tl:296`) | none known | no (grep: 0) |
| `api.engine.system.streetConnectorSystem.getConstructionEntityForStation` | station | construction entity (`TEAL:engine/system.d.tl:252`) | [DISCREPANCY] MPFever's self-test calls it on `streetConstructionSystem` [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:1750); the definitions list no such system and put the call on `streetConnectorSystem` | no (grep: 0) |
| `api.engine.terrain.getBaseHeightAt`, `getHeightAt` | `Vec2f` | ground height number (`TEAL:engine.d.tl:1734,1740`); metres is the author's reading | Terrain cells are 4 m wide; a script cannot read or write the height cells of a terrain edit [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:3930) | no (grep: 0) |
| `api.engine.util.proposal.replaceSegment`, `makeSegmentsRemoveProposal`, `makeProposalData` | edge and optional template; edges; proposal and context | build proposals and proposal data (`errorState.critical`, `.messages`, `.warnings`, `costs`) | Building API, catalogued by name only | no (grep: 0) |
| `api.gui.construction.getRefundableEntities`, `updateRefundableEntities` | none; result entities and street proposal (`TEAL:gui.d.tl:678-682`) | list of just-built entities with revision and update count [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_common.lua:1345-1370) | UI state only | no (grep: 0) |

### 2.11 Command factories (name catalogue)

Commands are `api.cmd.make*Cmd` factories sent through `api.cmd.sendCommand(cmd, callback(result, success))`. Our bridge sends none (grep for `api.cmd` and `sendCommand`: 0). Names the author's engine census lists (the author notes `pairs` cannot enumerate the native table): [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_common.lua:1393-1409)

- Animals and custom entities: `makeAnimalSetStateCmd`, `makeAnimalSpawnAtCmd`, `makeCustomEntityCreateCmd`, `makeCustomEntityDestroyCmd`, `makeCustomEntityUpdateStateCmd`, `makeCustomEntityUpdateTransformationCmd`, `makeCustomVehicleCreateOrUpdateCmd`.
- Entities: `makeEntitySetColorCmd`, `makeEntitySetEmissionsCmd`, `makeEntitySetNameCmd`, `makeEntitySetPlayerCmd`.
- Game and clock: `makeGameAddPlayerCmd`, `makeGameSetCalendarSpeedCmd`, `makeGameSetCloudCoverageCmd`, `makeGameSetDateCmd`, `makeGameSetSpeedCmd`, `makeGameSetTimeOfDayCmd`, plus `api.cmd.debug.makeGamePerformSimulationStepsCmd`.
- Industries: `makeCreateIndustryExtendProposalCmd`, `makeIndustrySetDespawnTimeCmd`, `makeIndustrySetManualDevelopmentCmd`.
- Journal: `makeJournalBookAssetCmd`, `makeJournalClearAllCmd`, `makeJournalLogEntryCmd`.
- Lines: `makeLineCreateCmd`, `makeLineDestroyCmd`, `makeLineUpdateCmd`.
- Scripting: `makeScriptingSendEventCmd`.
- Stocks: `makeStockListDiscardCargoCmd`, `makeStockListSetModifiersCmd`, `makeStockListSetStocksCargoTypeCmd`.
- Towns: `makeTownAutoDetectConnectionsCmd`, `makeTownBuildingSetBlockedDevelopmentCmd`, `makeTownConnectWithIndustriesCmd`, `makeTownCreateCmd`, `makeTownCustomDistributionWeightsCmd`, `makeTownDestroyCmd`, `makeTownDevelopAtCmd`, `makeTownSetDevelopmentActiveCmd`, `makeTownSetInitialLandUseCapacitiesCmd`, `makeTownUpdateCargoNeedsCmd`, `makeTownUpdateSizeCmd`.
- Vehicles: `makeVehicleBuyCmd`, `makeVehicleReplaceCmd`, `makeVehicleReverseCmd`, `makeVehicleSellCmd`, `makeVehicleSendToDepotCmd`, `makeVehicleSetLineCmd`, `makeVehicleSetManualDepartureCmd`, `makeVehicleSetModifiersCmd`, `makeVehicleSetStoppedByUserCmd`, `makeVehicleTryToDepartCmd`.
- World: `makeWorldBuildProposalCmd`, `makeWorldChangeWindCmd`, `makeWorldReplaceTerrainCmd`, `makeWorldSetBulldozableCmd`.

Argument layouts seen, as description: vehicle purchase takes (player, depot, vehicle configuration); sell takes the vehicle; set-line takes (vehicle, line, optional stop index); send-to-depot takes the vehicle plus a second argument (a depot in one place, a boolean in another); line create takes (name, colour, player, line table); line update takes (line, line table); set-name takes (entity, name); set-colour takes (entity, `Vec3f` with channels 0..1); build proposal takes (proposal, context, flag, flag). [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_refs.lua:498-515). The two flags of the build command are labelled "ignore errors" and "player initiated" by the author only. [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:5875-5901)

Result objects seen in command callbacks: `resultEntity`, `resultEntities` (entries are numbers or one-element tables), `resultVehicleEntity`, `proposal.proposal` (the engine's converted proposal), `resultProposalData` with `errorState.messages`, `.critical`, `.warnings`, `collisionInfo.collisionEntities` and `costs`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:5263)

Proposal-side value types, by name: `api.type.SimpleProposal` (with `.streetProposal` lists and `.constructionsToAdd/Remove`), `api.type.Proposal` (`.proposal`, `.toAdd`, `.toRemove`, `.parcelsToRemove`, `.terrain.baseHeightMod`), `NodeAndEntity`, `SegmentAndEntity`, `BaseEdgeStreet`, `Context` (fields `checkTerrainAlignment`, `cleanupStreetGraph`, `gatherBuildings`, `gatherFields`, `player`, `refundableEntities`), `GridVec2f` (fields `x0`, `y0`, `width`, `height` in 4 m cells), `Vec2f`/`Vec3f`/`Vec4f`/`Mat4f`, `TransportVehicleConfig`, `TransportVehiclePart`, `VehiclePart`, `LoadConfig`, `Line` (with `.Stop`, `.StopConfig`), `StationTerminal`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:1320-1421)

### 2.12 GUI-side helpers (name catalogue)

- `api.gui.camera.getCameraData()` returns a table with `x` and `y` (or `[1]`, `[2]`); `setCameraData(d)` moves the camera. Whether camera movement affects the simulation is an author assumption (no). [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:9204-9230)
- `api.gui.rendering.spawnDust`, `api.gui.mission.setZoneCircle`, `api.gui.mission.removeZone`, `api.gui.mouse.hasTerrainPosition`, `api.gui.mouse.getTerrainPosition`: map-marker and effect helpers. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:3895-3913)
- Terrain tool actions are identified by strings beginning `ACTION_TERRAIN_MODIFIER_`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:399-420)

## 3. Component catalogue

Components are read as `api.type.ComponentType.<NAME>` through `api.engine.getComponent`. The author's census lists about 60 types as `api.type.ComponentType` members. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4500-4510) Render-only types (`MODEL_INSTANCE_LIST`, `MODEL_PERSON`, `BOUNDING_VOLUME`) were left out of that list by the author; the author probes `COLLIDER`, `BOUNDING_VOLUME`, `PARCEL`, `TRANSFORM`, `MODEL_INSTANCE_LIST`, `SUBCONSTRUCTION`, `TOWN_BUILDING` and `NAME` under `pcall` without proving each exists. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:8065)

Groups follow the author's ownership model of the separate-companies design: *per company* (the player entity and its books), *owned object* (carries `PLAYER_OWNED`; maintenance is charged to the owner), *shared world* (same for all companies) and *interface-only* (state of the interface, not a component). [ADOPTED: code] (MPF:docs/RESEARCH.md:176-187) The author's group lists name only some types; the rest are placed by "where to look" probing and are labelled "ungrouped". [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4549-4561)

Interface-only items (no component): the interface's local-player word, the tool owner, the money check, windows and money popups of other companies. [ADOPTED: code] (MPF:docs/RESEARCH.md:186)

### 3.1 Components our bridge reads

Every component the bridge reads is listed here and again in the group tables below.

| Component | Fields we read | Where (`bridge.script.lua`) |
|---|---|---|
| `ACCOUNT` | `balance`, `loan` (on the player entity) | 194-197 |
| `LINE` | `stops[]` with `stationGroup`, `station`, `terminal`, `loadMode`, `minWaitingTime`, `maxWaitingTime` | 225-236 |
| `PLAYER_OWNED` | `player` (ownership filter) | 287-288 |
| `TRANSPORT_VEHICLE` | `carrier`, `state`, `line`, `stopIndex`, `userStopped`, `sellOnArrival`, `noPath`, `daysInDepot`, `daysAtTerminal`, `depot`, `transportVehicleConfig.vehicles[]` (`purchaseTime`, `part.modelId`), `config.capacities`, `config.allCaps` | 293-353 |
| `STATION_GROUP` | `stations[]` | 380-381, 543-545 |
| `CONSTRUCTION` | `fileName`, `transf` (elements 13..15 as position) | 413-419, 573-577 |
| `INDUSTRY` | `level`, `maxLevel`, `closureTimeStamp`, `upgradeProgress`, `stockList`, `construction` | 428-439 |
| `TOWN` | `developmentActive`, `noise`, `pollution` | 458-465 |
| `GAME_TIME` | `gameTime` | 505-506 |
| `STOCK_LIST` | `stocks[]` with `type` and `capacity` | 515-535 |
| `WAREHOUSE` | `stockList` | 556-558 |
| `VEHICLE_DEPOT` | `carrier` | 568-570 |

### 3.2 Per company

| Component | Known fields | Read by bridge | Notes |
|---|---|---|---|
| `PLAYER` | `headquarters` (the current headquarters construction; `TEAL:engine.d.tl:847-851`) | no | Player entity; the game supports several player entities, stock game uses one [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:333-345) |
| `ACCOUNT` | `balance`, `loan` (integers, `TEAL:engine.d.tl:22-29`) | yes (194) | Also present on constructions, lines and vehicles per the author's probing list [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4559) |
| `LOG_BOOK` | income and cost log, read through `getLogValuePerYear` | indirectly (243) | Per company, also on lines, vehicles, constructions and persons per the probing list [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4549-4561) |
| `COLOR` | `color`, a `Vec3f` "RGB color of the entity" (`TEAL:engine.d.tl:287-292`) | no | Channels 0..1 are the author's reading [ADOPTED: code] (MPF:docs/RESEARCH.md:182) |
| `NAME` | `.name` string (`TEAL:engine.d.tl:795-800`) | no (we use `getEntityName`, 98) | Also on lines, vehicles and station groups [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_refs.lua:815-820) |
| `PLAYER_OWNED` | `.player` owner entity; an entity with a player owner is that player's property and can be bulldozed only by them (`TEAL:engine.d.tl:854-860`) | yes (287) | Ownership tag on stations, depots, edges, constructions, vehicles and lines; absent or -1 for town streets and unowned savegame objects (a town building has no owner) [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:336-339) |

### 3.3 Owned objects

| Component | Known fields | Read by bridge | Notes |
|---|---|---|---|
| `LINE` | `stops[]`: `stationGroup`, `station`, `terminal`, `loadMode`, `minWaitingTime`, `maxWaitingTime`, `maxAdditionalWaitingTime`, `waypoints[]` | yes, stops (225) | Lua tables are 1-based; the waypoint shape is `{tag, edgePos = {edgeId = {entity, index}, param (0..1 along the lane)}}`; a track found in the opposite direction takes `1 - param` [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:8180-8241) |
| `TRANSPORT_VEHICLE` | `line` (-1 when none), `stopIndex` (0-based, ranges over the line's stops), `state` (enum), `depot` (may be absent, -1 or stale), `userStopped`, `sellOnArrival`, `transportVehicleConfig`, `carrier`, `noPath`, `daysInDepot`, `daysAtTerminal` | yes (293) | `line` and `depot` may not be numbers when absent [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7430-7523) |
| `VEHICLE_DEPOT` | `carrier` | yes (568) | Depot position comes from its construction (572-577) |
| `STATION` | existence; belongs to a station group | no | [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_refs.lua:103-120) |
| `STATION_GROUP` | `stations[]` | yes (380, 543) | Owner found through the group's own `PLAYER_OWNED`, else its first station [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_refs.lua:455-480) |
| `MAINTENANCE_COST` | `maintenanceCost` (integer) and `accumulatedCost` (map keyed by a pair of carriers to integer) (`TEAL:engine.d.tl:606-612`) | no | Believed to sit on constructions, vehicles and edges; the holders are [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4549-4561) |

### 3.4 Shared world

| Component | Known fields | Read by bridge | Notes |
|---|---|---|---|
| `TOWN` | `developmentActive`, `noise`, `pollution` (ours); also `sizeFactors` (array of numbers, a base size of the town), `initialLandUseCapacities`, `capacityScalingFactor`, `levelToCapacityDistributionWeights`, `cargoNeeds` (`TEAL:engine.d.tl:1285-1301`) | yes (458) | Entity list from `getEntitiesWithComponent`; `noise` and `pollution` are accumulated decibel values and the definitions prefer `getTownEmissionDB` |
| `TOWN_BUILDING` | existence | no | A construction hosting town buildings has a non-empty `CONSTRUCTION.townBuildings` [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:6146) |
| `INDUSTRY` | `level`, `maxLevel`, `closureTimeStamp`, `upgradeProgress`, `stockList`, `construction` | yes (428) | [INFERENCE]: the last three are named by our own reads only |
| `STOCK_LIST` | `stocks[]` with `type`, `capacity` | yes (515) | Present on constructions (industries, warehouses) [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4549-4561) |
| `WAREHOUSE` | `stockList` | yes (556) | none |
| `CONSTRUCTION` | `fileName`, `transf` (16 numbers; translation 13..15), `townBuildings`, `params`, `depots[]`, `stations[]`, `timeBuilt`, `subconstructions[].models[]`, `playerEntity` | yes (413, 573) | A construction with an empty `fileName` is a brush asset (trees, plants, rocks), not a building [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:1552-1575) |
| `SUBCONSTRUCTION` | existence | no | Used to resolve a construction by a station entity [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_refs.lua:455-480) |
| `BASE_NODE` | `position` (x, y, z metres) | no | [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:2720-2721) |
| `BASE_NODE_CONFIG` | `laneConnections`, `crosswalks`, `trafficLightPreference`, `trafficLightConfig` (`trafficLightType`, `states`), `userModifiedTrafficLightStates`, `userModifiedLaneConnections`, `doubleSlipSwitch` | no | Present on nodes with a configuration [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7607-7608) |
| `BASE_EDGE` | `node0`, `node1`, `tangent0`, `tangent1`, `position0`, `position1`, `type`, `typeIndex`, `roadTemplate`, `roadStyle`, `roadType`, `roadDevelopmentLocked`, `distance`, `edgeDecorations`, `laneConfigs`, `objects` | no | `type`: 0 ground or street, 1 bridge or track, 2 tunnel; the labels differ between the author's two comments (section 7). `objects` pairs are `{edgeObject entity, side}` with side 0 left stop, 1 right stop, 2 signal [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:2764-2795) |
| `BASE_EDGE_STREET` | `precedenceNode0`, `precedenceNode1`; present only on street segments | no | A track segment has no street component [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7589) |
| `EDGE_OBJECT` | `edgeObjectConstruction`, `param` (0..1 along the segment), `params`, `oneWay`, `left` | no | Stops and signals are edge objects; the side of a stop is relative to segment direction [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:1757-1787) |
| `TRANSPORT_NETWORK` | `nodes`, `edges` with `conns[1..2].entity/.index`, `curSpeed` | no | Huge; never dump in full (section 1.1). On edges, nodes, constructions and edge objects [ADOPTED: observed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4599-4606) |
| `MOVE_PATH` | `path.edges[i].edgeId = {entity, index}`, `dyn.pathPos.edgeIndex` (0-based), `dyn.speed` | no | Absent for a vehicle in a depot; units of `dyn.speed` unverified [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7927-7931) |
| `MOVE_PATH_AIRCRAFT` | existence | no | [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4554-4555) |
| `LAND_VEHICLE`, `AIRCRAFT`, `SHIP`, `TRAIN`, `CARRIAGE`, `CARRIAGE_LIST` | existence; vehicle-kind records | no | Vehicle-kind components next to `TRANSPORT_VEHICLE` [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:309-315) |
| `SIM_PERSON`, `SIM_PERSON_AT_TERMINAL`, `SIM_PERSON_AT_VEHICLE`, `SIM_CARGO`, `SIM_ENTITY_AT_BUILDING`, `SIM_ENTITY_AT_TERMINAL`, `SIM_ENTITY_AT_VEHICLE`, `SIM_ENTITY_IDLE`, `SIM_ENTITY_MOVING` | existence | no | Individually simulated people and cargo units exist as entities [ADOPTED: code] (MPF:docs/RESEARCH.md:168) |
| `EMISSION_GRID`, `EMISSION_EMITTER` | existence | no | Pollution and noise grid on the world entity [ADOPTED: code] (MPF:docs/RESEARCH.md:169) |
| `GAME_TIME` | `gameTime` (the current ingame time), `gameTime0` (time of the last update), `dates`, `timeOfDaySec`, `tickCount`, `updateCount` | yes, `gameTime` only (505) | `tickCount` counts simulation ticks once per frame, also while the game is paused; `updateCount` counts simulation updates and does not tick while paused (`TEAL:engine.d.tl:425-439`) |
| `GAME_SPEED` | `speedup`, a non-negative integer multiplier with 0 = paused, and `millisPerDay`, the length of an in-game calendar day in milliseconds (affected by speedup, 0 = paused) (`TEAL:engine.d.tl:415-422`) | no | The game's interface can lower the engine value below the chosen speed when it throttles to the estimated maximum game speed (value 3 stands for chosen speed 4 throttled by 1; `gui/main/game.tl:616-668` in `gui.zip`), so the value need not equal the button. Can read 0 while the simulation finishes started steps [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:36-41) |
| `GAME_SCRIPT` | `state` (whole Lua state table of one game script) | no | Section 4 [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:112-122) |
| `WORLD` | existence | no | On the world entity [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4559-4560) |

### 3.5 Ungrouped (author did not assign a group)

| Component | Known fields | Read by bridge | Notes |
|---|---|---|---|
| `PERSON_CAPACITY` | existence | no | On constructions [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4549-4561) |
| `CUSTOM_STATE`, `FIELD` | existence | no | On constructions [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4549-4561) |
| `SIGNAL_LIST`, `BRIDGE`, `BASE_PARALLEL_STRIP` | existence | no | On edges [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4549-4561) |
| `BASE_NODE_TRAFFIC_LIGHT`, `RAILROAD_CROSSING` | existence | no | On nodes [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4549-4561) |
| `ANIMAL`, `ASSET_GROUP` | existence | no | `ASSET_GROUP` and `EMISSION_EMITTER` entities exceed 100000 on a map (section 1.2) [ADOPTED: observed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4526) |

- Brush assets (trees, plants, rocks) are entities with `MODEL_INSTANCE_LIST` and no `CONSTRUCTION`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_refs.lua:62-75)
- Shared world versus per company: the author's probing list says edges, nodes, `TRANSPORT_NETWORK`, `MOVE_PATH`, `LAND_VEHICLE`, the `SIM_*` family, `EMISSION_GRID`, `WORLD`, `GAME_TIME` and `GAME_SPEED` are shared; `ACCOUNT`, `LOG_BOOK`, `PLAYER_OWNED`, `COLOR` and `NAME` are per company; `LINE`, `TRANSPORT_VEHICLE`, `VEHICLE_DEPOT`, `STATION`, `STATION_GROUP` and `MAINTENANCE_COST` are owned objects. [ADOPTED: code] (MPF:docs/RESEARCH.md:182-184)

## 4. Game-script state paths, shapes and events

### 4.1 Reaching a game script's state

- `api.engine.system.gameScriptSystem.getEntityForGameScript(name)` returns the script's entity (`TEAL:engine/system.d.tl:320-323`); the script's `GAME_SCRIPT` component has `gameScript` (resource name), `state` (the internal state as a table) and the event subscriptions (`TEAL:engine.d.tl:401-412`), and the game's own progression helper reads that `.state` (`GM:company/company_progression_util.tl:78-79`). That nil or a negative entity means absent, and that the whole state lives in the savegame, is the author's reading. We do not read any game-script state (grep for `gameScriptSystem` and `GAME_SCRIPT` in `bridge.script.lua`: 0). [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:70-122)
- The state table is plain Lua data (the author marshals it before use). [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7645)
- Resource-name forms: the game's own call for the progression script uses the `.gs` suffix with the `::game_mechanics/...` prefix, without a slash (`GM:company/company_progression_util.tl:78`), while `.res` resources are found with `::/game_mechanics/...` (`GM:towns/town_util.tl:56`). The author's code mixes `::/` and `::` forms for game scripts. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_co.lua:240)
- The game keeps company-wide state (progression, permits, loans) for the savegame's company only: progression state is keyed by company entity but only the player's company is updated (`GM:company/company_growth.script.tl:94-110`), and the loan script holds one table (`GM:finance/loan.script.tl:4-24`). The simulation scripts ask `getPlayer()` per event, so a state read is complete for a single-company game. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_co.lua:123-133)

| Script | Resource name |
|---|---|
| Company | `::/game_mechanics/company/company.gs` |
| Progression | `::game_mechanics/company/company_progression.gs` |
| Loans | `::/game_mechanics/finance/loan.gs` |
| Contracts (subventions) | `::/game_mechanics/subventions/subventions.gs` |
| Notifications | `::/game_mechanics/notifications/notifications.gs` |
| Mission (tutorial) | `::mission/mission.gs` |
| Game time | `::/game_mechanics/game_time/game_time.gs` |
| Industries | `::/game_mechanics/industries/industries.gs` |
| Towns | `::/game_mechanics/towns/town.gs` |
| Town cargo | `::/game_mechanics/towns/town_cargo.gs` |
| Celebrations | `::/game_mechanics/celebrations/celebrations.gs` |

Source: all eleven `.gs.lua` files exist in the game archives: `company/company.gs.lua`, `company/company_progression.gs.lua`, `finance/loan.gs.lua`, `subventions/subventions.gs.lua`, `notifications/notifications.gs.lua`, `game_time/game_time.gs.lua`, `industries/industries.gs.lua`, `towns/town.gs.lua`, `towns/town_cargo.gs.lua` and `celebrations/celebrations.gs.lua` under `GM:`, and `mission/mission.gs.lua` in `mission.zip`. The names with a slash after the prefix are as MPFever writes them [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:70-82); the game's own call for progression omits that slash. Our existing knowledge cites the `.script.tl` sources of these scripts (for example `GM:finance/loan.script.tl`); the `.gs` name is the runtime resource.

### 4.2 State shapes seen

Loans (`loan.gs`):
- `availableLoans` is an array of offers; each offer has `type` (`"Small"`, `"Medium"`, `"Large"`, `"ExtraLarge"`), `birthDay` (creation time) and `cooldownUntil`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:792-800)
- An obtained loan has `id`, `amount`, `duration`, `percentage`, `timesPaid`, `lastPayDay`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:844-856)
- MPFever's own per-company loan table has the keys `availableLoans`, `obtainedLoans`, `freeId`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:769)
- [DISCREPANCY] Is the game's `loan.gs` state one global list or per company? The support code says the game's script state is a single global list that holds the savegame company's loans only (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:214-240); the bridge's per-company table is MPFever's own registry (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:353-358), so the two are not about the same object. Which keys the game's own state has is `[UNVERIFIED]` (section 7).
- Loan-module helper names: `createSmallLoan`, `createMediumLoan`, `createLargeLoan`, `createExtraLargeLoan`, `createAvailableLoans`, `createNewObtainedLoan`, `maximalObtainableLoans`, `getMonthlyLoanAndInterestWithErrors`, `getFullLoanAndInterestPayBack`, `makeLoan`, `makeInterest`. Payment arithmetic belongs to `mechanics.md` (M15). [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:769-856)
- Loans are created for a company by the first simulation step that sees it. [ADOPTED: claim] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7633-7638)

Contracts (`subventions.gs`):
- State lists: `proposedSubventions` (offers), `activeSubventions` (accepted), `completedSubventions`, and `failedSubventions`; elements have `uid`, offers also `id`. The lifecycle order is proposed, active, completed, failed. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_co.lua:240-246)
- Contract types are generic resources of type `"subvention"`; each resource's `data.scriptFile` has the form `path@function`, and each type table has `handleEvent`, `onAccept`, `onComplete`, `onFailure`. The four type names seen are `deliver_cargo`, `deliver_passengers`, `deliver_cargo_town`, `deliver_workers`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:1098-1150)
- Rewards and penalties are booked to whoever `getPlayer()` returns in the script context at the moment of accept, complete or failure. [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_co.lua:288-303)
- A contract card's notification uid is the entity times 10000. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:1495)
- Contract fields beyond `id` and `uid` (cargo, endpoints, reward, deadline) were not seen (section 7).

Notifications (`notifications.gs`):
- `state.notifications` maps id to an entry with `notification` (`type` string of the form `game_mechanics/notifications/types/<name>.script` and `params`), `expired`, `dismissed`, `timestamp` (game time) and `persisting` (a non-empty table marks a persistent notification such as a warning or contract card). [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:1480-1530)
- Contract cards use a type containing `subvention` and `params.uid` equal to the contract uid. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7709-7717)
- Entity references in notification params have the shape `{entity, revision = {num = {a, b, c}}}`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:1520)
- The "Industry Founded" notification is generated by each game's interface (UI state), not by the simulation; the interface scans industries about every 5 s of game time. Type name for a new industry: `industry_spawn`, with params `{entity}`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:1612-1640)
- Notification types for contracts: card `subvention_notification.script`, failure `subvention.script`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_co.lua:349-380)
- Notification utility names: `updatePersistentNotifications`, `externalGetNotificationsStateNative`, `getNotificationEntryFromNative`, `getHistoryFromNative`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_co.lua:349-380)

Progression and permits (game modules, not a `.gs` read):
- `company_progression_util.tl`: `getCompanyProgressionState(companyEntity)` returns a table with `experience`, `level` and a third rank value; `getLevelAndFraction(basePopulation, experience)` returns the level first. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:124-153)
- [DISCREPANCY] The third rank field is named `potentialLevel` in the progression code (MPF:mod/mpfever_1/content/mpfever_progression.lua:21-27) and `potential` in the bridge's own rank record (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:9453); the bridge record is the author's format, so `potentialLevel` is the likelier game name. Check section 7.
- `company_util.tl`: `getBasePopulation()` (a positive number; an error when it is not), `getConstructionDisableCacheData(allDefs)` returning a table with `companyRank` and `data[key] = {numBuilt}`, `countUsedConstructionPermits`, `getActualPermitKey(fileName, metadata)`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_co.lua:157-200)
- `company_metadata.tl`: `getKey()` and `constructionInstance.get(persistentMetadata)`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:124-153)
- The progression state is read for the player a state acts as; another company would find rank 0 and mostly locked things. [ADOPTED: claim] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:9408-9410)

Towns (`town_util.tl`):
- `externalGetTownsState()` returns a table with `townStates[]`; each entry has `townEntity` (a number or a table with `.entity`), `cachedRatings` (keyed by rating, each with a numeric `.value`) and `authorityScore`; `getRatingSensitivity(townState, key)` reads a sensitivity. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:37-41)
- Sensitivity keys: `people_happiness`, `cargo_delivery` (company-earned); cached shared rating keys: `urban_care`, `traffic_congestion`, `noise`, `pollution`. Per-town override keys seen in an event: `pollution`, `noise`, `traffic_congestion`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:155-168)
- Range of `.value` (0..1 or other) and of `authorityScore` are unverified (section 7). Formulas: `mechanics.md` (M13).

Mission (`mission.gs`): state has `isTutorialActive` and `isComplete`; a tutorial in a save changes game state. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:2411-2417)

MPFever-private state keys, not game state: `revision`, `guiTimeSeconds` (local counters of the author's scripts). [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:59-62)

### 4.3 Event names (name catalogue)

Handler signature: `handleEvent(userParams, state, src, id, name, param)`. A script event carries four fields (source, id, name, parameter), where the first is an empty string for game scripts. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7652) The meaning of the first field is an author assumption. [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7652)

| Id | Name | Parameter keys seen | Notes |
|---|---|---|---|
| `apply_command` | `onPreBuildProposal` | `param[1]` proposal, `param[2]` proposal data (`costs`), `param[4]` player-initiated flag | Announced to game scripts before a build is applied [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:1435-1460) |
| `apply_command` | `onPostBuildProposal` | `param[3]` result entities (a number, or a table with the entity first) | After a build [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:1763-1776) |
| `Loan` | `Obtain`, `Repay` | offer or loan record | Loan window events [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7652) |
| `Subvention` | `onAccept`, `onDecline`, `_debugSpawn`, `_debugComplete` | `uid`; `index` for the completion debug event | The two debug names belong to the game's own debug events [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7677-7705) |
| `OnCalcTicketPrice` | (event id of the contract price hook) | `param` array whose entries expose `lineEntity`; the handler returns a table indexed like `param` | Flows through the subventions script [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_co.lua:259-285) |
| `Notifications` | `add`, `dismiss`, `enlist`, `updateIgnoredTypes` | `type`, `params.uid`; `id` for dismiss | Sent by the interface locally [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:89-95) |
| `Towns` | `setTownRatingSensitivity` | town entity, rating key, sensitivity | Sets one town's sensitivity for one rating; 0 disables it (existing `mechanics.md` M2) [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:9296-9301) |
| `Company` / `Companies` | `applyLevel` | `level` | Rank taken in the company window; a rank can be reached but not taken [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:244-263) |
| tool id (for example `streetBuilder`) | names beginning `builder.` | (varies) | Construction tools emit these while the player aims and when building; seen in `guiHandleEvent` [ADOPTED: observed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:9718-9726) |
| application | `mainMenuReady` | none | Application-script state [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_menu.lua:86-120) |

- Build-hook builds started by the game's own scripts (town growth, industries) report a player-initiated flag of false; player and tool builds report true. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:1440)
- [DISCREPANCY] Positions in the build-event parameter: the bridge reads `param[1]` proposal, `param[2]` proposal data, `param[3]` result, `param[4]` player-initiated (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:1796-1839); the test mock lists `{proposal, context, result, playerInitiated}` (MPF:tests/test_lockstep.py:63-68). The mock is the author's simplification; the second slot (proposal data or context) is unresolved.
- The notification-event call surface and every mod-private event (`mpfever` family) are omitted: they are protocol, not game facts.
- `game_mechanics` messages from `errorState.messages` name why a build was refused; the validator names behind "Construction impossible" are unmapped.

## 5. UI-hook and mod-packaging formats

### 5.1 UI hooks (`*.res.lua` resources)

- A mod registers a UI hook with a `*.res.lua` file whose `data()` returns a table with `type`, `data` (`filePath`, `order`). Type `"react-plugin ::ModEntryPointExtension"` mounts an invisible component on the game's mod entry point whose `onStep` hook runs every UI step; `filePath` has the form `<modId>::/<file>@<ComponentName>` and `order` 1000 was used. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_entry.res.lua:1-10)
- Type `"react-replacement-config"` has `data = {filePath = "<modId>::/<file>", doReplaceFn = "doReplace", order = 1000}`; the game runs the named function with a replacement API in the UI Lua state at UI boot. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.res.lua:1-11)
- A UI script module returns `M` from `data()`, with `M.doReplace` and component recipes; a recipe is registered through `react.RegisterPluginRecipe(entry.ModEntryPointExtension, "Name", fn)`. The loaders are `::/gui/main/react.lua`, `::/gui/main/builtin.lua`, `::/gui/main/mod_entry_point.tl`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:1786-1797)
- React-like API names: `react.onStep`, `react.onStepTimer`, `react.onMount`, `react.useState`, `react.useStateLazy`, `react.RegisterRecipe`, `react.RegisterWrapperRecipe`; widgets `builtin.TextView`, `Button`, `Component`, `BoxLayout`, `FloatingLayout`, `FloatingLayoutChild`, `TextInputField`, `ComboBox`, `ComboBoxItem`, `ImageView`, `Window`; enum `builtin.type.Orientation.Vertical/Horizontal`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:700-1000)
- Recipe ids come from `api.gui.react.detail.makeRecipeId(name, ...)`; named game recipes seen: `MainPage`, `PauseMainPage`, `ReleaseNotesWindow`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_menu.lua:86-88)
- UI modules and helpers seen by name: `/gui/main/game.tl` (default window container), `/gui/entity_window/make_entity_window.tl`, `/scripts/entity_util.tl` (`getEntityName`, `isOwnedByPlayerOrNotOwned`, `makeEntityAndRevision`), `/gui/construction/construction_react_util.tl`, `::/gui/main/default_colors.gres` (colours `Ok`, `Warning`, `Error`, `Info`, `Negative`, `NeutralLight`, each `{r, g, b, a}`). [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:165-175)
- Style classes referenced: `font-scale-title-1` to `font-scale-title-4`, `font-scale-body`, `secondary`, `primary`, `success`, `warning`, `error`, `info`, `negative`; nine-patch values `{0, 16, 48, 64}`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:900-1230)
- The line tool lets a company pick only stations it owns or that are unowned (`isOwnedByPlayerOrNotOwned`). [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:433-444)
- The main-menu and pause-menu UI run in their own Lua state where mods are not loaded; the author reaches them only through a native module (not described here). [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_pause.lua:1-15)
- The UI state's `api.engine` table is writable (so a function can be wrapped there) whereas `api.cmd` is userdata that takes no new members. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:42-60)

### 5.2 Mod packaging

Our own mod: `mod/tf3_companion_bridge/` has `mod.json`, `_content.json`, `_metadata/` and `content/tf3_companion/` with `bridge.gs.lua` and `bridge.script.lua` (listing checked, 2026-10-18). Format facts of MPFever's package, for comparison:

- `mod.json` keys: `dependencies`, `incompatibilities`, `modId`, `options`, `params`, `postRunScript`, `preRunScript`, `runScript` (each `{ fileName }`), `revision`, `severityAdd`, `severityRemove` (strings). [ADOPTED: code] (MPF:mod/mpfever_1/mod.json:1-18)
- `_content.json` is `{ archives: null, files: [...] }`, listing each shipped file by name; files live under `content/` and include `.gs.lua`, `.script.lua`, plain `.lua`, `.res.lua`, `.con.lua` and `.tga`. [ADOPTED: code] (MPF:mod/mpfever_1/_content.json:1-19)
- `_metadata/modinfo.json` keys: `authors` (list of `{name, role}`), `description`, `name`, `summary`, `tags`, `url`; `_metadata/0.png` is the thumbnail. [ADOPTED: code] (MPF:mod/mpfever_1/_metadata/modinfo.json:1-8)
- `texture_metadata_cache.lua`: `data()` returns, per texture file, `channels`, `extent` (`w`, `h`), `numMipmaps`, `numStrippedMipmaps`; the game generates it. [ADOPTED: code] (MPF:mod/mpfever_1/texture_metadata_cache.lua:1-10)
- Resource references: mod resources are `"<modId>::/<relative path>"`, game assets `"::/..."`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_entry.res.lua:6)
- Game-script resource (`.gs.lua`): `data()` returns `updateScript`, `handleEventScript`, `guiUpdateScript`, `guiHandleEventScript`, each `{ fileName = "<file>@<function>" }`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever.gs.lua:1-16)
- Construction template (`.con.lua`): `data()` fields `description` (`name`, `description`, `icon`), `params`, `order`, `skipCollision`, `updateScript` (`fileName`, `params`), `availability` (`yearFrom`, `yearTo`; 0, 0 means always); the update function returns `subconstructions` with `models` (`id`, 16-number `transf`) and `terrainAlignmentLists`. A construction needs `params.seed`. Built-in marker models start with `::/`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_asset.con.lua:1-22)
- Source files avoid the backslash character on purpose; paths are built with `string.char(92)`. The reason is not given. [ADOPTED: claim] (MPF:mod/mpfever_1/content/mpfever_common.lua:1-10)
- The savegame records its mod list (`info.mods`); loading with a different mod list is a supported operation of the load screen. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_auto.lua:61-84)
- The application script can be started from the executable's command line with `--script <modId>::/<file>`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_auto.lua:1-3)
- The mod's language reaches Lua through an environment variable and a text file written by its launcher; the author's code calls no Lua API for the game language, so none is known to exist. [ADOPTED: claim] (MPF:tests/test_lang.py:1-30)

### 5.3 Environment access

- `os.getenv` works in the game's Lua states (game scripts and UI), so environment variables are readable from mod Lua. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_common.lua:17-26)
- `io` is not a global; the author reaches it as `package.loaded["io"]` through `pcall`; the UI state may lack `debug` and `rawget`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_common.lua:12-15)
- `load(chunk, name, "t", env)` with an empty environment works (Lua 5.2 four-argument form). [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_common.lua:125-137)
- Runtime facts (Lua 5.2, hash seed, sandbox) are in `engine`; our collector writes only through `app.saveUserdata`.

### 5.4 Resource-name forms

- Construction names resolve in several forms; the author tried `mod::/file.con`, `file.con`, `::/file.con`, `/file.con` and `mod::file.con`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:4334-4345)
- A bus-stop model path `stations/street/small_stops/small_old.con` was used with and without the `::/` prefix; both are assumed to resolve. [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7341)
- Street-template paths seen: `town_old_small`, `town_new_medium`, `town_new_large`, `tram_old`, `highway_new_small_*`; edges built by a construction's own script carry `/constructions/` in `roadTemplate`, and entrance, rail-station, airport and rail-depot tracks use dedicated template paths. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:2924-2932)

## 6. Mocked-engine shapes (the author's test harness)

The author's tests run the real mod Lua against a mock of the API. These are the author's simplifications of the real API, useful as an index of what the author believes it looks like. [ADOPTED: assumed] (MPF:tests/test_lockstep.py:80-154)

- Root layout: `api.cmd` (`sendCommand(cmd, cb, progress)`, `debug.makeGamePerformSimulationStepsCmd`, `make*Cmd`), `api.type` (`ComponentType`, `Vec2f/3f/4f.new`, `Mat4f.new` of four `Vec4f`, `Context.new`, `SimpleProposal.new` with `.ConstructionEntity`, `NodeAndEntity`, `SegmentAndEntity`, `BaseNode`, `BaseEdge`, `BaseEdgeStreet`, `TransportVehicleConfig`, `TransportVehiclePart`, `VehiclePart`, `LoadConfig`, `Line` with `.Stop` and `.StopConfig`, `StationTerminal`), `api.engine` (`getComponent`, `entityExists`, `util.getWorld`, `util.getPlayer`, `forEachEntityWithComponent`, `getEntitiesWithComponent`, systems `streetConnectorSystem` (`getConstructionEntityForDepot`, `getConstructionEntityForStation`), `stationGroupSystem.getStationGroup`, `lineSystem.getLines`, `streetSystem.getEdgeForEdgeObject`), and globals `debugPrint`, `toString`, `getBuildVersion` (returns the text `"test"` there). [ADOPTED: assumed] (MPF:tests/test_lockstep.py:80-154)
- Component shapes: `GAME_TIME` gives `{gameTime}`; `GAME_SPEED` gives `{speedup}`; `ACCOUNT` gives `{balance, loan}`; `CONSTRUCTION` has `fileName`, `transf` (13, 14, 15 are the position), `depots`, `stations`; `BASE_NODE` has `position {x, y, z}`; `TOWN` has `sizeFactors` (array). [ADOPTED: assumed] (MPF:tests/test_lockstep.py:25-31)
- `ComponentType` numbers in the mock (1 to 15) are arbitrary; only the names are real. [ADOPTED: assumed] (MPF:tests/test_lockstep.py:80-82)
- Engine behaviours embedded in the mock (the author's lessons): callbacks are forbidden inside the simulation update (the author saw this trap in the game); a command is applied at the next step for the GUI queue; vehicles bought inside `update` appear at the next step ("seems to"); the engine announces pre- and post-build events. [ADOPTED: observed] (MPF:tests/test_lockstep.py:42-68)
- Mock clock: start `gameTime = 18600` and `+200` per simulation step; the step size is copied from the author's notes (see `engine`). [ADOPTED: assumed] (MPF:tests/test_lockstep.py:20-24)
- Mock id allocation: the second game allocates ids 1000 higher, a bought vehicle gets different ids in the two games, and the test asserts they differ. [ADOPTED: observed] (MPF:tests/test_lockstep.py:1-12)
- Handler shapes in the mock: `MOD.handleEvent(src, state, id, name, param)` with `state:get()`, `state:set(v)`, `state:subscribeToAllEvents()`; `MOD.update(src, state, dt)`; `MOD.guiUpdate(src, state, gstate)`. [ADOPTED: assumed] (MPF:tests/test_lockstep.py:157-169)
- Command callback in the mock receives `data.resultVehicleEntity` for a purchase and `entities` as pairs such as `{ {entityId, 1} }`. [ADOPTED: assumed] (MPF:tests/test_lockstep.py:119-123)
- The mock gives only the names the author's mod reads; absence of a name there says nothing about the real API.

## 7. Unresolved argument, unit and shape questions

Each item names the check that would settle it.

- Resolved (task 8.2): `GAME_TIME` has `gameTime`, `gameTime0`, `dates`, `timeOfDaySec`, `tickCount` and `updateCount` (`TEAL:engine.d.tl:425-439`); our `meta.gameTime` is `gameTime`, the current ingame time. [UNVERIFIED] Its relation to the number of simulation steps (200 per step is the author's figure). Check: compare two consecutive snapshots' `meta.gameTime`.
- Resolved (task 8.2): `GAME_SPEED.speedup` is a non-negative integer multiplier and 0 means paused (`TEAL:engine.d.tl:415-422`); the interface can throttle it below the chosen speed (see section 3.4).
- Partly resolved (task 8.2): the industry script multiplies `dt` by 1000 before relating it to the year duration (`GM:industries/industries.script.tl:55,128`), which reads `dt` as seconds and the year duration as milliseconds [INFERENCE]. [UNVERIFIED] The step size in seconds. Check: log `dt` and `gameTime` deltas in a throwaway script.
- Resolved (task 8.2): `getBuildVersion` is a global declared by the definitions and returns a string (`TEAL:util.d.tl:206`, `TEAL:main.d.tl:39`); the executable of the macOS Steam copy carries the label 40420 and no 40408 (see `engine`). [UNVERIFIED] The value returned at run time on a given install. Check: compare `meta.buildVersion` in a snapshot with the label.
- Resolved (task 8.2): the fourth argument of `finance.calculateBalance` is `maintenanceIncomeOnly` (`TEAL:engine/util.d.tl:842-848`); the second argument of `line.getLineCapacityUsages` is `allCapacities` ("all capacities or those of the vehicles' current load config", `TEAL:engine/util.d.tl:194-198`); the second argument of `line.getLineIssues` and `line.getLinesIssues` is `allIssues` (`TEAL:engine/util.d.tl:239-248`); the third and fourth arguments of `getTownDeliveriesStats` are `perLine` and `perCargoType`, and the second argument of `getTownHappinessStats` is `numTopLines` (`TEAL:engine/util.d.tl:630-641`).
- Resolved (task 8.2): `getTown2personCapacitiesMap` entries are arrays of three capacities in the order residential, commercial, industrial (`TEAL:engine/system.d.tl:121-125`); the author's `[1]` is the residential capacity, and the existing `list_towns` population sums all three.
- Resolved (task 8.2): the definitions give `getVehicle2Cargo2SimEntitesMap` as `{Engine.Entity : {CargoTypeId : {Engine.Entity}}}` and `getStock2SimEntityMap` as `{{Engine.Entity, StockId} : {Engine.Entity}}` (`TEAL:engine/system.d.tl:162-164,203-206`); the choice against the `getStockCount` route we use is ours.
- Partly resolved (task 8.2): `JournalEntry.Type` has `LOAN`, `INTEREST`, `CONSTRUCTION`, `ACQUISITION`, `MAINTENANCE`, `INCOME`, `OTHER` and `SUBSIDY` (`SCR:journal.d.tl:4-15`); the game's loan postings use `time = -1` (`GM:finance/loan.script.tl:94-98`). [UNVERIFIED] The meaning of `time = -1`.
- [UNVERIFIED] Whether a demolition `costs` value is negative for refunds, and the refund window; see `engine` and `mechanics.md` (M16).
- [UNVERIFIED] Unit of `MOVE_PATH.dyn.speed` (presumably metres per second), the `TRANSPORT_VEHICLE.state` enumeration beyond our `VEHICLE_STATES` table (`bridge.script.lua:26`), and the unit of waiting times (the author writes 21, 33 and 60 without a unit). Check: `TEAL:` comments; compare against observed `maxWaitingTime`.
- Resolved (task 8.2): `BASE_EDGE.type` is a `BaseEdgeType` with members `NORMAL`, `BRIDGE`, `TUNNEL` (`TEAL:type.d.tl:461-466`), so the author's reading "0 ground, 1 bridge, 2 tunnel" matches and the other comment, "0 street, 1 track, 2 tunnel" [DISCREPANCY] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7060), does not; the definitions name the members without numbers, so the numbering by declaration order is [INFERENCE].
- Resolved (task 8.2): `BASE_EDGE.objects` entries pair an edge-object entity with an `EdgeObjectType` whose members are `STOP_LEFT`, `STOP_RIGHT` and `SIGNAL` (`TEAL:engine.d.tl:99-110`, `TEAL:type.d.tl:420-428`); the numeric codes 0, 1, 2 are [INFERENCE] from declaration order.
- [UNVERIFIED] `LaneConfig.transportModes` index base (zero-based or one-based) and the `TransportMode` order; reads start at index 0 while writes may be shifted by one (measured once, build not stated). Check: `TEAL:` enumeration.
- [UNVERIFIED] Which components a player entity carries (`PLAYER`, `ACCOUNT`, `NAME`, `PLAYER_OWNED` were probed, results not published). Check: dump each type for the player entity.
- [UNVERIFIED] Whether `PLAYER_OWNED` exists on stations, station groups, lines and industries, and whether `ACCOUNT` truly exists on constructions, lines and vehicles. Check: probe each type on one entity.
- Partly resolved (task 8.2): `MAINTENANCE_COST` has the fields `maintenanceCost` and `accumulatedCost` (`TEAL:engine.d.tl:606-612`). [UNVERIFIED] Its holders. Check: dump on one construction, one vehicle and one edge.
- Resolved (task 8.2): the loan game script's state is one `LoanTable` (`availableLoans`, `obtainedLoans`, `freeId`), the game keeps no per-player loans, and the obtain event carries the offer taken and the loan as configured by the player (`GM:finance/loan.script.tl:4-24,119-135`).
- [UNVERIFIED] Contract fields (`proposedSubventions[i]`, `activeSubventions[i]`, `completedSubventions[i]`) beyond `id` and `uid`, `notification.type` values and `params` per type, and the `OnCalcTicketPrice` parameter shape beyond `lineEntity`. Check: dump the subventions and notifications script states.
- Resolved (task 8.2): the game's field is `potentialLevel` (`potential` is MPFever's name), `cachedRatings[key].value` and `authorityScore` are clamped to 0..1, the six rating keys map to the Reputation, Traffic, Happiness, Delivery, Noise and Pollution ratings, and a permit entry has only `numBuilt` (`GM:company/company_growth.script.tl:9-27`, `GM:towns/town_util.tl:643-716,754-784`, `GM:company/company_util.d.tl:29-35`).
- Resolved (task 8.2): the per-town sensitivity override is stored under any key string by the `setTownRatingSensitivity` event, and the rating code looks up the six keys `urban_care`, `traffic_congestion`, `people_happiness`, `cargo_delivery`, `noise` and `pollution` (`GM:towns/towns.script.tl:356-373`, `GM:towns/town_util.tl:20-35,82-91`).
- [UNVERIFIED] Whether the `io` library reachable as `package.loaded.io` works in our collector's state and which file locations it permits; our bridge does not use it. Check: a throwaway guiUpdate script.
- [UNVERIFIED] Whether `format("%d")` limits affect our `%015d` snapshot name (`bridge.script.lua:789`) and `%d` log fields (`bridge.script.lua:790`): the author reports 32-bit-only `%d` in Lua 5.2 on Windows (issue 30). Check: compare the largest stored `meta.gameTime` with 2^31.
- [UNVERIFIED] Whether `getEntityForGameScript` and `GAME_SCRIPT.state` can be read from the GUI half where our collector runs (the author reads both from simulation-side Lua and the UI state). Check: a throwaway guiUpdate script under `pcall`.
- [UNVERIFIED] Whether the full `api.type.ComponentType` list matches the author's census (names probed, not proven). Check: `TEAL:` enumeration or a `__members` dump.
- [UNVERIFIED] `roadTemplate` conventions for infrastructure belonging to a construction (`/constructions/`, rail-station and airport track templates, rail-depot templates). Check: list the distinct `roadTemplate` values of a test save.
- Partly resolved (task 8.2): the game's own call passes the `.gs` resource name in the form `::game_mechanics/company/company_progression.gs` (`GM:company/company_progression_util.tl:78`). [UNVERIFIED] Whether the leading-slash form is accepted too. Check: try both forms on the loan script.
