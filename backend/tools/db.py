"""Tabular data backend: DuckDB (laptop) or Impala over Iceberg (Cloudera).

All SQL in database_client.py / init_db.py is written against this tiny
interface so the storage engine is a deployment choice:

  DB_BACKEND=duckdb   embedded file, DUCKDB_PATH (default <repo>/data/store.db)
  DB_BACKEND=impala   Cloudera Data Warehouse / Data Hub Impala, tables stored as
                      Iceberg in the Cloudera Data Lake. Connection from:
                        IMPALA_HOST, IMPALA_PORT (443), IMPALA_HTTP_PATH (cliservice),
                        IMPALA_USER (default PROJECT_OWNER / HADOOP_USER_NAME / USER),
                        IMPALA_PASSWORD (default WORKLOAD_PASSWORD),
                        IMPALA_DATABASE (default new_item_eval),
                        IMPALA_AUTH (LDAP | JWT, default LDAP), IMPALA_USE_SSL (true)
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def backend() -> str:
    b = os.getenv("DB_BACKEND", "duckdb").strip().lower()
    if b not in ("duckdb", "impala"):
        raise RuntimeError(f"Unsupported DB_BACKEND={b!r} (expected duckdb or impala)")
    return b


def duckdb_path() -> str:
    return os.getenv("DUCKDB_PATH", str(REPO_ROOT / "data" / "store.db"))


def database() -> str:
    return os.getenv("IMPALA_DATABASE", "new_item_eval") if backend() == "impala" else ""


def placeholder() -> str:
    return "%s" if backend() == "impala" else "?"


def placeholders(n: int) -> str:
    return ", ".join([placeholder()] * n)


def qualify(table: str) -> str:
    db = database()
    return f"{db}.{table}" if db else table


def ident(name: str) -> str:
    """Quote a column name that may be a reserved word (e.g. `timestamp` in Impala)."""
    return f"`{name}`" if backend() == "impala" else f'"{name}"'


# ---------------------------------------------------------------------------
# DuckDB backend
# ---------------------------------------------------------------------------

def _duck_query(sql: str, params: Iterable[Any] | None, read_only: bool = True) -> list[tuple]:
    import duckdb

    con = duckdb.connect(duckdb_path(), read_only=read_only)
    try:
        cur = con.execute(sql, list(params or []))
        return cur.fetchall() if cur.description else []
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Impala backend (one shared connection, reconnect on failure)
# ---------------------------------------------------------------------------

_impala_conn = None
_impala_lock = threading.Lock()


def impala_settings() -> dict:
    user = (
        os.getenv("IMPALA_USER")
        or os.getenv("PROJECT_OWNER")
        or os.getenv("HADOOP_USER_NAME")
        or os.getenv("USER", "")
    )
    return {
        "host": os.getenv("IMPALA_HOST", ""),
        "port": int(os.getenv("IMPALA_PORT", "443")),
        "http_path": os.getenv("IMPALA_HTTP_PATH", "cliservice"),
        "user": user,
        "password": os.getenv("IMPALA_PASSWORD") or os.getenv("WORKLOAD_PASSWORD", ""),
        "auth": os.getenv("IMPALA_AUTH", "LDAP").upper(),
        "use_ssl": os.getenv("IMPALA_USE_SSL", "true").strip().lower() in ("1", "true", "yes"),
        "database": database(),
    }


def _impala_connect():
    from impala.dbapi import connect

    s = impala_settings()
    if not s["host"]:
        raise RuntimeError("DB_BACKEND=impala requires IMPALA_HOST")
    kwargs: dict[str, Any] = {
        "host": s["host"],
        "port": s["port"],
        "use_http_transport": True,
        "http_path": s["http_path"],
        "use_ssl": s["use_ssl"],
        "timeout": int(os.getenv("IMPALA_TIMEOUT", "60")),
    }
    if s["auth"] == "JWT":
        from tools.llm_config import resolve_api_key  # same Cloudera workload JWT

        kwargs.update({"auth_mechanism": "JWT", "jwt": resolve_api_key()})
    else:
        kwargs.update({"auth_mechanism": "LDAP", "user": s["user"], "password": s["password"]})
    return connect(**kwargs)


def _impala_run(sql: str, params: Iterable[Any] | None, retries: int = 1) -> list[tuple]:
    global _impala_conn
    params = list(params or [])
    with _impala_lock:
        for attempt in range(retries + 1):
            try:
                if _impala_conn is None:
                    _impala_conn = _impala_connect()
                cur = _impala_conn.cursor()
                try:
                    cur.execute(sql, params or None)
                    return cur.fetchall() if cur.description else []
                finally:
                    cur.close()
            except Exception:
                try:
                    if _impala_conn is not None:
                        _impala_conn.close()
                except Exception:
                    pass
                _impala_conn = None
                if attempt >= retries:
                    raise
    return []


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def query(sql: str, params: Iterable[Any] | None = None) -> list[tuple]:
    """Run a read query and return rows as tuples."""
    if backend() == "impala":
        return _impala_run(sql, params)
    return _duck_query(sql, params, read_only=True)


def execute(sql: str, params: Iterable[Any] | None = None) -> list[tuple]:
    """Run a statement that may write (DDL/DML)."""
    if backend() == "impala":
        return _impala_run(sql, params)
    return _duck_query(sql, params, read_only=False)


def scalar(sql: str, params: Iterable[Any] | None = None) -> Any:
    rows = query(sql, params)
    return rows[0][0] if rows else None


def describe() -> dict:
    """Non-secret summary for /api/health."""
    b = backend()
    out: dict[str, Any] = {"backend": b}
    if b == "duckdb":
        out["path"] = duckdb_path()
        out["exists"] = Path(duckdb_path()).exists()
    else:
        s = impala_settings()
        out.update({"host": s["host"], "database": s["database"], "user": s["user"], "auth": s["auth"]})
    try:
        out["products"] = int(scalar(f"SELECT COUNT(*) FROM {qualify('products')}") or 0)
        out["ok"] = True
    except Exception as e:
        out["ok"] = False
        out["error"] = str(e)[:200]
    return out
