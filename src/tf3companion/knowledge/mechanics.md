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

Cross-references: `strategy.md` cites these sections by ID (M1…M16); `cargo_economy.md` details cargo and industry chains.

> **Evidence legend (imported research).** `MPF:<file>` cites a file of MPFever (https://github.com/dkdknight/MPFever, MIT, studied at commit `ae5fc96`; paths relative to its repository root). `[ADOPTED: observed|code|assumed|claim]` marks a fact taken on the MPFever author's word and not verified by this project; the class is the author's own: observed = measured by the author, code = read by the author in game code or the engine, assumed = the author's assumption, claim = stated without evidence. Every statement is paraphrased. `[INFERENCE]`, `[UNVERIFIED]` and `[DISCREPANCY]` keep their existing meaning.

## Time units used by the companion

`GAME-YEAR` means 365.25 elapsed days of the exported Gregorian game calendar.
For example, 1979-12-31 to 1980-01-01 is `1 / 365.25` GAME-YEAR; 1980-02-28 to
1980-03-01 is `2 / 365.25`. Calendar-year report grouping still uses the exported year.
`game-calendar-v1` maps purchase ticks only at exact dated anchors or by interpolation
inside an enclosing dated span of at least seven days; no extrapolation or nominal fallback.
Such interpolations are estimates, not exact historical purchase dates or verified engine calibration.
Missing/out-of-range dates and ambiguous timelines stay unknown. Legacy history does not prove save isolation.
Nominal `meta.yearDuration` remains the collector's financial query duration in raw ticks;
rolling `profitYear` observations are neither rescaled nor summed across overlapping snapshots.
Wall-clock freshness is separate. Model lifespan and raw depot/terminal day-counter units
remain independently unverified; calendar age does not justify an age/lifespan ratio.


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
- Cargo item delivered to a town building: 10 / 20 / 40 XP according to cargo tier (tier 0/1/2; see `cargo_economy.md`).
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
  - See also M13 (exact happiness and on-time formulas, rating and sensitivity keys, statistics calls).
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
- Annual quantity demanded is lower for complex cargo types (`townConsumptionFactor`; table in `cargo_economy.md`).

---

## M3 — Industries: production, levels, boosters

**Structure** (`base/content/industries/<x>.zip:<x>/<x>.con.lua`, `industries/industryutil.lua`; details in `cargo_economy.md`):
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
- Consumes Tools, Machines or Fertilizer from input stock (type and amount: `cargo_economy.md`).
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
- See also M15 (loan state fields, schedule); its payback paragraph read `loan_util.tl` together with `loan.script.tl` and confirms the early-repayment rule above.

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
- See also M16 (day-length evidence) and `engine` E1 (clock). [DISCREPANCY] An empty station group expires 20 game days after its last stop is removed, seen as about 80 s at 1x, i.e. 4 s per day, matching this section and not the 2000 ms value assumed in `ECO:cargotype.script.lua`; the author states the 4000 ms day as his assumption. [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:114-116) The game scripts read for task 8.2 (build 40420) settle neither number: the 2000 is a local constant of the economy script, used only to turn milliseconds into days inside its price curves (`ECO:cargotype.script.lua:3-47`). Every other script takes day, month and year from `api.util.getDefaultDayDuration`, `getDefaultMonthDuration` and `getDefaultYearDuration` ("game ticks", values not visible in scripts) and from the live `GAME_SPEED.millisPerDay`; the calendar-speed factor shown in the game bar is `getDefaultDayDuration() / millisPerDay` and the offered factors are 0, 0.25, 0.5, 1, 2 and 4 (`TEAL:util.d.tl:100-120`, `TEAL:engine.d.tl:415-422`, `gui/game_bar/game_bar_widgets.tl:321-351` in `gui.zip`). The 2000 ms value stays [UNVERIFIED] as a configuration value. [INFERENCE] A default month is about 30 default days, from the contract scripts' `getDefaultDayDuration() * (30 * months ± 30)` (`GM:subventions/subvention_util.tl:290`).

---

## M11 — Company progression

- Company rank (maximum 15) depends on **map population** (`GM:company/company_progression_util.tl`; WIKI:management:companyandfinances).
- Each rank unlocks perks: landmarks, prospecting (founds a new industry if the resource exists), marketing campaigns (reputation + public transport usage), industry "greenification", pollution-cleaning plants (WIKI:management:companyandfinances).
- Rank also reduces income through inflation (M1).
- `companyRankRequiredIndustries` (`ECO:*.eco.lua`): ranks 2 (Quarry), 3 (Steel/Iron Ore/Coal), 5 (Oil), 7 (Forest/Saw Mill), 10 (Chemical Plant), 13 (Furniture/Glass/Sand). Probably guarantees these industries exist upon reaching the rank. [INFERENCE]
- Game difficulty options change costs and income: vehicle purchases, maintenance, infrastructure (50–150%) and cargo/passenger income (50–150%) (`base/mod.json`).
- See also M14: experience is the highest world population seen (read in the progression script), the rank has a reached value (it drives the ticket-price multiplier, so M1's inflation) and a taken value (it drives construction unlocks and permits), and per-company scores in some tools are not game rules.

---

## M12 — Maximum delivery time per cargo type

- Each cargo type has `timeToDeliverInSeconds` (table in `cargo_economy.md`, from `base/content/cargos/*.zip`). Delivery **after the deadline** does not reduce income, but counts as late in the "Delivery" rating (M2) (WIKI:management:companyandfinances#delivery_time).
- The company's "Delivery Time" tab shows the expected deadline per cargo type (new TF3 feature, same source).
- Values: from 900 (Meat) to 4500 (Iron Ore, Sand, Steel, Stone). Unit: seconds according to the field name; relationship to game days [UNVERIFIED].

---

## M13 — Town ratings and statistics (imported research)

Supplements M2. The rating formulas below were read in the game's own script (`GM:towns/town_util.tl`, scripts of build 40420, task 8.2) and match the MPFever author's transcription; facts that remain adopted carry their tag. No rating value was measured. M2's thresholds and tables are not changed by this section.

**Rescale of a raw fraction into a 0..1 rating** (same transform for both company-earned ratings):
- Happiness: raw fraction f = 1 − unhappy / max(total, 15); on-time delivery: f = 1 − late / max(delivered, 10) (`GM:towns/town_util.tl:479-519`, functions `getRatingHappinessFromStats` and `getRatingCargoDelivery`). This confirms M2's minimum denominators of 15 people and 10 items. The happiness totals combine the categories of the happiness statistics: `travellingInside` counts twice, `travellingTo` and `travellingFrom` count once each for residents and non-residents; `atBuilding`, `byCar`, `walking` and `byLine` are not used by this function (`GM:towns/town_util.tl:485-490`, `TEAL:engine/util.d.tl:585-597`).
- Transform: low = 1 − exp(−0.35667 × sens); s = sens clamped to 0..1; high = −1.2 s² + 2.2 s; rating = clamp((f − low) / (high − low), 0, 1). A sensitivity of 0 or less returns 1 (rating disabled). `sens` is the happiness sensitivity for passengers and the cargo-delivery sensitivity for on-time (`GM:towns/town_util.tl:480-502,506-518`). The sensitivity scale of both options is 0, 0.5, 0.75, 1, 1.5, 2, 3 (Off, Very Low, Low, Normal, High, Very High, Extreme; `BASE:difficulty_util.tl:46-47`). `town_ratings_sensitivity.res` holds the default level (4th entry, 1.0 Normal, for happiness, delivery, traffic, noise and pollution; 2nd entry, 1.0 On, for reputation) and the game's mod script writes the player's chosen option over it (`GM:towns/town_ratings_sensitivity.res.lua`, `BASE:mod.script.tl:680-689`).
- Worked values derived by us from that formula [INFERENCE]; see the source line above:

| sens | low (raw fraction that maps to 0) | high (raw fraction that maps to 1) |
|---|---|---|
| 0.5 | 0.163 | 0.8 |
| 1 (default "Normal") | 0.300 | 1.0 |
| 1.5 | 0.414 | 1.0 |
| 2 | 0.510 | 1.0 |

- Consequence [INFERENCE]: at the default sensitivity a raw on-time fraction of 0.30 already rates 0 and only 1.0 rates 1, so a rating that looks like "Good" in M2's level table can correspond to a much higher raw fraction.

**Keys and the authority score:**
- The game has six rating keys, the enum `TownRatingKey`: `urban_care`, `traffic_congestion`, `people_happiness`, `cargo_delivery`, `noise`, `pollution` (`GM:towns/town_util.d.tl:1-8`). Per-town sensitivity lookup `town_util.getRatingSensitivity(townState, key)` returns the town's own override when one is set, else the configured level mapped through the scales above (`GM:towns/town_util.tl:20-91`). Happiness and on-time cargo use `people_happiness` and `cargo_delivery`; these name entries of `town_ratings_sensitivity.res` (read, see above).
- Display names of the keys (`GM:towns/town_util.tl:643-716`): `urban_care` is "Reputation", `traffic_congestion` "Traffic", `people_happiness` "Happiness", `cargo_delivery` "Delivery", `noise` "Noise", `pollution` "Pollution". This settles the mapping of the six wiki ratings of M2 to keys; in particular `urban_care` is the Reputation rating. Its value comes from the town's event factors and the number of severed main connections (`GM:towns/town_util.tl:396-404`); the effect of terrain edits on it is in M16.
- The `Towns` game script handles two events: `setTownRatingSensitivity` (parameters `townEntity`, `rating`, `sensitivity`) stores a per-town override and `resetTownRatingSensitivity` (parameter `townEntity`) clears it (`GM:towns/towns.script.tl:345-373`). MPFever's use set `pollution`, `noise` and `traffic_congestion` to 0 for every town [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:9296-9301); a sensitivity of 0 or less makes that rating return 1.0 (`GM:towns/town_util.tl:413-449`), so those three can no longer be the lowest rating. M2's "Traffic" rating is keyed `traffic_congestion`.
- The game caches `{value, critical}` per rating key in the town state (`townState.cachedRatings`), for all six keys and a `growth_level` entry; `townState.authorityScore` is the minimum of the six values (no rating has the `added` flag), clamped to 0..1 (`GM:towns/town_util.tl:754-784`). [DISCREPANCY] MPFever treats only four keys (`urban_care`, `traffic_congestion`, `noise`, `pollution`) as the shared town rating, falls back to `authorityScore` when none is readable, and mixes in the company's own happiness and delivery itself [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:36) and (MPF:mod/mpfever_1/content/mpfever_progression.lua:155-168). Both agree with M2 that authority is the lowest rating; the difference is that the game's own cache already includes happiness and delivery, as town-wide values. The 0..1 range of `value` follows from the clamps in the game's rating functions.
- Reading the cached ratings: `urban_care` was assumed by the author's own comment to be Reputation [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_progression.lua:317); the game script confirms it (see the display names above).
- [DISCREPANCY] Per-company ratings. MPFever builds a company's own rating in a town as the minimum of the shared rating, its happiness rating and its on-time rating, clamped to 0..1, from per-line statistics [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:9-18) and (MPF:mod/mpfever_1/content/mpfever_progression.lua:313-316). The game has no per-company rating: `getRatingHappiness` and `getRatingCargoDelivery` take a town and its state only and read town-wide statistics (happiness with 0 top lines, deliveries with per-line and per-cargo splitting both off) (`GM:towns/town_util.tl:474-519`). The per-company split is MPFever's construction on top of the same transform.
- Town states: `town_util.externalGetTownsState()` returns a `TownsState` whose `townStates` array holds `TownState` entries with `townEntity` (an entity-and-revision table), `authorityScore`, `deliveryRating`, `cachedRatings` and `ratingSensitivity` (`GM:towns/towns.d.tl:55-72`, `GM:towns/town_util.tl:339`).
- The author removes pollution, noise and traffic from town growth because "engine computations made in parallel" are not the same on every machine; if true, those three ratings are non-deterministic between runs and growth forecasts that depend on them are noisy. [ADOPTED: claim] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:9293-9294) The game computes all six ratings through functions of the parallel town script (`getRatingFnName` of each rating, `GM:towns/town_util.tl:643-716`), but the scripts show no source of non-determinism; the random offset of noise and pollution is seeded with the town entity and is fixed per town (`GM:towns/town_util.tl:168-173`).
- A development command exists that makes the engine develop a town at a point using the C library random generator seeded with the clock; no stock script sends it (relayed from another project's investigation). Other town development uses the engine's deterministic generator. [ADOPTED: claim] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:84-92) and (MPF:docs/CHANGELOG.txt:116-118)

**Statistics calls (shapes as the author uses them):**

| Call | Returns | Source |
|---|---|---|
| `api.engine.util.town.getTownDeliveriesStats(town, interval, perLine, perCargoType)` | `{Entity : {CargoTypeId : {integer, integer}}}`; `interval` is milliseconds; the game calls it with half a game year and both flags false and reads `[-1][-1]` as the pair {late, delivered} (key `-1` is the all-cargo entry, and `-1` also keys the outer map when per-line is off, as the game reads it). With `perLine = true` the outer keys are line entities (MPFever passes `true, false` and sums the pairs when `-1` is absent) | `TEAL:engine/util.d.tl:635-641`; `GM:towns/town_util.tl:510-512`; [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:170-179) and (MPF:mod/mpfever_1/content/mpfever_progression.lua:197-207) |
| `api.engine.util.town.getTownHappinessStats(town, numTopLines)` | `TownHappinessStats` record: `travellingInside`, `atBuilding`, `byCar`, `walking` ({unhappy, total}), `travellingTo` and `travellingFrom` (each `resident` and `nonResident` pair), `byLine` (array of {line entity, `resident`/`nonResident` pairs}); pair order is {unhappy, total}. The second argument is the number of top lines considered; the game's rating passes 0, MPFever passes 1000 | `TEAL:engine/util.d.tl:585-597,630-634`; `GM:towns/town_util.tl:475,485-490`; MPFever's call [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:35) and (MPF:mod/mpfever_1/content/mpfever_progression.lua:208-222) |
| `api.engine.system.townBuildingSystem.getTown2personCapacitiesMap()` | `{Engine.Entity : {integer}}`: town entity to an array of 3 capacities in the order residential, commercial, industrial; element [1] is the residential capacity, which the game itself sums over all towns as the world population | `TEAL:engine/system.d.tl:121-125`; `GM:company/company_util.tl:365-371` |

- The window of the deliveries call is half a game year, `round(getDefaultYearDuration()/2)`, which agrees with M2's "last half-year" (`GM:towns/town_util.tl:510`). MPFever's `floor(x + 0.5)` is the same rounding. The third and fourth arguments are `perLine` and `perCargoType` (`TEAL:engine/util.d.tl:635-641`), and the second argument of the happiness call is the number of top lines (`TEAL:engine/util.d.tl:630-634`).
- Late and delivered counts can be split per line by passing `perLine = true`, so a town's delivery rating can be attributed to the lines that carry the cargo; the game's rating itself uses the town-wide totals. The attribution is MPFever's use. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:197-207)
- Population source: element [1] of the person-capacity array is the residential capacity (`TEAL:engine/system.d.tl:121-125`), and the game's world population is the sum of that element over all towns (`GM:company/company_util.tl:365-371`). `list_towns` defines population as the sum of residential, commercial and industrial capacity, which is a different quantity from the game's population.
- [UNVERIFIED] The meaning of the outer key `-1` of the deliveries map when per-line is off: the game reads `[-1][-1]` and the all-lines reading is inferred. Check: call it with `perLine = false` on a loaded save and print the keys.
- Our collector does not emit any of these ratings or statistics (see `snapshot_schema.md`, collector gaps).

---

## M14 — Company state: experience, rank reached against rank taken (imported research)

Supplements M11. Rank rule read in the game's progression scripts (`GM:company/company_growth.script.tl`, `GM:company/company_progression_util.tl`, `GM:company/company_util.tl`; scripts of build 40420, task 8.2); facts that stay adopted carry their tag.

- The progression script keeps one state per company entity (`companyState[companyEntity]`) but its update loop runs for the player's company only (`getPlayer()`). Experience is raised to the current world population whenever that is higher and is otherwise untouched, so it never decreases in normal play; world population is the sum over towns of element [1] (residential capacity) of the person-capacity map (`GM:company/company_growth.script.tl:9-27,86-110`, `GM:company/company_util.tl:365-371`). The rank follows from the thresholds on that experience. This sharpens M11's "rank depends on map population".
- The thresholds scale with a base population fixed once, when a new game starts from a map or a mission: it is the world population at that moment (`GM:company/company.script.tl:392-399`, read back by `GM:company/company_util.tl:356-363`). While it is not positive the progression update does nothing (`GM:company/company_growth.script.tl:81-84`). Level = first result of `getLevelAndFraction(basePopulation, experience)`: rank 0 below the base population, then the highest rank whose threshold the experience reaches, up to the maximum rank 15 (`GM:company/company_progression_util.tl:6-23,95-120`). The threshold for rank r, 1 to 15: interpolate the base population towards a normalised 725 with weight (15 − r) / 14, scale it with the town-growth function for rank r (`SCR:util/town_growth_function.tl`), subtract the interpolated value, add the real base population, never below r. Rank 0 needs 0.
- State fields: `experience`, `level` (the rank taken), `potentialLevel` (the rank reached) and `ticketPriceMultiplier`. Each update sets `potentialLevel` from the experience; a new state starts with level 1 and potential level 1. The company window takes a rank through the `applyLevel` event (script id `Companies`, parameter `level`), which the script accepts only when the new level is above the current one and not above `potentialLevel`; so a player can have reached a rank without having taken it, and a taken rank never goes down (`GM:company/company_growth.script.tl:9-62,153-157`). A configuration field `enforcedLevel` (nil in the shipped config) can force both levels (`GM:company/company_progression_util.tl:84-90`, `GM:company/company_growth_config.res.lua`).
  - The game's field names are `level` and `potentialLevel` (`GM:company/company_growth.script.tl:9-27`); `potential` is only the name MPFever uses in its own rank records [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:9453).
  - Which rank each effect reads: the ticket-price multiplier (inflation of M1) is computed from the rank reached, `1 + (rank − 1) × (m − 1) / 14` for rank above 1 with m = `ticketPriceMultiplierAtMaxLevel` (0.5 in the shipped config; no multiplier at rank 1 or below), and is sent for ticket-price events of the player's company (`GM:company/company_growth.script.tl:36-53,159-170`, `GM:company/company_progression_util.tl:25-40`, `GM:company/company_growth_config.res.lua`). Construction unlocks and permits use the rank taken: the rank gate, the extra-permit lookup and the permit counts read `level` (`GM:company/company_util.tl:83-93,171-180`, `GM:company/company_progression_util.tl:42-58`). [UNVERIFIED] Whether rank-gated industries of the economy files (M11) read taken or reached; the economy scripts were not traced. Check: dump the progression state around taking a rank and compare with industry appearance.
- The company state lives in a game script that follows only the savegame's company. Without a state for the player's company the helper `getCurrentCompanyState` reports level 0, potential level 0 and experience 0 (`GM:company/company_util.tl:373-389`). An interface acting as another company would therefore find rank 0 and most things locked [ADOPTED: claim] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:9408-9410) and (MPF:docs/CHANGELOG.txt:523-527).
- Read paths: `company_progression_util.getCompanyProgressionState(entity)` reads the progression game script (`getEntityForGameScript("::game_mechanics/company/company_progression.gs")`, then the `GAME_SCRIPT` component's `state.companyState[entity]`) and returns a table with `experience`, `level` and `potentialLevel` (`GM:company/company_progression_util.tl:74-93`).
- Permits: `company_util.getConstructionDisableCacheData` builds the permit data table: `companyRank` (the level taken, 0 without state), `extraPermits`, `maximumPermits`, `consumedPermits`, `remainingPermitCooldown` and `data`, which holds per construction file name and per instance permit key an entry whose only field is `numBuilt`. `numBuilt` is counted over every construction of the world that carries company metadata, with no owner filter (`GM:company/company_util.tl:83-169`, `GM:company/company_util.d.tl:29-35`). The call it uses, `forEachConstructionWithMetadata(key, constructionDescMeta, constructionInstanceMeta, callback)`, has the signature of `TEAL:engine/system.d.tl:266`. Whether unique buildings (headquarters, landmarks) are the constructions limited this way is MPFever's description [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_co.lua:157-200).

**Not a game rule: MPFever's per-company score.** To rank several companies in one world, MPFever invents its own score; it is the mod's design, ported from another project, and nobody has shown the game uses it. The shape is: score = sum over towns of (town population x the company's share of what was carried there x the company's rating there), where share averages the company's fractions of cargo and of passengers (weights 1 and 1; a kind nobody carries is dropped) and the rating is the company's own rating of M13. Experience is the floor of the score, kept at its maximum ever reached. It is sampled four times per game month, with passengers smoothed by an average over 24 samples. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:9-35) and (MPF:mod/mpfever_1/content/mpfever_progression.lua:81-121) and (MPF:mod/mpfever_1/content/mpfever_progression.lua:265-329); the changelog confirms the mod's rank score is its reimplementation and that the vanilla rule is only "map population" [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:72-76)
- Treat that score as a possible lens on what "population served" could mean, never as the thing the game computes. Do not report it as a rank rule.

---

## M15 — Game-script state: loans, contracts, notifications, counters (imported research)

Supplements M7 and M11. Game scripts keep serialisable state in the savegame. The loan shapes below were read in `GM:finance/loan.script.tl` and `GM:finance/loan_util.tl` (scripts of build 40420, task 8.2); the contract and notification shapes are still what the MPFever author reads and were not read by us.

**Reaching the state:**
- A game script's entity comes from `api.engine.system.gameScriptSystem.getEntityForGameScript(name)` (`TEAL:engine/system.d.tl:320-323`); its `GAME_SCRIPT` component carries `gameScript` (resource name), `state` (the internal state as a table) and the event subscriptions (`TEAL:engine.d.tl:401-412`). The game itself calls it with the `::game_mechanics/company/company_progression.gs` form, without a slash after the prefix (`GM:company/company_progression_util.tl:78`); the `::/game_mechanics/...` form with a slash is what the game uses for `.res` resources. MPFever's reading of the path form is [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7643-7647) and (MPF:mod/mpfever_1/content/mpfever_co.lua:239-246).
- Script files that exist: `game_mechanics/finance/loan.gs.lua` (loans), `game_mechanics/subventions/subventions.gs.lua` (contracts), `game_mechanics/notifications/notifications.gs.lua` (notification cards), `game_mechanics/company/company_progression.gs.lua` (progression, M14) and `game_mechanics/company/company.gs.lua` (`GM:` archive listing).
- The loan script holds a single table for the savegame's company, not one per company; its bookings go to `getPlayer()` (`GM:finance/loan.script.tl:4-24,47,101,136`).

**Loans (confirms M7's four offer types and waiting period; adds field names):**
- Loan state (`LoanTable`): `availableLoans` (the offers), `obtainedLoans` and `freeId` (`GM:finance/loan.script.tl:4-24`). A freshly made offer has `type` (Small, Medium, Large, ExtraLarge), `amount`, `duration`, `percentage` and `birthDay` (creation time) (`GM:finance/loan_util.tl:12-22`). After an offer is taken it is replaced by a placeholder with only `type` and `cooldownUntil`, set to now plus a random whole number between 4 and 8 default months (`GM:finance/loan.script.tl:144-155`). An obtained loan copies `type`, `amount`, `duration` and `percentage` from the chosen terms and adds `lastPayDay` (now), `timesPaid` (0) and `id` (`GM:finance/loan_util.tl:84-96`); `birthDay` is not carried over.
- An offer is regenerated when its creation time plus half a default game year has passed, or when its `cooldownUntil` is earlier than now; taking an offer is refused when the number of obtained loans is already `maximalObtainableLoans`, which is 4 (`GM:finance/loan.script.tl:59-78,133-134`, `GM:finance/loan_util.tl:3-5`). This agrees with M7 (half-year renewal, four loans). Loan accounting does nothing while the simulation does not advance and is frozen when the player has no balance (infinite money) (`GM:finance/loan.script.tl:43-50`).
- Schedule: months = round(duration / default month duration); one payment every duration / months game-time units since the last payment; each payment books principal and interest from the monthly helper, and the rounding remainders it also returns are added only on the final payment so principal and interest sum exactly; the loan is removed once `timesPaid` equals the number of months (`GM:finance/loan.script.tl:82-115`, `GM:finance/loan_util.tl:99-136`). The monthly principal is the rounded amount / months and the monthly interest the rounded percentage times that principal. This agrees with M7's fixed monthly instalments.
- Money bookkeeping: the player entity carries an `ACCOUNT` component with `balance` and `loan` (`TEAL:engine.d.tl:22-29`). The game books loan movements as journal entries with `amount`, `time` and `category.type` through `makeJournalBookAssetCmd(player, entry, position)`; loan entries use the category `LOAN`, interest entries `INTEREST`, and both are posted with `time = -1` (`GM:finance/loan_util.tl:202-216`, `GM:finance/loan.script.tl:94-104,135-136`). MPFever also names an `OTHER` category [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:5612-5616). What `time = -1` means is not stated in these scripts; "now" is the author's assumption. [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:205-211)
- Balances above 2,147,483,647 occurred (a 32-bit formatting overflow was reported against MPFever), so money is a Lua number, not a 32-bit integer; booked amounts are whole units. [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:278-280) and (MPF:mod/mpfever_1/content/mpfever_common.lua:92-98)
- Loan window events: the script subscribes to `Obtain` and `Repay` and handles them under the id `Loan`; the parameter is a pair {the offer taken, the loan as configured by the player} (`GM:finance/loan.script.tl:36-41,119-135`). Our tools never send events.
- Payback amount (resolved): `loan_util.getFullLoanAndInterestPayBack(loan)` returns two numbers, the remaining principal ((months − timesPaid) × monthly principal + the principal remainder) and the remaining interest ((months − timesPaid) × monthly interest + the interest remainder). The `Repay` handler books only the first one as a `LOAN` entry; the block that would book the interest is commented out, and the loan is dropped from `obtainedLoans` afterwards (`GM:finance/loan_util.tl:169-176`, `GM:finance/loan.script.tl:167-195`). This confirms M7: early repayment pays the remaining principal only and the remaining interest is never charged. MPFever's repayment for extra companies books the result of this helper; which of the two numbers it books is not stated. [ADOPTED: assumed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:808-810)

**Contracts (subsidies; M1 mentions only the 2x income):**
- State: lists `proposedSubventions`, `activeSubventions`, `completedSubventions` and (in the author's lifecycle order) `failedSubventions`: proposed, then active, then completed or failed; elements have a `uid`, offers also an `id`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_co.lua:239-246) and (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7669-7673)
- Contract types are generic resources of type `subvention`; each names a script as `path@function`, whose table offers handlers for events, accept, complete and failure. The accept and decline events are named `onAccept` and `onDecline` with the contract `uid`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_co.lua:313-346)
- The price event for contract income is `OnCalcTicketPrice` (the event of M1); its parameter entries expose the line entity, so income is computed per line delivery. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_co.lua:259-285)
- Rewards and penalties are booked to the current player at accept, complete and failure time, not to a stored owner. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_co.lua:288-303) In the game as shipped there is a single list for the savegame's company; MPFever's per-company ownership of contracts is its own extension. [ADOPTED: claim] (MPF:docs/CHANGELOG.txt:489-493)
- [UNVERIFIED] Contract fields beyond `id` and `uid` (cargo, endpoints, reward, deadline). Check: dump one proposed and one active entry.

