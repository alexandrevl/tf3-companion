# Transport Fever 3 mechanics relevant to profit

Source conventions (all paths relative to `Transport Fever 3/`):
- **WIKI:x** = `https://wiki.transportfever3.com/doku.php?id=gamemanual:x` (official manual). Pages marked "old revision" on the site are flagged.
- **GM:** = `base/content/game_mechanics.zip:game_mechanics/`
- **ECO:** = `base/content/economy.zip:economy/`
- **SCR:** = `base/content/scripts.zip:scripts/`
- **BASE:** = `base/content/base.zip:base/`
- **TEAL:** = `api/tealdef/api/` (type definitions with comments)
- Items without a direct source are marked `[INFERENCE]` or `[UNVERIFIED]`.
- No TF1/TF2 facts have been used as established truth.

Cross-references: `estrategia.md` (translated as `strategy.md`) cites the sections below by ID (M1…M12). References to `economia_cargas.md` correspond to the English `cargo_economy.md` topic.

---

## M1 — Passenger and cargo income

**Formula (from the game's Lua script, paraphrased):**
- Distance is the 3D Euclidean positional difference, plus eight times any positive elevation difference.
  - Source: `ECO:cargo_income.script.lua` (`calcTravelDistance`).
  - A positive Δz increases distance by 8 m per metre of ascent. [UNVERIFIED] whether `posDifference` means destination minus origin; if so, uphill deliveries pay more.
- Cargo income is the product of `incomeFactor`, `difficultyFactor` and distance (`calcCargoIncomeFn`).
- Passenger income uses the same product, multiplied by 0.5 plus `vehiclePriceFactor`; its default is 0.5, giving a multiplier of 1.0 (`calcPassengerIncomeFn`).
  - None of the inspected vehicle `.mdl` files (bus, train, tram, plane, ship, helicopter, car) defines `priceFactor`; therefore the default 0.5 (×1.0) applies. [UNVERIFIED] whether a mod/campaign vehicle defines another value.

**incomeFactor (`ECO:cargotype.script.lua`):**
- All 36 freight cargo types in `base/content/cargos/*.zip:*/*.cargo.lua` (37 files minus passengers) use `incomeFactors.constantFn` with an `initialPrice` of 4 and a `finalPrice` of 3.2.
  - `constantFn` adds one quarter of the difference between final and initial prices to the initial price, giving 3.8.
  - ⇒ **Every freight cargo type pays the same per item and per metre: 3.8.** The `decayRate/decayMod/decayStart` parameters exist in the files but are only used by `logisticDecayFn`, which no base cargo uses.
- Passengers: `passengersFn` multiplies 62.5 × 0.001 × 35 × 1.5 × 1.1, giving 3.609375 (`ECO:cargotype.script.lua`).
- Monetary unit/final scale of the result: [UNVERIFIED].

**Difficulty and inflation multipliers:**
- `difficultyFactor` comes from `advancedOptions.cargoIncome` / `passengerIncome`, with possible values {0.5; 0.75; 1.0; 1.25; 1.5} (default 1.0).
  - Source: `BASE:difficulty_util.tl` (`level2CargoIncomeFactor`), `BASE:mod.script.tl:207-219`, `base/mod.json`.
- **Inflation:** ticket/cargo price is multiplied by 1 + (rank−1) × (M−1)/14, where M is the game's "Inflation" setting.
  - M ∈ {1 (None); 0.9; 0.75 (Normal, default); 0.6; 0.5}, with maximum rank 15.
  - At the default setting, income per item falls linearly to ×0.75 at rank 15.
  - Sources: `GM:company/company_progression_util.tl` (`getTicketPriceMultiplierForLevel`), `GM:company/company_growth.script.tl` (`OnCalcTicketPrice`), `BASE:difficulty_util.tl` (`level2InflationFactor`).
  - The effect is adjusted by the `OnCalcTicketPrice` event (multiplier `[0]` = all cargo types).
- A fulfilled subsidy can grant temporary "2x income" on eligible lines (WIKI:management:subsidies).

**Effect of speed/time on income:**
- WIKI:gettingstarted:tipstricks says "the faster, the higher the income" and that distance is measured in a straight line between origin and final destination.
- The income Lua script **has no time term**; any speed effect would be in the native engine (`OnCalcTicketPrice` event). [UNVERIFIED in code]
- WIKI:management:companyandfinances: cargo delivered **late still pays full income**, but lowers the town's "Delivery" rating (see M2/M12).

---

## M2 — Town growth

**Levels and XP** (`GM:towns/town_growth.script.tl`, `GM:towns/town_cargo_util.tl`, WIKI:simulation:towns):
- 18 levels (Small Hamlet … Large Metropolis).
- Level 2 at 1,000 XP; each following level costs 1.5× the previous one (`townExpScaling` is 1.5, `expBaseTownLevel` is 1000 according to the wiki; the `.res` value has not been read).
- Cumulative XP to reach level L = 2000 × (1.5^(L−1) − 1):

| Level | Cumulative XP | Capacity multiplier `F` |
|---|---|---|
| 2 | 1,000 | 1.46 |
| 3 | 2,500 | 1.86 |
| 4 | 4,750 | 2.28 |
| 5 | 8,125 | 2.75 |
| 6 | 13,187 | 3.35 |
| 7 | 20,781 | 4.11 |
| 8 | 32,171 | 5.11 |
| 9 | 49,257 | 6.39 |
| 10 | 74,886 | 8.01 |
| 11 | 113,330 | 10.03 |
| 12 | 170,995 | 12.51 |
| 13 | 257,492 | 15.49 |
| 14 | 387,239 | 19.04 |
| 15 | 581,858 | 23.20 |
| 16 | 873,787 | 28.05 |
| 17 | 1,311,681 | 33.62 |
| 18 | 1,968,522 | 39.98 |

- F is the cubic polynomial 0.00930472 l³ − 0.08061382 l² + 0.63330472 l + 0.438, with F(1)=1 and F(18)=40.
  - Source: `SCR:util/town_growth_function.tl` (`getGrowthFactor`).
  - l = current level + 1 − initial level + fraction, so the multiplier is **relative to the level at which the town started** (`GM:towns/town_cargo_util.tl:getGrowthFactor`).
- Target capacity is initial capacity multiplied by F(l) (`GM:towns/town_growth.script.tl`).
- Towns that start large begin at levels 2–4 according to initial residential capacity (>100/150/200) (`town_cargo_util.ensureState`).

**Sources of raw XP** (`town_growth.script.tl`; values 5/10/20 and 10/20/40 from WIKI:simulation:towns; XP = base × 2^tier):
- Passenger reaching a destination by **line**: 5 XP (same town, tier 0), 10 XP (neighbouring town, tier 1), 20 XP (more distant town, tier 2).
  - Walking/car trips do not count (the `lastMoveMode` check requires `LINES`).
- Cargo item delivered to a town building: 10 / 20 / 40 XP according to cargo tier (tier 0/1/2; see `economia_cargas.md`).
- **Final XP = raw XP × authority multiplier** (below); headquarters grant an extra bonus starting at 5% (WIKI:simulation:towns).
- Automatic growth per tick is zero (`growthPerTick` in `town_cargo_util.tl`), so growth only comes from transport.

**XP multiplier (authority × supply)** (`GM:towns/town_util.tl:calculateGrowthLevelMult`, `town_cargo_util.authority2xpFactor`):
- Levels 0–5 = Very Poor, Poor, Mediocre, Good, Very Good, Excellent → XP ×0; 0.2; 0.4; 0.6; 0.8; 1.0.
- **Authority** = the lowest of six ratings: Reputation, Happiness, Delivery (on time), Traffic, Noise, Pollution (WIKI:simulation:towns; `calcAuthorityScore` takes the minimum of non-additive ratings).
- **Supply** = rounded average of **passenger** and **cargo** ratings. `noDeliveries` sets it to zero.
  - Passengers: double line usage, clamped to 0–1; therefore 50% of the population using lines = maximum.
  - Cargo: the **highest** supply/demand ratio among districts (`getRatingDeliveriesCargo` takes the maximum).
- Resulting mapping (rows = authority level 0–5, columns = supply level 0–5, value = XP factor):

| authority\supply | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1 | 0 | 0.2 | 0.2 | 0.2 | 0.4 | 0.4 |
| 2 | 0.2 | 0.2 | 0.4 | 0.4 | 0.6 | 0.6 |
| 3 | 0.2 | 0.4 | 0.6 | 0.6 | 0.8 | 0.8 |
| 4 | 0.2 | 0.4 | 0.6 | 0.8 | 0.8 | 1.0 |
| 5 | 0.4 | 0.6 | 0.8 | 0.8 | 1.0 | 1.0 |

  (Calculated from the code: `growthLevel` is (authority/5) × ((supply+1)/6), compared against cumulative thresholds with weights 1.4^i: 0.061; 0.147; 0.267; 0.435; 0.670; 1.0.)
- Individual ratings (`town_util.tl`):
  - **Delivery:** fraction of items delivered on time in the last half-year; minimum denominator of 10 items.
  - **Happiness:** 1 − unhappy/total (minimum 15 people), rescaled by sensitivity.
  - **Traffic:** road traffic speed.
  - **Reputation:** landscaping, removing trees/buildings and breaking major connections lower it; celebrations and marketing campaigns raise it (WIKI:simulation:towns).
- Sensitivities (game options, 0 = disabled, default "Normal" = 1) in `base/mod.json` and `BASE:difficulty_util.tl`.

**How the town uses capacity gains** (`town_growth.script.tl`):
- New capacity is divided among residential/commercial/industrial districts **in proportion to usage**:
  - residential: average of line usage×2 and residential supply/demand ratio;
  - commercial/industrial: cargo supply/demand ratio.
- Limits: minimum weight `townGrowthMinDistrictFraction` (value unread); district ≤50% of town (dampened starting at 40%) and ≤40% of map (starting at 32%).
- Source: `town_growth.script.tl` (constants `MaxTownDistrictFraction*`, `MaxMapDistrictFraction*`).

**Cargo demands by level** (`ECO:placementparamsutil.lua:getDefaultTownLevels2CargoInfos`; WIKI:simulation:towns):
- Initially: one commercial (tier ≤1) + one industrial (tier 0–1).
- Level 5: +1 commercial (tier 0–1). Level 7: +1 industrial (tier 0–1). Level 9: +1 commercial (tier 0–2). Level 11: +1 industrial (tier 0–2).
- **New demands are only added if the town has already received some cargo** (`townState.cargoDelivered`, `town_growth.script.tl`).
- The new cargo type is the highest-weight candidate: tier within range gives weight 1, outside gives 0.01, multiplied by the imbalance between towns (`pickBiggest`).
- Maximum demands per town: "Town Cargo Demands" option = 2/4/6 (`base/mod.json`, `BASE:difficulty_util.tl`).
- Fish only becomes a demand if Fish production exists on the map (`isCargoAvailable`).
- Annual quantity demanded is lower for complex cargo types (`townConsumptionFactor`; table in `economia_cargas.md`).

---

## M3 — Industries: production, levels, boosters

**Structure** (`base/content/industries/<x>.zip:<x>/<x>.con.lua`, `industries/industryutil.lua`; details in `economia_cargas.md`):
- Production rules ("rules") with input → output and a **duration** (`capacity`). The duration unit is undocumented. [UNVERIFIED]
- Primary industries (mines, farms, etc.) produce without inputs.
- **Production level = number of "plots"** (fields, wells, galleries). Rule output is scaled by level / maximum level (`industryutil.lua:adjustStocklistRule`); the wiki gives output ranges (e.g. Coal "1–16").
- **Expansion:** well-served industries add plots. Blocked or demolished plots limit/reduce production (WIKI:simulation:industriescargos).
- Expansion check (`GM:industries/industries.script.tl`):
  - Rating multiplies `productionRating` by the annual shipped/produced ratio, capped at 1.
  - Probability is (rating − 0.25)/(0.75 − 0.25), clamped to 0–1.
  - Rating ≤0.25 never expands; ≥0.75 expands whenever checked.
  - Checked every `extendTimeSpan` (360000 ms = 180 game days according to `BASE:mod.script.tl:170`; the script uses `industriesConfig.extendTimeSpanYears`, whose value has not been read).
  - Only up to `maxLevel`.
- Full output stock: production continues; **excess items are destroyed** (WIKI:simulation:industriescargos; `itemsDestroyed` log).

**Productivity:**
- `defaultIndustryProductivity` is 0.58 in the temperate economy (`ECO:temperate.eco.lua`); "Industry Productivity" option ∈ {50, 75, 100, 150, 200%} (`base/mod.json`, `BASE:difficulty_util.tl`).
- Exact effect of 0.58 on production: [UNVERIFIED].

**Worker booster** (`base/content/industries/industry_productivity_util.tl`, `industry_workers.script.tl`; WIKI:simulation:industriescargos):
- All industries have a capacity for 20 people (`industrialCapacity` is 20 in all 32 `.con.lua` files).
- Booster activates when the number of visitors **arriving by line** ≥50% of capacity, i.e. ≥10 people. Tracks at most 20 visitors over a two-game-year window.
- When active, `productivity` becomes the industry's "boost potential": randomly drawn from **1.5–2.5** (default 2 without a seed). Falls to 1.0 if workers are lacking.
- The "Transport Workers" subsidy exists for this (WIKI:management:subsidies).

**Cargo booster** (primary industries only; `.con.lua` rule flagged by `booster`):
- Consumes Tools, Machines or Fertilizer from input stock (type and amount: `economia_cargas.md`).
- Industry factor: `boostFactor` randomly drawn from 0.5–1.5 (rounded to 0.01) at creation (`industryutil.lua:399-403`); production multiplied by 1 plus `boostFactor` (`base/content/gui.zip:gui/main/industry_util.tl`).
- Stops when the input runs out (WIKI:simulation:industriescargos).
- Whether the two boosters multiply: [UNVERIFIED].

**Input dependency:** secondary industries only produce with inputs in their input stocks; the ratio is fixed by the rule (e.g. Steel Mill 6 Iron Ore + 6 Coal).

---

## M4 — Industry spawning and closure

- New industries spawn when demand rises sufficiently or a new cargo type is demanded for the first time (WIKI:simulation:industriescargos). `spawnTargetTimeSpan` is 50 years and `spawnProbabilityExponent` is 3 (`BASE:mod.script.tl:166-167`).
- **Closure** (`GM:industries/industries.script.tl`, WIKI:simulation:industriescargos):
  - Only if "Industry Closing Frequency" is not Never; not owned by the player; has output (`hasOutput`); has no depot.
  - Eligible if **nothing was consumed (`itemsConsumed`) or loaded (`itemsLoaded`)** during `unusedTimeSpanYears`.
    - The wiki says **10 years**; `BASE:mod.script.tl:171` defines five years for `unusedTimeSpan`. The effective value (`industries_config.res`) has not been read. [DISCREPANCY]
  - Random draw: closure probability = 0.011 × factor per industry per year (`closureProbability`), with option factor ∈ {0 (Never), 1 (Rarely, default), 2, 4, 8}.
  - After the draw, a **730-day** countdown (`closureCountdownTimeSpan` is two years). If production/consumption/loading resumes during the countdown, closure is cancelled.
  - An "Industry Closing" notification appears.

---

## M5 — Catchment areas

- Cargo: the building/industry only needs to be **within the station's radius**. Passengers: also require a valid path without large detours (WIKI:infrastructure:stationsdepots#catchment_area).
- Radii (m) extracted from modules (`base/content/stations/*.zip`, `*.module.lua`/`*.con.lua` files):

| Construction | Radius |
|---|---|
| Small street stop (`small_*.con.lua`; passenger + cargo) | 160 |
| Modular road station: entrance/exit | 175 |
| Underground station | 200 |
| Railway, passenger main building 1 / 2 (era b) / 3 (era b) | 150 / 175 / 200 |
| Railway, passenger side buildings | 50–70 |
| Railway, stairs | 100 |
| Railway, cargo main building 1 / 2 / 3 | 150 / 175 / 200 |
| Railway, cargo side buildings | 60–70 |
| Passenger docks (docks 25/50/100) | 150 / 250 / 250 |
| Airfield: main building (passenger and cargo) | 250 |
| Heliport / helipad (catchment) | 175 / 100 |

- Hangars/heliports have depot `catchmentArea` values of 550/800 m — [INFERENCE]: this is the maintenance radius (WIKI says depots have a "small maintenance radius").
- Multiple entrance buildings on different sides extend catchment (WIKI:infrastructure:stationsdepots, Rail).
- Station far from the centre: connect to town with a bus/tram/truck line to extend reach (WIKI:gettingstarted:tipstricks).
- An industry's entire station specializes in the cargo the industry needs (WIKI:management:linesvehicles).
- Overcrowded stations (waiting passengers) make passengers unhappy and **hurt growth** (WIKI:infrastructure:stationsdepots#station_capacity).

---

## M6 — Vehicles: maintenance, ageing, lifespan

- **`maintenanceState`** per vehicle part (`transportVehicleConfig.vehicles[i].maintenanceState`, `TEAL:type.d.tl:1526`):
  - Range [0,1]; 1 = perfect condition. UI uses the **average of the parts** (`base/content/gui.zip`, extracted: `gui/line_vehicle_mgmt/vehicle_util.tl:getAvgMaintenanceState`).
  - UI bands round condition×5 upwards: ≤0.2 Very Poor; ≤0.4 Poor; ≤0.6 Mediocre; ≤0.8 Good; >0.8 Very Good.
  - `maintenanceChange` = current rate of change (also averaged across parts). Unit/scale: [UNVERIFIED].
- **Effect of ageing** ("Vehicle Maintenance Effect" option: None/Low/Medium/High/Very High = ×0/0.5/1/1.5/2, default Medium):
  - With neglected maintenance, **noise, pollution and running costs rise; speed, power and comfort fall** with age; "None" disables this (`base/mod.json`, `BASE:difficulty_util.tl`; `vehicleMaintenance{Emissions,Performance,RunningCosts}Effect` fields in `TEAL:type.d.tl:3476`).
  - `Maintenance` has a `topSpeedMaintenanceFactorPenaltyPerLevel` field (`TEAL:type.d.tl:3966`); per-vehicle value [UNVERIFIED].
- **Repair:** depots and maintenance workshops repair vehicles passing within their radius. Depots have a small radius; **maintenance buildings** (road, rail, water; none for planes) have larger radii but do not sell vehicles. Waypoints can route vehicles through them (WIKI:infrastructure:stationsdepots#depots_maintenance; WIKI:management:linesvehicles#waypoints).
- **Lifespan** (`maintenance.lifespan` in `.mdl` files in `base/content/vehicle/*/*.zip`, complete sample; probable unit **days**, since 36525 = 100×365.25 — [INFERENCE]):
  - bus 14,610–21,915 (40–60 years); truck 14,610–25,568; train 21,915–40,178; wagon 21,915–36,525; tram 21,915–36,525; ship 36,525 (100 years); plane 21,915–42,369; helicopter 36,525–43,830.
  - UI shows `agePercent` as elapsed time since purchase divided by lifespan; after `lifespan`, there is no "remaining time" (`vehicle_util.tl:getAge`). What happens beyond that: [UNVERIFIED].
- **Costs in finances** (`GM:finance/finances_util.tl`): "Running Costs Vehicles" and "Maintenance Vehicles" (`VEHICLE_MAINTENANCE`) are separate entries; also upkeep for Stations, Depots, Roads, Tracks, Warehouses. Scales: "Vehicle Maintenance" and "Infrastructure Upkeep" ∈ {50…150%} (`base/mod.json`).
- Values of −1 for `runningCosts` and `price` in the sampled `.mdl` files mean automatically calculated values. [INFERENCE]
- A "Vehicle Condition" notification fires when condition is very poor (`GM:notifications/types/vehiclecondition.script.tl`).
- Vehicle maintenance automatically follows calendar speed (WIKI:simulation:overview).

---

## M7 — Loans and interest

(`GM:finance/loan_util.tl`, `GM:finance/loan.script.tl`)
- Maximum **four simultaneous loans** (`maximalObtainableLoans` is 4); four offers (Small, Medium, Large, Extra Large), randomly generated, renewed every half-year or after a 4–8-month waiting period when taking one.
- Ranges (uniform draw in millions, × year coefficient; term; "percentage"):

| Type | Base amount (M) | Term (years) | `percentage` |
|---|---|---|---|
| Small | 5–10 | 1–5 | 3–5% |
| Medium | 15–25 | 3–8 | 5–8% |
| Large | 30–50 | 5–12 | 8–10% |
| Extra Large | 40–60 | 10–24 | 10–12% |

- Year coefficient = 0.4 × 6^((year−1900)/120), limited to [0.4; 2.4] (e.g. 1900→0.4; 1950→0.84; 1990→1.53; 2020→2.4).
- **Interest is fixed on the original principal:** monthly instalment = amount/months (principal) + percentage × amount/months (interest). Total interest = amount × percentage, **independent of term**.
  - Annual cost ≈ percentage / term in years of the original amount (e.g. 12% over 10 years ≈ 1.2%/year; 4% over one year = 4%/year).
  - Monthly interest **does not decrease** as principal is repaid (`getMonthlyLoanAndInterestWithErrors`).
- **Early repayment** (`Repay`): books only remaining principal; remaining-interest code is **commented out** ⇒ future interest stops being charged (`loan.script.tl`, `Repay` block).
- Instalments are monthly according to the game calendar (`getDefaultMonthDuration`).
  - WIKI:management:companyandfinances (marked "old revision") mentions a "monthly interest rate", "annual payment" and "15-day intervals". This **differs** from the inspected code; trust the code. [DISCREPANCY]
- The wiki recommends repayment as soon as possible and says the rate depends on difficulty (WIKI:management:companyandfinances); the code has no difficulty dependency, only year and random draws.

---

## M8 — Lines: loading modes, waiting, priority

(WIKI:management:linesvehicles)
- Line = list of stops and waypoints; vehicles move from stop to stop and return to the beginning. Circular lines are possible; the wiki says they rarely make sense for long-distance passengers.
- **Departure mode** per stop:
  - *Load if available*: loads what is available and departs;
  - *Full load (any)*: waits for one cargo type to be full;
  - *Full load (all)*: waits for everything to be full.
  - "any/all" only differ for trains and ships; other vehicles wait for a full load in both.
- **Cargo filter** per stop: any combination of types with a target loading percentage. Unloading is automatic where a consumer for the cargo exists (industry, configured warehouse).
- Configurable **additional waiting time** after loading/unloading distributes vehicles along the line; the simulation uses it to space them out.
- **Alternative terminals** increase station throughput (vehicles of the same line stop in parallel).
- **Loading speed:** a platform shorter than the train **reduces** loading/unloading; matching vehicle/terminal/warehouse specializations give a bonus, mismatches a penalty (WIKI:management:linesvehicles#loading_speed). Per-cargo `loadSpeedFactor`: 0.0625 for all freight cargo types and 1 for passengers (`base/content/cargos/*.zip`); exact meaning [UNVERIFIED].
- Trains and trams have configurable line priority (WIKI:management:linesvehicles).
- Trains: signals recommended when several lines share track (WIKI:infrastructure:railwaysignals).
- Line window: capacity, rate and frequency, items transported in the last year, balance (income versus costs). Individual vehicles also have balance charts (WIKI:management:linesvehicles).
- Vehicles without a schedule: must be assigned to a line after purchase; the originating depot must have a path to the first stop.

---

## M9 — Logbook `itemsTransported` and `calculateBalance`

- **Logbook** = `LOG_BOOK` component with named series (`TEAL:engine/util.d.tl:UtilLogbook`). `getLogValuePerYear` takes an entity and a name and returns the **difference over the last year**; also `getLogValueMostRecent/Oldest`, `getChart`.
- Names used by the game (searched in `game_mechanics.zip` and `gui.zip`):
  - `itemsTransported` on a **line**: total items/passengers over the last year (`gui/entity_window/line/line_eow.script.tl`; "Transported" in WIKI:management:linesvehicles).
  - `itemsTransported<cargoTypeId>` on the **company**: series per cargo type (`GM:finance/finances_assets.tl:336`, Assets tab).
  - `itemsTransported` between two entities (industry→industry, town↔town, per cargo): `getCargoLogPerYearForTarget` (`TEAL:engine/util.d.tl:101`).
  - Industries: `itemsConsumed`, `itemsProduced`, `itemsDestroyed` (discarded due to full stock), `itemsLoaded` (loaded; used for closure).
  - Stations/warehouses: `itemsLoaded`, `itemsUnloaded`.
  - Town: `itemsAtDestination<cargoTypeId>` (`GM:towns/town_util.tl:getItemsAtDestinationPerYear`); XP logs `experience_raw_<tier>_<source>` and `experience_gain_<tier>_<source>` (source ∈ passenger, cargo, subvention, tick, other).
  - World: `industry_closed_<tag>`.
- **`calculateBalance`** takes entities, start, end, `maintenanceIncomeOnly` and an optional maintenance type (`TEAL:engine/util.d.tl:848`): sums balances of entities **with accounts** over the interval. Enabling `maintenanceIncomeOnly` considers only maintenance/income entries.
  - UI enables this for lines (sum of the line's vehicles), vehicles and constructions (`gui.zip`: `line_react_util.tl`, `vehicle_eow`, `entity_window_util.tl`).
  - **[INFERENCE]** therefore, line/vehicle balance ≈ income − vehicle operation/maintenance costs, excluding investment (purchase) and infrastructure upkeep (which belongs to constructions).
- `calculateEarnings` takes a player and returns earnings since the start of the year; `getPlayersBalance` returns nil with infinite money (`TEAL:engine/util.d.tl`, `GM:finance/loan.script.tl`).

---

## M10 — Time and calendar

- Game day = **4 s** by default at 1× speed (WIKI:simulation:overview); `ECO:cargotype.script.lua` assumes a `millisPerDay` value of 2000 (discrepancy in the base time scale [UNVERIFIED]).
- Changing calendar speed only affects availability of vehicles/infrastructure; production, consumption and maintenance adjust automatically (WIKI:simulation:overview).

---

## M11 — Company progression

- Company rank (maximum 15) depends on **map population** (`GM:company/company_progression_util.tl`; WIKI:management:companyandfinances).
- Each rank unlocks perks: landmarks, prospecting (founds a new industry if the resource exists), marketing campaigns (reputation + public transport usage), industry "greenification", pollution-cleaning plants (WIKI:management:companyandfinances).
- Rank also reduces income through inflation (M1).
- `companyRankRequiredIndustries` (`ECO:*.eco.lua`): ranks 2 (Quarry), 3 (Steel/Iron Ore/Coal), 5 (Oil), 7 (Forest/Saw Mill), 10 (Chemical Plant), 13 (Furniture/Glass/Sand). Probably guarantees these industries exist upon reaching the rank. [INFERENCE]
- Game difficulty options change costs and income: vehicle purchases, maintenance, infrastructure (50–150%) and cargo/passenger income (50–150%) (`base/mod.json`).

---

## M12 — Maximum delivery time per cargo type

- Each cargo type has `timeToDeliverInSeconds` (table in `economia_cargas.md`, from `base/content/cargos/*.zip`). Delivery **after the deadline** does not reduce income, but counts as late in the "Delivery" rating (M2) (WIKI:management:companyandfinances#delivery_time).
- The company's "Delivery Time" tab shows the expected deadline per cargo type (new TF3 feature, same source).
- Values: from 900 (Meat) to 4500 (Iron Ore, Sand, Steel, Stone). Unit: seconds according to the field name; relationship to game days [UNVERIFIED].

---

## Sources and gaps

**Read directly:** `economy.zip` (income, categories, `*.eco.lua`), `scripts.zip` (`town_growth_function.tl`), `game_mechanics.zip` (towns, industries, finances, company), `industries/*.con.lua`, `cargos/*.cargo.lua`, `stations/*.zip`, vehicle `.mdl` files, `api/tealdef`, `base/mod.json`, wiki (simulation, management, infrastructure, gettingstarted).

**Unverified / gaps:**
- Speed/time term in income (native, `OnCalcTicketPrice`).
- Final monetary unit; value of `incomeFactor` per metre.
- `.res` values: `town_growth_config.res` (XP per item), `industries_config.res` (unused years, expansion interval), `town_ratings_sensitivity.res`, `company_growth_config.res`.
- Unit and effect of production-rule `duration`; effect of `defaultIndustryProductivity` at 0.58; whether cargo and worker boosters multiply.
- Degradation rate of `maintenanceState`, exact repair radius per depot/workshop type and what happens beyond `lifespan`.
- Actual `vehiclePriceFactor` per vehicle.
- Whether `posDifference` means destination minus origin (effect of elevation gain).
- Wiki × code discrepancies: monthly interest/15-day instalments (loans); unused years before closure (10 versus 5); Livestock Farm and Furniture Factory have boosters in the wiki without rules in `.con.lua` (see `economia_cargas.md`).
- Wiki pages marked "not yet adapted"/"old revision": `gamemanual:management:companyandfinances` and `gamemanual:gameplayfaqs` appear as "old revision"; FAQ is empty.
