# TODO

Single project board. Read this before starting work; follow [the delivery process](CONTRIBUTING.md#work-tracking-and-delivery). OpenSpec owns detailed implementation checklists; this board owns priority, ownership, blockers and completion evidence. Checked boxes belong only in **Done**. One workstream is active per worktree, with one integration owner.

Review baseline: 2026-10-18, `uv run pytest` **943 passed**; installed-distribution acceptance **13 passed**; `openspec validate --all --strict` **21 passed, 0 failed**, including the newly synced import-integrity spec. These are local/synthetic checks, not real-game, Windows or release certification. Refresh the baseline when making changes; do not keep old task counts as current status.

Tags: `[P1]` correctness/safety, `[P2]` usability/delivery, `[P3]` exploration; `[bug]`, `[data]`, `[docs]`, `[debt]`, `[idea]`. New discoveries go into this board rather than expanding the active change. Session closure does not close unfinished work.

## In progress

No implementation is active after the consolidation pass. The next selected workstream must come from the ordered **Next** lane; no background implementation agents are running.

## Next

Order is deliberate. Resolve a card before starting a later one, or explicitly agree a reprioritization.

- [ ] `[P1][bug]` Fix the MCP SQLite thread-affinity failure on cached non-evaluate tools. `mcp_server.py` still shares a writable Companion; `evaluate` already owns a per-call read-only connection. Reproduce with an isolated store and actual threaded calls, implement one safe lifecycle for affected tools, and verify repeated requests without touching player data.
- [ ] `[P1][debt]` Reconcile compatibility identifiers and docs: bridge payload `MOD_REVISION=1` versus bundled metadata revision 3; writer schema 1 versus readable schemas 1-3; old revision-2 acceptance tasks. Determine which identifiers intentionally differ before changing them. Keep source/build identity separate from real-game activation evidence.
- [ ] `[P1][bug]` Repair line-detail capacity decoding and filtering (P-010/P-011). The service still returns zero-capacity entries and resolves the line's one-based cargo index as a cargo ID. Prove correct names and positive-capacity-only output through CLI and MCP with synthetic fixtures before marking fixed.
- [ ] `[P1][debt]` Resume the preserved collector/identity exploration from the other session, not its already-completed knowledge import. Decide between towns-only verified calls (`getTownDeliveriesStats`, `getTownHappinessStats`, `getTown2personCapacitiesMap`, bulk `getLinesIssues`) and a broader collector. Include ID-reuse robustness and preserving the previous game log in the proposed scope; do not implement before the scope decision. Existing `analysis-insights` and save-lineage ownership must be reconciled, not duplicated.
- [ ] `[P1][debt]` Audit ID reuse across vehicle/line histories, decisions and comparisons (P-023): vehicle incarnation includes purchase time; line/entity joins need corroborating evidence rather than ID alone. Preserve this as part of the collector/robustness exploration unless a separate focused change is agreed.
- [ ] `[P2][bug]` Fix multi-view hydration coverage: a shared EvidenceReader cache makes later families report cumulative reads from earlier families, so requesting an unrelated view can change another view's coverage or exceed its stated limit. Track per-family evidence usage separately from operation-wide caching; verify single-view versus combined-view equivalence.
- [ ] `[P2][bug]` Make MCP runtime freshness visible: status currently has no package version, and a running server can retain old code/tool definitions. Document restart after upgrades and choose a runtime version diagnostic; do not promise hot reload.
- [ ] `[P2][bug]` Clarify overview comparisons (P-004): same-date previous snapshots are valid observations but need an explicit interval or a deliberate distinct-date baseline. Label raw `earnings` and rolling line profits without asserting unverified accounting semantics (P-005/P-021), including XLSX labels.
- [ ] `[P2][debt]` Re-baseline `release-readiness` against delivered code. Its asset tasks 6.1-6.5 are superseded by `mod-listing-assets`; packaging/docs/installed-wheel work partly exists. Keep unexercised release gates unchecked rather than applying all 41 historical tasks blindly.
- [ ] `[P2][docs]` Reconcile remaining active specs/docs with delivered capabilities, especially the rebrand knowledge-base requirement that still names four topics (runtime now has seven). Keep archived evidence historical and update current instructions rather than rewriting old results.

## Blocked

Source work can be committed without claiming these acceptance gates are complete. No live installation, gameplay action, publication or external account action is authorized by this board.

- [ ] `[P1][data]` Automatic save isolation: `cross-platform-and-saves` needs a player-controlled persistent save-identity probe across reload, save-as/copies and new games before choosing routing. Keep the single-store/legacy-unverified caveat until then.
- [ ] `[P1][bug]` Refresh false-negative observation (P-001): game wrote a request snapshot while refresh reported timeout. Keep the observation open; inspect acknowledgement/timing with a deterministic regression and confirm the bridge path in-game. Do not dismiss it by rerunning the same live request.
- [ ] `[P1][bug]` Invalid depot construction entity (P-002): the bridge catches component access errors but still reports invalid entities. Add a justified guard/skip policy and verify affected depots in-game; Lua syntax alone is insufficient.
- [ ] `[P1][data]` Establish `deliveredYear`/`consumedYear` and `transportedYear` windows before changing accounting interpretation (P-025). Some views/export still consume deliveredYear. `analysis-insights` owns the observations; unknown remains unknown.
- [ ] `[P2][data]` Validate loadConfig cargo-change behavior and vehicle lifespan/cost/speed units in-game (`analysis-insights`, `basic-reports`). Imported engine research notes a lifespan-unit discrepancy; do not silently convert it to a confirmed mechanic.
- [ ] `[P2][data]` Confirm trackTotalLength semantics against a real controlled observation (P-006); zero rail vehicles does not prove the exported value is wrong.
- [ ] `[P2][check]` Confirm doctor bridge_seen after actual activation (P-009). Existing earlier activation evidence is historical; source inspection alone does not establish the current live transition.
- [ ] `[P2]` `visual-identity`: source artwork and cover/subway requirements are implemented; its remaining gate is player verification of the cover in the game's mod list. Record evidence in the existing brand/publishing docs before archive.
- [ ] `[P2]` `mod-listing-assets`: original assets and generation/listing scripts exist; remaining work includes actual mod-list/Mod Hub checks, any required TGA fallback and four player-approved gallery images. Run `scripts/check_listing.py` when those inputs exist.
- [ ] `[P2]` `brand-application`: pending implementation; existing plan depends on `visual-identity`. Revisit that dependency explicitly rather than silently treating a pending in-game gate as passed. Scope: token loader, branded documents/XLSX/banner/MCP icons.
- [ ] `[P2]` `service-boundary-hardening`: live bridge reload/acknowledgement acceptance on macOS and Windows remains open; reconcile its old revision-2 wording with current metadata first.
- [ ] `[P2]` `rebrand-tf3-companion`: OS-default opening on macOS/Windows and player-controlled live bridge cutover remain open. Do not overwrite installed prototype data as cleanup.
- [ ] `[P2]` `agent-experience`: third-party client setup rehearsal and player-approved live review remain open. Passing stdio tests is not GUI-client acceptance.
- [ ] `[P2]` `basic-reports`: intended-surface Mermaid/default-app and Windows/macOS report-opening checks plus unresolved model units remain open.
- [ ] `[P2]` `cross-platform-and-saves`: real Windows/Linux discovery/installer/activation evidence, interval configuration and bridge lineage acceptance remain open; do not mark them complete because a session ended.
- [ ] `[P2][docs]` Clean-machine quickstart on Windows/macOS, first hosted CI run, tag, package/Mod Hub release and publication remain explicit manual gates.
- [ ] `[P2][debt]` Lua syntax verification: `luac` is not installed on this machine (`command not found` in this review). Do not install silently; once available, run `luac -p` against all mod Lua files and record syntax-only evidence.

## Backlog

These cards are not commitments or permission to expand the active change. Promote a card to **Next** before implementing it.

- [ ] `[P2][debt]` Audit cargo/town attribution in every analysis path (P-016/P-017). Use station groups for towns and capacity/configuration for cargo; line names remain display data. Existing methodology/expansion coverage is not proof of every path.
- [ ] `[P2][debt]` Consistent CLI output convention: `lines` already emits JSON but has no `--json` switch while `findings` does (P-007). Choose the consumer contract before adding flags.
- [ ] `[P2][check]` Catalog provenance (P-024): endpoint-bounded catalog selection exists, but verify whether every suitability view makes older catalog evidence explicit. No blanket "stale flag implemented" claim yet.
- [ ] `[P2][debt]` Translate the gitignored historical `data/analysis-rules.md` into English without losing recorded policy. Retired code is gone; this file is historical input, not a product dependency. Do not commit player records.
- [ ] `[P2][data]` Station positions plus industries/towns served (`analysis-insights` 1.3): required for supported distance ladders, route-scope economics and reliable cargo links; requires collector implementation and player validation.
- [ ] `[P3][data]` Total station terminals and actual aircraft holding/circling state. Aircraft-per-used-terminal remains screening, never measured capacity or congestion.
- [ ] `[P3][data]` Station types, actual population, line creation date and finance journal, if the API supports them. Current capacities and oldest-vehicle age are explicitly proxies.
- [ ] `[P2]` Remaining `analysis-insights`: station-linked cargo mismatch, route-length bands/scope economics, decision follow-up after the rolling window, findings code in exports and supported tool documentation. Follow its actual task dependencies; do not duplicate collector work.
- [ ] `[P3][idea]` More scannable overview/findings text with useful prioritization rather than a dense stream.
- [ ] `[P3][idea]` A second packaged, name-free methodology example; keep it optional rather than product policy.
- [ ] `[P3][idea]` General town/role balance and history views with attribution caveats. A line counted in multiple towns is network participation, not additive municipal accounting or proof of feeder causation.
- [ ] `[P3][idea]` Aircraft-maintenance finding, with observed condition and comparable evidence rather than invented replacement savings.
- [ ] `[P3][idea]` Distinguish never-served full outputs (opportunity) from served outputs that accumulate (possible bottleneck).
- [ ] `[P3][idea]` Cargo misconfiguration finding for supported configuration/station evidence (P-028); an empty vehicle alone is not proof.
- [ ] `[P3][idea]` Methodology authoring helper: explain validation diagnostics and supported fields, possibly a starter command.
- [ ] `[P3][idea]` Interview-driven methodology skill: decide project skill versus packaged MCP prompt; ask one playstyle question at a time; use schema/field catalog rather than a hard-coded vocabulary; support new and edited policies and name-free starts. Files/IDs stay English and contain no personal identifiers. Validate and evaluate before proposing deliberate import/activation; never activate from interview answers alone. Acceptance is an actual synthetic validate/evaluate run, not a test of skill wording.
- [ ] `[P3][idea]` Navigable offline report bundle (index plus linked pages), then a dashboard over structured results rather than parsed Markdown.
- [ ] `[P3][idea]` Revisit the earlier dashboard-data brainstorm now that seven structured analysis views exist: choose additional fields/services based on actual consumer gaps, not an unrestricted collection project.
- [ ] `[P3][idea]` Lua mock/harness improvements from the MPFever exploration, without presenting mocks as game-runtime verification.

## Done

Completed source work is distinct from public release and live-game acceptance. Evidence below was observed locally; historical examples are not continuously rerun claims.

- [x] 2026-10-18: Python full suite **943 passed** in this cleanup review; strict OpenSpec validation **21 passed, 0 failed** before the subsequent data-integrity archive.
- [x] `separate-analysis-evaluation`: 10/10 tasks, archived with synced `analysis-evaluation`/library specs; stored-only service/CLI/MCP evaluation and composite analyse/report workflow verified.
- [x] `extract-report-analyses`: 19/19 tasks, archived with synced `operational-analysis-views`; seven typed views, thin report builders and end-to-end synthetic smoke verified.
- [x] `retire-local-analysis-generator`: 13/13 tasks, archived; seven source scripts removed, optional packaged example preserved, installed-wheel analysis exercised offline outside the checkout with synthetic evidence; historical player outputs preserved.
- [x] `validated-methodology-activation`, `user-methodology-default`, `methodology-report-policies`, `consistent-game-year-accounting`: implemented and archived; consume the shared gate, precedence, criteria and calendar clock rather than parallel implementations.
- [x] P-020 age conversion: current line/vehicle age paths use the shared calendar evidence clock rather than nominal yearDuration; unknown ages remain unknown. Calendar regressions are included in the passing suite.
- [x] `engine-runtime-knowledge`: 33/33 tasks, archived with synced `game-knowledge`; packaged engine/API research imported with confidence tags. The other session had no half-written collector change; its remaining exploration is preserved in **Next**.
- [x] `data-integrity-hardening`: 8/8 tasks, strictly validated and archived in this cleanup pass; four safety requirements synced to main specs.
- [x] Visual-identity cover-map/subway source assets exist and source tasks are checked; its separate live-game acceptance remains in **Blocked**.
- [x] Architecture guide with Mermaid diagrams exists and is linked from README/CONTRIBUTING; methodology fidelity docs distinguish the prototype's watch-only policy from the unchanged optional packaged example.
- [x] 2026-10-18 consolidation: completed work moved to Done, remaining work prioritized, original ideas retained and manual gates left blocked; other-session knowledge work preserved. Accumulated source/assets/plans are recorded in coherent local commit groups; no push or publication.
- [x] Contributor workflow recorded in AGENTS/CONTRIBUTING: one worktree integration owner, one active workstream, verified completion, explicit handoff and authorized coherent commits.
- [x] ROADMAP and review notes reconciled with current delivery; old integration results labeled historical, architecture archive links repaired and known implementation limitations documented rather than claimed fixed.
