# Spec Delta

## Purpose

Defines the player-facing identity of the TF3 Companion Bridge mod: the text and images shown in the game's mod list and on mod.io, and the checks that keep them valid before each upload.

## ADDED Requirements

### Requirement: Player-facing mod description
The mod's `modinfo.json` SHALL carry an English `summary` and `description` that state what the Companion does for the player, what the mod writes, that it is read-only and offline, and that the TF3 Companion app is required.

#### Scenario: Description content
- **WHEN** a player reads the mod description in the mod list or on mod.io
- **THEN** it says the mod writes read-only snapshots to the player's userdata folder
- **AND** it says the mod does not change the simulation, the save or money, and sends nothing over the network
- **AND** it says the TF3 Companion app is required to analyse the snapshots

#### Scenario: Summary length
- **WHEN** the metadata is validated
- **THEN** the `summary` is a single line of at most 120 characters

### Requirement: Unofficial-project disclaimer
The mod description SHALL state that the project is unofficial and not affiliated with or endorsed by Urban Games or Paradox Interactive. It SHALL name Transport Fever only descriptively.

#### Scenario: Disclaimer missing
- **WHEN** the listing check runs against a `description` without the disclaimer
- **THEN** it fails and names the missing disclaimer

### Requirement: Mod cover image
The mod folder SHALL ship a cover image at `_metadata/0.png` as a 1920x1080 PNG with an alpha channel, original to this project and containing no Urban Games or Paradox artwork or marks.

#### Scenario: Valid cover
- **WHEN** the listing check runs with a 1920x1080 RGBA PNG at `_metadata/0.png`
- **THEN** the cover check passes

#### Scenario: Wrong size or format
- **WHEN** the file is missing, is not a PNG, or its dimensions differ from 1920x1080
- **THEN** the check fails and reports the expected and actual size or format

#### Scenario: Cover installed with the mod
- **WHEN** the player runs `tf3c mod install`
- **THEN** the installed mod folder contains `_metadata/0.png` identical to the bundled file

### Requirement: Deterministic listing logo
The project SHALL provide a 512x512 PNG logo for the mod.io listing, produced deterministically from the brand logo source image when it exists and otherwise from the cover image, so that regenerating it from unchanged inputs yields byte-identical output.

#### Scenario: Reproducible logo
- **WHEN** the asset script runs twice on the same inputs
- **THEN** both runs produce byte-identical `assets/logo.png` at 512x512

#### Scenario: Brand logo source present
- **WHEN** `assets/art/logo-source.png` exists
- **THEN** the logo is resized from it and the cover is not cropped

### Requirement: Gallery slots
The project SHALL define four named gallery slots under `assets/gallery/` as 1920x1080 PNG images taken in the game, each with a documented subject and caption, and SHALL fail the listing check while any slot is empty or invalid.

#### Scenario: Slot not yet delivered
- **WHEN** the player has not yet supplied `assets/gallery/02-*.png`
- **THEN** the listing check fails and names the missing slot and its required size

#### Scenario: All slots delivered
- **WHEN** four valid 1920x1080 PNG gallery files exist
- **THEN** the gallery check passes

### Requirement: Revision bump with listing changes
A change to the mod's metadata or bundled images SHALL raise `mod.json` `revision`, so that `tf3c doctor` can tell an installed copy from the bundled one.

#### Scenario: Stale installed listing
- **WHEN** the installed mod has a different revision than the bundled mod
- **THEN** `tf3c doctor` reports a warning naming both revisions and advising `tf3c mod install`

### Requirement: Publishing documentation
The repository SHALL document the Mod Hub publishing flow, the `modinfo.json` field meanings, the final listing text, the gallery shot list with captions, and a pre-upload in-game checklist, and SHALL state which listing behaviours were verified in the game and on which build.

#### Scenario: Unverified thumbnail behaviour
- **WHEN** the in-game mod list has not been observed rendering `_metadata/0.png`
- **THEN** the document marks that behaviour as unverified rather than asserting it
