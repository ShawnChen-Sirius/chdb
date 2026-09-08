"""Native Azure Blob backend.

Conditional primitives: `overwrite=False` to create (a `ResourceExistsError`
is the precondition failing) and an `IfNotModified` ETag match to replace. No
S3 compatibility layer is involved.
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from ..errors import BackendAmbiguous, BackendError, MissingDependency


class AzureBlobBackend:
    def __init__(self, container: str, prefix: str, *, conn_str: str):
        try:
            from azure.storage.blob import ContainerClient
        except ImportError as e:
            raise MissingDependency(
                "azure backend needs azure-storage-blob: pip install 'chdb[durable-azure]'") from e
        self.prefix = prefix.strip("/")
        self.cc = ContainerClient.from_connection_string(conn_str, container)
        try:
            self.cc.create_container()
        except Exception:
            pass

    def _n(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    def _conditional(self, op, what: str):
        from azure.core.exceptions import (
            ResourceExistsError,
            ResourceModifiedError,
            ResourceNotFoundError,
            ServiceRequestError,
            ServiceResponseError,
            HttpResponseError,
        )
        try:
            return op()
        except (ResourceExistsError, ResourceModifiedError, ResourceNotFoundError):
            return None  # the precondition failed: a lost CAS, not an error
        except (ServiceRequestError, ServiceResponseError) as e:
            # The response never arrived; the service may still have applied it.
            raise BackendAmbiguous(f"{what}: response indeterminate") from e
        except HttpResponseError as e:
            if e.status_code and 500 <= e.status_code < 600:
                raise BackendAmbiguous(f"{what}: response indeterminate ({e.status_code})") from e
            raise BackendError(f"{what}: {e}") from e

    def get(self, key: str) -> Optional[bytes]:
        return self.get_with_etag(key)[0]

    def get_with_etag(self, key: str):
        from azure.core.exceptions import ResourceNotFoundError
        try:
            d = self.cc.download_blob(self._n(key))
            return (d.readall(), d.properties.etag)  # bytes + etag in one round-trip
        except ResourceNotFoundError:
            return (None, None)

    def put_bytes_if_absent(self, key: str, data: bytes) -> Optional[str]:
        r = self._conditional(
            lambda: self.cc.upload_blob(self._n(key), data, overwrite=False), f"create {key}")
        return None if r is None else r.get("etag")

    def put_file_if_absent(self, key: str, local_path: str) -> Optional[str]:
        # Hand the SDK a file object so it chunks the upload itself, rather
        # than materialising a whole checkpoint in memory (§5.1).
        def op():
            with open(local_path, "rb") as body:
                return self.cc.upload_blob(self._n(key), body, overwrite=False)

        r = self._conditional(op, f"create {key}")
        return None if r is None else r.get("etag")

    def replace_if_match(self, key: str, data: bytes, etag: str) -> Optional[str]:
        from azure.core import MatchConditions
        r = self._conditional(
            lambda: self.cc.upload_blob(self._n(key), data, overwrite=True, etag=etag,
                                        match_condition=MatchConditions.IfNotModified),
            f"replace {key}")
        return None if r is None else r.get("etag")

    def download_to_file(self, key: str, local_path: str) -> bool:
        from azure.core.exceptions import ResourceNotFoundError
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        tmp = f"{local_path}.{uuid.uuid4().hex}.part"
        try:
            stream = self.cc.download_blob(self._n(key))
            with open(tmp, "wb") as handle:
                stream.readinto(handle)
        except ResourceNotFoundError:
            if os.path.exists(tmp):
                os.unlink(tmp)
            return False
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        os.replace(tmp, local_path)  # publish only a complete transfer
        return True

    def delete_prefix(self, prefix: str = "") -> None:
        """Not V1 — see the note in `backends/__init__.py`."""
        # trailing "/" bounds the match to this object (not sibling "foobar/...");
        # empty scope (both empty) = the whole container.
        stripped = f"{self.prefix}/{prefix}".strip("/")
        p = stripped + "/" if stripped else ""
        for b in self.cc.list_blobs(name_starts_with=p):
            self.cc.delete_blob(b.name)
