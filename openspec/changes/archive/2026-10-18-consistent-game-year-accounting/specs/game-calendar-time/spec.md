# Spec Delta

## Purpose

Defines a consistent, evidence-bound GAME-YEAR for exposed age and elapsed-history facts, distinct from nominal tick windows and rolling financial values, with explicit uncertainty and reproducible provenance.

## ADDED Requirements

### Requirement: One calendar GAME-YEAR
The system SHALL define one GAME-YEAR as 365.25 elapsed days of the in-game Gregorian calendar. Calendar-year report grouping SHALL remain based on the exported calendar year. Nominal year-duration ticks, wall-clock seconds and rolling financial counters SHALL NOT be relabelled or rescaled as this unit.

#### Scenario: Calendar crossing and leap day
- **WHEN** dated evidence covers 1979-12-31 to 1980-01-01
- **THEN** elapsed GAME-YEAR is `1 / 365.25`
- **AND** 1980-02-28 to 1980-03-01 is `2 / 365.25`, without clamping either endpoint to day 28
- **AND** calendar-year reports still group the January sample under 1980

#### Scenario: Source and wall clocks remain distinct
- **WHEN** the nominal duration is 1,461,000 ticks and the observed calendar conversion differs
- **THEN** `profitYear`, nominal duration, purchase ticks, industry annual counters and wall-clock snapshot freshness remain unchanged
- **AND** outputs do not call their raw units GAME-YEAR merely because their field names contain year or day

### Requirement: Evidence-bound tick conversion
Tick-derived calendar ages SHALL use exact dated anchors or explicitly labelled interpolation between dated observations spanning at least seven calendar days. Interpolation SHALL use the narrowest eligible enclosing pair, breaking ties by earlier starting then ending tick. No conversion SHALL extrapolate outside observed bounds or fall back to nominal duration, a hard-coded ratio or local-script calibration constants.

#### Scenario: Fourfold nominal mismatch
- **WHEN** selected same-context anchors at ticks 0 and 28000 carry 1980-01-01 and 1980-01-29, and the snapshot nominal duration is 91312 ticks (approximately one quarter of the observed 365250 ticks per GAME-YEAR)
- **THEN** a purchase at tick 14000 evaluated at tick 28000 has estimated age `14 / 365.25` GAME-YEAR
- **AND** every consumer records the same used anchors and interpolation method, not nominal age `14000 / 91312`

#### Scenario: Observed local rates differ
- **WHEN** additional anchors at ticks 42000 and 70000 carry 1980-02-12 and 1980-02-26
- **THEN** conversion of tick 56000 uses the enclosing 42000-to-70000 pair rather than a global ticks-per-year constant
- **AND** output discloses an estimate and observed rate variability without claiming a speed-setting cause

### Requirement: Unknown time is never a fabricated value
Missing or invalid calendar evidence, insufficient interpolation span, future purchases and out-of-range purchases SHALL produce null with a reason. Insufficient history SHALL NOT become zero age, zero span, mature status or a stable trend. Exact supported zero-day measurements SHALL remain distinguishable from unknown measurements.

#### Scenario: Single sample and prehistory
- **WHEN** only the latest dated snapshot exists and a vehicle was purchased before it
- **THEN** vehicle age is null with insufficient-calendar-span or outside-observed-calendar as applicable
- **AND** no consumer substitutes `meta.yearDuration` or the local 16,000-ticks/day assumption

#### Scenario: Same day versus unknown
- **WHEN** two supported dated endpoints both have 1980-01-01
- **THEN** direct observed date span is zero GAME-YEAR
- **AND** two distinct ticks on that day alone cannot calibrate a non-anchor purchase age
- **AND** a missing calendar date is not treated as a zero-day observation

#### Scenario: Invalid and future timestamps
- **WHEN** an endpoint has invalid date 1980-02-30 or a purchase timestamp is later than the evaluated snapshot
- **THEN** its age is null with invalid-calendar-date or future-timestamp respectively
- **AND** no approximate month length, absolute difference or zero clamp hides the problem

### Requirement: Timeline-scoped conversion
Conversion SHALL use only evidence at or before the selected snapshot in the selected save and verified branch when available. Observable rewinds, calendar reversals and conflicting identities SHALL refuse cross-snapshot conversion. Legacy all-null identities SHALL be labelled unverified, never presented as isolated or repaired automatically.

#### Scenario: Historical evaluation excludes future evidence
- **WHEN** a report evaluates tick 28000 while the store also contains tick 70000
- **THEN** the later sample cannot supply a calibration anchor for that report
- **AND** evaluating the same evidence and context again produces the same conversion

