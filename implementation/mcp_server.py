from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn
from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from implementation.db import BaseDatabaseAdapter, PostgresAdapter, SQLiteAdapter, ValidationError
from implementation.init_db import DEFAULT_DB_PATH, create_database


class BearerTokenMiddleware:
    """Minimal bearer token protection for network transports."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        expected = f"Bearer {self.token}"
        if headers.get("authorization") != expected:
            response = JSONResponse(
                {
                    "error": "unauthorized transport request",
                    "error_description": "Provide a valid Bearer token in the Authorization header.",
                },
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


@dataclass(frozen=True)
class ServerConfig:
    db_backend: str = "sqlite"
    db_path: Path = DEFAULT_DB_PATH
    postgres_dsn: str | None = None
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000
    auth_token: str | None = None
    path: str = "/mcp"


def create_adapter(config: ServerConfig) -> BaseDatabaseAdapter:
    if config.db_backend == "sqlite":
        if not config.db_path.exists():
            create_database(config.db_path)
        return SQLiteAdapter(config.db_path)
    if config.db_backend == "postgres":
        if not config.postgres_dsn:
            raise ValueError("postgres backend requires --postgres-dsn or MCP_POSTGRES_DSN.")
        return PostgresAdapter(config.postgres_dsn)
    raise ValueError(f"Unsupported db backend: {config.db_backend}")


def create_mcp_server(adapter: BaseDatabaseAdapter) -> FastMCP:
    mcp = FastMCP(
        "SQLite Lab MCP Server",
        instructions=(
            "Use the schema resources when you need database structure context. "
            "All tool inputs are validated against the live database schema."
        ),
    )

    @mcp.tool(
        name="search",
        description="Search rows from a validated table or view using safe filters, ordering, and pagination.",
    )
    def search(
        table: str,
        filters: list[dict[str, Any]] | None = None,
        columns: list[str] | None = None,
        limit: int = BaseDatabaseAdapter.DEFAULT_LIMIT,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        return adapter.search(
            table=table,
            filters=filters,
            columns=columns,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
        )

    @mcp.tool(
        name="insert",
        description="Insert one validated row into a writable table and return the inserted payload.",
    )
    def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
        return adapter.insert(table=table, values=values)

    @mcp.tool(
        name="aggregate",
        description="Compute aggregate metrics such as count, avg, sum, min, and max with optional grouping.",
    )
    def aggregate(
        table: str,
        metric: str,
        column: str | None = None,
        filters: list[dict[str, Any]] | None = None,
        group_by: str | list[str] | None = None,
    ) -> dict[str, Any]:
        return adapter.aggregate(
            table=table,
            metric=metric,
            column=column,
            filters=filters,
            group_by=group_by,
        )

    @mcp.resource(
        "schema://database",
        name="database_schema",
        description="Full database schema snapshot including tables, views, and columns.",
        mime_type="application/json",
    )
    def database_schema() -> str:
        return adapter.schema_json()

    @mcp.resource(
        "schema://table/{table_name}",
        name="table_schema",
        description="Schema for a specific table or view.",
        mime_type="application/json",
    )
    def table_schema(table_name: str) -> str:
        return adapter.schema_json(table_name)

    return mcp


def create_http_app(
    mcp: FastMCP,
    *,
    transport: str,
    auth_token: str,
    path: str,
):
    middleware = [Middleware(BearerTokenMiddleware, token=auth_token)]
    app_transport = "sse" if transport == "sse" else "streamable-http"
    return mcp.http_app(path=path, middleware=middleware, transport=app_transport)


def parse_args(argv: list[str] | None = None) -> ServerConfig:
    parser = argparse.ArgumentParser(description="Run the SQLite Lab MCP server.")
    parser.add_argument("--db-backend", choices=["sqlite", "postgres"], default="sqlite")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--postgres-dsn", default=os.getenv("MCP_POSTGRES_DSN"))
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Run stdio by default, or expose an authenticated network transport for bonus verification.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--auth-token", default=os.getenv("MCP_AUTH_TOKEN"))
    parser.add_argument("--path", default="/mcp")
    args = parser.parse_args(argv)
    return ServerConfig(
        db_backend=args.db_backend,
        db_path=Path(args.db_path),
        postgres_dsn=args.postgres_dsn,
        transport=args.transport,
        host=args.host,
        port=args.port,
        auth_token=args.auth_token,
        path=args.path,
    )


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    adapter = create_adapter(config)
    mcp = create_mcp_server(adapter)

    if config.transport == "stdio":
        mcp.run(transport="stdio")
        return 0

    if not config.auth_token:
        raise SystemExit("Network transport requires --auth-token or MCP_AUTH_TOKEN.")

    app = create_http_app(
        mcp,
        transport=config.transport,
        auth_token=config.auth_token,
        path=config.path,
    )
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        raise SystemExit(str(exc)) from exc
