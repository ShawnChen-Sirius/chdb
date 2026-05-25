#!/usr/bin/env python3
"""
Benchmark: pandas string column ingestion via Python(df).

Measures the zero-copy fast path for object-dtype string columns.
Run separately from unit tests:
    python tests/benchmarks/bench_string_ingestion.py
"""

import time
import numpy as np
import pandas as pd
import chdb

N_ROWS = 5000_000
WARMUP = 2
REPEATS = 5


def make_df(n, rng):
    return pd.DataFrame({
        "s": pd.array(
            [f"{'x' * 80}_{i}_{rng.integers(0, 100000)}" for i in range(n)],
            dtype="object",
        ),
    })


def bench(df, sql, warmup=WARMUP, repeats=REPEATS):
    for _ in range(warmup):
        chdb.query(sql, "CSV")
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        chdb.query(sql, "CSV")
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
    return times


def main():
    print(f"chdb={chdb.__version__}  pandas={pd.__version__}  numpy={np.__version__}")
    print(f"rows={N_ROWS:,}  warmup={WARMUP}  repeats={REPEATS}")
    print()

    rng = np.random.default_rng(42)
    df = make_df(N_ROWS, rng)
    sql = "SELECT count() FROM Python(df)"

    times = bench(df, sql)
    best = min(times)
    median = sorted(times)[len(times) // 2]
    worst = max(times)

    print(f"best={best:.3f}s  median={median:.3f}s  worst={worst:.3f}s")


if __name__ == "__main__":
    main()