**Notifications:**
- The notification state has a `notifications` map from id to an entry with `notification` (a `type` string and `params`), `expired` and `dismissed`; the interface parser also reads `timestamp` (game time), `dismissed` and `persisting` (a non-empty table marks persistent notifications such as warnings and contract cards). Contract cards have a type containing `subvention` and `params.uid` equal to the contract uid; the card uid is the entity times 10000. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:7709-7717) and (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:1480-1530)
- Entity references in notification parameters are tables with `entity` and a three-number revision. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:1520)
- "Industry Founded" notifications are generated by each game's interface, which scans industries every 5 s of game time, and not by the simulation; the notification type is `industry_spawn`. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:1612-1640) This sits beside M4, which lists the "Industry Closing" notification.
- [UNVERIFIED] The list of notification types and their params beyond contract cards.

**Construction counters:**
- A `CONSTRUCTION` component has `timeBuilt`, so construction age is readable; industries point at their construction entity. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:1636)
- Permit counters (`numBuilt` per construction type) are described in M14.

---

## M16 — What building does to money and towns (imported research)

Everything here was observed by MPFever, mostly while making two game instances replay each other's builds. Builds: game build 40408 or 40420; the changelog entries cited do not name the build, and entries after the 0.2.9 switch to 40420 are marked "build 40420 (inferred)".

