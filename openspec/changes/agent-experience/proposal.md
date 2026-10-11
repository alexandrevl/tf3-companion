# Proposal

## Why

Today the analyst persona (role, rules of evidence, how to treat decisions) lives in the repo's `AGENTS.md`, in Portuguese, and only works when the agent is opened inside this repository. A player who installs TF3 Companion with `uvx` and plugs it into Claude Desktop, Cursor, Codex or omp gets 20 bare tools, a three-line server `instructions` string and no guidance on workflows. The product's "agent-agnostic" principle (ROADMAP §1, items B5/B6) requires the persona and the common workflows to ship inside the MCP server itself.

## What Changes

- **Server instructions**: replace the short Portuguese string with a complete English analyst brief delivered in the MCP `initialize` response: data before opinion; cite numbers and the snapshot date; use full entity names; explain mechanisms from the knowledge base or flag them as hypotheses; offer options with trade-offs; record decisions and review planned ones; answer in the user's language; the mod is read-only, so tell the player what to click.
- **MCP prompts** (new): `monthly-review`, `annual-review`, `line-triage`, `fleet-renewal`, `cargo-opportunities`, `decision-review`, each with typed arguments, that tell the agent which tools to call and in what order.
- **MCP resources** (new): the knowledge-base index and each topic, the active save's notes, and the latest generated report of the active save.
- **Tool descriptions**: all tool and parameter descriptions in English, one consistent shape (what it returns, when to use it, what it needs).
- **Actionable errors**: every expected failure (no snapshot, game closed, unknown line, unknown topic, no report yet, no save selected) states the cause and the next step for the agent or the player.
- **Contributor `AGENTS.md`**: rewritten as a developer guide (layout, commands, conventions, how to add an analysis/tool/prompt, in-game validation rules). The player persona no longer lives there; `CLAUDE.md` simply points at it.
- Dependency floor: `mcp` is raised to the 2.x line already installed (`MCPServer` with `instructions`, `@prompt`, `@resource` is verified present in 2.3.0).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-interface`: ADDED requirements for server instructions, prompts, resources, tool description conventions and actionable errors. No existing requirement changes behaviour (no MODIFIED/REMOVED).

## Impact

- Code: `mcp_server.py` (instructions, prompts, resources, tool docstrings, error text), `service.py` (small helpers to read the active save's notes and latest report), one new package-data file holding the instructions text, new tests under `tests/`.
- Docs: `AGENTS.md` rewritten for contributors; `docs/agents.md` (owned by `release-readiness`) can later link to the prompts list.
- Tool names and arguments are unchanged; existing agent configs keep working.

## Out of Scope

- New analyses, new tools, new report kinds (other changes own them; prompts only reference tools that already exist after changes 1–4).
- Translating finding texts or the knowledge base; the agent answers in the user's language.
- Prompt completion/autocomplete, sampling, elicitation or any MCP feature other than instructions, tools, prompts and resources.
- Per-agent configuration snippets (`release-readiness` documents them).
- HTTP/SSE transports; stdio stays the only supported transport.
