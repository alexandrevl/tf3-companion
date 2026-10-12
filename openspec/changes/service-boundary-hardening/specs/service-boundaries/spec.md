## ADDED Requirements

### Requirement: Validated and serialized refresh requests
The service SHALL reject non-finite, non-positive, or excessive timeout values before publishing a request, and SHALL prevent concurrent writers from replacing an active request.

#### Scenario: Invalid timeout
- **WHEN** a caller requests refresh with a negative or non-finite timeout
- **THEN** the call fails without publishing a request

#### Scenario: Refresh already running
- **WHEN** the exclusive request lock already exists
- **THEN** another caller fails with recovery guidance and does not replace the request

### Requirement: Successful bridge output precedes acknowledgment
The bridge SHALL acknowledge a request and advance its successful collection time only after writing the snapshot successfully. Failed attempts SHALL be throttled by the polling interval.

#### Scenario: Snapshot write fails
- **WHEN** the requested snapshot write raises an error
- **THEN** its request remains unacknowledged and a subsequent polling attempt can answer it

### Requirement: Honest current-state query errors
Current-state queries SHALL disclose failed imports rather than silently treating older stored data as current.

#### Scenario: Malformed new snapshot
- **WHEN** an older valid snapshot is stored and a newer file cannot be imported
- **THEN** current-state queries fail, status exposes the import failure, and the invalid file remains available

### Requirement: Safe report generation
Reports SHALL escape untrusted text, generate offline HTML without external dependencies, validate annual year arguments, and avoid adding overlapping annual financial windows into calendar income.

#### Scenario: Malicious entity label
- **WHEN** an entity label contains HTML or Markdown links
- **THEN** it is rendered as text instead of executable markup or an external image

#### Scenario: Incomplete annual baseline
- **WHEN** a reporting year lacks a preceding December baseline
- **THEN** its coverage is labeled partial even if all twelve months contain observations

### Requirement: Offline assistance
Packaged knowledge and diagnostics SHALL remain accessible without an installed game and diagnostics SHALL not create player storage.

#### Scenario: Missing game
- **WHEN** Steam userdata discovery finds no game installation
- **THEN** knowledge remains readable and doctor reports actionable setup information without creating a database
