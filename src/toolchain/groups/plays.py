"""Keyed public Plays; matching is performed by the current entitled API."""
from __future__ import annotations

import re
from datetime import datetime

import click

from ..helpers import emit, get_config, handle_errors
from ..models import APIError, UserInputError
from ..source import resolve_source

PUBLIC_FIELDS = frozenset({'id','claim_id','revision','brand','tool','tools','version','kind',
    'headline','narrative','why','context','do_this','prerequisite','effort','deadline','entry_url',
    'evidence','capability','hints','category','personas','valid_from','known_from','status',
    'delivery_state','manifest','test','prerelease','source_state','gap_proof'})


def _validate(data: object, brand: str) -> dict:
    if (not isinstance(data,dict) or data.get('state') not in ('available','held','unavailable')
            or not isinstance(data.get('plays'),list) or len(data['plays'])>5
            or 'brand' in data and data['brand']!=brand
            or data['state']!='available' and data['plays']):
        raise APIError('The Plays API returned an invalid availability state.')
    rows=[];seen=set()
    for row in data['plays']:
        if (not isinstance(row,dict) or row.get('brand')!=brand
                or not isinstance(row.get('claim_id'),str)
                or not re.fullmatch(r'clm_[0-9a-f]{32}',row['claim_id'])
                or row['claim_id'] in seen or type(row.get('revision')) is not int or row['revision']<1
                or any(not isinstance(row.get(k),str) or not row[k].strip()
                       for k in ('id','tool','headline','why','do_this'))):
            raise APIError('The Plays API returned an invalid claim revision or product.')
        seen.add(row['claim_id'])
        rows.append({key:value for key,value in row.items() if key in PUBLIC_FIELDS})
    result={'state':data['state'],'brand':brand,'plays':rows}
    checked=data.get('checked_tools')
    if checked is not None:
        if not isinstance(checked,list) or any(not isinstance(t,str) for t in checked):
            raise APIError('The Plays API returned invalid coverage.')
        result['checked_tools']=checked
    return result


@click.command('plays')
@click.option('-t','--tools',multiple=True,help='Tool names, comma separated; repeat for additional tools (up to 50).')
@click.option('-s','--since',default=None,help='Earliest release date or timezone-aware ISO timestamp.')
@click.option('-i','--claim-id',default=None,help='Read one exact public claim ID.')
@click.pass_context
@handle_errors
def plays(ctx: click.Context, tools: tuple[str,...], since: str | None, claim_id: str | None) -> None:
    """Get evidenced actions for your tools (Practitioner or above).

    Requires an API key from your account page. The server checks the current
    subscription and rollout state; held and unavailable remain explicit.
    """
    config=get_config(ctx)
    limit=config.limit if config.limit is not None else 3
    if not 1<=limit<=5: raise UserInputError('Plays accepts a global --limit between 1 and 5.')
    if not config.api_key:
        raise UserInputError('Plays requires a Practitioner API key. Create one on your account page and set TOOLCHAIN_API_KEY.')
    names=[name.strip() for chunk in tools for name in chunk.split(',') if name.strip()]
    if len(names)>50 or tools and not names or any(len(name)>120 or any(ord(c)<32 for c in name) for name in names):
        raise UserInputError('--tools accepts at most 50 nonempty names, each up to 120 characters.')
    if since:
        try:
            value=datetime.fromisoformat(since.replace('Z','+00:00'))
            if 'T' in since and value.tzinfo is None: raise ValueError
        except ValueError:
            raise UserInputError('--since must be an ISO date or a timestamp with a timezone.') from None
    if claim_id and not re.fullmatch(r'clm_[0-9a-f]{32}',claim_id):
        raise UserInputError('--claim-id must be a public claim ID.')
    params={'limit':limit}
    if names: params['tools']=','.join(names)
    if since: params['since']=since
    if claim_id: params['claim_id']=claim_id
    data=resolve_source(config).fetch('plays',**params)
    emit(_validate(data,config.site_key),config)
