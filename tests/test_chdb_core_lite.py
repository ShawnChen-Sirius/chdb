#!python3
"""Tests specific to the chdb-core-lite (slim) variant.

These run only when CHDB_LITE=1 is set in the environment. They verify that
functions trimmed from the lite build fail with a clean "function not found"
error (Code: 46 or 63) rather than crashing, and that core functionality is
preserved.

For the full chdb-core wheel, this whole class is skipped at setUpClass.
"""

import os
import unittest
import chdb


class TestChDBCoreLite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("CHDB_LITE") != "1":
            raise unittest.SkipTest("Lite-only tests; set CHDB_LITE=1 to run")

    def _assert_not_found(self, sql):
        with self.assertRaises(Exception) as ctx:
            chdb.query(sql)
        msg = str(ctx.exception)
        self.assertTrue(
            "Code: 46" in msg or "Code: 63" in msg,
            f"expected UNKNOWN_FUNCTION/UNKNOWN_AGGREGATE_FUNCTION, got: {msg[:200]}",
        )

    def test_trimmed_scalar_functions_throw_cleanly(self):
        for sql in [
            "SELECT murmurHash3_64('x')",          # FunctionsHashingMurmur
            "SELECT ngramSimHash('hello world')",  # FunctionsStringHash (LSH)
            "SELECT bitmapBuild([1, 2, 3])",       # FunctionsBitmap
            "SELECT bitShiftLeft(1, 2)",           # bit-shift trim
            "SELECT gcd(12, 8)",                   # math trim
            "SELECT FQDN()",                       # niche fn
            "SELECT filesystemAvailable()",        # niche fn
        ]:
            with self.subTest(sql=sql):
                self._assert_not_found(sql)

    def test_trimmed_array_and_map_functions_throw_cleanly(self):
        for sql in [
            "SELECT arrayCumSum([1, 2, 3])",
            "SELECT arrayFold((x, acc) -> acc + x, [1, 2, 3], 0)",
            "SELECT arrayShuffle([1, 2, 3])",
            "SELECT mapAdd(map(1, 1), map(1, 2))",
            "SELECT indexOfAssumeSorted([1, 2, 3], 2)",
        ]:
            with self.subTest(sql=sql):
                self._assert_not_found(sql)

    def test_trimmed_aggregates_throw_cleanly(self):
        for sql in [
            "SELECT groupBitOr(toUInt32(number)) FROM numbers(10)",
            "SELECT sumMap(['a'], [1])",
            "SELECT groupArrayIntersect([1, 2, 3])",
            "SELECT skewSamp(number) FROM numbers(100)",
            "SELECT groupUniqArray(number % 5) FROM numbers(100)",
        ]:
            with self.subTest(sql=sql):
                self._assert_not_found(sql)


if __name__ == "__main__":
    unittest.main()