**Refunds and costs:**
- Demolishing something just built can refund its cost, but only on the game that built it: the interface keeps a runtime list of refundable entities. After a reload that list is forgotten (an airport demolished about 50 s after a reload received no refund). [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:16-20) and (MPF:docs/CHANGELOG.txt:34-38) (build 40420, inferred).
- A removal that refunds nothing costs money: on replaying games it cost between 3,000 and 450,000, while the builder paid 0. [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:18-20) (build 40420, inferred)
- Measured example: a just-built heliport demolished on the builder's game versus the other game gave a cost of 2,190,453 on one side against 36,162 on the other. The author does not define the sign convention, so only magnitudes are usable. [ADOPTED: observed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:158-163) and (MPF:docs/CHANGELOG.txt:34-38) (build 40420, inferred)
- [UNVERIFIED] The refund window (time and percentage) and the sign of the cost reported by a build or demolition. Check: build and demolish one cheap object and read the money change.
- A build proposal carries maps of which new segments and nodes replace which old ones; the engine charges nothing for replaced parts and keeps what was on them (vehicles, for example). Without the maps the same build was paid twice. [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:239-245) (build 40420, inferred)
- Demolition with building gathering or terrain alignment on cost extra money on the other games and may reshape ground. [ADOPTED: observed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:2692-2694)
- The player's own company pays for its terrain edits, and the construction tool checks the company's money before building. [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:390-391) and (MPF:docs/CHANGELOG.txt:437-439)

