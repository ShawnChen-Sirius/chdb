#!/usr/bin/env python3
"""
Tests for remote() / remoteSecure() table function with query parameter.

Requires:
  1. A rebuilt chdb with the query= parameter support in remote().
  2. Environment variables:
       REMOTE_HOST     - e.g. "xiaozhe-yu-dev-vm:9000"
       REMOTE_USER     - e.g. "remote_user"
       REMOTE_PASSWORD - e.g. "test123"
       TEST_DB         - (optional) database name for test artifacts, default "test_remote_query"

Run:
    REMOTE_HOST=host:9000 REMOTE_USER=user REMOTE_PASSWORD=pwd \
        python -m pytest tests/test_remote_query.py -v
"""

import os
import unittest
import uuid

import pytest

REMOTE_HOST = os.environ.get("REMOTE_HOST")
REMOTE_USER = os.environ.get("REMOTE_USER")
REMOTE_PASSWORD = os.environ.get("REMOTE_PASSWORD")

if not all([REMOTE_HOST, REMOTE_USER, REMOTE_PASSWORD]):
    pytest.skip(
        "Skipping remote query tests: REMOTE_HOST, REMOTE_USER, and REMOTE_PASSWORD must be set",
        allow_module_level=True,
    )

import chdb

TEST_DB = os.environ.get("TEST_DB", "test_remote_query")
TEST_SUFFIX = uuid.uuid4().hex[:8]


def _check_query_param_support():
    """Check if current chdb binary supports remote(query=...) syntax."""
    try:
        chdb.query(
            f"SELECT * FROM remote('{REMOTE_HOST}', "
            f"query = 'SELECT 1', "
            f"'{REMOTE_USER}', '{REMOTE_PASSWORD}')",
            "TabSeparated",
        )
        return True
    except RuntimeError as e:
        if "UNKNOWN_IDENTIFIER" in str(e) or "Unknown expression" in str(e):
            return False
        # Other errors (e.g., connection refused) still mean the syntax is recognized
        return True


QUERY_PARAM_SUPPORTED = _check_query_param_support()
SKIP_MSG = "Current chdb binary does not support remote(query=...). Rebuild libchdb first."


def remote_exec(query_sql):
    """Execute an arbitrary SQL on the remote server via remote(query=...).
    Returns the chdb result object.
    Single quotes inside query_sql must be escaped as \\\\' by the caller.
    """
    sql = (
        f"SELECT * FROM remote('{REMOTE_HOST}', "
        f"query = '{query_sql}', "
        f"'{REMOTE_USER}', '{REMOTE_PASSWORD}')"
    )
    return chdb.query(sql, "TabSeparated")


def remote_table_select(db, table, extra=""):
    """Use original remote('host', 'db', 'table') path to SELECT."""
    sql = (
        f"SELECT * FROM remote('{REMOTE_HOST}', '{db}', '{table}', "
        f"'{REMOTE_USER}', '{REMOTE_PASSWORD}') {extra}"
    )
    return chdb.query(sql, "TabSeparated")


def remote_table_insert(db, table, values_sql):
    """Use original remote('host', 'db', 'table') path to INSERT."""
    sql = (
        f"INSERT INTO FUNCTION remote('{REMOTE_HOST}', '{db}', '{table}', "
        f"'{REMOTE_USER}', '{REMOTE_PASSWORD}') VALUES {values_sql}"
    )
    return chdb.query(sql, "TabSeparated")


def get_status(res):
    """Parse the status column from remote(query=...) result."""
    text = res.bytes().decode().strip()
    if not text:
        return ""
    # Format: shard_num \t host \t status
    parts = text.split("\n")
    statuses = []
    for line in parts:
        cols = line.split("\t")
        statuses.append(cols[2] if len(cols) >= 3 else line)
    return statuses


# ---------------------------------------------------------------------------
# Test: basic connectivity
# ---------------------------------------------------------------------------


@unittest.skipUnless(QUERY_PARAM_SUPPORTED, SKIP_MSG)
class TestRemoteConnectivity(unittest.TestCase):
    """Verify basic connectivity to the remote ClickHouse server."""

    def test_select_1_via_query_param(self):
        res = remote_exec("SELECT 1")
        self.assertFalse(res.has_error(), f"Query failed: {res.error_message()}")
        statuses = get_status(res)
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0], "OK")


