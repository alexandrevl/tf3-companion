# Privacy, data handling, and local storage

TF3 Companion is designed around local-first data processing. The companion operates directly on your machine, stores data on your local filesystem, and has no background network synchronization or analytics.

Understanding how data moves between the game, the companion, and your connected AI tools is essential.

## Storage locations

The companion does not store its database or notes inside the code repository. By default, it uses standard OS user data locations:

| Operating System | Default companion data directory (`TF3C_DATA_DIR`) |
| --- | --- |
| macOS | `~/Library/Application Support/tf3-companion` |
| Windows | `%LOCALAPPDATA%\tf3-companion` |
| Linux | `~/.local/share/tf3-companion` |

Within this directory, the companion maintains:

- `companion.db`: SQLite database storing imported snapshot history, calculated findings, opportunities, and the decision journal.
- `notes.md`: Markdown log of player notes, timestamped by the in-game date of the active snapshot.
- `reports/`: Generated Markdown and offline HTML analysis reports.
- `exports/`: Generated `.xlsx` spreadsheet workbooks.

## What data is collected from the game

The game bridge mod reads only in-memory simulation state. It exports:

- In-game simulation date and game speed;
- Company financial metrics (cash balance, outstanding loan, rolling annual profit);
- Lists of lines, stops, frequency, and assigned vehicles;
- Vehicle status (model name, operating costs, capacity, current cargo load, coordinates, depot status);
- Towns (population, demand, cargo fulfillment);
- Industries (production, consumption, output stock levels).

**What is never collected:**

- Your Steam account credentials, friends lists, chat logs, or community profiles;
- Game purchase receipts or licensing keys;
- Files outside the designated Transport Fever 3 `local` directory.

`tf3c doctor` performs read-only checks of standard Steam installation paths to locate your game directory. It prints the detected path for your confirmation and does not upload this information.

## Raw snapshot retention and pruning

The bridge mod writes snapshot files to `<userdata>/towns_industries/tf3c_snap_<timestamp>.lua`.

To prevent unbounded disk usage in your game directory while preserving data safety:

- Snapshots are verified before database ingestion.
- The companion keeps an ingestion receipt tracking both path and file contents. Rewritten snapshots with identical timestamps are detected and handled without silent data corruption.
- Successfully imported files are pruned from the game directory down to the **ten most recent raw snapshots** by in-game time.
- Any unread, invalid, corrupted, or conflicting snapshot files are **never automatically deleted**; they are retained for manual diagnosis.
- Full historical data remains preserved inside `companion.db`.

## Single-store boundary and save identity

The current release uses a **single local database** per data directory:

- The store **does not guess or infer save identity** from town names or map geography.
- If a snapshot carries an explicit `saveId` that mismatches existing records in the database, or attempts to mix identified snapshots into a legacy unpartitioned database, ingestion **fails closed** to prevent cross-contamination.
- Until bridge-owned persistent lineage IDs are verified in live gameplay, **keep separate databases for separate game saves** by setting an explicit data directory:

```sh
# Example: dedicated store for a specific save
export TF3C_DATA_DIR="$HOME/Library/Application Support/tf3-companion-save1"
uv run tf3c refresh
```

## AI providers and data disclosure

TF3 Companion communicates with AI clients (Claude Desktop, Claude Code, Cursor, Codex, omp) through the Model Context Protocol (MCP) using standard input/output (`stdio`) locally on your machine.

**Important boundary:**

- TF3 Companion itself makes no outbound network connections.
- However, when you connect an AI agent to the companion, **the agent reads data via MCP tools and transmits that data to the AI model's provider** (such as Anthropic, OpenAI, or a self-hosted endpoint) according to your arrangement with that provider.
- Transmitted data may include custom vehicle names, company names, city names, and economic statistics from your game.
- Review your AI client's privacy policy and data retention agreements before sharing proprietary or personal company logs.

## Deleting companion data

To completely remove all stored companion information:

1. Stop any running `tf3c mcp` processes or background agents.
2. Remove the companion data directory:
   - macOS: `rm -rf "$HOME/Library/Application Support/tf3-companion"`
   - Windows PowerShell: `Remove-Item -Recurse -Force "$env:LOCALAPPDATA\tf3-companion"`
   - Linux: `rm -rf "$HOME/.local/share/tf3-companion"`
3. To remove lingering raw snapshot files from the game folder, open your game directory's `towns_industries` subfolder and delete any `tf3c_snap_*.lua` and `tf3c_request.lua` files.
4. To remove the bridge mod from the game, see [Install and Remove the Mod](install-mod.md).
