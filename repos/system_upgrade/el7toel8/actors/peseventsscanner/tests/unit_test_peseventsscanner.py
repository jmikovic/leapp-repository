import os.path

import pytest

from leapp.exceptions import StopActorExecution
from leapp.libraries.actor import peseventsscanner
from leapp.libraries.actor.peseventsscanner import (
    Action,
    Event,
    Task,
    add_output_pkgs_to_transaction_conf,
    filter_out_pkgs_in_blacklisted_repos,
    filter_events_by_architecture,
    filter_events_by_releases,
    filter_releases_by_target,
    get_events,
    map_repositories, parse_action,
    parse_entry, parse_packageset,
    parse_pes_events_file,
    process_events,
    report_skipped_packages)
from leapp import reporting
from leapp.libraries.common.testutils import produce_mocked, create_report_mocked
from leapp.libraries.stdlib import api
from leapp.models import RpmTransactionTasks

CUR_DIR = os.path.dirname(os.path.abspath(__file__))


class show_message_mocked(object):
    def __init__(self):
        self.called = 0
        self.msg = None

    def __call__(self, msg):
        self.called += 1
        self.msg = msg


class get_repos_blacklisted_mocked(object):
    def __init__(self, blacklisted):
        self.blacklisted = blacklisted

    def __call__(self):
        return self.blacklisted


def test_parse_action(current_actor_context):
    for i in range(8):
        assert parse_action(i) == Action(i)

    with pytest.raises(ValueError):
        parse_action(-1)
        parse_action(8)


def test_parse_packageset(current_actor_context):
    pkgset = {'package': [{'name': 'pkg1', 'repository': 'Repo'}]}

    assert parse_packageset(pkgset) == {'pkg1': 'repo'}

    assert parse_packageset({}) == {}
    assert parse_packageset({'setid': 0}) == {}


def test_parse_entry(current_actor_context):
    entry = {
        'action': 4,
        'in_packageset': {
            'package': [{'name': 'original', 'repository': 'repo'}]},
        'out_packageset': {
            'package': [
                {'name': 'split01', 'repository': 'repo'},
                {'name': 'split02', 'repository': 'repo'}]}}

    event = parse_entry(entry)
    assert event.action == Action.split
    assert event.in_pkgs == {'original': 'repo'}
    assert event.out_pkgs == {'split01': 'repo', 'split02': 'repo'}

    entry = {
        'action': 1,
        'in_packageset': {
            'package': [{'name': 'removed', 'repository': 'repo'}]}}

    event = parse_entry(entry)
    assert event.action == Action.removed
    assert event.in_pkgs == {'removed': 'repo'}
    assert event.out_pkgs == {}


def test_parse_pes_events_file(current_actor_context):
    events = parse_pes_events_file(os.path.join(CUR_DIR, 'files/sample01.json'))
    assert len(events) == 2
    assert events[0].action == Action.split
    assert events[0].in_pkgs == {'original': 'repo'}
    assert events[0].out_pkgs == {'split01': 'repo', 'split02': 'repo'}
    assert events[1].action == Action.removed
    assert events[1].in_pkgs == {'removed': 'repo'}
    assert events[1].out_pkgs == {}


def test_report_skipped_packages(monkeypatch):
    monkeypatch.setattr(api, 'produce', produce_mocked())
    monkeypatch.setattr(api, 'show_message', show_message_mocked())
    monkeypatch.setattr(reporting, 'create_report', create_report_mocked())
    monkeypatch.setenv('LEAPP_VERBOSE', '1')
    report_skipped_packages('packages will not be installed:', ['skipped01', 'skipped02'])

    message = '2 packages will not be installed:\n- skipped01\n- skipped02'
    assert api.show_message.called == 1
    assert api.show_message.msg == message
    assert reporting.create_report.called == 1
    assert reporting.create_report.report_fields['title'] == 'Packages will not be installed'
    assert reporting.create_report.report_fields['summary'] == message


