# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities **privately**. Do not open a public issue or pull request for them.

1. Preferred: use GitHub's **Report a vulnerability** button on the repository's Security tab (private vulnerability reporting).
2. Fallback: e-mail alexandrevl@gmail.com with the subject `TF3 Companion security`.

Include the affected version (`uv run tf3c --version`), your operating system, what you did, what you expected and what happened. A minimal synthetic reproduction is best; never attach real save files, player snapshots or Steam account details.

This is a volunteer project. Expect an acknowledgement within 7 days and an assessment within 14 days. Fixes are released as soon as they are verified; reporters are credited unless they prefer otherwise.

## Supported versions

The project is pre-release. Security fixes go to the latest commit on the default branch and to the most recent tagged release, if any.

## Security boundary

TF3 Companion is designed so that its attack surface stays small:

- **Local only.** The companion makes no outbound network connections and has no hosted service. The MCP server speaks over standard input and output, not a network port.
- **Read-only toward the game.** The bridge mod never runs gameplay commands and writes only snapshot files into its own folder. The companion never alters the simulation.
- **Untrusted inputs are data.** Snapshot files, methodology files, and every text field inside them are parsed as data. Methodology text is never executed or treated as instructions, and methodology references are library ids, never file paths.
- **Player data stays on disk.** Companion data lives under the player's data directory. An AI client connected over MCP can read what the tools return and may send it to its provider; see [privacy](docs/privacy.md).

Examples of in-scope reports: a snapshot or methodology file that makes the parser read or write outside its folders, execute code, hang or exhaust memory (including through regular expressions); an MCP tool that writes outside the data directory or discloses files it should not; a bug that makes the bridge mod change the simulation; a leak of private data into generated files or the repository.

Out of scope: vulnerabilities in the game itself, in Steam, or in an AI provider or client; behaviour that requires an attacker who already controls the player's account or data directory; denial of service by a player against their own machine.
