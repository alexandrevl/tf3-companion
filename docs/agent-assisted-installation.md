# Install with an AI assistant

An AI assistant can walk you through installing TF3 Companion on Windows or macOS, before the MCP server exists. The full procedure, stage evidence and recovery table live in one place: the [setup guide](../src/tf3companion/setup_guide.md). After the MCP server is connected, the same guide is available as the `tf3c://setup` resource and the `setup-check` prompt.

## Two ways to work

| Assistant | What it can do |
| --- | --- |
| Local agent with terminal access (Claude Code, Codex, omp, Cursor agent…) | Runs the commands you approve and reads their output |
| Text-only chat (ChatGPT or Claude in a browser) | Gives you one command at a time; you run it and paste the output |

A browser chat cannot start the local stdio MCP server on your computer. It can still guide installation; analysis through MCP needs a local client.

## Copy this request

> Help me install TF3 Companion, a read-only Transport Fever 3 data analyst, on my computer (Windows or macOS — ask me which). Follow its setup guide: https://github.com/OWNER/REPO/blob/main/src/tf3companion/setup_guide.md (or the `src/tf3companion/setup_guide.md` file in my checkout).
>
> Before doing anything, tell me whether you can run commands and read files on my computer, or whether I should run commands and paste the output. Ask for my approval before installing software, cloning or updating the repository, installing or replacing the bridge mod, or editing an AI client's configuration; merge configuration entries and keep my other settings. I will enable the mod, load my save and make every game change myself.
>
> Run `tf3c doctor` and read every check, not only `ok`. Report each stage — package, game paths, bridge revision, my activation, MCP connection, fresh snapshot and first report — as verified, pending or failing with the evidence. Do not call setup complete until a fresh snapshot and a report exist.

Replace `OWNER/REPO` with the repository's actual GitHub location, or remove the link if you already have the checkout.

## Related

- [Install, update and remove the bridge](install-mod.md)
- [Connect an MCP agent](agents.md)
- [Troubleshooting](troubleshooting.md)
- [Privacy and storage](privacy.md)