def test_report_skipped_packages_no_verbose_mode(monkeypatch):
    monkeypatch.setattr(api, 'produce', produce_mocked())
    monkeypatch.setattr(api, 'show_message', show_message_mocked())
    monkeypatch.setattr(reporting, 'create_report', create_report_mocked())
    monkeypatch.setenv('LEAPP_VERBOSE', '0')
    report_skipped_packages('packages will not be installed:', ['skipped01', 'skipped02'])

    message = '2 packages will not be installed:\n- skipped01\n- skipped02'
    assert api.show_message.called == 0
    assert reporting.create_report.called == 1
    assert reporting.create_report.report_fields['title'] == 'Packages will not be installed'
    assert reporting.create_report.report_fields['summary'] == message


def test_filter_out_pkgs_in_blacklisted_repos(monkeypatch):
    monkeypatch.setattr(api, 'show_message', show_message_mocked())
    monkeypatch.setattr(reporting, 'create_report', create_report_mocked())
    monkeypatch.setattr(peseventsscanner, 'get_repositories_blacklisted',
                        get_repos_blacklisted_mocked(set(['blacklisted'])))
    monkeypatch.setenv('LEAPP_VERBOSE', '1')

    to_install = {
        'pkg01': 'repo01',
        'pkg02': 'repo02',
        'skipped01': 'blacklisted',
        'skipped02': 'blacklisted'}
    filter_out_pkgs_in_blacklisted_repos(to_install)

    msgs = [
        '2 packages will not be installed due to blacklisted repositories:',
        '- skipped01',
        '- skipped02']
    assert api.show_message.called == 1
    assert api.show_message.msg == '\n'.join(msgs)
    assert reporting.create_report.called == 1
    assert reporting.create_report.report_fields['summary'] == '\n'.join(msgs)
    assert reporting.create_report.report_fields['title'] == 'Packages will not be installed'

    assert to_install == {'pkg01': 'repo01', 'pkg02': 'repo02'}


def test_resolve_conflicting_requests(monkeypatch):
    monkeypatch.setattr(peseventsscanner, 'map_repositories', lambda x: x)
    monkeypatch.setattr(peseventsscanner, 'filter_out_pkgs_in_blacklisted_repos', lambda x: x)

    events = [
        Event(Action.split, {'sip-devel': 'repo'}, {'python3-sip-devel': 'repo', 'sip': 'repo'}, (7, 6), (8, 0), []),
        Event(Action.split, {'sip': 'repo'}, {'python3-pyqt5-sip': 'repo', 'python3-sip': 'repo'}, (7, 6), (8, 0), [])]
    installed_pkgs = {'sip', 'sip-devel'}

    tasks = process_events([(8, 0)], events, installed_pkgs)

    assert tasks[Task.install] == {'python3-sip-devel': 'repo', 'python3-pyqt5-sip': 'repo', 'python3-sip': 'repo'}
    assert tasks[Task.remove] == {'sip-devel': 'repo'}
    assert tasks[Task.keep] == {'sip': 'repo'}


def test_map_repositories(monkeypatch):
    monkeypatch.setattr(api, 'show_message', show_message_mocked())
    monkeypatch.setattr(peseventsscanner, '_get_repositories_mapping', lambda: {'repo': 'mapped'})
    monkeypatch.setattr(reporting, 'create_report', create_report_mocked())
    monkeypatch.setenv('LEAPP_VERBOSE', '1')

    to_install = {
        'pkg01': 'repo',
        'pkg02': 'repo',
        'skipped01': 'not_mapped',
        'skipped02': 'not_mapped'}
    map_repositories(to_install)

    msgs = [
        '2 packages will not be installed or upgraded due to repositories unknown to leapp:',
        '- skipped01',
        '- skipped02']
    assert api.show_message.called == 1
    assert api.show_message.msg == '\n'.join(msgs)
    assert reporting.create_report.called == 1
    assert reporting.create_report.report_fields['title'] == 'Packages will not be installed'
    assert reporting.create_report.report_fields['summary'] == '\n'.join(msgs)

    assert to_install == {'pkg01': 'mapped', 'pkg02': 'mapped'}


