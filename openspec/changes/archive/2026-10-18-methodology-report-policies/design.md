# Design

## Context

See proposal.md for motivation. Current `reports.render_report` passes thresholds only to vehicle-roi, lines-history and industries. `Lens.thresholds` calls `thresholds_for`; `Lens.provenance/header` expose parameters, not effective engine thresholds. `report_bottlenecks` uses module-global `THRESH`; expansion `_Context` and vehicle-roi `_fit_section` instantiate their own defaults. Industries uses literal 0.9 for below-capacity and 30 for decline priority. Lines-history computes `max(0.15 * max(abs(early), abs(recent)), 2 * detrended_MAD, 0.02 * median(abs(current_profit)))` and requires five samples. Expansion has a 100-point six-component score, piecewise distance preference and greedy demand allocation. Existing tests exercise these actual outputs (`test_report_thresholds`, report-family tests, `test_methodology_reports`), so adding config parsing alone is insufficient.

## Goals / Non-Goals

**Goals:** One resolved policy per report operation, explicit finite registry, consumer-visible classification/ranking changes, identical default analytical output, honest limits. Policies govern judgments, not measurements.

**Non-Goals:** A generic expression evaluator, per-role report criteria, policy parameter references, per-run policy flags, collector work or replacement of report algorithms. Existing rule `parameters` and `--param` retain their current semantics and cannot implicitly override report criteria. Presentation and statistical sufficiency settings are not policy.

## Decisions

### D1. Additive schema-1 extension and closed catalog

Add optional top-level `report_policies`, an object with only `industries`, `lines-history`, `bottlenecks`, `expansion`. Each family is an object of the exact keys below; empty object means defaults. Keys use the existing report-kind spelling, including hyphens. Values are literal JSON numbers, never booleans, strings, null, parameter references or expressions. No `$ref` to external resources is loaded. Keep `tf3c-methodology/1`: omitted optional data has precisely the old meaning. Existing consumers too old to know `report_policies` already reject unknown structural keys; document that they must upgrade, rather than silently discard policy. No automatic rewrite/version bump of user files; authors bump semantic version when adding policy. Built-in default remains schema 1 with no overrides.

Registry revision is integer `1` in effective output. It identifies engine-owned defaults/formulas, not a configurable key. A future incompatible meaning requires a new schema major; adding an optional supported key is additive, with older companions failing closed.

### D2. Exact registry, defaults, units and comparisons

All ranges are inclusive unless marked otherwise. Ratios are dimensionless fractions, not percent integers. A `number` must be finite and not boolean; `integer` rejects fractional numbers. Registry defaults copy the current implementation, not anticipated analysis-insights defaults.

