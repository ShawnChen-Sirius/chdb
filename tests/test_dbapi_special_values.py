#!/usr/bin/env python3

"""Regression tests for chdb.dbapi value conversion of IEEE 754 specials and Decimal.

Covers the bugs reported in chdb-io/chdb#574 and chdb-io/chdb#575:

  * #575: Float NaN / +Inf / -Inf came back as None, indistinguishable from
    a real SQL NULL. Root cause: ClickHouse emits these as JSON ``null`` in
    JSONCompactEachRowWithNamesAndTypes when
    ``output_format_json_quote_denormals=0`` (the historic default).

  * #574: Decimal(P, S) with P > 18 returned a lossy float-stringified ``str``,
    e.g. ``'1.2345678901234569e+27'`` for a 38-digit value. Root cause:
    ``output_format_json_quote_decimals=0`` (the historic default) emits the
    value as an unquoted JSON number, which json.loads parses through double.

The fix enables both settings in ``chdb.state.sqlitelike.Cursor`` so the
JSON carries exact textual representations, and adds a Decimal conversion
branch (plus Nullable() stripping) in the cursor's row decoder.
"""

import datetime as _dt
import math
import unittest
from decimal import Decimal

from chdb import dbapi


class TestDBAPISpecialValues(unittest.TestCase):
    """Regression for chdb-io/chdb#574 and #575."""

    def setUp(self):
        self.conn = dbapi.connect()
        self.cur = self.conn.cursor()

    def tearDown(self):
        try:
            self.cur.close()
        finally:
            self.conn.close()

    # ---- Issue #575: Float NaN / +Inf / -Inf ----------------------------------

    def test_float64_nan_inf_round_trip(self):
        """Float64 NaN / +Inf / -Inf must come back as the matching Python floats."""
        self.cur.execute(
            "CREATE TABLE t575_f64 (x Float64) ENGINE=Memory"
        )
        self.cur.execute(
            "INSERT INTO t575_f64 VALUES (nan), (inf), (-inf), (1.5), (0.0)"
        )
        self.cur.execute(
            "SELECT x FROM t575_f64 ORDER BY isNaN(x) DESC, x"
        )
        cells = [r[0] for r in self.cur.fetchall()]
        self.assertEqual(len(cells), 5)
        self.assertTrue(math.isnan(cells[0]), f"first row must be NaN, got {cells[0]!r}")
        self.assertEqual(cells[1], float("-inf"))
        self.assertEqual(cells[2], 0.0)
        self.assertEqual(cells[3], 1.5)
        self.assertEqual(cells[4], float("inf"))
        for c in cells:
            self.assertIsInstance(c, float)

    def test_float32_nan_inf_round_trip(self):
        """Float32 NaN / +Inf / -Inf must come back as floats too."""
        self.cur.execute(
            "CREATE TABLE t575_f32 (x Float32) ENGINE=Memory"
        )
        self.cur.execute(
            "INSERT INTO t575_f32 VALUES (nan), (inf), (-inf), (1.5)"
        )
        self.cur.execute(
            "SELECT x FROM t575_f32 ORDER BY isNaN(x) DESC, x"
        )
        cells = [r[0] for r in self.cur.fetchall()]
        self.assertEqual(len(cells), 4)
        self.assertTrue(math.isnan(cells[0]))
        self.assertEqual(cells[1], float("-inf"))
        self.assertEqual(cells[2], 1.5)
        self.assertEqual(cells[3], float("inf"))

    def test_nan_distinguishable_from_null(self):
        """The whole point of #575: NaN and SQL NULL must not collapse together."""
        self.cur.execute(
            "SELECT toFloat64('nan') AS f, CAST(NULL AS Nullable(Float64)) AS n"
        )
        row = self.cur.fetchone()
        self.assertTrue(math.isnan(row[0]))
        self.assertIsNone(row[1])

    def test_nullable_float_holds_nan_and_null(self):
        """A Nullable(Float64) column can hold both real NaN values and SQL NULLs."""
        self.cur.execute(
            "CREATE TABLE t575_nf (x Nullable(Float64)) ENGINE=Memory"
        )
        self.cur.execute(
            "INSERT INTO t575_nf VALUES (nan), (NULL), (1.5), (NULL), (-inf)"
        )
        self.cur.execute(
            "SELECT x FROM t575_nf ORDER BY x NULLS FIRST"
        )
        cells = [r[0] for r in self.cur.fetchall()]
        # NULLs sort first, then -inf, 1.5, NaN (NaN sorts last in ClickHouse).
        self.assertEqual(len([c for c in cells if c is None]), 2)
        floats = [c for c in cells if c is not None]
        self.assertIn(float("-inf"), floats)
        self.assertIn(1.5, floats)
        self.assertTrue(any(math.isnan(c) for c in floats))

    # ---- Issue #574: Decimal(P, S) with P > 18 --------------------------------

    def test_decimal_high_precision_exact(self):
        """A 38-digit Decimal must round-trip without going through double."""
        exact = "1234567890123456789012345678.0123456789"
        self.cur.execute(
            "CREATE TABLE t574_d (x Decimal(38, 10)) ENGINE=Memory"
        )
        self.cur.execute(
            "INSERT INTO t574_d VALUES (%s)" % exact
        )
        self.cur.execute("SELECT x FROM t574_d")
        cell = self.cur.fetchone()[0]
        self.assertIsInstance(cell, Decimal,
                              "Decimal column should return decimal.Decimal, "
                              "not %s (raw value %r)" % (type(cell).__name__, cell))
        self.assertEqual(cell, Decimal(exact))
        self.assertEqual(str(cell), exact)

    def test_decimal_small_precision_still_exact(self):
        """A Decimal(P<=18) value (the previously-working case) must remain exact."""
        self.cur.execute(
            "CREATE TABLE t574_d2 (x Decimal(18, 5)) ENGINE=Memory"
        )
        self.cur.execute(
            "INSERT INTO t574_d2 VALUES (1234567890.12345)"
        )
        self.cur.execute("SELECT x FROM t574_d2")
        cell = self.cur.fetchone()[0]
        self.assertIsInstance(cell, Decimal)
        self.assertEqual(cell, Decimal("1234567890.12345"))

    def test_nullable_decimal(self):
        """Nullable(Decimal(P, S)) must yield Decimal for values and None for NULL."""
        exact = "1234567890123456789012345678.0123456789"
        self.cur.execute(
            "SELECT CAST(%s AS Nullable(Decimal(38, 10))) AS x, "
            "CAST(NULL AS Nullable(Decimal(18, 2))) AS y" % repr(exact)
        )
        row = self.cur.fetchone()
        self.assertIsInstance(row[0], Decimal)
        self.assertEqual(str(row[0]), exact)
        self.assertIsNone(row[1])

    def test_decimal_negative(self):
        """Negative high-precision Decimal must keep the sign and all digits."""
        exact = "-9876543210987654321098765432.1234567890"
        self.cur.execute(
            "CREATE TABLE t574_neg (x Decimal(38, 10)) ENGINE=Memory"
        )
        self.cur.execute(
            "INSERT INTO t574_neg VALUES (%s)" % exact
        )
        self.cur.execute("SELECT x FROM t574_neg")
        cell = self.cur.fetchone()[0]
        self.assertIsInstance(cell, Decimal)
        self.assertEqual(cell, Decimal(exact))

    # ---- Pre-existing types still convert correctly ---------------------------

    def test_existing_types_unchanged(self):
        """The SET-based fix must not regress Int / String / Bool / Date / DateTime."""
        self.cur.execute(
            "SELECT toInt32(42), toString('hello'), toBool(1), "
            "toDate('2025-01-15'), toDateTime('2025-01-15 10:30:00')"
        )
        row = self.cur.fetchone()
        self.assertEqual(row[0], 42)
        self.assertIsInstance(row[0], int)
        self.assertEqual(row[1], "hello")
        self.assertIsInstance(row[1], str)
        self.assertEqual(row[2], True)
        self.assertIsInstance(row[2], bool)
        self.assertEqual(row[3].isoformat(), "2025-01-15")
        self.assertEqual(row[4].isoformat(sep=" "), "2025-01-15 10:30:00")

    # ---- Nullable(Bool/String/Date/DateTime) wrapper stripping ---------------
    # Regression for the [P2] review comment on PR #57: inner_type was
    # computed but the Bool / String / FixedString / DateTime / Date branches
    # still tested type_info directly, so Nullable(Bool), Nullable(Date) and
    # Nullable(DateTime) fell through to the trailing `str(val)` else-branch.

    def test_nullable_bool_returns_bool(self):
        """Nullable(Bool) must yield Python bool (and None for SQL NULL)."""
        self.cur.execute(
            "SELECT CAST(1 AS Nullable(Bool)) AS t, "
            "CAST(0 AS Nullable(Bool)) AS f, "
            "CAST(NULL AS Nullable(Bool)) AS n"
        )
        row = self.cur.fetchone()
        self.assertIsInstance(row[0], bool)
        self.assertEqual(row[0], True)
        self.assertIsInstance(row[1], bool)
        self.assertEqual(row[1], False)
        self.assertIsNone(row[2])

    def test_nullable_string_returns_str(self):
        """Nullable(String) must yield Python str (and None for SQL NULL)."""
        self.cur.execute(
            "SELECT CAST('hello' AS Nullable(String)) AS s, "
            "CAST(NULL AS Nullable(String)) AS n"
        )
        row = self.cur.fetchone()
        self.assertIsInstance(row[0], str)
        self.assertEqual(row[0], "hello")
        self.assertIsNone(row[1])

    def test_nullable_date_returns_date(self):
        """Nullable(Date) must yield datetime.date (and None for SQL NULL)."""
        self.cur.execute(
            "SELECT CAST('2025-01-15' AS Nullable(Date)) AS d, "
            "CAST(NULL AS Nullable(Date)) AS n"
        )
        row = self.cur.fetchone()
        self.assertIsInstance(row[0], _dt.date)
        # datetime is a subclass of date — exclude it to be precise.
        self.assertNotIsInstance(row[0], _dt.datetime)
        self.assertEqual(row[0].isoformat(), "2025-01-15")
        self.assertIsNone(row[1])

    def test_nullable_datetime_returns_datetime(self):
        """Nullable(DateTime) must yield datetime.datetime (and None for SQL NULL)."""
        self.cur.execute(
            "SELECT CAST('2025-01-15 10:30:00' AS Nullable(DateTime)) AS dt, "
            "CAST(NULL AS Nullable(DateTime)) AS n"
        )
        row = self.cur.fetchone()
        self.assertIsInstance(row[0], _dt.datetime)
        self.assertEqual(row[0].isoformat(sep=" "), "2025-01-15 10:30:00")
        self.assertIsNone(row[1])

    def test_nullable_all_three_types_combined(self):
        """Exact repro from the [P2] review comment on PR #57."""
        self.cur.execute(
            "SELECT "
            "CAST('2025-01-15' AS Nullable(Date)) AS d, "
            "CAST('2025-01-15 10:30:00' AS Nullable(DateTime)) AS dt, "
            "CAST(1 AS Nullable(Bool)) AS b"
        )
        row = self.cur.fetchone()
        self.assertIsInstance(row[0], _dt.date)
        self.assertNotIsInstance(row[0], _dt.datetime)
        self.assertIsInstance(row[1], _dt.datetime)
        self.assertIsInstance(row[2], bool)


if __name__ == "__main__":
    unittest.main()
