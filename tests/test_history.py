from __future__ import annotations

import json
import socket

import pytest
from click.testing import CliRunner

from toolchain.main import cli


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('History tests must not use the network')

    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'connect_ex', denied)
    monkeypatch.setattr(socket, 'getaddrinfo', denied)
    monkeypatch.setenv('TOOLCHAIN_API_KEY', '')


@pytest.mark.parametrize('brand', ['cyber', 'ai'])
@pytest.mark.parametrize('command', [['history', 'vendor-tool'], ['tools', 'history', 'vendor-tool']])
def test_free_history_selects_own_tool_and_brand_and_exposes_revision(monkeypatch, brand, command):
    calls = []

    class Source:
        def fetch(self, path, **params):
            calls.append(path)
            return {'brand': brand, 'claims': {
                'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa': {'subject': 'Vendor Tool@Autumn Release', 'revision': 3,
                          'status': 'supported', 'object': 'Corrected fact',
                          'note': 'PRIVATE-NOTE', 'source_key': 'PRIVATE-SOURCE'},
                'clm_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb': {'subject': 'Other Tool@v1', 'revision': 9,
                          'status': 'suggested', 'object': 'Other tool fact'},
            }, 'history': {'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa': [{'revision': 3, 'role': 'the editor',
                                       'status': 'supported', 'object': 'Corrected fact',
                                       'reason': 'scope corrected', 'subscriber_id': 'PRIVATE-ID'}]}}

    monkeypatch.setattr('toolchain.groups.history.resolve_source', lambda config: Source())
    result = CliRunner().invoke(cli, ['--site', brand, '--output', 'json', *command], env={'TOOLCHAIN_API_KEY': ''})
    assert result.exit_code == 0, result.output
    body = json.loads(result.output)
    assert calls == [f'claims/{brand}.json']
    assert [(row['claim_id'], row['revision'], row['marker']) for row in body['claims']] == [('clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 3, 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@3')]
    assert body['decisions'][0]['claim_id'] == 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    assert 'PRIVATE' not in result.output


def test_keyed_history_uses_live_history_and_keeps_machine_markers(monkeypatch):
    class Source:
        def fetch(self, path, **params):
            assert path == 'tools/vendor-tool/history'
            return {'claims': [{'claim_id': 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'revision': 4, 'note': 'PRIVATE'}],
                    'decisions': [{'claim_id': 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'revision': 4, 'cause': 'incomplete scope',
                                   'intake_id': 'PRIVATE'}]}

    monkeypatch.setattr('toolchain.groups.history.resolve_source', lambda config: Source())
    result = CliRunner().invoke(cli, ['--api-key', 'fixture-key', 'history', 'vendor-tool'])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)['claims'][0]['marker'] == 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@4'
    assert 'PRIVATE' not in result.output and 'fixture-key' not in result.output


def test_legacy_keyed_response_keeps_missing_marker_distinct_from_empty(monkeypatch):
    class Source:
        def fetch(self, *args, **kwargs):
            return {'entries': [], 'note': 'PRIVATE'}

    monkeypatch.setattr('toolchain.groups.history.resolve_source', lambda config: Source())
    result = CliRunner().invoke(cli, ['--api-key', 'fixture-key', 'history', 'vendor-tool'])
    assert result.exit_code == 0, result.output
    assert 'claims' not in json.loads(result.output)
    assert 'PRIVATE' not in result.output


def test_empty_measured_free_history_has_empty_claims(monkeypatch):
    class Source:
        def fetch(self, *args, **kwargs):
            return {'brand': 'cyber', 'claims': {}, 'history': {}}

    monkeypatch.setattr('toolchain.groups.history.resolve_source', lambda config: Source())
    result = CliRunner().invoke(cli, ['history', 'vendor-tool'], env={'TOOLCHAIN_API_KEY': ''})
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)['claims'] == []


