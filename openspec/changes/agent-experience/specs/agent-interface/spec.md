## ADDED Requirements

### Requirement: Server instructions carry the analyst role
The MCP server SHALL return, in its `initialize` response, instructions in English that define the analyst role for any MCP client without relying on a repository file. The instructions MUST state that the assistant: consults data before giving opinions; cites numbers and the snapshot date; uses full entity names; explains game mechanisms from the knowledge base or labels them a hypothesis; offers options with trade-offs; records decisions and reviews planned ones; answers in the user's language; and knows the mod is read-only.

#### Scenario: Client reads instructions on connect
- **WHEN** an MCP client connects and reads the server instructions
- **THEN** the text contains each of the seven behaviours above and names the starting tools `status` and `findings`

#### Scenario: Works outside the repository
- **WHEN** the server is launched from any working directory with no `AGENTS.md` present
- **THEN** the instructions returned are identical to those returned inside the repository

### Requirement: Instructions describe data caveats
The instructions SHALL list the data caveats an analyst must respect: yearly figures cover the last game year and are partial for lines younger than one year; `load` is an instant occupancy, not an average; collection errors reported by `status` must be disclosed before drawing conclusions that depend on them.

#### Scenario: Caveats present
- **WHEN** the instructions are read
- **THEN** they mention partial figures for young lines, instantaneous load, and the need to disclose collection errors

### Requirement: Read-only guidance to the player
The instructions SHALL tell the agent that neither it nor the mod can act in the game and that it must describe, in the player's terms, what to do and where to click.

#### Scenario: Recommendation requires an in-game action
- **WHEN** the agent proposes a change such as replacing a vehicle model
- **THEN** it is instructed to explain the manual steps instead of claiming it applied the change

### Requirement: Prompt catalogue
The server SHALL expose the following MCP prompts, each returning user-role guidance that names the tools to call and the order to call them in: `monthly-review`, `annual-review`, `line-triage`, `fleet-renewal`, `cargo-opportunities`, `decision-review`. Every prompt MUST have a one-sentence description and every argument MUST have a description.

#### Scenario: Listing prompts
- **WHEN** a client lists prompts
- **THEN** the six analysis names above are returned, each with a description, together with the `setup-check` onboarding prompt defined by the `installation-onboarding` capability and no other prompts

#### Scenario: Prompt references only existing tools
- **WHEN** any prompt is rendered
- **THEN** every tool name mentioned in its text is a registered tool of the server

### Requirement: Monthly review prompt
The `monthly-review` prompt SHALL take no required arguments and SHALL guide the agent to check snapshot freshness with `status` (refreshing if the game is open and the data is stale), read `company_overview` for the change since the previous snapshot, read `findings`, review planned decisions, and finish with at most three recommended actions backed by numbers.

#### Scenario: Default monthly review
- **WHEN** a client gets `monthly-review` without arguments
- **THEN** the returned text orders status, overview, findings and planned decisions, and asks for a prioritised short list of actions

### Requirement: Annual review prompt
The `annual-review` prompt SHALL accept an optional `year` argument (game year) and guide the agent to build the annual picture from the generated annual report and `company_history`, compare the year with the previous one, and name the best and worst performers.

#### Scenario: Year given
- **WHEN** a client gets `annual-review` with `year` set to `1984`
- **THEN** the text asks for the 1984 annual report and a comparison with 1983

#### Scenario: Year omitted
- **WHEN** a client gets `annual-review` without `year`
- **THEN** the text tells the agent to use the latest completed game year found in the history

### Requirement: Line triage prompt
The `line-triage` prompt SHALL accept an optional `line` argument (id or name). With a line, it guides the agent through `line_detail` and its vehicles; without, through `list_lines` ordered by profit and the loss-making findings. In both cases it asks the agent to separate causes visible in the data from hypotheses and to check the load trend rather than a single instant.

#### Scenario: Line given
- **WHEN** a client gets `line-triage` with `line` set to a line name
- **THEN** the text directs the agent to `line_detail` for that line before any recommendation

#### Scenario: No line given
- **WHEN** a client gets `line-triage` without `line`
- **THEN** the text directs the agent to rank lines by profit and triage the worst ones

### Requirement: Fleet renewal prompt
The `fleet-renewal` prompt SHALL accept an optional `line` argument and guide the agent to compare vehicles in service against `vehicle_catalog` for the current game year, flag vehicles near end of life, idle in depots or out of production, and present replacement options with capacity, speed and running cost trade-offs.

#### Scenario: Fleet-wide renewal
- **WHEN** a client gets `fleet-renewal` without arguments
- **THEN** the text asks for age, depot idleness and catalogue alternatives across the whole fleet

### Requirement: Cargo opportunities prompt
The `cargo-opportunities` prompt SHALL accept an optional `cargo` argument and guide the agent to use `opportunities`, `list_industries` (unserved) and `list_stocks` (full stocks), listing nearest consumers with distances and stating that building a line is a manual in-game action.

#### Scenario: Cargo filter
- **WHEN** a client gets `cargo-opportunities` with `cargo` set to `LOGS`
- **THEN** the text restricts the analysis to that cargo

