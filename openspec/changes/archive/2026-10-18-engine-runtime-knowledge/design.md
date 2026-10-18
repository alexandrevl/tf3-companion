# Design

## Context

See proposal.md for motivation. Facts about the current repo that shape the approach (full survey in `research/our-knowledge-map.md`):

- `src/tf3companion/knowledge/` holds five flat `.md` topics. A topic's name is its file stem; any new `.md` there is listed and served by the `knowledge` MCP tool, the CLI and the `tf3c://knowledge` resources with no code change. Packaging ships the whole package tree. Subdirectories are not scanned.
- A topic's summary in the index is its first non-heading line. `mechanics` and `cargo_economy` currently show "Source conventions" as their summary.
- `methodology-fields.md` is generated from `methodology/catalog_doc.py`; a test fails if it is stale. It is not edited here.
- Existing evidence conventions: source prefixes `WIKI:`, `GM:`, `ECO:`, `SCR:`, `BASE:`, `TEAL:`, `CARGO:`, `IND:`; tags `[INFERENCE]`, `[UNVERIFIED]`, `[DISCREPANCY]`; `strategy.md` uses `[V]`, `[I]`, `[?]` and "Based on: §M#" lines. `strategy.md` cites `mechanics.md` ids M1 to M12, which must stay stable.
- Nothing in the topics covers threads, ECS, the Lua runtime, commands, or crash and log artifacts. The Lua bridge runs in the GUI half, reads through `pcall`, and writes only through `app.saveUserdata`.
- Research inputs: six dossiers under `research/` (changelog, two halves of the MPFever bridge, supporting Lua, native engine notes, and a map of our own files). Each fact in them carries an author-confidence tag, a `file:line` citation, a relevance rating, a suggested home and a NEW, CONFIRMS-EXISTING or CONTRADICTS-EXISTING status.

## Goals / Non-Goals

**Goals:**
- Every relevant, paraphrased fact from the dossiers lands in a topic with its confidence stated, so nothing useful stays in a scratch file.
- A reader can always tell a verified fact from an adopted one.
- The new text does not break existing section ids, generated files, or in-flight edits.

**Non-Goals:**
- Verifying all of MPFever's claims. Where cheap, tasks upgrade a tag; otherwise the tag stays.
- Deciding collector or store changes. Gaps are listed, and a second change decides them.

## Decisions

### 1. Two new topics, additive sections elsewhere

New flat topics `engine.md` and `api_catalog.md`; mechanics knowledge goes into new sections M13 and up plus small refinements in M2, M7, M10 and M11; schema caveats and the gaps table go into `snapshot_schema.md`.

| Content (research source) | Home |
|---|---|
| Clock, steps, threads, Lua states, entity ids, Lua runtime and sandbox, commands, construction and network behaviour, files, logs, crash artifacts, saves, language, builds, determinism evidence, ownership model (`native-engine`, `changelog`, `bridge-*`) | `engine.md` |
| Lua calls, argument and return shapes, call-state restrictions, component catalogue and fields, game-script paths and state shapes, events, UI hook and packaging formats, mocked-engine shapes (`bridge-*`, `support-lua`) | `api_catalog.md` |
| Town rating and delivery formulas, rating keys, company experience and rank, loan, subsidy, notification and permit state, refunds and build side effects, day-length evidence (`support-lua`, `bridge-*`, `changelog`) | `mechanics.md` M13 and up, plus refinements |
| Confirmations, contradictions or new heuristics tied to a mechanic | `cargo_economy.md`, `strategy.md` |
| Identity and timing caveats, collector gaps | `snapshot_schema.md` |
| File locations, log rewrite, crash artifacts | `docs/troubleshooting.md` |

Alternatives: one very large `engine` topic (rejected: the API catalogue is looked up by name, the runtime model is read through; they have different readers); subdirectories (rejected: not discovered); extending only `mechanics.md` (rejected: M-ids are game rules, not engine behaviour, and `strategy.md` expects M1 to M12 to stay stable).

### 2. Evidence legend for adopted facts

Source prefix `MPF:<file>` names the MPFever file (paths relative to its repo root). Tag `[ADOPTED: observed|code|assumed|claim]` states that we took the fact on the author's word and which class the author used. The legend, repeated once per topic that uses it, names the studied commit (`ae5fc96`), the MIT licence, and says every statement is paraphrased.

Alternatives: reusing `[INFERENCE]` (rejected: it means our own reasoning, and would hide that the author did the work); one tag per author class (rejected: four new tags for one idea); no tag (rejected: the analyst could not tell what was measured here).

