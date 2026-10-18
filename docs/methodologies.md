# Analysis methodologies

A **methodology** is one JSON file that says how *you* want your company judged: which lines are "local feeders" and
which are "trunks", how much loss each may carry, what to do about it, and which reports matter. The engine keeps
computing the facts (profit, load, stock fill, ages); the methodology only decides how those facts are classified,
judged and presented. It contains no code, loads nothing from elsewhere and never touches the network.

| Layer | Owns | Lives in |
|---|---|---|
| Game mechanics | How the game works, with `[V]`/`[I]` labels | `knowledge/*.md` (shared, not overridable) |
| Evidence | Per-save snapshots, decisions, notes | the companion store |
| Methodology | Roles, tolerances, markers, rules, recommendations, report selection | one `.tf3c-methodology.json` file |
| Engine | Computing facts, the field catalog, finding builders, caveat text, rendering | `src/tf3companion/` |

A methodology can never change a measured value, a data caveat or game knowledge: the same snapshots under two
methodologies give the same numbers, different markers.

## Quick start

```bash
tf3c methodology list
tf3c methodology validate my-methodology.tf3c-methodology.json --strict
tf3c methodology import my-methodology.tf3c-methodology.json
tf3c methodology use my-methodology
tf3c analyse
tf3c analyse --methodology default
tf3c findings --methodology my-methodology
tf3c report lines --methodology my-methodology
tf3c methodology export my-methodology shared-copy.tf3c-methodology.json
tf3c methodology unuse
```

