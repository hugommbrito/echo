"""Owner (tenant) context.

Every business model inherits `OwnedModel`, whose default manager refuses to run a query unless
the current owner is known. The owner is set per request by `OwnerContextMiddleware` and
explicitly by background tasks / management commands via `owner_context(user_id)`.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator
from contextvars import ContextVar

_current_owner_id: ContextVar[uuid.UUID | None] = ContextVar("echo_current_owner_id", default=None)


class NoOwnerContext(RuntimeError):
    """Raised when owned data is queried without an owner context (fail-closed)."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message
            or "No owner context: wrap the code in owner_context(user_id) or use Model.all_users "
            "for deliberate cross-user access."
        )


def _coerce_id(value) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    if hasattr(value, "pk"):
        return _coerce_id(value.pk)
    return uuid.UUID(str(value))


def get_current_owner_id() -> uuid.UUID | None:
    return _current_owner_id.get()


def require_current_owner_id() -> uuid.UUID:
    owner_id = _current_owner_id.get()
    if owner_id is None:
        raise NoOwnerContext()
    return owner_id


@contextlib.contextmanager
def owner_context(user_or_id) -> Iterator[uuid.UUID]:
    """Bind the current owner for the duration of the block (nestable, thread/async safe)."""
    owner_id = _coerce_id(user_or_id)
    token = _current_owner_id.set(owner_id)
    try:
        yield owner_id
    finally:
        _current_owner_id.reset(token)


@contextlib.contextmanager
def no_owner_context() -> Iterator[None]:
    """Explicitly clear the owner (used by tests to assert fail-closed behaviour)."""
    token = _current_owner_id.set(None)
    try:
        yield
    finally:
        _current_owner_id.reset(token)
