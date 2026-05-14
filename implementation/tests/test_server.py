from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastmcp import Client

from implementation.db import PostgresAdapter, SQLiteAdapter, ValidationError
from implementation.init_db import create_database
from implementation.mcp_server import BearerTokenMiddleware, ServerConfig, create_adapter, create_mcp_server


@pytest.fixture()
def sqlite_db_path(tmp_path: Path) -> Path:
    return create_database(tmp_path / "lab.db")


@pytest.fixture()
def sqlite_adapter(sqlite_db_path: Path) -> SQLiteAdapter:
    return SQLiteAdapter(sqlite_db_path)


@pytest.fixture()
def sqlite_server(sqlite_adapter: SQLiteAdapter):
    return create_mcp_server(sqlite_adapter)


@pytest.mark.anyio
async def test_server_discovery(sqlite_server):
    async with Client(sqlite_server) as client:
        tools = await client.list_tools()
        assert sorted(tool.name for tool in tools) == ["aggregate", "insert", "search"]

        resources = await client.list_resources()
        assert [str(resource.uri) for resource in resources] == ["schema://database"]

        templates = await client.list_resource_templates()
        assert "schema://table/{table_name}" in [template.uriTemplate for template in templates]


@pytest.mark.anyio
async def test_search_supports_filters_order_and_pagination(sqlite_server):
    async with Client(sqlite_server) as client:
        result = await client.call_tool(
            "search",
            {
                "table": "students",
                "filters": [{"column": "cohort", "operator": "eq", "value": "A1"}],
                "columns": ["name", "cohort"],
                "limit": 1,
                "offset": 1,
                "order_by": "name",
            },
        )

    assert result.data["returned"] == 1
    assert result.data["rows"] == [{"name": "Binh Tran", "cohort": "A1"}]
    assert result.data["limit"] == 1
    assert result.data["offset"] == 1
    assert result.data["backend"] == "sqlite"


@pytest.mark.anyio
async def test_insert_returns_inserted_payload(sqlite_server):
    async with Client(sqlite_server) as client:
        result = await client.call_tool(
            "insert",
            {
                "table": "students",
                "values": {
                    "name": "Lan Do",
                    "cohort": "C1",
                    "email": "lan.do@example.com",
                    "age": 24,
                },
            },
        )

    assert result.data["row"]["name"] == "Lan Do"
    assert result.data["row_id"] is not None


@pytest.mark.anyio
async def test_aggregate_supports_metrics(sqlite_server):
    async with Client(sqlite_server) as client:
        count_result = await client.call_tool("aggregate", {"table": "students", "metric": "count"})
        avg_result = await client.call_tool(
            "aggregate",
            {
                "table": "student_scores",
                "metric": "avg",
                "column": "score",
                "group_by": "cohort",
            },
        )
        sum_result = await client.call_tool(
            "aggregate",
            {"table": "student_scores", "metric": "sum", "column": "score"},
        )
        min_result = await client.call_tool(
            "aggregate",
            {"table": "student_scores", "metric": "min", "column": "score"},
        )
        max_result = await client.call_tool(
            "aggregate",
            {"table": "student_scores", "metric": "max", "column": "score"},
        )

    assert count_result.data["rows"] == [{"value": 4}]
    assert len(avg_result.data["rows"]) == 2
    assert sum_result.data["rows"][0]["value"] > 0
    assert min_result.data["rows"][0]["value"] == 68.0
    assert max_result.data["rows"][0]["value"] == 95.0


@pytest.mark.anyio
async def test_schema_resources_are_readable(sqlite_server):
    async with Client(sqlite_server) as client:
        database_schema = await client.read_resource("schema://database")
        table_schema = await client.read_resource("schema://table/students")

    database_payload = json.loads(database_schema[0].text)
    table_payload = json.loads(table_schema[0].text)
    assert any(relation["name"] == "student_scores" for relation in database_payload["relations"])
    assert table_payload["name"] == "students"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool_name", "arguments", "expected_message"),
    [
        ("search", {"table": "missing"}, "unknown table"),
        ("search", {"table": "students", "order_by": "missing"}, "unknown column"),
        (
            "search",
            {"table": "students", "filters": [{"column": "cohort", "operator": "contains", "value": "A"}]},
            "unsupported operator",
        ),
        ("aggregate", {"table": "students", "metric": "median", "column": "age"}, "invalid aggregate metric"),
        ("aggregate", {"table": "students", "metric": "avg"}, "aggregate missing column"),
        ("insert", {"table": "students", "values": {}}, "empty insert"),
        ("insert", {"table": "student_scores", "values": {"score": 50}}, "insert into view not allowed"),
    ],
)
async def test_invalid_requests_raise_clear_errors(sqlite_server, tool_name, arguments, expected_message):
    async with Client(sqlite_server) as client:
        with pytest.raises(Exception, match=expected_message):
            await client.call_tool(tool_name, arguments)


def test_sqlite_adapter_rejects_invalid_limit(sqlite_adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="invalid limit"):
        sqlite_adapter.search("students", limit=0)


def test_create_adapter_supports_postgres_config():
    adapter = create_adapter(
        ServerConfig(
            db_backend="postgres",
            postgres_dsn="postgresql://postgres:postgres@localhost:5432/postgres",
        )
    )
    assert isinstance(adapter, PostgresAdapter)


@pytest.mark.anyio
async def test_network_transport_requires_valid_bearer_token():
    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    middleware = BearerTokenMiddleware(downstream, token="secret-token")

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    unauthorized_messages = []

    async def capture_unauthorized(message):
        unauthorized_messages.append(message)

    await middleware(
        {"type": "http", "headers": [], "method": "GET", "path": "/mcp"},
        empty_receive,
        capture_unauthorized,
    )

    authorized_messages = []

    async def capture_authorized(message):
        authorized_messages.append(message)

    await middleware(
        {
            "type": "http",
            "headers": [(b"authorization", b"Bearer secret-token")],
            "method": "GET",
            "path": "/mcp",
        },
        empty_receive,
        capture_authorized,
    )

    assert unauthorized_messages[0]["status"] == 401
    assert authorized_messages[0]["status"] == 204


@pytest.mark.skipif(not pytest.importorskip("psycopg"), reason="psycopg is required for postgres adapter bonus coverage")
def test_postgres_adapter_bonus_configuration():
    adapter = PostgresAdapter("postgresql://postgres:postgres@localhost:5432/postgres")
    assert adapter.backend_name == "postgres"
