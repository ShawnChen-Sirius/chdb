"""S3-compatible backend: AWS S3, MinIO, Cloudflare R2, Backblaze, Tigris, and
GCS through its S3-interoperability endpoint — one code path, `endpoint_url`
picks the provider.

Conditional primitives: `IfNoneMatch: *` to create, `IfMatch: <etag>` to
replace. Both are real S3 preconditions, which is what makes the lease a lease
and not a convention.
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from ..errors import BackendAmbiguous, BackendError, MissingDependency

#: Codes that mean "the precondition was not met" — a lost CAS, not an error.
_CAS_MISS = ("PreconditionFailed", "412", "NoSuchKey", "404")

#: Codes that mean "we do not know whether the server applied this". A 409 on a
#: conditional write is S3 telling us another conditional write raced ours; a
#: 5xx or a dropped connection may or may not have committed. Either way the
#: state machine has to look, not assume (§5.8).
_AMBIGUOUS = ("409", "ConditionalRequestConflict", "OperationAborted",
              "InternalError", "ServiceUnavailable", "SlowDown", "500", "503")


class S3Backend:
    def __init__(self, bucket: str, prefix: str, *, endpoint_url=None,
                 access_key=None, secret_key=None, region="us-east-1"):
        try:
            import boto3
        except ImportError as e:
            raise MissingDependency("s3 backend needs boto3: pip install 'chdb[durable]'") from e
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.s3 = boto3.client(
            "s3", endpoint_url=endpoint_url, region_name=region,
            aws_access_key_id=access_key, aws_secret_access_key=secret_key,
        )

    def _k(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    @staticmethod
    def _code(exc) -> str:
        err = getattr(exc, "response", {}).get("Error", {})
        return str(err.get("Code", ""))

    def _conditional(self, op, what: str):
        """Run a conditional write, sorting the three outcomes apart."""
        import botocore
        try:
            return op()
        except botocore.exceptions.ClientError as e:
            code = self._code(e)
            status = str(e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", ""))
            if code in _CAS_MISS or status == "412":
                return None
            if code in _AMBIGUOUS or status.startswith("5") or status == "409":
                raise BackendAmbiguous(f"{what}: response indeterminate ({code or status})") from e
            raise BackendError(f"{what}: {e}") from e
        except (botocore.exceptions.ConnectionError, botocore.exceptions.HTTPClientError) as e:
            # The request left; whether it landed is exactly what we do not know.
            raise BackendAmbiguous(f"{what}: connection lost before a response") from e

    def get(self, key: str) -> Optional[bytes]:
        return self.get_with_etag(key)[0]

    def get_with_etag(self, key: str):
        import botocore
        try:
            r = self.s3.get_object(Bucket=self.bucket, Key=self._k(key))
            return (r["Body"].read(), r["ETag"])  # bytes + etag in one round-trip
        except botocore.exceptions.ClientError as e:
            if self._code(e) in ("NoSuchKey", "404", "NoSuchBucket"):
                return (None, None)
            raise BackendError(f"get {key}: {e}") from e

    def put_bytes_if_absent(self, key: str, data: bytes) -> Optional[str]:
        r = self._conditional(
            lambda: self.s3.put_object(Bucket=self.bucket, Key=self._k(key), Body=data,
                                       IfNoneMatch="*"),
            f"create {key}")
        return None if r is None else r["ETag"]

    def put_file_if_absent(self, key: str, local_path: str) -> Optional[str]:
        # A file object, not bytes: boto3 streams it, so a multi-gigabyte
        # checkpoint is never resident in one piece (§5.1).
        def op():
            with open(local_path, "rb") as body:
                return self.s3.put_object(Bucket=self.bucket, Key=self._k(key), Body=body,
                                          IfNoneMatch="*")

        r = self._conditional(op, f"create {key}")
        return None if r is None else r["ETag"]

    def replace_if_match(self, key: str, data: bytes, etag: str) -> Optional[str]:
        r = self._conditional(
            lambda: self.s3.put_object(Bucket=self.bucket, Key=self._k(key), Body=data,
                                       IfMatch=etag),
            f"replace {key}")
        return None if r is None else r["ETag"]

    def download_to_file(self, key: str, local_path: str) -> bool:
        import botocore
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        tmp = f"{local_path}.{uuid.uuid4().hex}.part"
        try:
            self.s3.download_file(self.bucket, self._k(key), tmp)
        except botocore.exceptions.ClientError as e:
            if os.path.exists(tmp):
                os.unlink(tmp)
            if self._code(e) in ("NoSuchKey", "404", "NoSuchBucket"):
                return False
            raise BackendError(f"download {key}: {e}") from e
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        # Publish only once the whole transfer is on disk, so a caller can
        # never verify a partial download against the manifest.
        os.replace(tmp, local_path)
        return True

    def delete_prefix(self, prefix: str = "") -> None:
        """Not V1 — see the note in `backends/__init__.py`."""
        # trailing "/" bounds the match to this object — without it, destroying
        # "foo" would also delete sibling keys under "foobar/...". An empty
        # scope (prefix and self.prefix both empty) means the whole bucket.
        stripped = self._k(prefix).strip("/")
        p = stripped + "/" if stripped else ""
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=p):
            objs = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if objs:
                resp = self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": objs})
                errs = resp.get("Errors") or []
                if errs:  # S3 reports per-key failures here even on a 200
                    raise BackendError(
                        f"delete_prefix: {len(errs)} object(s) not deleted, e.g. {errs[0]}")