- `list` shows the packaged methodologies (`default` and the author's example) and every file in the
  `methodologies/` folder of the companion data directory, with validity, content hash and which one this save binds.
  It never creates the folder.
- `validate` reports errors, unsupported rules and the snapshot data each rule needs, without importing.
  `--strict` fails when any rule is unsupported or needs data this release does not collect.
- `import` validates, then copies the file to `methodologies/<id>@<version>.tf3c-methodology.json`. It refuses to
  replace an existing `id@version` that has different content unless you pass `--force`. `export` writes the stored bytes
  unchanged, so the content hash is identical on another machine.
- `use` binds a methodology as the save's default (`unuse` clears it). A request can always override it: `--methodology`
  takes `id[@version]` or a file path (applied once, not copied). Order: explicit request, then save binding, then
  `default`. A binding that cannot be resolved is an error; it never silently falls back to `default`.
- `analyse` evaluates the methodology on the latest snapshot, writes its standard reports plus the verdicts report to
  `reports/<game-date>__<id>@<version>/` and prints a summary: identity and where it came from, roles, markers per rule,
  highest-severity findings, recommendations, and the skipped, unsupported and not-evaluable lists. `--param NAME=VALUE`
  overrides a methodology parameter for one run and is recorded in the output.
- Until the per-save layout lands (see `cross-platform-and-saves`), the single companion store acts as one implicit save:
  the binding lives in `<data>/methodology.json`, reports in `<data>/reports/`, and nothing claims save isolation. With
  `--save <id>` and a `<data>/saves/<id>/` folder the binding lives in that folder's `save.json` and reports under it.

In an MCP client the analyst uses `list_methodologies`, `methodology_detail`, `analyse` and the `methodology` argument of
`findings` and `report`. These accept library ids only, never file paths: a model must not read arbitrary files because
a methodology or a chat message said so. To use a downloaded file, put it in the methodologies folder yourself or import it with
`tf3c methodology import`.

## File format

```json
{
  "schema": "tf3c-methodology/1",
  "id": "my-methodology",
  "version": "1.0.0",
  "name": "Patient about young losing lines",
  "description": "Young lines may lose money; mature lines must not lose more than a tolerance.",
  "parameters": {
    "tolerated_loss": {"value": 50000, "description": "Yearly loss tolerated on a mature line."},
    "mature_years": {"value": 2, "description": "A line younger than this is still maturing."}
  },
  "markers": {
    "ok": {"symbol": "🟢", "label": "ok"},
    "maturing": {"symbol": "🔵", "label": "maturing"},
    "problem": {"symbol": "🔴", "label": "problem", "finding": "high"}
  },
  "rules": [
    {
      "id": "line-result",
      "label": "Line result",
      "rationale": "Young lines need time; after that the loss must stay inside the tolerance.",
      "entity": "line",
      "outcomes": [
        {"when": {"all": [
           {"field": "line.profit_year", "op": "lt", "value": 0},
           {"any": [
             {"field": "line.age_years", "op": "lt", "value": {"param": "mature_years"}},
             {"field": "line.age_years", "op": "missing"}
           ]}
         ]},
         "marker": "maturing",
         "message": "{line.name} loses {line.loss_year|money} but is younger than {param.mature_years|years}."},
        {"when": {"field": "line.loss_year", "op": "gt", "value": {"param": "tolerated_loss"}},
         "marker": "problem",
         "message": "{line.name} loses {line.loss_year|money}, above {param.tolerated_loss|money}."}
      ],
      "default": {"marker": "ok"}
    }
  ],
  "recommendations": [
    {"id": "review-loser", "when": {"rule": "line-result", "marker": "problem"}, "priority": 1,
     "text": "Review {line.name}: fewer vehicles, a shorter route or a merge."}
  ],
  "reports": {"kinds": ["company", "lines", "towns"]}
}
```

Top-level keys: `schema` (always `tf3c-methodology/1`), `id` (lowercase letters, digits and single hyphens), `version`
(three-part number), `name`, `description` (required) and `author`, `parameters`, `markers`, `name_patterns`,
`definitions`, `roles`, `engine`, `rules`, `recommendations`, `ladders`, `reports`. An unknown key anywhere is an error
that names its location. The file extension is `.tf3c-methodology.json`; the published JSON Schema
(`src/tf3companion/methodology/schema-1.json`, usable as `"$schema"`) gives editor completion for the structure.
The companion's validator is authoritative: it additionally checks references, regular expressions, limits, engine
threshold names and finding codes.

### Conditions

A condition is a tree: `{"all": [...]}`, `{"any": [...]}`, `{"not": ...}`, `{"ref": "<definition>"}` (a reusable
condition from the top-level `definitions`, validated acyclic) or a leaf
`{"field": "line.profit_year", "op": "lt", "value": 0}`. `value` is a literal or `{"param": "<name>"}`.

| Operator | Meaning |
|---|---|
| `eq` `ne` `lt` `le` `gt` `ge` | comparison of a number (or `eq`/`ne` of a string or boolean) |
| `in` `not_in` | the field's value is (not) one of a literal list |
| `matches` | bounded regular expression search in a string (or any element of a list); case-sensitive |
| `contains_any` | a list field shares an element with the literal list |
| `exists` `missing` | take no value; the only operators that turn a missing value into a definite answer |

**Missing is not zero.** Evaluation is three-valued (Kleene): a leaf over a missing value is *unknown*. `all` is false if
any part is false, else unknown if any part is unknown; `any` is true if any part is true, else unknown; `not unknown` is
unknown. A rule fires only on *true*. Outcomes are tried in order and the first true one wins; if an earlier outcome is
unknown and a later one is true, the entity is reported as *not evaluable* instead of receiving the later marker, because
the earlier outcome might have applied. Use `exists`/`missing` to state fallbacks explicitly, and guard comparisons you
combine with a fallback:

```json
{"any": [
  {"all": [{"field": "line.name_capture.scope", "op": "exists"},
           {"field": "line.name_capture.scope", "op": "eq", "value": "LO"}]},
  {"all": [{"field": "line.name_capture.scope", "op": "missing"},
           {"field": "line.town_count", "op": "le", "value": 1}]}
]}
```

Without the `exists` guard the first branch is unknown whenever the capture is missing, which would make the whole
`any` unknown even though the second branch is false.

### Roles

`roles` assigns each entity of a kind (`line`, `vehicle`, `industry`, `stock`, `town`) one role: an ordered list of
`{id, label, select}`; the first selector that is true wins. An entity that matches none is `unclassified` and counted,
never dropped. If a selector before the winner was unknown the entity is also unclassified (and counted as unknown), for the
reason above. Selectors can use anything in the field catalog: carrier, passenger-only capacity, cargo, number of towns,
industry type, and optionally name captures. A name pattern is never required:

```json
"name_patterns": {"line": [{"id": "coded", "pattern": "^(?P<mode>\\S+) .*?-(?P<scope>LO|IC|RE)-(?P<n>\\d+)$"}]}
```

Patterns are tried in order; captures come from the first one that matches and are read as `line.name_capture.<name>`.
Towns never come from name codes: `line.stop_towns` and `line.first_stop_town` come from each stop's station group, so two
towns that share an abbreviation stay distinct. A stop whose station group is absent from the snapshot has a missing
town, which is excluded and counted as not evaluable.

### Rules, markers and messages

A rule selects entities by `entity` (and optionally `role`) and evaluates ordered `outcomes` of
`{when, marker, message}`, plus an optional `default`. A **marker** is yours: a `label`, a display `symbol`, and a
`finding` severity (`high`, `medium`, `low`) or none. Only markers with a `finding` produce findings
(`rule:<rule-id>`, `source: "methodology"`); the others are shown in the verdicts tables. Messages use `{path}` or
`{path|fmt}` placeholders over catalog fields of the rule's entity, `{param.<name>}` and, in aggregates, `{group}` and the
rule's measures. Formats: `money` (`150,000`), `pct` (`90%`), `int`, `km` (`95.0 km`), `years` (`3 years`), `text`.
`{{` and `}}` are literal braces. A missing value prints `n/a`. There are no expressions and no nested templates.

### Aggregate rules

Group entities by a key and judge the group, for example the balance of a town:

```json
{"id": "town-balance", "entity": "line", "aggregate": {
  "group_by": "town",
  "measures": {
    "local_result": {"agg": "sum", "value": "line.profit_year",
                     "where": {"field": "line.role", "op": "eq", "value": "local-passenger"}, "via": "line.first_stop_town"},
    "local_lines":  {"agg": "count",
                     "where": {"field": "line.role", "op": "eq", "value": "local-passenger"}, "via": "line.first_stop_town"}
  },
  "having": {"measure": "local_lines", "op": "gt", "value": 0},
  "outcomes": [{"when": {"measure": "local_result", "op": "lt", "value": 0}, "marker": "watch"}],
  "default": {"marker": "ok"}
}}
```

Measures are `sum`, `count`, `distinct_count`, `min`, `max` and `ratio` (numerator and denominator are earlier
measures, the numerator optionally `negate`d). `where` filters members; `via` names the field that gives the group key a
member contributes through (for example the first town versus every distinct town); `distinct_by` counts each underlying
entity once; `having` restricts groups and may use `{"any_member": <condition>}`. `ratio` is missing when the denominator is not
positive. Entity kind `stop` (every stop of every line, with `stop.line.*`) is available for aggregates only.
`group_by` is `town` (every measure then needs a `via`) or a field such as `stop.station`.

### Recommendations and ladders

A recommendation names a rule, a marker and optionally a role, plus a priority 1 to 5 and a text template. Its text comes
only from your template with measured values filled in, and each one carries an evidence reference (rule, entity, values).
A recommendation whose trigger rule is unsupported or skipped is listed as skipped. A **ladder** maps distance bands to
transport modes and recommends a change when a line's carrier differs from its band's mode:

```json
"ladders": [{"id": "mode-by-distance", "entity": "line", "role": "intercity-passenger", "metric": "line.route_km",
  "bands": [{"max_km": 40, "mode": "ROAD"}, {"max_km": 150, "mode": "RAIL"}, {"mode": "AIR"}],
  "text": "{line.name} spans {line.route_km|km}; the band suggests {band.mode}, the line runs on {line.carrier}."}]
```

A distance below `max_km` belongs to that band (exactly 40 km is rail here). `line.route_km` needs station positions, which
the collector does not emit yet, so ladders are reported as skipped (`missing data: station positions`) until it does.

### Engine overrides

`engine.thresholds` overrides the engine's named thresholds (`overloaded_load`, `underused_load`,
`underused_min_vehicles`, `mature_years`, `idle_depot_days`, `unshipped_ratio`, `profit_drop_ratio`, `min_profit_drop`,
`full_stock_ratio`, `trend_snapshots`, `trend_min_samples`, `fit_improvement`); `engine.findings` switches a built-in
finding off or changes its severity by stable code, optionally for one role:
`{"code": "line_losing_money", "role": "local-passenger", "action": "off"}` or
`{"code": "line_overloaded", "action": "set_severity", "severity": "low"}`. Unknown names make the file invalid. Disabled
findings are listed in the verdicts report. `mature_years` and `full_stock_ratio` also reach the `lines-history`,
`vehicle-roi` and `industries` reports.

