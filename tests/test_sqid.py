#!/usr/bin/env python3

import unittest
import chdb
from chdb.session import Session


class TestSqidFunctions(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_sqid_encode_single(self):
        ret = self.session.query("SELECT sqidEncode(1)", "CSV")
        result = str(ret).strip().strip('"')
        self.assertTrue(len(result) > 0)

    def test_sqid_encode_multiple(self):
        ret = self.session.query("SELECT sqidEncode(1, 2, 3)", "CSV")
        result = str(ret).strip().strip('"')
        self.assertTrue(len(result) > 0)

    def test_sqid_roundtrip(self):
        ret = self.session.query("SELECT sqidDecode(sqidEncode(1, 2, 3))", "CSV")
        self.assertEqual(str(ret).strip(), '"[1,2,3]"')

    def test_sqid_roundtrip_single(self):
        ret = self.session.query("SELECT sqidDecode(sqidEncode(42))", "CSV")
        self.assertEqual(str(ret).strip(), '"[42]"')

    def test_sqid_encode_deterministic(self):
        ret1 = self.session.query("SELECT sqidEncode(100, 200)", "CSV")
        ret2 = self.session.query("SELECT sqidEncode(100, 200)", "CSV")
        self.assertEqual(str(ret1).strip(), str(ret2).strip())

    def test_sqid_decode_empty_string(self):
        ret = self.session.query("SELECT sqidDecode('')", "CSV")
        self.assertEqual(str(ret).strip(), '"[]"')


if __name__ == "__main__":
    unittest.main()
