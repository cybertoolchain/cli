"""Write contracts use synthetic credentials and an in-process HTTP transport only."""
import json

import httpx
import pytest
from click.testing import CliRunner

from toolchain.config import resolve_config
from toolchain.main import cli
from toolchain.models import ToolchainError

BODY = {'claim_id': 'clm_' + 'a' * 32, 'claim_rev': 3, 'observed_hash': 'b' * 64,
        'kind': 'wrong', 'predicate': 'mcp', 'proposal': {'value': 'provides_server'}, 'tool': 'example'}
CAP = {'contract': 'unlinked-claim-report-v1', 'typed_reports': True, 'attachments': False,
       'receipt': 'persisted-report', 'identity': 'unlinked', 'time_resolution': 'day'}
RECEIPT = {'contract': CAP['contract'], 'report_id': 'r-' + 'c' * 24, 'revision': 1,
           'status': 'received', 'persisted': True}


@pytest.mark.parametrize('brand', ['cyber', 'ai'])
def test_capability_then_one_uncached_write_fixed_endpoint(brand, caplog):
    from toolchain.feedback import FeedbackClient
    import logging
    caplog.set_level(logging.DEBUG)
    calls = []
    key = 'ctk_SYNTHETIC_DO_NOT_LOG'
    def handler(req):
        calls.append(req)
        if req.method == 'GET':
            assert 'x-api-key' not in req.headers
            return httpx.Response(200, json={**CAP, 'brand': brand})
        assert req.headers['x-api-key'] == key
        payload = json.loads(req.content)
        assert payload['report'] == BODY and payload['brand'] == brand
        assert len(payload['ownership_token']) == 64
        assert key not in req.content.decode()
        return httpx.Response(200, json={**RECEIPT, 'brand': brand})
    config = resolve_config(site=brand, api_key=key, debug=True)
    result = FeedbackClient(config, client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)).submit(BODY)
    assert result.receipt['persisted'] is True
    assert len(result.ownership_token) == 64
    assert result.ownership_token not in repr(result)
    assert [r.method for r in calls] == ['GET', 'POST']
    assert all(r.url.host == 'api.cybertoolchain.io' for r in calls)
    assert key not in caplog.text
    assert resolve_config(site='ai').site.api_base is None  # read behavior unchanged


@pytest.mark.parametrize('response', [
    httpx.Response(404), httpx.Response(200, json={'status': 'ok'}),
    httpx.Response(200, json={**CAP, 'brand': 'ai'}),
    httpx.Response(200, json={**CAP, 'brand': 'cyber', 'typed_reports': False}),
    httpx.Response(302, headers={'Location': 'https://surprise.example/steal'}),
    httpx.Response(200, text='not json'),
])
def test_old_or_incompatible_server_never_receives_post(response):
    from toolchain.feedback import FeedbackClient
    calls = []
    client = httpx.Client(transport=httpx.MockTransport(lambda req: calls.append(req) or response))
    with pytest.raises(ToolchainError):
        FeedbackClient(resolve_config(api_key='ctk_SYNTHETIC'), client=client).submit(BODY)
    assert len(calls) == 1 and calls[0].method == 'GET'


@pytest.mark.parametrize('bad', [
    httpx.Response(307, headers={'Location': 'https://surprise.example/steal'}),
    httpx.Response(200, json={'receipt': 'queued'}),
    httpx.Response(200, json={**RECEIPT, 'brand': 'ai'}),
    httpx.Response(200, json={**RECEIPT, 'brand': 'cyber', 'persisted': False}),
    httpx.Response(500, text='ctk_SYNTHETIC private body'),
])
def test_post_receipt_and_redirect_errors_redact_and_never_retry(bad):
    from toolchain.feedback import FeedbackClient
    calls = []
    def handler(req):
        calls.append(req)
        return httpx.Response(200, json={**CAP, 'brand': 'cyber'}) if req.method == 'GET' else bad
    with pytest.raises(ToolchainError) as err:
        FeedbackClient(resolve_config(api_key='ctk_SYNTHETIC'),
                       client=httpx.Client(transport=httpx.MockTransport(handler))).submit(BODY)
    assert 'ctk_SYNTHETIC' not in str(err.value) and 'private body' not in str(err.value)
    assert len(calls) == 2


@pytest.mark.parametrize('config', [resolve_config(), resolve_config(api_key='ctk_test', cache=True)])
def test_no_key_or_read_cache_cannot_send(config):
    from toolchain.feedback import FeedbackClient
    with pytest.raises(ToolchainError):
        FeedbackClient(config, client=httpx.Client(transport=httpx.MockTransport(
            lambda req: pytest.fail('must not send')))).submit(BODY)


