"""SQLModel tables for users, connected repos, and comment tracking."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "github_user"

    id: int | None = Field(default=None, primary_key=True)
    github_id: int = Field(index=True, unique=True)
    login: str
    access_token: str = Field(sa_column=Column(Text))


class ConnectedRepo(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    full_name: str = Field(index=True, unique=True)
    user_id: int = Field(foreign_key="github_user.id")
    webhook_id: int | None = None
    webhook_secret: str = Field(sa_column=Column(Text))
    language: str = "auto-detect"
    strictness: str = "medium"
    standards_json: str = Field(default="[]", sa_column=Column(Text))
    review_dimensions_json: str | None = Field(default=None, sa_column=Column(Text))


class ReviewRun(SQLModel, table=True):
    """Manual dashboard review: track progress and outcome for polling UI."""

    __tablename__ = "review_run"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="github_user.id", index=True)
    repo_full_name: str = Field(index=True)
    pr_number: int = Field(index=True)
    status: str = "queued"  # queued | running | completed | failed
    created_at: datetime = Field(default_factory=_utc_now)
    finished_at: datetime | None = None
    error_message: str | None = Field(default=None, sa_column=Column(Text))
    inline_posted: int | None = None
    patched_count: int | None = None
    resolved_threads: int | None = None
    general_notes_count: int | None = None
    skipped_files_count: int | None = None
    dropped_invalid_count: int | None = None
    used_fallback_comment: bool | None = None


class PRCommentSnapshot(SQLModel, table=True):
    """Maps logical file:line on a PR to the latest GitHub pull comment id for PATCH updates."""

    id: int | None = Field(default=None, primary_key=True)
    repo_full_name: str = Field(index=True)
    pr_number: int = Field(index=True)
    path: str
    line: int
    github_comment_id: int = Field(index=True)


def standards_from_json(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
        return list(data) if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def standards_to_json(standards: list[str]) -> str:
    return json.dumps(standards)