### Reports, tables and charts

`reports.kinds` names the standard report set from the existing kinds (`company`, `lines`, `fleet`, `cargo`, `decisions`,
`annual`, `history`, `vehicle-roi`, `lines-history`, `industries`, `towns`, `expansion`, `bottlenecks`); the verdicts
report (`methodology`) is always added. Without `kinds` the set is `company`, `lines`, `fleet`, `cargo`. `reports.tables`
(`entity`, `role`, `sort`, `columns`, `limit`) and `reports.charts` (`type` `bar`, `pie` or `history_line`, `metric`, `agg`
`sum`/`count`/`mean`/`min`/`max`, `group_by` `role` or a field) come from a closed catalog and render in the verdicts
report; every chart is followed by a table with the same numbers. A methodology cannot add report kinds or free-form output.

## Field catalog

The facts a methodology may read are in the `methodology-fields` knowledge topic (`tf3c knowledge methodology-fields`, or the
`knowledge` tool) and `tf3c methodology fields [--entity line]`, both generated from the engine's registry. Each field
declares its type, entity, snapshot source and caveat. Strings observed in a real snapshot (Transport Fever 3, game language
Portuguese), to write patterns and lists against:

- `industry.type`: `::/industries/<kind>/<kind>.con`, for example `oil_platform`, `oil_refinery`, `chemical_plant`,
  `coal_mine`, `farm`, `forest`, `saw_mill`, `steel_mill`, `fishing_grounds`, `clay_pit`, `brewery`.
