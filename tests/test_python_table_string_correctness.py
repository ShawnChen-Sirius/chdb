#!/usr/bin/env python3
"""Regression tests for the Python(df) string input path.

Covers two bugs fixed in programs/local/:

1. Hang/segfault on string columns containing missing values:
   PandasScan's GIL-free scan thread called isNone(), whose import cache
   lazily resolved pandas.NaT via Python C-API without a thread state
   (crash in _PyObject_Malloc on CPython 3.12+, then a deadlock in the
   fatal signal handler). Fixed by pre-resolving pandas.NaT/NA under the
   GIL in StoragePython::prepareColumnCache. On the buggy build these
   tests hang forever when run first in the process.

2. Trailing NUL byte on every non-ASCII string value:
   ConvertPyUnicodeToUtf8 still appended the old ColumnString zero
   terminator and counted it in offsets, so any non-ASCII value entering
   chdb through the PyUnicode path was stored as value + '\\0' (equality
   with literals never matched, length()/hex()/hashes were off by one).

Both must pass on pandas 2.x (object-dtype strings) and pandas 3.x
(Arrow-backed `str` dtype), which exercise different scan paths:
object dtype -> per-row PyUnicode conversion; str dtype -> Arrow buffers.
"""

import unittest

import pandas as pd

import chdb


PANDAS_MAJOR = int(pd.__version__.split(".")[0])

# 1-byte (Latin-1), 2-byte (BMP) and 4-byte (non-BMP) PyUnicode kinds,
# to cover every branch of the PyUnicode -> UTF-8 conversion.
CAFE = "café"  # é: kind-1, utf8 C3A9
CJK = "中文"  # 中文: kind-2, utf8 E4B8ADE69687
CYR = "привет"  # привет: kind-2
ROCKET = "\U0001f680"  # 🚀: kind-4, utf8 F09F9A80


def fresh(s):
    """Return a newly constructed string object equal to `s`.

    Literal/interned strings can already carry a cached UTF-8 representation,
    in which case the scan takes the direct-insert fast path and would mask
    bugs in the manual PyUnicode -> UTF-8 conversion. A string built at
    runtime has no cached UTF-8, so it deterministically exercises
    ConvertPyUnicodeToUtf8.
    """
    return "".join([s[i] for i in range(len(s))])


def q(sql):
    return str(chdb.query(sql, "CSV")).strip()


class TestNonAsciiStringValues(unittest.TestCase):
    """Bug 2: values must be stored byte-exact, without a trailing NUL."""

    def _check_byte_exact(self, df):  # noqa: F841 -- df referenced by Python(df)
        rows = q(
            "SELECT hex(s), length(s) FROM Python(df) ORDER BY s"
        ).splitlines()
        expected = sorted([CAFE, CJK, CYR, ROCKET, "ascii"])
        self.assertEqual(len(rows), len(expected))
        for row, value in zip(rows, expected):
            utf8 = value.encode("utf-8")
            self.assertEqual(row, f'"{utf8.hex().upper()}",{len(utf8)}')

        # equality with a literal must match (failed when a NUL was appended)
        for value in (CAFE, CJK, CYR, ROCKET):
            self.assertEqual(
                q(f"SELECT COUNT(*) FROM Python(df) WHERE s = '{value}'"),
                "1",
                f"equality failed for {value!r}",
            )

        # group keys must round-trip intact
        self.assertEqual(
            q(
                "SELECT s, COUNT(*) FROM Python(df) "
                f"WHERE s = '{CJK}' GROUP BY s"
            ),
            f'"{CJK}",1',
        )

    def test_object_dtype_pyunicode_path(self):
        """object dtype: per-row PyUnicode conversion (both pandas 2.x/3.x)."""
        values = [fresh(v) for v in (CAFE, CJK, CYR, ROCKET, "ascii")]
        df = pd.DataFrame({"s": pd.Series(values, dtype=object)})
        self.assertEqual(str(df["s"].dtype), "object")
        self._check_byte_exact(df)

    def test_default_string_dtype_path(self):
        """astype(str): object dtype on pandas 2.x, Arrow `str` dtype on 3.x."""
        df = pd.DataFrame({"s": [fresh(v) for v in (CAFE, CJK, CYR, ROCKET, "ascii")]})
        df["s"] = df["s"].astype(str)
        self._check_byte_exact(df)

    @unittest.skipIf(PANDAS_MAJOR >= 3, "string[pyarrow] folded into str on 3.x")
    def test_pyarrow_backed_string_dtype_pandas2(self):
        """pandas 2.x string[pyarrow]: exercises the Arrow buffer scan path."""
        df = pd.DataFrame(
            {
                "s": pd.array(
                    [fresh(v) for v in (CAFE, CJK, CYR, ROCKET, "ascii")],
                    dtype="string[pyarrow]",
                )
            }
        )
        self._check_byte_exact(df)


