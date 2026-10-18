# Methodology fields

The facts an analysis methodology may read. A methodology names these fields in conditions, measures, message
templates, tables and charts; it can never change them. The list is generated from the field registry in
`src/tf3companion/methodology/fields.py` (regenerate with `uv run python -m tf3companion.methodology.catalog_doc`),
so every field here exists in this companion release.

Two outcomes when a rule names a field:
- the name is **not in this list**: the rule is *unsupported* (reason `unknown field`, with the nearest name when close);
  the file still loads and every other rule is evaluated;
- the name is in this list but the save's snapshots do not carry its source data: the rule is *skipped*
  (reason `missing data: <snapshot path>`).
A single entity whose own value is missing is *not evaluable* for that rule; a missing value is never zero, never an
empty string and never satisfies a condition.

Fields marked **not collected yet** need data the bridge mod does not emit in this release (station positions);
rules using them are skipped until the collector provides it.

`<entity>.line.<field>` (for `vehicle` and `stop`) reads any `line.*` field below for the entity's line, for example
`vehicle.line.name` or `stop.line.carrier`. `line.name_capture.<name>` (also `vehicle.line.name_capture.<name>`) is a
named group captured by the first matching `name_patterns` entry; it is missing when no pattern matches. Every entity
has a `<entity>.role` field holding the role this methodology assigned, or `unclassified`.

Measurement caveats apply to every methodology: `line.load` is instantaneous and `profitYear` is a rolling query-window
observation, never calendar income. Ages use `game-calendar-v1`: 365.25 elapsed Gregorian calendar days per GAME-YEAR,
with exact dated anchors or bounded interpolation spanning at least seven days. Unsupported purchases are unknown,
never nominal-duration estimates. Line age is the oldest currently assigned vehicle proxy, not creation or first observation.

## line

| Field | Type | Source (snapshot path) | Meaning and caveat |
|---|---|---|---|
| `line.age_years` | number | `vehicles[].purchaseTime`, `meta.date`, `(dated history and scope)` | Oldest currently assigned vehicle age proxy, in calendar GAME-YEAR. **Caveat:** Not line creation or first-observed age. Exact anchors or bounded interpolation only; 365.25 calendar days per GAME-YEAR; unsupported purchases are unknown. |
| `line.cargo_ids` | list[number] | `lines[].capacity[]` | Cargo ids with positive capacity on the line. **Caveat:** capacity[].cargo minus one. |
| `line.cargo_keys` | list[string] | `lines[].capacity[]`, `cargos[].res` | Language-neutral cargo keys (segment of the cargo resource path, for example `grain`). |
| `line.cargo_names` | list[string] | `lines[].capacity[]` | Cargo names with positive capacity, as the game shows them. **Caveat:** Names follow the game language; use line.cargo_keys for language-neutral matching. |
| `line.carrier` | string | `vehicles[].carrier` | Transport mode of the line: ROAD, RAIL, TRAM, WATER or AIR (most common among its vehicles). **Caveat:** Missing for lines without vehicles. |
| `line.first_stop_town` | number | `lines[].stops[].stationGroup`, `stations[].townName` | Town of the line's first stop. **Caveat:** Missing when the first stop's station group is absent from stations[]. |
| `line.id` | number | `lines[].id` | Entity id of the line. |
| `line.is_passenger_only` | bool | `lines[].capacity[]` | True when every positive-capacity entry of the line is passengers (cargo id 0). **Caveat:** capacity[].cargo is the cargo id plus one. Missing when the line has no positive capacity (for example no vehicles). |
| `line.issue_types` | list[string] | `lines[].issues[]` | Configuration issue types reported for the line. |
| `line.load` | number | `lines[].capacity[]` | Occupancy of the line's vehicles, 0 to 1. **Caveat:** Instantaneous reading at snapshot time, not an average. |
| `line.loss_year` | number | `lines[].profitYear` | Loss over the rolling game year: max(0, -profit_year). **Caveat:** Rolling game year, not calendar income; partial for lines younger than a year. |
| `line.name` | string | `lines[].name` | Line name as typed in the game. |
| `line.profit_year` | number | `lines[].profitYear` | Rolling game-year profit of the line. **Caveat:** Rolling game year, not calendar income; partial for lines younger than a year. |
| `line.rate` | number | `lines[].rate` | Line throughput rate reported by the game. |
| `line.role` | string | `(methodology roles)` | Role this methodology assigned to the line, or `unclassified`. |
| `line.route_km` | number | `stations[].position`, `lines[].stops[].stationGroup` | Straight-line length of the line through its stops, in kilometres. **Caveat:** Needs station positions, which the collector does not emit yet. Chain of straight legs, not track length. **Not collected yet.** |
| `line.stop_count` | number | `lines[].stops` | Number of stops on the line. |
| `line.stop_distances_km` | list[number] | `stations[].position`, `lines[].stops[].stationGroup` | Straight-line distance of each leg between consecutive stops, in kilometres. **Caveat:** Needs station positions, which the collector does not emit yet. **Not collected yet.** |
| `line.stop_towns` | list[number] | `lines[].stops[].stationGroup`, `stations[].townName` | Distinct towns of the line's stops, from each stop's station group (never from name codes). **Caveat:** Stops whose station group is absent from stations[] contribute no town. |
| `line.town_count` | number | `lines[].stops[].stationGroup`, `stations[].townName` | Number of distinct towns the line's stops belong to. **Caveat:** Missing when no stop resolves to a town. |
| `line.transported_year` | number | `lines[].transportedYear` | Items transported over the rolling game year. **Caveat:** The accounting interpretation of transportedYear is unverified. |
| `line.vehicle_count` | number | `lines[].vehicles` | Number of vehicles assigned to the line. |

