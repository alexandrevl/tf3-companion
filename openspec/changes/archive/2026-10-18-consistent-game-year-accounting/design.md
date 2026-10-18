# Design

## Context

See `proposal.md` for motivation. Read-only inspection established these distinct clocks and current inconsistencies:

| Evidence | Observed behavior and limit |
|---|---|
| `snapshot.py:96-118`, `analysis.py:88-118` | Ages divide raw tick differences by the latest nominal `yearDuration`; line age is the oldest assigned vehicle, not creation time. |
| `store.py` | Snapshots are keyed/ordered by `game_time`; a non-null versus different/missing `saveId` is rejected on insertion, but all-null legacy history is not isolated. JSON retains dates, ticks and purchase times. `ingested_at` and source modification time are wall-clock metadata, not simulated duration. |
| Bridge `readClock`, `collectMeta`, `buildSnapshot` | `GAME_TIME.gameTime`, `getDefaultYearDuration()` and `getCalendarDate(now)` are exported separately. `fromTime = max(now - yearDuration, 0)` feeds financial queries. Interval sampling also uses the nominal duration. None of this proves nominal duration equals a calendar year. |
| `data/playtest-issues.md` P-020/P-018/P-023 | One save exhibits roughly 4x disagreement, mixed legacy histories are possible, and vehicle ids can be reused. The recorded counts/rate are historical observations, not rerun results. |
| `data/analise/common.py:71-85,134-136` | Widest dated span >=7 days gives ticks/year using 365.25; otherwise a hard-coded `16000 * 365.25` is used. This proposal deliberately does not adopt that fallback. |
| `report_lines_history.py:216-259` | >=14-day calibration uses 365.0 and clamps days to 28; fallback is nominal duration. Maturity also combines oldest-vehicle age and first-observed history. |
| `report_vehicle_roi.py:99-129` | >=7-day calibration uses 365.25, extrapolates to purchases before observations, then falls back to nominal duration. |
| `report_history.py`, `report_industries.py`, `report_towns.py` | Independent ordinal/date calculations and approximate/nominal fallbacks; towns returns zero on insufficient duration; history warns when last ingestion differs from max game time. |
| `reports.py:_decision_details` | Labels a nominal-tick comparison a complete profit window. This is not proof of calendar accounting. |
| `methodology/fields.py`, `catalog_doc.py`, `docs/methodologies.md` | Fields and generated caveats accurately describe today's nominal arithmetic; the example's three-year threshold explicitly differs from local calibrated scripts. |
| Existing report tests | `test_report_history.py` deliberately uses ticks/day unrelated to nominal duration; line-history tests use their own synthetic ticks/year. Those fixtures must be kept as cross-clock regressions, not rewritten to hide mismatches. |

No inspected collector field establishes date-speed settings, historical clock changes or the calendar date of an old purchase. No assumption about wall-clock speed controls is warranted. A finite set of dated observations cannot prove the tick/calendar relation outside its observed range, or exclude an unseen rate change inside a sampling gap.

## Goals / Non-Goals

**Goals:** one pure conversion context for a selected evidence set; numeric facts invariant across methodologies; explicit date-resolution estimates and unknown reasons; no destructive migration; consumer-visible consistency even when the correct result is unknown.

**Non-Goals:** a universal physical game clock, exact sub-day purchase dates, inferred branch identity, backwards extrapolation to unsupported purchases, or any change to collector financial windows and cadence. A lifespan ratio is not made trustworthy merely by fixing vehicle age: model `lifespan` and raw depot/terminal day fields retain their independently documented units and uncertainty.

## Decisions

### D1. Name the units and retain the source clocks

`GAME-YEAR = elapsed in-game Gregorian calendar days / 365.25`; `GAME-DAY` is one calendar-date step. Use actual valid Gregorian ordinals, including leap days and December/January crossing. 365.25 is a documented reporting normalization, not a claim that every calendar year contains 365.25 days. A 366-day interval is `366 / 365.25` GAME-YEAR. Calendar-year annual report selection remains based on the date's year, not this normalized duration.

