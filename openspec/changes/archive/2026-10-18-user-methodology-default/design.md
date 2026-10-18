# Design

## Context

See `proposal.md` for motivation. `Library(data)` reads packaged resources and `<data>/methodologies/`. `Resolver(data, save)` currently resolves request > `SaveScope.binding()` > `load_default()`. `SaveScope.fallback()` stores `methodology` in `<data>/methodology.json`; explicit existing save folders use `saves/<id>/save.json`. `use` stores the reference as typed, so bare ids float. `Companion` constructs its resolver from the original `Paths.data` before redirecting its database/report paths into the save folder. MCP inspection currently constructs `Companion`, unnecessarily requiring discovery/database setup. Existing tests already enforce read-only library listing, save metadata preservation, path rejection in MCP and broken-binding errors.

The methodology JSON schema describes policy content, not preference storage. No schema-1 change is needed. `cross-platform-and-saves` owns the eventual registry and verified active-save routing; its lineage probe is not complete and its design explicitly forbids claiming isolation prematurely.

## Goals / Non-Goals

**Goals:** one library-root preference shared by all inheriting save scopes; lazy precedence; inspectable selection provenance; atomic selection changes independent of snapshots and game installation.

**Non-Goals:** a machine-wide settings service, multiple library search roots, content-hash pinning, a second save registry or activation-validator implementation. The packaged default remains neutral and directly selectable.

## Decisions

### D1 — Library-root preference, not active-save configuration

Add a small preference owner alongside `SaveScope`, rooted at the original data/library root. Store `<library-root>/user-methodology.json` as `{"schema":"tf3c-user-methodology/1","methodology":"id@version"}`. Absence of the file or `methodology` means no user default; null, empty/whitespace-only references, non-string references, unknown keys, wrong schema or invalid JSON are errors. A cleared document is `{"schema":"tf3c-user-methodology/1"}`. A dedicated file avoids colliding with `cross-platform-and-saves`' planned `config.json` and prevents accidental promotion of the existing implicit save's `methodology.json`.

The root is `data_directory()` (or injected base `Paths.data` in service tests), never `scope.root`. `--save` changes only the save override being inspected, not preference/library location. `TF3C_DATA_DIR` selects a separate complete library and user default; output and docs call this a **library-root user default**, not an account-wide or machine-global setting. No new environment variable or root search chain.

Read operations never mkdir, migrate, write preference files or open a database. Writes reuse same-directory temporary-file plus `os.replace` patterns. `set-default` validates and gates the candidate before replacing any bytes. `clear-default` explicitly resets this dedicated file, including malformed content, without touching save metadata or reports; diagnostics return the previous reference when readable and a previous-error field otherwise. This is a deliberate reset, not a read-time repair. An already absent preference needs no write.

Alternative rejected: storing the user default in `<data>/methodology.json` would reinterpret old save bindings and silently change scope. An OS settings root outside `TF3C_DATA_DIR` would select references unavailable in the chosen library.

### D2 — Reference semantics and lazy selection

Keep the existing library resolution policy: bare `id` is a floating reference resolved on each use to the numerically highest structurally valid version; `id@version` requires exactly that version. A conflict at the selected version is an error, not a reason to downgrade. Invalid higher-version files remain visible as invalid, consistent with current `Library.resolve`; the shared activation gate must not select an older candidate when the highest structurally valid candidate fails support validation. Version pins do not pin bytes: a forced same-version replacement is revalidated and its new hash is recorded. Import/drop-in alone does not choose a reference or rewrite configuration, but a newly available higher version can affect an already deliberately floating reference. Explain this distinction explicitly.

Resolve lazily: explicit request (CLI one-off path allowed) > selected save override > user default > directly loaded packaged neutral default. An error in a selected layer stops resolution. An explicit request need not read malformed lower layers; a valid save override need not read malformed user-default configuration. Inspection still reports lower-layer errors separately, without falsely saying the effective selected policy failed.

Consume `validated-methodology-activation`'s shared gate after library selection and before configuration mutation or runtime output generation. Never fall back after gate rejection, cache a stale validation result, or erase the old binding/results. Normal per-entity missing data retains that change's unknown/not-evaluable behavior. Clear/reset operations remove policy selection and do not require successful validation of the reference being removed.

### D3 — Explicit interfaces, no compatibility aliases for ambiguous output

Preserve existing `Resolver.use(ref)` / `unuse()` behavior as save override operations; update names in help/output, not their command spelling. Add `set_default(ref)` / `clear_default()` on the resolver/preference service and route both CLI and MCP through the same mutation methods. Global operations must not construct or validate a save scope. CLI:

- `tf3c methodology set-default <id[@version]>` selects the library-root preference; no `--save` flag.
- `tf3c methodology clear-default` removes it; no `--save` flag.
- `tf3c methodology use <id[@version]> [--save ID]` writes only that save override.
- `tf3c methodology unuse [--save ID]` removes only that override, returning to inheritance, not necessarily to packaged default.
- `tf3c methodology list [--save ID] [--json]` inspects both layers and the effective selection without needing a snapshot. An unknown explicit save remains an actionable error, never an automatically created save.