**Town buildings and street upgrades:**
- Upgrading a street through a town moves town buildings: the engine takes buildings away and puts them back, choosing the new places with the game's random numbers. Buildings rebuilt as plain constructions stop being town buildings. [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:136-139) and (MPF:docs/CHANGELOG.txt:246-250) and (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:2557-2562)
- Measured street-upgrade example (build 40420, inferred; large community map, name withheld): the engine's own upgrade of one town street cost 8.4 M and removed 35 town buildings; a rebuild of the same street through script forms (not the game's tool) cost 13.8 M and removed 44 buildings. Use 8.4 M and 35 buildings as the upgrade figures and 13.8 M and 44 as the cost of a different path through the engine. [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:136-139) and (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:3465-3475)
- Placement after an upgrade has a random element: one extra building may be placed differently even with identical inputs. [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:648-652)
- A street laid through houses takes them away (three 30 m pieces through the houses beside it in one scenario). [ADOPTED: claim] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:6125-6130)
- The upgrade tool, by default, aligns terrain, cleans up the street graph and gathers buildings, while the bulldozer by default does not align terrain or gather buildings. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:2621-2626)

**Terrain, reputation and auto-removal:**
- Terrain edits (raise, lower, flatten) change the reputation of the nearest town; applying one late made towns drift apart. This confirms M2's "landscaping lowers Reputation". [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:381-386) (build 40420, inferred)
- The game's town script scores a player-initiated build per town through `town_util.getProposalStats`: removed and added trees and rocks, removed buildings, the fraction of the district removed, terrain brush volume added and removed, terrain alignment volume added and removed, and tunnel volume added; a build not initiated by the player returns no statistics (`GM:towns/town_util.tl:1062-1097`). The engine also reports per-town {added, removed} reputation impacts for terrain brushes, terrain alignment and the automatic removal of trees and rocks (`TEAL:engine/util.d.tl:646-657`). [DISCREPANCY] MPFever names two inputs, terrain alignment and the auto-removal of town entities [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:1436-1460); the game's statistics record has more inputs, and the TEAL describes auto removal as that of trees and rocks. The size of the effect is not stated.
- [UNVERIFIED] The reputation change per edit or removal. Check: edit terrain beside a town and read its Reputation rating before and after (M13).

