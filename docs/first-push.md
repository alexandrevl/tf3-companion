# First push to GitHub

This page is the maintainer's runbook for publishing the repository. Nothing in it is done by an agent or by CI: creating the repository, pushing, changing visibility and tagging are your decisions and your account actions.

## Repository identity

One decision, applied everywhere. If the name ever changes, change it in every place below and in `scripts/check_repo.py` (`OWNER`, `REPOSITORY`), whose link-identity check then tells you what you missed.

| Item | Value |
| --- | --- |
| Owner and repository | `alexandrevl/tf3-companion` |
| Repository URL | <https://github.com/alexandrevl/tf3-companion> |
| Security reports | GitHub private vulnerability reporting, fallback alexandrevl@gmail.com |
| Conduct reports | alexandrevl@gmail.com |
| Declared author (the only e-mail the guard allows) | alexandrevl@gmail.com |

Files that carry the identity:

| File | What it carries |
| --- | --- |
| `scripts/check_repo.py` | `OWNER`, `REPOSITORY`, `ALLOWED_EMAILS` (the single definition the guard enforces) |
| `.github/ISSUE_TEMPLATE/config.yml` | links to the troubleshooting guide and roadmap |
| `.github/CODEOWNERS` | the maintainer account |
| `pyproject.toml` | `[project.urls]` (Homepage, Repository, Issues, Changelog, Security) and the author |
| `mod/tf3_companion_bridge/_metadata/modinfo.json` | the listing `url` and the author |
| `README.md`, `CONTRIBUTING.md` | clone URL and links |
| `SECURITY.md`, `CODE_OF_CONDUCT.md` | reporting channels |
| `NOTICE`, `LICENSE` | copyright holder and attribution |
