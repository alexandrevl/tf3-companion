# game-knowledge Specification

## Purpose
Define how the packaged game knowledge is organised, sourced and labelled, including the evidence rules for facts adopted from third-party research, so the analyst can separate what was verified from what was taken on trust.

## Requirements

### Requirement: Engine runtime and API topics are packaged
The packaged knowledge SHALL include a topic `engine` describing the engine's runtime model and a topic `api_catalog` describing the Lua calls and ECS components available to a read-only collector. Both SHALL be discoverable through the same listing and read paths as every other topic, with no game or store required.

#### Scenario: Topic listing
- **WHEN** the player or an agent lists the knowledge topics
- **THEN** `engine` and `api_catalog` appear alongside the existing topics

#### Scenario: Offline read
- **WHEN** a topic is read with the game closed and no stored history
- **THEN** its full text is returned

### Requirement: Topic opens with a usable summary
Each new knowledge topic SHALL begin with a single-sentence description of its scope as its first non-heading line, because that line is the topic's summary in the knowledge index.

#### Scenario: Index summary
- **WHEN** the knowledge index is shown
- **THEN** each new topic's summary states what the topic covers and is not a source legend

### Requirement: Claims cite a source or carry an evidence tag
Every game or engine claim added by this change SHALL cite a game file path, a wiki page, or a third-party source, or SHALL be marked `[INFERENCE]` or `[UNVERIFIED]`. Text SHALL be paraphrased; verbatim game or third-party source code SHALL NOT appear.

#### Scenario: Claim without a source
- **WHEN** a statement has neither a citation nor a tag
- **THEN** the statement is not accepted into a topic

#### Scenario: Quoted source code
- **WHEN** a draft section reproduces more than an identifier or API name from a source file
- **THEN** it is rewritten as prose before it is accepted

### Requirement: Adopted third-party facts are labelled
A fact taken from MPFever without verification by this project SHALL carry the tag `[ADOPTED]`, the source prefix `MPF:` naming the MPFever file, and the author's own confidence class: observed, read from game code, assumed, or claimed. The legend SHALL name the studied MPFever commit and licence.

#### Scenario: Author-assumed fact
- **WHEN** MPFever states a fact it only assumed
- **THEN** the topic keeps the fact, tags it `[ADOPTED]`, and states that the author assumed it

#### Scenario: Fact later verified
- **WHEN** this project confirms an adopted fact against game files or in the game
- **THEN** the tag is replaced by the project's own source citation and the adoption note is dropped

### Requirement: Contradictions are surfaced
When imported research contradicts an existing statement, another imported statement, or the game's documented behaviour, the topics SHALL record both versions marked `[DISCREPANCY]` and SHALL NOT choose one silently.

#### Scenario: Conflict inside the research
- **WHEN** the research states one value in its notes and another in its code comments
- **THEN** both values are listed with their sources under `[DISCREPANCY]`

### Requirement: Build-specific knowledge names its build
Knowledge derived from a measured game build SHALL name the build it covers. Executable addresses, struct offsets and hook points SHALL NOT appear in packaged topics.

#### Scenario: Measured on one build
- **WHEN** a section reports a measurement taken on build 40420
- **THEN** the section states that build and does not claim the result for other builds

#### Scenario: Build-internal detail
- **WHEN** research offers an executable address
- **THEN** the packaged topics omit it

### Requirement: Entity-identity caveat
The packaged knowledge and the analyst instructions SHALL state that entity ids are reused after removal, so an id does not by itself prove the same entity across snapshots, and that ids allocated during a play session can differ between machines.

#### Scenario: Line id reused
- **WHEN** the analyst relates two snapshots through a line id
- **THEN** it also compares the entity name or other descriptors before treating them as the same line

### Requirement: Time-base caveat
The `engine` topic SHALL state the simulation step in game-time units and that the game-time component exposes both a rendered-frame counter and a simulation-step counter, and SHALL mark which of them the collector exports as unverified. It SHALL NOT change the GAME-YEAR accounting rules.

#### Scenario: Reading a raw tick
- **WHEN** the analyst cites a raw tick count
- **THEN** it does not convert it to calendar time except through the existing game-calendar rules

### Requirement: Collector gaps are separate from emitted fields
`snapshot_schema` SHALL list data that the research shows is readable but that the collector does not emit in a separate "gaps" section, never in the table of emitted or validated fields.

#### Scenario: Reader checks what a snapshot contains
- **WHEN** a reader looks up the fields a snapshot may contain
- **THEN** gap entries are not presented as fields that exist

### Requirement: Knowledge states facts and never gives action procedures
Packaged knowledge SHALL describe observed engine and game behaviour and SHALL NOT include procedures for altering the simulation, issuing game commands, or hooking the game. Techniques used by the source mod are described only as facts about the engine.

#### Scenario: Source mod hooks the engine
- **WHEN** research describes how the source mod patches the executable
- **THEN** the topics record only the engine behaviour that made the patch necessary

### Requirement: Research is traceable
The change SHALL keep its research dossiers, and every open question in them SHALL appear in the topics as an `[UNVERIFIED]` item or be listed as consciously dropped with a reason.

#### Scenario: Open question
- **WHEN** a dossier lists a thing to verify in the game files
- **THEN** the topics carry it as `[UNVERIFIED]` or the change records why it was dropped
