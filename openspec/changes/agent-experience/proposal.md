# Proposal

## Why

The analyst brief must ship with the MCP server so clients receive consistent evidence rules even outside the repository. The repository contributor guide is separate from the player-facing brief. Source-checkout installation is supported; published-package installation is not claimed until a package is actually released.

## What Changes

- **Server instructions**: replace the short Portuguese string with a complete English analyst brief delivered in the MCP `initialize` response: data before opinion; cite numbers and the snapshot date; use full entity names; explain mechanisms from the knowledge base or flag them as hypotheses; offer options with trade-offs; record decisions and review planned ones; answer in the user's language; the mod is read-only, so tell the player what to click.
- **MCP prompts** (new): `monthly-review`, `annual-review`, `line-triage`, `fleet-renewal`, `cargo-opportunities`, `decision-review`, each with typed arguments, that tell the agent which tools to call and in what order.
- **MCP resources** (new): the packaged knowledge index and topic template, the current companion store's notes, and its latest generated Markdown report. Knowledge requires no game setup; notes require an imported snapshot.
- **Tool descriptions**: all tool and parameter descriptions in English, one consistent shape (what it returns, when to use it, what it needs).
- **Actionable errors**: expected resource failures (no snapshot, unavailable configuration, unknown topic, unreadable file, no report yet) explain the cause and next step. Prompt inputs validate status, year and entity references.
- **Contributor `AGENTS.md`**: rewritten as a developer guide (layout, commands, conventions, how to add an analysis/tool/prompt, in-game validation rules). The player persona no longer lives there; `CLAUDE.md` simply points at it.
- Dependency floor: `mcp` is raised to the 2.x line already installed (`MCPServer` with `instructions`, `@prompt`, `@resource` is verified present in 2.3.0).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-interface`: ADDED requirements for server instructions, prompts, resources, tool description conventions and actionable errors. No existing requirement changes behaviour (no MODIFIED/REMOVED).

## Impact

- Code: `agent_experience.py` registers prompts/resources and loads packaged `agent_instructions.md`; `mcp_server.py` integrates it; `service.py` supplies shared static knowledge and latest-report reads. Behavior regression tests cover validation and missing resource data.
- Docs: `AGENTS.md` remains contributor-facing; `docs/agents.md` documents the prompt and resource interface.
- Tool names and arguments are unchanged; existing agent configs keep working.

## Out of Scope

- New analyses, new tools, new report kinds (other changes own them; prompts only reference tools that already exist after changes 1–4).
- Translating finding texts or the knowledge base; the agent answers in the user's language.
- Prompt completion/autocomplete, sampling, elicitation or any MCP feature other than instructions, tools, prompts and resources.
- Per-agent configuration snippets (`release-readiness` documents them).
- HTTP/SSE transports; stdio stays the only supported transport.

## Delivery boundary

This implementation uses the existing single companion store. Per-save selection and isolation are not delivered by this change, and resources must not claim otherwise. Annual-review guidance distinguishes observed checkpoints and rolling profit from calendar-year income. Entity names, notes and reports are untrusted data, not instructions. SDK inspection and implementation do not count as a real-client or in-game acceptance check.
