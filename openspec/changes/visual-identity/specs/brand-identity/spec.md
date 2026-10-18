# Spec Delta

## Purpose

Gives TF3 Companion one recognisable visual and verbal identity, aligned with Transport Fever 3's own interface, that the
mod listing, reports, exports, documentation and agent answers all draw from.

## ADDED Requirements

### Requirement: Single brand token source
The project SHALL keep every brand colour and typeface in one machine-readable token file. Each colour token SHALL have a
dark-theme and a light-theme value. Any product surface that applies the brand SHALL take its colours and typefaces from
that file, not from values copied into the surface.

#### Scenario: Token covers both themes
- **WHEN** the token file is read
- **THEN** every colour token has a dark value and a light value, each a 6-digit hex colour

#### Scenario: Surface uses a colour outside the token set
- **WHEN** a branded surface shows a colour that is not a token value
- **THEN** that is a defect against this requirement

### Requirement: Dark theme is the default
Dark SHALL be the default theme on every surface that offers a choice. The light theme SHALL use the same roles with
values derived from the same hue, and a surface that supports only one theme SHALL use the dark one.

#### Scenario: Surface without a theme preference
- **WHEN** a branded surface renders and no light preference is expressed
- **THEN** it uses the dark token values

### Requirement: Base and accent follow the game's interface
The dark theme's background, surface, border and accent tokens SHALL be the values Transport Fever 3's interface derives
from its hue-210 theme, and the brand typeface SHALL be the typeface the game's interface uses, Lato, with a documented
system fallback.

#### Scenario: Base colour matches the game
- **WHEN** the dark `surface-raised` token is compared with the game's `BaseDarkMedium` interface colour
- **THEN** both are `#22282E`

#### Scenario: Typeface unavailable
- **WHEN** a surface cannot load Lato
- **THEN** it falls back to the documented system sans-serif stack, not to an unrelated display face

### Requirement: Text contrast meets WCAG AA
Every token documented for text SHALL have a contrast ratio of at least 4.5:1 against the canvas and surface tokens of
its theme. Tokens used only for graphics, such as chart series, icons and badges, SHALL reach at least 3:1. A token below
4.5:1 SHALL be documented as not for text.

#### Scenario: Error colour on dark
- **WHEN** the dark `error` token (`#D02029`, 3.2:1 on canvas) is needed in running text
- **THEN** the `negative` token is used for the text and `error` only for the icon or badge

#### Scenario: Contrast check
- **WHEN** contrast is computed for every token against canvas and surface in both themes
- **THEN** no text token is below 4.5:1 and no graphic token is below 3:1

### Requirement: Profit and loss follow the game's convention
Positive money values SHALL use the `positive` token (blue) and negative values the `negative` token (coral), matching
the game's interface. Green SHALL mean an `ok` status only, never profit.

#### Scenario: Loss-making line in a chart
- **WHEN** a chart or table shows a line with negative annual profit
- **THEN** that value uses `negative`, and a profitable line uses `positive`

### Requirement: Semantic and transport-mode colours stay separate
Each transport carrier (rail, road, tram, water, air, other) SHALL have its own mode token, used for series and
legends grouped by mode. No mode token SHALL reuse the hue family of a semantic token (`positive`, `negative`, `ok`,
`warning`, `error`), and semantic tokens SHALL NOT be used as mode or series colours.

#### Scenario: Profit by transport mode chart
- **WHEN** a chart plots annual profit per carrier
- **THEN** bars use mode tokens, and none of them is blue, coral or green

#### Scenario: Vehicles without a carrier
- **WHEN** a group has no carrier or an unknown one
- **THEN** it uses the `mode-other` neutral token

### Requirement: Signal colour is reserved for the brand
The `signal` token SHALL appear only in the brand mark and on marketing surfaces (cover, listing art, README banner). It
SHALL NOT mark warnings, highlights or data.