Add MCP `set_methodology_default(methodology: str | None)` (required parameter; null clears) and `set_save_methodology(methodology: str | None, save: str | None = None)` (required methodology; null inherits). Change `list_methodologies(save: str | None = None)` to use resolver-only inspection. All MCP inputs are library ids, never paths; tools document that mutations require the player's deliberate request and do not alter the game. A null/omitted save targets the current implicit scope until the existing save-registry change supplies active scope routing. No new persistent active-save mechanism. Global operations work even if active-save metadata is invalid.

Read preference files on each request so changing the default through another process affects an already-running MCP server's next unbound-save request without restart. Do not cache selection in the cached `Companion`.

### D4 — Selection provenance is distinct from file source

Use origins `request`, `file`, `save-override`, `user-default`, `packaged-default`. File `source` remains `packaged`, `user` or `file`: a packaged example may be selected as a user default, and a user file may be a save override. Replace old ambiguous listing `binding` and `boundToSave` fields in all consumers, rather than maintain aliases.

Listing contains `libraryRoot`, `userDefault` and `saveOverride` each with `reference`, `resolved`, `hash`, `error`, and `metadataFile`; absent reference/resolution is null. Include existing `save`, `effective`, `origin`, top-level selected-resolution `error` and methodology rows, marking rows with `selectedAsUserDefault`, `selectedAsSaveOverride` and `effective`. Only the actually resolved identity is marked for floating references. Store selection provenance as `selection: {origin, reference, libraryRoot, metadataFile}` alongside the existing identity/hash/file-source/parameters in lens outputs, analysis summary, manifests and report headers; request/file/packaged-default have null metadataFile. Findings retain existing methodology identity/hash/source-of-finding fields and add `methodology_selection` to each item; empty findings remain an empty list and inspection provides provenance separately. Do not confuse the finding's `source` (`engine`/`methodology`) with either origin or file source.

A list may show a valid effective save override and an invalid lower-priority user default simultaneously. Its top-level error is null, while `userDefault.error` names the invalid setting and remedy. Analysis errors name the selected layer, reference, library root and exact set/clear/use/unuse remedy. Read errors never trigger fallback or rewrites.

### D5 — Backward migration preserves scope and evidence

No eager file migration is needed: keep reading the existing `methodology` string in `<data>/methodology.json` and `saves/<id>/save.json` as save overrides, with their existing floating/pinned semantics. Never copy them into the new preference. Preserve unrelated save metadata on use/unuse; treat malformed legacy values as broken save overrides, not absence. Missing/null legacy keys mean inheritance for compatibility. Existing valid explicit requests can bypass broken lower-level metadata; inspection exposes it.

When `cross-platform-and-saves` performs its separate explicit legacy-store migration, move the old implicit override with that store into the destination save metadata, preserving the reference and unrelated keys. A conflicting destination override must halt that migration for explicit resolution, never be overwritten or promoted to user default. Do not route untagged historical evidence based on preference configuration. This proposal adds no automatic data migration.

### D6 — Dependency order and read-only collection

Land the common activation gate first, then preference storage/resolution, output contract, CLI/MCP and docs/tests. Synthetic save-folder tests exercise A/B semantics without asserting in-game lineage. Integrate the existing registry API only when `cross-platform-and-saves` lands; its real routing claims retain its own in-game acceptance gate. Geometry and basic-report completion are unrelated prerequisites.

Resolver/preference construction performs no selection or validation. Only analysis/activation resolves policies; ingestion, snapshot refresh, collection diagnostics and game export do not depend on a valid binding. A broken user default cannot prevent collecting evidence. Selection/reset commands work with no userdata discovery and no ingested snapshots.

## Risks / Trade-offs

- [Bare ids can change effective version after an import] → show reference and resolved identity/hash separately; document `id@version` for stable version selection and never silently downgrade a gate-rejected candidate.
- [Configuration writes from different processes race] → atomic replacement prevents partial files; ordinary last completed write wins for this single preference; no locking subsystem is introduced.
- [Origins/listing fields change for machine consumers] → explicit breaking cutover, update every internal caller/test and document the new values; historical report files remain immutable historical evidence.
- [Manual save folders currently advertise an isolated scope internally] → do not broaden that claim into automatic save detection; preserve implicit-store caveats and defer verified lineage to the owning change.
- [A newer default is invalid after direct filesystem edits] → fail selected analysis with validation diagnostics, preserve existing reports, allow explicit selection/reset as recovery.

## Migration Plan

Deploy the additive preference file and new resolver contract together with migrated output consumers. Leave all legacy override files untouched on reads. On first deliberate global selection create only the new preference; existing save overrides remain byte-for-byte unchanged. Rollback can ignore/remove the dedicated user preference to restore previous behavior; it does not require database or methodology-content conversion. Previously generated output origins remain as recorded; do not rewrite old report bundles.