| Family/key | Default | Accepted range/unit | Consumer semantics |
|---|---:|---|---|
| industries.below_capacity_ratio | 0.9 | number (0,1] | output `produced < ratio * capacity`; capacity must be positive |
| industries.production_decline_min | 30 | number [0,1000000000], recorded producedYear counter units | first-minus-last production `>=` threshold for manual-review priority; this is an absolute counter-level drop, NOT percentage points, income, throughput or a level/game mechanic |
| lines-history.relative_change_ratio | 0.15 | number [0,1] | relative term of the existing maximum threshold |
| lines-history.noise_factor | 2 | number [0,10], MAD multiplier | detrended-MAD term |
| lines-history.floor_share | 0.02 | number [0,1] | median absolute current profit multiplier |
| bottlenecks.persistence_streak | 3 | integer [3,36], eligible latest samples | consecutive latest observations `>=` streak gives persistent status; noisy family total sightings also must reach streak |
| bottlenecks.noisy_min_share | 0.4 | number [0,1] | noisy-family sightings / eligible samples `>=` share |
| bottlenecks.pileup_min | 3 | integer [2,1000], simultaneous recorded AT_TERMINAL vehicles | station screening count `>=`; never actual queue/capacity |
| bottlenecks.long_wait_days | 10 | number (0,36500], raw daysAtTerminal units | recorded counter `>=`; label raw field units unverified |
| bottlenecks.rising_stock_min_fill | 0.5 | number [0,1] | latest fill `>=` and below effective full_stock_ratio |
| bottlenecks.rising_stock_min_slope | 0.02 | number (0,1], capacity fraction / sample | existing linear slope / capacity `>=`; sampling frequency caveat retained |
| expansion.weight_volume | 30 | number [0,100], points | existing volume term |
| expansion.weight_distance | 20 | number [0,100], points | piecewise distance term |
| expansion.weight_urgency | 20 | number [0,100], points | existing urgency term |
| expansion.weight_pull | 10 | number [0,100], points | existing unmet-demand fraction |
| expansion.weight_chain | 10 | number [0,100], points | existing downstream-usefulness term |
| expansion.weight_proven | 10 | number [0,100], points | existing profitable vehicle-share term |
| expansion.volume_reference | 150 | number (0,1000000000], recorded annual cargo-counter units | volume / reference saturates at 1; accounting unverified |
| expansion.distance_short_km | 0.5 | number [0,100000], straight-line km | no distance points below short |
| expansion.distance_sweet_from_km | 3 | number [0,100000], straight-line km | linear ramp reaches full distance budget |
| expansion.distance_sweet_to_km | 10 | number [0,100000], straight-line km | full budget through sweet_to inclusive |
| expansion.distance_long_km | 20 | number [0,100000], straight-line km | linear fall reaches long-distance floor |
| expansion.distance_long_floor | 0.4 | number [0,1], budget fraction | distance points beyond long |
| expansion.closing_penalty | 30 | number [0,100], points per closing endpoint | retain producer and consumer deductions |
| expansion.full_input_penalty | 15 | number [0,100], points | input fill >= effective full_stock_ratio |

Weights must sum to 100 (absolute tolerance 1e-9, no normalization); short < sweet_from <= sweet_to < long, preventing zero divisors. A rising-stock interval whose minimum is at or above effective full_stock_ratio is empty: retain those effective values and show an explicit 'no not-yet-full interval under effective criteria' note. Do not reject previously valid engine.thresholds files solely because of this new screen, clip the values or invent candidates. Expansion's former FULL_INPUT_STOCK=0.9 now uses the existing engine full_stock_ratio, including output-stock warning text, rather than introducing a conflicting second threshold. Do not silently clip, normalize or fall back on invalid settings.

Industry decline source `first.produced - last.produced` is not an industry level; correct the current documentation's ambiguous '30-point level-decline' description. At a zero decline threshold existing equality behavior is retained and disclosed; this is user policy rather than a measurement rewrite.

### D3. Engine-owned safeguards and bounded algorithms

Keep lines-history MIN_POINTS=5, MAX_K=6 and its 1.5-year window-switch algorithm; vehicle-roi MIN_SAMPLE=3, MIN_LOAD_SAMPLES=3 and LOAD_HISTORY=24; expansion PROVEN_MIN_VEHICLES=3 and PERSISTENCE_MIN_SAMPLES=3; bottleneck sample deduplication, 36-sample window, load limits and rising-stock three-point/six-sample algorithm. Users cannot lower these, select arbitrary history query limits or alter missing-value arithmetic. Persistence may be made stricter but not less than three. Keep row/chart limits, buckets, age presentation and strings out of the registry. Cargo matching, water-industry mechanics, available models, demand conservation, default urgency composition (including uncertainty discounts), downstream-input logic and nonnegative score flooring remain fixed algorithm definitions. Component weights/preferences are the configurable judgments; permitting arbitrary formulas would defeat a closed registry.

Shared existing engine threshold overrides remain in `engine.thresholds`: maturity, high/low load, underused fleet count, idle duration, stock fullness and unshipped ratio. Do not add aliases under report_policies. Existing engine sample controls are not expanded here; report-local minima remain independent hard safeguards even if an engine trend threshold is changed. Report-specific missing station positions/links remain unknown, not zero or an inferred new collector field.

### D4. One context and explicit precedence

Introduce a frozen resolved `ReportAnalysisContext` (in the methodology/report boundary) with effective `Thresholds`, typed policy families and origin maps. Resolve once: registry defaults, then the selected methodology's explicit `report_policies`; engine defaults, then existing engine.thresholds. Lens owns this context so report helpers never rebuild it. Internal callers with no lens resolve the neutral context at the public report/build boundary only. Keep the existing explicit `thresholds` argument for internal callers/tests by folding it into that boundary context when no lens exists; supplying both a lens and an explicit threshold/context argument is an error (no ambiguous override of methodology provenance). Nested helpers require context/typed subpolicy, not optional values. Update every caller rather than retaining private compatibility shims.

