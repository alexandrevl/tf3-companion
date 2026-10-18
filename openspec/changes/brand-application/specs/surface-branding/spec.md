# Spec Delta

## Purpose

Defines how each TF3 Companion product surface applies the brand tokens, logo and voice defined by the visual identity, so reports, spreadsheets, documentation and agent metadata read as one product.

## ADDED Requirements

### Requirement: One token loader feeds every surface
Every Python surface that applies brand colours or typefaces SHALL obtain them through a single token loader that reads the brand token file. No surface SHALL hold its own copy of a brand colour value.

#### Scenario: Token change reaches every surface
- **WHEN** a colour value in the brand token file is changed
- **THEN** the HTML report, the mermaid configuration and the spreadsheet styling all use the new value without any other source edit

#### Scenario: Token file unreadable
- **WHEN** the token file is missing or lacks a required token
- **THEN** the surface fails with an error that names the file and the missing token, and does not fall back to an unrelated palette

### Requirement: Brand assets ship with the package
The token file and the logo SVGs that runtime surfaces read SHALL be included in the built wheel, and a source checkout SHALL resolve the same files from `assets/brand/`.

#### Scenario: Installed from a wheel
- **WHEN** a report is generated from an installed wheel with no source checkout present
- **THEN** the branded output is identical to one generated from a source checkout

### Requirement: HTML reports default to the dark theme
The HTML report SHALL render with the dark token values when no colour-scheme preference is expressed, and with the light token values when the viewer prefers a light colour scheme.

#### Scenario: No preference
- **WHEN** an HTML report is opened by a viewer without a light colour-scheme preference
- **THEN** the page uses the dark `canvas`, `surface`, `text` and `accent` token values

#### Scenario: Light preference
- **WHEN** the viewer prefers a light colour scheme
- **THEN** the page uses the light token values for the same roles

### Requirement: HTML charts use brand colours
In HTML report charts, bar, line and slice colours SHALL use brand tokens: `positive` for gains, `negative` for losses, and mode tokens for series grouped by transport carrier. Series not grouped by mode SHALL use the mode tokens in table order. Green SHALL NOT mean profit.

#### Scenario: Loss-making line in a bar chart
- **WHEN** a bar chart shows a line with negative annual profit and another with positive profit
- **THEN** the first bar uses the `negative` token and the second the `positive` token

#### Scenario: Profit by carrier
- **WHEN** a chart plots values per transport carrier
- **THEN** each carrier uses its mode token and no bar uses a semantic token

### Requirement: HTML reports use the brand typeface and carry the mark
HTML reports SHALL set text in the brand Lato font stack with tabular numerals for figures, and SHALL show the logo mark in the report header as inline vector markup, with the dark or light variant matching the active theme.

#### Scenario: Offline report
- **WHEN** an HTML report is generated
- **THEN** it contains the logo as inline SVG and references no external script, stylesheet, font, image or link

#### Scenario: Lato not installed
- **WHEN** the viewer's machine has no Lato font
- **THEN** the page renders in the documented fallback stack without a layout failure

### Requirement: Markdown charts carry a brand theme
Each mermaid `pie` and `xychart-beta` block in a Markdown report SHALL begin with an initialisation directive whose colours come from the brand tokens, and SHALL remain valid mermaid that renderers ignoring the directive can still draw.

#### Scenario: Pie chart
- **WHEN** a Markdown report contains a mermaid pie chart
- **THEN** the block starts with a theme directive whose slice colours are mode tokens

#### Scenario: Renderer without theme support
- **WHEN** a renderer ignores the directive
- **THEN** the chart still renders with the renderer's default colours and every slice or series stays labelled in text

### Requirement: Spreadsheets use light cells with a dark branded header
The XLSX export SHALL use the light token values for body cells and chart backgrounds, and the dark `canvas`, `text` and `accent` tokens for table header rows. It SHALL keep Arial as its typeface. This is the sole exception to the dark-by-default rule, because dark cell fills print poorly and are unusual in spreadsheets.

#### Scenario: Table header
- **WHEN** a sheet is exported
- **THEN** its header row fill is the dark `canvas` token, its header text the dark `text` token, and body cells have no brand background fill

#### Scenario: Typeface
- **WHEN** any cell is inspected
- **THEN** its font is Arial

### Requirement: Spreadsheet charts use brand series colours
Every chart in the XLSX export SHALL set series and data-point colours from brand tokens: mode tokens for carrier groupings, `positive` and `negative` for signed values, and mode tokens in table order otherwise. The light-theme values SHALL be used.

#### Scenario: Profit by carrier
- **WHEN** the charts sheet is opened
- **THEN** each carrier bar uses its light-theme mode token

#### Scenario: Negative profit bar
- **WHEN** a chart plots a negative profit value
- **THEN** that data point uses the light-theme `negative` token

### Requirement: README presents the brand
The README SHALL open with the logo as a rendered raster image from `assets/brand/` derived from the vector source, and SHALL link to the brand guide. It SHALL keep the non-affiliation disclaimer.

#### Scenario: Reader opens the repository
- **WHEN** the README is rendered
- **THEN** the logo appears above the first heading text and a link to the brand guide resolves to an existing file

### Requirement: MCP server exposes the logo when supported
The MCP server SHALL declare the logo as a server icon and the project page as its website URL, using the icon and website fields of the installed MCP library.

#### Scenario: Client lists server information
- **WHEN** an MCP client initialises the server
- **THEN** the server information includes an icon whose source is an embedded `data:` URI of the logo and a website URL

### Requirement: Terminal output stays plain
Command-line output SHALL NOT emit ANSI colour or style sequences, and machine-readable (JSON) output SHALL be unchanged by branding.

#### Scenario: Findings printed to a terminal
- **WHEN** `tf3c findings` prints to a terminal
- **THEN** the output contains no escape sequences

### Requirement: Analytic voice on data surfaces
Reports, exports and agent instructions SHALL keep the analytic register: state the figure and entity first, evidence before judgement, no promotional language. Branding changes SHALL NOT add marketing wording to them.

#### Scenario: Report header
- **WHEN** a branded report header is rendered
- **THEN** it shows the logo and the report title and metadata only, with no tagline