# ---------------------------------------------------------------------------
# Test: DDL operations
# ---------------------------------------------------------------------------


@unittest.skipUnless(QUERY_PARAM_SUPPORTED, SKIP_MSG)
class TestRemoteDDL(unittest.TestCase):
    """Test DDL operations via remote(query=...) on the remote server."""

    @classmethod
    def setUpClass(cls):
        remote_exec(f"CREATE DATABASE IF NOT EXISTS {TEST_DB}")

    @classmethod
    def tearDownClass(cls):
        remote_exec(f"DROP DATABASE IF EXISTS {TEST_DB}")

    def test_create_and_drop_table(self):
        tbl = f"{TEST_DB}.ddl_create_{TEST_SUFFIX}"
        res = remote_exec(
            f"CREATE TABLE {tbl} (id UInt32, name String) ENGINE = MergeTree() ORDER BY id"
        )
        statuses = get_status(res)
        self.assertEqual(statuses[0], "OK", f"CREATE TABLE failed: {res.bytes()}")

        res = remote_exec(f"DROP TABLE {tbl}")
        statuses = get_status(res)
        self.assertEqual(statuses[0], "OK", f"DROP TABLE failed: {res.bytes()}")

    def test_create_table_if_not_exists_is_idempotent(self):
        tbl = f"{TEST_DB}.ddl_ifne_{TEST_SUFFIX}"
        remote_exec(f"CREATE TABLE {tbl} (x UInt32) ENGINE = Memory")

        res = remote_exec(f"CREATE TABLE IF NOT EXISTS {tbl} (x UInt32) ENGINE = Memory")
        statuses = get_status(res)
        self.assertEqual(statuses[0], "OK")

        remote_exec(f"DROP TABLE IF EXISTS {tbl}")

    def test_alter_table_add_column(self):
        tbl = f"{TEST_DB}.ddl_alter_{TEST_SUFFIX}"
        remote_exec(f"CREATE TABLE {tbl} (id UInt32) ENGINE = MergeTree() ORDER BY id")

        res = remote_exec(f"ALTER TABLE {tbl} ADD COLUMN value Float64 DEFAULT 0")
        statuses = get_status(res)
        self.assertEqual(statuses[0], "OK", f"ALTER TABLE failed: {res.bytes()}")

        remote_exec(f"DROP TABLE IF EXISTS {tbl}")

    def test_truncate_table(self):
        tbl = f"{TEST_DB}.ddl_trunc_{TEST_SUFFIX}"
        remote_exec(f"CREATE TABLE {tbl} (x UInt32) ENGINE = Memory")

        res = remote_exec(f"TRUNCATE TABLE {tbl}")
        statuses = get_status(res)
        self.assertEqual(statuses[0], "OK", f"TRUNCATE failed: {res.bytes()}")

        remote_exec(f"DROP TABLE IF EXISTS {tbl}")

    def test_drop_nonexistent_table_raises_exception(self):
        """Dropping a non-existent table should raise an exception, same as the original remote() path."""
        tbl = f"{TEST_DB}.nonexistent_{TEST_SUFFIX}"
        with self.assertRaises(RuntimeError) as ctx:
            remote_exec(f"DROP TABLE {tbl}")
        self.assertIn("UNKNOWN_TABLE", str(ctx.exception))

    def test_syntax_error_raises_exception(self):
        """SQL syntax errors should raise an exception."""
        with self.assertRaises(RuntimeError) as ctx:
            remote_exec("CREAT TABLE bad_syntax")
        self.assertIn("SYNTAX_ERROR", str(ctx.exception))


# ---------------------------------------------------------------------------
# Test: DML via query= mode and original remote() path
# ---------------------------------------------------------------------------


