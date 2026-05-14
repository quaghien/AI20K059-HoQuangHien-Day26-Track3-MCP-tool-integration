from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


@dataclass(frozen=True)
class FilterSpec:
    column: str
    operator: str
    value: Any


class BaseDatabaseAdapter(ABC):
    """Common contract for database backends used by the MCP surface."""

    DEFAULT_LIMIT = 20
    MAX_LIMIT = 100
    SUPPORTED_OPERATORS = {
        "eq": "=",
        "ne": "!=",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
        "like": "LIKE",
        "in": "IN",
    }
    SUPPORTED_METRICS = {"count", "avg", "sum", "min", "max"}

    def __init__(self) -> None:
        self._schema_cache: dict[str, dict[str, Any]] | None = None

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """A human-friendly backend identifier."""

    @abstractmethod
    def connect(self):
        """Open a connection for the concrete backend."""

    @abstractmethod
    def _list_relations(self) -> list[dict[str, str]]:
        """Return relations with name and kind."""

    @abstractmethod
    def _fetch_table_schema(self, table: str) -> list[dict[str, Any]]:
        """Return normalized column definitions for a single relation."""

    @abstractmethod
    def _placeholder(self, index: int) -> str:
        """Return the backend-specific SQL parameter placeholder."""

    @abstractmethod
    def _insert_and_fetch(
        self,
        conn: Any,
        table: str,
        values: dict[str, Any],
        schema_entry: dict[str, Any],
    ) -> tuple[int | str | None, dict[str, Any]]:
        """Insert a record and return its identifier plus fetched row."""

    def refresh_schema(self) -> dict[str, dict[str, Any]]:
        schema: dict[str, dict[str, Any]] = {}
        for relation in self._list_relations():
            columns = self._fetch_table_schema(relation["name"])
            schema[relation["name"]] = {
                "name": relation["name"],
                "kind": relation["kind"],
                "columns": columns,
                "column_names": [column["name"] for column in columns],
            }
        self._schema_cache = schema
        return schema

    def _schema(self) -> dict[str, dict[str, Any]]:
        return self._schema_cache or self.refresh_schema()

    def list_tables(self) -> list[str]:
        return sorted(self._schema().keys())

    def get_table_schema(self, table: str) -> dict[str, Any]:
        schema = self._schema()
        if table not in schema:
            raise ValidationError(f"unknown table: {table}")
        return schema[table]

    def get_database_schema(self) -> dict[str, Any]:
        relations = [
            {
                "name": entry["name"],
                "kind": entry["kind"],
                "columns": entry["columns"],
            }
            for entry in self._schema().values()
        ]
        return {"backend": self.backend_name, "relations": sorted(relations, key=lambda item: item["name"])}

    def schema_json(self, table: str | None = None) -> str:
        payload = self.get_table_schema(table) if table else self.get_database_schema()
        return json.dumps(payload, indent=2)

    def _quote_identifier(self, identifier: str) -> str:
        return f'"{identifier}"'

    def _validate_limit_offset(self, limit: int, offset: int) -> None:
        if limit < 1 or limit > self.MAX_LIMIT:
            raise ValidationError(f"invalid limit: {limit}. Expected 1-{self.MAX_LIMIT}.")
        if offset < 0:
            raise ValidationError(f"invalid offset: {offset}. Expected a non-negative integer.")

    def _validate_relation(self, table: str, *, write: bool = False) -> dict[str, Any]:
        schema_entry = self.get_table_schema(table)
        if write and schema_entry["kind"] != "table":
            raise ValidationError(f"insert into view not allowed: {table}")
        return schema_entry

    def _validate_columns(
        self,
        schema_entry: dict[str, Any],
        columns: list[str] | None,
        *,
        field_name: str = "column",
    ) -> list[str]:
        if not columns:
            return schema_entry["column_names"]

        unknown = [column for column in columns if column not in schema_entry["column_names"]]
        if unknown:
            raise ValidationError(f"unknown {field_name}: {', '.join(unknown)}")
        return columns

    def _normalize_filters(self, filters: list[dict[str, Any]] | None) -> list[FilterSpec]:
        if not filters:
            return []

        normalized: list[FilterSpec] = []
        for raw_filter in filters:
            if not isinstance(raw_filter, dict):
                raise ValidationError("filters must be a list of objects.")

            column = raw_filter.get("column")
            operator = raw_filter.get("operator")
            if not column or not operator:
                raise ValidationError("each filter must include column and operator.")
            if operator not in self.SUPPORTED_OPERATORS:
                raise ValidationError(f"unsupported operator: {operator}")

            value = raw_filter.get("value")
            if operator == "in":
                if not isinstance(value, list) or not value:
                    raise ValidationError("operator 'in' requires a non-empty list value.")
            normalized.append(FilterSpec(column=column, operator=operator, value=value))
        return normalized

    def _build_where_clause(
        self,
        schema_entry: dict[str, Any],
        filters: list[dict[str, Any]] | None,
        params: list[Any],
    ) -> str:
        normalized_filters = self._normalize_filters(filters)
        if not normalized_filters:
            return ""

        self._validate_columns(
            schema_entry,
            [flt.column for flt in normalized_filters],
            field_name="column",
        )

        clauses: list[str] = []
        for flt in normalized_filters:
            quoted = self._quote_identifier(flt.column)
            if flt.operator == "in":
                placeholders: list[str] = []
                for value in flt.value:
                    params.append(value)
                    placeholders.append(self._placeholder(len(params)))
                clauses.append(f"{quoted} IN ({', '.join(placeholders)})")
            else:
                params.append(flt.value)
                clauses.append(f"{quoted} {self.SUPPORTED_OPERATORS[flt.operator]} {self._placeholder(len(params))}")
        return " WHERE " + " AND ".join(clauses)

    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        self._validate_limit_offset(limit, offset)
        schema_entry = self._validate_relation(table)
        selected_columns = self._validate_columns(schema_entry, columns, field_name="column")
        params: list[Any] = []

        where_clause = self._build_where_clause(schema_entry, filters, params)
        order_clause = ""
        if order_by:
            self._validate_columns(schema_entry, [order_by], field_name="column")
            direction = "DESC" if descending else "ASC"
            order_clause = f" ORDER BY {self._quote_identifier(order_by)} {direction}"

        params.extend([limit, offset])
        column_sql = ", ".join(self._quote_identifier(column) for column in selected_columns)
        sql = (
            f"SELECT {column_sql} FROM {self._quote_identifier(table)}"
            f"{where_clause}{order_clause} "
            f"LIMIT {self._placeholder(len(params) - 1)} OFFSET {self._placeholder(len(params))}"
        )

        with self.connect() as conn:
            cursor = conn.execute(sql, tuple(params))
            rows = [self._row_to_dict(row) for row in cursor.fetchall()]

        return {
            "table": table,
            "rows": rows,
            "returned": len(rows),
            "limit": limit,
            "offset": offset,
            "order_by": order_by,
            "backend": self.backend_name,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        if not values:
            raise ValidationError("empty insert is not allowed.")

        schema_entry = self._validate_relation(table, write=True)
        columns = list(values.keys())
        self._validate_columns(schema_entry, columns, field_name="column")

        with self.connect() as conn:
            row_id, row = self._insert_and_fetch(conn, table, values, schema_entry)
            conn.commit()

        return {
            "table": table,
            "row": row,
            "row_id": row_id,
            "backend": self.backend_name,
        }

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: list[dict[str, Any]] | None = None,
        group_by: str | list[str] | None = None,
    ) -> dict[str, Any]:
        normalized_metric = metric.lower()
        if normalized_metric not in self.SUPPORTED_METRICS:
            raise ValidationError(f"invalid aggregate metric: {metric}")

        schema_entry = self._validate_relation(table)
        group_columns = [group_by] if isinstance(group_by, str) else list(group_by or [])
        if group_columns:
            self._validate_columns(schema_entry, group_columns, field_name="column")

        aggregate_column = None
        if normalized_metric == "count":
            aggregate_sql = "COUNT(*)"
        else:
            if not column:
                raise ValidationError(f"aggregate missing column for metric: {metric}")
            self._validate_columns(schema_entry, [column], field_name="column")
            aggregate_column = column
            aggregate_sql = f"{normalized_metric.upper()}({self._quote_identifier(column)})"

        params: list[Any] = []
        where_clause = self._build_where_clause(schema_entry, filters, params)

        select_parts = [f"{aggregate_sql} AS value"]
        if group_columns:
            select_parts = [self._quote_identifier(group) for group in group_columns] + select_parts

        group_clause = ""
        if group_columns:
            quoted_groups = ", ".join(self._quote_identifier(group) for group in group_columns)
            group_clause = f" GROUP BY {quoted_groups}"

        sql = (
            f"SELECT {', '.join(select_parts)} FROM {self._quote_identifier(table)}"
            f"{where_clause}{group_clause}"
        )
        with self.connect() as conn:
            cursor = conn.execute(sql, tuple(params))
            rows = [self._row_to_dict(row) for row in cursor.fetchall()]

        return {
            "table": table,
            "metric": normalized_metric,
            "column": aggregate_column,
            "group_by": group_columns,
            "rows": rows,
            "backend": self.backend_name,
        }

    def _row_to_dict(self, row: Any) -> dict[str, Any]:
        if isinstance(row, sqlite3.Row):
            return dict(row)
        if isinstance(row, dict):
            return row
        if hasattr(row, "_mapping"):
            return dict(row._mapping)
        return dict(row)