Retain `meta.gameTime`, `meta.yearDuration`, purchase timestamps and all finance values verbatim. Name `yearDuration` the **nominal financial/query-duration ticks**, not GAME-YEAR. Wall seconds remain wall seconds (`status.ageSeconds` is not converted). `profitYear`, production/transport yearly counters, model lifespan, `daysInDepot` and `daysAtTerminal` are not rescaled.

Rejected: use nominal ticks as universal game years (contradicts observed calendar); use 4x or the local fallback (save-specific unverifiable extrapolation); redefine `profitYear` as calendar accounting (changes the problem).

### D2. Pure shared result, built once per evaluation

Add `game_time.py` with immutable `GameCalendarClock` and `TimeMeasure` values, no database/file operations. Proposed interfaces:

- `GameCalendarClock.from_samples(samples, *, context)` consumes lightweight `(gameTime, date, source)` anchors plus verified save/branch context or an explicitly unverified legacy context.
- `elapsed_between_dates(start, end) -> TimeMeasure`: direct ordinal difference for valid dates in a nonambiguous selected context.
- `calendar_at_tick(tick) -> CalendarEstimate`: an exact anchor date or bracketed interpolation; no extrapolation.
- `elapsed_between_ticks(start, end) -> TimeMeasure`: mapped calendar difference for supported nonnegative ordering, otherwise null with a reason.
- `snapshot.age_years(purchase_time, *, clock)` delegates to that context. Remove context-free nominal age arithmetic; internal callers must supply the same context explicitly. Pure standalone snapshots without context return unknown, not an implicit clock.

`TimeMeasure` contains `value` (number or null), `unit: "GAME-YEAR"`, `method` (`calendar-dates`, `calendar-interpolation`, `unavailable`), `reason`, and anchor references. `timeBasis` has `version: "game-calendar-v1"`, `daysPerYear: 365.25`, `saveId`, `isolation` (`verified` or `legacy-unverified`), verified branch id when supplied, selected snapshot tick, anchor bounds and warnings. Publish a deterministic hash of the ordered `(gameTime,date)` anchors and scope identifier so a newly ingested anchor cannot silently change a supposedly reproducible estimate. Dates have day resolution: labels must say estimate for interpolation; do not present precision as an exact purchase date.

Age-bearing rows retain numeric `ageYears` and add `ageTime` containing the serialized `TimeMeasure`; `ageTime.value` equals `ageYears`. Elapsed-duration objects analogously use `elapsedGameYears` plus `elapsedTime`. The context fingerprint key is `timeBasis.anchorHash`; `timeBasis` is available at top level of object responses and on each age-bearing row of existing list responses. Unknown reasons are stable codes, not only free-text report notes.

Build once per selected snapshot/report evaluation using only samples at or before that evaluation tick. `Store.time_context(snapshot)` supplies a reusable context; reports should reuse their existing compact history projection rather than reparsing every large snapshot for every row. Shared metadata is serialized once per response/report; rows carry only the measure method/reason and used-anchor references where needed.

### D3. Deterministic bracketed conversion, never guessed calibration

For exact tick matches, use the exported calendar date. For a non-anchor tick, select the narrowest dated anchor pair that contains it and spans at least seven calendar days, with strictly increasing ticks/dates (ties choose earlier starting tick then earlier ending tick). Use linear interpolation between their ordinal days. Seven days is a documented minimum evidence span, inherited conservatively from the existing ROI/local calibration, not a claim of seven-day physical accuracy. Interpolation is an estimate; expose pair span/rate, do not call it verified engine calibration. Use original day values, never clamp to day 28. A date with no valid Gregorian interpretation is unavailable, never synthesized.

Exact dated endpoints can yield a valid zero-day observed span even with one repeated day; a single undated or dated sample cannot support tick-derived purchase age. Non-anchor same-day or <7-day histories yield `insufficient-calendar-span`. A purchase before the oldest anchor, after the evaluated snapshot or in a refused timeline yields `outside-observed-calendar`, `future-timestamp` or `ambiguous-timeline`; not zero and not a nominal fallback. Exact equality with the evaluation tick is a valid zero age only if its calendar anchor is valid. Two date-less ticks that happen to match are not evidence for a calendar duration.

