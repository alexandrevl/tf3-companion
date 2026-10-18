# Prompt pack for generated illustrations

Prompts for external image generators. They produce **text-free illustrations only**: README section art, a social preview background and an optional wide banner background. Names, labels, the wordmark and the disclaimer are never generated. They are overlaid afterwards from the vector files in `assets/brand/` (see [identity.md](identity.md)).

Generators cannot render reliable text or exact colours, so treat output as a background: recolour or tone-correct it to the token values if needed, and never rely on it for a brand colour.

## Shared parts

**Palette (dark theme, from `assets/brand/tokens.json`):**

| Use | Hex |
| --- | --- |
| Background canvas | `#171B1F` |
| Panels, shapes | `#22282E` |
| Thin outlines | `#343C45` |
| Main route line | `#6DB0F2` |
| Chip and station fill | `#E6E6E6` |
| Second line | `#FF8C00` |
| Third line | `#C38FFF` |
| Fourth line | `#D86FC6` |
| Small accent (one arrow or dot at most) | `#FFC40C` |

**Style:** flat vector illustration, metro map meets circuit board. Lines routed only at 0, 45 and 90 degrees with rounded bends, like a transit map and a printed circuit trace at once. Round stations, a square microchip with pins as the central hub, one database cylinder, one speech bubble. No shading, no gradients, no texture, no 3D. Even line weight.

**Exclusion list (copy verbatim into every prompt):**

> No text, letters or numbers; no logos; no game UI; no recognisable official vehicles or box art; no AI cliches such as brains, robots, sparkles or thought bubbles.

## 1. README section art

Aspect ratio 16:9 (for example 1600x900), a calm illustration to sit between README sections.

```text
Flat vector illustration, metro map meets circuit board, on a solid #171B1F background. A transit-style network drawn with rounded lines routed only at 0, 45 and 90 degrees. A main route in #6DB0F2 starts at a round station on the left beside a database cylinder, passes through a square microchip with short pins at the centre, and ends beside a speech bubble on the right. Branches in #FF8C00 and #C38FFF pass through the chip's pins. Station fills #E6E6E6, rings #6DB0F2, panels #22282E, outlines #343C45. Do not use the reserved signal yellow; it belongs only in the vector brand mark overlaid afterwards. Wide empty margins, empty space along the bottom for an overlay. Even line weight, no shading, gradients, texture or 3D, 16:9.
No text, letters or numbers; no logos; no game UI; no recognisable official vehicles or box art; no AI cliches such as brains, robots, sparkles or thought bubbles.
```

## 2. Social preview background

Aspect ratio 2:1 (1280x640). Keep the middle clear: the vector lockup is placed over it.

```text
Flat vector illustration, metro map meets circuit board, solid #171B1F background, 2:1 wide format. Rounded lines in #6DB0F2, #FF8C00 and #C38FFF routed at 0, 45 and 90 degrees run along the edges, leaving the central 50 percent empty. A database cylinder at the left terminus, a speech bubble at the right, small square microchips with pins along the lines. Station fills #E6E6E6, rings #6DB0F2, shapes #22282E, outlines #343C45. No signal yellow: reserve it for the vector brand mark overlaid afterwards. Even line weight, no shading, gradients, texture or 3D.
No text, letters or numbers; no logos; no game UI; no recognisable official vehicles or box art; no AI cliches such as brains, robots, sparkles or thought bubbles.
```

## 3. Wide banner background (optional)

Aspect ratio 4:1 (for example 2400x600). Left third stays quiet for the lockup.

```text
Flat vector illustration, metro map meets circuit board, solid #171B1F background, 4:1 banner. Rounded lines routed at 0, 45 and 90 degrees flow left to right: main route #6DB0F2, branches #FF8C00, #C38FFF and #D86FC6. They gather at a square microchip with pins two thirds along the width, then fan out to round stations. Leave the left third empty for the vector lockup, with faint #343C45 grid lines only. A database cylinder near the left terminus, a speech bubble at the right. Station fills #E6E6E6, rings #6DB0F2, shapes #22282E, outlines #343C45. No signal yellow: reserve it for the vector brand mark overlaid afterwards. Even line weight, no shading, gradients, texture or 3D.
No text, letters or numbers; no logos; no game UI; no recognisable official vehicles or box art; no AI cliches such as brains, robots, sparkles or thought bubbles.
```

## Review before use

Check every generated image against the identity's "Distinct from official marks" requirement before it enters the repository or a listing. Reject the image if any answer is no.

- [ ] Contains no text, letters or numbers, including pseudo-text, signs, fake logos and watermarks.
- [ ] Contains no Transport Fever logo, wordmark, box art, icons, UI screenshots or other Urban Games or Paradox Interactive artwork.
- [ ] Shows no recognisable official vehicle, building or scene copied from the game.
- [ ] Contains no brains, robots, sparkles, thought bubbles or similar AI cliches.
- [ ] Colours are close to the dark-theme tokens; recolour to token values if not. No other bright hues.
- [ ] Uses 0, 45 and 90 degree routing, round stations, and at most one chip, one database and one speech bubble motif.
- [ ] Has clear space where the vector lockup, tagline and disclaimer will be overlaid.
- [ ] Any name, label or disclaimer shown with it comes from the vector files (`assets/brand/logo-lockup.svg`, `assets/brand/cover.svg`), not from the generator.
- [ ] The marketing surface that uses it carries "Not affiliated with or endorsed by Urban Games or Paradox Interactive."
- [ ] The tool or service's terms allow the image to be used in an MIT-licensed open project.
