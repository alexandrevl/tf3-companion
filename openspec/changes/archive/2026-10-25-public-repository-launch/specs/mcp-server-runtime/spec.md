# Spec Delta

## Purpose

Defines how MCP tools reach stored evidence so that repeated, concurrent and long-lived agent sessions behave correctly and never corrupt or lock the player's store.

## ADDED Requirements

### Requirement: Tool calls are safe across threads
Every MCP tool SHALL return its normal result when called repeatedly, and from different worker threads, in one server process. No tool SHALL fail with a database thread-affinity error.

#### Scenario: Repeated calls
- **WHEN** an agent calls `company_overview` and `list_lines` twenty times in one session
- **THEN** every call returns data and none returns a thread-affinity error

#### Scenario: Concurrent calls
- **WHEN** several different tools are called at the same time from separate threads against one store
- **THEN** all return consistent results from the same latest snapshot

### Requirement: No connection outlives a call
A tool SHALL release every store connection before it returns, whether it succeeds or fails, so that no connection survives between calls or can be used from another thread.

#### Scenario: Failure inside a tool
- **WHEN** a tool raises an expected error
- **THEN** its store connection is closed and the next call opens a fresh one

### Requirement: Stored-only tools never write
Tools documented as stored-only, namely `evaluate`, `list_methodologies`, `methodology_detail`, `validate_methodology`, `knowledge` and `doctor`, SHALL NOT modify the store, create files or ingest pending snapshots.

#### Scenario: Evaluate with newer exports pending
- **WHEN** newer exported snapshots exist and `evaluate` is called
- **THEN** the stored result is unchanged and nothing is ingested

#### Scenario: Evaluate on a read-only store file
- **WHEN** the store file is read-only and `evaluate` is called
- **THEN** it returns results

### Requirement: Ingesting and writing tools are serialised
Tools that ingest pending snapshots or write player records, including the overview, line, fleet, industry, town, findings, opportunity, history, stock, depot, catalogue, decision, notes, export, report, analyse and refresh tools, SHALL NOT overlap with one another within one server process. A failed write SHALL leave the previous stored state intact.

#### Scenario: Two decisions recorded at once
- **WHEN** two `record_decision` calls overlap
- **THEN** both decisions are stored exactly once

#### Scenario: Two overlapping ingesting reads
- **WHEN** two ingesting tools are called at once with a pending snapshot
- **THEN** the snapshot is ingested once and both calls return results

### Requirement: Expected failures are actionable
A missing store, a missing snapshot or an invalid argument SHALL be reported as an actionable tool error naming what to do next, not as an internal exception.

#### Scenario: Empty store
- **WHEN** an ingesting tool is called before any snapshot exists
- **THEN** the tool error says to run `tf3c refresh` or `tf3c ingest`

### Requirement: Runtime version is observable
`status` SHALL report the running package version so a long-lived server started before an upgrade can be recognised. Documentation SHALL state that clients must restart the server after upgrading.

#### Scenario: Stale server
- **WHEN** a user upgrades the package and calls `status` on a server started earlier
- **THEN** the reported version differs from the installed one and the documentation explains restarting
