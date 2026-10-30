from __future__ import annotations
import json
import pytest
from click.testing import CliRunner
from toolchain.main import cli
from toolchain.source.site import SiteSource
from toolchain.source.api import ApiSource
from .fakes import FakeClient, FakeResponse

PAYLOAD={'tool':'example','claims':{'f-one':{'claim_id':'clm_one','revision':3,'word':'Our summary',
    'detail':'Date unknown','source_mark':'One source','checked_at':None,'evidence':[
        {'id':'e-one','origin':'docs','url':'https://example.com/docs','quote':'Inspect packets.',
         'quote_is_vendor':False,'fetched_at':None,'span':None}]}}}

@pytest.mark.parametrize('keyed',[False,True])
@pytest.mark.parametrize('site',['cyber','ai'])
def test_claims_json_matches_fixture(monkeypatch,keyed,site):
    base='https://example.com'
    path='/v1/tools/example/claims' if keyed else '/claims/example.json'
    client=FakeClient(responses={base+path:FakeResponse(200,PAYLOAD)})
    source=ApiSource(base,'test-key',client=client) if keyed else SiteSource(base,client=client)
    def resolve(config):
        assert config.site_key==site
        assert bool(config.api_key)==keyed
        return source
    monkeypatch.setattr('toolchain.groups.tools.resolve_source',resolve)
    args=['--site',site]+(['-k','test-key'] if keyed else [])+['claims','example','--json']
    result=CliRunner().invoke(cli,args)
    assert result.exit_code==0,result.output
    assert json.loads(result.output)==PAYLOAD
    assert 'test-key' not in result.output


def test_claims_prints_word_per_feature(monkeypatch):
    client=FakeClient(responses={'https://example.com/claims/example.json':FakeResponse(200,PAYLOAD)})
    monkeypatch.setattr('toolchain.groups.tools.resolve_source',lambda config:SiteSource('https://example.com',client=client))
    result=CliRunner().invoke(cli,['-o','table','claims','example'])
    assert result.exit_code==0,result.output
    assert 'Our summary' in result.output
    assert 'f-one' in result.output


@pytest.mark.parametrize('site',['cyber','ai'])
@pytest.mark.parametrize('keyed',[False,True])
def test_claims_actual_resolver_and_both_real_source_paths(monkeypatch,site,keyed):
    from toolchain.config import SITES
    import httpx
    setting=SITES[site]
    base=setting.api_base if keyed else setting.site_base
    path='/v1/tools/example/claims' if keyed else '/claims/example.json'
    client=FakeClient(responses={base+path:FakeResponse(200,PAYLOAD)})
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:client)
    args=['--site',site,'--debug']+(['-k','test-key'] if keyed else [])+['claims','example','--json']
    result=CliRunner().invoke(cli,args)
    assert result.exit_code==0,result.output
    assert json.loads(result.stdout)==PAYLOAD
    assert 'test-key' not in result.output
    assert client.calls[0]['url']==base+path
    assert (client.calls[0]['headers'] or {}).get('x-api-key')==('test-key' if keyed else None)


@pytest.mark.parametrize('status',[401,403,404,429])
def test_claims_errors_are_shared_errors_without_raw_key(monkeypatch,status):
    client=FakeClient(responses={'https://example.com/v1/tools/example/claims':FakeResponse(status,{})})
    monkeypatch.setattr('toolchain.groups.tools.resolve_source',lambda config:ApiSource('https://example.com','test-key',client=client))
    result=CliRunner().invoke(cli,['-k','test-key','claims','example'])
    assert result.exit_code in (1,2)
    assert 'test-key' not in result.output
