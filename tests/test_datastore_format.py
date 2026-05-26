#!python3

import shutil
import sys
import unittest

import chdb
from chdb import session
from chdb.state import connect


def _datastore_cls():
    from chdb.datastore import DataStore
    return DataStore


class TestDataStoreOutputFormat(unittest.TestCase):
    """Verify output_format="DataStore" across query / Connection / Session / send_query."""

    def test_query_returns_datastore(self):
        DataStore = _datastore_cls()
        res = chdb.query("SELECT number AS n FROM numbers(3)", "DataStore")
        self.assertIsInstance(res, DataStore)
        self.assertEqual(list(res.columns), ["n"])
        self.assertEqual(len(res), 3)
        self.assertEqual(list(res["n"]), [0, 1, 2])

    def test_query_case_insensitive(self):
        DataStore = _datastore_cls()
        for fmt in ("DataStore", "datastore", "DATASTORE", "dataStore"):
            res = chdb.query("SELECT 1 AS x", fmt)
            self.assertIsInstance(res, DataStore, msg=f"fmt={fmt}")
            self.assertEqual(list(res.columns), ["x"])

    def test_connection_query_returns_datastore(self):
        DataStore = _datastore_cls()
        with connect(":memory:") as conn:
            res = conn.query("SELECT 1 AS a, 2 AS b", "DataStore")
            self.assertIsInstance(res, DataStore)
            self.assertEqual(list(res.columns), ["a", "b"])
            self.assertEqual(len(res), 1)

    def test_session_query_returns_datastore(self):
        DataStore = _datastore_cls()
        test_dir = ".tmp_test_datastore_session"
        shutil.rmtree(test_dir, ignore_errors=True)
        try:
            with session.Session(test_dir) as sess:
                sess.query("CREATE TABLE t (id Int32, name String) ENGINE = MergeTree ORDER BY id")
                sess.query("INSERT INTO t VALUES (1, 'a'), (2, 'b'), (3, 'c')")
                res = sess.query("SELECT id, name FROM t ORDER BY id", "DataStore")
                self.assertIsInstance(res, DataStore)
                self.assertEqual(list(res.columns), ["id", "name"])
                self.assertEqual(len(res), 3)
                self.assertEqual(list(res["id"]), [1, 2, 3])
                self.assertEqual(list(res["name"]), ["a", "b", "c"])
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_send_query_streams_datastore_chunks(self):
        DataStore = _datastore_cls()
        with session.Session() as sess:
            stream = sess.send_query(
                "SELECT number AS n FROM numbers(50)", "DataStore"
            )
            total_rows = 0
            chunks = 0
            seen = []
            for chunk in stream:
                self.assertIsInstance(chunk, DataStore)
                self.assertEqual(list(chunk.columns), ["n"])
                chunks += 1
                total_rows += len(chunk)
                seen.extend(list(chunk["n"]))
            self.assertGreaterEqual(chunks, 1)
            self.assertEqual(total_rows, 50)
            self.assertEqual(seen, list(range(50)))

    def test_connection_send_query_streams_datastore_chunks(self):
        DataStore = _datastore_cls()
        with connect(":memory:") as conn:
            stream = conn.send_query(
                "SELECT number AS n FROM numbers(10)", "DataStore"
            )
            collected = []
            for chunk in stream:
                self.assertIsInstance(chunk, DataStore)
                self.assertEqual(list(chunk.columns), ["n"])
                collected.extend(list(chunk["n"]))
            self.assertEqual(collected, list(range(10)))

    def test_missing_chdb_package_raises_import_error(self):
        """If chdb.datastore is unavailable, DataStore output must raise ImportError."""
        # Simulate chdb-ds not being installed by blocking the import path.
        saved_modules = {
            name: sys.modules[name]
            for name in list(sys.modules)
            if name == "chdb.datastore" or name.startswith("datastore")
        }
        for name in saved_modules:
            del sys.modules[name]

        class _Blocker:
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "chdb.datastore" or fullname == "datastore" or fullname.startswith("datastore."):
                    raise ImportError(f"blocked for test: {fullname}")
                return None

        blocker = _Blocker()
        sys.meta_path.insert(0, blocker)
        try:
            with self.assertRaises(ImportError) as ctx:
                chdb.query("SELECT 1", "DataStore")
            self.assertIn("DataStore", str(ctx.exception))
            self.assertIn("chdb", str(ctx.exception))
        finally:
            sys.meta_path.remove(blocker)
            sys.modules.update(saved_modules)


if __name__ == "__main__":
    unittest.main()
