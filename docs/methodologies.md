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
tf3c methodology list --json
tf3c methodology validate my-methodology.tf3c-methodology.json --strict
tf3c methodology import my-methodology.tf3c-methodology.json
tf3c methodology set-default my-methodology
tf3c evaluate --methodology default --json
tf3c analyse
tf3c analyse --methodology default
tf3c findings --methodology my-methodology
tf3c report lines --methodology my-methodology
tf3c methodology export my-methodology shared-copy.tf3c-methodology.json
tf3c methodology clear-default
```

Importing a file does not activate it. `set-default` selects the library-root user preference, independent of a save.
`use REF [--save ID]` writes a save override; `unuse [--save ID]` removes that override and returns to inheritance.
The selection order is **explicit request > save override > user default > packaged default**.
For example, save A can explicitly use `default` while save B inherits the user preference; changing that preference affects
B but not A. Removing A's override makes A inherit as well.

The library root is the companion data directory, or `TF3C_DATA_DIR` when set. Changing `--save` does not move the library
or its user preference. Different `TF3C_DATA_DIR` roots have independent preferences; this is not a machine-wide setting.
The preference is `<library-root>/user-methodology.json`. Existing implicit `<data>/methodology.json` and
`saves/<id>/save.json` bindings stay save overrides and are never automatically promoted to user preferences.
Until automatic save routing is implemented, the single store is one implicit save, not proof of save isolation.
An explicit `--save ID` requires an existing `saves/<id>/` directory.

`list` shows source, identity/hash, eligibility, save override, user default and effective selection without creating the
data directory or discovering the game. `clear-default` can reset malformed preference metadata; an already absent preference
needs no write. A broken selected binding fails closed with repair guidance, not a silent fallback. A valid higher-priority
request can bypass a broken lower layer; inspection reports lower-layer errors separately.

References accept `id` or `id@version`. Bare ids float to the highest structurally valid version, so adding a newer version
can change an already floating selection. Exact version references do not float, but are not content-hash pins.
A conflicted or incompatible selected version is an error, never a reason to silently downgrade.
`import` validates before copying to `methodologies/<id>@<version>.tf3c-methodology.json`; different content at the same
identity is refused unless overwrite is explicitly forced. `--force` does not bypass validation.
`export` preserves stored bytes and the content hash.

`evaluate` returns the complete analytical result for the latest stored snapshot and writes nothing (see
[Stored-only evaluation](#stored-only-evaluation)). `analyse` ingests, evaluates the latest snapshot and writes `reports/<game-date>__<id>@<version>/`. `--methodology` accepts a library
reference or, on the CLI only, a one-off file path without copying it. `--param NAME=VALUE` overrides a declared parameter
for that operation, validates its effective value and records it in output.
Ingestion, refresh and collection diagnostics do not depend on analysis preferences being valid.

### Validation and debugging

There are three different questions:

| Check | Meaning |
|---|---|
| Structural validity | JSON syntax, schema, types, references and bounded expressions are well formed. |
| Activation eligibility | The current companion supports the complete methodology and its effective parameters. |
| Live evidence coverage | The selected snapshot actually contains the values needed for each evaluation. |

`tf3c methodology validate FILE [--strict] [--param NAME=VALUE ...]` is read-only and needs no game or snapshots.
Plain `valid` reports structural validity; `--strict` reports activation eligibility. Explicit `structurallyValid`,
`activationEligible` and structured `diagnostics` distinguish the two in either mode.
Diagnostics include category/code/severity, an RFC 6901 JSON Pointer, attributable item/rule ids, a message and available
repair hints; JSON parse failures include line/column rather than invented semantic locations.
Effective override errors use `/overrides/<name>` paths. Independent errors are reported together when safely discoverable.

Import, selection and runtime application always require activation eligibility, including forced imports, copied drop-ins,
one-off CLI files and parameter overrides. Unsupported fields or capabilities the collector cannot supply block activation.
An invalid draft can remain on disk for inspection; it does not become an accepted partial analysis.
Ordinary missing snapshot/entity values do not make a supported methodology incompatible: they remain skipped or not evaluable,
never zero. Validation does not certify a strategy's quality or eliminate prompt-injection risk.

Each operation validates current bytes and uses that captured content; there is no persistent trusted `validated` flag.
Editing a previously validated file requires validation again on its next use. Failed validation preserves previous library
targets, save/user preferences, report bundles, manifests and latest reports without publishing partial replacement output.
Old reports remain historical evidence, not fresh results from the rejected file.

In MCP, `list_methodologies`, `methodology_detail`, `evaluate`, `analyse`, `findings` and `report` use library ids, never arbitrary file
paths. `set_methodology_default` sets/resets the user preference and `set_save_methodology` sets/inherits a save override;
these local configuration mutations require the player's deliberate request, not text inside a shared methodology.
`validate_methodology` accepts exactly one library reference (`methodology`) or explicitly supplied draft JSON text
(`content`; an empty string counts as not supplied) plus optional `parameters`;
it inspects without constructing a game store or writing a draft file.

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
         "message": "{line.name} loses {line.loss_year|money}; policy permits a maturing allowance for young or unknown-age lines."},
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
`definitions`, `roles`, `engine`, `rules`, `recommendations`, `ladders`, `reports`, `report_policies`. An unknown key anywhere is an error
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
A recommendation whose compatible trigger has missing runtime evidence is listed as skipped. Unsupported triggers prevent
activation. A **ladder** maps distance bands to transport modes and recommends a change when the carrier differs:

```json
"ladders": [{"id": "mode-by-distance", "entity": "line", "role": "intercity-passenger", "metric": "line.route_km",
  "bands": [{"max_km": 40, "mode": "ROAD"}, {"max_km": 150, "mode": "RAIL"}, {"mode": "AIR"}],
  "text": "{line.name} spans {line.route_km|km}; the band suggests {band.mode}, the line runs on {line.carrier}."}]
