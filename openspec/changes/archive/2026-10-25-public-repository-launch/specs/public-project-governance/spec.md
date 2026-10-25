# Spec Delta

## Purpose

Defines the legal, security, community and identity files a public repository must carry and keep consistent, so strangers can use, trust, report on and contribute to the project.

## ADDED Requirements

### Requirement: Third-party attribution
The repository SHALL include a `NOTICE` file naming every third-party project whose material is adopted, its licence, the studied revision and what was adopted. The README SHALL point to it. The attribution SHALL state that adopted material is paraphrased and that no third-party or game source is vendored.

#### Scenario: Reader checks provenance
- **WHEN** a reader opens `NOTICE`
- **THEN** they find the MPFever project, its MIT licence, commit `ae5fc96` and the knowledge topics derived from it

#### Scenario: New adopted material
- **WHEN** a change adopts material from another project
- **THEN** that project is added to `NOTICE` in the same change

### Requirement: Security policy
The repository SHALL include `SECURITY.md` stating the supported versions, a private reporting channel, expected response times and the project's security boundary: local-only operation, read-only game access, no network access by the companion itself and no execution of methodology text as instructions.

#### Scenario: Reporter finds a vulnerability
- **WHEN** a reader looks for how to report a vulnerability
- **THEN** `SECURITY.md` names a private channel and asks them not to open a public issue

### Requirement: Code of conduct and ownership
The repository SHALL include a `CODE_OF_CONDUCT.md` with an enforcement contact and a `.github/CODEOWNERS` that assigns review of workflows, release files and the bridge mod to the maintainer.

#### Scenario: Workflow change proposed
- **WHEN** a pull request edits a file under `.github/workflows/`
- **THEN** the maintainer is requested as reviewer

### Requirement: Consistent repository identity
The repository name, URLs and project metadata SHALL be identical everywhere they appear: issue-template links, package URLs, README, docs and the bridge-mod metadata `url`. No link SHALL point to a repository that is not the published one.

#### Scenario: Issue template link
- **WHEN** a user opens the issue chooser and follows a link
- **THEN** it resolves to a document in this repository

#### Scenario: Package metadata
- **WHEN** the built wheel metadata is read
- **THEN** its Homepage, Repository and Issues URLs name the published repository

### Requirement: Unofficial status and trademark statement
The README, the package description and the mod listing text SHALL state that the project is unofficial and not affiliated with the game's developer or publisher, and SHALL name products only descriptively.

#### Scenario: Reader of the mod listing
- **WHEN** the mod description is read
- **THEN** it states that the project is unofficial and read-only

### Requirement: Public readiness is explicit and honest
The repository SHALL carry a first-push runbook listing the manual steps in order, each with the evidence that proves it. Gates that cannot be verified from source, such as live game activation or hosted CI, SHALL remain labelled as pending until that evidence exists.

#### Scenario: Maintainer prepares to publish
- **WHEN** the maintainer opens the runbook
- **THEN** they find the ordered steps for creating the repository, the first push, watching CI and enabling repository protections

#### Scenario: Unverified platform
- **WHEN** a platform has no real installation evidence
- **THEN** the compatibility table keeps its status as not verified
