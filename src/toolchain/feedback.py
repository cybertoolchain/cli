"""Uncached, capability-negotiated writes; independent of the read-only Source API."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
import secrets
from typing import Any

import httpx

from .config import Config
from .models import APIError, NetworkError, UserInputError
from .versioning import default_headers

CONTRACT = 'unlinked-claim-report-v1'
# Both brand.yaml api.subscriber entries use this shared billing service. Brand
# is explicit in every request/receipt. These do not change the existing data APIs.
FEEDBACK_BASES = {'cyber': 'https://api.cybertoolchain.io', 'ai': 'https://api.cybertoolchain.io'}
PATH = '/agent/claim-reports'
REQUIRED = {'claim_id', 'claim_rev', 'observed_hash', 'kind', 'predicate', 'proposal'}
ALLOWED = REQUIRED | {'tool', 'note', 'evidence_url'}


@dataclass(frozen=True)
class Submission:
    receipt: dict
    # Retained in memory for the later attachment ownership lane, never printed.
    ownership_token: str = field(repr=False)


def validate_report(report: dict) -> None:
    valid = (isinstance(report, dict) and REQUIRED <= set(report) <= ALLOWED
             and isinstance(report.get('claim_id'), str)
             and re.fullmatch(r'clm_[0-9a-f]{32}', report['claim_id'])
             and type(report.get('claim_rev')) is int and report['claim_rev'] >= 1
             and isinstance(report.get('observed_hash'), str)
             and re.fullmatch(r'[0-9a-f]{64}', report['observed_hash'])
             and report.get('kind') in ('wrong', 'missing', 'outdated', 'unclear')
             and report.get('predicate') in ('mcp', 'api', 'capability', 'feature', 'price')
             and isinstance(report.get('proposal'), dict))
    if not valid:
        raise UserInputError('A flag needs the complete published claim ID, revision, hash, kind and typed proposal.')
    for name, limit in (('tool', 128), ('note', 500), ('evidence_url', 2000)):
        if name in report and (not isinstance(report[name], str) or len(report[name]) > limit):
            raise UserInputError('A flag contains an invalid optional field.')
    try:
        encoded = json.dumps(report, allow_nan=False)
    except (TypeError, ValueError):
        raise UserInputError('The typed proposal must be valid JSON.') from None
    if len(encoded.encode()) > 16_384:
        raise UserInputError('The flag is too large.')


class FeedbackClient:
    def __init__(self, config: Config, *, client: Any = None):
        self.config = config
        self._client = client

    def submit(self, report: dict, *, ownership_token: str | None = None) -> Submission:
        if not self.config.api_key:
            raise UserInputError('Flagging needs an API key from your account page; set TOOLCHAIN_API_KEY.')
        if self.config.cache:
            raise UserInputError('Flags cannot use the read cache; omit --cache before submitting.')
        validate_report(report)
        token = ownership_token or secrets.token_hex(32)
        if not isinstance(token, str) or not re.fullmatch('[0-9a-f]{64}', token):
            raise UserInputError('Invalid report ownership capability.')
        if self.config.site_key not in FEEDBACK_BASES:
            raise UserInputError('This site has no supported correction endpoint.')
        if self._client is not None:
            return self._submit(self._client, report, token)
        with httpx.Client(timeout=self.config.timeout, follow_redirects=False,
                          headers=default_headers()) as client:
            return self._submit(client, report, token)

    def _submit(self, client, report, token) -> Submission:
        brand = self.config.site_key
        base = FEEDBACK_BASES[brand] + PATH
        try:
            response = client.get(base + '/capabilities', params={'brand': brand},
                                  follow_redirects=False)
            capabilities = response.json() if response.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            raise NetworkError('Could not verify correction support; no report was sent.') from None
        if (not isinstance(capabilities, dict) or capabilities.get('contract') != CONTRACT
                or capabilities.get('brand') != brand or capabilities.get('typed_reports') is not True
                or capabilities.get('receipt') != 'persisted-report'
                or capabilities.get('identity') != 'unlinked' or capabilities.get('time_resolution') != 'day'):
            raise APIError('This server does not support typed corrections yet; no report was sent.')
        try:
            response = client.post(base, json={'brand': brand, 'report': report, 'ownership_token': token},
                                   headers={'x-api-key': self.config.api_key}, follow_redirects=False)
        except httpx.HTTPError:
            # Do not retry a POST or echo exception/request bodies. The client has
            # no authoritative receipt; a timeout is not proof that nothing landed.
            raise NetworkError('No persistence receipt was received; report delivery is unknown.') from None
        if response.status_code == 401:
            raise UserInputError('The API key was refused; check your account key.')
        if response.status_code == 403:
            raise UserInputError('The API key needs Researcher or Business access for this brand.')
        if response.status_code == 429:
            raise APIError('The correction limit was reached; try again later.')
        if response.status_code != 200:
            raise APIError('No persistence receipt was received; the correction was refused or is unavailable.')
        try:
            receipt = response.json()
        except ValueError:
            raise APIError('No valid persistence receipt was received; report delivery is unknown.') from None
        if (not isinstance(receipt, dict) or receipt.get('contract') != CONTRACT
                or receipt.get('brand') != brand or receipt.get('persisted') is not True
                or receipt.get('status') != 'received' or type(receipt.get('revision')) is not int
                or receipt['revision'] < 1 or not isinstance(receipt.get('report_id'), str)
                or not re.fullmatch(r'r-[0-9a-f]{24}', receipt['report_id'])):
            raise APIError('No valid persistence receipt was received; report delivery is unknown.')
        # Allowlisted output: a server cannot reflect credentials/private fields into CLI logs.
        safe = {k: receipt[k] for k in ('contract', 'brand', 'report_id', 'revision', 'status', 'persisted')}
        return Submission(safe, token)
