# Cargo economy: cargo types, industries and chains (base TF3)

> **Evidence legend (imported research).** `MPF:<file>` cites a file of MPFever (https://github.com/dkdknight/MPFever, MIT, studied at commit `ae5fc96`; paths relative to its repository root). `[ADOPTED: observed|code|assumed|claim]` marks a fact taken on the MPFever author's word and not verified by this project; the class is the author's own: observed = measured by the author, code = read by the author in game code or the engine, assumed = the author's assumption, claim = stated without evidence. Every statement is paraphrased. `[INFERENCE]`, `[UNVERIFIED]` and `[DISCREPANCY]` keep their existing meaning.

Source conventions (paths relative to `Transport Fever 3/`):
- **CARGO:x** = `base/content/cargos/x.zip:x/x.cargo.lua`
- **IND:x** = `base/content/industries/x.zip:x/x.con.lua`
- **ECO:** = `base/content/economy.zip:economy/` (`placementparamsutil.lua`, `temperate|dry|tropic|subarctic|all.eco.lua`)
- **WIKI:ic** = `https://wiki.transportfever3.com/doku.php?id=gamemanual:simulation:industriescargos`
- **WIKI:towns** = `https://wiki.transportfever3.com/doku.php?id=gamemanual:simulation:towns`
- General mechanics (income, growth, boosters, closure): `mechanics.md` (M1…M12).
- Where the wiki and `.con.lua` conflict, both values are listed and marked [DISCREPANCY].
- Total (WIKI:ic): 36 cargo types (12 raw materials, 11 intermediates, 3 boosters, 10 final products) and 32 industries (32 `.con.lua` files in `base/content/industries/`). Passengers are a 37th cargo type (`CARGO:passengers`).

---

## 1. Cargo types

All freight cargo types pay the same per item and per metre (3.8; see `mechanics.md` M1, `ECO:cargotype.script.lua` + `CARGO:*`). What differs between cargo types: vehicle class, delivery deadline, where they are produced and consumed, and town demand.

Key: **Class** = the cargo's `cargoClasses` (every cargo is also UNIVERSAL), in `CARGO:x`. **Deadline** = `timeToDeliverInSeconds` in `CARGO:x`. **Tier/Use/Factor** = `ECO:placementparamsutil.lua:getCargoCategories` (only cargo types demanded by towns). Factor = `townConsumptionFactor` (the lower it is, the smaller the annual quantity; WIKI:towns: complex cargo types are demanded in smaller quantities). Type/Producer/Consumer = WIKI:ic, confirmed against `IND:x`.

| Cargo (id) | Type | Class | Producer(s) | Consumer(s) | Deadline | Town: use / tier / factor |
|---|---|---|---|---|---|---|
| Grain (grain) | raw material | BULK | Farm | Livestock Farm; **Brewery** (according to `IND:brewery`; not listed by the wiki) | 1286 | — |
| Vegetables (vegetables) | final | GOODS | Farm | Commercial district | 1125 | COMMERCIAL / 0 / 1 |
| Fertilizer (fertilizer) | booster | BULK | **Oil Refinery** (according to `IND:oil_refinery`; the wiki says "Chemical Plant" [DISCREPANCY]) | Farm, Cotton Farm, Rubber Plantation (booster) | 1500 | — |
| Wool (wool) | raw material | GOODS | Cotton Farm, Livestock Farm | Weaving Mill | 1500 | — |
| Meat (meat) | raw material | GOODS | Livestock Farm | Commercial district; Food Factory | **900** | COMMERCIAL / 0 / 1 |
| Fish (fish) | raw material | GOODS | Fishing Grounds | Commercial district; Food Factory | 1125 | COMMERCIAL / 0 / 1 (only if there are fishing grounds on the map) |
| Logs (logs) | raw material | FLATBED | Forest | Saw Mill | 3000 | — |
| Planks (planks) | intermediate | FLATBED | Saw Mill | Industrial district; Furniture Factory; Tool Factory | 3000 | INDUSTRIAL / 0 / 1 |
| Sawdust (sawdust) | intermediate | BULK | Saw Mill | Paper Mill | 2250 | — |
| Paper (paper) | intermediate | GOODS | Paper Mill | Printing Press | 1800 | — |
| Books (books) | final | GOODS | Printing Press | Commercial district | 1800 | COMMERCIAL / 1 / 0.5 |
| Sand (sand) | raw material | BULK | Sand Excavator, Sand Pit | Glass Works | 4500 | — |
| Glass (glass) | intermediate | GOODS | Glass Works | Furniture Factory; Brewery | 2250 | — |
| Furniture (furniture) | final | GOODS | Furniture Factory | Industrial district | 1800 | INDUSTRIAL / 1 / 0.5 |
| Beverages (beverages) | final | GOODS | Brewery | Commercial district | 1125 | COMMERCIAL / 1 / 0.5 |
| Clay (clay) | raw material | BULK | Clay Pit | Brick Works | 3000 | — |
| Bricks (bricks) | final | GOODS | Brick Works | Industrial district | 3000 | INDUSTRIAL / 0 / 1 |
| Stone (stone) | raw material | BULK | Quarry | Cement Plant | 4500 | — |
| Cement (cement) | final | BULK | Cement Plant | Industrial district | 2250 | INDUSTRIAL / 0 / 1 |
| Coal (coal) | raw material | BULK | Coal Mine | Steel Mill | 3000 | — |
| Iron Ore (iron_ore) | raw material | BULK | Iron Ore Mine | Steel Mill | 4500 | — |
| Steel (steel) | intermediate | FLATBED | Steel Mill | Machine Factory | 4500 | — |
| Sheet Metal (sheet_metal) | intermediate | FLATBED | Steel Mill | Food Factory; Vehicle Factory | 3000 | — |
| Machines (machines) | booster | FLATBED | Machine Factory | Industrial district; Vehicle Factory; boosters: Forest, Iron Ore Mine, Oil Well, Sand Excavator, Oil Platform (according to `IND`; the wiki lists Tools for the platform [DISCREPANCY]) | 2250 | INDUSTRIAL / 1 / 0.5 |
| Crude Oil (crude_oil) | raw material | LIQUID | Oil Platform, Oil Well | Oil Refinery | 3000 | — |
| Fuel (fuel) | final | LIQUID | Oil Refinery | Industrial district | 2250 | INDUSTRIAL / 0 / 1 |
| Chemicals (chemicals) | intermediate | LIQUID | Oil Refinery | Chemical Plant | 1800 | no town use (`tier 1`, no `landUses`), factor 0.5 |
| Dyes (dyes) | intermediate | LIQUID | Chemical Plant | Textile Factory; Printing Press | 2250 | — |
| Plastic (plastic) | intermediate | GOODS | Chemical Plant | Tool Factory; Machine Factory | 1500 | — |
| Fabric (fabric) | intermediate | GOODS | Weaving Mill | Textile Factory | 1500 | — |
| Clothes (clothes) | final | GOODS | Textile Factory | Commercial district | 1500 | COMMERCIAL / 1 / 0.5 |
| Tinned Food (tinned_food) | final | GOODS | Food Factory | Commercial district | 1800 | COMMERCIAL / 1 / 0.5 |
| Rubber (rubber) | raw material | LIQUID | Rubber Plantation | Tire Factory | 1800 | — |
| Tires (tires) | intermediate | GOODS | Tire Factory | Vehicle Factory | 1500 | — |
| Tools (tools) | booster | GOODS | Tool Factory | Industrial district; boosters: Clay Pit, Coal Mine, Fishing Grounds, Quarry, Sand Pit (+ Oil Platform according to the wiki) | 2250 | INDUSTRIAL / 1 / 0.5 |
| Vehicles (vehicles) | final | FLATBED | Vehicle Factory | Industrial district | 2250 | INDUSTRIAL / **2** / 0.25 |
| Passengers (passengers) | passengers | PASSENGERS | Homes | Destinations (work/shopping/leisure) | — | cargo weight 1/6; `loadSpeedFactor` 1 |

Notes:
- Wiki type/consumers: WIKI:ic. Class/deadline: `CARGO:*`. Tier/use/factor: `ECO:placementparamsutil.lua:getCargoCategories`.
- All freight cargo types have a `loadSpeedFactor` of 0.0625 (`CARGO:*`); passengers have 1. Exact semantics [UNVERIFIED].
- **Deadline** (in `timeToDeliverInSeconds`): late delivery does not reduce income, but worsens the town's "Delivery" rating (`mechanics.md` M12). Shortest: Meat 900; Vegetables/Fish/Beverages 1125; Grain 1286. Longest: Iron Ore, Steel, Stone, Sand 4500.
- Town demands (`ECO:placementparamsutil.lua`):
  - **Commercial:** Vegetables, Fish, Meat (tier 0); Beverages, Books, Clothes, Tinned Food (tier 1).
  - **Industrial:** Bricks, Cement, Fuel, Planks (tier 0); Furniture, Machines, Tools (tier 1); Vehicles (tier 2).
  - **There is no tier 2 commercial cargo in the data.** The wiki says the third commercial demand (level 9) can be "the most complex type"; in practice, commercial cargo types only have tier ≤1.
- Tiers × town XP per delivered item: tier 0 = 10, tier 1 = 20, tier 2 = 40 (WIKI:towns; `mechanics.md` M2).
- Which cargo types/industries exist depends on the climate: see §3. Town demand only considers cargo types in the current climate (`cargoCategories` removed by climate in `ECO:*.eco.lua`).

---

## 2. Industries: inputs → outputs, stocks, boosters

Values per **production cycle at maximum level**; "duration" = the rule's `capacity` field in `IND:x` (the unit is undocumented; see the note below). Booster: a rule flagged by `booster`, consuming an input with duration 4. Stocks = capacity in items (input / output), `IND:x` `stocks`. Raw materials are produced without inputs.

**Primary industries** (no mandatory input):

| Industry (id) | Output per cycle (max. level) | Duration | Cargo booster | Output stock | Booster stock |
|---|---|---|---|---|---|
| Farm (farm) | 24 Grain + 16 Vegetables | 11.41 | Fertilizer, consumes 17 | Grain 300 / Vegetables 200 | 100 |
| Cotton Farm (cotton_farm) | 12 Wool | 22.81 | Fertilizer, 17 | 300 | 100 |
| Rubber Plantation (rubber_farm) | 32 Rubber | 11.41 | Fertilizer, 17 | 400 | 100 |
| Fishing Grounds (fishing_grounds) | 12 Fish | 21.90 | Tools, 12 | 300 | 100 |
| Forest (forest) | 8 Logs | 30.42 | Machines, 15 | 300 | 100 |
| Coal Mine (coal_mine) | 16 Coal | 20.00 | Tools, 13 | 400 | 100 |
| Iron Ore Mine (iron_ore_mine) | 16 Iron Ore | 22.81 | Machines, 15 | 400 | 100 |
| Quarry (quarry) | 16 Stone | 22.81 | Tools, 12 | 400 | 100 |
| Clay Pit (clay_pit) | 16 Clay | 22.81 | Tools, 12 | 400 | 100 |
| Sand Pit (sand_pit) | 8 Sand | 45.63 | Tools, 12 | 400 | 100 |
| Sand Excavator (sand_excavator, on water) | 8 Sand | 45.63 | Machines, 15 | 400 | 100 |
| Oil Well (oil_well) | 6 Crude Oil | 91.25 | Machines, 15 | 600 | 100 |
| Oil Platform (oil_platform, on water) | 4 Crude Oil | 91.25 | **Machines**, 12 (`IND`); wiki says Tools [DISCREPANCY] | 400 | 100 |

**Secondary and tertiary industries:**

| Industry (id) | Input per cycle | Output per cycle | Duration | Input stock | Output stock |
|---|---|---|---|---|---|
| Saw Mill (saw_mill) | 4 Logs | 8 Planks + 4 Sawdust | 91.25 | Logs 400 | Planks 800 / Sawdust 400 |
| Paper Mill (paper_mill) | 4 Sawdust | 2 Paper | 182.5 | 800 | 400 |
| Printing Press (printing_press) | 4 Paper + 2 Dyes | 4 Books | 91.25 | Paper 400 / Dyes 200 | 400 |
| Glass Works (glass_works) | 4 Sand | 2 Glass | 182.5 | 800 | 400 |
| Furniture Factory (furniture_factory) | 4 Planks + 1 Glass | 2 Furniture | 182.5 | Planks 800 / Glass 200 | 400 |
| Brewery (brewery) | 8 Grain + 3 Glass | 8 Beverages | 45.63 | Grain 400 / Glass 200 | 400 |
| Brick Works (bricks_works) | 4 Clay | 4 Bricks | 182.5 | 800 | 400 |
| Cement Plant (cement_plant) | 4 Stone | 2 Cement | 182.5 | 800 | 400 |
| Steel Mill (steel_mill) | 6 Iron Ore + 6 Coal | 3 Steel + 4 Sheet Metal | 121.67 | Iron Ore 800 / Coal 800 | Steel 400 / Sheet Metal 500 |
| Machine Factory (machine_factory) | 7 Steel + 4 Plastic | 7 Machines | 45.63 | Steel 400 / Plastic 200 | 400 |
| Oil Refinery (oil_refinery) | 4 Crude Oil | 2 Fuel + 1 Fertilizer + 4 Chemicals | 182.5 | 800 | Fuel 400 / Chemicals 800 / Fertilizer 300 |
| Chemical Plant (chemical_plant) | 6 Chemicals | 2 Dyes + 5 Plastic | 121.67 | 800 | Dyes 300 / Plastic 700 |
| Livestock Farm (livestock_farm) | 8 Grain (`IND`; wiki 7) | 4 Meat + 5 Wool (`IND`; wiki 3 and 4) [DISCREPANCY] | 91.25 | 800 | Meat 400 / Wool 500 |
| Weaving Mill (weaving_mill) | 4 Wool | 4 Fabric | 121.67 | 500 | 500 |
| Textile Factory (textile_factory) | 4 Fabric + 2 Dyes | 3 Clothes | 121.67 | Fabric 500 / Dyes 300 | 400 |
| Tool Factory (tool_factory) | 4 Planks + 2 Plastic | 5 Tools | 121.67 | Planks 500 / Plastic 300 | 700 |
| Tire Factory (tire_factory) | 4 Rubber | 2 Tires | 182.5 | 800 | 400 |
| Vehicle Factory (vehicle_factory) | 1 Tire + 4 Sheet Metal + 1 Machine | 1 Vehicle | 365 | Tires 400 / Sheet Metal 800 / Machines 400 | 400 |
| Food Factory (food_factory) | 2 Fish **or** 2 Meat, **plus** 1 Sheet Metal | 2 Tinned Food | 182.5 | Fish 400 / Meat 400 / Sheet Metal 200 | 200 |

Source: input/output/duration/stock values in `IND:x`; these match WIKI:ic ("Industries List" section) except where marked.

Notes on the rules:
- The **duration** of most rules is 365/n (365, 182.5, 121.67, 91.25, 45.63, 30.42, 22.81, 11.41; exceptions: Coal 20, Fishing Grounds 21.9): [INFERENCE] these are fractions of a year in days. Do not use the table to estimate annual volume. **Always use `getCargoMaxProductionPerYear`/actual in-game production (MCP snapshot)**: actual production is scaled by production level, `defaultIndustryProductivity` (temperate 0.58), boosters and the "Industry Productivity" option (`mechanics.md` M3).
- **Production level** = number of plots; output per cycle is scaled by level/maximum level. The wiki gives ranges (e.g. Coal 1–16; Quarry 1–16; Oil Platform 1–4).
- Food Factory has **two** rules: Fish + Sheet Metal or Meat + Sheet Metal. It is not "Fish and Meat together".
- Steel Mill requires **both** inputs in a 1:1 ratio (6 Iron Ore : 6 Coal).
- Several processing industries (Steel Mill, Saw Mill, Oil Refinery, Chemical Plant, Livestock Farm) have **two or more outputs** in separate stocks; excess output goes to `itemsDestroyed` when stock fills up (`mechanics.md` M3 and M9). Whether one full output stock blocks the other outputs: [UNVERIFIED].
- Capacity for people (worker booster) = 20 in all industries (`industrialCapacity` in `IND:*`); see `mechanics.md` M3.

---

## 3. Availability by climate

Source: `ECO:temperate|dry|tropic|subarctic.eco.lua` (removal of `placementParams.X`), matching the WIKI:ic table.

| Climate | **Absent** industries (do not appear) |
|---|---|
| Temperate | Cement Plant, Paper Mill, Printing Press, Rubber Plantation, Tire Factory |
| Dry | Cement Plant, Cotton Farm, Fishing Grounds, Paper Mill, Printing Press, Rubber Plantation, Sand Excavator, Tire Factory |
| Tropical | Brewery, Brick Works, Cement Plant, Clay Pit, Paper Mill, Printing Press |
| Subarctic | Brick Works, Clay Pit, Cotton Farm, Rubber Plantation, Tire Factory |

Effects on cargo types (removal of `cargoCategories` in `ECO:*.eco.lua`):
- Temperate: no Cement, Books, Paper, Rubber, Tires.
- Dry: no Cement, Fish, Books, Wool, Paper, Rubber, Tires.
- Tropical: no Cement, Beverages, Books, Bricks, Clay, Paper.
- Subarctic: no Bricks, Clay, Wool, Rubber, Tires.
- `industryPlacementFallbacks`: Oil Platform → Oil Well and Sand Excavator → Sand Pit (when the water-based version cannot fit); Oil Refinery in temperate/tropical climates requires Oil Platform; Glass Works requires Sand Excavator in temperate/tropical/subarctic climates (`requiredIndustryTags`).
- `waterIndustryFraction` (share of industries on water): temperate 6/41, dry 2/39, tropical 6/41, subarctic 5/40 (`ECO:*.eco.lua`).
- Tires can only be produced in the tropical climate (the only `eco.lua` that keeps both `tire_factory` and `rubber_farm`). Since Vehicle Factory requires Tires (`IND:vehicle_factory`) and the wiki marks it ✔ in all four climates, how it operates in the other climates is [UNVERIFIED].
- To check a save's climate: `ECO:all.eco.lua` does not define a climate; the climate is `baseConfig.climate` (`base/mod.script.tl`). The MCP snapshot should state the climate.

---

## 4. Main chains and their consumers

(inferred from the rules above; sources `IND:*`, WIKI:ic)

- **Steel and derivatives:** Iron Ore Mine + Coal Mine → Steel Mill → Steel (Machine Factory) and Sheet Metal (Food Factory, Vehicle Factory).
- **Machines:** Steel + Plastic (Chemical Plant ← Oil Refinery ← Crude Oil) → Machine Factory → Machines (industrial district; boosters for Forest/Iron Ore Mine/Oil Well/Sand Excavator; Vehicle Factory).
- **Oil:** Oil Platform/Oil Well → Oil Refinery → Fuel (industrial district), Fertilizer (farm boosters), Chemicals → Chemical Plant → Dyes + Plastic.
- **Wood:** Forest → Saw Mill → Planks (industrial district, Furniture, Tools) + Sawdust → Paper Mill (subarctic) → Paper → Printing Press (with Dyes) → Books (commercial).
- **Furniture:** Planks + Glass (Sand → Glass Works) → Furniture Factory → industrial district.
- **Agriculture:** Farm → Vegetables (commercial) and Grain → Livestock Farm → Meat (commercial/Food Factory) + Wool → Weaving Mill → Fabric → Textile Factory (with Dyes) → Clothes (commercial); Brewery: Grain + Glass → Beverages (commercial).
- **Tinned Food:** Fish or Meat + Sheet Metal (Steel Mill) → Tinned Food (commercial).
- **Construction:** Clay → Brick Works → Bricks; Stone → Cement Plant → Cement (both industrial district).
- **Vehicles (tier 2):** Tires (Rubber) + Sheet Metal + Machines → Vehicle Factory → industrial district. The complete Tire chain only exists in the tropical climate (§3); outside it, whether Vehicle Factory operates/appears is [UNVERIFIED].
- **Boosters** form loops: Tools ← Tool Factory (Planks + Plastic); Machines ← Machine Factory; Fertilizer ← Oil Refinery. Primary industries consume end-of-chain products in return.

`ECO:*.eco.lua` also contains `cargoRequiredIndustries` (one weight per industry for each cargo type), whose interpretation is undocumented. [UNVERIFIED]

---

## 5. Research notes (imported MPFever evidence)

Each note names the section it affects. None changes a value in §1 to §4; they confirm or sharpen them. Builds: 40408 or 40420; entries that do not name the build are marked inferred.

- **Affects §1 deadlines (`mechanics.md` M12, M13) — sharpening.** Late deliveries are counted per line and per cargo type over a window of half a game year, and the delivery rating uses at least 10 delivered items; the raw late share is then rescaled (M13), so the Deadline column feeds a quantity that can be attributed to individual lines. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:103-111) and (MPF:mod/mpfever_1/content/mpfever_progression.lua:170-179,190-207)
- **Affects §1 town demands and town XP (M2, M13) — confirmation.** A company's own rating in a town is the lowest of the town's shared rating and the company's own happiness and on-time ratings, so cargo delivered to meet a demand grows the town only as far as that lowest rating allows; happiness and delivery are per-company inputs. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_progression.lua:9-18,313-316)
- **Affects §1 town demands (M2, M16) — confirmation.** Terrain edits near a town lower its reputation, which is one of the ratings in that minimum (build 40420, inferred). [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:381-386)
- **Affects §1 income statement (M1) — [UNVERIFIED].** The price event for delivery income, `OnCalcTicketPrice`, receives parameter entries that expose the line entity, so income is computed per line delivery. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_co.lua:259-285) The research gives no other field of those entries, so it neither confirms nor contradicts the equal pay per cargo type stated in §1. Check: dump the parameter entries of one delivery.
- **Affects §2 closure and founding (M4) — sharpening.** Industry events such as closure and the founding of new industries are random draws made by the engine, identical between games only when the seeds and inputs are identical; they are not functions of time alone. [ADOPTED: observed] (MPF:docs/CHANGELOG.txt:681-683,721-722)
- **Affects §2 industry age (M4) — new.** An industry points at its construction entity, and a construction has a `timeBuilt` field, so industry age is readable; the "Industry Founded" notification is created by each game's interface, which scans industries every 5 s of game time. [ADOPTED: code] (MPF:mod/mpfever_1/content/mpfever_ui.script.lua:1612-1640)
- **Affects §2 stocks (M3, M9) — confirmation.** The stock sizes in §2 are per-stock counts held in the `STOCK_LIST` component, while cargo in transit is simulated as individual cargo entities. [ADOPTED: code] (MPF:docs/RESEARCH.md:168,184)
- **Affects §1 town demands (M16) — [UNVERIFIED].** A street upgrade through a town moves or removes town buildings (M16), but the research does not say whether that changes the town's capacities and therefore the quantities in its demands. Check: read `list_towns` capacities before and after one upgrade.