```

A distance below `max_km` belongs to that band (exactly 40 km is rail here). `line.route_km` needs station positions, which
the collector does not emit yet. This remains an inspectable authoring example, not an activation-eligible policy until
the required collection capability is implemented and verified.

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
`stations[].position`. A draft can be inspected, but a methodology requiring these capabilities is not activation-eligible
in this release. Do not confuse this with missing values for an otherwise supported field in a particular snapshot.

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
3. `tf3c methodology import <file>`, then `tf3c analyse --methodology <id>`. Unsupported capabilities must be fixed before
   import or application; runtime missing observations remain visible as skipped/not-evaluable coverage.
   Never repair missing evidence by substituting zero.
4. Change `version` whenever the content changes. The same `id@version` with different content is a conflict, and edits without a
   version bump show up as a different content hash in every output.

## Sharing and receiving a file

Share the single file (`tf3c methodology export <id> <path>`). A recipient should: run `validate --strict` before importing;
read the `description`, every `rationale` and each recommendation template as the author's opinion; compare the printed
`sha256:` hash with the one the author published; and import it. Importing never executes anything and never follows
references. Applying it only changes classification, markers, recommendations and report selection. Facts, game knowledge and
the data caveats cannot be changed, and the methodology id, version and hash are printed in every report header, finding,
manifest and `analyse` summary.

## Stored-only evaluation

Four responsibilities stay separate: **evidence** (the store: acquisition, identity, units, clocks and measured facts),
**analysis** (rules and findings under a prepared methodology), **presentation** (report documents, Markdown/HTML, the bundle
summary) and **orchestration** (the `Companion` service used by both the CLI and the MCP server). `evaluate` is the analysis
stage on its own.

```bash
tf3c evaluate                                  # human summary, effective methodology (save > user default > packaged)
tf3c evaluate --methodology default --json     # complete version-1 result
tf3c evaluate --methodology ./draft.tf3c-methodology.json --param tolerated_loss=80000 --json   # one-off file, CLI only
tf3c evaluate --save alpha --json              # an existing saves/alpha/ scope
```

MCP `evaluate(methodology=None, save=None, parameters=None)` returns the same result for the same stored evidence,
methodology and parameters; it accepts library ids only. Both adapters call `Companion.open_stored(data=None, save=None)`.

Optional analysis views extend the result without leaving the stored-only boundary: `tf3c evaluate --view bottlenecks --view towns`
(repeatable) or MCP `evaluate(views=["bottlenecks", "towns"])` adds `analysisViews`, keyed only by the requested names in a fixed
order (`bottlenecks`, `expansion`, `lines-history`, `history`, `industries`, `vehicle-roi`, `towns`). Unknown names fail before
anything is read, duplicates collapse, and with no views no extended history is read. Views reuse the evaluation's methodology,
effective report policies and calendar clock and never replace its complete findings or recommendations. Their records, fixed
versus methodology-owned criteria and read bounds are described in [reports](reports.md#analysis-views-the-numbers-behind-a-report).

**Noncreating construction.** `open_stored` resolves the data directory and save scope without Steam discovery and opens the
database through SQLite's read-only mode: no directory, database, schema, migration or report folder is ever created, and
writing methods on that store fail before any side effect. An absent database fails with a missing-evidence error that points to
`ingest`/`refresh`; an existing but unsupported schema fails with compatibility guidance and is never migrated or repaired (open
it once with a writable command such as `tf3c ingest`); a supported empty store reports that no snapshot exists. Evaluation never
ingests newer export files, writes request files, reports, preferences or verdict history; newer game evidence is acquired
explicitly through `tf3c ingest` or `tf3c refresh` (MCP `refresh`) first. `analyse`, `findings` and `report` keep their existing
checked ingestion stage.

**One operation, one view.** Each operation selects the latest snapshot (by ingestion order, as `Store.latest()` does), its
predecessor, the prepared methodology bytes/parameters and the calendar clock once, inside one SQLite read transaction. Reads
stay bounded to that endpoint, with each analysis keeping its own history window (the 12-snapshot rule probe is a support check,
not a global cap). A newer snapshot stored meanwhile does not change the running result; the next operation selects again.
Limitations: the store runs in SQLite's default rollback-journal mode, so a writer committing during a long view waits for it
to close (the busy timeout applies) instead of overlapping it, and the isolation protects one connection's reads, not save
identity: legacy history stays `isolation: legacy-unverified` and observations after the selected endpoint never affect it.
Report files are written only after reads and document composition finish.

**Result (`version: 1`).** JSON-native, deterministic for identical inputs and free of paths, Markdown, handles or live objects:

| Key | Content |
|---|---|
| `snapshot`, `save` | Selected `{date, gameTime}` and the save scope, including the honest isolation note |
| `methodology` | Identity, hashes, selection origin, effective parameters and overrides |
| `timeBasis` | Calendar provenance (`game-calendar-v1`): anchors, isolation, warnings |
| `reportPolicy`, `engineThresholds`, `engineThresholdOrigins` | Effective criteria and where each value came from |
| `roles` | Per entity kind: role counts, `unclassified`, `unclassifiedUnknown`, status and the `assignments` (entity id to role) |
| `ruleResults` | Every rule and aggregate: status, counts, marker counts, all hits with their evidence, aggregate groups; methodology text under `untrusted` |
| `findings` | All findings (engine and methodology) in the existing order, with code, source, severity, entity and evidence; methodology-sourced items carry `untrusted: true` |
| `recommendations` | All recommendation and ladder items by priority, each `untrusted` with evidence |
| `disabledFindings` | Engine findings the methodology switched off |
| `coverage` | `skipped`, `unsupported`, `notEvaluable` with reasons and counts |

Findings, recommendations and rule hits are never truncated; the bundle summary of `analyse` caps them (10 findings, 15
recommendations) only for display. Unknown values stay in `coverage` and are never zero or a success marker. The packaged
`default` appears as an explicit baseline policy, so results with different methodologies over identical measured facts differ
only in their outcomes and recorded criteria. Standalone evaluation succeeds even when the report destination is unwritable.

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

## Report policies and fixed safeguards

Optional `report_policies` configures judgment criteria from a finite registry. Existing files without this object keep
the registry defaults. This is an additive schema-1 extension: older companions reject the unfamiliar key instead of
silently ignoring it. Bump your methodology version when changing its policy.

```json
"report_policies": {
  "industries": {"below_capacity_ratio": 0.95, "production_decline_min": 40},
  "lines-history": {"relative_change_ratio": 0.1},
  "expansion": {"weight_volume": 10, "weight_distance": 40}
}
```

The expansion example keeps the other four default weights (20, 10, 10, 10); all six must total 100.
Values are finite literal JSON numbers, not booleans, parameter references or expressions.
No new CLI policy flags are introduced: existing `--param` affects declared rule parameters, not report policy.

| Family | Configurable criteria and defaults |
|---|---|
| `industries` | `below_capacity_ratio=0.9`; `production_decline_min=30` in recorded production-counter units, not percentage points or industry level. |
| `lines-history` | `relative_change_ratio=0.15`; `noise_factor=2`; `floor_share=0.02`. The existing maximum-of-three threshold formula remains. |
| `bottlenecks` | `persistence_streak=3`; `noisy_min_share=0.4`; `pileup_min=3`; `long_wait_days=10`; `rising_stock_min_fill=0.5`; `rising_stock_min_slope=0.02`. |
| `expansion` | Six score weights: volume 30, distance 20, urgency 20, pull 10, chain 10, proven 10; `volume_reference=150`; distance breakpoints 0.5, 3, 10, 20 km; `distance_long_floor=0.4`; closing/full-input penalties 30/15. |

Ratio criteria lie in [0,1], except `below_capacity_ratio` must be positive and `noise_factor` is in [0,10].
Persistence is an integer from 3 to 36; pileup is an integer from 2 to 1000; wait is positive and at most 36500 in the
raw field's unverified units. Rising-stock slope is positive and at most 1 capacity fraction per sample.
Production decline is nonnegative and at most 1e9 recorded units; volume reference is positive and at most 1e9.
Weights and penalties are in [0,100]; distance breakpoints are in [0,100000] and must satisfy
`short < sweet_from <= sweet_to < long`. Weight totals use absolute tolerance 1e-9; invalid values are never normalized.
Full registry keys, types and constraints are defined in the packaged schema and authoritative validator.

`engine.thresholds` remains the only place for shared stock/load/maturity/fleet thresholds. Vehicle-ROI fit, expansion and
bottlenecks consume the same effective thresholds rather than building hidden defaults.
Finding-code overrides control matching findings, not unrelated report screening rows.
If rising-stock minimum fill is at or above the effective full-stock threshold, the screen explains that its interval is empty.

Minimum evidence counts, missing-value handling, bounded history access, row/chart caps and game mechanics stay engine-owned.
For example, line-history still needs five points and fleet-fit still needs three occupancy observations.
Changing a distance score never creates missing geometry or upgrades a rough estimate to a measured route.

Reports disclose `reportPolicy` (registry version, values and origins), `engineThresholds` and `engineThresholdOrigins`.
Explicitly configuring a default value still has origin `methodology`. The same resolved context drives evaluation, explanatory
text, Markdown/HTML, show/analysis output and manifests. Invalid policy fails before activation or output replacement.

## Calendar ages and duration provenance

`GAME-YEAR` is elapsed in-game Gregorian calendar days divided by 365.25, not `meta.yearDuration` or wall-clock time.
The shared clock uses exact dated anchors or labelled interpolation inside dated brackets spanning at least seven days;
it never extrapolates to old purchases outside observed history or falls back to nominal ticks.
Line age remains the oldest currently assigned vehicle's age, not the line's creation date or first-observed history.
Unknown ages propagate through ordinary missing-data rules. An explicit missing-age outcome is player policy, not evidence
that the line is young. Lifespan and raw depot/terminal counters retain their independent unit caveats.

Rows expose numeric `ageYears` plus `ageTime` with unit/method/reason; analyses, manifests and report surfaces carry
`timeBasis` with version `game-calendar-v1`, normalization, anchor hash, bounds and isolation warnings.
Two methodologies applied to the same evidence share the same physical age values and anchor hash.
Observable rewinds, conflicting identities/dates and unsupported timestamps prevent cross-snapshot conversion;
monotone legacy histories still carry a `legacy-unverified` isolation warning.
Existing numeric policy thresholds remain unchanged; stored snapshots/decisions and user methodology files are not migrated.
Old generated reports are not rewritten on upgrade and provenance-less historical outputs have an unknown time basis.

## The optional `local-feeder-intercity-trunk` example

`local-feeder-intercity-trunk` is a packaged, optional, self-contained example policy: local feeders may lose money inside a
town balance; intercity lines must not lose relevantly; freight may lose money while maturing. It is selectable like any other
methodology, never an engine assumption, and the neutral `default` stays the baseline. The engine accepts policies that use no
name patterns at all (factual fields only); this example uses optional name patterns with factual fallbacks. Its identity,
version, parameters and outcomes are retained as published, so existing selections and generated reports keep their meaning.
The file's `author` text calls it a port of the author's own rules; that is provenance only, and nothing in the product
needs, runs or compares against the author's earlier local scripts, which are retired.

Documented boundaries, each covered by an expectation written in `tests/test_example_methodology.py`:

- Comparison directions: intercity loss and the town feeder-cost ratio are strictly greater than their tolerance (a loss of
  exactly 100,000 is `watch`, a ratio of exactly 0.25 stays within the rule), instantaneous load is greater-or-equal (0.90 is
  flagged, 0.899 is not) and maintenance is strictly below its limits (exactly 0.70 or 0.85 is not below).
- Air stations use `stop.line.carrier == AIR` instead of name modes. Aircraft per terminal is `watch` from 3.0 and `problem`
  from 3.5 (parameters `air_per_terminal_watch` and `air_per_terminal_problem`). Both markers are policy screening: the fleet
  of the lines divided by the terminals those lines use, not capacity, arrivals, a queue or measured congestion, and never a
  reason by itself to build infrastructure or cut a fleet. The recommendation text asks the player to check the game first.
  When no terminal is collected the rule is reported as skipped for missing data, never as a zero ratio.
- Historical difference: the author's earlier local prototype treated this ratio as watch-only (no red marker). The packaged
  example keeps the `problem` marker at 3.5. This is an accepted, documented difference of an optional policy; it is not a
  congestion measurement and nothing here asks for a packaged policy change. A player who prefers watch-only edits a copy
  (new `id`/`version`) and imports it.
- A stop with no station has a missing town (excluded and counted not evaluable); there is no placeholder town bucket.
- Vehicles with a missing maintenance state are not evaluable; no default of 1.0 is invented.
- Ages use the shared calendar basis, not nominal `meta.yearDuration` or a widest-span extrapolation. Purchases before the
  observed dated history have unknown ages. The example's explicit missing-age branch is a policy allowance, not a measured
  young age.
- Report kinds are the package kinds the policy selects; there is no fixed five-page layout or personal naming requirement.