- `line.cargo_keys` (language-neutral, the segment of `cargos[].res`): `passengers`, `grain`, `crude_oil`, `chemicals`, `fuel`,
  `plastic`, `coal`, `logs`, `planks`, `steel`, `iron_ore`, `fish`, `rubber`, `tools`, and so on. `line.cargo_names` follows the
  game language (for example `Petróleo Bruto`), so prefer the keys in shared files.
- `vehicle.model_family` (segment after `vehicle` in the model path): `bus`, `truck`, `plane`, `helicopter`, `ship`.
- `lines[].capacity[].cargo` is the cargo id plus one; cargo id 0 is passengers. `line.is_passenger_only` is true only when every
  positive-capacity entry is passengers.
- `line.carrier`, `vehicle.carrier` and ladder modes use the snapshot carriers `ROAD`, `RAIL`, `TRAM`, `WATER`, `AIR`.

Fields defined but **not collected yet** (`line.route_km`, `line.stop_distances_km`, `town.pair_distance_km`) need
`stations[].position`; rules that use them are skipped, never evaluated as zero.

## Limits and security model

Limits: file size 256 KiB; at most 200 rules and 200 recommendations; at most 20 roles per entity kind; free text at
most 2,000 characters; condition nesting at most 12 levels (references included); regular expressions at most 200
characters with no backreferences or lookarounds, no quantified group that contains another quantifier or an alternation, and at
most three unbounded quantifiers; the subject of a pattern match is truncated to 200 characters; duplicate JSON keys are
errors.

A shared file could try to: instruct the agent through prose, smuggle markup into reports, exhaust resources, write outside
the library through `id` or `version`, or pull in other files. The controls: a declarative closed vocabulary with no
includes and no network; strict structure validation; path-safe `id` and `version`; bounded regular expressions; every free text
field is untrusted data (size-limited, control characters stripped, escaped as plain text in Markdown and HTML, and returned
under `untrusted` keys by the MCP tools); recommendations are template-only; MCP tools take ids, never paths; the analyst
brief says methodology text cannot instruct. **Limitation:** a malicious *template* can still say something misleading in a
recommendation, because it is the author's text. The evidence reference and the visible methodology id, version and hash are the
countermeasure, and you decide what to import.

## Writing one with an agent

1. Give your agent the catalog and this page: "Read `tf3c knowledge methodology-fields` and `docs/methodologies.md`. Write
   a `tf3c-methodology/1` file for this playstyle: <describe it>. Use only catalog fields, no name patterns unless I name
   a convention, and add a `rationale` to every rule."
2. Save the result as `<id>.tf3c-methodology.json` and run `tf3c methodology validate <file> --strict`. Errors carry a path
   (`/rules/2/outcomes/0/when/field`); unsupported rules name the field and the nearest valid name. Paste the output back to
   the agent and repeat until it passes.