**Stops and stations:**
- A stop placed on a street without sidewalk lanes: the stop tool adds platform lanes on both sides; if they are missing the engine accepts the build and silently drops the stop. This explains stops that "do not appear" (a tram-style street, for example). [ADOPTED: observed] (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:2780-2782) and (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:6749)
- Bulldozing a street that carries stops removes the stops; replacing a segment (an upgrade) keeps them; a road joined to a street with stops moves them. [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:540-542) and (MPF:mod/mpfever_1/content/mpfever_bridge.script.lua:2555-2556) and (MPF:docs/CHANGELOG.txt:333-334)
- A road built across a street with stops, leaving the stops on the removed piece, crashed the game when it computed their catchment (M5): stops need a valid street node. [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:368-374) (build 40420, inferred)
- Bulldozing a dead-end street with the engine's own removal proposal from a script can trip an engine assertion about non-empty nodes, also without the mod. [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:145-147) (build 40420, inferred)
- Station-group expiry: an empty station group expires 20 game days after it became empty; the icon of a deleted stop stays about 80 s at 1x. Station groups, not stations, are what lines list in their stops. [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:114-116) (build 40420, inferred)
  - [DISCREPANCY] Day length. M10 and the wiki say 4 s per day, and 20 days of 4 s equal the observed 80 s; `ECO:cargotype.script.lua` assumes 2000 ms per day (which would give 40 s). The author's "20 game days of 4000 ms" is an assumption, not a measured day length. [ADOPTED: assumed] (MPF:docs/CHANGELOG.txt:114-116) and (MPF:docs/CHANGELOG.txt:164) Task 8.2 read the game scripts and found no numeric day length in them (see M10).
  - [UNVERIFIED] Whether a removed station's group lingering in our snapshots affects `list_stocks` or `stops`. Check: remove a stop and read the group for 20 game days.

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
- Wiki × code discrepancies: monthly interest/15-day instalments (loans); unused years before closure (10 versus 5); Livestock Farm and Furniture Factory have boosters in the wiki without rules in `.con.lua` (see `cargo_economy.md`).
- Wiki pages marked "not yet adapted"/"old revision": `gamemanual:management:companyandfinances` and `gamemanual:gameplayfaqs` appear as "old revision"; FAQ is empty.

