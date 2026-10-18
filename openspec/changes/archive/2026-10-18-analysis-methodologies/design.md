# Design

## Context

Current state (read from the working tree, including uncommitted report work):

- `analysis.py` holds one implicit policy: a frozen `Thresholds` dataclass (`overloaded_load` 0.9, `underused_load` 0.3, `mature_years` 1.0, `idle_depot_days` 30, `unshipped_ratio` 0.5, `full_stock_ratio` 0.9, trend and fit knobs) and finding builders with fixed `code`, severity, title and suggestion (`line_losing_money`, `line_overloaded`, `line_underused`, `line_config_issue`, `line_profit_dropping`, `vehicle_no_path`, `fleet_idle_in_depot`, `industry_closing`, ...). `line_losing_money` is `high` for any mature loss-making line, regardless of what the line is for. That is exactly what a "local feeders may lose money" player does not want.
- `report_*.py` repeat knobs as module constants: `FULL_STOCK = 0.9` (`report_industries`), `MATURE_YEARS = 1.0` (`report_lines_history`, `report_vehicle_roi`), persistence streaks and noise shares (`report_bottlenecks`), score budgets and distance bands (`report_expansion`), `REL_THRESHOLD`, `NOISE_FACTOR` (`report_lines_history`). `report_bottlenecks` already builds on `analysis.Thresholds()`.
- `reports.VALID_KINDS` is `company, lines, fleet, cargo, decisions, annual, history, vehicle-roi, lines-history, industries, towns, expansion, bottlenecks`. `Companion.report` writes `<data>/reports/<kind>.md` plus `latest.md` atomically.
- The author's methodology lives outside the package: `data/analysis-rules.md` (Portuguese) and constants plus a classifier in `data/analise/common.py` and its report scripts. Facts verified there: the name pattern `^(?P<mode>\S+) .*?-(?P<scope>LO|IC|RE)-(?P<n>\d+)$` with fallback scope `LO` if one town else `IC`; towns come from each stop's station group, not name codes; passenger-ness comes from real capacity (`capacity[].cargo` is cargo id + 1; passenger-only if every positive-capacity entry is cargo 0), falling back to mode `Bus`/`AP` when no capacity is exported; town balance sums local-line result by the line's first town and intercity result over every distinct town of the line, restricted to towns that have at least one local line, and flags `local < 0 and (intercity <= 0 or -local/intercity > 0.25)`; intercity result is `ok` when >= 0, `problem` when the loss is strictly greater than 100,000, else `watch`; freight with a loss is `maturing` below 3 years of age (age 0 when a line has no vehicles) else `problem`; load >= 0.90 always warns; maintenance below 0.70 is `problem`, below 0.85 `watch`; aircraft per terminal is **watch-only** at >= 3.0 (code comment: it "never reaches BAD").
- Snapshot facts that bound what a methodology can say today (`knowledge/snapshot_schema.md`, `snapshot.py`): stops carry `stationGroup`, `name`, `loadMode`, waiting times (the mod also emits `terminal`, `bridge.script.lua:232`, which the schema doc omits); `stations[]` carry `town`/`townName` but **no position**; industries carry `position`; there is no terminal total, no waiting-in-the-air state, no line creation date (age is the oldest vehicle's, a lower bound). `analysis-insights` plans station-group positions through a mod change that is not in snapshots yet.
- Not in the repo and not proven: save identity (`cross-platform-and-saves` D4/D5). The current code has one store and `<data>/reports/`.
- `agent_instructions.md` already declares game and report text untrusted; `mcp_server.py` tools take entity names and enumerated literals, never paths.

See `proposal.md` for motivation.

## Goals / Non-Goals

**Goals:**

- A player can write or receive one JSON file, drop it in a folder, and have the analyst apply it to a chosen save with no code change and no trust in the file's prose.
- The author's current hard-coded policy is expressible without loss, so the schema is proven on a real, non-trivial methodology.
- The neutral default is byte-for-byte equivalent to today's findings.
- Honest about data: rules needing uncollected fields are visibly skipped.

**Non-Goals:**

- A general-purpose rules engine or scripting language. The vocabulary is closed and grows only through companion releases.
- New facts. Methodologies reuse facts the engine already computes or that `analysis-insights` adds; new facts need engine (and sometimes collector) work.
- Persisting verdict history, per-entity manual overrides, methodology inheritance.
- Making every report-module constant overridable in v1 (see D8 for the subset).

## Decisions

### D1 — Three layers and who owns what

| Layer | Owns | Lives in |
|---|---|---|
| Game mechanics | How the game works (income formula, stocks, maintenance, catchment) with `[V]`/`[I]`/unverified labels | `knowledge/*.md` (shared, not overridable) |
| Evidence | Per-save snapshots, decisions, notes | per-save store |
| Methodology | Roles, tolerances, markers, severities, rules, recommendations, report selection | one JSON file |
| Engine | Computing facts (rows, ratios, trends, stock fill), the field catalog, finding builders, caveat text, rendering | `src/tf3companion/` |

The engine never asks a methodology for facts and a methodology can never alter a fact, a caveat string, or knowledge text. A methodology may *read* the same facts through the field catalog (D4).

**Findings composition.** Output of an analysis is: (1) built-in engine findings, after the methodology's `engine.thresholds` and `engine.findings` overrides, plus (2) findings produced by methodology rule outcomes (code `rule:<rule-id>`, `source: "methodology"`). Overrides can be scoped to roles (`{"code": "line_losing_money", "role": "local-passenger", "action": "off"}`) so that "local lines may lose money" silences the engine's generic loss finding for local lines only, while unclassified lines keep it. Without this a methodology would be contradicted by the engine's own findings.

Alternatives: (a) methodology replaces all engine findings: discards verified checks such as `line_config_issue` and `vehicle_no_path` that no playstyle wants disabled; (b) methodology only adds findings: leaves the contradiction above. Rejected.

### D2 — File format: JSON, own validator, schema published

One UTF-8 JSON file, `"schema": "tf3c-methodology/1"`, extension `.tf3c-methodology.json` (library candidates are files with that suffix).

Why JSON: stdlib parser, no new runtime dependency, a standard schema language, no ambiguous scalars, and, decisively, players will ask their AI agent to *write* methodologies; LLMs produce JSON reliably and a schema plus precise validator errors closes the loop. Missing comments are compensated by mandatory-friendly `description`/`rationale` fields in the format.

Validation is an in-repo validator (structure, types, limits, cross-references, regex safety, field/measure/parameter/role/marker resolution) with errors carrying a JSON-pointer-like path. A packaged `schema-1.json` (JSON Schema 2020-12) ships for editor support (`"$schema"` key allowed) and documents the structure. Two sources of truth is a drift risk, so a test runs every valid/invalid fixture through both and asserts they agree; `jsonschema` is added to the **dev** dependency group only.

Alternatives: **YAML** (comments, but a new dependency, implicit typing pitfalls, richer attack surface in loaders); **TOML** (stdlib read-only parser, comments, but nested condition trees become unreadable arrays-of-tables); **XML** (verbose, DTD/entity attack surface, worse for agents). **Runtime `jsonschema`** rejected: cannot express cross-references or regex safety, so a custom validator is needed anyway, and it adds a dependency to every install.

Limits (constants in the loader, listed in the schema doc): file <= 256 KiB, <= 200 rules, <= 20 roles per entity kind, free-text fields <= 2,000 characters, regex <= 200 characters, subject strings truncated to 200 characters before matching.

### D3 — Condition language

A condition is a JSON tree:

```json
{"all": [ {"field": "line.loss_year", "op": "gt", "value": {"param": "intercity_loss_alert"}},
          {"not": {"field": "line.name_capture.scope", "op": "eq", "value": "LO"}} ]}
```

- Combinators: `all`, `any`, `not`, and `{"ref": "<definition>"}` for named reusable conditions declared in a top-level `definitions` map (no recursion; validated acyclic).
- Leaf: `{"field": ..., "op": ..., "value": ...}` where `op` in `eq ne lt le gt ge in not_in matches contains_any exists missing`. `value` is a literal or `{"param": name}`. `exists`/`missing` take no value. In aggregate rules `{"measure": ...}` replaces `field`; in group `having` a member quantifier `{"any_member": cond}` is allowed.
- **Tri-state (Kleene) evaluation**: a leaf over a missing value is *unknown*; `all` is false if any part is false, else unknown if any is unknown; `any` is true if any part is true, else unknown if any is unknown; `not unknown` is unknown. A rule fires only on *true*. The count of unknown evaluations per rule is reported as "not evaluable". This is what makes "never zero" a property of the evaluator rather than a convention. `exists`/`missing` are the only operators that turn a missing value into a definite answer, which lets authors state fallbacks explicitly (as the author's `age`-missing-means-young does).
- `matches` uses Python `re` on a pattern that passed the safety check at load: length cap, no backreferences, no lookarounds, no quantified group containing another quantifier. Subject truncated to 200 chars. Alternative: a template syntax (`{mode} {cargos}-{town}-{scope}-{n}`) with no regex at all was considered; it cannot express the author's lazy `.*?` and alternation, and the restricted-regex check bounds the risk.
- Numbers are plain JSON numbers. Money fields use game units. No arithmetic in leaves: derived quantities (`line.loss_year = max(0, -profit_year)`, ratios) are catalog fields or aggregate measures, which keeps the vocabulary small and each derivation documented.

Alternatives: embedding an expression language (`profit < -100000 and age < 3`) is shorter to write but is a parser, an injection surface and a drift source; rejected in favour of the closed tree. JSON-Logic style arrays were rejected as unreadable for authors.

### D4 — Field catalog, availability and the two meanings of "unsupported"

The engine owns a registry mapping field name -> `{type, entity, source snapshot paths, caveat, since}` (e.g. `line.profit_year` -> `lines[].profitYear`, caveat "rolling game-year, partial for lines younger than a year"; `line.load` -> `lines[].capacity[]`, caveat "instantaneous"; `line.age_years` -> oldest vehicle's `purchaseTime`, caveat "lower bound"; `vehicle.maintenance_state` -> `vehicles[].maintenanceState`, 0-1). v1 catalog by entity kind:

| Entity | Fields (illustrative, final list fixed in implementation from existing rows) |
|---|---|
| `line` | `id`, `name`, `name_capture.<n>`, `carrier`, `vehicle_count`, `stop_count`, `town_count`, `stop_towns`, `first_stop_town`, `profit_year`, `loss_year`, `transported_year`, `load`, `age_years`, `is_passenger_only`, `cargo_ids`, `cargo_names`, `issue_types`, `role` |
| `vehicle` | `maintenance_state`, `carrier`, `model_family` (segment of the model `res` path, as the author's `kind_of` derives it), `age_years`, `profit_year`, `state`, `days_in_depot`, `value`, `line.*`, `role` |
| `stop` | `station`, `terminal`, `town`, `line.*` |
| `industry` | `type`, `level`, `production_rating`, `shipped_ratio`, `input_delivery_ratio`, `closing`, `role` |
| `stock` | `kind`, `fill_ratio`, `owner_name` |
| `town` | `capacity_sum`, `line_usage` |

Fields that are **defined but not collectable today** (`line.route_km`, `line.stop_distances_km`, `town.pair_distance_km`) are in the registry flagged `requires: ["stations[].position"]`.

Two distinct outcomes, both reported:
1. **Unknown field name** (not in this companion's registry): rule is *unsupported* (reason `unknown field`, with a nearest-name suggestion); file still loads. This is the forward-compatibility path for a methodology written against a newer companion, and the typo path.
2. **Known field, data absent in this save** (probe over the snapshots: the source path is missing or empty in every stored snapshot): rule is *skipped* (reason `missing data: <snapshot path>`).
3. Per-entity missing value: *not evaluable* count (tri-state, D3).

The catalog is exposed to authors and agents through a `knowledge` topic (`methodology-fields`) generated from the registry, and `tf3c methodology fields`, so a methodology can be authored against facts that exist.

### D5 — Roles and classification

Roles are declared per entity kind as an ordered list; the first selector that evaluates true wins; entities with no true selector are `unclassified` and counted (never dropped).

Name classification is an optional top-level `name_patterns` list per entity kind: patterns tried in order, captures taken from the **first pattern that matches** (all-or-nothing), exposed as `line.name_capture.<name>`; a capture name must be declared by some pattern (validated). A line matching no pattern has its captures *missing*, which feeds the tri-state logic and explicit fallbacks. Town attribution never uses name captures: it uses `stop_towns`, derived from each stop's station group through `stations[]` (this is the author's fix for the `Mon`/`Lei` code collisions). A stop whose station group is absent from `stations[]` yields a missing town, not a placeholder town. The geometric/semantic alternatives (carrier, passenger-only capacity, town count, cargo, industry type, later route distance) are ordinary fields, so a name-free methodology is first-class.

### D6 — Rules, markers, aggregates

```
rule := { id, label, description?, rationale?, entity, role?, outcomes: [ {when, marker, message} ... ], default?: {marker, message?} }
aggregate rule := { id, ..., entity, aggregate: { group_by, measures, having?, outcomes, default? } }
marker := { symbol, label, description?, finding?: "high"|"medium"|"low" }   # no finding key = shown in tables only
```

- **Outcomes are ordered, first true wins**, which expresses graded tolerances without duplicating conditions.
- **Markers are methodology-defined** (the author's five: ok, watch, problem, maturing, local-loss-within-rule). The marker's `finding` key maps it to the engine's three severities, or to "no finding". Symbols are escaped text.
- **Message templates** contain `{path}` or `{path|fmt}` with `fmt` in `money pct int km years text`; only catalog fields and the rule's own measures may be referenced (validated). No expressions, no nested templates.
- **Aggregates** group members by a key (`town`, `stop.station`, ...). A measure is `sum|count|distinct_count|min|max|ratio` over member values, with optional `where` (member filter) and `via` (which key a member contributes through, e.g. first town vs every distinct town) and `distinct_by` (count each underlying entity once). `ratio` is *missing* when the denominator is not positive. `having` restricts groups.
- Entity kinds for rules: `line`, `vehicle`, `stop` (aggregates only), `industry`, `stock`, `town`.

Alternatives: severities fixed to a global emoji scale (rejected: the author's `maturing` and `local-loss-within-rule` are not severities); one flat threshold table (rejected: cannot express the town balance or graded outcomes).

### D7 — Recommendations, ladder and text safety

```
recommendation := { id, when: {rule, marker, role?}, priority: 1..5, text: "<template>", rationale? }
ladder := { id, entity: "line", role?, metric: "line.route_km",
            bands: [ {max_km, mode}, {max_km, mode}, {mode} ],   # mode in ROAD|RAIL|TRAM|WATER|AIR (snapshot carriers)
            text: "<template>" }
```

A recommendation is emitted once per rule hit that matches its trigger and carries an `evidence` reference (`rule`, entity, measured values). The only text in a recommendation is its author template with placeholders filled from measured values. A ladder computes `route_km` (needs positions, so it is skipped today), picks the band, and emits `text` when `line.carrier` differs from the band mode. If the trigger rule or ladder metric is unsupported/skipped, the recommendation is listed as skipped. Engine built-in suggestions are unchanged under `default`.

Text safety (also D14): free text is size-limited, control characters stripped, HTML-escaped in HTML output and Markdown-neutralised (pipes, backticks, angle brackets, leading `#`/`>`/list markers escaped) in Markdown tables and paragraphs. Methodology text is rendered inside a clearly labelled "Methodology (untrusted text)" quotation and in tool results is returned under keys marked `untrusted: true`.

### D8 — Engine integration

- `analysis.findings(snap, prev, thresholds, methodology=None)`: `Thresholds` is built from defaults plus `engine.thresholds` overrides (validated against `dataclasses.fields(Thresholds)` so a new threshold becomes overridable automatically, unknown names invalid). Finding overrides apply after building, matched by `code` and optionally by the finding entity's role.
- Report constants that **duplicate** `Thresholds` are rewired so one override reaches them: `FULL_STOCK` (`report_industries`) -> `full_stock_ratio`; `MATURE_YEARS` (`report_lines_history`, `report_vehicle_roi`) -> `mature_years`. All other report constants (persistence streaks, noise shares, score budgets, chart caps) stay report-local in v1 and are listed in `docs/` as non-overridable; adding one is a one-line registry change later.
- A new report kind `methodology` ("verdicts") renders: methodology header and provenance, roles with counts, per-rule results with markers and evidence, aggregate tables (town balance, station pressure), recommendations, and the skipped/unsupported/not-evaluable lists first. It is always part of the generated set.
- `analyse` computes verdicts once and passes the resolved methodology (an immutable object) to each report builder; builders that do not use it ignore it, so unmodified report kinds are unaffected.

### D9 — Report and chart selection

```json
"reports": {
  "kinds": ["company", "lines-history", "towns", "cargo", "fleet"],
  "tables": [ {"id": "helis", "entity": "vehicle", "role": "helicopter", "sort": "vehicle.maintenance_state", "columns": ["vehicle.line.name", "vehicle.maintenance_state"]} ],
  "charts": [ {"id": "result-by-role", "type": "bar", "entity": "line", "metric": "line.profit_year", "agg": "sum", "group_by": "role"} ]
}
```

`kinds` must be existing `VALID_KINDS`; `tables` and `charts` draw from catalog fields and chart types `bar | pie | history_line`, rendered with the existing Mermaid helpers and always accompanied by a table with the same numbers (the `basic-reports` rule). A methodology cannot define new kinds or free-form output.

### D10 — Library, versions, identity

- Packaged: `default.json` and `examples/` inside the wheel (read via package resources, like the bundled mod/knowledge). User folder: `<data>/methodologies/` (global across saves: a methodology is policy, not evidence).
- Identity is `id@version` from file content, not the file name. `import` stores as `<id>@<version>.tf3c-methodology.json`. Resolution of a bare `id` picks the highest valid version.
- Every file gets a SHA-256 content hash (full bytes) recorded as `sha256:<first 12 hex>` in outputs. Two files with equal `id@version` and different hash are a **conflict**: both listed, neither applicable. Editing without a version bump is detected through the hash.
- `import` = validate, then copy; never executes, never follows references. `--force` replaces an existing `id@version`. `export` writes the stored bytes unchanged, so hashes match across machines.
- No network access of any kind: no URL import, no update check.

Alternative: bundling methodologies into a zip/pack with assets. Rejected: single file is the sharing unit the user wants and removes archive-extraction risk.

### D11 — Binding, precedence and the save indirection

Precedence: explicit request > save binding > `default`. Binding is `"methodology": "id"` or `"id@version"` in the save's `save.json` (set by `tf3c methodology use`). A missing/invalid bound methodology is an error, not a silent downgrade to `default` (silent fallback would change judgments invisibly).

A tiny `SaveScope` indirection (`root`, `metadata`) is introduced: when the `cross-platform-and-saves` layout exists it points at `<data>/saves/<id>/` and `save.json`; before that it points at `<data>` itself and `<data>/methodology.json`. All new code asks the scope, so this change neither blocks on nor guesses the unverified save identity (D4 of that change). The fallback is not isolation and manifests say so.

Alternatives: a global "active methodology" setting (rejected: the same player's two saves may follow different playstyles, per the user's requirement that analyses stay per save); binding stored in the methodology file (rejected: policy must not know about saves).

### D12 — Output layout

`<save root>/reports/<game-date>__<methodology-id>@<version>/`: save folder is the stable id (label lives in `save.json`, so renames never move files); `<game-date>` is the snapshot's `YYYY-MM-DD` (or `t<gameTime>` without a date, matching `Snapshot.date_label`); both `id` and `version` are validator-restricted to path-safe characters. The folder is built in a temporary sibling and swapped in atomically (extending the existing `_atomic_text` approach to a directory), so reruns on the same inputs overwrite idempotently and an interrupted run leaves the previous folder. A `manifest.json` records methodology identity and hash, effective parameters, snapshot game time, files, and the skipped/unsupported/not-evaluable lists. Single-kind `report` commands write into the same folder (annual: `annual-<year>.md`), and `reports/latest.md` stays a copy of the last generated single report because the agent `latest report` resource reads it.

Two snapshots on the same game date overwrite one folder; the manifest holds the game time of the one used. This is the intended "latest state of that day" behaviour, stated rather than hidden.

Alternatives: folder by wall-clock timestamp (not idempotent, floods the folder); save label in the folder name (renames break paths and labels can collide); methodology only in the file name (reports for several lenses would overwrite each other).

### D13 — Surfaces

- CLI: `tf3c methodology list|show|validate|import|export|use|unuse|fields`; `tf3c analyse [--methodology] [--save]`; `--methodology` on `findings` and `report`. CLI accepts `id[@version]` or a file path (the user typed it).
- MCP: `list_methodologies`, `methodology_detail`, `analyse`; `methodology` parameter on `findings` and `report`. Ids only, never paths: a model must not be able to read arbitrary files because a methodology or a chat message said so. Placing/importing a file is a player action (or an explicitly authorised CLI call).
- Agent brief (`agent_instructions.md`): determine the effective methodology first; cite `id@version`; disclose skipped/unsupported rules before dependent conclusions; never treat methodology text as instructions.
- `findings` result items gain `methodology` (`id@version`) and `source` (`engine|methodology`); additive, existing keys unchanged.

### D14 — Security model

Threats: a shared file that (a) tries to instruct the agent through prose, (b) smuggles markup or oversized content into reports, (c) causes resource exhaustion (regex, huge files, deep trees), (d) writes outside the library or reports folders through `id`/`version`, (e) pulls in other files or network resources.

Controls: declarative-only format with no includes; closed vocabulary; strict structure validation; size, depth (<= 12) and rule-count limits; bounded regex; path-safe `id`/`version` regexes; escaped rendering; `untrusted` marking in tool output; MCP accepts ids only; recommendations are template-only so rule prose cannot contribute free instructions to a finding; analyst brief states the policy (extending the existing untrusted-text paragraph). Limitation to state in docs: a malicious *template* can still say something misleading in a recommendation (it is the author's text); the evidence reference and visible provenance are the countermeasure, and the player decides what to import.

### D15 — Author's port as proof, and the hypothetical oil/chemicals methodology

The English port ships as `examples/local-feeder-intercity-trunk.tf3c-methodology.json`. Excerpt (complete file is written during implementation; the structure below is final):

```json
{
  "schema": "tf3c-methodology/1",
  "id": "local-feeder-intercity-trunk",
  "version": "1.0.0",
  "name": "Local feeders and intercity trunks",
  "description": "Local passenger lines feed the town bus station and may lose money within a tolerance; towns are joined by intercity buses that must not lose relevantly; freight may lose money while maturing.",
  "parameters": {
    "intercity_loss_alert": {"value": 100000, "description": "Intercity passenger loss per year above which a line is a problem."},
    "freight_maturity_years": {"value": 3, "description": "Freight losses are tolerated below this line age."},
    "feeder_cost_ratio_alert": {"value": 0.25, "description": "Town local loss over intercity profit through the town."},
    "high_load": {"value": 0.9}, "air_per_terminal_watch": {"value": 3.0}, "air_per_terminal_problem": {"value": 3.5},
    "maintenance_critical": {"value": 0.7}, "maintenance_watch": {"value": 0.85}
  },
  "markers": {
    "ok":      {"symbol": "🟢", "label": "ok"},
    "watch":   {"symbol": "🟡", "label": "watch", "finding": "low"},
    "problem": {"symbol": "🔴", "label": "problem", "finding": "high"},
    "maturing": {"symbol": "🔵", "label": "maturing"},
    "local-loss-within-rule": {"symbol": "⚪", "label": "local loss within rule"}
  },
  "name_patterns": {"line": [
    {"id": "coded", "pattern": "^(?P<mode>\\S+) .*?-(?P<scope>LO|IC|RE)-(?P<n>\\d+)$"},
    {"id": "first-word", "pattern": "^(?P<mode>\\S+)"}
  ]},
  "definitions": {
    "passenger": {"any": [
      {"all": [{"field": "line.is_passenger_only", "op": "exists"},
               {"field": "line.is_passenger_only", "op": "eq", "value": true}]},
      {"all": [{"field": "line.is_passenger_only", "op": "missing"},
               {"field": "line.name_capture.mode", "op": "in", "value": ["Bus", "AP"]}]}
    ]}
  },
  "roles": {"line": [
    {"id": "local-passenger", "label": "Local passengers", "select": {"all": [
       {"ref": "passenger"},
       {"any": [{"all": [{"field": "line.name_capture.scope", "op": "exists"},
                         {"field": "line.name_capture.scope", "op": "eq", "value": "LO"}]},
                {"all": [{"field": "line.name_capture.scope", "op": "missing"},
                         {"field": "line.town_count", "op": "le", "value": 1}]}]}]}},
    {"id": "intercity-passenger", "label": "Intercity / regional passengers", "select": {"ref": "passenger"}},
    {"id": "freight", "label": "Freight", "select": {"not": {"ref": "passenger"}}}
  ], "vehicle": [
    {"id": "helicopter", "select": {"field": "vehicle.line.name_capture.mode", "op": "eq", "value": "HC"}}
  ]},
  "engine": {"findings": [
    {"code": "line_losing_money", "role": "local-passenger", "action": "off"},
    {"code": "line_losing_money", "role": "intercity-passenger", "action": "off"},
    {"code": "line_losing_money", "role": "freight", "action": "off"}
  ]},
  "rules": [
    {"id": "intercity-result", "entity": "line", "role": "intercity-passenger",
     "rationale": "Trunk lines must not lose relevant money.",
     "outcomes": [
       {"when": {"field": "line.loss_year", "op": "gt", "value": {"param": "intercity_loss_alert"}}, "marker": "problem",
        "message": "{line.name} loses {line.loss_year|money} a year, above the {param.intercity_loss_alert|money} tolerance."},
       {"when": {"field": "line.profit_year", "op": "lt", "value": 0}, "marker": "watch",
        "message": "{line.name} loses {line.loss_year|money} a year, within tolerance."}],
     "default": {"marker": "ok"}},
    {"id": "freight-result", "entity": "line", "role": "freight",
     "outcomes": [
       {"when": {"all": [{"field": "line.profit_year", "op": "lt", "value": 0},
                         {"any": [{"field": "line.age_years", "op": "lt", "value": {"param": "freight_maturity_years"}},
                                  {"field": "line.age_years", "op": "missing"}]}]},
        "marker": "maturing", "message": "{line.name} is losing money but is younger than {param.freight_maturity_years|years}."},
       {"when": {"field": "line.profit_year", "op": "lt", "value": 0}, "marker": "problem",
        "message": "{line.name} still loses {line.loss_year|money} after the maturity period."}],
     "default": {"marker": "ok"}},
    {"id": "local-result", "entity": "line", "role": "local-passenger",
     "outcomes": [{"when": {"field": "line.profit_year", "op": "lt", "value": 0}, "marker": "local-loss-within-rule"}],
     "default": {"marker": "ok"}},
    {"id": "high-load", "entity": "line",
     "outcomes": [{"when": {"field": "line.load", "op": "ge", "value": {"param": "high_load"}}, "marker": "watch",
        "message": "{line.name} was {line.load|pct} full at snapshot time (an instantaneous reading)."}]},
    {"id": "vehicle-maintenance", "entity": "vehicle",
     "outcomes": [
       {"when": {"field": "vehicle.maintenance_state", "op": "lt", "value": {"param": "maintenance_critical"}}, "marker": "problem"},
       {"when": {"field": "vehicle.maintenance_state", "op": "lt", "value": {"param": "maintenance_watch"}}, "marker": "watch"}],
     "default": {"marker": "ok"}},
    {"id": "town-feeder-balance", "entity": "line", "aggregate": {
       "group_by": "town",
       "measures": {
         "local_result":     {"agg": "sum",   "value": "line.profit_year", "where": {"field": "line.role", "op": "eq", "value": "local-passenger"},       "via": "line.first_stop_town"},
         "local_lines":      {"agg": "count", "where": {"field": "line.role", "op": "eq", "value": "local-passenger"},                                     "via": "line.first_stop_town"},
         "intercity_result": {"agg": "sum",   "value": "line.profit_year", "where": {"field": "line.role", "op": "eq", "value": "intercity-passenger"}, "via": "line.stop_towns"},
         "feeder_cost_ratio": {"agg": "ratio", "numerator": {"measure": "local_result", "negate": true}, "denominator": {"measure": "intercity_result"}}},
       "having": {"measure": "local_lines", "op": "gt", "value": 0},
       "outcomes": [
         {"when": {"all": [{"measure": "local_result", "op": "lt", "value": 0},
                           {"any": [{"measure": "intercity_result", "op": "le", "value": 0},
                                    {"measure": "feeder_cost_ratio", "op": "gt", "value": {"param": "feeder_cost_ratio_alert"}}]}]},
          "marker": "problem", "message": "Local lines in {group} lose {local_result|money}, over the tolerance against intercity {intercity_result|money}."},
         {"when": {"measure": "local_result", "op": "lt", "value": 0}, "marker": "local-loss-within-rule"}],
       "default": {"marker": "ok"}}},
    {"id": "air-station-pressure", "entity": "stop", "aggregate": {
       "group_by": "stop.station",
       "having": {"any_member": {"field": "stop.line.carrier", "op": "eq", "value": "AIR"}},
       "measures": {
         "vehicles":  {"agg": "sum", "value": "stop.line.vehicle_count", "distinct_by": "stop.line_id"},
         "terminals": {"agg": "distinct_count", "value": "stop.terminal"},
         "fleet_per_terminal": {"agg": "ratio", "numerator": {"measure": "vehicles"}, "denominator": {"measure": "terminals"}}},
       "outcomes": [{"when": {"measure": "fleet_per_terminal", "op": "ge", "value": {"param": "air_per_terminal_problem"}}, "marker": "problem",
          "message": "{group} has {fleet_per_terminal} aircraft per terminal used by its lines. Not capacity or queue: check the game for aircraft waiting to land before building."},
         {"when": {"measure": "fleet_per_terminal", "op": "ge", "value": {"param": "air_per_terminal_watch"}}, "marker": "watch",
          "message": "{group} has {fleet_per_terminal} aircraft per terminal used by its lines. Not capacity or queue: check the game for aircraft waiting to land before building."}],
       "default": {"marker": "ok"}}}
  ],
  "recommendations": [
    {"id": "fix-intercity", "when": {"rule": "intercity-result", "marker": "problem"}, "priority": 1,
     "text": "Review {line.name}: reduce vehicles, shorten the route or merge it with another trunk line."},
    {"id": "fix-feeders", "when": {"rule": "town-feeder-balance", "marker": "problem"}, "priority": 2,
     "text": "Local lines in {group} cost too much compared with the intercity profit through the town. Review the local network."},
    {"id": "air-infrastructure", "when": {"rule": "air-station-pressure", "marker": "watch"}, "priority": 3,
     "text": "If aircraft really wait at {group}, build terminal infrastructure; adding vehicles will not help."}
  ],
  "reports": {"kinds": ["company", "lines-history", "towns", "cargo", "fleet"],
              "tables": [{"id": "helicopter-maintenance", "entity": "vehicle", "role": "helicopter",
                          "sort": "vehicle.maintenance_state", "columns": ["vehicle.line.name", "vehicle.maintenance_state"]}]}
}
```

**Faithfulness notes for the port** (each is a deliberate, recorded fidelity decision):

- Comparison directions follow the source: intercity loss uses strictly-greater (a loss of exactly 100,000 is `watch`), the town ratio is strictly-greater, load is greater-or-equal.
- `age_years` missing is treated as young in the freight rule through an explicit `missing` branch, reproducing the source's age 0 for lines without vehicles.
- Air stations use `stop.line.carrier == AIR` instead of the name modes `AP/AC/HC`; equivalent for the author's naming, name-free for everyone else. Aircraft per terminal is `watch` from 3.0 and `problem` from 3.5 (the user-approved documented policy), still a screening number; the author's current code and rules file call it watch-only (see Open Questions).
- Role definitions guard every fallback branch with an explicit `exists`: `any(scope == LO, all(scope missing, town_count <= 1))` is *unknown*, not false, when the scope is missing and the town count is above one (the first leaf is unknown), so the example writes `all(scope exists, scope == LO)` instead. This follows from the tri-state rule that a comparison over a missing value is unknown.
- An unknown outcome before a true one makes the entity *not evaluable* instead of falling through to the later marker, and an unknown role selector before the winner leaves the entity unclassified (counted as unknown): the earlier outcome or role might have applied.
- A stop with no matching station yields a missing town (excluded and counted not-evaluable) where the source used a `"?"` bucket.
- Per-vehicle maintenance flags all vehicles, with helicopters surfaced through a role-based table, as `frota.py` and `raio_x.py` do. Vehicles with missing maintenance state are not evaluable where the source defaulted to 1.0; verdicts are identical, only the not-evaluable count differs.
- The author's five report pages (X-ray, evolution, by town, cargo chains, fleet and maintenance) are not one-to-one with existing report kinds; the port selects the nearest kinds. Page-for-page parity is not claimed.

**Hypothetical second methodology (not shipped; test fixture): oil/chemicals chain for a struggling player.**

```json
{
  "schema": "tf3c-methodology/1", "id": "oil-chemicals-chain", "version": "0.1.0",
  "name": "Oil and chemicals chain, patient",
  "description": "Tuned for crude oil -> refinery -> chemicals chains: judge the chain by stocks and deliveries before judging lines by profit.",
  "parameters": {"chain_maturity_years": {"value": 5}, "starved_input_ratio": {"value": 0.5}, "full_stock": {"value": 0.9}},
  "markers": {"ok": {"symbol": "🟢", "label": "ok"}, "watch": {"symbol": "🟡", "label": "watch", "finding": "medium"},
              "problem": {"symbol": "🔴", "label": "problem", "finding": "high"}, "maturing": {"symbol": "🔵", "label": "maturing"}},
  "roles": {
    "line": [{"id": "chain-freight", "select": {"field": "line.cargo_names", "op": "contains_any", "value": ["crude_oil", "oil", "fuel", "plastic", "chemicals"]}}],
    "industry": [{"id": "chain-industry", "select": {"field": "industry.type", "op": "matches", "value": "oil|refiner|chemical|plastic"}}]
  },
  "engine": {"thresholds": {"mature_years": 5}},
  "rules": [
    {"id": "chain-line-result", "entity": "line", "role": "chain-freight", "outcomes": [
      {"when": {"all": [{"field": "line.profit_year", "op": "lt", "value": 0}, {"field": "line.age_years", "op": "lt", "value": {"param": "chain_maturity_years"}}]}, "marker": "maturing"},
      {"when": {"field": "line.profit_year", "op": "lt", "value": 0}, "marker": "problem"}], "default": {"marker": "ok"}},
    {"id": "starved-consumer", "entity": "industry", "role": "chain-industry", "outcomes": [
      {"when": {"field": "industry.input_delivery_ratio", "op": "lt", "value": {"param": "starved_input_ratio"}}, "marker": "watch",
       "message": "{industry.name} receives {industry.input_delivery_ratio|pct} of the input it could consume."}]},
    {"id": "full-destination", "entity": "stock", "outcomes": [
      {"when": {"field": "stock.fill_ratio", "op": "ge", "value": {"param": "full_stock"}}, "marker": "problem",
       "message": "{stock.owner_name} stock is {stock.fill_ratio|pct} full; deliveries to it can stall."}]}
  ],
  "recommendations": [
    {"id": "unblock-destination", "when": {"rule": "full-destination", "marker": "problem"}, "priority": 1,
     "text": "Raise outbound capacity or consumption at {stock.owner_name} before adding more feeding vehicles."}
  ],
  "reports": {"kinds": ["industries", "cargo", "bottlenecks"]}
}
```

Cargo identifiers and industry type strings above are illustrative; real values are those in a snapshot's `cargos[]` and `industries[].type`, and the implementation task verifies them. This methodology uses only fields available in today's snapshots; a distance-ladder variant needing positions appears in tests as the skipped-rule fixture:

```json
"ladders": [{"id": "mode-by-distance", "entity": "line", "role": "intercity-passenger", "metric": "line.route_km",
  "bands": [{"max_km": 40, "mode": "ROAD"}, {"max_km": 150, "mode": "RAIL"}, {"mode": "AIR"}],
  "text": "{line.name} spans {line.route_km|km}; the band suggests {band.mode}, the line runs on {line.carrier}."}]
```

## Risks / Trade-offs

- [Vocabulary too small for real playstyles] -> Start from the author's real port and the hypothetical chain methodology; unsupported-rule reporting makes gaps visible instead of silent; the catalog grows by release.
- [Vocabulary too large, becomes a language] -> No arithmetic, no recursion, no loops; every derived quantity is a documented catalog field.
- [Schema validator and published JSON Schema drift] -> Shared fixtures run through both in tests (dev-only `jsonschema`).
- [Engine age basis may disagree with the author's] -> Scripts calibrate ticks per year (`common.py` comment on `meta.yearDuration` ~4x shorter than the observed calendar year, P-020) whereas `Snapshot.age_years` divides by `meta.yearDuration`. Maturity tolerances in years therefore may differ from the author's reports until the engine calibrates; surfaced in the parity task and Open Questions, not hidden by the methodology layer.
- [Methodology contradicts engine findings] -> Role-scoped finding overrides (D1); the default stays untouched.
- [Silent judgment change] -> Provenance everywhere, content hash, no silent fallback on a broken binding.
- [Misleading recommendation text from a shared file] -> Template-only text, visible provenance, untrusted marking; the player chooses what to import. Cannot be eliminated for text a player chooses to trust.
- [Save layout not yet verified in game] -> Single indirection with documented fallback; no isolation claim without the layout.
- [Report layout cutover] -> Pre-release, no shim; `latest.md` kept for the existing resource.
- [Performance] -> Evaluation is linear in entities x rules over one snapshot (hundreds of lines); aggregates use hash grouping; negligible next to snapshot loading.

## Migration Plan

1. Land the loader, validator, registry, evaluator and `default` with the equivalence test; no behaviour change.
2. Wire thresholds/finding overrides and the duplicate report constants.
3. Add library, binding and `analyse`; cut `Companion.report` over to the lens folder and update the callers/docs in the same change.
4. Ship the author's port as an example; run the parity check locally against the author's own save.
Rollback: revert the change; no data migration exists (no schema or store changes). Existing `<data>/reports/*.md` files from before the cutover are left in place and are no longer written.

## Future work (collector/engine, not in this change)

Fields that would make methodologies stronger: station-group positions and served industries/towns (already planned in `analysis-insights`; enables `route_km` and ladders), total terminals per station group and a "waiting to land" state (P-014), a line creation date (P-013), distinct helicopter versus airplane model family confirmation, engine calibration of the game year (P-020). Methodology inheritance/overlay, per-entity role overrides, calibrated community packs and a signed registry are possible later work.

## Open Questions

- **Aircraft per terminal (resolved by the user, 2026-10-18)**: the port declares the documented policy, watch at >= 3.0 and problem at >= 3.5 (parameters `air_per_terminal_watch`, `air_per_terminal_problem`), and stays a screening number, never capacity or a queue. Where the terminal count is not collected (P-014), the rule reports *skipped* (`missing data: lines[].stops[].terminal`) or, for single stations, *not evaluable*; it is never evaluated as zero. Observation recorded at implementation: the current `data/analysis-rules.md` line 23 and `data/analise/common.py` still say "screening only, never red", so the author's scripts count three more `watch` stations where the port reports `problem`; removing the `problem` outcome from the example restores that behaviour (one-line change).
- **Age basis (P-020, resolved: out of scope)**: calibration of the game year is not part of this change. The engine keeps `Snapshot.age_years` (divides by `meta.yearDuration`). Measured on the author's save: `meta.yearDuration` 1,461,000 versus 5,856,303 ticks per calendar year in the author's calibration, so engine ages are about four times the calendar ages. Maturity tolerances in years (freight 3 years) therefore classify more lines as past maturity than the author's local scripts do (see parity results). Documented in `docs/methodologies.md`; the methodology layer does not hide it.
- **Local line presentation (resolved)**: the `local-result` rule reproduces the author's per-line local result (9 losing, 5 earning on the author's save, identical to `common.py`); the town verdict is the town-feeder-balance aggregate.
- **Industry type, cargo and model family strings (resolved)**: enumerated from the author's snapshot and recorded in `docs/methodologies.md`: `industry.type` is `::/industries/<kind>/<kind>.con` (`oil_platform`, `oil_refinery`, `chemical_plant`, ...); cargo `res` keys include `crude_oil`, `fuel`, `chemicals`, `plastic`, and passengers are cargo id 0 (`passengers`); `cargos[].name` is localised, so the oil fixture matches on the new language-neutral `line.cargo_keys`; model families are `bus`, `truck`, `plane`, `helicopter`, `ship`. The oil fixture's chain roles match 18 lines and 14 industries on that snapshot.
- **Distance-band ladder (resolved)**: implemented completely and exercised in tests with a synthetic positions fixture; on real saves it is reported as skipped (`missing data: station positions`) until the collector provides positions (`analysis-insights`).
- **Report relocation (resolved)**: `Companion.report` and `latest_report` move to the lens folder with no compatibility shim; the pre-release flat `reports/<kind>.md` files are no longer written.
- **Recommendation severity for `watch`**: the port maps watch to `low` and problem to `high`; the author may prefer `medium` for watch. Example-only choice, unchanged.

### Parity check against the author's scripts (task 8.4, run 2026-10-18 on a copy of the author's save, 28 snapshots, latest 1974-01-05)

Read-only comparison of `uv run tf3c analyse` (example methodology) with `data/analise/common.py`, `raio_x.py`, `cidades.py` and `frota.py` evaluated on the same snapshot:

| Check | Author's scripts | Port | Result |
|---|---|---|---|
| Roles (local / intercity / freight) | 14 / 20 / 42 | 14 / 20 / 42 | identical |
| Intercity result (ok / watch / problem) | 16 / 3 / 1 | 16 / 3 / 1 | identical |
| Local lines (losing / earning) | 9 / 5 | 9 / 5 | identical |
| Load >= 90% | 9 | 9 | identical |
| Town balance (not in table / within rule / ok / problem) | 10 / 4 / 4 / 2 | 10 / 4 / 4 / 2 | identical (same towns flagged) |
| Maintenance (ok / watch / critical) | 214 / 4 / 0 | 214 / 4 / 0 | identical; 0 vehicles not evaluable |
| Air stations per terminal (ok / watch / problem) | 5 ok, 6 watch (3.0 and above) | 5 ok, 3 watch, 3 problem | differs by the decision above: the three stations at 3.5 or more are `problem` in the port |
| Freight (ok / maturing / problem) | 28 / 12 / 2 | 28 / 4 / 10 | differs by the age basis (P-020): the engine's year is about four times shorter than the calendar year, so eight lines are past the 3-year tolerance in engine years but under it in calendar years |

Not-evaluable counts on this save are zero for every rule (every stop resolves to a station and every vehicle has a maintenance state), so the `?` town bucket and missing-state differences did not occur here.
