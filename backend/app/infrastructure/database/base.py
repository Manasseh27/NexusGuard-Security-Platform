"""Shared SQLAlchemy declarative base for the database layer."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""

    pass