Pass context to all five families and their classification, observation, scoring and explanatory-text helpers. Remove bottleneck global THRESH, expansion default _Context threshold construction and ROI fit local defaults. Built-in report sections in reports.py that call analysis.findings must use effective thresholds and existing methodology finding decisions where already available, rather than advertise a methodology while using raw defaults; keep historical report evidence dates and sample selection unchanged. Never copy latest methodology verdict facts onto a different annual closing snapshot. If findings are evaluated for historical endpoints, evaluate the selected methodology against that endpoint with history bounded to it.

Vehicle-roi fit has no new policy family: consume effective overloaded_load, underused_load and underused_min_vehicles, retaining the existing median load calculation and hard three-sample guard. Engine finding toggles/severity overrides affect matching built-in finding codes, not unrelated report screening rows; clearly label report screens and disclose their criteria rather than imply code overrides control them.

The shared gate from `validated-methodology-activation` must validate schema, all registry values and effective cross-field relationships before binding or output replacement. Failure never means use neutral/default instead; the gate owns debug diagnostics and preservation of previous selection/results. Missing evidence is not an invalid policy and yields existing insufficient-data notes. Invalid combined context from internal APIs raises before document creation. No policy is evaluated after gate failure.

### D5. Effective-policy provenance, not hidden metadata

Expose `reportPolicy` in methodology show, Lens provenance, analysis JSON and manifest: `{registryVersion: 1, values: {family: {key: value}}, origins: {family: {key: 'default'|'methodology'}}}`. Expose effective `engineThresholds` and corresponding `engineThresholdOrigins` alongside it; no duplicated configurable aliases. Methodology content hash still hashes original file bytes, not resolved defaults. Identity/hash/origin and snapshot game time/date remain present. Registry revision plus complete resolved values make changing engine defaults visible across companion versions.

Every affected rendered report includes a 'Report policy' section/table with only its relevant policies/shared thresholds and their origins/units; methodology verdicts report includes all families. Markdown and HTML consume the same document blocks and escape all free text. Headers carry registry revision; other reports can state no report-local policy while still recording effective thresholds used. No-policy/default reports preserve original measured values, classifications, recommendations, row order and score parts, allowing only additional policy/provenance disclosure and corrected explanatory units. Manifest consumers receive additive fields.

### D6. Dependency order and migration

Implement registry/validation first, resolved context second, report consumers third, provenance/documentation fourth, integration verification last. `validated-methodology-activation` supplies the shared strict gate and transactional failure guarantees; merge its hook before considering runtime acceptance complete. Neither user-default selection changes nor game-year changes are prerequisites; use whichever selected methodology the resolver returns and retain current temporal basis. Coordinate source signature changes if applied together.

`basic-reports` already owns model/rendering, standard report output and annual coverage caveats; do not duplicate its plan. `analysis-insights` owns station position/link collection (tasks 1.1-1.3) and scope economics (7.1-7.3). Until its player-validated data exists, ladder geometry stays skipped and town expansion distances remain their existing explicitly rough estimate/unknown. A favorable distance weight never creates geometry or upgrades confidence. No game or save-layout migration is needed; all verdicts/reports are regenerated on demand from existing snapshots. No per-save isolation claim.

## Risks / Trade-offs

- Additive schema 1 means older companions cannot read policy-bearing files; explicit rejection is safer than silently applying contradictory criteria. Preserve acceptance of every currently valid file without report_policies, subject to shared gate support requirements.
- A fixed registry cannot express every custom ranking philosophy; finite documented criteria are intentional, and new keys need a separately specified consumer and tests.
- A policy changes ordering under greedy shared-demand allocation, not just displayed scores; tests must verify later candidates are re-scored and demand is not allocated twice.
- Replacing hidden defaults exposes inconsistencies in nondefault outputs intentionally; neutral-default golden analytical results are the regression anchor. Unverified field units remain labeled, never calibrated by this change.
