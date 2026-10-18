# Design

## Context

See `proposal.md` for motivation. Observed current boundaries:

- `loader.parse` checks bytes/UTF-8/JSON/schema and calls `validate(data)`; `load_file` and `Library.import_file` already reject structural failures. This is not a proposal to add missing structural validation from scratch.
- `Library.entries` isolates broken drop-ins and detects same-identity/different-hash conflicts; `resolve` chooses valid versions but has no strict support gate. `Resolver.use` resolves before writing metadata, while explicit paths and bound/default runtime resolution use normal loading.
- `resolve.validate_file(strict=True)` already rejects every non-`ok` static support row. `support.static_probe` identifies capabilities the release cannot collect, whereas `snapshot_probe` diagnoses missing stored data. These are different from per-entity not-evaluable values.
- `engine.effective_parameters` checks unknown names and broad types, but does not establish a full effective-policy validation contract. `build_lens` evaluates resolved objects directly; service `analyse`, `findings` and `report` share that boundary.
- `output.write_bundle` stages complete bundles, but `add_files` publishes individual report files and manifests sequentially, and `latest.md` is updated separately. Validation must precede all these writes; no failed validation should reach output helpers.
- Current `Issue` holds path/message, validation responses stringify issues, and MCP has inspection but no validation tool. `methodology_detail` ingests snapshots, so it cannot serve as the new read-only debugging operation.
- Existing tests deliberately load unknown fields and render unsupported/skipped items; distinguish low-level authoring/evaluator inspection tests from the stricter public activation path when updating them.

## Goals / Non-Goals

**Goals:** One reusable prepare/validate boundary with consistent diagnostics and fail-safe public operations. Preserve structural parsing as an authoring facility while preventing accidental partial activation. Keep static compatibility independent of the live game.

**Non-Goals:** Add a second rule engine, a trust database, signed files, generic plugins, network services, speculative retry logic or a transaction spanning unrelated user operations. Binding a methodology does not automatically analyse it, and analysis does not silently rebind it.

## Decisions

### 1. Separate inspection, compatibility and runtime evidence

Reuse loader/validator and support traversal, not a duplicate JSON validator. A structured validation report contains `structurallyValid`, `activationEligible`, `diagnostics`, source identity/hash when available, required-data/support rows and effective parameters when valid. CLI legacy `valid` remains mode-dependent: structural validity for plain validation and activation eligibility for `--strict`; explicit eligibility is always visible. Strictness is mandatory for import/selection/runtime and is not an application flag users can disable.

The static gate rejects unknown fields, unsupported schema/features, and catalog fields marked unavailable to this release's collector. Existing static `skipped` rows caused by never-collected data become blocking `unsupported-capability` diagnostics for activation. Runtime snapshot gaps remain `missing-data` warnings/skips and entity gaps remain `not-evaluable`; neither contributes to activation failure. No snapshot lookup or database open belongs in static validation. The neutral packaged default must also pass the same compatibility gate.

Rejected alternatives: globally prohibiting invalid draft files would break authoring; accepting a supported subset would contradict the user's intended policy; probing current snapshots during binding would create a no-snapshot lockout.

### 2. Prepare once per operation and use exactly those bytes

Add one internal preparation entry point integrating structural, static-support and effective-override checks. It returns an operation-scoped prepared value derived from immutable raw bytes plus full SHA-256 and effective parameters, or structured failure. Use the existing parser rather than interpreting a persisted `validated` flag. Deeply isolate/freeze effective data so mutable `Methodology.data` or override dictionaries cannot change after preparation.

At each import, bind, default setter or runtime request, read current candidate bytes and prepare them; within that operation copy/evaluate the captured bytes, not a later reread. A file edited after preparation cannot change that operation's evaluated content; the next operation sees the new hash and revalidates. Avoid persistent filename/mtime trust caches. Existing reference version/conflict selection remains authoritative; conflicting structurally valid files stay conflicts even if one is incompatible. A bare id first uses the existing highest structurally valid/conflict candidate rule and then gates that choice: do not silently choose an older version to conceal an incompatible latest candidate. Exact refs remain exact, not hash pins.

### 3. Gate every accepting entry point, keep non-activating access available

| Path | Required behavior |
|---|---|
| Managed import, including force | Prepare before directory creation or overwrite; write captured validated bytes atomically; retain existing identity conflicts and packaged protection |
| Drop-in listing | Inspect candidates independently; expose structural status plus eligibility/diagnostics; do not modify any file or selection |
| Save `use` and user-default setters | Resolve and prepare before atomic metadata replacement; keep old state on failure; no snapshots needed |
| Explicit CLI path or id, save binding, user default, packaged default | Prepare at runtime before lens evaluation, built-in policy application, rendering or publication |
| Lower-level lens/evaluation application | Require prepared effective policy or call the shared gate, so direct internal use cannot accidentally bypass it |
| Author inspection/debug | Parse/validate non-activating content without executing/evaluating a supported subset as an accepted analysis |

