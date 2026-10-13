# Roadmap

TF3 Companion helps players understand their transport company through explainable local data, without automating gameplay. This roadmap describes **source delivery and release gates separately**. Detailed proposals, designs, specifications and acceptance tasks live in [OpenSpec changes](../openspec/changes/); an implemented feature does not mean its whole proposal is complete.

## Delivered foundation

The current source tree provides:

- An English-language `tf3companion` package, `tf3c` CLI and read-only bridge mod.
- Snapshot ingestion, SQLite history, company/line/vehicle queries and explainable findings.
- Cargo opportunities, vehicle catalog access, player notes and a decision journal.
- XLSX exports and an MCP stdio interface with packaged knowledge.
- Local data storage outside the checkout and an MIT license credited to Alexandre Lima.

These are source capabilities, not evidence of a published package or compatibility on every operating system.

## Current delivery: usable, reviewable source build

| Workstream | Source deliverable | Acceptance still required |
| --- | --- | --- |
| Portable setup | Read-only doctor, conservative Steam discovery, explicit overrides, portable mod install/uninstall | Clean-machine setup; real Windows and macOS game activation/refresh; Linux/Proton evidence where available |
| Insights and reports | Explainable findings, six report kinds, annual coverage, decision follow-up, Markdown and offline HTML | Review collector-gap behavior and model units against real observations |
| Agent experience | Analyst instructions, offline `setup-check` onboarding prompt and `tf3c://setup` guide, six analysis prompts, knowledge/notes/latest-report resources; real stdio round trips verified | Rehearse guided installation and configuration in the intended third-party desktop/client applications on Windows and macOS |
| Data safety | Verified receipts, strict input validation, protected pruning and identified-lineage conflict rejection | Persistent save-identity probe and fully isolated lineage storage before claiming multi-save support |
| Public documentation | English quickstart, agent-assisted installation entrypoint and canonical setup guide, privacy, troubleshooting, reports, contribution guide and templates; installed-wheel smoke verified | Clean-machine and real-game quickstart rehearsal, including an assistant-guided run |
| CI | Locked Python tests and package builds on Windows/macOS/Linux | First hosted run after a separately authorized push; configured CI is not executed CI |

See [review notes](review-notes.md) for evidence and remaining gates. No publishing, live mod installation or player-data changes are part of this local review.

## Locally verified

- Full behavior suite, including the Lua polling lifecycle, passes.
- Actual CLI exercised install/doctor/import/refresh/report/export/uninstall with isolated synthetic history.
- Real MCP stdio exercised tools, all prompts, resources, malformed/missing-data errors and the decision journal; setup guidance was retrieved from an installed wheel with no game or player storage.
- Wheel and source distribution built; wheel installed and exercised outside the checkout.
- Annual HTML inspected in Chromium without scripts, external resource requests or horizontal overflow at the inspected desktop viewport.
- All nine OpenSpec changes validate strictly. Detailed evidence and limitations are in [review notes](review-notes.md).


## Next: release readiness

1. **Prove safe save identity.** Validate bridge-owned persistent lineage across save/reload, copies, new games and collisions. Route snapshots, notes and decisions without mixing unrelated games; never infer identity from town names or ids.
2. **Complete platform rehearsals.** Run install → enable → reload → refresh → first finding on real Windows and macOS installations. CI proves Python behavior, not game APIs or mod activation.
3. **Settle unknown game semantics.** Verify `transportedYear`, lifespan units, station links and position provenance before using them in accounting or route-fit claims.
4. **Exercise the release artifacts.** Inspect built wheel/sdist contents, perform an installed-wheel smoke run, validate mod bundle layout, and run Lua structural/harness checks where implemented. Stubs cannot prove game API signatures or persistence.
5. **Capture real visuals.** Create original branding and player-approved screenshots of the mod list, a finding and an offline report. Verify thumbnail format in the actual game. No placeholder images or borrowed game artwork.
6. **Prepare a reviewed release.** Confirm version/schema/mod-revision compatibility, changelog accuracy, license inclusion, privacy of fixtures and a complete manual checklist. Publication is a later, explicit action.

## Later: better longitudinal decisions

- Reliable save selection and isolated histories once persistent lineage is demonstrated.
- Collection interval controls and measured compression improvements without sacrificing evidence.
- Station-linked cargo mismatch and route-scope economics with verified schema fields.
- Vehicle suitability and renewal recommendations with verified units and catalog constraints.
- Follow-up on player decisions after enough observed game time, with honest uncertainty.

Future features remain OpenSpec work, not promises that all game mechanics are already known.

## OpenSpec workstreams

| Plan | Scope |
| --- | --- |
| [Rebrand](../openspec/changes/rebrand-tf3-companion/) | Product/package names, English artifacts and local storage foundation |
| [Cross-platform and saves](../openspec/changes/cross-platform-and-saves/) | Portable setup, discovery, save identity and collection controls |
| [Analysis insights](../openspec/changes/analysis-insights/) | Cargo/fleet/stock/trend analysis and verified economic interpretation |
| [Basic reports](../openspec/changes/basic-reports/) | Markdown, offline HTML and honest annual observation coverage |
| [Agent experience](../openspec/changes/agent-experience/) | MCP analyst instructions, prompts and resources |
| [Release readiness](../openspec/changes/release-readiness/) | Packaging, CI, documentation, fixtures, assets and manual release gates |
| [Data integrity](../openspec/changes/data-integrity-hardening/) | Parser/model boundaries, verified import receipts and chronological queries |
| [Service boundaries](../openspec/changes/service-boundary-hardening/) | Refresh locking, bridge acknowledgment, import errors and safe report output |
| [Agent-assisted installation](../openspec/changes/agent-assisted-installation/) | Pre-connection bootstrap request, offline MCP setup guidance and stage-based readiness evidence |

## Lessons that shape the design

- Cargo configurations can be wrong even when a line runs: findings need explicit configuration evidence.
- Full industry stocks indicate a potential bottleneck, not automatically a profitable route.
- Instantaneous load is not sustained demand; compare observations before suggesting more vehicles.
- Rolling annual profit responds slowly to changes and cannot be summed as monthly income.
- Recommendations must name the affected entity and disclose incomplete collection.

## Boundaries

No automatic gameplay actions, hosted analytics service, telemetry or direct save-file reverse engineering are planned. Local analysis does not make an external AI client private: users control what they share with their provider. Trademark/name availability and distribution approvals have not been established. GitHub, PyPI and Mod Hub publication require a separate manual decision.
