from __future__ import annotations

import copy
import json

import pytest
from click.testing import CliRunner

from toolchain.config import SITES
from toolchain.main import cli
from tests.fakes import FakeClient, FakeResponse


def response(brand):
    return {'state':'available','plays':[{'id':'play_'+'b'*32,'claim_id':'clm_'+'a'*32,
        'revision':2,'brand':brand,'tool':'Acme','tools':['Acme'],'version':'2',
        'headline':'Use structured output','why':'Parse it in a script.','do_this':'Use --json.',
        'status':'supported','private_account':'must-not-print'}], 'checked_tools':['Acme']}


@pytest.mark.parametrize('brand',['cyber','ai'])
def test_plays_uses_actual_keyed_api_and_retains_revision(monkeypatch,brand):
    client = FakeClient({SITES[brand].api_base+'/v1/plays':FakeResponse(200,response(brand))})
    monkeypatch.setattr('httpx.Client',lambda **kwargs:client)
    result = CliRunner().invoke(cli,['--site',brand,'--api-key','fictional-key','--limit','5','plays',
        '--tools','Acme,Other','--since','2026-11-01'])
    assert result.exit_code==0, result.output
    doc = json.loads(result.output)
    assert doc['plays'][0]['revision']==2 and doc['plays'][0]['claim_id']=='clm_'+'a'*32
    assert 'must-not-print' not in result.output and 'fictional-key' not in result.output
    assert client.calls==[{'url':SITES[brand].api_base+'/v1/plays',
        'params':{'tools':'Acme,Other','since':'2026-11-01','limit':5},
        'headers':{'x-api-key':'fictional-key'}}]


def test_no_key_does_not_fall_back_to_public_artifact(monkeypatch):
    monkeypatch.setenv('TOOLCHAIN_API_KEY','')
    monkeypatch.setattr('httpx.Client',lambda **kw:pytest.fail('must reject before network'))
    result = CliRunner().invoke(cli,['plays'])
    assert result.exit_code==1 and 'Practitioner' in result.output


@pytest.mark.parametrize('args',[['--limit','6'],['--limit','0'],['--since','yesterday'],
    ['--since','2026-11-01T00:00:00'],['--tools','x'*121],['--tools',','.join('T'+str(i) for i in range(51))]])
def test_invalid_parameters_do_not_dispatch(monkeypatch,args):
    monkeypatch.setattr('httpx.Client',lambda **kw:pytest.fail('invalid request reached network'))
    result=CliRunner().invoke(cli,['--api-key','fictional-key','plays',*args])
    assert result.exit_code!=0


@pytest.mark.parametrize('bad',[{'state':'available','plays':None},
    {'state':'mystery','plays':[]}, {'state':'held','plays':[{}]}])
def test_malformed_or_false_held_response_is_rejected(monkeypatch,bad):
    client=FakeClient({SITES['cyber'].api_base+'/v1/plays':FakeResponse(200,bad)})
    monkeypatch.setattr('httpx.Client',lambda **kw:client)
    result=CliRunner().invoke(cli,['--api-key','fictional-key','plays'])
    assert result.exit_code==2


@pytest.mark.parametrize('mutation',[{'brand':'ai'},{'revision':True},{'claim_id':'not-a-claim'}])
def test_wrong_brand_or_invalid_claim_marker_is_rejected(monkeypatch,mutation):
    bad=copy.deepcopy(response('cyber'));bad['plays'][0].update(mutation)
    client=FakeClient({SITES['cyber'].api_base+'/v1/plays':FakeResponse(200,bad)})
    monkeypatch.setattr('httpx.Client',lambda **kw:client)
    result=CliRunner().invoke(cli,['--api-key','fictional-key','plays'])
    assert result.exit_code==2 and 'Use structured output' not in result.output


def test_server_checks_current_practitioner_entitlement(monkeypatch):
    client=FakeClient({SITES['cyber'].api_base+'/v1/plays':FakeResponse(403,{'error':'requires-practitioner'})})
    monkeypatch.setattr('httpx.Client',lambda **kw:client)
    result=CliRunner().invoke(cli,['--api-key','fictional-key','plays'])
    assert result.exit_code==1 and 'Practitioner' in result.output


@pytest.mark.parametrize('state',['held','unavailable'])
def test_holds_remain_explicit_and_never_empty_success(monkeypatch,state):
    client=FakeClient({SITES['cyber'].api_base+'/v1/plays':FakeResponse(200,{'state':state,'plays':[]})})
    monkeypatch.setattr('httpx.Client',lambda **kw:client)
    result=CliRunner().invoke(cli,['--api-key','fictional-key','plays'])
    assert result.exit_code==0 and json.loads(result.output)['state']==state


def test_exact_claim_query_is_forwarded_without_changing_claim(monkeypatch):
    client=FakeClient({SITES['cyber'].api_base+'/v1/plays':FakeResponse(200,response('cyber'))})
    monkeypatch.setattr('httpx.Client',lambda **kw:client)
    cid='clm_'+'a'*32
    result=CliRunner().invoke(cli,['--api-key','fictional-key','plays','--claim-id',cid])
    assert result.exit_code==0, result.output
    assert client.calls[0]['params']=={'limit':3,'claim_id':cid}
