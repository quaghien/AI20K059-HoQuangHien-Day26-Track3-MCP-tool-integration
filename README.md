# SQLite Lab MCP Server

## Student Information

- Họ tên: Hồ Quang Hiển
- MSSV: 2A202600059

## Overview

This repository contains a FastMCP server that exposes a small academic database through three tools:

- `search`
- `insert`
- `aggregate`

It also exposes schema context through MCP resources:

- `schema://database`
- `schema://table/{table_name}`

The main backend is SQLite. Bonus support is included for PostgreSQL through the same adapter contract, plus authenticated network transport for `sse` and `streamable-http`.

## Project Structure

```text
implementation/
  db.py
  init_db.py
  mcp_server.py
  verify_server.py
  start_inspector.sh
  tests/
    conftest.py
    test_server.py
```

## Dataset

The seeded SQLite database contains:

- `students`
- `courses`
- `enrollments`
- `student_scores` view

The `student_scores` view is read-only and is useful for demo queries such as average score by cohort.

## Environment Setup

All lab commands should run inside the `aitclab` conda environment.

Interactive shell:

```bash
conda activate aitclab
```

If you need to run commands from a non-interactive shell:

```bash
eval "$(conda shell.bash hook)"
conda activate aitclab
```

Install dependencies:

```bash
conda activate aitclab
pip install fastmcp psycopg[binary] pytest httpx
```

## Initialize the Database

Create or reset the SQLite demo database:

```bash
conda activate aitclab
python implementation/init_db.py
```

This creates `implementation/lab.db`.

## Run the MCP Server

### Default stdio mode

```bash
conda activate aitclab
python implementation/mcp_server.py --db-path implementation/lab.db
```

Default behavior:

- backend: `sqlite`
- transport: `stdio`
- database path: `implementation/lab.db`

### Bonus: authenticated SSE transport

```bash
conda activate aitclab
python implementation/mcp_server.py \
  --db-path implementation/lab.db \
  --transport sse \
  --host 127.0.0.1 \
  --port 8000 \
  --auth-token demo-token
```

### Bonus: authenticated streamable HTTP transport

```bash
conda activate aitclab
python implementation/mcp_server.py \
  --db-path implementation/lab.db \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8000 \
  --auth-token demo-token
```

### Bonus: PostgreSQL backend

```bash
conda activate aitclab
python implementation/mcp_server.py \
  --db-backend postgres \
  --postgres-dsn "postgresql://USER:PASSWORD@HOST:5432/DBNAME"
```

## Tool Reference

### `search`

Purpose:

- query rows from a validated table or view
- support filters, selected columns, ordering, and pagination

Arguments:

- `table`
- `filters`
- `columns`
- `limit`
- `offset`
- `order_by`
- `descending`

Supported operators:

- `eq`
- `ne`
- `gt`
- `gte`
- `lt`
- `lte`
- `like`
- `in`

Example:

```json
{
  "table": "students",
  "filters": [
    {"column": "cohort", "operator": "eq", "value": "A1"}
  ],
  "columns": ["name", "cohort"],
  "order_by": "name",
  "limit": 2,
  "offset": 0
}
```

### `insert`

Purpose:

- insert one row into a writable table
- reject empty payloads
- reject writes into views

Arguments:

- `table`
- `values`

Example:

```json
{
  "table": "students",
  "values": {
    "name": "Lan Do",
    "cohort": "C1",
    "email": "lan.do@example.com",
    "age": 24
  }
}
```

### `aggregate`

Purpose:

- compute aggregate metrics with optional filters and grouping

Arguments:

- `table`
- `metric`
- `column`
- `filters`
- `group_by`

Supported metrics:

- `count`
- `avg`
- `sum`
- `min`
- `max`

Example:

```json
{
  "table": "student_scores",
  "metric": "avg",
  "column": "score",
  "group_by": "cohort"
}
```

## Resource Reference

### Full schema

```text
schema://database
```

Returns the full database schema as JSON text, including tables, views, column types, nullable flags, defaults, and primary key markers.

### Single table schema

```text
schema://table/{table_name}
```

Example:

```text
schema://table/students
```

