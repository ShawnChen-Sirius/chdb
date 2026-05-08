#!/usr/bin/env python3

import unittest
import chdb


class TestTempViewCrash(unittest.TestCase):
    """Regression test: creating a temporary view/table then closing the connection should not crash."""

    def test_temp_view_close_without_select(self):
        conn = chdb.connect()
        conn.query("CREATE TEMPORARY VIEW myview AS (SELECT 1)")
        conn.close()

    def test_temp_view_close_with_select(self):
        conn = chdb.connect()
        conn.query("CREATE TEMPORARY VIEW myview AS (SELECT 1 AS val)")
        result = conn.query("SELECT * FROM myview", "CSV")
        self.assertEqual(str(result).strip(), "1")
        conn.close()

    def test_temp_table_close_without_select(self):
        conn = chdb.connect()
        conn.query("CREATE TEMPORARY TABLE tmp (x UInt8) ENGINE = Memory")
        conn.query("INSERT INTO tmp VALUES (1), (2)")
        conn.close()

    def test_temp_table_close_with_select(self):
        conn = chdb.connect()
        conn.query("CREATE TEMPORARY TABLE tmp (x UInt8) ENGINE = Memory")
        conn.query("INSERT INTO tmp VALUES (1), (2)")
        result = conn.query("SELECT sum(x) FROM tmp", "CSV")
        self.assertEqual(str(result).strip(), "3")
        conn.close()


if __name__ == "__main__":
    unittest.main()
