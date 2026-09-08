"""Native GCS backend.

Conditional primitives: `if_generation_match=0` to create, and
`if_generation_match=<generation>` to replace. A GCS generation *is* a CAS
token, so the object's ETag is the generation number as a string — opaque to
everything above this file, exactly as the protocol requires.
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from ..errors import BackendAmbiguous, BackendError, MissingDependency


class GCSBackend:
    def __init__(self, bucket: str, prefix: str, *, token: Optional[str] = None, project=None):
        try:
            from google.cloud import storage
        except ImportError as e:
            raise MissingDependency(
                "gcs backend needs google-cloud-storage: pip install 'chdb[durable-gcs]'") from e
        self.prefix = prefix.strip("/")
        if token:
            # Explicit bare token: for constrained envs (e.g. a metadata-server
            # access token). NOTE: it cannot refresh — it stops working once the
            # short-lived token expires. Prefer leaving token unset to use
            # Application Default Credentials, which refresh automatically.
            from google.oauth2.credentials import Credentials
            client = storage.Client(project=project, credentials=Credentials(token=token))
        else:
            client = storage.Client(project=project)  # ADC (auto-refreshing)
        self.bucket = client.bucket(bucket)

    def _b(self, key: str):
        return self.bucket.blob(f"{self.prefix}/{key}" if self.prefix else key)

    def _conditional(self, op, what: str) -> bool:
        """True if the conditional write applied, False if the precondition
        failed. `upload_*` returns None either way, so the answer cannot come
        from its return value.
        """
        from google.api_core import exceptions as gexc
        try:
            op()
            return True
        except gexc.PreconditionFailed:
            return False  # the generation moved: a lost CAS, not a failure
        except gexc.NotFound:
            return False  # replace target is gone: also a lost CAS
        except (gexc.ServiceUnavailable, gexc.InternalServerError, gexc.GatewayTimeout,
                gexc.TooManyRequests, gexc.RetryError, gexc.DeadlineExceeded) as e:
            raise BackendAmbiguous(f"{what}: response indeterminate ({e.__class__.__name__})") from e
        except gexc.GoogleAPICallError as e:
            raise BackendError(f"{what}: {e}") from e

    def get(self, key: str) -> Optional[bytes]:
        return self.get_with_etag(key)[0]

    def get_with_etag(self, key: str):
        from google.cloud.exceptions import NotFound
        b = self._b(key)
        try:
            data = b.download_as_bytes()  # populates b.generation
        except NotFound:
            return (None, None)
        gen = b.generation
        if gen is None:
            b.reload()
            gen = b.generation
        return (data, str(gen))

    def put_bytes_if_absent(self, key: str, data: bytes) -> Optional[str]:
        b = self._b(key)
        applied = self._conditional(
            lambda: b.upload_from_string(data, if_generation_match=0), f"create {key}")
        return str(b.generation) if applied else None

    def put_file_if_absent(self, key: str, local_path: str) -> Optional[str]:
        # upload_from_filename streams the file, so a full checkpoint is never
        # read into memory whole (§5.1).
        b = self._b(key)
        applied = self._conditional(
            lambda: b.upload_from_filename(local_path, if_generation_match=0), f"create {key}")
        return str(b.generation) if applied else None

    def replace_if_match(self, key: str, data: bytes, etag: str) -> Optional[str]:
        b = self._b(key)
        applied = self._conditional(
            lambda: b.upload_from_string(data, if_generation_match=int(etag)), f"replace {key}")
        # The upload sets the new generation on the blob it wrote, so the next
        # CAS token comes free — no extra round-trip to read it back.
        return str(b.generation) if applied else None

    def download_to_file(self, key: str, local_path: str) -> bool:
        from google.cloud.exceptions import NotFound
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        tmp = f"{local_path}.{uuid.uuid4().hex}.part"
        try:
            self._b(key).download_to_filename(tmp)
        except NotFound:
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
        # empty scope (both empty) = the whole bucket.
        stripped = f"{self.prefix}/{prefix}".strip("/")
        p = stripped + "/" if stripped else ""
        for blob in self.bucket.list_blobs(prefix=p):
            blob.delete()
