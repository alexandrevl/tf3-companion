# Spec Delta

## Purpose

Finds Transport Fever 3's user-data folder, mod staging area and game log on Windows, macOS and Linux so the companion works without manual configuration.

## ADDED Requirements

### Requirement: Locate game userdata
The companion SHALL find `<Steam>/userdata/<account>/3493540/local` on Windows (Steam root from the registry, then standard Program Files locations), macOS (`~/Library/Application Support/Steam`) and Linux (`~/.steam/steam`, `~/.local/share/Steam`, Flatpak Steam), selecting only an unambiguous candidate.

#### Scenario: Windows default install
- **WHEN** Steam is installed in `C:\Program Files (x86)\Steam` and one account has TF3 data
- **THEN** that account's `3493540\local` folder is used

#### Scenario: Two Steam accounts
- **WHEN** two account folders contain TF3 data
- **THEN** neither is silently selected, both are listed by `doctor`, and the player is instructed to set `TF3C_USERDATA_DIR`

### Requirement: Explicit override
`TF3C_USERDATA_DIR` SHALL take precedence over discovery on every OS.

#### Scenario: Non-standard location
- **WHEN** `TF3C_USERDATA_DIR` is set to an existing folder
- **THEN** discovery is skipped and that folder is used

### Requirement: Helpful failure
When no TF3 userdata is found the companion SHALL fail with a message listing every location it searched and how to set `TF3C_USERDATA_DIR`.

#### Scenario: Game never started
- **WHEN** Steam exists but TF3 was never launched
- **THEN** the error lists the searched folders and suggests launching the game once

### Requirement: Doctor report
`tf3c doctor` SHALL report OS, searched Steam roots, candidate accounts, selected userdata, installed and bundled mod revisions, snapshot count and newest age, recent bridge log presence, data directory and packaged knowledge, marking checks ok, warning or error with a fix. It SHALL run without game installation or database construction and SHALL NOT create data folders. While automatic save isolation is unavailable, active save SHALL be null and a warning SHALL disclose the shared store.

#### Scenario: Mod outdated
- **WHEN** the installed mod revision is lower than the bundled one
- **THEN** doctor marks it as a warning and suggests `tf3c mod install`

#### Scenario: All good
- **WHEN** every check passes
- **THEN** doctor exits 0; with any error it exits 1
