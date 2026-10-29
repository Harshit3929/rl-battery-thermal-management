"""Checks evidence aggregation, actual policy execution and HTTP boundaries."""
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from btms.dashboard.evidence import aggregate, audit, get_runs, read_json, recorded_episodes, ROOT
from btms.dashboard.server import handler_for
from btms.dashboard.simulation import simulate


def test_raw_episodes_reproduce_manuscript_tables():
    rows = recorded_episodes()
    result = audit(aggregate(rows), rows, get_runs())
    failures = [r for r in result['checks'] if r['status'] != 'pass']
    assert not failures, failures


def test_detects_changed_recorded_episode():
    rows = recorded_episodes()
    rows[0] = dict(rows[0], cost=rows[0]['cost'] + 1000)
    result = audit(aggregate(rows), rows, get_runs(include_curves=False))
    assert next(c for c in result['checks'] if c['name'].startswith('Aggregated'))['status'] == 'fail'


def test_fresh_pid_episode_matches_saved_result_and_time_zero():
    spec = next(r for r in read_json(ROOT / 'data/evaluation_episodes.json') if r['id'] == 'hot_s701')
    result = simulate(spec, 'pid', True)
    assert result['reproduces_recorded_metrics'], result['recorded_comparison']
    assert result['trace'][0]['time_s'] == 0
    assert result['trace'][0]['raw_action'] is None
    assert result['trace'][-1]['time_s'] == result['metrics']['duration_s'] == 1800
    assert result['source_sha256']['btms/envs/btms_env.py']


def test_fresh_sac_checkpoint_reproduces_raw_episode():
    spec = next(r for r in read_json(ROOT / 'data/evaluation_episodes.json') if r['id'] == 'hot_s701')
    result = simulate(spec, 'sac', False, 0)
    assert result['reproduces_recorded_metrics'], result['recorded_comparison']
    assert result['checkpoint']['completed_steps'] == 20000
    assert result['metrics']['violation_seconds'] > 0
    assert result['metrics']['shield_seconds'] == 0


def test_http_rejects_unlisted_files_and_invalid_jobs():
    class App:
        allowed = {'requirements.txt'}
        fingerprints = {'requirements.txt': 'changed-file-fingerprint'}
        evidence = {'evaluation_manifest': []}
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(App()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base + '/api/health') as response:
            assert json.load(response)['backend'] == 'python'
        for path in ('/api/artifact?path=../requirements.txt', '/.git/config'):
            with pytest.raises(HTTPError) as error:
                urlopen(base + path)
            assert error.value.code == 404
        with pytest.raises(HTTPError) as error:
            urlopen(base + '/api/artifact?path=requirements.txt')
        assert error.value.code == 409
        request = Request(base + '/api/runs', data=b'{}', headers={'Content-Type': 'application/json'})
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 400
        request = Request(base + '/api/runs', data=b'{}', headers={'Origin': 'https://example.org'})
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
