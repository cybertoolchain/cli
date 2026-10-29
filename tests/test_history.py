from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from toolchain.main import cli


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
                'clm_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb': {'subject': 'Other Tool@v1', 'revision': 9},
            }, 'history': {'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa': [{'revision': 3, 'role': 'the editor',
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
            return {'brand': 'cyber', 'claims': {'clm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa': {'subject': 'Vendor Tool@v1', 'revision': 3}}}

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
