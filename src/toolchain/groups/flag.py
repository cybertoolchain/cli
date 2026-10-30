"""File a typed correction using the exact claim reference the reader saw."""
from __future__ import annotations

import json

import click

from ..feedback import FeedbackClient
from ..helpers import emit, get_config, handle_errors
from ..models import UserInputError


@click.command()
@click.option('-j', '--claim-id', required=True, help='Canonical clm_ identifier from the published fact.')
@click.option('-r', '--claim-rev', type=click.IntRange(min=1), required=True, help='Published revision; never guessed.')
@click.option('-H', '--observed-hash', required=True, help='Full published claim_hash.')
@click.option('-k', '--kind', type=click.Choice(['wrong', 'missing', 'outdated', 'unclear']), required=True)
@click.option('-p', '--predicate', type=click.Choice(['mcp', 'api', 'capability', 'feature', 'price']), required=True)
@click.option('-P', '--proposal', required=True, help='Typed JSON value, such as {"value":"provides_server"}.')
@click.option('-T', '--tool', help='Canonical tool slug; required by some published targets.')
@click.option('-n', '--note', help='Optional explanation, without personal or private details.')
@click.option('-e', '--evidence-url', help='Public evidence URL; no file uploads.')
@click.pass_context
@handle_errors
def flag(ctx, claim_id, claim_rev, observed_hash, kind, predicate, proposal, tool, note, evidence_url):
    """Report a published fact; a receipt means stored for review, never published.

    API keys admit the request but do not identify the report or boost its weight.
    Reports keep only the day. Leave private details out of text and URLs.
    Older servers are refused before any write; there is no legacy fallback.
    """
    try:
        value = json.loads(proposal)
    except ValueError:
        raise UserInputError('--proposal must be a JSON object.') from None
    body = dict(claim_id=claim_id, claim_rev=claim_rev, observed_hash=observed_hash,
                kind=kind, predicate=predicate, proposal=value)
    body.update({k: v for k, v in {'tool': tool, 'note': note, 'evidence_url': evidence_url}.items() if v is not None})
    config = get_config(ctx)
    emit(FeedbackClient(config).submit(body).receipt, config)
