# Tasks

Implementation and observed verification are recorded separately. Per-save paths depend on verified lineage; the current single-store reports use `<data>/reports/` and do not claim automatic isolation.

## 1. Delivered source
- [x] Document model and Markdown renderer with table, markup and entity-name escaping.
- [x] Offline HTML with inline CSS and real SVG line/bar/pie rendering; no external assets or JavaScript.
- [x] Chronological, annual and current-time-bounded store queries.
- [x] Company report with financial comparisons, modal results and balance/loan history.
- [x] Non-overlapping line rankings, losses, missing stop/vehicle configuration and sampled occupancy trends.
- [x] Fleet report with measured ages, raw lifespan/unit caveats, losses, depot capital, catalog availability and verified-unit fitness guard.
- [x] Cargo report with near-capacity stocks, unshipped production, nearest industry consumers and closures.
- [x] Decision rationale/outcome and baseline-identity follow-up, including renamed/removed entities and young profit windows.
- [x] Annual coverage, exact sample dates, missing months, in-progress/rewind disclosure, rolling-profit semantics, network changes, modal comparison, year comparison and decision metrics.
- [x] Atomic service output; six CLI report kinds and MCP Markdown report tool; default-app opening only on request.
- [x] XLSX remains a separate raw-data export; formula injection and default-app failure handling are guarded.
- [x] English report usage and financial interpretation documentation.

## 2. Integration acceptance
- [x] Run the complete behavior suite after final integration, including monetary-window, malformed-input, ranking-overlap, renamed-entity and rewind regressions.
- [x] Generate all six Markdown/HTML report kinds through the actual CLI against isolated monthly history.
- [x] Exercise the report tool and latest-report resource over real MCP stdio.
- [x] Inspect multi-series history and modal SVG charts in a browser; verify no scripts or external resource requests.
- [x] Build and exercise an installed wheel outside the checkout.

## 3. Dependency and real-environment gates
- [ ] After persistent save lineage is proven, route reports and exports through per-save storage and verify cross-save isolation.
- [ ] Verify lifespan and model cost/speed units against live game observations before enabling age/lifespan or suitability verdicts.
- [ ] Inspect Mermaid rendering in the intended GitHub/client surface after a separately authorized publication/client setup.
- [ ] Rehearse default-app opening and report generation with player-approved real saves on Windows and macOS.

These pending gates preserve the original acceptance goals; fixture runs are not substituted for game or third-party-client evidence.
