"""The V1 error categories, as Python exception types.

The contract (`dev-docs/CHDB_DURABLE_V1_CONTRACT.md` §6) freezes a set of
categories every binding must let a caller tell apart programmatically. Python
spells them as exception classes; `category` carries the frozen name, so a
cross-binding conformance runner can compare what was raised against the table
without knowing Python's class names.

`LeaseError` is the one grouping type: `lease_held` and `lease_fenced` are
distinct categories, but "I do not own this object" is the question callers
usually ask, and one `except` should answer it.
"""
from __future__ import annotations


class DurableError(RuntimeError):
    """Base class for every chdb.durable error."""

    category = "durable"


class NotFound(DurableError):
    """A read-only open (or an existing-only open) found no object."""

    category = "not_found"


class LeaseError(DurableError):
    """Grouping type for the two lease categories; never raised directly."""

    category = "lease"


class LeaseHeld(LeaseError):
    """Another writer holds an unexpired lease."""

    category = "lease_held"


class LeaseFenced(LeaseError):
    """This instance lost generation/ETag ownership of the object."""

    category = "lease_fenced"


class EngineIncompatible(DurableError):
    """The object's backup format is newer than this engine can restore, this
    engine is older than the object's `min_reader`, or the engine is not chDB."""

    category = "engine_incompatible"


class ProtocolUnsupported(DurableError):
    """The object's protocol version or a declared feature is not supported."""

    category = "protocol_unsupported"


class Corrupt(DurableError):
    """A head that fails schema validation, or an immutable object that is
    missing, the wrong length, or the wrong SHA-256."""

    category = "corrupt"


class ClassificationRefused(DurableError):
    """Statement count, class, or write target did not satisfy the entry gate."""

    category = "classification_refused"


class SecretRefused(DurableError):
    """A mutation carries a credential, so it cannot be written to the WAL."""

    category = "secret_refused"


class EngineError(DurableError):
    """A chdb-core query, backup, or restore failed."""

    category = "engine"


class BackendError(DurableError):
    """A provider network, authentication, or non-conditional failure."""

    category = "backend"


class BackendAmbiguous(BackendError):
    """A conditional write whose response was lost or indeterminate.

    Internal to the backend seam: the state machine catches this and runs the
    §5.8 reconcile, which resolves it into success, `lease_fenced`, or
    `commit_ambiguous`. It is never the final answer given to a caller.
    """

    category = "backend"


class Timeout(DurableError):
    """An operation is known not to have committed and passed its deadline."""

    category = "timeout"


class CommitAmbiguous(DurableError):
    """Reconcile could not prove whether the remote committed."""

    category = "commit_ambiguous"


class LimitExceeded(DurableError):
    """SQL, a WAL segment, or the head passed a limit V1 freezes."""

    category = "limit_exceeded"


class Closed(DurableError):
    """An operation on an object whose close() has completed."""

    category = "closed"


class MissingDependency(DurableError):
    """A backend extra (boto3 / google-cloud-storage / azure-storage-blob) is
    not installed. Not a V1 category — it is an install problem, raised before
    any object is touched."""

    category = "backend"


#: Every frozen V1 category, mapped to the exception raised for it. Useful to a
#: conformance runner; `LeaseError` and `MissingDependency` are deliberately
#: absent, being a grouping type and an install-time error respectively.
V1_CATEGORIES = {
    "not_found": NotFound,
    "lease_held": LeaseHeld,
    "lease_fenced": LeaseFenced,
    "engine_incompatible": EngineIncompatible,
    "protocol_unsupported": ProtocolUnsupported,
    "corrupt": Corrupt,
    "classification_refused": ClassificationRefused,
    "secret_refused": SecretRefused,
    "engine": EngineError,
    "backend": BackendError,
    "timeout": Timeout,
    "commit_ambiguous": CommitAmbiguous,
    "limit_exceeded": LimitExceeded,
    "closed": Closed,
}
