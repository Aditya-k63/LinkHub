"""SQLAlchemy models.

The UUID columns use the generic :class:`sqlalchemy.Uuid` type rather than
``postgresql.UUID`` so that the exact same models work against PostgreSQL
(native ``uuid``) and SQLite (``CHAR(32)``) - which is what the test suite
and the local dev fallback use.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Timezone-naive UTC timestamp (the columns are ``TIMESTAMP``)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    links: Mapped[list["Link"]] = relationship(
        "Link", back_populates="owner", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<User {self.username}>"


class Link(Base):
    __tablename__ = "links"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    short_code: Mapped[str] = mapped_column(
        String(10), unique=True, nullable=False, index=True
    )
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    click_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    owner: Mapped["User"] = relationship("User", back_populates="links")
    clicks: Mapped[list["Click"]] = relationship(
        "Click", back_populates="link", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_short_code_active", "short_code", "is_active"),
        Index("idx_links_owner_created", "owner_id", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Link {self.short_code} -> {self.original_url}>"


class Click(Base):
    __tablename__ = "clicks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    link_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("links.id", ondelete="CASCADE"), nullable=False
    )
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    referrer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    browser: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    os: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    device_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    link: Mapped["Link"] = relationship("Link", back_populates="clicks")

    __table_args__ = (
        Index("idx_link_clicked_at", "link_id", "clicked_at"),
        Index("idx_clicks_link_browser", "link_id", "browser"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Click {self.link_id} at {self.clicked_at}>"
