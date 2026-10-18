# Proposal

## Why

Our packaged knowledge (`src/tf3companion/knowledge/`) comes from static reading of the game's scripts and the wiki. It says nothing about how the engine behaves at runtime: step length, threads, entity ids, Lua sandbox, crash and log artifacts, the shape of the Lua API we call. MPFever (MIT, a multiplayer mod for build 40420, https://github.com/dkdknight/MPFever, studied at commit `ae5fc96`) spent months measuring exactly that, plus company, town-rating and loan state that our mechanics notes only sketch. Importing it now, as labelled evidence, fixes real gaps in what the analyst can claim and feeds a second change that hardens the collector.

## What Changes

- Add a new packaged topic `engine` (runtime model): simulation step and clock, threads and Lua states, entity id lifecycle, Lua 5.2 behaviour, the game-state copy the UI reads, known engine assertions, what the sandbox exposes, per-build facts, and the file, log, save and crash locations.
- Add a new packaged topic `api_catalog`: the engine Lua calls and ECS components documented by MPFever and by our own collector, with argument and return shapes where known, the call-state restrictions, and which of them our bridge already uses. Includes the full component catalogue.
- Extend `mechanics.md` with additive sections (new ids M13 and up) and targeted refinements of M2, M7, M10 and M11: town rating formulas and keys, delivery and happiness statistics, company rank and experience, game-script state (loans, subsidies, notifications, permits), construction refunds and town side effects of builds, terrain and reputation, and day-length evidence.
- Extend `cargo_economy.md` and `strategy.md` only where the research confirms, sharpens or contradicts an existing item, citing the section ids.
- Extend `snapshot_schema.md` with an identity and timing caveats section and a "Collector gaps" table. The table lists data MPFever reads and we do not; it records gaps and implements nothing.
- Introduce an evidence legend for imported facts: source prefix `MPF:` and tag `[ADOPTED]`, meaning "taken on MPFever's word, not verified by us", always stating the author's own confidence class (observed, read from game code, assumed, or claimed). MPFever's own internal contradictions get `[DISCREPANCY]`.
- Stamp every new or changed section with the game build the research covers (40408 and 40420) and with `[UNVERIFIED]` where we have not checked it.
- Add the open-questions list as `[UNVERIFIED]` items so each is a future in-game or file check.
- Add file locations, log rewrite behaviour and crash artifacts to `docs/troubleshooting.md`.
- Add one analyst caveat to `agent_instructions.md` about reused entity ids (stays under the 60-line cap).
- Keep the six research dossiers under `openspec/changes/engine-runtime-knowledge/research/` as the evidence base; the knowledge files paraphrase them.
- Add a structural test for the evidence legend and update `CHANGELOG.md`.

## Capabilities

### New Capabilities

- `game-knowledge`: how packaged game knowledge is organised, sourced and labelled: topic set and discovery, citation and paraphrase rules, the evidence legend for facts adopted from third-party research, build stamping, and the identity and time caveats the analyst must respect.

### Modified Capabilities

None. No capability named `knowledge-base` exists under `openspec/specs/`; the unarchived change `rebrand-tf3-companion` defines one with a "four topics" wording. This change leaves that change untouched and reconciles the wording at archive time (see design.md).

## Impact

- Files: `src/tf3companion/knowledge/` (two new topics, edits to four existing files; `methodology-fields.md` is generated and is not touched), `src/tf3companion/agent_instructions.md`, `docs/troubleshooting.md`, `CHANGELOG.md`, one new test under `tests/`.
- Behaviour: `tf3c knowledge`, the MCP `knowledge` tool and the `tf3c://knowledge` resources list and serve the new topics automatically; no code change in discovery or packaging.
- Overlap with in-flight changes: `analysis-insights` tasks 1.4 and 8.2 edit the lifespan and `transportedYear` text in `mechanics.md` and `snapshot_schema.md`; `cross-platform-and-saves` task 5.2 edits the `snapshot_schema.md` header. This change adds sections and avoids rewriting those sentences (design.md, Decisions 6).
- No mod change, no collector change, no store change, no new dependency.

## Out of Scope

- Any change to the Lua bridge or its snapshot schema (collecting ratings, deliveries, game-script state, component census). Recorded as gaps for a second change.
- Hardening the store and decisions against reused entity ids (second change).
- Verifying every adopted claim in the game. Claims that can be checked cheaply against local game files are covered by a task; the rest stay `[ADOPTED]` or `[UNVERIFIED]`.
- Anything MPFever does to alter the game: native hooks, proxy DLL, command replay, lockstep, companies, networking, launcher, auto-update. Only the facts they uncovered are imported.
- Copying MPFever or Urban Games source. All text is paraphrased and cites file paths.
- Localising knowledge text, and an in-game window.
