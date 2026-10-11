# Tasks

## 1. Dependency and instruction source

- [ ] 1.1 Raise the `mcp` constraint to `>=2.0,<3` in `pyproject.toml`, run `uv lock`, and verify `uv run python -c "from mcp.server.mcpserver import MCPServer"` succeeds.
- [ ] 1.2 Write `src/tf3companion/agent_instructions.md` (English, ≲ 60 lines: role, method, data caveats, read-only, decisions and notes, language) and include it as package data; verify it loads from an installed wheel via `uv build` and `python -c "importlib.resources..."` in a clean venv.
- [ ] 1.3 Load the packaged instructions in `mcp_server.py`; inspect the real MCP initialization response in a throwaway client smoke. Do not create tests pinning persona wording.

## 2. Tool descriptions and errors

- [ ] 2.1 Write clear English tool and parameter descriptions; inspect `list_tools()` in the real client smoke rather than maintaining a copied tool-list assertion.
- [ ] 2.2 Reword domain exceptions to the `<what>. <next step>.` pattern, add the refresh-timeout exception with likely causes, near-match suggestions for unknown lines, valid-value lists for enums; verify with parametrised tests covering the five error scenarios in the spec.
- [ ] 2.3 Extend the error-wrapping decorator to resource handlers and verify a failing resource read yields a readable error, not a traceback (test).

## 3. Prompts

- [ ] 3.1 Implement the six prompts with optional arguments and meaningful status validation. Keep a regression test for invalid status; inspect other prompt rendering through a throwaway MCP client.
- [ ] 3.2 Exercise each prompt with and without arguments through a real MCP session and inspect the rendered instructions; do not persist bare non-empty or mock-forwarding tests.

## 4. Resources

- [ ] 4.1 Implement `tf3c://knowledge`, `tf3c://knowledge/{topic}`, `tf3c://notes` and `tf3c://report/latest` as `text/markdown` resources delegating to the same service methods as the tools; verify tests for index, topic equal to the `knowledge` tool output, unknown topic listing available topics, notes present/absent/no-save, report present/absent with the actionable message.
- [ ] 4.2 Exercise resource/template discovery via the real client and inspect the MIME types and URIs; retain tests only for missing-data and isolation behavior.

## 5. Contributor guide and docs

- [ ] 5.1 Keep `AGENTS.md` as the English contributor guide and `CLAUDE.md` pointing to it; exercise the documented contributor commands and avoid copying the player persona.
- [ ] 5.2 Document prompts and resource URIs and check them against the live server during the smoke run.

## 6. Integration check

- [ ] 6.1 Run `uv run pytest` (all green) and `uv run python -c "from tf3companion.mcp_server import server; print(server.instructions[:200])"`.
- [ ] 6.2 In a real agent (Claude Desktop or omp) without any repo `AGENTS.md`, connect `tf3c mcp`, confirm the analyst tone and caveats appear, run `/monthly-review` from the prompt list, and open the `tf3c://knowledge/mechanics` resource; record the result in the PR description.
