"""Helpers for coercing user-supplied identifiers into UUIDs.

API paths and JWT claims carry UUIDs as strings. The database columns are
native ``uuid`` on PostgreSQL and ``CHAR(32)`` on SQLite, and the two
represent a UUID differently, so every identifier is normalised through
:func:`to_uuid` before it reaches a query.
"""

from __future__ import annotations

import uuid


def to_uuid(value: object) -> uuid.UUID | None:
    """Return ``value`` as a :class:`uuid.UUID`, or ``None`` if it is not one."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None