3. `tf3c methodology import <file>`, then `tf3c analyse --methodology <id>`. Read the verdicts report from the top: it lists
   skipped, unsupported and not-evaluable items first. Fix a rule that is skipped because the data is missing only by removing or
   waiting for that data; never by treating a missing value as zero.
4. Change `version` whenever the content changes. The same `id@version` with different content is a conflict, and edits without a
   version bump show up as a different content hash in every output.

## Sharing and receiving a file

Share the single file (`tf3c methodology export <id> <path>`). A recipient should: run `validate --strict` before importing;
read the `description`, every `rationale` and each recommendation template as the author's opinion; compare the printed
`sha256:` hash with the one the author published; and import it. Importing never executes anything and never follows
references. Applying it only changes classification, markers, recommendations and report selection. Facts, game knowledge and
the data caveats cannot be changed, and the methodology id, version and hash are printed in every report header, finding,
manifest and `analyse` summary.

## Output and provenance

`analyse` writes `<save root>/reports/<game-date>__<id>@<version>/` (the date is the snapshot's `YYYY-MM-DD`, or `t<gameTime>`
when it has no calendar date) containing the standard reports, `methodology.md` (the verdicts report) and `manifest.json`:
methodology identity and hash, effective parameters, snapshot game time, files, and the skipped, unsupported and not-evaluable
lists. The folder is built beside the target and swapped in atomically, so rerunning on the same inputs overwrites it and an
interrupted run leaves the previous one. Two snapshots on the same game date share one folder (the manifest holds the game time
of the one used); two methodologies make two sibling folders. `tf3c report <kind>` writes into the same folder (`<kind>.md`,
`annual-<year>.md` for the annual report) and copies the Markdown to `reports/latest.md`. **Breaking:** the earlier flat
`reports/<kind>.md` files are no longer written; existing ones are left in place. Verdicts are computed from the stored snapshots
on demand and never stored, so changing a methodology never rewrites history.

## Report constants that stay report-local

Only thresholds that duplicate an engine `Thresholds` field are overridable in the reports: `mature_years` and
`full_stock_ratio`. These stay fixed inside the reports (adding one is a one-line registry change later):

- `industries`: evolution rows, event cap, bucket days, the 90% "below capacity" share and the 30-point level-decline rule.
- `lines-history`: noise factor, floor share, long-history years, sample and table caps, minimum points.
- `vehicle-roi`: minimum sample, model and cargo rows, age buckets, load-history settings, trend groups.
- `bottlenecks` and `expansion`: persistence streaks, noise shares, score budgets, chart caps; the `vehicle-roi` fit check builds
  its own default load thresholds.

## The author's port, and what it deliberately differs on

`local-feeder-intercity-trunk` is a port of the author's own rules (local feeders may lose money inside a town balance; intercity
lines must not lose relevantly; freight may lose money while maturing). It is the proof that the schema expresses a real policy.
Recorded fidelity decisions:

- Comparison directions follow the source: intercity loss and the town ratio are strictly greater than their tolerance (a loss
  of exactly 100,000 is `watch`), load is greater-or-equal, maintenance is strictly below its limits.
- A missing line age is treated as young in the freight rule through an explicit `missing` branch, reproducing the source's
  age 0 for lines without vehicles.
- Air stations use `stop.line.carrier == AIR` instead of the name modes `AP`/`AC`/`HC`. Aircraft per terminal is `watch` from
  3.0 and `problem` from 3.5 (parameters `air_per_terminal_watch` and `air_per_terminal_problem`). It stays a screening number:
  fleet of the lines divided by the terminals those lines use, not capacity, arrivals or a queue. Note: the current
  `data/analysis-rules.md` and `data/analise/common.py` describe a watch-only marker that never reaches red; delete the problem
  outcome from the example to match them.
- A stop with no station has a missing town (excluded and counted not evaluable) where the source used a `?` bucket.
- Vehicles with a missing maintenance state are not evaluable where the source defaulted to 1.0.
- The game-year basis is the engine's: `line.age_years` divides by `meta.yearDuration` and does not use the calibrated calendar year
  of the author's local scripts, so maturity thresholds in years can differ from those scripts' numbers until the engine adopts the
  calibration.
- The author's five pages are not one-to-one with report kinds; the port selects the nearest kinds.