## Validation Rules

The server rejects:

- unknown table names
- unknown column names
- unsupported filter operators
- invalid aggregate metrics
- aggregate requests missing a required column
- empty inserts
- inserts into views
- invalid `limit` or `offset`

All query values are executed with parameterized SQL. Table and column names are validated against live schema introspection before any SQL is assembled.

## Automated Tests

Run the unit test suite:

```bash
conda activate aitclab
pytest implementation/tests/test_server.py
```

Coverage includes:

- tool discovery
- resource discovery
- resource readability
- valid `search`, `insert`, `aggregate`
- invalid request handling
- SQLite adapter validation
- bonus bearer-token gate
- PostgreSQL adapter contract instantiation

## Smoke Verification

Run the repeatable verification script:

```bash
conda activate aitclab
python implementation/verify_server.py
```

This checks:

- server startup through FastMCP client initialization
- tool discovery
- resource and resource-template discovery
- successful tool calls
- failing tool calls with clear errors

## MCP Inspector

Use the helper script:

```bash
conda activate aitclab
./implementation/start_inspector.sh
```

Or run manually:

```bash
conda activate aitclab
mkdir -p .npm-cache
NPM_CONFIG_CACHE="$PWD/.npm-cache" npx -y @modelcontextprotocol/inspector \
  "$(which python)" "$PWD/implementation/mcp_server.py" --db-path "$PWD/implementation/lab.db"
```

Suggested Inspector checks:

1. Confirm `search`, `insert`, and `aggregate` are listed.
2. Confirm `schema://database` appears in resources.
3. Confirm `schema://table/{table_name}` appears in resource templates.
4. Run a valid `search` on cohort `A1`.
5. Run a valid `insert`.
6. Run an invalid `search` with a missing table.

## Claude Desktop MCP Client Example

Claude Desktop chat should be the primary client for the lab demo.

Use a local MCP config JSON similar to [claude_desktop.mcp.json.example](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/claude_desktop.mcp.json.example).
For this machine, you can also start from [claude_desktop_config.local.example.json](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/claude_desktop_config.local.example.json), which is prepared for `Windows Claude Desktop + WSL2 + aitclab`.

Example config:

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

Recommended workflow:

1. `conda activate aitclab`
2. Run `python implementation/init_db.py`
3. Point Claude Desktop to the JSON config above
4. Restart Claude Desktop if needed so the MCP server is discovered
5. Verify Claude can call `search`, `insert`, `aggregate`
6. Verify Claude can attach `Database schema` from `Connectors -> Add from sqlite-lab`
7. Ask Claude to summarize the attached schema resource and then extract the `students` table schema

Important note:

- Claude Desktop launches the MCP server process directly.
- If you use the Windows Claude Desktop app together with a repo and conda environment inside WSL2, do not point `command` directly at `/home/.../python`.
- The Windows app cannot spawn a Linux executable path directly, which leads to `ENOENT`.
- In practice, the safest setup is to let Windows spawn `C:\\Windows\\System32\\wsl.exe`, then let `wsl.exe` run `bash -lc`, activate `aitclab`, and launch the Python server inside WSL.
- This is an implementation recommendation based on the observed `ENOENT` behavior and local process spawning rules, not a direct quote from Anthropic docs.

Important distinction:

- `claude_desktop_config.json` is for the Claude Desktop chat app and its `Connectors`.
- The `Code` tab uses a separate MCP configuration path such as `~/.claude.json` or project `.mcp.json`.
- If you configure a server in `claude_desktop_config.json`, it should appear in chat `Connectors`, not automatically in the `Code` tab.

Suggested E2E prompts in Claude Desktop:

```text
Use the sqlite-lab MCP server. Show me all students in cohort A1.
```

```text
Use sqlite-lab to calculate the average score by cohort.
```

```text
Use sqlite-lab to insert a new student named Demo User in cohort C9 with email demo.user@example.com and age 22.
```

Resource flow in Claude Desktop chat:

1. Click `+`
2. Choose `Connectors`
3. Choose `Add from sqlite-lab`
4. Select `Database schema`
5. After the resource card is attached, ask:

