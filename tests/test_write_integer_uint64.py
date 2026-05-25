"""
Regression test for writeInteger bug: Python ints in (INT64_MAX, UINT64_MAX] were
serialized as UINT64_MAX (18446744073709551615) instead of their actual value.

Root cause: programs/local/PythonConversion.cpp `writeInteger` called
json_value.SetUint64(value) where `value` is the int64_t that overflowed (== -1),
instead of json_value.SetUint64(unsigned_value) which holds the correct uint64 result.

See: https://github.com/chdb-io/chdb-core/issues/46
"""

import unittest
import pandas as pd
import chdb

INT64_MAX = (1 << 63) - 1          # 9223372036854775807 — largest int64
INT64_MAX_PLUS_1 = 1 << 63         # 9223372036854775808 — first value to overflow int64
UINT64_NEAR_MAX = (1 << 64) - 2    # 18446744073709551614
UINT64_MAX = (1 << 64) - 1         # 18446744073709551615

# DataFrame with a dict-typed column whose values contain large Python ints.
# This exercises the writeInteger → SetUint64 path in PythonConversion.cpp.
df_large_int_dicts = pd.DataFrame(
    {
        "id": [1, 2, 3, 4],
        "info": [
            {"val": INT64_MAX},           # just fits in int64 — control row
            {"val": INT64_MAX_PLUS_1},    # first value that overflows int64
            {"val": UINT64_NEAR_MAX},     # UINT64_MAX - 1
            {"val": UINT64_MAX},          # UINT64_MAX — edge
        ],
    }
)


class TestWriteIntegerUint64(unittest.TestCase):
    """
    writeInteger must use unsigned_value (not value) when serialising Python ints
    in the range (INT64_MAX, UINT64_MAX] to JSON.
    """

    def _query_info_val(self, row_id):
        """Return the 'val' field from the JSON 'info' column for the given id."""
        res = chdb.query(
            f"SELECT CAST(info.val AS UInt64) AS v "
            f"FROM Python(df_large_int_dicts) WHERE id = {row_id}",
            "CSV",
        )
        self.assertFalse(res.has_error(), msg=f"query error: {res.error_message()}")
        return int(res.bytes().decode().strip())

    def test_int64_max_control(self):
        """INT64_MAX itself must round-trip correctly (sanity check)."""
        self.assertEqual(self._query_info_val(1), INT64_MAX)

    def test_int64_max_plus_1(self):
        """
        INT64_MAX + 1 = 2^63 must NOT be serialised as UINT64_MAX.
        Before the fix this returned 18446744073709551615 for every overflow value.
        """
        self.assertEqual(self._query_info_val(2), INT64_MAX_PLUS_1)

    def test_uint64_near_max(self):
        """UINT64_MAX - 1 must round-trip correctly."""
        self.assertEqual(self._query_info_val(3), UINT64_NEAR_MAX)

    def test_uint64_max(self):
        """UINT64_MAX itself must round-trip correctly."""
        self.assertEqual(self._query_info_val(4), UINT64_MAX)


if __name__ == "__main__":
    unittest.main()