## vehicle

| Field | Type | Source (snapshot path) | Meaning and caveat |
|---|---|---|---|
| `vehicle.age_years` | number | `vehicles[].purchaseTime`, `meta.date`, `(dated history and scope)` | Vehicle age in calendar GAME-YEAR. **Caveat:** Exact anchors or bounded interpolation only; unsupported old purchases are unknown; no nominal fallback. |
| `vehicle.carrier` | string | `vehicles[].carrier` | Transport mode of the vehicle. |
| `vehicle.days_in_depot` | number | `vehicles[].daysInDepot` | Days the vehicle has been in a depot. |
| `vehicle.id` | number | `vehicles[].id` | Entity id of the vehicle. |
| `vehicle.line_id` | number | `vehicles[].line` | Id of the line the vehicle is assigned to. |
| `vehicle.maintenance_state` | number | `vehicles[].maintenanceState` | Maintenance condition, 0 to 1 (1 = excellent). |
| `vehicle.model_family` | string | `vehicles[].models`, `models[].res` | Vehicle family from the model resource path. Observed in a real snapshot: `bus`, `truck`, `plane`, `helicopter`, `ship`. |
| `vehicle.name` | string | `vehicles[].name` | Vehicle name. |
| `vehicle.profit_year` | number | `vehicles[].profitYear` | Rolling game-year profit of the vehicle. **Caveat:** Rolling game year, not calendar income. |
| `vehicle.role` | string | `(methodology roles)` | Role this methodology assigned to the vehicle. |
| `vehicle.state` | string | `vehicles[].state` | Vehicle state reported by the game. |
| `vehicle.value` | number | `vehicles[].value` | Recorded resale value. |

## stop (a stop of a line; aggregate rules only)

| Field | Type | Source (snapshot path) | Meaning and caveat |
|---|---|---|---|
| `stop.line_id` | number | `lines[].id` | Id of the line the stop belongs to. |
| `stop.station` | number | `lines[].stops[].stationGroup` | Station group id of the stop. |
| `stop.station_name` | string | `stations[].name` | Station group name. |
| `stop.terminal` | number | `lines[].stops[].terminal` | Terminal (platform or gate) the stop uses. **Caveat:** Only the terminals used by the player's lines are known; the station's total terminals are not collected. |
| `stop.town` | number | `lines[].stops[].stationGroup`, `stations[].townName` | Town of the stop's station group. **Caveat:** Missing when the station group is absent from stations[]. |

## industry

| Field | Type | Source (snapshot path) | Meaning and caveat |
|---|---|---|---|
| `industry.closing` | bool | `industries[].closureTimeStamp`, `problems.closingIndustries` | Whether the industry is scheduled to close. |
| `industry.id` | number | `industries[].id` | Entity id of the industry. |
| `industry.input_delivery_ratio` | number | `industries[].inputs[].deliveredYear`, `industries[].inputs[].maxConsumptionYear` | Delivered over maximum consumption, summed over all inputs, per rolling game year. **Caveat:** Missing for industries without inputs. Rolling game year. |
| `industry.level` | number | `industries[].level` | Current production level. |
| `industry.name` | string | `industries[].name` | Industry name. |
| `industry.production_rating` | number | `industries[].productionRating` | Production rating reported by the game. |
| `industry.role` | string | `(methodology roles)` | Role this methodology assigned to the industry. |
| `industry.shipped_ratio` | number | `industries[].outputs[].producedYear`, `industries[].outputs[].shippedYear` | Shipped over produced, summed over all outputs, per rolling game year. **Caveat:** Missing when the industry produces nothing. Rolling game year. |
| `industry.type` | string | `industries[].type` | Industry resource path, for example `::/industries/oil_refinery/oil_refinery.con`. |

## stock

| Field | Type | Source (snapshot path) | Meaning and caveat |
|---|---|---|---|
| `stock.capacity` | number | `stocks[].capacity` | Stock capacity in units. |
| `stock.count` | number | `stocks[].count` | Units in the stock. |
| `stock.fill_ratio` | number | `stocks[].count`, `stocks[].capacity` | Stock fill, count over capacity, 0 to 1. **Caveat:** Instantaneous reading. Full destination stocks can prevent unloading. |
| `stock.kind` | string | `stocks[].kind` | Stock owner kind: station, industry or warehouse. |
| `stock.owner_name` | string | `stocks[].ownerName` | Name of the stock's owner. |
| `stock.role` | string | `(methodology roles)` | Role this methodology assigned to the stock. |

## town

| Field | Type | Source (snapshot path) | Meaning and caveat |
|---|---|---|---|
| `town.capacity_sum` | number | `towns[].capacities` | Sum of residential, commercial and industrial capacities. **Caveat:** A proxy for population [INFERENCE]. |
| `town.id` | number | `towns[].id` | Entity id of the town. |
| `town.line_usage` | number | `towns[].lineUsage` | Share of the town using the player's lines. |
| `town.name` | string | `towns[].name` | Town name. |
| `town.pair_distance_km` | list[number] | `stations[].position`, `lines[].stops[].stationGroup` | Straight-line distances from this town to the other towns its lines connect, in kilometres. **Caveat:** Needs station positions, which the collector does not emit yet. Centre = mean of the town's stations. **Not collected yet.** |
| `town.role` | string | `(methodology roles)` | Role this methodology assigned to the town. |