```text
Hãy tóm tắt schema database từ resource vừa được thêm.
```

```text
Dựa trên resource vừa thêm, hãy cho tôi schema của bảng students.
```

### Optional Codex Example

If you also want to verify with Codex, use `~/.codex/config.toml`:

```toml
[mcp_servers.sqlite_lab]
command = "python"
args = ["/ABSOLUTE/PATH/TO/implementation/mcp_server.py", "--db-path", "/ABSOLUTE/PATH/TO/implementation/lab.db"]
```

## Demo Checklist

- show `conda activate aitclab`
- initialize the database
- start the MCP server
- open Claude Desktop and show the `Connectors` panel
- show tool discovery in Inspector or a client
- attach `Database schema` from `Connectors -> Add from sqlite-lab`
- summarize the attached schema resource
- extract the `students` table schema from the attached resource
- run a valid `search`
- run a valid `insert`
- run a valid `aggregate`
- run an invalid request and show the clear error
- show Claude Desktop config JSON
- show Claude Desktop discovering the MCP server
- if using WSL2, show that the config uses `wsl.exe`
- if bonus is demonstrated, show authenticated SSE transport or PostgreSQL backend

## Screenshot Evidence

Suggested screenshot set for submission:

1. [01-claude-desktop-server-running.png](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/docs/screenshots/01-claude-desktop-server-running.png)
   Claude Desktop Developer settings showing `sqlite-lab` is running through `wsl.exe`.
2. [02-claude-desktop-add-database-schema-resource.png](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/docs/screenshots/02-claude-desktop-add-database-schema-resource.png)
   `Connectors -> Add from sqlite-lab -> Database schema`.
3. [03-claude-desktop-tool-discovery-search-aggregate-insert.png](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/docs/screenshots/03-claude-desktop-tool-discovery-search-aggregate-insert.png)
   Claude discovers the `search`, `aggregate`, and `insert` tools.
4. [04-claude-desktop-tool-discovery-aggregate-insert-details.png](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/docs/screenshots/04-claude-desktop-tool-discovery-aggregate-insert-details.png)
   Additional tool details for `aggregate` and `insert`.
5. [05-claude-desktop-database-schema-resource-summary.png](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/docs/screenshots/05-claude-desktop-database-schema-resource-summary.png)
   Claude summarizes the full database schema from the attached resource.
6. [06-claude-desktop-students-table-schema-from-resource.png](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/docs/screenshots/06-claude-desktop-students-table-schema-from-resource.png)
   Claude extracts the `students` table schema from the attached resource.
7. [07-pytest-16-passed.png](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/docs/screenshots/07-pytest-16-passed.png)
   Unit tests passing in the `aitclab` environment.
8. [08-verify-server-pass-output.png](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/docs/screenshots/08-verify-server-pass-output.png)
   Repeatable smoke verification, including the intentional invalid-request PASS case.

## Notes for Grading

Base-score requirements covered:

- FastMCP server starts
- clean implementation structure
- reproducible SQLite seed data
- separate database logic and server logic
- required tools with validation
- required resources
- automated testing and smoke verification
- Claude Desktop configuration example

Bonus coverage included in code:

- PostgreSQL adapter behind the same MCP surface
- authenticated network transport for `sse` and `streamable-http`
- output metadata such as `returned`, `limit`, `offset`, and `backend`

## Verified References

These docs were re-checked while preparing the Claude Desktop flow:

- Anthropic / Claude Code MCP docs: https://code.claude.com/docs/en/mcp
- Anthropic Help Center, "Getting Started with Local MCP Servers on Claude Desktop", published March 16, 2026: https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop

Useful takeaways from those sources:

- Project-scoped MCP configs use `.mcp.json`.
- Anthropic currently highlights Desktop Extensions as the easier Claude Desktop path.
- For this lab, manual local stdio JSON config is still appropriate because the assignment explicitly asks for config JSON and E2E verification.
- In Claude Desktop, you can inspect connected servers via the `Connectors` entry from the `+` button, or via Developer settings and logs.
- Claude Code desktop docs also clarify that MCP servers configured for the desktop chat app in `claude_desktop_config.json` are separate from the `Code` tab.
