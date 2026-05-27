#!/usr/bin/env python3

import os
import unittest
import chdb
from chdb.session import Session


# chdb-core-lite disables ENABLE_SQIDS; sqidEncode/sqidDecode are absent from
# FunctionFactory and any call raises Code 46.
_LITE = os.environ.get("CHDB_LITE") == "1"


class TestSqidFunctions(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def _expect_lite_missing(self, sql):
        with self.assertRaises(Exception) as ctx:
            self.session.query(sql, "CSV")
        self.assertIn("Code: 46", str(ctx.exception))

    def test_sqid_encode_single(self):
        if _LITE:
            self._expect_lite_missing("SELECT sqidEncode(1)")
            return
        ret = self.session.query("SELECT sqidEncode(1)", "CSV")
        result = str(ret).strip().strip('"')
        self.assertTrue(len(result) > 0)

    def test_sqid_encode_multiple(self):
        if _LITE:
            self._expect_lite_missing("SELECT sqidEncode(1, 2, 3)")
            return
        ret = self.session.query("SELECT sqidEncode(1, 2, 3)", "CSV")
        result = str(ret).strip().strip('"')
        self.assertTrue(len(result) > 0)

    def test_sqid_roundtrip(self):
        if _LITE:
            self._expect_lite_missing("SELECT sqidDecode(sqidEncode(1, 2, 3))")
            return
        ret = self.session.query("SELECT sqidDecode(sqidEncode(1, 2, 3))", "CSV")
        self.assertEqual(str(ret).strip(), '"[1,2,3]"')

    def test_sqid_roundtrip_single(self):
        if _LITE:
            self._expect_lite_missing("SELECT sqidDecode(sqidEncode(42))")
            return
        ret = self.session.query("SELECT sqidDecode(sqidEncode(42))", "CSV")
        self.assertEqual(str(ret).strip(), '"[42]"')

    def test_sqid_encode_deterministic(self):
        if _LITE:
            self._expect_lite_missing("SELECT sqidEncode(100, 200)")
            return
        ret1 = self.session.query("SELECT sqidEncode(100, 200)", "CSV")
        ret2 = self.session.query("SELECT sqidEncode(100, 200)", "CSV")
        self.assertEqual(str(ret1).strip(), str(ret2).strip())

    def test_sqid_decode_empty_string(self):
        if _LITE:
            self._expect_lite_missing("SELECT sqidDecode('')")
            return
        ret = self.session.query("SELECT sqidDecode('')", "CSV")
        self.assertEqual(str(ret).strip(), '"[]"')


if __name__ == "__main__":
    unittest.main()
