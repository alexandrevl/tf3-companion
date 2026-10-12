# Connect an MCP agent

TF3 Companion runs an MCP **stdio** server. It is not a web service, and no API key is required by the companion. Your AI client may require its own account and may send tool outputs to a provider; see [privacy](privacy.md).

Install the source environment first with `uv sync --locked`. The package is not yet on PyPI: do not use `uvx tf3-companion` as an installation shortcut.

## Launch command

macOS/Linux:

```sh
uv run --project /absolute/path/to/tf3-companion tf3c mcp
```

Windows PowerShell:

```powershell
uv run --project C:\Projects\tf3-companion tf3c mcp
```

Use absolute paths for both the checkout and, if the client cannot resolve it, the `uv` executable. GUI clients need not inherit your terminal's PATH or environment. `--project` selects the environment even when the client starts in another working directory. The repository `.mcp.json` uses a relative path for repository-aware clients; do not copy that relative path into a global GUI configuration.

## JSON clients

For clients that accept an `mcpServers` map (such as Claude Desktop and compatible project configurations), merge this entry into the client's existing configuration rather than overwriting other servers.

macOS:

```json
{
  "mcpServers": {
    "tf3-companion": {
      "command": "/absolute/path/to/uv",
      "args": ["run", "--project", "/absolute/path/to/tf3-companion", "tf3c", "mcp"],
      "env": {
        "TF3C_USERDATA_DIR": "/absolute/path/to/Steam/userdata/ACCOUNT_ID/3493540/local",
        "TF3C_DATA_DIR": "/absolute/path/to/companion-data"
      }
    }
  }
}
```

Windows:

```json
{
  "mcpServers": {
    "tf3-companion": {
      "command": "C:\\Tools\\uv\\uv.exe",
      "args": ["run", "--project", "C:\\Projects\\tf3-companion", "tf3c", "mcp"],
      "env": {
        "TF3C_USERDATA_DIR": "C:\\Program Files (x86)\\Steam\\userdata\\ACCOUNT_ID\\3493540\\local",
        "TF3C_DATA_DIR": "C:\\CompanionData"
      }
    }
  }
}
```

Replace all example paths. Omit `env` if discovery and default storage are appropriate. Backslashes must be escaped in JSON, unlike PowerShell strings.

Claude Desktop commonly stores this in `claude_desktop_config.json` under `~/Library/Application Support/Claude` on macOS or `%APPDATA%\Claude` on Windows. Claude Code supports project `.mcp.json`; Cursor supports its MCP settings/`mcp.json`. Client versions can change configuration locations and approval flows: use the client's current settings documentation, restart/reconnect, and inspect server startup errors. These examples have not been exercised in a real client during this review.

## Codex TOML configuration

Merge a server entry into your Codex `config.toml`, using actual absolute paths:

```toml
[mcp_servers.tf3-companion]
command = "/absolute/path/to/uv"
args = ["run", "--project", "/absolute/path/to/tf3-companion", "tf3c", "mcp"]

[mcp_servers.tf3-companion.env]
TF3C_USERDATA_DIR = "/absolute/path/to/game/userdata/local"
```

On Windows, TOML literal strings simplify paths:

```toml
[mcp_servers.tf3-companion]
command = 'C:\Tools\uv\uv.exe'
args = ['run', '--project', 'C:\Projects\tf3-companion', 'tf3c', 'mcp']
```

For omp or another MCP-capable client, register the same command, argument array and optional environment in that client's MCP configuration. Do not assume JSON key names are interchangeable across clients.

## First conversation

> Check the companion status and collection errors. Review loss-making lines first, then opportunities to improve profitable ones. Explain your evidence and uncertainty. Do not change anything in the game or install/remove mods. Ask me before recording a decision.

Start with `status`, then findings; request `refresh` only when the game is open and the player intends a new observation. `load` is instantaneous, annual profit is rolling, and unverified fields must not become accounting facts. Preserve full entity names so the player can find them. The agent should answer in the player's language while code and public documents remain English.

## Prompts and resources

| Prompt | Optional argument |
| --- | --- |
| `monthly-review` | None |
| `annual-review` | `year` |
| `line-triage` | `line` id or name |
| `fleet-renewal` | `line` id or name |
| `cargo-opportunities` | `cargo` |
| `decision-review` | `status`: `planned`, `done` or `dropped` (default `planned`) |

Resources: `tf3c://knowledge` lists shipped topics; `tf3c://knowledge/{topic}` reads a topic; `tf3c://notes` exposes player notes; `tf3c://report/latest` reads the latest generated Markdown report. Missing reports require generating one first. Knowledge can be read without game discovery; data-dependent resources need the relevant snapshot/history.

Tools expose company/entity data, findings, opportunities, history, knowledge, notes, decisions, logs, XLSX export and reports. The `report` tool accepts `kind`, optional `year` and `html`; it returns Markdown and local output paths, not an uploaded report. Recording notes or decisions changes companion data, not gameplay, and should reflect a real agreement with the player.

## Connection checks

Run `uv run tf3c doctor` in the source checkout, then use the same executable, checkout path and environment in the client. Confirm a `status` response through the client before assuming configuration works. Approve only permissions you understand. Hosted CI cannot verify a desktop client's configuration or privacy behavior.