@unittest.skipUnless(QUERY_PARAM_SUPPORTED, SKIP_MSG)
class TestRemoteDML(unittest.TestCase):
    """Test DML (INSERT/SELECT) via both query= mode and the original remote() path."""

    tbl_short = f"dml_{TEST_SUFFIX}"
    tbl_full = f"{TEST_DB}.{tbl_short}"

    @classmethod
    def setUpClass(cls):
        remote_exec(f"CREATE DATABASE IF NOT EXISTS {TEST_DB}")
        res = remote_exec(
            f"CREATE TABLE {cls.tbl_full} "
            f"(id UInt32, value Float64) ENGINE = MergeTree() ORDER BY id"
        )
        statuses = get_status(res)
        assert statuses and statuses[0] == "OK", f"Setup failed: {res.bytes()}"

    @classmethod
    def tearDownClass(cls):
        remote_exec(f"DROP TABLE IF EXISTS {cls.tbl_full}")

    def test_01_insert_via_query_param(self):
        """INSERT numeric-only data via remote(query=...) mode."""
        res = remote_exec(
            f"INSERT INTO {self.tbl_full} VALUES (1, 10.5), (2, 20.3), (3, 30.1)"
        )
        statuses = get_status(res)
        self.assertEqual(statuses[0], "OK", f"INSERT via query= failed: {res.bytes()}")

    def test_02_select_via_original_remote_returns_actual_data(self):
        """SELECT via original remote('host','db','table') returns actual row data."""
        res = remote_table_select(TEST_DB, self.tbl_short, "ORDER BY id")
        self.assertFalse(res.has_error(), f"SELECT error: {res.error_message()}")
        output = res.bytes().decode().strip()
        lines = [l for l in output.split("\n") if l]
        self.assertEqual(len(lines), 3, f"Expected 3 rows, got: {output}")
        self.assertIn("10.5", lines[0])
        self.assertIn("20.3", lines[1])
        self.assertIn("30.1", lines[2])

    def test_03_insert_via_original_remote(self):
        """INSERT via original remote('host','db','table') path still works."""
        remote_table_insert(TEST_DB, self.tbl_short, "(4, 40.0)")
        res = remote_table_select(TEST_DB, self.tbl_short, "WHERE id = 4")
        output = res.bytes().decode().strip()
        self.assertIn("40", output)

    def test_04_select_via_query_param_returns_status_not_data(self):
        """SELECT via remote(query='SELECT ...') returns execution status, NOT the query result rows."""
        res = remote_exec(f"SELECT count() FROM {self.tbl_full}")
        statuses = get_status(res)
        self.assertEqual(statuses[0], "OK")
        # The actual count value is NOT returned — only execution status
        raw = res.bytes().decode().strip()
        self.assertNotIn("4", raw.split("\t")[2] if "\t" in raw else "")

    def test_05_verify_final_row_count(self):
        """Verify total row count after all inserts via original remote() path."""
        res = remote_table_select(TEST_DB, self.tbl_short, "")
        output = res.bytes().decode().strip()
        lines = [l for l in output.split("\n") if l]
        self.assertEqual(len(lines), 4, f"Expected 4 rows, got {len(lines)}: {output}")


# ---------------------------------------------------------------------------
# Test: original remote() paths remain fully functional
# ---------------------------------------------------------------------------


@unittest.skipUnless(QUERY_PARAM_SUPPORTED, SKIP_MSG)
class TestOriginalRemoteUnchanged(unittest.TestCase):
    """Verify that the original remote() SELECT/INSERT paths work identically to before."""

    tbl_short = f"orig_{TEST_SUFFIX}"
    tbl_full = f"{TEST_DB}.{tbl_short}"

    @classmethod
    def setUpClass(cls):
        remote_exec(f"CREATE DATABASE IF NOT EXISTS {TEST_DB}")
        remote_exec(f"CREATE TABLE {cls.tbl_full} (val UInt64) ENGINE = Memory")

    @classmethod
    def tearDownClass(cls):
        remote_exec(f"DROP TABLE IF EXISTS {cls.tbl_full}")

    def test_original_select_from_system_one(self):
        """Original remote() can read system.one on the remote server."""
        sql = (
            f"SELECT dummy FROM remote('{REMOTE_HOST}', 'system', 'one', "
            f"'{REMOTE_USER}', '{REMOTE_PASSWORD}')"
        )
        res = chdb.query(sql, "TabSeparated")
        self.assertFalse(res.has_error(), f"Error: {res.error_message()}")
        self.assertEqual(res.bytes().decode().strip(), "0")

    def test_original_insert_and_select_roundtrip(self):
        """Original remote() INSERT → SELECT roundtrip with value verification."""
        remote_table_insert(TEST_DB, self.tbl_short, "(100), (200), (300)")

        res = remote_table_select(TEST_DB, self.tbl_short, "ORDER BY val")
        output = res.bytes().decode().strip()
        lines = output.split("\n")
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], "100")
        self.assertEqual(lines[1], "200")
        self.assertEqual(lines[2], "300")


if __name__ == "__main__":
    unittest.main()