class TestStringColumnWithMissingValues(unittest.TestCase):
    """Bug 1: missing values in string columns must not hang the scan.

    On the unfixed build, the first query in the process whose scan hits a
    nan/NaT row crashes a GIL-free thread inside the lazy pandas.NaT import
    and never returns (observed on CPython 3.12+).
    """

    def _check_nulls(self, df, n_total, n_valid):  # noqa: F841
        self.assertEqual(
            q("SELECT COUNT(*), COUNT(s) FROM Python(df)"),
            f"{n_total},{n_valid}",
        )
        self.assertEqual(
            q("SELECT COUNT(*) FROM Python(df) WHERE s IS NULL"),
            str(n_total - n_valid),
        )
        self.assertEqual(q("SELECT MAX(s) FROM Python(df)"), f'"{CJK}"')

    def test_object_dtype_with_nan(self):
        """float('nan') in an object column: the exact lazy-NaT trigger."""
        df = pd.DataFrame(
            {"s": pd.Series(["x", float("nan"), CJK], dtype=object)}
        )
        self._check_nulls(df, 3, 2)

    def test_object_dtype_with_pd_nat(self):
        """pd.NaT in an object column: hits the cached-NaT pointer compare."""
        df = pd.DataFrame({"s": pd.Series(["x", pd.NaT, CJK], dtype=object)})
        self._check_nulls(df, 3, 2)

    def test_object_dtype_with_none(self):
        df = pd.DataFrame({"s": pd.Series(["x", None, CJK], dtype=object)})
        self._check_nulls(df, 3, 2)

    def test_default_string_dtype_with_none(self):
        """None through astype-free default dtype (str on 3.x, object on 2.x)."""
        df = pd.DataFrame({"s": ["x", None, CJK]})
        self._check_nulls(df, 3, 2)

    @unittest.skipIf(PANDAS_MAJOR >= 3, "string[pyarrow] folded into str on 3.x")
    def test_pyarrow_backed_string_dtype_with_none_pandas2(self):
        df = pd.DataFrame(
            {"s": pd.array(["x", None, CJK], dtype="string[pyarrow]")}
        )
        self._check_nulls(df, 3, 2)

    @unittest.skipIf(PANDAS_MAJOR < 3, "default str dtype needs pandas >= 3")
    def test_str_dtype_nulls_and_values_pandas3(self):
        """pandas 3.x `str` dtype with nulls: Arrow validity bitmap path."""
        df = pd.DataFrame(
            {"s": pd.array(["x", None, CJK, None, CYR], dtype="str")}
        )
        self.assertEqual(str(df["s"].dtype), "str")
        self.assertEqual(
            q("SELECT COUNT(*), COUNT(s) FROM Python(df)"), "5,3"
        )
        self.assertEqual(
            q("SELECT hex(s) FROM Python(df) WHERE s IS NOT NULL ORDER BY s"),
            "\n".join(
                f'"{v.encode("utf-8").hex().upper()}"'
                for v in sorted(["x", CJK, CYR])
            ),
        )


if __name__ == "__main__":
    unittest.main()
