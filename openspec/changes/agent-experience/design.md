# Design

## Context

`mcp_server.py` builds a single `MCPServer` (mcp 2.3.0) with a Portuguese `instructions` string and 20 tools registered through a `tool()` wrapper that converts `NoSnapshotError`, `LookupError` and `ValueError` into `ToolError`. Introspection with `uv run python` confirmed that this SDK supports `MCPServer(instructions=...)`, `@server.prompt()` (arguments derived from the function signature, so they get `required` from defaults), `@server.resource(uri)` with `{param}` templates (listed as resource templates, default MIME `text/plain`, overridable with `mime_type`), `list_resource_templates`, and `add_prompt/add_resource`. The previous API name `FastMCP` does not exist in 2.x; `pyproject.toml` still says `mcp>=1.10` and must be raised. The player persona is in `AGENTS.md`/`CLAUDE.md` (Portuguese, repo-bound). After changes 1–4 the package is `tf3companion`, knowledge is package data, notes are per save, and a `report` tool and a reports folder per save exist.

## Goals / Non-Goals

**Goals:** the persona and workflows ship in the server; one source of truth per piece of text; everything testable without a game or a live MCP client.

**Non-Goals:** new tools or analyses; client-specific tweaks; prompt localisation (agents translate).

## Decisions

### D1. Instructions live in one packaged Markdown file
`src/tf3companion/agent_instructions.md` (package data, same loading mechanism as `knowledge/`) holds the analyst brief. `load_instructions()` reads it at import and passes it to `MCPServer(instructions=...)`. Nothing else restates it: prompts instruct the agent to follow server instructions and outline only workflow steps; `AGENTS.md` is strictly contributor-facing.
*Alternatives:* a Python string constant (harder to edit and diff); keeping `AGENTS.md` as the source (couples contributor rules to the persona and fails when the repo is absent).

### D2. Keep instructions short and tool-referencing
Target ≲ 60 lines. Sections: Role, Working method (numbered), Data caveats, Read-only, Decisions & notes, Style. Tool names appear in backticks; a test verifies each backticked name is a registered tool, prompt or resource name, so renames cannot silently rot the text.
*Alternative:* describing behaviour without tool names — rejected, agents need the entry points (`status`, `findings`).

### D3. Prompts as plain functions returning one user message
Each prompt is a plain function decorated with `@server.prompt()` that returns a string built from workflow steps. Arguments are optional with defaults, validated before rendering (`decision_review.status` allows only `planned`, `done`, `dropped`; `annual_review.year` requires positive integers; entity references reject empty/control characters). Templates tell the agent *what to fetch and in which order* and *what the answer shape is*; they do not embed dynamic snapshots or make-up unverified tools.
*Alternatives:* prompts that pre-fetch data and embed it (stale, large, fails when no snapshot); one generic prompt with a `workflow` argument (loses discovery in client UIs that list prompts as slash commands).

### D4. Resources: one template, three fixed URIs
`tf3c://knowledge` (index), `tf3c://knowledge/{topic}` (template), `tf3c://notes` (current store), `tf3c://report/latest` (current store). All `text/markdown`. Knowledge resources use static `Companion.knowledge` and require no game discovery. Notes require an imported snapshot via `companion.current()`. The latest report delegates to `companion.latest_report()`. Topic validation uses the existing topic catalog.
*Alternatives:* registering each topic as a static resource at import (breaks if topics are added at runtime); exposing the decision journal and snapshots as resources too — deferred, tools already cover them and large JSON resources are poorly supported by clients.

### D5. One error vocabulary
Domain exceptions already carry messages; the change moves the *wording* into them so CLI and MCP share it, and widens the wrapper in `tool()` to also wrap resource handlers (same `try/except`, raising `ToolError`/resource error). Message pattern: `<what happened>. <what to do next>.` Choice errors list valid values (`Valid values: planned, done, dropped`). Refresh timeout gets its own exception subclass so its message can list causes. `LookupError` for lines includes up to five close matches (case-insensitive substring).
*Alternative:* MCP-only error text — rejected, the CLI would show different advice for the same failure.

### D6. Tool descriptions via docstring convention
Docstrings are the single source: first sentence = what is returned; second = when to use; optional third = prerequisites. Parameter descriptions come from `Annotated[..., Field(description=...)]` so units and allowed values reach the schema. A test walks `list_tools()` and checks non-empty descriptions on every tool/parameter, and a small stop-word check flags Portuguese remnants (`não`, `são`, `linha de`, accented vowels in descriptions).

### D7. Dependency floor
`mcp>=2.0,<3` in `pyproject.toml` matching the lockfile; this removes the pretence that 1.x (`FastMCP`) works.

### D8. AGENTS.md rewritten for contributors
Sections: what the project is (one paragraph), layout, commands (`uv run pytest`, `tf3c doctor`, `tf3c mcp`), conventions (English only, read-only mod, no verbatim game code, finding `code`s stable), recipes (new analysis → `analysis.py` + `service.py` + tool + test; new prompt/resource; new data field → mod collector + `snapshot_schema` topic + `schemaVersion`), and in-game validation rules. `CLAUDE.md` becomes a one-line pointer to `AGENTS.md`.

## Risks / Trade-offs

- Client support for prompts/resources is uneven (some clients ignore resources) → instructions and tools remain sufficient on their own; resources and prompts are conveniences.
- Long instructions consume context on every session → keep ≲ 60 lines, move detail to knowledge topics read on demand.
- Prompts naming tools can drift from the tool set → registered-name test (D2/D3).
- Prompt text referencing `report` and annual report assumes change 4 landed → ordering of the roadmap guarantees it; the test would fail loudly otherwise.
- mcp 2.x is new; clients are unaffected (protocol-level), but contributors on 1.x environments break → floor raised (D7).

## Migration Plan

Single release, no data migration. Existing MCP configs keep working (tool names and arguments unchanged). Rollback is reverting the commit. Players with a repo-local `AGENTS.md` from the prototype lose nothing; the server now supplies the persona.

## Open Questions

- Whether to also expose the decision journal as a resource once clients handle larger resources well (deferrable).
