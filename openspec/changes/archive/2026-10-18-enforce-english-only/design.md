## Context

- `AGENTS.md` (294 bytes) reads "Follow AGENTS.md for repository conventions…", a self-reference with no content.
- `CLAUDE.md` is a symlink to `AGENTS.md` (`ls -la` shows `CLAUDE.md -> AGENTS.md`), not an empty file.
- `CONTRIBUTING.md` principle 4 ("Clean language separation") already requires English code, comments, docs and error messages, and says agents talk to players in their language via MCP instructions. It does not mention file names, gitignored paths or commit messages.
- `openspec/config.yaml` `context:` says to write every artifact, comment, doc and user-facing string in English; only OpenSpec-writing agents see it.
- `docs/agents.md` and `src/tf3companion/agent_instructions.md` are player-facing analyst instructions ("Answer in the player's language"). They are not the contributor role and stay unchanged.
- `data/` is gitignored and author-local. `data/analise/` holds Portuguese scripts and is out of scope. No `scripts/` directory exists yet.

## Goals / Non-Goals

**Goals:** one authoritative, short contributor file that every agent loads; the English rule stated once in full and mirrored briefly; a runnable check.

**Non-Goals:** output localization, touching `data/analise/`, CI enforcement, editing in-flight changes.

## Decisions

### D1: `AGENTS.md` is the single source; sections kept short
Sections: Language, Product boundary (read-only, no `api.cmd`, local-first), Verification (`uv run pytest`; Lua checked with `luac -p` only; in-game behaviour verified by the player), OpenSpec planning (changes under `openspec/changes/<name>/`, final task names an exact command, per `config.yaml` rules). Each section links to `CONTRIBUTING.md` rather than duplicating detail, so the two cannot drift.

### D2: Keep `CLAUDE.md` as the symlink
It already points to `AGENTS.md`; Claude-based agents get the rule with zero duplication. Alternative (a one-line `CLAUDE.md` saying "see AGENTS.md") adds a hop an agent may not follow. Risk: Windows checkouts without symlink support materialize it as a text file containing `AGENTS.md`. Accepted: the task checks the symlink and, if the repository is meant to support symlink-less Windows checkouts, the implementer may replace it with a regular file holding the same content (recorded as open question).

### D3: Language rule wording
Scope is "anything written to disk or history": code, identifiers, file and folder names, comments, docstrings, string literals, tests, scripts, docs, commit messages, OpenSpec artifacts. Explicitly includes gitignored `data/` and `scripts/`, because that is where the violations originate. Domain terms use English names. Conversation may use the player's language but never leaks into files.

### D4: Localization is deferred
Player-facing rendering in the player's language is neither required nor forbidden. The invariant recorded is that source contains no localized literals. If localization is wanted, a future change designs a message-catalog approach.

### D5: `CONTRIBUTING.md` mirrors in principle 4 only
Extend principle 4 with file/folder names, tests, scripts, commit messages, gitignored paths, and a pointer to `AGENTS.md`. No new section.

### D6: Verification command
Run from the repo root:

```sh
git ls-files -z | xargs -0 grep -nIE '[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]|\b(não|você|para o|ônibus|passageiros|gerar|raio)\b' -- ; test $? -eq 1
```

Must print nothing and succeed (grep exit 1 = no matches). `git ls-files` lists tracked files only, so ignored `data/` is excluded automatically. The implementer may need an allowlist if a tracked file legitimately contains such characters (for example third-party license text or a game-quoted proper name); any exception must be justified in the task, not silently skipped. The accent class can also hit non-Portuguese diacritics; review hits manually.

## Risks / Trade-offs

- Heuristic check misses unaccented Portuguese; mitigated by the word list and reading `AGENTS.md` and new files in review.
- The rule cannot be enforced on gitignored files by the check; it relies on agents reading `AGENTS.md`.

## Open Questions

- Should output localization ever be offered? Deferred to a future change.
- Should `CLAUDE.md` stay a symlink given Windows first-class support (D2)?
