from __future__ import annotations

import functools
import sys
from typing import Any, Callable, TypeVar

import click

from .config import Config
from .models import ToolchainError
from .output import format_output

F = TypeVar("F", bound=Callable[..., Any])


def get_config(ctx: click.Context) -> Config:
    return ctx.obj


def emit(data: Any, config: Config) -> None:
    click.echo(
        format_output(
            data,
            fmt=config.output,
            limit=config.limit,
            search_fields=config.search_fields,
            short=config.short,
        )
    )


def handle_errors(fn: F) -> F:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ToolchainError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(exc.exit_code)

    return wrapper  # type: ignore[return-value]
