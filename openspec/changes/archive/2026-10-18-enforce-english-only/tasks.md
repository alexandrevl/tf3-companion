## 1. Contributor instructions

- [x] 1.1 Rewrite `AGENTS.md` with sections Language, Product boundary, Verification, OpenSpec planning (design D1), consistent with `CONTRIBUTING.md` and `openspec/config.yaml`; remove the self-reference.
- [x] 1.2 In the Language section state the English-only rule per design D3, including file/folder names, commit messages, gitignored `data/` and `scripts/`, English domain terms, and that conversation with the player may use the player's language.
- [x] 1.3 Note in `AGENTS.md` that player-facing output localization is out of scope and source holds no localized literals.
- [x] 1.4 Confirm `CLAUDE.md` is still a symlink to `AGENTS.md` (`ls -la CLAUDE.md`); decide the Windows question from design D2 and record the outcome.

## 2. Contributing guide

- [x] 2.1 Extend `CONTRIBUTING.md` principle 4 per design D5 and link to `AGENTS.md`.

## 3. Verification

- [x] 3.1 Run `git ls-files -z | xargs -0 grep -nIE '[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]|\b(não|você|para o|ônibus|passageiros|gerar|raio)\b' -- ; test $? -eq 1` from the repo root; it must print no matches. Fix real Portuguese hits; justify any legitimate exception. Do not touch `data/analise/`.
- [x] 3.2 Read `AGENTS.md` end to end and confirm the Language section, the other three sections and no self-reference.
- [x] 3.3 Run `openspec validate enforce-english-only`.
