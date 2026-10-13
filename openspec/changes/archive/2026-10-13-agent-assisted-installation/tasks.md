# Tasks

## 1. Canonical installation guidance

- [x] 1.1 Add packaged English setup guidance for Windows and macOS using the existing CLI and installation documentation; verify it covers source installation, path discovery, bridge revision, manual activation, client configuration and first report without assuming an unpublished package exists on PyPI.
- [x] 1.2 Add the README bootstrap request and link existing mod/client documents to the canonical guide; verify both local-terminal and text-only walkthroughs establish capabilities and explicit mutation consent, preserve unrelated client settings and distinguish local stdio from ChatGPT web connectivity.
- [x] 1.3 Document stage-specific completion evidence and recovery for warnings, missing snapshots, stale bridge, closed game and collection errors; verify a tabletop walkthrough of `doctor.ok=true` with missing-mod/missing-snapshot warnings cannot be reported as complete, and no game changes are implied.

## 2. MCP onboarding integration

- [x] 2.1 Expose `setup-check` and `tf3c://setup` through the existing packaged-resource and MCP registration conventions without initializing player storage; verify actual stdio retrieval with nonexistent game/userdata paths returns setup guidance and leaves the player database absent.
- [x] 2.2 Update packaged analyst instructions to select onboarding before data-dependent analysis when setup or observations are missing; verify the delivered instructions identify the appropriate first-use path and retain the read-only gameplay and save-isolation boundaries.
- [x] 2.3 Add deterministic regression coverage for bootstrap availability without game/data and behavior after installing the distribution; verify `uv run pytest tests/test_agent_experience.py tests/test_setup.py` passes without source-text assertions, prompt-wording snapshots or mock registration echoes.
- [x] 2.4 Reconcile only the active `agent-experience` six-only prompt-catalogue scenario, preserving all six analysis prompts and adding setup; update agent documentation, roadmap and changelog to reflect exercised behavior and outstanding real-platform release gates; verify both changes' prompt contracts agree.

## 3. End-to-end verification

- [x] 3.1 Run an isolated CLI setup/refresh/report smoke with temporary fixture paths and a newly produced snapshot; verify the new observation and generated report, distinguish this fixture evidence from real game verification and remove throwaway scaffolding afterward.
- [x] 3.2 Build with `uv build`, install the wheel into an isolated environment and connect over real stdio from outside the checkout; retrieve `setup-check`, read `tf3c://setup` and call `doctor`, verifying the guide is shipped, existing analysis prompts remain available and missing installation is not misreported as complete.
- [x] 3.3 Run `uv run pytest` and `openspec validate agent-assisted-installation --strict`, then record exact observed results and explicitly unperformed Windows/macOS GUI-client and player in-game activation/refresh/report checks; verify no fixture result is presented as proof of those external release gates.
