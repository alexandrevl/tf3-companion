# report-policies Specification

## Purpose

Make report judgments and rankings reproducible under a selected methodology through a finite validated policy catalog, while preserving measured facts, engine evidence safeguards and neutral-default behavior.

## Requirements

### Requirement: Closed report policy vocabulary
A methodology MAY supply optional `report_policies` under schema `tf3c-methodology/1`. The system SHALL accept only the family/key registry in this change's design D2, with its stated defaults, units, ranges, comparison directions and effective cross-field constraints. All values SHALL be finite literal numbers of the specified numeric kind, never booleans or expressions. Unknown family/key, wrong type, unsupported criterion or invalid effective combination SHALL reject the whole methodology with the exact JSON field location, offending value and valid constraint before activation or report publication. No unsupported policy SHALL be ignored or replaced by a neutral policy. Existing files without this object SHALL remain valid subject to the shared methodology support gate.

#### Scenario: Reject a presentation knob or unsafe safeguard change
- **WHEN** a file declares `report_policies.lines-history.minimum_points` or `report_policies.expansion.table_cap`
- **THEN** validation fails naming that full path and listing supported keys
- **AND** the previous selection and generated results remain unchanged under the validated-methodology activation gate

#### Scenario: Validate numeric and combined constraints
- **WHEN** a file supplies a boolean noise factor, nonfinite numeric input, a persistence streak of 2, weights summing to 99, or equal short and sweet-from distances
- **THEN** validation fails before any report is replaced and diagnostics identify the invalid fields and expected constraints

#### Scenario: Shared full threshold leaves an empty rising-stock interval
- **WHEN** effective engine full_stock_ratio is 0.45 and effective rising_stock_min_fill is 0.5
- **THEN** the valid methodology remains accepted and the rising-stock section states that no not-yet-full interval exists under the effective criteria
- **AND** neither value is clipped and no candidate is invented
- **AND** explicitly setting rising_stock_min_fill to 0.4 enables the interval [0.4,0.45)

### Requirement: Preserve neutral outputs and engine safeguards
Omitted policy SHALL reproduce the current report measurements, verdicts, recommendations, scores and ranking order, apart from added provenance and accurate explanation of units. The system SHALL retain the engine-owned sample sufficiency guards, missing-value behavior, bounded history/sampling algorithms, schema rules, game-mechanics restrictions and data caveats described in design D3. Policy SHALL NOT manufacture geometry, collection support or statistical confidence.

#### Scenario: Default regression across report families
- **WHEN** the same fixture evidence is rendered without a methodology, with `default`, and with a valid file declaring an empty report_policies object
- **THEN** industries, lines-history, bottlenecks, expansion and vehicle-roi have identical analytical rows, score parts, ordering and advice after excluding policy/provenance additions

#### Scenario: Small sample cannot become a trend
- **WHEN** a line has four usable profit samples and policy noise_factor, relative_change_ratio and floor_share are all zero
- **THEN** lines-history still reports insufficient data rather than improving or deteriorating
- **AND** a two-sample vehicle load series cannot produce a sustained ROI fit recommendation

#### Scenario: Missing positions stay missing
- **WHEN** distance is unknown and the methodology allocates all expansion weight to distance
- **THEN** that candidate receives zero distance points, never fabricated geometry
- **AND** unknown-distance and existing rough town-distance caveats remain visible and station-position-dependent ladders remain skipped

### Requirement: Policy controls industry and line-history judgments
Industries SHALL use the effective below-capacity fraction and absolute recorded-production decline criterion in all corresponding statuses, priority selection and explanations. Lines-history SHALL use the effective relative-change fraction, noise multiplier and current-profit floor share in its existing maximum-threshold classifier. Equality SHALL follow design D2: below-capacity strictly less, decline greater-or-equal, and improvement/deterioration strictly beyond the computed change threshold.

#### Scenario: Capacity and decline boundaries
- **WHEN** an industry has capacity 100 and produced 90 with below_capacity_ratio 0.9
- **THEN** it is not below capacity
- **AND** changing that ratio to 0.95 makes it below capacity without changing its recorded production
- **AND** a production-counter decline exactly 30 meets production_decline_min 30 but not 31

#### Scenario: Exact trend boundary
- **WHEN** a mature line has five usable samples, early median 100, recent median 120, zero residual MAD, zero floor term and relative_change_ratio 0.2
- **THEN** the change 20 is stable because it does not exceed the threshold 24
- **AND** reducing the ratio to 0.1 makes it improving with threshold 12, with the same measured medians
- **AND** a change exactly equal to a computed threshold remains stable

