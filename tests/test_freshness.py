"""The real CLI ages canonical timestamps on both backends and brands."""
from datetime import datetime, timezone
import json
import pytest
from click.testing import CliRunner
from toolchain.main import cli
from toolchain.freshness import age_freshness, age_payload, badge_word
from toolchain.source.site import SiteSource
from toolchain.source.api import ApiSource
from .fakes import FakeClient, FakeResponse

NOW=datetime(2026,10,28,12,tzinfo=timezone.utc)
VALUE={'word':'Checked today','checked_at':'2026-10-20T00:00:00Z','pages':2,'pages_checked':2}

def test_cached_aggregate_ages_and_invalid_inventory_is_absent():
    assert age_freshness(VALUE,now=NOW)=={'word':'Over a week old','checked_at':'2026-10-20T00:00:00+00:00','pages':2,'pages_checked':2}
    for row in [None,{},dict(VALUE,pages=0),dict(VALUE,pages_checked=1),dict(VALUE,checked_at='2027-01-01')]:
        assert age_freshness(row,now=NOW) is None

@pytest.mark.parametrize('keyed',[False,True])
@pytest.mark.parametrize('site',['cyber','ai'])
def test_real_tools_get_does_not_trust_cached_word(monkeypatch,keyed,site):
    base='https://example.com'
    path='/v1/tools/example' if keyed else '/tools.json'
    row={'tool':'Example','freshness':dict(VALUE,checked_at='2000-01-01')}
    body=row if keyed else {'tools':[row]}
    client=FakeClient(responses={base+path:FakeResponse(200,body)})
    source=ApiSource(base,'test-key',client=client) if keyed else SiteSource(base,client=client)
    monkeypatch.setattr('toolchain.groups.tools.resolve_source',lambda config:source)
    result=CliRunner().invoke(cli,['--site',site]+(['-k','test-key'] if keyed else [])+['tools','get','example'])
    assert result.exit_code==0,result.output
    assert json.loads(result.stdout)['freshness']['word']=='Over a week old'
    assert 'test-key' not in result.output

def test_claim_and_aggregate_advance_on_the_same_client_clock():
    row={'word':'Documented','detail':'Checked today','checked_at':'2026-10-20','source_mark':'One source','evidence':[]}
    got=age_payload({'claims':{'one':row},'freshness':VALUE},now=NOW)
    assert got['claims']['one']['word']=='Stale'
    assert got['claims']['one']['detail']==got['freshness']['word']=='Over a week old'


def test_week_edge_uses_elapsed_milliseconds_not_calendar_floor():
    assert badge_word('2026-10-22T12:00:00Z',now=datetime.fromisoformat('2026-10-29T12:00:00+00:00'))=='Checked this week'
    assert badge_word('2026-10-22T12:00:00Z',now=datetime.fromisoformat('2026-10-29T12:00:00.001+00:00'))=='Over a week old'


from pathlib import Path
@pytest.mark.parametrize('case',json.loads((Path(__file__).parent/'fixtures/badge-word-cases.json').read_text()),ids=lambda row:row['name'])
def test_shared_badge_fixture(case):
    assert badge_word(case['checked_at'],now=datetime.fromisoformat(case['now'].replace('Z','+00:00')))==case['word']


def _ran(when,outcome='passed'):
    return {'word':'We ran it','detail':None,'checked_at':'2026-10-27T00:00:00Z','source_mark':'One source',
        'evidence':[{'test':{'outcome':outcome,'executed_at':when}}]}


def test_a_run_past_its_window_reads_saw_it_and_loses_the_mark():
    got=age_payload({'claims':{'old':_ran('2026-07-01T00:00:00Z')},'run_mark':{'word':'Verified by running','executed_at':'2026-07-01T00:00:00Z'}},now=NOW)
    assert got['claims']['old']['word']=='Saw it'
    assert got['run_mark'] is None


def test_a_current_run_keeps_its_word_and_the_mark_names_the_newest():
    got=age_payload({'claims':{'a':_ran('2026-10-01T00:00:00Z'),'b':_ran('2026-10-20T00:00:00Z')},'run_mark':{'word':'Verified by running','executed_at':'2026-10-01T00:00:00Z'}},now=NOW)
    assert got['claims']['a']['word']=='We ran it'
    assert got['run_mark']=={'word':'Verified by running','executed_at':'2026-10-20T00:00:00Z'}


@pytest.mark.parametrize('row',[_ran('2026-10-20T00:00:00Z','failed'),_ran('2026-10-20T00:00:00Z','unknown'),_ran('2027-01-01T00:00:00Z'),_ran(None),{**_ran('2026-10-20T00:00:00Z'),'evidence':[]}])
def test_a_run_that_earns_nothing_carries_no_mark(row):
    got=age_payload({'claims':{'one':row},'run_mark':{'word':'Verified by running','executed_at':'2026-10-20T00:00:00Z'}},now=NOW)
    assert got['claims']['one']['word']=='Saw it'
    assert got['run_mark'] is None


def test_a_payload_without_a_mark_gains_no_key():
    assert 'run_mark' not in age_payload({'claims':{}},now=NOW)
