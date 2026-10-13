# Design

## Context

See proposal.md for motivation. The companion already has a read-only structured `doctor`, CLI mod installation and refresh/report operations. MCP creates its companion lazily and already packages static knowledge and agent instructions. The existing six prompts support analysis, not bootstrap. No durable main specs have been archived yet; the active `agent-experience` draft constrains its prompt catalogue to six names.

The diagnostic contract distinguishes errors from warnings. A successful `doctor.ok` is not a completeness signal and must remain backward-compatible.

## Goals / Non-Goals

**Goals:** Reuse existing installation commands and diagnostics; keep onboarding available before storage initialization; maintain one canonical body of setup guidance; verify the shipped package rather than only the checkout.

**Non-Goals:** A second installer, new diagnosis state machine, dependency manager, remote MCP transport or new game bridge behavior. The setup prompt guides a capable host agent; it does not itself acquire permissions or execute installation.

## Decisions

### One packaged guide, multiple entrypoints

Place the canonical English guide alongside packaged agent instructions. Load it using the existing package-resource convention, exposing it as `tf3c://setup` and composing `setup-check` with instructions to inspect `doctor` next. Repository documentation links to this guide and adds only the pre-connection bootstrap request and navigation.

An independent long-form documentation guide and resource copy were rejected because installation details would drift. A generic framework for installation recipes would add unnecessary machinery.

### Static onboarding, factual diagnosis

Keep prompt/resource reads independent of the lazy companion and database. The prompt asks the host to call `doctor` once connected; it does not embed a diagnosis taken at registration time. Follow existing MCP resource response and error conventions. Preserve the six analysis prompts and add the setup prompt as an additive surface.

Changing `doctor.ok` was rejected: existing consumers may rely on its error semantics. Guidance instead enumerates each readiness stage and interprets warning details. There is no automatic recommendation to refresh unless the player confirms the game is open with the mod enabled.

### Two execution modes and explicit consent

The bootstrap request first establishes whether the assistant has approved terminal/filesystem access. A capable local agent can perform authorized local actions using documented commands; text-only chat supplies commands for the player. Neither mode implies permission to install software, overwrite mods or alter client configuration. Guide merge-only configuration examples and manual game activation.

Do not ship an MCP `install` tool. Installation must also work before MCP exists, and mutation exposed through a generic read-only analyst server obscures permission boundaries. Local stdio client support is separate from ChatGPT web's remote-connectivity requirements.

### Stage-based proof, not a binary success label

The guide records distinct evidence for the executable, expected bridge revision, an actual MCP round trip, a newly requested snapshot and generated report. Existing observations cannot prove the current loaded save or mod activation. If the game step is pending, stop with a precise partial-completion statement. Surface collection errors and current save-isolation limits even after refresh succeeds.

### Reconcile overlapping planning contracts

During application, update only the active `agent-experience` prompt-catalogue scenario that assumes exactly six prompts, preserving its six analysis names and adding `setup-check`. Do not rewrite unrelated artifacts or invent a MODIFIED durable capability when none exists. Update documentation/roadmap status only after exercised implementation evidence.

## Risks / Trade-offs

- Agents may equate diagnostics success with readiness -> include missing-mod and missing-snapshot warning examples and consumer-visible regression coverage.
- Package-data omission can break onboarding after installation -> build/install the distribution in isolation and retrieve resource/prompt outside the checkout.
- Client configuration formats and capabilities vary -> keep examples scoped to supported documented clients and distinguish instructions from observed GUI success.
- Historical snapshots may belong to another save -> require a fresh request, cite its date and disclose the existing lack of guaranteed save isolation.
- Fixture smoke cannot prove Steam/game or GUI-client compatibility -> retain real Windows/macOS client and in-game walkthroughs as explicitly unverified release gates.

## Migration Plan

Ship the packaged guide and additive MCP surfaces together with the README entrypoint and analyst routing. Existing clients retain their tools and analysis prompts; no player-store migration is required. Reconcile the overlapping draft before validation. Rollback removes the new setup prompt/resource and their documentation links without touching player data, installed mods or existing client configuration.