### Requirement: Policy controls bottleneck recurrence and screening
Bottlenecks SHALL consume effective persistence streak, noisy-family share, station pileup count, raw terminal-wait criterion and rising-stock fill/slope criteria. All underlying detector calls, status/severity decisions and explanation text SHALL use the same effective engine thresholds, including fullness, idle duration and high/low load. Policies SHALL NOT relabel sampled occupancy as average demand or a station screening count as capacity/queue.

#### Scenario: Stricter persistence and recurrence
- **WHEN** an eligible noisy family occurs in the last three of five samples
- **THEN** streak 3 and share 0.4 retain it as persistent
- **AND** streak 4 removes it from noisy findings because three sightings are insufficient
- **AND** streak 3 with share 0.6 retains it at equality, while share 0.61 filters it out

#### Scenario: Rising-stock exact boundaries
- **WHEN** a served stock has at least three usable points, latest fill 0.5, effective fullness 0.9 and slope 0.02 capacity per sample
- **THEN** it passes default rising-stock criteria at both lower boundaries
- **AND** it no longer passes when either minimum is raised above the measured value
- **AND** fill equal to effective fullness is never shown as not-yet-full

### Requirement: Policy controls expansion ranking without changing allocation mechanics
Expansion SHALL use the effective six component budgets, volume reference, distance preference breakpoints/floor and penalties in its current score formula. Budgets SHALL sum to 100 without normalization. Missing distance SHALL contribute zero, score SHALL stay nonnegative, already-served exclusions SHALL be unchanged and each greedy selection SHALL deduct its proposed volume from shared unmet demand before remaining candidates are re-scored. Deterministic ties SHALL remain ordered by rounded descending score then producer id, cargo id and consumer id.

#### Scenario: Priority reversal with identical evidence
- **WHEN** two otherwise eligible candidates differ only in normalized volume and distance terms, A having volume fraction 1 and distance fraction 0, B having volume fraction 0.2 and distance fraction 1
- **THEN** default volume/distance weights 30/20 rank A's 30 points above B's 26
- **AND** setting volume/distance weights to 10/40 while retaining the other weights ranks B's 42 points above A's 10
- **AND** their measured cargo amounts and distances are identical between outputs

#### Scenario: Distance curve and greedy allocation
- **WHEN** candidates lie exactly at the configured short, sweet-from, sweet-to and long breakpoints
- **THEN** their distance fractions are respectively 0, 1, 1 and the configured long floor
- **AND** tied candidates retain stable identifier ordering, later candidates are re-scored after demand allocation, and allocated volume never exceeds recorded unmet demand

### Requirement: Shared threshold propagation has one meaning
Report-local policy SHALL NOT duplicate existing engine threshold keys. Vehicle-roi sustained fit screens SHALL use selected overloaded_load, underused_load and underused_min_vehicles; expansion SHALL use selected unshipped_ratio and full_stock_ratio; bottlenecks SHALL use selected applicable engine thresholds throughout detector and explanatory paths. Simultaneously supplying an explicit internal threshold override and a selected methodology lens SHALL fail clearly instead of contradicting recorded provenance. User parameter overrides SHALL NOT override numeric report policy literals.

#### Scenario: Same threshold reaches every consumer
- **WHEN** selected full_stock_ratio is 0.75 and a stock is 80% full
- **THEN** industries and bottlenecks classify it as full and expansion applies the full-input penalty when it is a candidate consumer input
- **AND** each output states 0.75 as the effective threshold from the methodology

#### Scenario: ROI fit uses selected thresholds
- **WHEN** a line has the engine-required usable history, median sampled load 0.85 and enough vehicles, and selected overloaded_load is 0.8
- **THEN** vehicle-roi includes its sustained-high-load screen instead of using the built-in 0.9
- **AND** changing the selected threshold to 0.9 removes that screen without changing the load series

### Requirement: Effective policy is externally auditable
Methodology show, analysis JSON, manifests and report provenance SHALL expose reportPolicy with registryVersion, complete resolved values and per-value default/methodology origins, together with effective engineThresholds and engineThresholdOrigins. Rendered affected reports SHALL display relevant effective criteria, units and origins using the same escaped document content in Markdown and HTML. The methodology report SHALL display all families. Existing methodology identity/hash/origin and actual snapshot date/game time SHALL remain available. Report screens SHALL be distinguishable from built-in findings controlled by finding-code overrides.

#### Scenario: Explicit value equal to default retains origin
- **WHEN** a methodology explicitly sets noise_factor to 2 and omits floor_share
- **THEN** outputs show noise_factor 2 from methodology and floor_share 0.02 from default
- **AND** manifest and rendered criteria agree, including registry revision and methodology content hash

#### Scenario: No silent failure or stale relabeling
- **WHEN** a previously usable file is edited to contain an unsupported policy and generation is requested
- **THEN** the validated-methodology activation gate rejects it with debug-accessible diagnostics
- **AND** the previous binding/results remain unchanged and no report with the rejected file's identity is published
