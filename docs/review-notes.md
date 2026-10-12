# Review Notes and Unresolved Release Gates

This document records the evidence, assumptions, and open release gates established during the architectural review and source implementation of TF3 Companion.

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


## Local integration evidence

All review runs used synthetic player folders. The real mod installation, player database and private notes were not changed.

| Check | Observed result |
| --- | --- |
| `uv run pytest` | 107 passed, including the Lua write-failure/retry lifecycle, import safety, report semantics and installer preservation |
| `uv build` | Wheel and source distribution built successfully |
| Artifact inspection | Wheel contains analyst instructions, four knowledge topics, bridge assets and MIT license; neither artifact contains player databases/spreadsheets |
| Installed wheel | Version/knowledge/install/doctor/annual HTML/uninstall exercised outside the checkout; missing-game doctor did not create player storage |
| Real CLI | Install, doctor, import, overview, findings, line detail, notes, requested refresh, six report kinds, XLSX and uninstall passed with isolated fixtures |
| History retention | Thirteen monthly/baseline observations persisted in SQLite after raw-file pruning |
| MCP stdio | 23 tools, six prompts, three resources and one resource template; tool/report/journal/error/prompt/resource calls exercised |
| Resource failure paths | Missing snapshot/report and corrupt-database reads returned readable protocol errors; knowledge remained available |
| Browser | Generated annual HTML rendered in Chromium; zero scripts, zero external resource requests and no desktop horizontal overflow |
| OpenSpec | Eight changes passed `openspec validate --all --strict` |

Current compatibility identifiers: companion `0.1.0`, bridge revision `2`, snapshot schema `1`. This is source verification on macOS, not a public release or proof of real Windows/game compatibility.

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