@pytest.mark.parametrize('doc', [
    {'brand': 'ai', 'claims': {}},
    {'brand': 'cyber', 'claims': {'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa': {'subject': 'Vendor Tool@v1', 'revision': True}}},
    {'brand': 'cyber', 'claims': {'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa': {'subject': 'Vendor Tool@v1', 'revision': 0}}},
    {'brand': 'cyber', 'claims': []},
])
def test_malformed_or_wrong_brand_history_fails_instead_of_inventing_a_revision(monkeypatch, doc):
    class Source:
        def fetch(self, *args, **kwargs):
            return doc

    monkeypatch.setattr('toolchain.groups.history.resolve_source', lambda config: Source())
    result = CliRunner().invoke(cli, ['history', 'vendor-tool'], env={'TOOLCHAIN_API_KEY': ''})
    assert result.exit_code != 0, result.output


def test_table_output_prints_claim_at_revision(monkeypatch):
    class Source:
        def fetch(self, *args, **kwargs):
            return {'brand': 'cyber', 'claims': {'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa': {
                'subject': 'Vendor Tool@v1', 'revision': 3, 'status': 'suggested', 'object': 'Current fact'}},
                'history': {'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa': [
                    {'revision': 3, 'status': 'suggested', 'object': 'Current fact'}]}}

    monkeypatch.setattr('toolchain.groups.history.resolve_source', lambda config: Source())
    result = CliRunner().invoke(cli, ['--output', 'table', 'history', 'vendor-tool'], env={'TOOLCHAIN_API_KEY': ''})
    assert result.exit_code == 0 and 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@3' in result.output


