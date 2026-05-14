# MCP Client Tips

These examples are meant to reduce setup friction for students. Replace `/ABSOLUTE/PATH/...` with the real path on the machine.

## Environment First

Before running any command in this repo:

```bash
conda activate aitclab
```

If you are scripting from a non-interactive shell, load the conda hook first:

```bash
eval "$(conda shell.bash hook)"
conda activate aitclab
```

## Claude Desktop

Anthropic’s MCP docs are here:

- https://code.claude.com/docs/en/mcp

Example `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "C:\\Windows\\System32\\wsl.exe",
      "args": [
        "bash",
        "-lc",
        "source ~/miniconda3/etc/profile.d/conda.sh && conda activate aitclab && python /ABSOLUTE/PATH/TO/implementation/mcp_server.py --db-path /ABSOLUTE/PATH/TO/implementation/lab.db"
      ],
      "env": {}
    }
  }
}
```

Tips:

- Use absolute paths to avoid `spawn ... ENOENT` issues.
- On Windows + WSL2, do not point `command` directly at `/home/.../python`; let Windows spawn `wsl.exe` and run the Linux command inside `bash -lc`.
- In the current Claude Desktop chat flow on this machine, MCP resources work most reliably when you attach them from `Connectors -> Add from sqlite-lab` instead of only typing the URI manually.
- Restart Claude Desktop after editing the MCP config if the server does not appear immediately.
- If outputs are large, check `MAX_MCP_OUTPUT_TOKENS`.
- You can keep [claude_desktop.mcp.json.example](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/claude_desktop.mcp.json.example) in the repo as a ready-made template.
- On this machine, [claude_desktop_config.local.example.json](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/claude_desktop_config.local.example.json) is the fastest starting point.
- Anthropic’s current help center now emphasizes Desktop Extensions in Claude Desktop; for this lab, manual JSON config is still the simplest grading-friendly setup.
- `claude_desktop_config.json` is for the chat app connector flow; the `Code` tab uses separate MCP config files.

## Codex

OpenAI’s current MCP doc page for Codex is here:

- https://developers.openai.com/learn/docs-mcp

Example `~/.codex/config.toml`:

```toml
[mcp_servers.sqlite_lab]
command = "python"
args = ["/ABSOLUTE/PATH/TO/implementation/mcp_server.py", "--db-path", "/ABSOLUTE/PATH/TO/implementation/lab.db"]
```

Tips:

- Keep the server name short and descriptive.
- Add project instructions in `AGENTS.md` telling the agent when to use the database MCP server.
- Verify with `codex mcp list` if the CLI version supports it.
- Use the exact `python` from the `aitclab` environment.
- Treat Codex as optional verification; for this lab, prioritize Claude Desktop in screenshots and demo flow.

Suggested `AGENTS.md` snippet:

```md
Use the `sqlite_lab` MCP server whenever the task needs database schema context or SQL-backed record lookup.
```

## Gemini CLI

Reference:

- https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md

Recommended setup command:

```bash
gemini mcp add sqlite-lab /ABSOLUTE/PATH/TO/python /ABSOLUTE/PATH/TO/implementation/mcp_server.py --description "SQLite lab FastMCP server" --timeout 10000
```

Then verify:

```bash
gemini mcp list
gemini --allowed-mcp-server-names sqlite-lab --yolo -p "Use the sqlite-lab MCP server and show me the top 2 students by score."
```

Alternative settings fragment:

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/implementation/mcp_server.py"],
      "cwd": "/ABSOLUTE/PATH/TO/implementation",
      "timeout": 10000,
      "trust": false
    }
  }
}
```

Tips:

- Prefer `gemini mcp add` over manual JSON edits.
- Avoid underscores in Gemini MCP server aliases.
- Use the exact Python interpreter where `fastmcp` is installed.
- `gemini mcp list` should show the server as `Connected`.

## Antigravity

Antigravity’s MCP behavior changes quickly. In many current setups, the config file is `mcp_config.json` and uses a shape similar to Gemini CLI.

Illustrative config:

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/implementation/mcp_server.py"],
      "cwd": "/ABSOLUTE/PATH/TO/implementation"
    }
  }
}
```

Tips:

- Verify the actual config location from the product UI in your installed version.
- Prefer stdio first; it is easier for a classroom lab than remote auth.
- Avoid hardcoding secrets into raw JSON files.

## Inspector

Reference:

- https://modelcontextprotocol.io/docs/tools/inspector

Typical local run:

```bash
mkdir -p .npm-cache
NPM_CONFIG_CACHE="$PWD/.npm-cache" npx -y @modelcontextprotocol/inspector /ABSOLUTE/PATH/TO/python /ABSOLUTE/PATH/TO/implementation/mcp_server.py
```

If you keep the reference implementation structure, you can also run:

```bash
cd implementation
./start_inspector.sh
```

Checklist:

- tools appear with schemas
- resources appear
- resource templates appear
- valid tool call succeeds
- invalid tool call returns a clear error

## Bonus Tips

- For bonus network transport, use `--transport sse` or `--transport streamable-http` together with `--auth-token`.
- For bonus PostgreSQL support, use `--db-backend postgres --postgres-dsn ...`.
- Keep stdio as the default path for grading because it is the lowest-friction MCP setup.
