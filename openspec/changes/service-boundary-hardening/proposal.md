## Why

The review reproduced two consumer-visible failures: `log_tail(0)` returned the entire log, and a negative refresh timeout published a request before returning failure. A bridge write failure also acknowledged a request without producing its response. Concurrent refresh callers could overwrite requests, and queries could silently use older history after import failures.

## What Changes

- Validate bounds before side effects; serialize refresh writers with an exclusive lock and publish requests atomically.
- Acknowledge bridge requests only after a successful snapshot write; throttle failed attempts to the existing polling interval.
- Disclose ingestion failures rather than presenting an older snapshot as current. Retain offline knowledge and non-mutating diagnostics.
- Generate six report kinds with atomic Markdown/offline HTML output. Escape untrusted report text and validate annual year arguments.
- Apply current-year catalog availability using the collector's exclusive retirement boundary and time-bounded historical catalog lookup.

## Capabilities

### New Capabilities
- `service-boundaries`: Validated requests, trustworthy query failure behavior, safe report output, and offline assistance.

## Impact

Changes affect the shared service, CLI/MCP integration, report renderer, and bridge polling state. Bridge revision becomes 2; snapshot schema remains 1. No live mod installation, gameplay actions, network publication, or private-data migration is required.