Different observed tick/day rates are handled locally by different anchor pairs, never by one store-wide ticks/year constant. Disclose observed variability; do not guess a speed change cause. This does not establish that speed changes are relevant to this API, and no speed telemetry or collector work is introduced. A report may show a whole-span observed ratio as a diagnostic, explicitly not as the conversion used for every age.

Rejected: widest-span extrapolation to the oldest purchases (unsupported behavior outside observations); a global regression or 4x correction (hides variable clocks); fabricated month/day from `meta.year` (insufficient source precision).

### D4. Scope and rewind safety without implementing save isolation

Use the caller's selected save/branch context. Never use a sample after the requested snapshot, a different non-null `saveId`, or a different verified branch. Consume lineage/rewind context from `cross-platform-and-saves` when implemented. Until then, surface `legacy-unverified` for all-null legacy histories and explicitly state that isolation is not guaranteed. Do not claim a monotone date sequence proves common lineage.

In the current single store, reject cross-snapshot conversion on a detectable ambiguity: last-ingested row is older than max game time, increasing ticks with decreasing dates, duplicate tick anchors with conflicting dates in supplied samples, or mixed identities. Do not recover by sorting away the contradiction, taking absolute values, or automatically selecting the apparent newest branch. Same-date distinct ticks are not themselves a rewind; they cannot alone calibrate. Cross-snapshot values from a monotone legacy context are permitted only as **legacy-unverified estimates**, with that warning on every consumer and no verified-isolation claim. Exact snapshot facts remain readable when conversion is refused. Silent mixing that left no trace in today's primary-key store cannot be detected retrospectively; that is a concrete isolation limitation, not something this clock fixes.

### D5. Consumer cutover and facts versus policy

| Consumer | Contract after cutover |
|---|---|
| Line/vehicle rows, CLI `lines`/`line`, MCP lists/detail, XLSX | Same unrounded `ageYears` for the same context; null and reason when unsupported; human headers use GAME-YEAR. Sort unknown ages last. |
| Methodology facts | `line.age_years`, inherited line-age fields and `vehicle.age_years` read the shared result. Registry sources include purchase ticks plus dated history and scope, not nominal duration. Existing missing/tri-state logic remains authoritative, including explicit `missing` outcomes. |
| Engine thresholds/example | Keep `mature_years` and `freight_maturity_years` numeric values (including 1 and 3), but document GAME-YEAR. Do not multiply a policy threshold by four or let a parameter override the clock. Neutral default equals built-in analysis after the cutover, not the old erroneous numeric engine. |
| Historical reports | Date coverage, elapsed windows, town annualization, industry trend intervals, vehicle cohorts/ROI ages and line-history windows use shared time results. Replace report-specific calibrators, approximate ordinals and nominal fallbacks. Annualization requires a known positive span; unknown is not zero or `stable`. |
| Line-history maturity | Keep oldest assigned vehicle as `ageYears`; retain first-observed duration as a separately labelled observation, never merge it with age using `max`. If a report uses an observed service-span policy, label it separately; the three-year age threshold must use exactly the methodology age fact. |
| Decision/report follow-up | Show `elapsedGameYears` with shared provenance. If displaying `elapsedNominalWindows`, derive raw tick difference / nominal duration separately and label it a collector query-window diagnostic, not proven `profitYear` completeness or evidence of causal outcomes. Remove the misleading unqualified `window complete` label. |
| Company year-ago comparison | Select at/before the mapped date 365.25 GAME-DAY before the evaluation snapshot, disclose actual baseline date/span and missing baseline; no `gameTime - yearDuration` substitute. |
| Lifespan/end-of-life | Carry known age as GAME-YEAR, keep model lifespan units/caveats. Do not publish a numeric age/lifespan ratio where its denominator's clock/unit is unverified. This does not expand into lifespan verification. |
| Report/MCP/JSON metadata | Add `timeBasis` alongside existing methodology provenance in summaries/manifests and service payloads. Preserve existing list-returning tools: add per-row metadata to age-bearing rows instead of wrapping lists in new objects. Findings evidence carries time provenance when it depends on age. Markdown/HTML show the same basis/coverage note; XLSX summary includes it. |

