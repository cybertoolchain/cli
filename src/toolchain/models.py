from __future__ import annotations

from typing import NotRequired, TypedDict


class ToolchainError(Exception):
    """Base of every error the CLI raises deliberately. Never raise bare."""

    exit_code = 1


class UserInputError(ToolchainError):
    """Bad flag, missing/invalid argument, or a command run without a
    required API key."""

    exit_code = 1


class APIError(ToolchainError):
    """HTTP 4xx/5xx (other than an auth rejection) from either backend."""

    exit_code = 2


class NetworkError(ToolchainError):
    """Connection refused, timeout, DNS failure."""

    exit_code = 3


class ClaimReceipt(TypedDict):
    claim_id: str
    revision: NotRequired[int | None]
    word: str
    detail: str | None
    source_mark: str
    checked_at: str | None
    evidence: list[dict]
    source_checks: NotRequired[list[dict]]
    page_changed: NotRequired[bool]


class ToolClaims(TypedDict):
    tool: str
    claims: dict[str, ClaimReceipt]
    freshness: NotRequired[dict | None]
