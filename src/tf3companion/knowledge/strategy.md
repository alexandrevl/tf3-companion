# Strategy: heuristics for a profitable company

**Every item below is a HEURISTIC, not a rule.** Each identifies the mechanic it relies on (`mechanics.md` §M#, `cargo_economy.md` §#) and what is verified or inferred. Before recommending anything, confirm it against actual snapshot data (line/vehicle balance, industry production/stock, town ratings). Sources for each mechanic are in the referenced files; only the minimum is repeated here.

Key: `[V]` = basis verified in code/wiki; `[I]` = an inference to test; `[?]` = depends on something unverified.

---

## A. Choosing routes and cargo types

**H1 — Choose cargo by volume and logistics, not by its "price".** `[V]`
- Based on: `mechanics.md` §M1 — all freight cargo types pay equally (3.8 × distance × difficulty); passengers ≈ 3.61.
- Consequence: differences in profit per trip come from **vehicle capacity per cargo type, loading speed, distance, return cargo and running costs**, not the type of goods. Cargo types differ in deadline (`cargo_economy.md` §1) and whether there is demand/a consumer.
- Consequence [I]: high-volume cargo types already piled up in stock (Coal, Iron Ore, Stone, Sand, Logs) tend to fill vehicles easily; end-of-chain cargo types have lower volumes but help towns grow (H12).

**H2 — Prefer routes that are straight and long enough for income per trip to compensate for stationary time.** `[V]` for the basis, `[I]` for the optimum
- Based on: §M1 (income ∝ straight-line distance between origin and final destination) and the wiki tip that S/U-shaped detours pay less because upkeep follows actual length (WIKI tipstricks).
- Compare **straight-line distance ÷ actual route length**; if far from 1, review the alignment.
- For uphill travel, the script adds eight times the positive elevation difference to distance; if Δz means destination minus origin, uphill deliveries earn more. `[?]` (§M1)
- The effect of speed on income is absent from the Lua script; the wiki claims faster travel pays more. Nevertheless, speed matters for cycle time (more trips per vehicle) `[V]` and delivery deadlines (H12).

**H3 — Eliminate empty trips with return cargo.** `[V]`
- Based on: WIKI tipstricks ("minimize empty time"; vehicles refit automatically at stations) and §M1 (income only for delivered items).
- Examples of natural outbound/return pairs (from `cargo_economy.md` §2/§4): Coal/Iron Ore → Steel Mill and Steel/Sheet Metal back; Tools to mines and Coal to Steel Mill on the return trip; Crude Oil → Oil Refinery and Fuel/Chemicals back. `[I]` (must fit the body types: BULK/FLATBED/GOODS/LIQUID classes in `cargo_economy.md` §1).

**H4 — Serve both sides of a chain in the right ratio.** `[V]` for the rule, `[I]` for practice
- Based on: `cargo_economy.md` §2 — rules have fixed ratios (Steel Mill 6 Iron Ore : 6 Coal; Machines 7 Steel : 4 Plastic; Tinned Food 2 Fish or 2 Meat : 1 Sheet Metal).
- If one input is missing, the other accumulates in input stock (limit 400–800) and transport stalls. Adjust vehicle counts on each branch so the cheapest branch is not the bottleneck.
- Full output stock **destroys** production (§M3); if output stock is near its limit, collection is the bottleneck.

---

## B. Vehicle counts

**H5 — Add vehicles when origin stock rises and demand exists; remove them when line balance is negative and occupancy is low.** `[V]` basis, `[I]` thresholds
- Based on: §M3 (full stock destroys production), §M8 (line window shows capacity/rate/frequency and annual balance), §M9 (line `calculateBalance` ≈ income − operation/maintenance, excluding purchases and infrastructure).
- Signs to **add**: cargo waiting in industry output stock (HUD number) is growing or near the limit; unhappy passengers at the station ("increase the line rate", WIKI linesvehicles); high frequency in the line window.
- Signs to **remove**: negative annual line/vehicle balance or very low occupancy; vehicles bunching up on the same line.
- Before removing, check whether the line feeds a chain (H4) or a town (H12): its isolated balance does not capture indirect benefits. `[I]`
- Configured "Additional waiting time" spaces vehicles out; use it before adding another vehicle. `[V]` (§M8)

**H6 — Trains: buy a complete, compatible consist.** `[V]`
- Based on: WIKI tipstricks ("buy enough wagons, otherwise it loses money"; locomotive and wagons with similar top speeds) and §M8 (a platform shorter than the train reduces loading speed; matching specializations give a bonus).

**H7 — Departure mode: full load where cargo queues exist, "load if available" for passengers/frequent lines.** `[I]`
- Based on: §M8 (three modes; "any/all" only differ for trains/ships; other vehicles wait for a full load in both).
- *Full load* avoids empty trips from a cargo source (mine, farm), but holds the terminal and blocks other lines' turns. On passenger lines, waiting for a full load usually worsens happiness and frequency. Net effect: [?] depends on the station.

---

## C. Feeders × trunk lines

**H8 — High-capacity trunk line between centres + cheap neighbourhood feeders.** `[I]` (combination of verified facts)
- Based on: §M5 (each station only serves its catchment radius, 150–200 m for large stations), §M1 (passenger income depends on distance between origin and final destination, not the number of legs), WIKI tipstricks (station outside the centre: connect with bus/tram/truck to extend reach).
- Trunk: few stops, large and fast vehicles, long distance (H2).
- Feeder: short bus/tram routes to the trunk station; several stops within town.
- Caution `[I]`: each transfer adds waiting time (happiness, §M2) and income still measures origin to final destination; a feeder that is worthwhile on its own can show a loss in its balance yet still be justified by the trunk's catchment. Judge the whole network.

**H9 — To connect towns, place stops at several points in each town rather than a single terminal.** `[V]`
- Based on: §M5 (limited catchment radius; passengers need a valid path) and WIKI tipstricks.
- Passengers travelling between neighbouring or distant towns give more XP to the destination town (10/20 versus 5 within the same town; §M2) — good for the long term (H12).

---

## D. Industries: increase production and avoid losing them

**H10 — Serving a primary source well makes it grow; abandoning it may close it.** `[V]`
- Based on: §M3 (expansion probability clamps (rating−0.25)/0.5 to 0–1; rating is productionRating multiplied by the shipped/produced ratio, capped at 1) and §M4 (closure after years without consumption/loading; default "Rarely").
- For growth: collect a large share of industry production (rating near 0.75 ⇒ expansion almost certain; ≤0.25 ⇒ none). In practice: transport ≳75% of production. `[I]` (rating approximation).
- To avoid loss: do not leave an industry without loading/consumption for years; the signal is an "Industry Closing" notification with a 730-day countdown (§M4). If transport depends on it (H4), reactivate it before the countdown ends.
- Blocked plots (building over them or demolishing them) limit production (§M3): avoid building on fields.

**H11 — Consider the worker booster: a cheap bus line may yield +50% to +150% production.** `[V]` for the mechanism, `[I]` for cost-benefit
- Based on: §M3 — with ≥10 visitors arriving by line (50% of capacity 20) within a two-year window, productivity becomes the industry's "potential" (1.5–2.5; default 2).
- The visitor-count condition is demanding for isolated industries: the bus must connect a town with residents to the industry, with passengers arriving by line (not car).
- The gain is worth more where cargo transport already carries production away (H5); otherwise it creates more idle stock (and destruction).
- Compare with the cargo booster (Tools/Machines/Fertilizer): it consumes input stock (§M3, `cargo_economy.md` §2) and multiplies production by 1+f, with f randomly drawn from 0.5–1.5. Which is worthwhile depends on the cost of transporting the input. `[?]`

**H11b — Choose industries to invest in with the climate in mind.** `[V]`
- Based on: `cargo_economy.md` §3 — not every industry exists in every climate (e.g. Paper Mill/Printing Press only in subarctic). The complete Vehicles chain (tier 2) exists only in tropical (§4 there).

---

## E. Towns: growth yields passengers and demand

**H12 — To grow: meet commercial/industrial cargo demand, keep ratings green, and use the passenger network.** `[V]`
- Based on: §M2.
  - Final XP = raw XP × (authority/supply factor 0–1). Authority = the **worst** of six ratings (reputation, happiness, delivery, traffic, noise, pollution). Improving the worst rating has the greatest effect.
  - Supply = average of passengers (50% usage is enough) and cargo (**the best** district).
  - The authority×supply table shows that "Excellent" requires authority 5/5 and supply ≥4/5.
- Practical steps:
  - Meet each town's commercial and industrial demands (shown in its panel). New demands appear at levels 5, 7, 9, 11, and only if the town has already received some cargo (§M2). Revisit cargo lines when a town levels up (WIKI tipstricks).
  - Complex cargo types yield more XP per item (tier 0/1/2 = 10/20/40) but are demanded in smaller quantities (factor 1/0.5/0.25). Do not assume tier 2 is the best XP source: there is only one tier 2 cargo (Vehicles, industrial), and it requires the longest chain.
  - Avoid late deliveries: cargo past its deadline does not reduce income, but reduces the Delivery rating, which enters the authority minimum (§M2, §M12). Meat and perishables have the shortest deadlines (Meat 900; Vegetables/Fish/Beverages 1125).
  - Do not destroy buildings or trees near towns intended to grow; earthworks also affect reputation (WIKI towns/tipstricks).
  - Noise and pollution from vehicles/stations near residential areas lower ratings; prefer cleaner vehicles near neighbourhoods (noise and pollution values are in each vehicle's shop entry, WIKI linesvehicles). `[I]`
- Growing towns increases world population → raises **company rank** (perks, §M11), but inflation reduces income per item as rank rises (§M1). See H17.

**H12b — Where Delivery is a town's lowest rating, keep the late share small, not just "mostly on time".** `[?]`
- Based on: `mechanics.md` §M13, §M12, §M2. The rescale comes from MPFever's reading of the game's rating code and has not been checked against the game's own script.
- At the default sensitivity the on-time fraction is rescaled so that 0.30 rates 0 and 1.0 rates 1 (§M13 table). `[INFERENCE]` A raw 90% on time then rates about 0.86, 80% about 0.71 and 70% about 0.57, and because authority is the lowest of the ratings (H12), a modest late share can be what holds growth back.
- Compare the town's displayed Delivery rating with transit time against the cargo's deadline (`cargo_economy.md` §1) before acting; the collector does not emit per-line late counts (see `snapshot_schema.md`, collector gaps).

---

## F. Maintenance and replacement

**H13 — Before replacing based on age, check condition (`maintenanceState`) and nearby maintenance.** `[V]` basis, `[I]` decision rule
- Based on: §M6.
  - `maintenanceState` ≤0.4 ("Poor/Very Poor") with "Vehicle Maintenance Effect" ≥Medium ⇒ speed/power/comfort fall; noise, pollution and costs rise.
  - A depot or maintenance workshop repairs vehicles in its radius; workshops have larger radii; a waypoint can force the route through one.
- Practical order `[I]`:
  1. Vehicle in poor condition on a profitable line: build/adjust a workshop or waypoint near the route.
  2. If condition remains low, or a new model is much faster/larger, replace it ("replace" button; WIKI linesvehicles).
  3. Age itself matters less: the game's `lifespan` values are 40–116 years (if the unit is days; §M6), longer than most games; actual lifespan only matters in long games. `[?]` (effect of exceeding it unverified).
- An old but well-maintained vehicle with a good balance does not need replacement.

**H14 — Check balance per vehicle, not just per line.** `[V]`
- Based on: §M8/§M9 (balance charts per vehicle and line).
- An old vehicle with high running costs can be sold without changing the line. `[I]`

---

## G. Debt and cash

**H15 — Loans: fixed interest on the original principal ⇒ longer terms cost less per year; early repayment stops interest.** `[V]` from reading code; **differs from the wiki**
- Based on: §M7.
  - Total interest = amount × `percentage`, independent of term; cost/year ≈ `percentage ÷ years`.
  - Early repayment books only the remaining principal; future interest is not charged.
  - Maximum four loans; a new offer only 4–8 months after taking one of the same type.
- Heuristic `[I]`:
  - To finance infrastructure/fleets that yield returns for many years, a long-term Large/Extra Large loan has a low annual cost (e.g. 10–12% ÷ 10–24 years ≈ 0.4–1.2%/year of the amount), but the **monthly instalment** (principal ÷ months + interest) must fit cash flow. Size the fleet for monthly cash flow, not just "annual profit".
  - Short-term Small loans (1–5 years, 3–5%) are the most expensive annually (up to 3–5%/year) — use only to cover short gaps.
  - Repay when cash exceeds a reserve (to avoid lacking money to buy vehicles/fix lines).
- **Discrepancy to test:** the wiki (old revision) mentions a "monthly rate" and "annual payments at 15-day intervals". If the snapshot shows monthly `interest` greater than amount × percentage ÷ months, the wiki is correct and this heuristic should be revised.

**H16 — Expect losses in the first months of a large network.** `[V]`
- Based on: WIKI tipstricks (initial investment may cause losses for a few months) and §M7. Provide cash and a loan term covering this period.

---

## H. Time, inflation and difficulty

**H17 — Do not judge old lines only by their old income.** `[V]`
- Based on: §M1 (inflation multiplier by rank; default Normal reaches ×0.75 at rank 15) and §M11.
- Income per item falls as company rank rises; compensate with volume/distance/capacity, not just more short routes.

**H17b — Before attributing falling income to rank, check which rank is in force.** `[?]`
- Based on: §M14, §M1, §M11. Experience is the highest world population the game has seen, so it never falls; a rank can be reached without being taken. Whether inflation and perks follow the rank taken or the rank reached is unverified.
- If the company window shows a rank reached but not taken, compare income per item before and after taking it; until then, do not assume which rank drives the decline in H17.

**H18 — Confirm game difficulty before calibrating.** `[V]`
- Based on: `base/mod.json`, `BASE:difficulty_util.tl` (§M1, §M3, §M4, §M6).
- Income ×0.5–1.5; vehicle/infrastructure/maintenance costs ×0.5–1.5; industry productivity ×0.5–2; closure ×0–8; maintenance effect ×0–2. The snapshot should contain these parameters (otherwise ask the player).

**H19 — Subsidies: accept only when the objective matches something that would be done anyway.** `[V]` for the rules, `[I]` for evaluation
- Based on: WIKI subsidies — declining has no cost; failure reverses the advance payment and may incur a fine; "Fair/Risky/Very Risky" risk shortens the deadline and raises the target. Rewards: money, town XP, temporary 2× income.
- Types: supply an idle industry, supply a town, connect towns, transport workers (fits H11).

---

## I. Building near towns and stops

**H20 — Count the town buildings a street upgrade takes, not only its price.** `[?]`
- Based on: §M16, §M2. Upgrading a street through a town moves or removes town buildings and places them again at random spots. One measured example (build 40420, inferred; large community map) cost 8.4 M and removed 35 town buildings with the engine's own upgrade. Terrain edits and automatic removal also feed the town script's scoring of a build, which lowers reputation by an unmeasured amount.
- For a town meant to grow (H12), treat an upgrade through a built-up street as a cost in buildings and reputation as well as money; the size of the reputation effect needs a before-and-after read of the rating.

**H21 — Undo a building mistake before saving and reloading.** `[?]`
- Based on: §M16. Demolishing something just built can refund its cost, but only on the game that built it, and only while the interface still remembers it; the list is forgotten after a reload, and a plain removal costs money. The refund window and percentage are unverified.

**H22 — If a new bus or tram stop does not appear, check that the street has sidewalk lanes.** `[?]`
- Based on: §M16, §M5. On a street without sidewalk lanes the stop tool adds platform lanes; if that fails the engine accepts the build and silently drops the stop. This is one cause of "missing" stops, not the only one.

---

## How to use this list

- Present each heuristic to the player with: what was observed in the data, the mechanic, and the caveat.
- If snapshot data contradicts the premise (e.g. full industry but no waiting vehicle on the line), the heuristic changes.
- Do not present numerical thresholds as game rules: the only **code-based** thresholds are those cited in mechanics (0.25/0.75 for expansion; 50% line usage; ≥10 workers; 730 days; ≤0.2…0.8 for condition).

---

## Sources and gaps

**Verified in mechanics:** all `[V]` items cite sections of `mechanics.md`/`cargo_economy.md` and, through them, game files (`economy.zip`, `game_mechanics.zip`, `industries/*.con.lua`, `cargos/*.cargo.lua`, `scripts.zip`, `base/mod.json`) and the official wiki (`gamemanual:simulation:*`, `management:*`, `infrastructure:stationsdepots`, `gettingstarted:tipstricks`).

**Gaps affecting the heuristics:**
- Actual effect of speed on income and per-vehicle costs (`runningCosts`) — no number; comparisons require actual in-game balance.
- Degradation rate of `maintenanceState` and exact effect on stats — unverified; H13 is qualitative.
- Actual annual industry production and how level/boosters change it — use snapshot data.
- Occupancy thresholds for adding/removing vehicles (H5) are practices, not specified by the game.
- Interest discrepancy (H15) between wiki and code.
- Whether worker and cargo boosters stack (H11).
- `vehiclePriceFactor` (comfort/ticket price) per vehicle.
- Vehicle Factory behaviour outside the tropical climate.
- Reputation cost of terrain edits and street upgrades, refund window, and the rating rescale behind H12b, H17b and H20 to H22 rest on imported, unverified evidence (§M13, §M14, §M16).