#### Scenario: Rewind or save conflict
- **WHEN** the last ingested sample is older than the maximum game time, increasing ticks carry decreasing calendar dates, or supplied anchors have conflicting save identities
- **THEN** cross-snapshot ages and elapsed comparisons are unavailable with ambiguous-timeline
- **AND** raw financial facts and source timestamps remain readable
- **AND** the system does not select a branch by sorting away the contradiction

#### Scenario: Legacy monotone history
- **WHEN** an existing store has monotone dated observations but no save identity or verified branch
- **THEN** bracketed derived values are labelled legacy-unverified estimates with no isolation guarantee
- **AND** detection of a conflict refuses conversion instead of silently joining timelines

### Requirement: Age facts are independent of methodology policy
The same evidence and time context SHALL produce identical unrounded ages in built-in analysis and every methodology. Numeric maturity parameters SHALL retain their configured values in GAME-YEAR; methodologies SHALL NOT change the conversion. Line age SHALL remain the oldest currently assigned vehicle's age proxy, not an invented creation date or first-observed age.

#### Scenario: Three-year boundary and two policies
- **WHEN** a fixture's oldest assigned vehicle has supported age exactly 3 GAME-YEAR and two methodologies set maturity to 3 and 4
- **THEN** both outputs expose age 3
- **AND** the first considers the proxy mature while the second does not
- **AND** parameters remain 3 and 4, never multiplied by a calibration ratio

#### Scenario: Replacement and unknown proxy
- **WHEN** a line observed for five GAME-YEAR now has only newly purchased vehicles
- **THEN** ageYears reflects the oldest currently assigned vehicle rather than five years or the maximum of both measures
- **AND** first-observed duration, if shown, is separately labelled and is not a line creation date
- **AND** if the oldest purchase is outside calibrated history, an age-dependent rule follows existing missing-value semantics rather than receiving a fabricated mature verdict

### Requirement: Consistent consumer presentation and provenance
Age/history values in CLI, MCP, XLSX, findings, methodology fields and reports SHALL share one conversion context. Outputs SHALL expose the unit, conversion version, anchor-set hash, scope/isolation, method, used anchors and unknown reasons through `timeBasis` and measure metadata. Existing list response shapes SHALL remain lists. Human outputs SHALL disclose estimates and missing coverage.

#### Scenario: Same entity through all surfaces
- **WHEN** a supported age is requested through line detail, vehicle list, methodology analysis, a Markdown/HTML report and XLSX
- **THEN** their underlying numeric age agrees before display rounding
- **AND** each identifies GAME-YEAR and game-calendar-v1, with matching context hash
- **AND** unknown-age sorting places null ages last without converting them to zero

#### Scenario: Unsupported annualization
- **WHEN** town, industry, ROI or line-history analysis lacks a known positive elapsed span for an age-dependent calculation
- **THEN** that calculation is marked unavailable with a reason
- **AND** unrelated raw observations remain visible without a fabricated annualized rate or stability verdict

### Requirement: Financial window semantics remain separate
Elapsed GAME-YEAR SHALL NOT establish that a rolling financial window is complete or turn `profitYear` into calendar income. Decision comparisons SHALL label calendar elapsed time separately from any nominal query-window diagnostic. Financial facts SHALL remain single observations, never sums of overlapping rolling windows.

#### Scenario: Calendar year is not a financial proof
- **WHEN** a decision comparison covers one GAME-YEAR while its nominal tick duration differs
- **THEN** the output shows its measured elapsed GAME-YEAR and basis
- **AND** it does not claim a proven completed profitYear window from that calendar span
- **AND** any nominal-window diagnostic is separately labelled and does not rescale the reported profit

### Requirement: Non-destructive historical compatibility
Existing snapshot schemas, raw JSON, decisions and user methodology bytes SHALL remain unchanged by the conversion upgrade. Derived values SHALL be recomputed on demand with the new version and explicit unknowns. Existing generated outputs SHALL remain untouched until explicitly regenerated; outputs lacking conversion provenance SHALL be identified as legacy or unknown-basis rather than reinterpreted.

#### Scenario: Upgrade and regeneration
- **WHEN** an existing dated legacy store and a user methodology with a numeric three-year parameter are opened after upgrade
- **THEN** snapshot/decision counts, raw financial and purchase facts, and methodology bytes are unchanged
- **AND** newly requested output records game-calendar-v1 and uses three GAME-YEAR without editing that parameter
- **AND** unsupported old purchases yield null with a reason rather than a nominal fallback
- **AND** previously generated report files are not automatically rewritten
