# Proposal

## Why

Users need help before the MCP server is connected, while existing setup documents assume a person can assemble installation, game activation and client configuration themselves. An agent must also distinguish a successful diagnostic from verified end-to-end readiness: `doctor.ok` can be true with no installed bridge or snapshots.

## What Changes

- Provide one packaged English installation guide, readable from the repository before installation and through MCP afterward.
- Add a README entry and focused documentation entrypoint for agent-assisted installation on Windows and macOS.
- Add the read-only MCP prompt `setup-check` and Markdown resource `tf3c://setup`, available without Steam userdata or player storage.
- Route first-use/missing-data guidance to onboarding instead of requiring current-state analysis tools first.
- Specify stage-specific evidence, permissions, safe recovery and partial-completion language; retain the current doctor contract rather than redefining `ok`.
- Reconcile the active `agent-experience` draft's exactly-six-prompt scenario with six analysis prompts plus onboarding.

## Capabilities

### New Capabilities
- `installation-onboarding`: Agent-independent bootstrap instructions, offline MCP setup guidance and evidence-based readiness criteria.

### Modified Capabilities

None in durable main specs, which are currently empty. The overlapping prompt-catalogue scenario in the active `agent-experience` change will be updated during application to avoid a contradictory six-only requirement.

## Impact

- Source: packaged setup Markdown, `agent_experience.py`, `agent_instructions.md`.
- Documentation: README, agent-assisted installation entrypoint, existing client/mod guides, roadmap and changelog.
- MCP: one additive prompt and one additive static Markdown resource; existing tools and prompts remain available. No new dependencies or bridge/schema changes.
- Verification: real stdio bootstrap with missing game paths, installed-wheel resource/prompt reads outside the checkout, isolated CLI setup/refresh/report smoke and existing regressions.

## Out of Scope

Remote HTTP/SSE servers, Secure MCP Tunnel, direct ChatGPT web connectivity, hosted services, telemetry, unattended dependency/mod/configuration changes, gameplay automation, PyPI/GitHub/Mod Hub publication and automatic save isolation. Real Windows/macOS game and third-party GUI-client rehearsals remain external release gates, not claims established by fixture tests.
