"""Shared pytest fixtures.

Since the app is Postgres-only (no local SQLite fallback — see backend/db.py), DB-touching
tests need a real Postgres to run against. `fresh_db` isolates each test in its own
throwaway schema on that same database (via libpq's `options=-csearch_path=...` connection
trick), so tests stay independent and repeatable without needing a fresh database per test.

Point TEST_DATABASE_URL (falling back to DATABASE_URL) at any Postgres — your Supabase
project is fine to use directly; tests only ever touch their own throwaway schema, never
the app's real tables. If neither is set, DB-touching tests are skipped (not failed) so the
pure-logic test files (stats/rules/guardrails/data_gen) still run with zero setup.
"""
from __future__ import annotations

import os
import uuid

import psycopg
import pytest

import backend.db as db_module
from backend.config import get_settings


@pytest.fixture
def fresh_db(monkeypatch):
    base_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not base_url:
        pytest.skip(
            "Set TEST_DATABASE_URL (or DATABASE_URL) to a Postgres connection string to "
            "run DB-touching tests — see README 'Database' section."
        )

    schema = f"test_{uuid.uuid4().hex[:12]}"

    admin_conn = psycopg.connect(base_url)
    try:
        with admin_conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA "{schema}"')
        admin_conn.commit()
    finally:
        admin_conn.close()

    sep = "&" if "?" in base_url else "?"
    scoped_url = f"{base_url}{sep}options=-csearch_path%3D{schema}"
    monkeypatch.setenv("DATABASE_URL", scoped_url)
    get_settings.cache_clear()
    db_module._conn = None

    try:
        db_module.get_connection()  # triggers schema DDL inside the throwaway schema
        yield
    finally:
        db_module._conn = None
        get_settings.cache_clear()
        cleanup_conn = psycopg.connect(base_url)
        try:
            with cleanup_conn.cursor() as cur:
                cur.execute(f'DROP SCHEMA "{schema}" CASCADE')
            cleanup_conn.commit()
        finally:
            cleanup_conn.close()
