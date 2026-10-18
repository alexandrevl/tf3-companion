# Proposal

## Why

The packaged neutral methodology is an initial option, not a compulsory player policy. Today `use` changes only an implicit/save binding, so players cannot choose one independent user default inherited by every unbound save without repeatedly configuring saves.

## What Changes

- Add a distinct user default at the companion library root, selected and reset without editing packaged files, finding a game installation or loading a save.
- Resolve explicit request > save override > user default > packaged `default`; importing or dropping in a file never activates it.
- Preserve `use`/`unuse` as save-override operations, add `set-default`/`clear-default`, and expose equivalent deliberate MCP configuration tools.
- Display the library root, user default, save override, effective identity/hash and selection origin separately. **BREAKING**: replace ambiguous `binding`/`default` origin values and listing fields with explicit scope names; migrate all internal consumers and tests together.
- Retain reference semantics: bare ids float to the highest valid numeric version; `id@version` pins a version, not content. Broken selected references fail rather than silently selecting a lower-priority policy.
- Treat existing `<data>/methodology.json` and `saves/<id>/save.json` methodology values as save overrides; never promote them to a user default.
- Reuse the common activation gate from `validated-methodology-activation` before committing a selection or applying a selected file; failed validation preserves prior configuration and generated results. This change does not redefine author diagnostics or missing-data eligibility.

## Capabilities

### New Capabilities

None. This is an extension of the existing methodology library contract.

### Modified Capabilities

- `methodology-library`: independent user-default storage, four-level selection, explicit scope inspection and CLI/MCP selection/reset workflows, and legacy save-override compatibility.

## Impact

Targets `methodology/{scope,resolve,library,cli,lens,engine,summary}.py`, provenance output consumers, `service.py`, `mcp_server.py`, CLI help, analyst instructions, existing methodology tests and `docs/methodologies.md`. The methodology JSON schema `tf3c-methodology/1`, packaged files, evidence database, collector and game mechanisms remain unchanged. User-default configuration is local to the resolved `data_directory()` library root, not a machine-wide preference: `TF3C_DATA_DIR` intentionally selects an independent library and default.

## Scope and Non-Goals

This change manages companion analysis policy only. Collection/ingestion remains possible without any user methodology and despite broken analysis-policy configuration. No mod installation, bridge change, network access, plugins, localization, save-identity inference, report-policy redesign or historical verdict migration is included.

## Dependencies and Ordering

Implement on the archived `analysis-methodologies` baseline. Core preference and implicit-save behavior has no dependency on `cross-platform-and-saves`. That existing change owns verified lineage, active-save routing and data migration; integrate its selected scope when available, never invent a second save registry or claim that the current manually addressable folders establish save isolation. Test A/B inheritance with synthetic save scopes now; real automatic routing remains blocked by that change's in-game lineage validation. `analysis-insights` geometry and `basic-reports` completion do not block this change and are not duplicated here.

`validated-methodology-activation` is a prerequisite for the selection/application gate. Its strict support checks distinguish unsupported policy from normal per-entity missing evidence; this change consumes that contract rather than creating a second validation policy.
