#!python3

import os
import unittest
import chdb


# chdb-core-lite disables ENABLE_BASE64; in that build base64Encode/Decode are
# absent from FunctionFactory and any call raises Code 46. Tests stay valid:
# they assert the clean "function not found" failure instead of the result.
_LITE = os.environ.get("CHDB_LITE") == "1"


class TestBase64Functions(unittest.TestCase):
    """Test ClickHouse base64Encode and base64Decode functions."""

    def _expect_lite_missing(self, sql):
        with self.assertRaises(Exception) as ctx:
            chdb.query(sql, "CSV")
        self.assertIn("Code: 46", str(ctx.exception))

    def test_base64_encode(self):
        if _LITE:
            self._expect_lite_missing("SELECT base64Encode('clickhouse')")
            return
        res = chdb.query("SELECT base64Encode('clickhouse')", "CSV")
        self.assertEqual(res.bytes().strip(), b'"Y2xpY2tob3VzZQ=="')

    def test_base64_decode(self):
        if _LITE:
            self._expect_lite_missing("SELECT base64Decode('Y2xpY2tob3VzZQ==')")
            return
        res = chdb.query("SELECT base64Decode('Y2xpY2tob3VzZQ==')", "CSV")
        self.assertEqual(res.bytes().strip(), b'"clickhouse"')

    def test_base64_roundtrip(self):
        if _LITE:
            self._expect_lite_missing("SELECT base64Decode(base64Encode('hello world'))")
            return
        res = chdb.query("SELECT base64Decode(base64Encode('hello world'))", "CSV")
        self.assertEqual(res.bytes().strip(), b'"hello world"')


if __name__ == "__main__":
    unittest.main()
