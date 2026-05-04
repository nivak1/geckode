"""SQLModel tables for users, connected repos, and comment tracking."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


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