**Imported research (MPFever; adopted facts keep their tag, verified facts cite the game):**
- M13 ratings: the formulas, the 0.35667 rescale, the minimum denominators, the sensitivity scales and keys, the display names and the authority-score minimum were read in `GM:towns/town_util.tl` and match; the statistics call shapes come from `TEAL:`; MPFever's per-company ratings and four-key shared rating are recorded as a discrepancy with the game's town-wide, six-key rating.
- M14 company state: experience as the highest world population, the reached and taken ranks, the apply-level event, base population, and the permit data were read in the company scripts; MPFever's own score stays recorded as design, not rule.
- M15 game-script state: loan state, schedule, offer lifecycle, bookkeeping and payback were read in the loan scripts; contract lifecycle and notification shapes remain adopted.
- M16 building effects: refund behaviour (runtime-only), demolition costs, replacement maps, town-building removal with the measured street-upgrade example, terrain and reputation, stops dropped without sidewalk lanes, station-group expiry and the day-length evidence stay adopted measurements; the scripts add the proposal-statistics inputs.
- Builds: every MPFever measurement was made on game build 40408 or 40420 (`MPF:docs/CHANGELOG.txt:571-577`); changelog entries do not name the build per result, so figures from entries after its 0.2.9 switch are marked "build 40420 (inferred)". The scripts read for verification are those installed on the macOS Steam copy, whose executable carries the label 40420 (see `engine`).