Findings may still report a directly observed loss when age is unknown, but cannot assert the line is mature/young or that its rolling financial window is complete. Existing conservative unknown-maturity severity policy may remain if explicitly described as policy rather than a measured age.

### D6. Migration, versioning and related-plan boundaries

No SQL schema migration, raw JSON rewrite, purchase-time backfill or decision timestamp conversion is required. Derived values are recomputed on read using `game-calendar-v1`; chronology selection remains the store's responsibility. Existing schema-1/2/3 snapshots remain readable: valid dated histories can support conversion, missing dates produce explicit unknown, all-null lineage produces an isolation warning, and suspicious mixed/rewound histories refuse cross-snapshot conversion.

Do not edit player methodology files or silently bump their identities. Existing numeric parameters load unchanged; update packaged example descriptions/field catalog and release notes to announce the behavior break. A player may voluntarily revise their threshold, but only policy changes, never the numeric fact basis. Conversion metadata/anchor hash disambiguates old versus newly generated reports even if methodology bytes are unchanged. Existing generated output is not rewritten on upgrade; explicitly regenerating a report uses the normal overwrite behavior and new metadata. Old outputs without `timeBasis.version` are legacy/unknown-basis, not silently reinterpreted.

`cross-platform-and-saves` retains ownership of game-proven identity, save-as behavior, routing, backwards-jump reporting and migration. This change consumes its context but does not require unimplemented automatic isolation for conservative legacy operation. `analysis-insights` future fleet-fit/scope/follow-up must use this API, not its D6/D9/D10 nominal arithmetic; no geometry work is duplicated. `basic-reports` D4/D6 time assumptions are superseded only for time conversion, leaving annual sample coverage and non-summing financial rules intact. Coordinate the cutover before those unimplemented consumers land; do not create a parallel report subsystem.

## Risks / Trade-offs

- [Old purchases precede available history] → Return unknown rather than unverifiable extrapolation. P-020's recorded 10-to-2 count is not an acceptance target: the conservative clock may classify fewer entities because calibration cannot establish old purchase dates.
- [Interpolation misses a within-gap calendar-rate change] → Label it as estimate with exact anchors, minimum span and no extrapolation; no claim of engine-verified calibration. Accepting precise out-of-range ages would require new game-proven evidence and a separate reviewed change.
- [Legacy store may contain an undetectable merge/overwrite] → Mark all derived values `legacy-unverified`; refuse observable conflicts and gate claims of isolated/proven lineage on the existing save-isolation proposal.
- [Unknown age changes report ranking and rule outcomes] → Preserve null propagation and explicit missing rules; cross-consumer regression cases and release notes make the break visible.
- [Calendar normalization differs from exact anniversaries] → Publish 365.25 and leap-year examples; calendar annual reporting retains its separate year grouping.
- [Future insight plans reintroduce nominal arithmetic] → Their implementation must depend on this conversion contract for age and elapsed duration; nominal financial windows stay separately named.

## Migration Plan

1. Land the pure clock and deterministic scope/unknown tests without changing evidence storage.
2. Cut over all existing consumer paths in one release; delete obsolete report-specific calibrators and nominal age fallbacks, and retain nominal duration only for explicitly named source/financial diagnostics.
3. Regenerate the field catalog, update English knowledge/docs/changelog and packaged example descriptions, then run integration and isolated real-data checks from `tasks.md`.
4. Do not run automatic player-store migration, rewrite library files, or reissue historical reports. Rollback is a code/version rollback; raw evidence and decision data are unchanged. Outputs already generated with the new version retain their conversion metadata.

## Open Questions

No unresolved design choice blocks implementation. The game API's behavior under calendar/date-speed changes and reliable lineage are not established by inspected evidence; this change does not depend on guessing either. Broader conversion guarantees require player-controlled evidence and verified lineage from their owning proposal before any future relaxation of the conservative bounds.
