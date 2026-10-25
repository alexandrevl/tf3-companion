# First push to GitHub

This page is the maintainer's runbook for publishing the repository. Nothing in it is done by an agent or by CI: creating the repository, pushing, changing visibility and tagging are your decisions and your account actions. Steps marked **(you)** are commands you run; steps marked **(evidence)** say what proves the step worked.

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

## Before you push: decisions that cannot be undone

- **Your name and e-mail are public forever.** Every commit carries `Alexandre Lima <alexandrevl@gmail.com>`, and the same address is in `pyproject.toml`, `modinfo.json`, `SECURITY.md` and `CODE_OF_CONDUCT.md`. Check with `git log --format='%an <%ae>' | sort | uniq -c`. If you want another identity, rewrite history **before** the first push; after it, rewriting is disruptive.
- **Private first, public second (recommended).** The CI has never run. Windows in particular has had no hosted or real-installation run. Pushing to a private repository, letting the three-platform run finish and fixing what it shows keeps the public first impression clean. Going public immediately is also fine; it just means any first-run failure is visible.
- **Nothing here publishes a package or a mod.** PyPI and the in-game mod hub are separate manual decisions (`CONTRIBUTING.md`, `docs/publishing-mod.md`).

## Runbook

1. **Verify locally (you).** From the repository root, with `luac` installed (see `CONTRIBUTING.md`):

   ```sh
   git status                                 # clean; nothing unexpected is tracked
   uv sync --locked
   uv run pre-commit run --all-files
   uv run pytest
   uv build
   openspec validate --all --strict
   ```

   (evidence) every command exits 0. A leftover `openspec/changes/<name>/` from another session is not part of this repository's published state unless you commit it.

2. **Name the default branch (you).** The workflows and links assume `main`; the local branch may still be `master`:

   ```sh
   git branch -M main
   ```

   (evidence) `git branch --show-current` prints `main`.

3. **Create the repository (you).** On GitHub create `alexandrevl/tf3-companion`, **private**, with no README, licence or `.gitignore` (the repository already has them). With the GitHub CLI: `gh repo create alexandrevl/tf3-companion --private --source . --remote origin`. Otherwise add the remote yourself: `git remote add origin https://github.com/alexandrevl/tf3-companion.git`.

   (evidence) `git remote -v` shows `origin`.

4. **First push (you).**

   ```sh
   git push -u origin main
   ```

   (evidence) the branch appears on GitHub and the **CI** workflow starts.

5. **Watch the first CI run (you).** Open the **Actions** tab. The `test` job runs on Ubuntu, macOS and Windows (plus Ubuntu with Python 3.14); `lint`, `guards` and `openspec` run once. Expect to look closely at two unverified parts:
   - **Lua on every runner.** `leafo/gh-actions-lua` compiles Lua 5.4 on the runner; on Windows it needs the MSVC step that precedes it. `scripts/check_repo.py` fails, never skips, if `luac` is missing.
   - **Windows.** Nothing in the project has run on a Windows host yet. Failures there are information, not a reason to hide the run.

   (evidence) every job is green. If one fails, fix it on a branch, push, and repeat. This step is the evidence for the README's "GitHub Actions" row: update it only after the run exists.

6. **Turn on repository protections (you).** Settings, then:
   - **Branches**: protect `main`; require the `Lint and format`, `Repository guards`, `OpenSpec validation` and `Test` jobs and a pull request before merging.
   - **Code security**: enable **Private vulnerability reporting**, **Dependency graph**, **Dependabot alerts** and **Secret scanning** (with push protection).
   - **Actions, General**: allow actions created by GitHub and the verified or explicitly listed creators used here (`astral-sh`, `leafo`, `step-security`); set the default workflow token to read-only.

   (evidence) the Security tab shows the policy and the reporting button; the first Dependabot and CodeQL runs appear.

7. **Go public (you).** Settings, General, Danger zone, **Change visibility**. Do this only after steps 5 and 6.

   (evidence) the repository opens in a signed-out browser window.

8. **Optional: a first tag and draft release (you).** Only when you want release artifacts. The tag must equal the package version:

   ```sh
   uv run python scripts/release_assets.py check-tag v0.1.0
   git tag v0.1.0
   git push origin v0.1.0
   ```

   (evidence) the **Release (draft)** workflow creates a draft release with the wheel, the sdist and `tf3_companion_bridge-<revision>.zip`. Review it and publish or delete it yourself. The workflow never uploads to PyPI or the mod hub.

## Rollback

- **Before step 4**: nothing has left your machine. Undo with ordinary `git` on your local branch.
- **After step 4, still private**: fix forward on a branch; or delete the repository on GitHub (Settings, Danger zone) and start again. History is unchanged by either.
- **After step 7**: assume everything pushed is public and cached. Fix forward; rotating or removing something does not unpublish it.

## Pinned actions

Third-party actions are pinned to full commit SHAs (the `scripts/check_repo.py` `workflows` rule enforces it) and Dependabot proposes updates. Each SHA below was resolved with `git ls-remote https://github.com/<action> refs/tags/<tag>` on 2026-10-25 and matches the version comment in the workflow files.

| Action | Version | Commit |
| --- | --- | --- |
| `actions/checkout` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `astral-sh/setup-uv` | v10.3.2 | `07a047e608db84b3d8c06cd9a7c7dcc9c355c18e` |
| `leafo/gh-actions-lua` | v13.1.0 | `32909a2dea0a48c433aec79e7fcd31b4cd55800f` |
| `step-security/msvc-dev-cmd` | v1.13.1 | `22c98154b708dbd743e6f27a933cf6ceba3305c4` |
| `github/codeql-action` | v4.39.1 | `9b3254085494b55a0f7c4c2b3d2d52cc712ce370` |
| `actions/dependency-review-action` | v5.0.0 | `a1d282b36b6f3519aa1f3fc636f609c47dddb294` |
| `actions/upload-artifact` | v7.0.2 | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |
| `actions/download-artifact` | v8.0.2 | `9000827ccba6bdab643e8b6fd33ac0654aef8333` |

## What the local checks could not prove

Local verification covered the workflow syntax (`actionlint`, the GitHub workflow and Dependabot schemas), every script step the workflows run, and the Python suite on one machine. It did not and could not run the hosted jobs, Lua compilation on Windows, Windows or Linux behaviour, CodeQL, dependency review or the draft-release job. Those are proven by step 5 and, for the bridge mod's behaviour inside the game, by the player's own in-game checks listed in `TODO.md`.