**Unverified / gaps (imported research):**
- Resolved by reading the scripts (task 8.2): the rating formulas of M13 equal the game's own; `urban_care` is the Reputation rating and Happiness and Delivery are among the six cached keys; the trailing arguments of the deliveries call are `perLine` and `perCargoType` and the second argument of the happiness call is the number of top lines; index 1 of the person-capacity array is residential capacity; the base population is the world population at the start of a game; inflation reads the rank reached and construction permits the rank taken; `Repay` pays remaining principal only.
- [UNVERIFIED] Whether rank-gated industries (M11) read the rank taken or reached: the economy scripts were not traced (M14).
- [UNVERIFIED] Contract fields beyond `id` and `uid`, and notification types and their params beyond the contract card.
- [UNVERIFIED] Size and time window of the refund for demolishing something just built, and the sign convention of the reported cost (M16).
- [UNVERIFIED] Whether expiry of an empty station group (M16) affects stops or `list_stocks` rows of removed stations.
- [DISCREPANCY] Day length: 4 s per day (M10 and M16 evidence) against a 2000 ms value assumed in `ECO:cargotype.script.lua`; the scripts read in task 8.2 contain no numeric default, so the evidence for 4 s is still the wiki and the adopted 80-second observation.
- [DISCREPANCY] Vehicle lifespan unit (M6 not edited here): the interface script multiplies `maintenance.lifespan` by 1000 before comparing it with the age in game time (`gui/line_vehicle_mgmt/vehicle_util.tl:31-34`, `gui/entity_window/line/line_eow.script.tl:136-144` in `gui.zip`), so the unit is seconds of game time, not days as M6's inference reads it. The calendar span depends on the default day length, and the two readings agree only for a day of 1000 ms.
