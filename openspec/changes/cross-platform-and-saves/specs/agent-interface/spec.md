# Spec Delta

## ADDED Requirements

### Requirement: Save tools
The MCP server SHALL expose `list_saves` and `use_save(save)` (id or label; empty value unpins), and `status` SHALL include the active save, whether it is pinned, and saves with newer snapshots than the active one.

#### Scenario: Agent switches save
- **WHEN** the agent calls `use_save("Holland main")`
- **THEN** later tool calls answer about that save

### Requirement: Doctor tool
The MCP server SHALL expose `doctor`, returning the same checks as `tf3c doctor` as structured data.

#### Scenario: Mod missing
- **WHEN** the agent calls `doctor` and the mod is not installed
- **THEN** the result marks the mod check as error with the fix `tf3c mod install`