@pytest.mark.parametrize('extra', [
    {'brand': 'ai'}, {'tool': 'other-tool'},
    {'claims': [{'claim_id': 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'revision': 4, 'object': {'token': 'PRIVATE'}}]},
    {'claims': [{'claim_id': 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'revision': 4, 'subject': 'Other Tool@v1'}]},
    {'claims': [{'claim_id': 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\x1b[31m', 'revision': 4}]},
    {'decisions': [{'claim_id': 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'revision': True}]},
    {'decisions': [{'claim_id': 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'revision': 4, 'reason': {'note': 'PRIVATE'}}]},
    {'decisions': [None]},
    {'decisions': [{'revision': 2, 'reason': 'missing identity'}]},
])
def test_keyed_history_refuses_scope_or_nested_private_values(monkeypatch, extra):
    class Source:
        def fetch(self, *args, **kwargs):
            return {'brand': 'cyber', 'tool': 'vendor-tool',
                    'claims': [{'claim_id': 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'revision': 4}], **extra}

    monkeypatch.setattr('toolchain.groups.history.resolve_source', lambda config: Source())
    result = CliRunner().invoke(cli, ['--api-key', 'fixture-key', 'history', 'vendor-tool'])
    assert result.exit_code == 2 and 'PRIVATE' not in result.output, result.output


@pytest.mark.parametrize('claims,message', [(None, 'not available'), ([], 'No breaking-change claims')])
def test_empty_and_missing_human_history_have_distinct_messages(monkeypatch, claims, message):
    class Source:
        def fetch(self, *args, **kwargs):
            return {} if claims is None else {'claims': claims}

    monkeypatch.setattr('toolchain.groups.history.resolve_source', lambda config: Source())
    result = CliRunner().invoke(cli, ['--api-key', 'fixture-key', '--output', 'table', 'history', 'vendor-tool'])
    assert result.exit_code == 0 and message in result.output, result.output


@pytest.mark.parametrize('output', ['table', 'csv', 'tsv'])
def test_table_includes_correction_decisions_and_current_markers(monkeypatch, output):
    class Source:
        def fetch(self, *args, **kwargs):
            return {'claims': [{'claim_id': 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'revision': 4}], 'decisions': [
                {'claim_id': 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'revision': 2, 'reason': 'scope corrected', 'role': 'the editor'}]}

    monkeypatch.setattr('toolchain.groups.history.resolve_source', lambda config: Source())
    result = CliRunner().invoke(cli, ['--api-key', 'fixture-key', '--output', output, 'history', 'vendor-tool'])
    assert result.exit_code == 0 and 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@4' in result.output and 'scope corrected' in result.output
    assert 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@2' in result.output


@pytest.mark.parametrize('status,label', [('contested', 'Under review'), ('absent', 'No documented match')])
def test_history_uses_the_canonical_reader_status_label(monkeypatch, status, label):
    class Source:
        def fetch(self, *args, **kwargs):
            return {'claims': [{'claim_id': 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'revision': 4, 'status': status}]}

    monkeypatch.setattr('toolchain.groups.history.resolve_source', lambda config: Source())
    result = CliRunner().invoke(cli, ['--api-key', 'fixture-key', 'history', 'vendor-tool'])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)['claims'][0]['label'] == label


def test_invalid_history_status_is_not_a_reader_fact(monkeypatch):
    class Source:
        def fetch(self, *args, **kwargs):
            return {'claims': [{'claim_id': 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'revision': 4, 'status': 'candidate'}]}

    monkeypatch.setattr('toolchain.groups.history.resolve_source', lambda config: Source())
    result = CliRunner().invoke(cli, ['--api-key', 'fixture-key', 'history', 'vendor-tool'])
    assert result.exit_code == 2


_CID = 'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'


def _ledger(brand):
    return {'brand': brand, 'claims': {_CID: {
        'subject': 'Vendor Tool@v1', 'tool': 'Vendor Tool', 'scope': f'brand:{brand}',
        'revision': 3, 'status': 'supported', 'object': 'Current fact',
        'known_from': '2026-10-29',
    }}, 'history': {_CID: [{
        'revision': 3, 'status': 'supported', 'object': 'Current fact',
        'date': '2026-10-29', 'origin': 'https://example.org/notes',
    }]}}


def _invoke_ledger(monkeypatch, doc, brand, keyed=False, output='json'):
    if keyed:
        doc = {'brand': brand, 'tool': 'vendor-tool',
               'claims': [{'claim_id': cid, **row} for cid, row in doc['claims'].items()],
               'decisions': [{'claim_id': cid, **row}
                             for cid, rows in doc.get('history', {}).items() for row in rows]}

    class Source:
        def fetch(self, path, **params):
            assert path == ('tools/vendor-tool/history' if keyed else f'claims/{brand}.json')
            return doc

    monkeypatch.setattr('toolchain.groups.history.resolve_source', lambda config: Source())
    return CliRunner().invoke(cli, ['--site', brand, '--output', output,
                                   *(['--api-key', 'fixture-key'] if keyed else []),
                                   'history', 'vendor-tool'])


@pytest.mark.parametrize('brand', ['cyber', 'ai'])
@pytest.mark.parametrize('keyed', [False, True])
@pytest.mark.parametrize('metadata', [
    {'tool': 'Other Tool'}, {'subject': 'Other Tool@v1'},
    {'scope': 'brand:OTHER'}, {'brand': 'OTHER'},
    {'tool': None}, {'tool': 7}, {'subject': None}, {'subject': 'Vendor Tool@'},
])
def test_history_rejects_conflicting_or_malformed_claim_identity(monkeypatch, brand, keyed, metadata):
    doc = _ledger(brand)
    opposite = 'ai' if brand == 'cyber' else 'cyber'
    metadata = {key: value.replace('OTHER', opposite) if isinstance(value, str) else value
                for key, value in metadata.items()}
    doc['claims'][_CID].update(metadata)
    result = _invoke_ledger(monkeypatch, doc, brand, keyed)
    assert result.exit_code == 2, result.output
    assert 'Current fact' not in result.output


@pytest.mark.parametrize('brand', ['cyber', 'ai'])
@pytest.mark.parametrize('field', ['subject', 'revision', 'status', 'object'])
def test_free_history_rejects_incomplete_other_tool_rows(monkeypatch, brand, field):
    doc = _ledger(brand)
    row = doc['claims'][_CID]
    row.update(subject='Other Tool@v1', tool='Other Tool')
    del row[field]
    result = _invoke_ledger(monkeypatch, doc, brand)
    assert result.exit_code == 2, result.output


@pytest.mark.parametrize('brand', ['cyber', 'ai'])
@pytest.mark.parametrize('fault', [
    'missing_history', 'missing_member', 'empty', 'future', 'older_head',
    'duplicate', 'status', 'object', 'date', 'identity',
])
def test_free_history_requires_history_bound_to_current_head(monkeypatch, brand, fault):
    doc = _ledger(brand)
    rows = doc['history'][_CID]
    if fault == 'missing_history':
        del doc['history']
    elif fault == 'missing_member':
        del doc['history'][_CID]
    elif fault == 'empty':
        rows.clear()
    elif fault == 'future':
        rows[0]['revision'] = 99
    elif fault == 'older_head':
        rows[0]['revision'] = 2
    elif fault == 'duplicate':
        rows.append(dict(rows[0]))
    elif fault == 'identity':
        rows[0]['claim_id'] = 'clm_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
    else:
        rows[0][fault] = {'status': 'contested', 'object': 'Other fact', 'date': '2026-10-28'}[fault]
    result = _invoke_ledger(monkeypatch, doc, brand)
    assert result.exit_code == 2, result.output
    assert 'Current fact' not in result.output


@pytest.mark.parametrize('brand', ['cyber', 'ai'])
@pytest.mark.parametrize('keyed', [False, True])
@pytest.mark.parametrize('output', ['json', 'table'])
@pytest.mark.parametrize('origin', [
    'https://user:FAKE-TOKEN@example.invalid/path?token=FAKE-TOKEN',
    'https://FAKE-TOKEN@example.invalid/path',
])
def test_history_rejects_credential_origin_without_echoing_it(monkeypatch, brand, keyed, output, origin):
    doc = _ledger(brand)
    doc['history'][_CID][0]['origin'] = origin
    result = _invoke_ledger(monkeypatch, doc, brand, keyed, output)
    assert result.exit_code == 2, result.output
    assert 'FAKE-TOKEN' not in result.output + result.stdout + result.stderr
    assert 'example.invalid' not in result.output + result.stdout + result.stderr


@pytest.mark.parametrize('brand', ['cyber', 'ai'])
@pytest.mark.parametrize('keyed', [False, True])
def test_history_keeps_normal_public_origin(monkeypatch, brand, keyed):
    result = _invoke_ledger(monkeypatch, _ledger(brand), brand, keyed)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)['decisions'][0]['origin'] == 'https://example.org/notes'


@pytest.mark.parametrize('brand', ['cyber', 'ai'])
def test_free_history_withheld_and_other_tool_are_measured_empty(monkeypatch, brand):
    doc = _ledger(brand)
    doc['claims'][_CID].update(subject='Other Tool@v1', tool='Other Tool')
    hidden = 'clm_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
    doc['claims'][hidden] = {'revision': 4, 'status': 'unknown', 'withheld': 'evidence_revoked'}
    doc['history'][hidden] = []
    result = _invoke_ledger(monkeypatch, doc, brand)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {'tool': 'vendor-tool', 'brand': brand, 'claims': [], 'decisions': []}
    assert hidden not in result.output and 'evidence_revoked' not in result.output


@pytest.mark.parametrize('extra', [
    {'withheld': 'other'}, {'status': 'supported'}, {'revision': True}, {'subject': 'PRIVATE@v1'},
])
def test_free_history_rejects_malformed_withheld_tombstone(monkeypatch, extra):
    doc = _ledger('cyber')
    doc['claims'][_CID] = {'revision': 4, 'status': 'unknown', 'withheld': 'evidence_revoked', **extra}
    doc['history'][_CID] = []
    result = _invoke_ledger(monkeypatch, doc, 'cyber')
    assert result.exit_code == 2 and 'PRIVATE' not in result.output, result.output


@pytest.mark.parametrize('brand', ['cyber', 'ai'])
@pytest.mark.parametrize('keyed', [False, True])
@pytest.mark.parametrize('metadata', [
    {'tool': 'Other Tool'}, {'subject': 'Other Tool@v1'},
    {'scope': 'brand:OTHER'}, {'brand': 'OTHER'}, {'revision': 99},
])
def test_history_rejects_conflicting_decision_context(monkeypatch, brand, keyed, metadata):
    doc = _ledger(brand)
    opposite = 'ai' if brand == 'cyber' else 'cyber'
    metadata = {key: value.replace('OTHER', opposite) if isinstance(value, str) else value
                for key, value in metadata.items()}
    doc['history'][_CID][0].update(metadata)
    result = _invoke_ledger(monkeypatch, doc, brand, keyed)
    assert result.exit_code == 2, result.output


def test_free_history_refuses_withheld_history_content(monkeypatch):
    doc = _ledger('cyber')
    doc['claims'][_CID] = {'revision': 3, 'status': 'unknown', 'withheld': 'evidence_revoked'}
    result = _invoke_ledger(monkeypatch, doc, 'cyber')
    assert result.exit_code == 2, result.output
