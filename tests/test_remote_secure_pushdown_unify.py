#!/usr/bin/env python3
"""Integration tests for the per-shard rewrite that unifies equivalent sibling
remote()/remoteSecure() calls into local-table references.

Before the fix in src/Storages/StorageDistributed.cpp, a query of the shape

    SELECT ... FROM remoteSecure(host, ..., a) JOIN remoteSecure(host, ..., b) ...

would push the *current* source as a local-table StorageDummy but leave the
sibling remote-table-function referring to the same cluster intact. The
remote server then re-resolved that hostname during nested DESC TABLE, which
fails with DNS_ERROR under one-way PrivateLink DNS visibility.

After the fix, the per-shard SQL the remote receives no longer contains
nested remote()/remoteSecure() calls to the *same* cluster.

The rewrite is identical for remote() and remoteSecure() — both produce a
StorageDistributed with `is_remote_function = true`. This test uses plain
remote() to avoid coupling the test fixture to TLS config (chDB's embedded
engine is a process-wide singleton; once initialized without an openSSL
client config, later per-query `config-file` options cannot reconfigure it).

Environment variables (test is skipped unless all required vars are set):

    CHDB_TEST_REMOTE_CH_HOST         - hostname or IP of a reachable ClickHouse
                                       server (e.g. "127.0.0.1")
    CHDB_TEST_REMOTE_CH_PORT_PLAIN   - plain native TCP port (e.g. "19000")
    CHDB_TEST_REMOTE_CH_USER         - username (default: "default")
    CHDB_TEST_REMOTE_CH_PASSWORD     - password (default: "")

For the structural assertion (`test_rewrite_removes_nested_remote_in_remote_query_log`)
the remote server must have system.query_log enabled. The same chDB instance
queries it back via remote() with no extra setup.

The remote is expected to already host `system.one` (always present on any
ClickHouse). No table setup is required.
"""
import os
import re
import time
import unittest
import uuid

import chdb


HOST = os.environ.get("CHDB_TEST_REMOTE_CH_HOST")
PORT_PLAIN = os.environ.get("CHDB_TEST_REMOTE_CH_PORT_PLAIN")
USER = os.environ.get("CHDB_TEST_REMOTE_CH_USER", "default")
PWD = os.environ.get("CHDB_TEST_REMOTE_CH_PASSWORD", "")


def _q(sql, fmt="CSV"):
    return chdb.query(sql, output_format=fmt)


def _remote_has_query_log(host_port):
    """Probe whether the remote has system.query_log usable from chDB."""
    try:
        r = _q(
            f"SELECT count() FROM remote('{host_port}', 'system', 'query_log', '{USER}', '{PWD}')",
            "CSV",
        )
        return True, r.bytes().decode().strip()
    except Exception as e:
        return False, str(e)


