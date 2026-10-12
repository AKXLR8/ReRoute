"""Shared test fakes — a scriptable stand-in for the async DB session."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from reroute.models.user import User


class FakeResult:
    """Enough of a SQLAlchemy Result for the queries the auth code issues."""

    def __init__(self, first=None, rows=None, scalar=None, rowcount=1):
        self._first = first
        self._rows = rows if rows is not None else ([first] if first is not None else [])
        self._scalar = scalar
        self.rowcount = rowcount

    def scalars(self):
        return self

    def first(self):
        return self._first

    def all(self):
        return self._rows

    def scalar_one(self):
        return self._scalar


class FakeDb:
    """execute → per-test lambda; add/commit/refresh tracked for assertions."""

    def __init__(self):
        self.execute_impl = None  # callable(stmt) -> FakeResult
        self.get_impl = None  # callable(model, pk) -> obj | None
        self.added: list = []
        self.commits = 0

    async def execute(self, stmt):
        if self.execute_impl is None:
            raise AssertionError("unexpected db.execute in this test")
        return self.execute_impl(stmt)

    async def get(self, model, pk):
        if self.get_impl is None:
            raise AssertionError("unexpected db.get in this test")
        return self.get_impl(model, pk)

    def add(self, obj):
        if isinstance(obj, User):
            # flush-time column defaults don't exist without a real session
            if obj.is_active is None:
                obj.is_active = True
            if obj.failed_logins is None:
                obj.failed_logins = 0
            if obj.token_version is None:
                obj.token_version = 1
            if obj.role is None:
                obj.role = "member"
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        if isinstance(obj, User):
            if obj.id is None:
                obj.id = uuid.uuid4()
            if obj.created_at is None:
                obj.created_at = datetime.now(UTC)
            if obj.updated_at is None:
                obj.updated_at = datetime.now(UTC)


_default_hash: str | None = None


def make_user(
    *,
    email: str = "admin@example.com",
    password_hash: str | None = None,
    role: str = "admin",
    is_active: bool = True,
    token_version: int = 1,
    failed_logins: int = 0,
    locked_until=None,
) -> User:
    global _default_hash
    if password_hash is None:
        if _default_hash is None:  # one 600k-iteration hash for the whole session
            from reroute.auth.passwords import hash_password

            _default_hash = hash_password("correct-horse-battery")
        password_hash = _default_hash
    return User(
        id=uuid.uuid4(),
        email=email,
        password_hash=password_hash,
        role=role,
        is_active=is_active,
        failed_logins=failed_logins,
        locked_until=locked_until,
        token_version=token_version,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
