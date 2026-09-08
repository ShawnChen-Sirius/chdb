"""The statement WAL — the incremental tier between full checkpoints.

A segment is UTF-8 JSONL, one `{"sql": ...}` object per line, terminated by a
newline (§4.4). `flush()` publishes the buffered statements as one immutable
segment and records it in the manifest, so the recovery point is the flush
interval rather than the (much longer) checkpoint interval. On open, the base
is restored and then every segment is replayed in manifest order.

**Replay re-executes the SQL, so only log statements that mean the same thing
twice.** V1 promises to replay the original statements in order; it does not
promise a non-deterministic statement produces the rows it produced the first
time (§4.4), and the caller owns that distinction:

  - DO log literal values: `INSERT INTO beliefs VALUES ('k', 'v', '2026-01-01')`.
  - DON'T log `now()`, `today()`, `rand()`, `generateUUIDv4()`, or
    `INSERT ... SELECT` from anything that can change underneath you. On replay
    those yield different rows than the ones that were committed.
  - Compute a timestamp or an id in the caller and log the literal.
  - A bulk or non-deterministic transformation belongs in a `checkpoint()`,
    which snapshots the state that resulted, not the statement that caused it.

Unqualified names are safe: the object pins its own database as current, both
when it runs a statement and when it replays one.

A V2 may store row data as Parquet segments, making replay data rather than
re-execution and removing the determinism requirement entirely (§8.1).
"""
from __future__ import annotations

import json
from typing import Callable, List

from .errors import Corrupt, LimitExceeded
from .protocol import MAX_SQL_BYTES, MAX_WAL_SEGMENT_BYTES


def encode_statement(sql: str) -> bytes:
    """One WAL line. Raises `limit_exceeded` for SQL over the frozen cap."""
    size = len(sql.encode("utf-8"))
    if size > MAX_SQL_BYTES:
        raise LimitExceeded(
            f"statement is {size} bytes of UTF-8, over the V1 limit of {MAX_SQL_BYTES}")
    return json.dumps({"sql": sql}, ensure_ascii=False).encode("utf-8") + b"\n"


class WalBuffer:
    """Statements executed locally but not yet published.

    The buffer measures itself as it fills, so a writer refuses an oversized
    segment *before* running the statement it could not log — running it first
    would leave local state the object storage can never be made to match.
    """

    def __init__(self):
        self._lines: List[bytes] = []
        self._bytes = 0

    def would_exceed(self, sql: str) -> bool:
        return self._bytes + len(encode_statement(sql)) > MAX_WAL_SEGMENT_BYTES

    def append(self, sql: str) -> None:
        line = encode_statement(sql)
        if self._bytes + len(line) > MAX_WAL_SEGMENT_BYTES:
            raise LimitExceeded(
                f"WAL segment would reach {self._bytes + len(line)} bytes, over the V1 limit "
                f"of {MAX_WAL_SEGMENT_BYTES}; flush() before adding more")
        self._lines.append(line)
        self._bytes += len(line)

    def __len__(self) -> int:
        return len(self._lines)

    @property
    def nbytes(self) -> int:
        return self._bytes

    def serialize(self) -> bytes:
        return b"".join(self._lines)

    def clear(self) -> None:
        self._lines = []
        self._bytes = 0


def parse_segment(segment: bytes, key: str) -> List[str]:
    """The statements in one verified segment, in replay order.

    Strict on purpose: a segment whose bytes passed the size and SHA-256 check
    but whose contents do not parse is `corrupt`, and §4.5 forbids skipping it
    or falling back to the base. Committed writes are either all replayed or
    the open fails.
    """
    if segment and not segment.endswith(b"\n"):
        raise Corrupt(f"WAL segment {key} does not end with a newline")
    statements: List[str] = []
    for lineno, line in enumerate(segment.split(b"\n")[:-1] if segment else [], start=1):
        try:
            record = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise Corrupt(f"WAL segment {key} line {lineno} is not valid UTF-8 JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise Corrupt(f"WAL segment {key} line {lineno} is not a JSON object")
        sql = record.get("sql")
        if not isinstance(sql, str):
            raise Corrupt(f"WAL segment {key} line {lineno} has no string 'sql' field")
        statements.append(sql)
    return statements


def replay(segment: bytes, key: str, run: Callable[[str], object]) -> int:
    """Replay one segment through `run`, returning the statement count.

    `run` is the object's internal execution path, never the public
    `execute()`: replay must not re-classify, re-log, or re-buffer statements
    that were already committed (§4.4).
    """
    statements = parse_segment(segment, key)
    for sql in statements:
        run(sql)
    return len(statements)