#### Scenario: Warning badge
- **WHEN** a report shows a warning finding
- **THEN** it uses `warning`, not `signal`

### Requirement: Route mark logo
The logo SHALL be a route line drawn as a "C" with three stations, meaning game, Companion and AI agent, ending in an
upward arrow in the signal colour. The game and agent stations SHALL be circles and the Companion station a square with
pins (chip). It SHALL ship as vector files: mark, small-size mark, horizontal lockup and monochrome. The mark SHALL remain
recognisable at 32 px and render cleanly at 512 px.

#### Scenario: Small size
- **WHEN** the mark is rendered at 32x32 px
- **THEN** the C shape, the square Companion station, the two round stations and the arrow are still distinguishable,
  even if the pins are dropped

#### Scenario: Station meaning
- **WHEN** the brand guide explains the mark
- **THEN** it names the top station as the game, the square station as the Companion and the bottom station as the AI
  agent

#### Scenario: Single-colour use
- **WHEN** a surface cannot use colour
- **THEN** the monochrome variant is used, not a recoloured full-colour file

### Requirement: Distinct from official marks
Brand assets SHALL NOT include or imitate the Transport Fever logo, wordmark, box art, icons or other Urban Games or
Paradox Interactive artwork or marks. Marketing surfaces that use the brand SHALL carry the existing "not affiliated with
or endorsed by Urban Games or Paradox Interactive" disclaimer.

#### Scenario: Generated cover art review
- **WHEN** a generated or commissioned image is proposed as cover art
- **THEN** it is rejected if it contains the game's logo, wordmark, UI screenshots of official art, or recognisable
  official marks

### Requirement: Voice registers per surface
The identity SHALL define two voice registers. The marketing register (mod listing, README, cover) MAY use short, punchy,
tycoon-vocabulary lines. The analytic register (reports, exports, agent answers) SHALL state numbers and evidence before
judgement and SHALL NOT use promotional language.

#### Scenario: Report sentence
- **WHEN** a report describes a loss-making line
- **THEN** it states the line name and figure first, without hype adjectives

#### Scenario: Listing tagline
- **WHEN** the mod listing summary is written
- **THEN** it may use the marketing register but still makes no claim the product cannot back

### Requirement: Cover is a transit map of the product
The listing cover SHALL be a vector transit map on the dark canvas: workflow lines (Diagnose, Grow, Report, Decide)
routed at 0, 45 and 90 degrees, converging on a central chip that stands for the Companion's MCP server, with a snapshot
database terminus and an AI agent terminus. The chip SHALL sit inside the central 1080x1080 square of the 1920x1080 cover.

#### Scenario: Cover rendered for the listing slot
- **WHEN** the cover source is rendered
- **THEN** the result is a 1920x1080 PNG on the `canvas` colour, the chip is inside the central 1080x1080 square, and the
  database and agent termini are at opposite ends of the map

### Requirement: Cover stations name real tools
Every station on the cover SHALL carry a human-readable label and, beneath it, the exact name of an MCP tool that the
Companion exposes. A station SHALL NOT name a tool that does not exist.

#### Scenario: Tool renamed or removed
- **WHEN** an MCP tool shown on the cover is renamed or removed
- **THEN** the cover is out of date and the station is updated or removed before the next listing upload

#### Scenario: Reader without MCP knowledge
- **WHEN** a player who has never used MCP looks at the cover
- **THEN** the human-readable labels (for example "Findings", "Reports") explain what the agent can do without the
  tool names

### Requirement: Generative art constraints
The brand SHALL provide prompts for external image generators that state the palette, composition and exclusions. The
exclusions SHALL forbid rendered text and official marks. Generated images SHALL serve only as text-free illustration;
product names and station labels SHALL come from vector sources, never from a generator.

#### Scenario: Illustration produced with an external generator
- **WHEN** a contributor generates an illustration from the prompt pack
- **THEN** the image contains no text, letters, logos or game UI, and any name shown with it is overlaid from the vector
  lockup
