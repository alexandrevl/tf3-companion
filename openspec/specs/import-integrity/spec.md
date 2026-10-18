# import-integrity Specification

## Purpose
Defines safe snapshot ingestion, verified import receipts and pruning, strict parser boundaries, lineage-conflict rejection and endpoint-bounded history access without claiming automatic isolation of unidentified saves.

## Requirements

### Requirement: Verified import receipts
The store SHALL retain source-path and content-digest receipts, and SHALL prune only successfully imported files whose contents and signatures still match their receipts.

#### Scenario: File changes after import
- **WHEN** a raw file is modified after ingestion
- **THEN** pruning preserves it for a verified reimport rather than deleting unverified content

#### Scenario: Invalid file
- **WHEN** a file cannot be parsed or validated
- **THEN** ingestion reports its failure and pruning retains it

### Requirement: Strict data parsing
The parser and snapshot model SHALL reject duplicate Lua keys, invalid key types, unsupported schemas, invalid calendar values, duplicate entity IDs, and integers outside storage bounds.

#### Scenario: Invalid storage integer
- **WHEN** a snapshot contains a negative or out-of-range game time
- **THEN** it fails validation before database mutation

### Requirement: Identified lineage conflicts fail closed
The single-store implementation SHALL reject conflicting save identifiers and SHALL not label unidentified legacy history as automatically isolated.

#### Scenario: Different identified save
- **WHEN** a snapshot with a different save identifier is imported into an existing history
- **THEN** the import fails without overwriting that history

### Requirement: Time-bounded history access
Historical queries SHALL expose chronological observations and permit catalog lookup bounded by the requested game time.

#### Scenario: Future catalog
- **WHEN** a caller requests a catalog at an earlier game time
- **THEN** snapshots from later game times are excluded