class SQLiteAdapter(BaseDatabaseAdapter):
    """SQLite database adapter used by the main lab implementation."""

    def __init__(self, db_path: str | Path) -> None:
        super().__init__()
        self.db_path = Path(db_path)

    @property
    def backend_name(self) -> str:
        return "sqlite"

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _list_relations(self) -> list[dict[str, str]]:
        sql = """
        SELECT name, type
        FROM sqlite_master
        WHERE type IN ('table', 'view')
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
        with self.connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [{"name": row["name"], "kind": row["type"]} for row in rows]

    def _fetch_table_schema(self, table: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({self._quote_identifier(table)})").fetchall()
        return [
            {
                "name": row["name"],
                "type": row["type"],
                "nullable": not bool(row["notnull"]),
                "default": row["dflt_value"],
                "primary_key": bool(row["pk"]),
            }
            for row in rows
        ]

    def _placeholder(self, index: int) -> str:
        return "?"

    def _insert_and_fetch(
        self,
        conn: sqlite3.Connection,
        table: str,
        values: dict[str, Any],
        schema_entry: dict[str, Any],
    ) -> tuple[int | str | None, dict[str, Any]]:
        columns = list(values.keys())
        placeholders = ", ".join("?" for _ in columns)
        sql = (
            f"INSERT INTO {self._quote_identifier(table)} "
            f"({', '.join(self._quote_identifier(column) for column in columns)}) "
            f"VALUES ({placeholders})"
        )
        cursor = conn.execute(sql, tuple(values[column] for column in columns))
        row_id = cursor.lastrowid

        if "id" in schema_entry["column_names"] and row_id is not None:
            fetch_sql = f"SELECT * FROM {self._quote_identifier(table)} WHERE \"id\" = ?"
            row = conn.execute(fetch_sql, (row_id,)).fetchone()
            return row_id, self._row_to_dict(row)
        return row_id, values


class PostgresAdapter(BaseDatabaseAdapter):
    """Bonus adapter that keeps the MCP surface compatible with PostgreSQL."""

    def __init__(self, dsn: str) -> None:
        super().__init__()
        self.dsn = dsn

    @property
    def backend_name(self) -> str:
        return "postgres"

    def connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def _list_relations(self) -> list[dict[str, str]]:
        sql = """
        SELECT table_name AS name,
               CASE WHEN table_type = 'VIEW' THEN 'view' ELSE 'table' END AS kind
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type IN ('BASE TABLE', 'VIEW')
        ORDER BY table_name
        """
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
        return [{"name": row["name"], "kind": row["kind"]} for row in rows]

    def _fetch_table_schema(self, table: str) -> list[dict[str, Any]]:
        sql = """
        SELECT
            columns.column_name AS name,
            columns.data_type AS type,
            columns.is_nullable = 'YES' AS nullable,
            columns.column_default AS default,
            COALESCE(pk.column_name IS NOT NULL, false) AS primary_key
        FROM information_schema.columns AS columns
        LEFT JOIN (
            SELECT kcu.column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = 'public'
              AND tc.table_name = %s
              AND tc.constraint_type = 'PRIMARY KEY'
        ) AS pk
          ON pk.column_name = columns.column_name
        WHERE columns.table_schema = 'public'
          AND columns.table_name = %s
        ORDER BY columns.ordinal_position
        """
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (table, table))
                return cursor.fetchall()

    def _placeholder(self, index: int) -> str:
        return "%s"

    def _insert_and_fetch(
        self,
        conn: Any,
        table: str,
        values: dict[str, Any],
        schema_entry: dict[str, Any],
    ) -> tuple[int | str | None, dict[str, Any]]:
        columns = list(values.keys())
        placeholders = ", ".join(self._placeholder(i + 1) for i in range(len(columns)))
        sql = (
            f"INSERT INTO {self._quote_identifier(table)} "
            f"({', '.join(self._quote_identifier(column) for column in columns)}) "
            f"VALUES ({placeholders}) RETURNING *"
        )
        with conn.cursor() as cursor:
            cursor.execute(sql, tuple(values[column] for column in columns))
            row = cursor.fetchone()
        row_dict = self._row_to_dict(row)
        return row_dict.get("id"), row_dict

