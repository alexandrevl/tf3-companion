# operational-analysis-views Specification

## Purpose
Provide reusable structured results for the companion's existing operational diagnostics and historical analyses without constructing, rendering or publishing reports.

## Requirements

### Requirement: Finite stored-evidence analysis selection

Evaluation SHALL accept the closed view names `bottlenecks`, `expansion`, `lines-history`, `history`, `industries`, `vehicle-roi` and `towns`. CLI SHALL expose repeated `tf3c evaluate --view NAME` options and MCP evaluate SHALL accept a `views` list using the same names and application operation. Results SHALL contain `analysisViews` keyed only by requested names, with no extended views selected by default. Unknown names SHALL fail explicitly. Selecting views SHALL NOT ingest, refresh, render, publish, change selections or modify stored evidence, and SHALL work without the game installed or running when a stored snapshot exists.

#### Scenario: Consumer requests two views without a report

- **WHEN** CLI or MCP evaluates stored evidence with `bottlenecks` and `expansion` selected
- **THEN** `analysisViews` contains exactly those domain results alongside the prerequisite evaluation envelope, with no presentation blocks, report paths or filesystem writes

#### Scenario: Default evaluation stays bounded to its existing work

- **WHEN** evaluation omits the views selection
- **THEN** `analysisViews` is empty and no specialized view history is read

### Requirement: Shared operation and endpoint provenance

Views SHALL use the prerequisite evaluation's selected snapshot/save context, validated methodology bytes and resolved policies, calendar clock and provenance. Each result SHALL disclose its actual sample endpoints/counts, selection/hydration bounds, evidence gaps and relevant collection errors. Every historical query and catalog/baseline lookup SHALL be bounded at or before the selected endpoint; a historical report closing endpoint SHALL have its own correctly bounded evaluation. No view SHALL independently choose latest evidence, resolve a methodology again or instantiate alternate policy defaults.

#### Scenario: Retained future history cannot change past results

- **WHEN** a stored historical endpoint is evaluated while newer snapshots, lines and catalogs remain in the same database
- **THEN** the historical result contains no future entities, samples, catalog choices, calendar anchors or judgments derived from those future rows

#### Scenario: Annual closing findings are not current findings

- **WHEN** an annual report closes before the selected current snapshot
- **THEN** its closing diagnostics use evaluation at that closing snapshot under the selected methodology, rather than copying the current evaluation's findings

### Requirement: Reusable operational algorithms

Bottleneck results SHALL expose observations, eligible-sample denominators, occurrence counts/streaks, persistent/intermittent/new/resolved statuses, severity, stock-rise measurements/extrapolation, sampled occupancy statistics, station/depot groups, trend counts and collection coverage. Expansion results SHALL expose candidate identity, exclusions and dead ends, demand/volume allocation, component scores and penalties, ranking, persistence evidence, alternatives, cargo economics, estimated town anchors, starvation and available vehicle-fit evidence. Line-history results SHALL expose line time series, early/recent medians, detrended noise, threshold components, maturity evidence, classes/reasons, sampled occupancy, vehicle changes, created/removed observations and selected manual follow-ups.

#### Scenario: Recurrence distinguishes unknown from absent

- **WHEN** output stocks are unavailable in early snapshots and full in three eligible recent samples
- **THEN** bottleneck recurrence reports three flagged eligible observations without treating missing earlier stock collection as zero or healthy samples

#### Scenario: Shared demand is conserved in ranked candidates

- **WHEN** two under-shipping producers compete for one consumer's remaining demand
- **THEN** expansion selects and rescoring occurs in the existing deterministic greedy order, deducts assigned demand and exposes allocated volumes and score parts without allocating that demand twice

#### Scenario: Line movement is classified using robust evidence

- **WHEN** sufficiently mature lines have enough profit observations for early/recent comparison
- **THEN** the result exposes medians, detrended MAD, each effective threshold term and the resulting class, and reports insufficient evidence rather than stable when maturity or sample sufficiency is unknown

### Requirement: Complete ownership of existing report analytics

Company-history, industry, vehicle-return and town results SHALL include the existing calculations and selected diagnostics described in the design's disposition matrix. Base company, lines, fleet, cargo, annual and decision report calculations SHALL likewise consume structured analysis results. No report-only fallback SHALL recompute rankings, diagnostic membership, score parts, historical comparisons or policy judgments. Presentation MAY choose sections, display caps, formatting, explanatory wording and chart styling, but SHALL NOT determine whether a diagnostic is true or a candidate is eligible.

#### Scenario: Same data supports machine and human consumers

- **WHEN** structured evaluation and Markdown/HTML reports use the same context and selected view
- **THEN** visible metrics, diagnostic membership, class, rank, score parts, event dates and coverage agree with the structured result, even when presentation omits lower-ranked rows with an omission count

### Requirement: Facts, policy and statistical safeguards remain distinct

Method-independent observations and derived metrics SHALL remain invariant across methodologies for identical evidence. Method-dependent classifications, inclusion, rankings and follow-up selections SHALL record effective criteria and reasons from the existing policy context. Engine-owned statistical minima, sampling algorithms and mathematical safeguards SHALL NOT become user methodology knobs. Existing fixed analytic heuristics not covered by methodology policy SHALL be explicitly identified as engine-owned criteria rather than falsely advertised as user-configurable or universal facts.

#### Scenario: Policy changes judgments without rewriting facts

- **WHEN** two valid methodologies change expansion weights or line-history thresholds on identical evidence
- **THEN** the underlying distances, annual counters, medians and noise measurements are unchanged while affected scores, ordering or classes change with the corresponding effective-policy provenance

#### Scenario: Unverified accounting stays unverified

- **WHEN** samples contain rolling annual profits, instantaneous occupancy, raw costs or estimated positions
- **THEN** results retain those semantics and uncertainty, never sum overlapping rolling profits into period income, claim a time-weighted occupancy average, or promote distance estimates into route feasibility

### Requirement: Compatibility and deterministic bounded reads

Extraction SHALL preserve existing report kinds, default algorithms and analytical outputs, except endpoint leakage, unsupported unknown-as-zero conclusions and formerly unspecified equal-key ordering corrected explicitly with regression cases. Compact histories MAY stream all eligible stored rows in fixed-size batches; full snapshot hydration SHALL obey each view's existing finite sampling bounds, without arbitrary huge limits followed by Python filtering. Results SHALL describe truncation/sampling honestly and order equal-priority records by stable entity identifiers or endpoint ticks after existing substantive sort keys.

#### Scenario: Large history preserves diagnostic endpoints without unbounded hydration

- **WHEN** a temporary store contains years of eligible samples and a future retained branch
- **THEN** compact history reads are endpoint-filtered before streaming, full hydration respects the documented per-view limits, first/latest required samples are retained and no result claims to cover excluded or unsampled evidence

#### Scenario: Ties and missing measurements remain reproducible

- **WHEN** equivalent snapshots vary only in input entity ordering and contain equal scores or unknown numeric fields
- **THEN** view ordering is stable, known values remain ordered before unknown values where applicable, and unknown values carry reasons rather than invented zero measurements
