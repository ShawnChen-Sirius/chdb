#!/usr/bin/env python3
"""Tests for parallel Arrow IPC encoding (output_format_arrow_parallel_encoding).

Validates that:
  * Parallel encoding produces output that decodes to the same pyarrow Table
    as serial encoding for diverse data types.
  * Row order is preserved across multiple chunks.
  * LowCardinality + low_cardinality_as_dictionary transparently falls back
    to serial encoding (the dictionary state is per-converter and would
    otherwise diverge across worker threads).
  * Both Arrow (file) and ArrowStream (stream) IPC formats are supported.
"""

import io
import unittest

import pyarrow as pa
import chdb


def _query_arrow(sql: str, parallel: bool, fmt: str = "Arrow", threads: int = 4) -> pa.Table:
    full = (
        f"{sql} SETTINGS max_threads = {threads}, max_block_size = 4096, "
        f"output_format_arrow_parallel_encoding = {1 if parallel else 0}"
    )
    data = chdb.query(full, fmt).bytes()
    buf = io.BytesIO(data)
    if fmt == "Arrow":
        return pa.ipc.open_file(buf).read_all()
    if fmt == "ArrowStream":
        return pa.ipc.open_stream(buf).read_all()
    raise ValueError(fmt)


class TestArrowParallelEncoding(unittest.TestCase):
    def _assert_parallel_matches_serial(self, sql: str, fmt: str = "Arrow", threads: int = 4):
        serial = _query_arrow(sql, parallel=False, fmt=fmt, threads=threads)
        parallel = _query_arrow(sql, parallel=True, fmt=fmt, threads=threads)
        self.assertEqual(serial.column_names, parallel.column_names)
        self.assertEqual(serial.num_rows, parallel.num_rows)
        # Strict equality across the entire table - this catches both data
        # corruption and reordering caused by parallel workers.
        self.assertTrue(
            serial.equals(parallel),
            msg=f"parallel Arrow output differs from serial for: {sql}",
        )
        return serial

    # --- Basic types --------------------------------------------------------

    def test_numeric_strings_match_serial(self):
        sql = (
            "SELECT number AS i, "
            "toFloat64(number) AS f, "
            "toString(number) AS s, "
            "toUInt32(number * 2) AS u "
            "FROM numbers(50000)"
        )
        tbl = self._assert_parallel_matches_serial(sql)
        self.assertEqual(tbl.num_rows, 50000)
        self.assertEqual(tbl.column_names, ["i", "f", "s", "u"])

    def test_nullable_columns_match_serial(self):
        sql = (
            "SELECT number AS k, "
            "if(number % 7 = 0, NULL, toString(number)) AS s, "
            "if(number % 5 = 0, NULL, toFloat64(number) / 3) AS f "
            "FROM numbers(20000)"
        )
        tbl = self._assert_parallel_matches_serial(sql)
        # Make sure nulls actually round-trip; otherwise the equality above
        # would still pass on tables with no nulls and silently weaken the test.
        self.assertGreater(tbl.column("s").null_count, 0)
        self.assertGreater(tbl.column("f").null_count, 0)

    def test_arrays_and_tuples_match_serial(self):
        sql = (
            "SELECT number AS k, "
            "range(toUInt32(number % 8)) AS arr, "
            "tuple(number, toString(number)) AS tup "
            "FROM numbers(10000)"
        )
        tbl = self._assert_parallel_matches_serial(sql)
        self.assertEqual(tbl.num_rows, 10000)
        # Verify nested types survived the round-trip in both engines.
        self.assertTrue(pa.types.is_list(tbl.schema.field("arr").type))

    # --- Multi-chunk ordering ----------------------------------------------

    def test_row_order_preserved_across_many_chunks(self):
        # max_block_size=4096 + 50_000 rows guarantees ~12 chunks delivered to
        # the format. Workers may finish out of order but the writer must
        # serialize batches in arrival order.
        sql = "SELECT number AS n FROM numbers(50000)"
        tbl = self._assert_parallel_matches_serial(sql)
        col = tbl.column("n").to_pylist()
        self.assertEqual(col, list(range(50000)))

    def test_arrow_stream_format_match_serial(self):
        sql = (
            "SELECT number AS i, toString(number) AS s "
            "FROM numbers(20000)"
        )
        self._assert_parallel_matches_serial(sql, fmt="ArrowStream")

    # --- LowCardinality fallback -------------------------------------------

    def test_low_cardinality_dictionary_falls_back_to_serial(self):
        # When LowCardinality is emitted as Arrow Dictionary, the converter's
        # dictionary_values map is per-instance and parallel encoding cannot
        # produce a coherent shared dictionary. We must auto fall back to
        # serial encoding and still produce the correct result.
        sql = (
            "SELECT toLowCardinality(concat('cat-', toString(number % 16))) AS c, "
            "number AS n "
            "FROM numbers(20000) "
            "SETTINGS output_format_arrow_low_cardinality_as_dictionary = 1"
        )
        # Note: the SETTINGS clause already lives inside the query, so we
        # bypass the helper that would append its own SETTINGS.
        def run(parallel: bool) -> pa.Table:
            full = sql + (
                f", max_threads = 4, max_block_size = 4096, "
                f"output_format_arrow_parallel_encoding = {1 if parallel else 0}"
            )
            data = chdb.query(full, "Arrow").bytes()
            return pa.ipc.open_file(io.BytesIO(data)).read_all()

        serial = run(parallel=False)
        parallel = run(parallel=True)

        self.assertEqual(serial.num_rows, 20000)
        self.assertTrue(
            pa.types.is_dictionary(serial.schema.field("c").type),
            "expected LowCardinality column to surface as Arrow Dictionary",
        )
        self.assertTrue(
            serial.equals(parallel),
            "parallel encoding must transparently fall back to serial for "
            "LowCardinality-as-Dictionary and produce identical bytes-decoded data",
        )

    def test_low_cardinality_without_dictionary_still_uses_parallel(self):
        # Default low_cardinality_as_dictionary = 0 strips LC at conversion
        # time, so parallel encoding stays enabled and must match serial.
        sql = (
            "SELECT toLowCardinality(concat('cat-', toString(number % 16))) AS c, "
            "number AS n "
            "FROM numbers(20000)"
        )
        self._assert_parallel_matches_serial(sql)

    # --- Edge cases ---------------------------------------------------------

    def test_empty_result_writes_valid_schema(self):
        sql = "SELECT number AS n FROM numbers(0)"
        tbl = self._assert_parallel_matches_serial(sql)
        self.assertEqual(tbl.num_rows, 0)
        self.assertEqual(tbl.column_names, ["n"])

    def test_single_thread_setting_uses_serial_path(self):
        # max_threads = 1 must short-circuit to the serial path (no thread
        # pool created) but still produce identical results.
        sql = "SELECT number AS n, toString(number) AS s FROM numbers(5000)"
        serial = _query_arrow(sql, parallel=False, threads=1)
        parallel = _query_arrow(sql, parallel=True, threads=1)
        self.assertTrue(serial.equals(parallel))


if __name__ == "__main__":
    unittest.main()