@unittest.skipUnless(
    HOST and PORT_PLAIN,
    "CHDB_TEST_REMOTE_CH_HOST / CHDB_TEST_REMOTE_CH_PORT_PLAIN not set; skipping remote integration",
)
class TestRemotePushdownUnify(unittest.TestCase):
    """Semantic + structural integration coverage for the equivalent-remote rewrite."""

    @classmethod
    def setUpClass(cls):
        cls.host_port = f"{HOST}:{PORT_PLAIN}"

    def _join_two_remote_to_system_one(self):
        return (
            f"SELECT count() "
            f"FROM remote('{self.host_port}', 'system', 'one', '{USER}', '{PWD}') a "
            f"JOIN remote('{self.host_port}', 'system', 'one', '{USER}', '{PWD}') b "
            f"USING (dummy)"
        )

    def test_single_remote_succeeds(self):
        sql = (
            f"SELECT count() "
            f"FROM remote('{self.host_port}', 'system', 'one', '{USER}', '{PWD}')"
        )
        out = _q(sql).bytes().decode().strip()
        self.assertEqual(out, "1", f"Expected count 1, got {out!r}")

    def test_two_equivalent_remote_join_returns_correct_count(self):
        out = _q(self._join_two_remote_to_system_one()).bytes().decode().strip()
        # system.one has exactly one row (dummy=0). Self-join on dummy: 1 row.
        self.assertEqual(out, "1", f"Expected count 1, got {out!r}")

    def test_view_workaround_unaffected(self):
        sql = (
            f"SELECT * FROM remote("
            f"'{self.host_port}', "
            f"view(SELECT count() AS n FROM system.one), "
            f"'{USER}', '{PWD}')"
        )
        out = _q(sql).bytes().decode().strip()
        self.assertEqual(out, "1", f"Expected view() result 1, got {out!r}")

    def test_rewrite_removes_nested_remote_in_remote_query_log(self):
        """Structural assertion. Fails before the fix; passes after.

        Issues a self-JOIN of two `remote(host, system, one, ...)`. The
        per-shard SQL chDB sends to the remote should contain a reference to
        `system.one` (local on the remote) rather than nested remote(host,
        ...) to the same cluster. We verify by reading back the remote's
        system.query_log with a unique marker literal that survives the
        per-shard rewrite.
        """
        has_log, info = _remote_has_query_log(self.host_port)
        if not has_log:
            self.skipTest(f"Remote does not expose system.query_log: {info}")

        marker = f"chdb-pushdown-marker-{uuid.uuid4().hex}"
        sql = (
            f"SELECT '{marker}' AS marker, count() "
            f"FROM remote('{self.host_port}', 'system', 'one', '{USER}', '{PWD}') a "
            f"JOIN remote('{self.host_port}', 'system', 'one', '{USER}', '{PWD}') b "
            f"USING (dummy)"
        )
        out = _q(sql).bytes().decode().strip()
        self.assertIn("1", out, f"Marker query failed; got {out!r}")

        # Poll system.query_log over remote() until the marker appears or we
        # give up after ~3 seconds.
        deadline = time.time() + 3.0
        captured_query = None
        while time.time() < deadline:
            log_sql = (
                f"SELECT query FROM remote("
                f"'{self.host_port}', 'system', 'query_log', '{USER}', '{PWD}') "
                f"WHERE type = 'QueryFinish' "
                f"  AND event_time > now() - INTERVAL 30 SECOND "
                f"  AND query LIKE '%{marker}%' "
                f"  AND query NOT LIKE '%query_log%' "
                f"FORMAT TabSeparatedRaw"
            )
            rows = _q(log_sql, "TabSeparatedRaw").bytes().decode().strip().splitlines()
            if rows:
                captured_query = "\n".join(rows)
                break
            time.sleep(0.5)

        self.assertIsNotNone(
            captured_query,
            f"Could not find marker '{marker}' in remote system.query_log",
        )

        # The rewrite must replace every sibling remote(<this cluster>, system, one, ...)
        # with a reference to `system.one` (local on the remote). After the
        # rewrite, the remote-received SQL must NOT contain a nested
        # `remote(<this cluster>, ...)`.
        host_pattern = re.escape(HOST)
        nested_remote_re = re.compile(
            rf"\bremote\(\s*'{host_pattern}:{PORT_PLAIN}'", re.IGNORECASE
        )
        match = nested_remote_re.search(captured_query)
        self.assertIsNone(
            match,
            f"Remote received unrewritten nested remote({HOST}:{PORT_PLAIN}, ...). "
            f"Captured query: {captured_query[:400]}",
        )

        # Sanity: per-shard SQL should reference `system.one` as a local table.
        self.assertRegex(
            captured_query,
            r"system\.?one|`system`\.`one`",
            f"Expected local system.one reference in per-shard SQL; got: {captured_query[:400]}",
        )


class TestRemotePushdownUnifyBasic(unittest.TestCase):
    """Self-contained tests that do not require an external ClickHouse server.

    These exercise the surrounding code paths (binary symbol export, chDB-side
    error handling for unreachable remotes) without depending on the lab
    fixture. They run by default as part of `make test`.
    """

    def test_chdb_binary_exports_clusters_have_identical_shard_addresses(self):
        """Sanity: the per-shard pushdown helper that the equivalent-remote
        rewrite relies on is present in the loaded chDB binary. This catches
        regressions where the StorageDistributed accessor/helper is silently
        dead-code-eliminated or the source file is excluded from the build.
        """
        import subprocess
        from chdb import _chdb

        chdb_so = _chdb.__file__
        result = subprocess.run(
            ["nm", chdb_so],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.skipTest(f"nm exited {result.returncode}: {result.stderr[:200]}")
        self.assertIn(
            "clustersHaveIdenticalShardAddresses",
            result.stdout,
            "StorageDistributed::clustersHaveIdenticalShardAddresses is missing "
            "from the compiled chDB binary; the rewrite cannot fire.",
        )

    def test_two_remote_calls_to_unreachable_host_yields_clean_netexception(self):
        """The rewrite path must not change failure semantics when neither remote
        is reachable. chDB must reject the query with a NetException-style error
        rather than crash. Uses 127.0.0.1:1 (unreachable port) so neither
        DNS nor the rewrite is exercised; this test guards against analyzer
        crashes adjacent to the visitor.
        """
        sql = (
            "SELECT count() "
            "FROM remote('127.0.0.1:1', 'system', 'one', 'default', '') a "
            "JOIN remote('127.0.0.1:1', 'system', 'one', 'default', '') b "
            "USING (dummy)"
        )
        with self.assertRaises(Exception) as ctx:
            chdb.query(sql)
        message = str(ctx.exception)
        self.assertTrue(
            any(token in message for token in (
                "All connection tries failed",
                "All attempts to get table structure failed",
                "NetException",
                "NETWORK_ERROR",
                "DNS_ERROR",
                "NO_REMOTE_SHARD_AVAILABLE",
            )),
            f"Expected a clean network/structure-fetch error; got: {message[:400]}",
        )


if __name__ == "__main__":
    unittest.main()
