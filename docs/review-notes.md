# Review Notes and Unresolved Release Gates

This document records the evidence, assumptions, and open release gates established during the architectural review and source implementation of TF3 Companion.

## Consolidation review: 2026-10-18

- `uv run pytest`: **943 passed**, including installed-wheel synthetic analysis outside the checkout.
- `openspec validate --all --strict`: **21 passed, 0 failed** in the consolidation run; the subsequently archived data-integrity change synced four import-safety requirements.
- Methodology activation/defaults/report policy, calendar time, structured evaluation/views, generator retirement and engine knowledge are implemented and archived. OpenSpec acceptance does not replace live-game or platform evidence.
- A read-only code review found per-view hydration counters sharing operation-wide cache totals. Combined-view requests can therefore report misleading coverage; the fix is prioritized in [TODO.md](../TODO.md), not silently counted as complete.
- The older non-evaluate MCP tools still share a thread-affine SQLite connection. The stored-only evaluate tool has a per-call connection; that does not fix the older tools. Keep the reported thread error open.
- Line-detail cargo decoding/filtering, compatibility identifier reconciliation and ID-reuse robustness remain open. Source bridge payload revision, bundled metadata revision and readable schema range must not be conflated.
- The previous research session completed the tagged engine/API knowledge import and left only collector/robustness exploration. Its files and archived evidence are preserved; no unfinished collector implementation was discarded.
- `luac` is absent on this machine; this review does not claim a Lua syntax run. No live-game, Windows/Linux, clean-machine, hosted CI, push or publication check was performed.
- A personal save-directory default in an uncommitted archived calendar-smoke command was redacted before versioning; its environment override is now required explicitly. No player evidence is included.

The following original observations and integration results are historical baseline records, not current tool/topic counts or a current compatibility matrix.

## Evidence-backed review observations

1. **Local-first, read-only boundary preserved:**
   - The Lua bridge mod uses exclusively read-only game APIs (`guiUpdate`, inspection tables).
   - Snapshot exports write solely to the designated userdata sink (`towns_industries/`).
   - The CLI and MCP tools provide read-only queries and local analytics without game mutation commands (`api.cmd`).

2. **Cross-platform path discovery:**
   - Steam userdata layout on macOS is empirically grounded in observed Steam directories (App ID `3493540`).
   - Windows candidate paths inspect standard Steam registry and `Program Files (x86)` locations.
   - When multiple Steam accounts or ambiguous paths are present, discovery strictly halts and requires an explicit `TF3C_USERDATA_DIR` environment variable rather than guessing.

3. **Data safety and single-store protection:**
   - SQLite store enforces strict consistency: mixing differing `saveId` tokens or identified snapshots into an unpartitioned legacy database fails closed.
   - Import receipts verify source paths/content and preserve malformed, modified or conflicting files. Conflicts at a shared time across source paths fail closed; a verified rewrite of the same source path may replace that time's sample.
   - Raw pruning retains the ten newest successfully verified files; failed/unverified files remain. SQLite retains historical sample times, not every rewrite or simulation branch.

4. **Accounting and report integrity:**
   - In-game `profitYear` is verified as a rolling 12-month figure. The analysis and reporting layers forbid summing rolling profits into discrete calendar-year figures.
   - `transportedYear` figures remain explicitly flagged as unverified pending confirmed game accounting definitions.
   - Vehicle load readings are treated strictly as instantaneous snapshot observations, never as averaged line utilization.


## Historical local integration evidence

All review runs used synthetic player folders. The real mod installation, player database and private notes were not changed.

| Check | Observed result |
| --- | --- |
| `uv run pytest` | 108 passed, including the Lua write-failure/retry lifecycle, import safety, report semantics, installer preservation and offline stdio onboarding |
| `uv build` | Wheel and source distribution built successfully |
| Artifact inspection | Wheel contains analyst instructions, four knowledge topics, bridge assets and MIT license; neither artifact contains player databases/spreadsheets |
| Installed wheel | Version/knowledge/install/doctor/annual HTML/uninstall exercised outside the checkout; missing-game doctor did not create player storage |
| Real CLI | Install, doctor, import, overview, findings, line detail, notes, requested refresh, six report kinds, XLSX and uninstall passed with isolated fixtures |
| History retention | Thirteen monthly/baseline observations persisted in SQLite after raw-file pruning |
| MCP stdio | 23 tools, seven prompts (`setup-check` plus six analysis prompts), four resources and one resource template; tool/report/journal/error/prompt/resource calls exercised |
| Offline onboarding | From an installed wheel outside the checkout, with a missing game folder: `setup-check` and `tf3c://setup` returned the packaged guide, `doctor` reported `ok: false` with a `userdata` error, and no player storage was created |
| Setup stages (fixtures) | Real CLI with a synthetic userdata folder: `doctor` returned `ok: true` while `installed_mod` and `snapshots` were warnings; after `mod install` revisions matched (2/2); a simulated bridge answered `refresh` (`1980-01-01`) and `report company` succeeded. Synthetic answers do not prove the real bridge or game |
| Resource failure paths | Missing snapshot/report and corrupt-database reads returned readable protocol errors; knowledge remained available |
| Browser | Generated annual HTML rendered in Chromium; zero scripts, zero external resource requests and no desktop horizontal overflow |
| OpenSpec | Nine changes passed `openspec validate --all --strict` |

Identifiers recorded at that historical baseline: companion `0.1.0`, bridge revision `2`, snapshot schema `1`. They are not a current reconciled compatibility claim. This was source verification on macOS, not a public release or proof of real Windows/game compatibility.

---

## Unresolved release gates (prerequisites for public release)

The following items cannot be settled by local static analysis or automated tests alone and remain formal release gates:

| Gate | Category | Prerequisite evidence required |
| --- | --- | --- |
| **Real Windows game execution** | Platform | Live installation, activation, and snapshot refresh must be executed and confirmed on an actual Windows game machine. Unit tests and GitHub Actions runners do not establish game compatibility. |
| **Bridge-owned save lineage** | Data Safety | Bridge-owned persistent lineage IDs across game save, reload, "Save As", and new games must be validated in live gameplay before claiming multi-save automatic partitioning. |
| **Real-game visual assets** | Assets / Branding | Verify thumbnail format and presentation in the actual game, then create original branding and player-approved screenshots. No placeholder assets are shipped. |
| **First hosted CI run** | Quality / CI | Multi-platform GitHub Actions workflow (`ubuntu-latest`, `macos-latest`, `windows-latest`) is configured with locked dependencies; it must execute successfully on first upstream push. |
| **Third-party client rehearsal** | User Experience | Protocol behavior was exercised through a real stdio SDK client. Claude Desktop/Claude Code/Codex/omp GUI configuration and a live-game review still need their own evidence. |
| **Assistant-guided installation** | User Experience | Run the bootstrap request with a local terminal agent and with a text-only chat on clean Windows and macOS machines, through mod activation, a real refresh and the first report. |