### 3. Assume what the author assumed, and say so

Per the owner's call, author-assumed and author-claimed facts are imported rather than dropped. They are tagged `[ADOPTED: assumed]` or `[ADOPTED: claim]` and carry the author's own caveat. Rules that keep this safe:
- A `strategy.md` item that rests only on an adopted fact is marked `[?]`, never `[V]`.
- No report or methodology default may depend on an adopted fact in this change; tasks add none.
- Where the research is internally inconsistent, both versions are listed under `[DISCREPANCY]`. Known cases: whether the simulation reads the frame counter (notes say it does not appear to; a native comment lists call sites that do), the sync interval (200 ms in notes, 200 to 400 ms in a comment), and the game-day length (4 s in our M10 against a configuration value of 2000 ms that M10 already flags).

### 4. Verification pass against local game files

A bounded task group checks, where the game's script archives are available, the claims most likely to change an analysis: the rating formulas, the experience and rank rule, the loan payback rule, day length, and the lifespan unit. A confirmed claim loses `[ADOPTED]` and gains a `GM:`, `ECO:`, `SCR:` or `BASE:` citation. An unconfirmed or unavailable one keeps its tag. In-game checks stay `[UNVERIFIED]` with the check named.

### 5. Build stamping and no addresses

`engine.md` opens with "Studied builds" listing 40408 and 40420 and the research's identification method. Sections whose evidence is measured on one build say so inline. Executable addresses, struct offsets and hook sites are left out of packaged topics; only the engine behaviour that required them is kept.

### 6. Overlap policy with in-flight changes

`analysis-insights` (tasks 1.4 and 8.2) edits the lifespan unit and `transportedYear` text in `mechanics.md` M6 and M9 and in `snapshot_schema.md`; `cross-platform-and-saves` (5.2) edits the `snapshot_schema.md` header; the archived GAME-YEAR change owns `mechanics.md` "Time units". This change does not rewrite those sentences. It adds new sections and, where research bears on them, a "See also" line beside them. Either landing order then merges without a text conflict. Only one existing sentence is touched: the "IDs identify game entities while they exist" claim in the `snapshot_schema.md` header gains the reuse caveat, in a way that keeps the rest of the line intact.

### 7. Knowledge describes, never instructs

Research describes how the source mod hooks, replays and reloads the game. Topics keep only the engine behaviour behind each technique. This preserves the read-only boundary in `AGENTS.md` and keeps the topics from reading as a modding or cheating guide.

### 8. One analyst instruction

`agent_instructions.md` gains one line: confirm that two snapshots' ids refer to the same entity through its name or descriptors, because ids are reused. The file stays under its 60-line cap and keeps its backticked tool names valid.

### 9. Structural test

One test pins invariants a reader relies on, not wording: every line carrying `[ADOPTED` also carries an `MPF:` citation and a valid author class; packaged topics contain no executable-address-like hex literals; each new topic has a summary line that is not a legend line; the `[ADOPTED` and `MPF:` tokens are defined in a legend of each topic that uses them. It does not assert on prose.

### 10. Research kept in the change

Dossiers stay in `research/` of the change, which moves to the archive with it. They contain no localised text and no source copies.

## Risks / Trade-offs

- [Adopted facts turn out wrong] → each is tagged with the author's class; nothing in reports or methodologies depends on them; the verification task upgrades the cheap ones.
- [Large new text dilutes the topics an agent reads first] → new topics open with a one-line scope; `agent_instructions.md` still points only at the tool; additive sections carry stable ids.
- [Archive collision with `rebrand-tf3-companion`, which defines `knowledge-base` and says the tool returns "four topic names"] → this change names its capability `game-knowledge`, so the two specs do not collide on archive; the final task checks whether `rebrand-tf3-companion` has archived and, if so, raises the stale "four topics" wording for correction.
- [Edit conflicts with `analysis-insights`] → Decision 6.
- [Reading the new text as a how-to for modifying the game] → Decision 7.
- [Time-unit statements drift from the archived GAME-YEAR rules] → the `engine` time section states the step and counters only and points to `mechanics.md` "Time units" for accounting.

## Migration Plan

Additive documentation. Order of landing: legend and test scaffold, `engine`, `api_catalog`, mechanics sections, snapshot caveats and gaps, smaller docs, verification pass, final checks. Rollback is reverting the commit; no stored data or code depends on the new text.
