# Roadmap

TF3 Companion helps players understand their transport company through explainable local data, without automating gameplay. This roadmap describes **source delivery and release gates separately**. [TODO.md](../TODO.md) is the ordered work board; [OpenSpec changes](../openspec/changes/) own detailed acceptance tasks. An implemented feature does not mean its live-game or platform gates are complete.

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
| Insights and reports | Stored-only evaluation, seven structured analytical views, 14 report kinds, Markdown/offline HTML and XLSX; the private generator is retired | Collector semantics, entity-incarnation joins, per-view coverage accounting and live opening/rendering checks |
| Agent experience | Analyst instructions, offline `setup-check` onboarding prompt and `tf3c://setup` guide, six analysis prompts, knowledge/notes/latest-report resources; real stdio round trips verified | Rehearse guided installation and configuration in the intended third-party desktop/client applications on Windows and macOS |
| Data safety | Verified receipts, strict input validation, protected pruning and identified-lineage conflict rejection | Persistent save-identity probe and fully isolated lineage storage before claiming multi-save support |
| Public documentation | English quickstart, agent-assisted installation entrypoint and canonical setup guide, privacy, troubleshooting, reports, contribution guide and templates; installed-wheel smoke verified | Clean-machine and real-game quickstart rehearsal, including an assistant-guided run |
| Methodologies and time | Validated declarative policy, user/save/request selection, shared report criteria, calendar evidence and complete evaluation provenance | Real save isolation and unresolved game counter/model units are not supplied by policy |
| Engine knowledge | Seven packaged topics, including confidence-tagged engine/API research and explicit unknowns | New collector/ID-robustness scope remains exploration; imported claims do not become verified mechanics |
| Visual identity | Original tokens, vector/raster assets and listing generation/checking tools | Cover display in the game, gallery inputs, broader brand application and publishing acceptance |
| CI and repository gates | Hardened CI (lint, repository guards, strict OpenSpec validation, Linux/macOS/Windows tests with Lua 5.4 built per runner), CodeQL, dependency review, Dependabot, a draft-only release workflow and a pre-commit gate | First hosted run after a separately authorized push; configured CI is not executed CI, and Lua compilation on Windows runners is unproven until then |

See [review notes](review-notes.md) for evidence and remaining gates. No publishing, live mod installation or player-data changes are part of this local review.

## Locally verified

- Full behavior suite, including the Lua polling lifecycle, passes.
- Actual CLI exercised install/doctor/import/refresh/report/export/uninstall with isolated synthetic history.
- Real MCP stdio exercised tools, all prompts, resources, malformed/missing-data errors and the decision journal; setup guidance was retrieved from an installed wheel with no game or player storage.
- Wheel and source distribution built; wheel installed and exercised outside the checkout.
- Annual HTML inspected in Chromium without scripts, external resource requests or horizontal overflow at the inspected desktop viewport.
- Launch verification on 2026-10-25: locally `uv run pytest` passed 1008 tests, `ruff check`/`ruff format --check`, the repository guards (including `luac -p`, Lua 5.4.9), the pre-commit hooks, strict OpenSpec validation and the package build; on GitHub the CI run for commit `d930c6d` passed every job on Ubuntu (Python 3.12 and 3.14), macOS and Windows, including the installed-wheel acceptance tests. This is synthetic and installed-package evidence, not live-game certification.
- Installed-wheel analysis acceptance (`tests/test_installed_analysis.py`) passes on the development machine: the wheel was built and installed offline into a clean temporary environment and exercised outside the checkout (service, CLI and MCP evaluation, seven views, report publication, `analyse`) with synthetic evidence. This is not a clean-machine, real-game or Windows/Linux result.


## Next: release readiness

1. **Stabilize daily use.** The MCP connection lifecycle and line-detail cargo decoding are fixed (see [TODO.md](../TODO.md) Done). Continue the ordered **Next** lane: compatibility identifiers, entity-ID robustness and truthful multi-view coverage.
2. **Scope the next collector change.** Preserve the completed engine-knowledge research; decide the towns-only versus broader collector scope before adding APIs. Keep existing `analysis-insights` and save-lineage responsibilities explicit.
3. **Prove safe save identity.** Validate bridge-owned persistent lineage across reload, copies, new games and collisions before claiming automatic save isolation.
4. **Complete platform and game rehearsals.** Source tests do not prove game activation, cover rendering, GUI-client setup or Windows/macOS behavior. Keep those cards blocked until the required environment and player evidence are available.
5. **Reconcile release readiness.** Re-baseline its old tasks against existing packaging/docs/assets, settle version/schema/revision claims and capture approved gallery inputs. Hosted CI, tagging and publication are later explicit actions.

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
| [Rebrand](../openspec/changes/rebrand-tf3-companion/) | Delivered source plus outstanding default-app/live-cutover gates |
| [Cross-platform and saves](../openspec/changes/cross-platform-and-saves/) | Portable setup, discovery, save identity and collection controls |
| [Analysis insights](../openspec/changes/analysis-insights/) | Remaining collector-linked analysis and game-semantic validation |
| [Basic reports](../openspec/changes/basic-reports/) | Delivered reports with remaining model-unit and platform acceptance |
| [Agent experience](../openspec/changes/agent-experience/) | Delivered protocol surface with remaining GUI-client/live rehearsals |
| [Service boundaries](../openspec/changes/service-boundary-hardening/) | Source safety work with a remaining live bridge check |
| [Visual identity](../openspec/changes/visual-identity/) | Source identity delivered; live cover acceptance pending |
| [Mod listing assets](../openspec/changes/mod-listing-assets/) | Generation/checking tools and remaining player-approved gallery/game checks |
| [Brand application](../openspec/changes/brand-application/) | Planned shared token application to product surfaces |
| [Release readiness](../openspec/changes/release-readiness/) | Re-baselined against delivered work; open items are the player and game gates |
| [Public repository launch](../openspec/changes/archive/2026-10-25-public-repository-launch/) | Archived: MCP lifecycle and line-detail fixes, repository guards, pre-commit and CI hardening, governance files and the maintainer's [first-push runbook](first-push.md); the push itself stays manual |

Completed plans are retained under [the archive](../openspec/changes/archive/), including installation onboarding, data integrity, methodology activation/defaults/report policy, calendar time, structured evaluation/views, generator retirement and engine-runtime knowledge. Their implemented contracts live in [main specs](../openspec/specs/); do not reopen them merely to track a new bug.

## Lessons that shape the design

- Cargo configurations can be wrong even when a line runs: findings need explicit configuration evidence.
- Full industry stocks indicate a potential bottleneck, not automatically a profitable route.
- Instantaneous load is not sustained demand; compare observations before suggesting more vehicles.
- Rolling annual profit responds slowly to changes and cannot be summed as monthly income.
- Recommendations must name the affected entity and disclose incomplete collection.

## Boundaries

No automatic gameplay actions, hosted analytics service, telemetry or direct save-file reverse engineering are planned. Local analysis does not make an external AI client private: users control what they share with their provider. Trademark/name availability and distribution approvals have not been established. GitHub, PyPI and Mod Hub publication require a separate manual decision.
