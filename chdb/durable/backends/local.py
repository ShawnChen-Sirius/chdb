"""Local filesystem backend — the most vendor-neutral home of all: a folder.

**Scope: development, tests, and single-writer/single-host use.** The strong
concurrency guarantees a durable object relies on — atomic conditional writes
for the lease and head CAS — belong to the object-store backends (S3
`IfMatch`/`IfNoneMatch`, GCS generation-match, Azure ETag), which provide them
natively. This backend approximates them on a POSIX filesystem
(`O_CREAT|O_EXCL` for create, `flock` for compare-and-set, path containment in
`_p`) so tests are realistic, but it is not multi-host safe. Point a namespace
at a cloud (or S3-compatible) backend for that.

A local write either happens or raises, so this backend never reports an
ambiguous conditional write — the reconcile path (§5.8) exists for the network
backends and is exercised there.
"""
from __future__ import annotations

import os
import shutil
import uuid
from typing import Optional


class LocalFSBackend:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)

    def _p(self, key: str) -> str:
        # Constrain every key under root: an absolute key or ".." would
        # otherwise let put/delete_prefix write or rm outside the backend.
        full = os.path.realpath(os.path.join(self.root, key))
        root = os.path.realpath(self.root)
        if full != root and not full.startswith(root + os.sep):
            raise ValueError(f"key escapes backend root: {key!r}")
        return full

    def _etag(self, path: str) -> Optional[str]:
        try:
            st = os.stat(path)
        except FileNotFoundError:
            return None
        return f"{st.st_mtime_ns}-{st.st_size}"

    def get(self, key: str) -> Optional[bytes]:
        try:
            with open(self._p(key), "rb") as f:
                return f.read()
        except FileNotFoundError:
            return None

    def get_with_etag(self, key: str):
        # Read body and etag from the SAME file descriptor so they describe the
        # same version — a separate stat could pair an old body with a new etag
        # if the file is replaced between the two calls.
        try:
            fd = os.open(self._p(key), os.O_RDONLY)
        except FileNotFoundError:
            return (None, None)
        try:
            st = os.fstat(fd)
            f = os.fdopen(fd, "rb")
            fd = -1  # fdopen owns the descriptor now
            with f:
                data = f.read()
        except BaseException:
            if fd >= 0:  # only close if fdopen never took ownership
                os.close(fd)
            raise
        return (data, f"{st.st_mtime_ns}-{st.st_size}")

    def put_bytes_if_absent(self, key: str, data: bytes) -> Optional[str]:
        p = self._p(key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return None
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            st = os.fstat(f.fileno())  # etag of exactly what we created
        return f"{st.st_mtime_ns}-{st.st_size}"

    def put_file_if_absent(self, key: str, local_path: str) -> Optional[str]:
        # Stage beside the target, then link it into place: the link is the
        # atomic create, so a large archive is never visible half-copied and
        # two writers cannot both believe they created the key.
        p = self._p(key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        staged = f"{p}.{uuid.uuid4().hex}.staging"
        try:
            shutil.copyfile(local_path, staged)
            try:
                os.link(staged, p)
            except FileExistsError:
                return None
        finally:
            if os.path.exists(staged):
                os.unlink(staged)
        return self._etag(p)

    def replace_if_match(self, key: str, data: bytes, etag: str) -> Optional[str]:
        import fcntl
        # serialize check-then-act across processes so two writers can't both
        # observe the same etag and both write (which would defeat the CAS).
        p = self._p(key)
        lockpath = p + ".lock"
        os.makedirs(os.path.dirname(lockpath), exist_ok=True)
        with open(lockpath, "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            if self._etag(p) != etag:
                return None
            tmp = f"{p}.{uuid.uuid4().hex}.tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, p)  # atomic
            return self._etag(p)

    def download_to_file(self, key: str, local_path: str) -> bool:
        src = self._p(key)
        if not os.path.exists(src):
            return False
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        tmp = f"{local_path}.{uuid.uuid4().hex}.part"
        shutil.copyfile(src, tmp)
        os.replace(tmp, local_path)
        return True

    def delete_prefix(self, prefix: str = "") -> None:
        """Not V1 — see the note in `backends/__init__.py`."""
        target = self._p(prefix) if prefix else self.root
        shutil.rmtree(target, ignore_errors=True)