---

## Sources and gaps

**Verified in files:** all 32 industry `.con.lua` files (inputs/outputs/stocks/booster/duration), 37 `.cargo.lua` files (class, deadline), `ECO:placementparamsutil.lua` + 5 `.eco.lua` files (tiers, demands, climates, fallbacks), wiki `simulation:industriescargos` and `simulation:towns`.

**Unverified / gaps:**
- Unit of duration; actual annual production per industry and per level (use actual game data).
- Exact number of plots (maximum level) per industry; only the wiki gives ranges.
- Meaning of `cargoRequiredIndustries`; effect of `defaultIndustryProductivity` (only the temperate value has been read).
- What happens to a full output stock when the other output continues to be collected.
- Which cargo types each town actually demands (varies by map; supplied by the snapshot).
- Wiki × `.con.lua` discrepancies: Fertilizer (Chemical Plant vs Oil Refinery), Oil Platform (Tools vs Machines), Livestock Farm (7/3/4 vs 8/4/5, Machines booster only in the wiki), Furniture Factory (Machines booster only in the wiki), Grain consumption by Brewery (only in `.con.lua`).
- Availability of Vegetables in the subarctic (`removeTags OUTPUT_VEGETABLES` in `ECO:subarctic.eco.lua`, but Farm remains; effect on demand unverified).
- Campaign/mission content (special cargo types) is out of scope.
- Research-note items marked [UNVERIFIED] in §5 (equal pay in `OnCalcTicketPrice`, effect of removed town buildings on demand) and the unverified rating formulas of M13.
