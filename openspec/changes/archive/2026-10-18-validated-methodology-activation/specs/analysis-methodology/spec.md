# Spec Delta

## MODIFIED Requirements

### Requirement: Strict structure, tolerant field references
Unknown structural keys, wrong value types, undefined parameters, undefined roles or markers, duplicate identifiers inside the file, invalid regular expressions and size-limit violations SHALL make the whole file invalid with an error that names the location. Unknown field references SHALL remain structurally inspectable and SHALL be reported as unsupported with a suggested correction when available, but SHALL block strict activation validation.

#### Scenario: Typo in a structural key
- **WHEN** a rule contains the key `outcome` instead of `outcomes`
- **THEN** the file is rejected and the error names the rule and the unknown key

#### Scenario: Field from a newer companion
- **WHEN** a rule references a field name this companion does not define
- **THEN** non-activating inspection lists that rule as unsupported with its field name
- **AND** applying the methodology fails without evaluating a supported subset

#### Scenario: Strict validation on request
- **WHEN** validation is requested in strict mode and any rule or other declared item is unsupported by this release
- **THEN** validation reports failure and lists every discovered incompatible item

## ADDED Requirements

### Requirement: Release compatibility is distinct from evidence availability
Activation validation SHALL reject unknown fields, unsupported schema/features and fields the installed collector cannot emit. It SHALL NOT require a snapshot or every live measurement. Missing values for individual entities or temporarily absent snapshot fields for supported capabilities SHALL retain skipped/not-evaluable semantics and SHALL NOT invalidate the methodology.

#### Scenario: Collector capability unavailable
- **WHEN** a methodology requires station positions and the installed release cannot collect them
- **THEN** strict activation fails with an unsupported-capability diagnostic naming the item, field and required snapshot path
- **AND** non-activating validation remains available to debug it

#### Scenario: Older snapshot lacks a supported field
- **WHEN** the installed release supports a referenced field but stored snapshots temporarily lack its source data
- **THEN** activation validation succeeds and runtime output reports the affected rule as skipped
- **AND** no missing value is replaced with zero

#### Scenario: One entity lacks a value
- **WHEN** a compatible rule meets a line whose age is unknown
- **THEN** the methodology remains applicable and that line is reported as not evaluable as required by the evaluator

#### Scenario: Validate without a save
- **WHEN** a compatible methodology is validated or selected before any snapshot exists
- **THEN** validation and selection can succeed without loading the game
- **AND** later analysis without a snapshot retains its normal no-snapshot error and writes no report

### Requirement: Effective parameter validation
Every application SHALL validate the effective methodology after parameter overrides, before evaluation or output publication. Overrides SHALL name declared parameters and satisfy their type, finite-number and declared domain constraints, including constraints imposed by their uses. Invalid overrides SHALL NOT mutate the original file or persistent selection.

#### Scenario: Invalid override
- **WHEN** an override names an unknown parameter, supplies the wrong type, supplies a non-finite number, or violates a declared bound or consumer constraint
- **THEN** application fails with an override-category diagnostic locating the override and affected rule or policy when applicable
- **AND** previous bindings and generated results remain unchanged

#### Scenario: Valid override is reproducible
- **WHEN** a compatible methodology is applied with a valid override
- **THEN** output records the file hash, effective parameter values and request overrides without modifying the methodology file

### Requirement: Actionable machine-readable validation diagnostics
Validation SHALL return structured diagnostics with category, stable code, severity, exact JSON Pointer path, item kind/id and rule id when attributable, a human message and an actionable hint when known. It SHALL aggregate independent errors safely discoverable in one pass; syntax failures SHALL include line/column when available. Unlocatable root failures SHALL use the empty JSON Pointer and null item/rule ids.

#### Scenario: Debug several mistakes
- **WHEN** a parseable draft contains independent wrong keys, broken references and unsupported fields
- **THEN** validation reports all safely discoverable issues with distinct paths, categories and attributable rule ids rather than only the first error
- **AND** no reported success certifies strategic merit or makes methodology text trusted

#### Scenario: Broken JSON
- **WHEN** a methodology contains damaged JSON
- **THEN** diagnostics identify the file, syntax category, root path and available line/column without attempting evaluation
