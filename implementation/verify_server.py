from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import anyio
from fastmcp import Client

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from implementation.init_db import create_database
from implementation.mcp_server import ServerConfig, create_adapter, create_mcp_server


async def run_verification(db_path: Path) -> list[tuple[str, bool, str]]:
    create_database(db_path)
    server = create_mcp_server(create_adapter(ServerConfig(db_path=db_path)))
    checks: list[tuple[str, bool, str]] = []

    async with Client(server) as client:
        tools = await client.list_tools()
        tool_names = sorted(tool.name for tool in tools)
        checks.append(("server starts correctly", True, "client initialized successfully"))
        checks.append(
            ("three required tools are discoverable", tool_names == ["aggregate", "insert", "search"], ", ".join(tool_names)),
        )

        resources = await client.list_resources()
        resource_uris = [str(resource.uri) for resource in resources]
        checks.append(
            ("full schema resource is discoverable", "schema://database" in resource_uris, ", ".join(map(str, resource_uris))),
        )

        templates = await client.list_resource_templates()
        template_uris = [template.uriTemplate for template in templates]
        checks.append(
            (
                "table schema resource template is discoverable",
                "schema://table/{table_name}" in template_uris,
                ", ".join(map(str, template_uris)),
            )
        )

        search_result = await client.call_tool(
            "search",
            {
                "table": "students",
                "filters": [{"column": "cohort", "operator": "eq", "value": "A1"}],
                "order_by": "name",
            },
        )
        checks.append(
            ("valid search call succeeds", search_result.data["returned"] == 2, json.dumps(search_result.data, ensure_ascii=False)),
        )

        insert_result = await client.call_tool(
            "insert",
            {
                "table": "students",
                "values": {
                    "name": "Hoa Vu",
                    "cohort": "C3",
                    "email": "hoa.vu@example.com",
                    "age": 23,
                },
            },
        )
        checks.append(
            ("valid insert call succeeds", insert_result.data["row"]["name"] == "Hoa Vu", json.dumps(insert_result.data, ensure_ascii=False)),
        )

        aggregate_result = await client.call_tool(
            "aggregate",
            {
                "table": "student_scores",
                "metric": "avg",
                "column": "score",
                "group_by": "cohort",
            },
        )
        checks.append(
            ("valid aggregate call succeeds", len(aggregate_result.data["rows"]) >= 2, json.dumps(aggregate_result.data, ensure_ascii=False)),
        )

        schema_payload = await client.read_resource("schema://database")
        checks.append(
            ("full schema resource is readable", "student_scores" in schema_payload[0].text, schema_payload[0].text[:120]),
        )
        table_payload = await client.read_resource("schema://table/students")
        checks.append(
            ("per-table schema resource is readable", "\"name\": \"students\"" in table_payload[0].text, table_payload[0].text[:120]),
        )

        invalid_result = await client.call_tool(
            "search",
            {"table": "missing_table"},
            raise_on_error=False,
        )
        error_text = invalid_result.content[0].text if invalid_result.content else ""
        checks.append(("invalid tool call returns clear error", invalid_result.is_error and "unknown table" in error_text, error_text))

    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the SQLite Lab MCP server.")
    parser.add_argument("--db-path", default=str(Path(__file__).resolve().parent / "verify_lab.db"))
    args = parser.parse_args(argv)

    checks = anyio.run(run_verification, Path(args.db_path))
    failed = False
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {detail}")
        failed = failed or not ok
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