def test_process_events(monkeypatch):
    monkeypatch.setattr(peseventsscanner, '_get_repositories_mapping', lambda: {'rhel8-repo': 'rhel8-mapped'})
    monkeypatch.setattr(peseventsscanner, 'get_repositories_blacklisted', get_repos_blacklisted_mocked(set()))

    events = [
        Event(Action.split, {'original': 'rhel7-repo'}, {'split01': 'rhel8-repo', 'split02': 'rhel8-repo'},
              (7, 6), (8, 0), []),
        Event(Action.removed, {'removed': 'rhel7-repo'}, {}, (7, 6), (8, 0), []),
        Event(Action.present, {'present': 'rhel8-repo'}, {}, (7, 6), (8, 0), []),
        # this package is present at the start, gets removed and then reintroduced
        Event(Action.removed, {'reintroduced': 'rhel7-repo'}, {}, (7, 6), (8, 0), []),
        Event(Action.present, {'reintroduced': 'rhel8-repo'}, {}, (8, 0), (8, 1), []),
        # however, this package was never there
        Event(Action.removed, {'neverthere': 'rhel7-repo'}, {}, (7, 6), (8, 0), []),
        Event(Action.present, {'neverthere': 'rhel8-repo'}, {}, (8, 0), (8, 1), [])]
    installed_pkgs = {'original', 'removed', 'present', 'reintroduced'}
    tasks = process_events([(8, 0), (8, 1)], events, installed_pkgs)

    assert tasks[Task.install] == {'split02': 'rhel8-mapped', 'split01': 'rhel8-mapped'}
    assert tasks[Task.remove] == {'removed': 'rhel7-repo', 'original': 'rhel7-repo'}
    assert tasks[Task.keep] == {'present': 'rhel8-mapped', 'reintroduced': 'rhel8-mapped'}


def test_get_events(monkeypatch):
    monkeypatch.setattr(reporting, 'create_report', create_report_mocked())

    with pytest.raises(StopActorExecution):
        get_events(os.path.join(CUR_DIR, 'files/sample02.json'))
    assert reporting.create_report.called == 1
    assert 'inhibitor' in reporting.create_report.report_fields['flags']

    reporting.create_report.called = 0
    reporting.create_report.model_instances = []
    with pytest.raises(StopActorExecution):
        get_events(os.path.join(CUR_DIR, 'files/sample03.json'))
    assert reporting.create_report.called == 1
    assert 'inhibitor' in reporting.create_report.report_fields['flags']


def test_pes_data_not_found(monkeypatch):
    def file_not_exists(_filepath):
        return False

    monkeypatch.setattr(os.path, 'isfile', file_not_exists)
    monkeypatch.setattr(reporting, 'create_report', create_report_mocked())
    with pytest.raises(StopActorExecution):
        get_events('/etc/leapp/pes-data.json')
    assert reporting.create_report.called == 1
    assert 'inhibitor' in reporting.create_report.report_fields['flags']


