"""Length and SHA-256, the two things a manifest says about an immutable object.

Both are checked before the bytes are used (§4.5). They fail on different
things — a truncated upload has the right prefix, a replaced object has the
right length — so neither is redundant.

Checkpoints are hashed by streaming: a full backup must never have to sit in
memory in one piece just to be measured (§5.1).
"""
from __future__ import annotations

import hashlib
import os
from typing import Tuple

from .errors import Corrupt

_CHUNK = 1024 * 1024


def bytes_digest(data: bytes) -> Tuple[int, str]:
    return len(data), hashlib.sha256(data).hexdigest()


def file_digest(path: str) -> Tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def verify_bytes(data: bytes, ref, *, what: str) -> None:
    size, sha256 = bytes_digest(data)
    _compare(size, sha256, ref, what)


def verify_file(path: str, ref, *, what: str) -> None:
    if not os.path.exists(path):
        raise Corrupt(f"{what} {ref.key} was not downloaded")
    size, sha256 = file_digest(path)
    _compare(size, sha256, ref, what)


def _compare(size: int, sha256: str, ref, what: str) -> None:
    if size != ref.size:
        raise Corrupt(
            f"{what} {ref.key} is {size} bytes, the manifest says {ref.size}")
    if sha256 != ref.sha256:
        raise Corrupt(
            f"{what} {ref.key} has SHA-256 {sha256}, the manifest says {ref.sha256}")