`user-methodology-default` owns `set-default`/`clear-default`, `set_methodology_default`/`set_save_methodology`, and origins `request|file|save-override|user-default|packaged-default`; this change supplies their gate, not another selection store. `methodology-report-policies` owns schema-1 `report_policies` registry/ranges/cross-field constraints; reuse its validator inside preparation and report exact policy paths. Effective overrides are validated as a complete set against declared types, finite values and existing use-site/domain constraints, without inventing new strategic ranges.

### 4. Debuggable diagnostics are data, not a prose-only exception

Extend the existing issue model with `category`, stable `code`, `severity`, RFC 6901 `path`, `itemKind`, `itemId`, `ruleId`, `message`, optional `hint` and parse `line`/`column`. Categories: `io`, `syntax`, `structure`, `reference`, `unsupported-schema`, `unsupported-feature`, `unsupported-field`, `unsupported-capability`, `override`, `conflict`; runtime coverage uses nonblocking `missing-data`/`not-evaluable`. Root path is `""`; unassignable ids are null. Rule errors use original array-index pointers (for example `/rules/2/outcomes/0/when/field`) plus stable author rule id, avoiding dependence on position alone. Override pointers use a documented separate `/overrides/<escaped-name>` diagnostic input namespace and may carry `relatedPaths` into the original methodology.

Accumulate safely independent errors; malformed JSON cannot provide semantic pointers, and unsupported major schema should not be semantically interpreted. Do not fabricate rule ids for unparseable input. Machine responses retain all collected diagnostics even if human exception summaries are shortened. Render text as existing escaped, size-limited untrusted data; validation proves compatibility, not playstyle quality or prompt-injection immunity.

### 5. Read-only CLI and MCP validation

Extend `tf3c methodology validate FILE [--strict] [--param NAME=VALUE ...]` to use shared reporting. Plain mode may return structural success while `activationEligible` is false; strict mode exits nonzero for every blocker. Both show all discovered diagnostics.

Add MCP `validate_methodology(methodology: str | None = None, content: str | None = None, parameters: dict | None = None)`: exactly one library reference or explicit draft JSON text is required; validation always reports activation eligibility. References must not be paths and resolve candidates through inspection, not activation, so damaged entries remain debuggable; invalid entries without recoverable ids can be debugged via supplied content. Multiple candidate sources/conflicts are explicit, never arbitrarily chosen. Content has the loader's byte/size limits and is never written to a temporary or library file. The caller deliberately supplies text; the tool never fetches it from a path or network. Do not construct `Companion`/Store or call ingest merely to validate; use the resolver/library inspection layer. Existing arbitrary-path restrictions on every other MCP operation remain intact.

Rejected alternative: a generic MCP file-reading validator would expand filesystem authority and is unnecessary for debugging.

### 6. Transactional preparation then publication

Failed preparation performs no library/config/report mutation, even with force or same-output-folder regeneration. Setters stage complete replacement metadata and atomically replace it only after successful preparation; import retains atomic byte replacement. Runtime prepares and renders everything in memory/staging before output publication. Reuse staged bundle replacement for analysis and extend single-report publication so files/manifest are complete before replacing existing content; update latest only from successfully prepared/rendered content. Validation errors must leave previous report folder, manifest and latest bytes untouched and publish no partial folders.

There is no promise to undo a successful independent `use` command if a later analysis fails for absent snapshots. A subsequent invalid disk edit must fail closed without erasing the stored binding or pretending cached old reports are fresh; users may explicitly restore/reselect a compatible file. Existing old reports remain readable as historical output with their original provenance.

## Risks / Trade-offs

- [Previously accepted files with unknown fields or never-collected geometry now fail activation] → Mark as breaking, provide exact diagnostics and preserve inspection/export/manual drafts; never auto-remove fields or enable fallback.
- [Existing highest-version semantics surprise users with an incompatible new drop-in] → Expose source/hash/eligibility in listing and explain exact-version selection; do not silently downgrade.
- [New schema-1 policy extensions and changed release support] → Validate through the current capability registry on every operation; old releases fail unknown structural keys rather than misapply them.
- [Accidental writes in debug tools via service initialization] → Test absent data directory and byte-level snapshots of configuration/database/reports; keep validation beneath Companion ingestion.
- [Output staging differences on Windows/macOS] → Reuse existing replacement/rollback helpers and explicitly test failures before publication; no network or game interaction is involved.

## Migration Plan

1. Introduce structured diagnostics/shared preparation while preserving inspection semantics; route every accepting caller through it.
2. Integrate user-default setters and report-policy validation when those changes land; no new persisted trusted flag or migration of methodology bytes.
3. Existing files remain on disk. Invalid/incompatible active refs stay recorded but fail closed with repair/reselect guidance; existing reports remain unchanged. Publish documentation contrasting structural validity, eligibility and missing evidence.
4. Rollback is a code-version rollback, not automatic configuration rewriting. Preserve user files and metadata; an older release may not understand newer policies, which is an explicit compatibility failure rather than permission to weaken them.
