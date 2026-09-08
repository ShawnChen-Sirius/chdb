"""`head.json` — the object's whole mutable state, in one CAS-able document.

The lease and the manifest share a single object on purpose: taking the lease,
publishing a WAL segment, and replacing the base are all one conditional
replace, so a cold open costs a couple of round-trips and there is no window
in which the lease says one thing and the manifest another.

What this module is strict about, and why:

* **Schema.** §4.5 requires a head that fails validation to be `corrupt`, not
  coerced. A manifest that "mostly parses" is how a reader ends up restoring a
  base it cannot verify.
* **Unknown fields.** §4.2 requires a writer to preserve keys it does not
  recognise at the top level and inside `protocol`, `engine`, `lease` and
  `manifest`. A future field must survive a round-trip through a writer that
  predates it, so the document is rebuilt from the one it was read from.
* **Byte-for-byte equality.** Not required, and not attempted. Key order and
  whitespace are free; the *semantics* are frozen, which is what lets Node,
  Go and Python read each other's objects.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .errors import Corrupt, LimitExceeded
from .protocol import (
    BACKUP_FORMAT,
    ENGINE_NAME,
    MAX_HEAD_BYTES,
    PROTOCOL_VERSION,
    validate_object_key,
    validate_safe_int,
    validate_sha256,
)


def _require_dict(value: object, where: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise Corrupt(f"{where}: expected an object, got {type(value).__name__}")
    return value


def _require_str(value: object, where: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise Corrupt(f"{where}: expected a non-empty string, got {value!r}")
    return value


def _require_str_list(value: object, where: str) -> List[str]:
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise Corrupt(f"{where}: expected a list of strings, got {value!r}")
    return list(value)


def _unknown(source: Dict[str, Any], known: tuple) -> Dict[str, Any]:
    return {k: v for k, v in source.items() if k not in known}


@dataclass
class ObjectRef:
    """A reference to one immutable object: where it is, and what it must be.

    `size` and `sha256` are not belt-and-braces. §4.5 requires both to be
    checked before the bytes are used, because the two failures they catch are
    different: a truncated upload has the right prefix, and a replaced object
    has the right length.
    """

    key: str
    size: int
    sha256: str
    extra: Dict[str, Any] = field(default_factory=dict, compare=False)

    @classmethod
    def parse(cls, value: object, where: str) -> "ObjectRef":
        raw = _require_dict(value, where)
        return cls(
            key=validate_object_key(raw.get("key"), f"{where}.key"),
            size=validate_safe_int(raw.get("size"), f"{where}.size"),
            sha256=validate_sha256(raw.get("sha256"), f"{where}.sha256"),
            extra=_unknown(raw, ("key", "size", "sha256")),
        )

    def to_json(self) -> Dict[str, Any]:
        out = dict(self.extra)
        out.update({"key": self.key, "size": self.size, "sha256": self.sha256})
        return out


@dataclass
class Lease:
    """Who owns the object, and until when.

    `generation` only ever moves forward, and only on a real change of owner
    (§4.2): acquiring from released, taking over an expired lease, or a force
    takeover. A heartbeat renews `expires_at` and leaves the generation alone,
    which is what lets a fenced writer tell "I was superseded" from "my clock
    and the head disagree".
    """

    generation: int
    owner: Optional[str] = None
    instance: Optional[str] = None
    expires_at: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def released(self) -> bool:
        return self.owner is None

    def held_at(self, now: float, *, clock_skew: float = 0.0) -> bool:
        """Is this lease still someone's at `now`, allowing for clock skew?

        A held lease with no expiry never expires, so it can only be taken by
        an explicit force takeover — which is the safe reading of a head we
        cannot date.
        """
        if self.released:
            return False
        if self.expires_at is None:
            return True
        return now <= self.expires_at + clock_skew

    @classmethod
    def parse(cls, value: object, where: str) -> "Lease":
        raw = _require_dict(value, where)
        generation = validate_safe_int(raw.get("generation"), f"{where}.generation")
        owner, instance, expires_at = raw.get("owner"), raw.get("instance"), raw.get("expires_at")
        if owner is None:
            # §4.2 fixes one representation for a released lease. A head that
            # nulls the owner but keeps an expiry is not it, and guessing which
            # half to believe is how a live writer gets fenced by a reader.
            if instance is not None or expires_at is not None:
                raise Corrupt(
                    f"{where}: a released lease must null owner, instance and expires_at together")
        else:
            _require_str(owner, f"{where}.owner")
            _require_str(instance, f"{where}.instance")
            if isinstance(expires_at, bool) or not isinstance(expires_at, (int, float)):
                raise Corrupt(f"{where}.expires_at: expected a number, got {expires_at!r}")
            expires_at = float(expires_at)
        return cls(
            generation=generation,
            owner=owner,
            instance=instance,
            expires_at=expires_at,
            extra=_unknown(raw, ("generation", "owner", "instance", "expires_at")),
        )

    def to_json(self) -> Dict[str, Any]:
        out = dict(self.extra)
        out.update({
            "generation": self.generation,
            "owner": self.owner,
            "instance": self.instance,
            "expires_at": self.expires_at,
        })
        return out


@dataclass
class Manifest:
    """The database's name, its base checkpoint, and the WAL to replay onto it.

    `wal` is in replay order, and `seq` advances on every published reference —
    which is what makes a lost CAS response resolvable: the key is unique, so
    finding it in the manifest proves the commit landed.
    """

    db: str
    base: Optional[ObjectRef] = None
    wal: List[ObjectRef] = field(default_factory=list)
    seq: int = 0
    extra: Dict[str, Any] = field(default_factory=dict, compare=False)

    @classmethod
    def parse(cls, value: object, where: str) -> "Manifest":
        raw = _require_dict(value, where)
        base = raw.get("base")
        wal = raw.get("wal", [])
        if not isinstance(wal, list):
            raise Corrupt(f"{where}.wal: expected a list, got {wal!r}")
        return cls(
            db=_require_str(raw.get("db"), f"{where}.db"),
            base=None if base is None else ObjectRef.parse(base, f"{where}.base"),
            wal=[ObjectRef.parse(v, f"{where}.wal[{i}]") for i, v in enumerate(wal)],
            seq=validate_safe_int(raw.get("seq"), f"{where}.seq"),
            extra=_unknown(raw, ("db", "base", "wal", "seq")),
        )

    def to_json(self) -> Dict[str, Any]:
        out = dict(self.extra)
        out.update({
            "db": self.db,
            "base": None if self.base is None else self.base.to_json(),
            "wal": [ref.to_json() for ref in self.wal],
            "seq": self.seq,
        })
        return out


@dataclass
class EngineInfo:
    """Which engine wrote the object, and which engines can read it.

    `version` is diagnostic — "who wrote this last" — and is deliberately not
    an equality gate. `backup_format` and `min_reader` are the gate (§4.3), so
    a later core opens an earlier object instead of refusing it for having a
    different version string.
    """

    name: str = ENGINE_NAME
    version: str = ""
    backup_format: int = BACKUP_FORMAT
    min_reader: str = ""
    extra: Dict[str, Any] = field(default_factory=dict, compare=False)

    @classmethod
    def parse(cls, value: object, where: str) -> "EngineInfo":
        raw = _require_dict(value, where)
        return cls(
            name=_require_str(raw.get("name"), f"{where}.name"),
            version=_require_str(raw.get("version"), f"{where}.version"),
            backup_format=validate_safe_int(raw.get("backup_format"), f"{where}.backup_format"),
            min_reader=_require_str(raw.get("min_reader"), f"{where}.min_reader"),
            extra=_unknown(raw, ("name", "version", "backup_format", "min_reader")),
        )

    def to_json(self) -> Dict[str, Any]:
        out = dict(self.extra)
        out.update({
            "name": self.name,
            "version": self.version,
            "backup_format": self.backup_format,
            "min_reader": self.min_reader,
        })
        return out


@dataclass
class ProtocolInfo:
    version: int = PROTOCOL_VERSION
    reader_features: List[str] = field(default_factory=list)
    writer_features: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict, compare=False)

    @classmethod
    def parse(cls, value: object, where: str) -> "ProtocolInfo":
        raw = _require_dict(value, where)
        return cls(
            version=validate_safe_int(raw.get("version"), f"{where}.version", minimum=1),
            reader_features=_require_str_list(
                raw.get("reader_features", []), f"{where}.reader_features"),
            writer_features=_require_str_list(
                raw.get("writer_features", []), f"{where}.writer_features"),
            extra=_unknown(raw, ("version", "reader_features", "writer_features")),
        )

    def to_json(self) -> Dict[str, Any]:
        out = dict(self.extra)
        out.update({
            "version": self.version,
            "reader_features": list(self.reader_features),
            "writer_features": list(self.writer_features),
        })
        return out


@dataclass
class Head:
    protocol: ProtocolInfo
    engine: EngineInfo
    lease: Lease
    manifest: Manifest
    #: The document as it was read, so keys this version does not know about
    #: are written back unchanged.
    raw: Dict[str, Any] = field(default_factory=dict, compare=False)

    @classmethod
    def parse(cls, data: bytes) -> "Head":
        if len(data) > MAX_HEAD_BYTES:
            raise LimitExceeded(
                f"head.json is {len(data)} bytes, over the V1 limit of {MAX_HEAD_BYTES}")
        try:
            doc = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise Corrupt(f"head.json is not valid UTF-8 JSON: {exc}") from exc
        raw = _require_dict(doc, "head")
        if "protocol" not in raw and "engine" not in raw and "manifest" in raw:
            # The shape chdb.durable wrote before V1 was frozen: a lease and a
            # manifest whose base/WAL are bare key strings, with no protocol or
            # engine section and no checksums. Say that, rather than report a
            # missing key and leave the reader guessing which key.
            raise Corrupt(
                "head.json has no 'protocol' or 'engine' section, which is the shape the "
                "pre-V1 chdb.durable prototype wrote. A V1 reader cannot verify its "
                "checkpoints (they carry no length or SHA-256) and will not restore them; "
                "export the data with the prototype version and load it into a new object")
        for required in ("protocol", "engine", "lease", "manifest"):
            if required not in raw:
                raise Corrupt(f"head.json is missing {required!r}")
        return cls(
            protocol=ProtocolInfo.parse(raw["protocol"], "head.protocol"),
            engine=EngineInfo.parse(raw["engine"], "head.engine"),
            lease=Lease.parse(raw["lease"], "head.lease"),
            manifest=Manifest.parse(raw["manifest"], "head.manifest"),
            raw=copy.deepcopy(raw),
        )

    @classmethod
    def cold(cls, *, db: str, engine_version: str, lease: Lease) -> "Head":
        """The head a writer creates for an object that does not exist yet."""
        return cls(
            protocol=ProtocolInfo(),
            engine=EngineInfo(
                name=ENGINE_NAME,
                version=engine_version,
                backup_format=BACKUP_FORMAT,
                min_reader=engine_version,
            ),
            lease=lease,
            manifest=Manifest(db=db),
        )

    def to_bytes(self) -> bytes:
        doc = copy.deepcopy(self.raw) if self.raw else {}
        doc["protocol"] = self.protocol.to_json()
        doc["engine"] = self.engine.to_json()
        doc["lease"] = self.lease.to_json()
        doc["manifest"] = self.manifest.to_json()
        body = json.dumps(doc, ensure_ascii=False).encode("utf-8")
        if len(body) > MAX_HEAD_BYTES:
            # §4.5: the writer is the one that has to notice, while it still
            # has the option of checkpointing the WAL list away.
            raise LimitExceeded(
                f"head.json would be {len(body)} bytes, over the V1 limit of "
                f"{MAX_HEAD_BYTES}; checkpoint to shorten the WAL list")
        return body
