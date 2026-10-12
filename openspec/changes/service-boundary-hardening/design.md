## Context

The CLI and MCP share a local application service. Files are exchanged with a read-only GUI script, whose writes can fail independently of collection. Input files may be malformed or belong to another identified lineage.

## Decisions

1. Validate finite refresh timeouts and bounded integer query limits before writing. Reject invalid values; do not reinterpret zero as unlimited.
2. Use an exclusive request-adjacent lock across processes. A crashed lock requires deliberate recovery after confirming no writer is active; no timeout-based lock stealing.
3. Write temporary files in the destination directory and replace only after closing the handle. This avoids partial requests and Windows open-handle replacement problems.
4. Preserve the bridge's acknowledgment and successful collection time on failure. Retry no sooner than the existing polling interval; only successful output advances them.
5. Queries requiring current state fail on any ingestion failure. Status still exposes errors. Notes and decisions may precede the first snapshot, but must not stamp stale data after import failures.
6. Keep packaged knowledge and doctor independent of a working game installation. Diagnostics must not create the database or data directory.
7. Escape entity/player text in Markdown and HTML; generated HTML uses no external dependencies. Annual reporting describes observed coverage rather than inventing calendar income from overlapping annual windows. Complete monthly coverage requires a preceding December baseline and samples in all twelve reporting months.
8. Keep true multi-save lineage and live platform validation as release gates, not heuristics or mocked claims.

## Risks and Verification

Exclusive locks can survive crashes; the error explains recovery. Synthetic fixtures prove service behavior, not game APIs. Verification combines behavior regressions, real CLI and MCP stdio round trips, wheel installation, an offline report browser inspection, and a Lua polling harness. Real Windows/game activation and persistent lineage remain pending.
