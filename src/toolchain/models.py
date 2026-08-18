from __future__ import annotations


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
