"""Stable names for private, schema-scoped PostgreSQL capabilities.

Naming does not establish that a schema is private: deployment must verify
ownership, ACLs and the actual PostgREST exposed-schema configuration.
Migration copies of this v1 algorithm are intentionally immutable.
"""
from __future__ import annotations

import hashlib

_DOMAIN = b"clinic-capability-schema-v1\0"
_PREFIX = "clinic_internal_"


def capability_schema_name(application_schema: str) -> str:
    """Derive the v1 namespace from an exact PostgreSQL schema identifier."""
    if not isinstance(application_schema, str) or not application_schema or "\0" in application_schema:
        raise ValueError("A nonempty PostgreSQL schema identifier is required")
    try:
        identifier = application_schema.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("The schema identifier must be valid UTF-8") from exc
    if len(identifier) > 63:
        raise ValueError("The schema identifier exceeds PostgreSQL's identifier limit")
    return _PREFIX + hashlib.sha256(_DOMAIN + identifier).hexdigest()[:32]
