## Why

TF3 Companion has no visual identity. The mod listing has an empty cover slot (`mod-listing-assets` excludes designing the
artwork), HTML reports use a generic slate palette, the XLSX export uses default chart colours, and nothing ties the
mod, the companion and the agent conversation together as one product. Players find the product through the mod, but
it only pays off once they reach the companion and an AI agent, so the identity has to sell and explain that journey and
feel at home next to Transport Fever 3.

## What Changes

- Define the brand: a "metro map meets circuit board" identity. Transit lines and circuit traces share the same
  0/45/90-degree grammar, so one line reads as both: game data travelling to an AI agent.
- The mark is a route line drawn as a "C" with three stations (your game, the Companion, your AI agent) ending in an
  upward arrow. The Companion station is a square with pins, read both as a metro interchange and as a chip.
- The cover is a vector transit map of the product itself: workflow lines (Diagnose, Grow, Report, Decide) whose
  stations are real MCP tools, converging on a central chip, from a snapshot database terminus to an agent terminus.
- Define one machine-readable token set (colour, typography, semantic and transport-mode roles) with dark as the default
  theme and a derived light theme. The base and accent ramps reuse the game's own UI theme (hue 210 slate and steel
  blue), and profit/loss follow the game's convention (positive blue, negative coral).
- Fix colour-role rules: semantic colours never double as transport-mode colours, text meets WCAG AA, the signal colour
  is reserved for the brand mark.
- Produce the logo as vector files (mark, small-size mark, horizontal lockup, monochrome), the cover as a vector source
  rendered to the existing `assets/art/cover.png` slot, and a square raster logo source for the mod listing.
- Define the voice: marketing register for listing and README, analytic register for reports and agent answers.
- Write a brand guide and a prompt pack so other AI tools can generate on-brand, text-free illustrations without using
  Urban Games or Paradox marks.

Out of scope:

- Applying the identity to code: HTML report CSS, mermaid themes, XLSX chart colours, CLI output, `agent_instructions.md`
  tone and `modinfo.json` copy. A separate follow-up change will specify and implement that application.
- Gallery screenshots, which stay with `mod-listing-assets` and the player, and the in-game rendering check of the cover,
  which only the player can run.
- Any change to the bridge mod, snapshot schema or companion behaviour.
- A website, social media assets, merchandise, or localised brand material (English only).
- Trademark registration or clearance.

## Capabilities

### New Capabilities

- `brand-identity`: the TF3 Companion visual and verbal identity (tokens, colour roles, logo, cover map, typography,
  voice and generative-art constraints) that every product surface consumes.

### Modified Capabilities

None. `installation-onboarding` is unaffected.

## Impact

- New: `assets/brand/` (token file, logo SVGs, cover SVG), `docs/brand/identity.md` (brand guide),
  `docs/brand/prompts.md` (prompt pack), `assets/art/logo-source.png` (rendered from the mark) and `assets/art/cover.png`
  (rendered from the cover SVG), both consumed by `scripts/make_assets.py`.
- Related: `mod-listing-assets` assumed the player would supply the cover. This change supplies it instead; that change's
  slot sizes and checks are unchanged, and its gallery work is unaffected.
- No runtime code, dependency or wheel content changes beyond what `mod-listing-assets` already plans for `_metadata/0.png`.
