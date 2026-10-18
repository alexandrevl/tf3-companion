# Proposal

## Why

A shared methodology may be broken or incompatible with this release, and authors need actionable debugging without activating it. Structural validation already exists, but normal import/resolution/runtime paths do not enforce the stricter support checks, so an accepted selection can silently omit intended policy.

## What Changes

- **BREAKING**: Require structural and release-capability validation before managed import, save binding, user-default selection, and every application, including drop-ins, CLI one-off paths and effective parameter overrides. Unsupported features or fields are inspectable but not applicable; `--force` cannot bypass validation.
- Keep drafts on disk legal and invalid/incompatible library candidates isolated and visibly diagnosed. Add machine-readable, multi-error diagnostics and read-only CLI/MCP debugging without activation.
- Separate malformed content, unsupported schema/features/collector capabilities, invalid effective overrides, conflicts, and ordinary runtime evidence gaps. No live snapshot is required to validate, import or select a compatible methodology.
- Revalidate changed bytes and bind evaluation to the exact validated content/hash and effective parameters, never a mutable file's trusted flag.
- Preserve previous configuration, bindings, report bundles, manifests and latest-report pointers when validation fails; stage successful replacement instead of destructively clearing prior state.
- Retain identity/hash/conflict protection, local-only declarative processing, untrusted-text handling and read-only gameplay boundaries.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `analysis-methodology`: Distinguish structural validity from activation compatibility; require effective-policy validation and structured debugging diagnostics while retaining runtime missing-data semantics.
- `methodology-library`: Gate import/selection/application, isolate damaged drop-ins, expose read-only MCP validation, and preserve prior configuration/results on failure.

## Impact

Affected implementation: `methodology/{loader,validate,model,support,library,resolve,lens,engine,output,cli}.py`, `service.py`, `mcp_server.py`, existing methodology regression suites, `docs/methodologies.md`, and analyst guidance. No new dependency, network access, plugins, executable methodology code, gameplay writes or mod changes are needed.

Coordination: `user-methodology-default` owns global/default selection APIs and precedence; its setters and runtime resolution must call this shared gate. `methodology-report-policies` owns the policy registry/ranges; this gate validates the effective policy before any report write. `consistent-game-year-accounting` owns accounting semantics, not activation.

Out of scope: changing playstyle strategy, proving strategic merit, certifying authors or eliminating prompt-injection risk, requiring complete live measurements, fixing missing collector fields, introducing a methodology editor, automatic repairs, save isolation, or changing report-policy/accounting formulas.
