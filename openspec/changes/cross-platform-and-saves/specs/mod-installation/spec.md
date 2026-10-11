# Spec Delta

## Purpose

Installs and removes the TF3 Companion Bridge mod from the command line on any supported OS, using the mod files bundled with the companion.

## ADDED Requirements

### Requirement: Bundled mod
The installed companion package SHALL contain the bridge mod files, so installing the mod never needs a source checkout.

#### Scenario: Installed from a wheel
- **WHEN** the companion is installed with `uvx` or `pipx`
- **THEN** `tf3c mod install` finds the mod files inside the package

### Requirement: Install
`tf3c mod install` SHALL copy the bundled mod into `<userdata>/staging_area/tf3_companion_bridge`, replacing any previous copy completely, and print the next in-game steps (enable the mod in the save's mod list, then save).

#### Scenario: Upgrade
- **WHEN** an older revision is installed and the player runs `tf3c mod install`
- **THEN** the folder holds exactly the bundled files and doctor reports the new revision

### Requirement: Uninstall
`tf3c mod uninstall` SHALL remove `staging_area/tf3_companion_bridge` and leave snapshots, history and notes untouched.

#### Scenario: Remove
- **WHEN** the player runs `tf3c mod uninstall`
- **THEN** the mod folder is gone and `tf3c saves` still lists the saves

### Requirement: Game running warning
Install and uninstall SHALL warn that changes take effect after the save is reloaded.

#### Scenario: Reload hint
- **WHEN** the mod is installed
- **THEN** the output says to return to the main menu and load the save again