### Requirement: Decision review prompt
The `decision-review` prompt SHALL accept an optional `status` argument (`planned`, `done`, `dropped`; default `planned`) and guide the agent to list decisions, compare the entities' metrics before and after, warn when the 12-month profit window has not yet moved enough to judge, and close decisions with `update_decision` and the observed outcome.

#### Scenario: Default status
- **WHEN** a client gets `decision-review` without arguments
- **THEN** the text targets decisions with status `planned`

#### Scenario: Invalid status
- **WHEN** a client gets `decision-review` with `status` set to `foo`
- **THEN** the request fails with an error that lists the three valid values

### Requirement: Knowledge resources
The server SHALL expose the knowledge base as MCP resources: an index resource listing the available topics and one resource per shipped topic, all as Markdown. The resource set MUST match the topics served by the `knowledge` tool.

#### Scenario: Listing topics
- **WHEN** a client reads the knowledge index resource
- **THEN** it receives each topic name with a one-line summary

#### Scenario: Reading a topic
- **WHEN** a client reads the resource of topic `mechanics`
- **THEN** it receives the same Markdown that the `knowledge` tool returns for `mechanics`

#### Scenario: Unknown topic
- **WHEN** a client reads a knowledge resource for a topic that does not exist
- **THEN** the error names the available topics

### Requirement: Save notes resource
The server SHALL expose the active save's notes as a Markdown resource, readable without calling a tool, with the same content as the notes read through `save_notes`.

#### Scenario: Notes exist
- **WHEN** a client reads the notes resource and the active save has notes
- **THEN** the full notes text is returned

#### Scenario: No notes yet
- **WHEN** a client reads the notes resource and the save has no notes
- **THEN** the resource returns a short text saying there are no notes and that `save_notes` can create them

#### Scenario: No save yet
- **WHEN** no snapshot has ever been ingested
- **THEN** the read fails with an error telling the player to open the game with the mod enabled and run `refresh`, or `tf3c doctor`

### Requirement: Latest report resource
The server SHALL expose the most recently generated report of the active save as a Markdown resource.

#### Scenario: Report exists
- **WHEN** a client reads the latest-report resource and the save has generated reports
- **THEN** the newest report is returned with its generation date

#### Scenario: No report generated
- **WHEN** no report exists for the save
- **THEN** the error states that none exists and names the way to create one (the `report` tool or `tf3c report`)

### Requirement: Resources are discoverable and typed
Every resource SHALL have a stable URI with the `tf3c://` scheme, a name, a description and the MIME type `text/markdown`. Parameterised topics MUST be advertised as a resource template.

#### Scenario: Listing resources
- **WHEN** a client lists resources and resource templates
- **THEN** each entry carries a description and `text/markdown`, and the topic URI template is present

### Requirement: Tool descriptions in English and consistent
All tool descriptions and parameter descriptions SHALL be English. Each description MUST start with what the tool returns, then say when to use it, then state prerequisites (for example "needs the game open"). Parameters MUST describe units and allowed values. No tool name changes.

#### Scenario: Language and shape check
- **WHEN** the registered tools are listed
- **THEN** every tool has a non-empty English description, every parameter has a description, and no description contains Portuguese text

#### Scenario: Existing configurations keep working
- **WHEN** a client written against the previous tool names calls them
- **THEN** the calls succeed with unchanged argument names

### Requirement: Actionable errors
Expected failures SHALL reach the agent as readable tool errors, never as stack traces, and each MUST state what went wrong and what to do next. Errors MUST name valid alternatives when the input was a choice from a finite set.

#### Scenario: No snapshot
- **WHEN** a data tool is called before any snapshot exists
- **THEN** the error says no snapshot was found and tells the agent to ask the player to open the game with the mod enabled and call `refresh`, or to run `tf3c doctor`

#### Scenario: Refresh with the game closed
- **WHEN** `refresh` times out
- **THEN** the error says the game did not answer, lists the likely causes (game closed, mod not enabled for this save, save not loaded) and suggests continuing with the existing snapshot dated as returned by `status`

#### Scenario: Unknown line
- **WHEN** `line_detail` receives a name matching no line
- **THEN** the error says so and suggests `list_lines` to find the exact name, listing near matches when there are any

#### Scenario: Invalid enum value
- **WHEN** a tool receives a status or modality that is not valid
- **THEN** the error lists the valid values

### Requirement: Contributor guide separate from the persona
The repository `AGENTS.md` SHALL be a contributor-facing developer guide in English (layout, commands, conventions, how to extend, in-game validation rules) and MUST NOT contain the player-analyst persona; that persona lives only in the server instructions.

#### Scenario: Persona not duplicated
- **WHEN** the repository files are searched for the instruction text delivered by the server
- **THEN** it exists in exactly one source file and `AGENTS.md` does not repeat it

#### Scenario: Contributor guide content
- **WHEN** a contributor opens `AGENTS.md`
- **THEN** it explains how to run tests, where the mod and the package live, and how to add an analysis, tool, prompt or resource