@pytest.mark.parametrize('patch', [{'claim_rev': 0}, {'observed_hash': 'b'*8}, {'kind': 'confirm'},
                                 {'proposal': 'yes'}, {'account_id': 'private'}])
def test_bad_input_refused_before_http(patch):
    from toolchain.feedback import FeedbackClient
    with pytest.raises(ToolchainError):
        FeedbackClient(resolve_config(api_key='ctk_test'), client=httpx.Client(
            transport=httpx.MockTransport(lambda req: pytest.fail('must not send')))).submit({**BODY, **patch})


@pytest.mark.parametrize('brand', ['cyber', 'ai'])
def test_command_uses_shared_output_and_keeps_ownership_private(monkeypatch, brand):
    from toolchain.feedback import Submission
    from toolchain.groups import flag
    calls = []
    class Fake:
        def __init__(self, config):
            assert config.site_key == brand
        def submit(self, report):
            calls.append(report)
            return Submission({**RECEIPT, 'brand': brand}, 'd' * 64)
    monkeypatch.setattr(flag, 'FeedbackClient', Fake)
    result = CliRunner().invoke(cli, ['--site', brand, '--api-key', 'ctk_test', 'flag',
        '--claim-id', BODY['claim_id'], '--claim-rev', '3', '--observed-hash', BODY['observed_hash'],
        '--kind', 'wrong', '--predicate', 'mcp', '--proposal', json.dumps(BODY['proposal']), '--tool', 'example'])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)['report_id'] == RECEIPT['report_id']
    assert 'd' * 64 not in result.output
    assert calls == [BODY]


@pytest.mark.parametrize('brand', ['cyber', 'ai'])
def test_origin_payload_hash_covers_exact_once_serialized_bytes(brand):
    import hashlib
    from toolchain.feedback import FeedbackClient
    calls = []
    report = {**BODY, 'note': 'Résumé “β”\nsecond line'}
    def edge(req):
        calls.append(req)
        if req.method == 'GET':
            assert 'x-api-key' not in req.headers and 'x-amz-content-sha256' not in req.headers
            return httpx.Response(200, json={**CAP, 'brand': brand})
        assert req.headers.get('x-amz-content-sha256') == hashlib.sha256(req.content).hexdigest()
        assert req.headers['content-type'] == 'application/json'
        assert json.loads(req.content)['report'] == report
        return httpx.Response(200, json={**RECEIPT, 'brand': brand})
    client = httpx.Client(transport=httpx.MockTransport(edge), follow_redirects=True)
    FeedbackClient(resolve_config(site=brand, api_key='ctk_synthetic'), client=client).submit(report)
    assert [r.method for r in calls] == ['GET', 'POST']


@pytest.mark.parametrize('brand', ['cyber', 'ai'])
@pytest.mark.parametrize('edge_body', [None, {}, {'error': 'requires-researcher'},
                                       {'contract': CAP['contract'], 'brand': 'wrong', 'error': 'requires-researcher'}])
def test_edge_403_does_not_blame_subscription(brand, edge_body):
    from toolchain.feedback import FeedbackClient
    def edge(req):
        if req.method == 'GET':
            return httpx.Response(200, json={**CAP, 'brand': brand})
        return httpx.Response(403, json=edge_body) if edge_body is not None else httpx.Response(403, text='Synthetic edge denial')
    with pytest.raises(ToolchainError) as err:
        FeedbackClient(resolve_config(site=brand, api_key='ctk_synthetic'),
                       client=httpx.Client(transport=httpx.MockTransport(edge))).submit(BODY)
    assert 'Researcher' not in str(err.value) and 'Business' not in str(err.value)
    assert 'Synthetic' not in str(err.value)


@pytest.mark.parametrize('brand', ['cyber', 'ai'])
def test_explicit_versioned_brand_app_403_can_explain_tier(brand):
    from toolchain.feedback import FeedbackClient
    def app(req):
        if req.method == 'GET':
            return httpx.Response(200, json={**CAP, 'brand': brand})
        return httpx.Response(403, json={'contract': CAP['contract'], 'brand': brand, 'error': 'requires-researcher'})
    with pytest.raises(ToolchainError, match='Researcher'):
        FeedbackClient(resolve_config(site=brand, api_key='ctk_synthetic'),
                       client=httpx.Client(transport=httpx.MockTransport(app))).submit(BODY)