def test_add_output_pkgs_to_transaction_conf():
    events = [
        Event(Action.split, {'split_in': 'repo'}, {'split_out1': 'repo', 'split_out2': 'repo'}, (7, 6), (8, 0), []),
        Event(Action.merged, {'merged_in1': 'repo', 'merged_in2': 'repo'}, {'merged_out': 'repo'}, (7, 6), (8, 0), []),
        Event(Action.renamed, {'renamed_in': 'repo'}, {'renamed_out': 'repo'}, (7, 6), (8, 0), []),
        Event(Action.replaced, {'replaced_in': 'repo'}, {'replaced_out': 'repo'}, (7, 6), (8, 0), []),
    ]

    conf_empty = RpmTransactionTasks()
    add_output_pkgs_to_transaction_conf(conf_empty, events)
    assert conf_empty.to_remove == []

    conf_split = RpmTransactionTasks(to_remove=['split_in'])
    add_output_pkgs_to_transaction_conf(conf_split, events)
    assert sorted(conf_split.to_remove) == ['split_in', 'split_out1', 'split_out2']

    conf_merged_incomplete = RpmTransactionTasks(to_remove=['merged_in1'])
    add_output_pkgs_to_transaction_conf(conf_merged_incomplete, events)
    assert conf_merged_incomplete.to_remove == ['merged_in1']

    conf_merged = RpmTransactionTasks(to_remove=['merged_in1', 'merged_in2'])
    add_output_pkgs_to_transaction_conf(conf_merged, events)
    assert sorted(conf_merged.to_remove) == ['merged_in1', 'merged_in2', 'merged_out']

    conf_renamed = RpmTransactionTasks(to_remove=['renamed_in'])
    add_output_pkgs_to_transaction_conf(conf_renamed, events)
    assert sorted(conf_renamed.to_remove) == ['renamed_in', 'renamed_out']

    conf_replaced = RpmTransactionTasks(to_remove=['replaced_in'])
    add_output_pkgs_to_transaction_conf(conf_replaced, events)
    assert sorted(conf_replaced.to_remove) == ['replaced_in', 'replaced_out']


def test_filter_events_by_architecture():
    events = [
        Event(Action.present, {'pkg1': 'repo'}, {}, (7, 6), (8, 0), ['arch1']),
        Event(Action.present, {'pkg2': 'repo'}, {}, (7, 6), (8, 0), ['arch2', 'arch1', 'arch3']),
        Event(Action.present, {'pkg3': 'repo'}, {}, (7, 6), (8, 0), ['arch2', 'arch3', 'arch4']),
        Event(Action.present, {'pkg4': 'repo'}, {}, (7, 6), (8, 0), [])
    ]

    filtered = filter_events_by_architecture(events, 'arch1')
    assert {'pkg1': 'repo'} in [event.in_pkgs for event in filtered]
    assert {'pkg2': 'repo'} in [event.in_pkgs for event in filtered]
    assert {'pkg3': 'repo'} not in [event.in_pkgs for event in filtered]
    assert {'pkg4': 'repo'} in [event.in_pkgs for event in filtered]


def test_filter_events_by_releases():
    events = [
        Event(Action.present, {'pkg1': 'repo'}, {}, (7, 6), (7, 7), []),
        Event(Action.present, {'pkg2': 'repo'}, {}, (7, 7), (7, 8), []),
        Event(Action.present, {'pkg3': 'repo'}, {}, (7, 8), (8, 0), []),
        Event(Action.present, {'pkg4': 'repo'}, {}, (8, 0), (8, 1), []),
        Event(Action.present, {'pkg5': 'repo'}, {}, (8, 1), (8, 2), [])
    ]

    filtered = filter_events_by_releases(events, [(7, 6), (7, 7), (8, 0), (8, 3)])
    assert {'pkg1': 'repo'} in [event.in_pkgs for event in filtered]
    assert {'pkg2': 'repo'} not in [event.in_pkgs for event in filtered]
    assert {'pkg3': 'repo'} in [event.in_pkgs for event in filtered]
    assert {'pkg4': 'repo'} not in [event.in_pkgs for event in filtered]
    assert {'pkg5': 'repo'} not in [event.in_pkgs for event in filtered]


def test_filter_releases_by_target():
    releases = [(7, 6), (7, 7), (7, 8), (7, 9), (8, 0), (8, 1), (8, 2), (8, 3), (9, 0), (9, 1)]
    filtered_releases = filter_releases_by_target(releases, (8, 1))
    assert filtered_releases == [(7, 6), (7, 7), (7, 8), (7, 9), (8, 0), (8, 1)]
