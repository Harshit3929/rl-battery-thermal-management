"""Capture actual test output and reproduce saved controller metrics.

Run with --full for every saved learned-policy episode and all inexpensive
baselines. Sampling MPC is explicitly excluded from that reproduction budget.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from .evidence import ROOT, digest, read_json, stamp
from .simulation import simulate, source_fingerprints


def execute_selection(selection):
    name, seed, shield, episode = selection
    return name, seed, shield, episode, simulate(episode, name, shield, seed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--tests-only', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error('--workers must be between one and four')
    destination = ROOT / 'report/dashboard'
    destination.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
               'tests/test_plant.py', 'tests/test_env.py', 'tests/test_dashboard.py']
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    report = dict(completed_at=stamp(), command=' '.join(command), returncode=process.returncode,
                  output=process.stdout + process.stderr,
                  test_source_sha256={p: digest(ROOT / p) for p in
                                      ('tests/test_plant.py', 'tests/test_env.py', 'tests/test_dashboard.py')},
                  implementation_source_sha256={**source_fingerprints(),
                                                **{f'btms/dashboard/{p.name}': digest(p)
                                                   for p in (ROOT / 'btms/dashboard').glob('*.py')}})
    (destination / 'test_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(report['output'], flush=True)
    if process.returncode:
        raise SystemExit(process.returncode)
    if args.tests_only:
        return
    manifest = read_json(ROOT / 'data/evaluation_episodes.json')
    selections = ([(name, seed, shield, episode) for name in ('sac', 'ppo', 'td3')
                   for seed in range(5) for shield in (True, False) for episode in manifest]
                  + [(name, 0, shield, episode) for name in ('pid', 'null', 'bangbang')
                     for shield in (True, False) for episode in manifest]
                  if args.full else
                  [(name, 0, shield, episode) for name in ('sac', 'pid') for shield in (True, False)
                   for episode in manifest if episode['id'] in ('hot_s701', 'fastcharge_s701')])
    rows = []
    previous_path = destination / 'reproduction.json'
    if args.resume and previous_path.is_file():
        previous = read_json(previous_path)
        if previous['planned_checks'] != len(selections):
            raise ValueError('Cannot resume a different reproduction scope')
        current_hashes = source_fingerprints()
        if any(r['source_sha256'] != current_hashes for r in previous['runs']):
            raise ValueError('Source fingerprints changed; run without --resume')
        rows = previous['runs']
    done = {(r['controller'], r['training_seed'], r['shield'], r['episode_id']) for r in rows}
    remaining = [s for s in selections if (s[0], s[1], s[2], s[3]['id']) not in done]
    replay_directory = destination / 'replays'
    replay_directory.mkdir(exist_ok=True)
    replay_index = (read_json(replay_directory / 'index.json')
                    if args.resume and (replay_directory / 'index.json').is_file() else [])
    # Spawn is used by Windows. Each process retains its own immutable actors;
    # no random training or shared mutable environment enters this evaluation.
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
      futures = [pool.submit(execute_selection, selection) for selection in remaining]
      for future in as_completed(futures):
        name, seed, shield, episode, result = future.result()
        row = dict(controller=name, training_seed=seed, shield=shield, episode_id=episode['id'],
                   matches=result['reproduces_recorded_metrics'],
                   differences=result['recorded_comparison'], completed_at=result['completed_at'],
                   source_sha256=result['source_sha256'], checkpoint=result['checkpoint'])
        rows.append(row)
        if name in ('sac', 'pid') and seed == 0 and episode['id'] in ('hot_s701', 'fastcharge_s701'):
            filename = f'{name}_{episode["id"]}_{"shielded" if shield else "raw"}.json'
            payload = dict(id=filename.removesuffix('.json'), status='complete', request={}, results=[result])
            (replay_directory / filename).write_text(json.dumps(payload, allow_nan=False), encoding='utf-8')
            replay_index.append(dict(file=filename, label=f'{name.upper()} · {episode["id"]} · supervisor {"on" if shield else "off"}'))
            (replay_directory / 'index.json').write_text(json.dumps(replay_index, indent=2), encoding='utf-8')
        print(f'{len(rows)}/{len(selections)} {name} seed={seed} {episode["id"]} shield={shield}: '
              f'{"MATCH" if row["matches"] else "DIFFERENCE"}', flush=True)
        summary = dict(completed_at=stamp(), mode='full except sampling MPC' if args.full else 'selected episodes',
                       all_match=all(r['matches'] for r in rows), planned_checks=len(selections),
                       complete=len(rows) == len(selections), excluded=['sampling MPC'], runs=rows)
        (destination / 'reproduction.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (replay_directory / 'index.json').write_text(json.dumps(replay_index, indent=2), encoding='utf-8')
    if not all(r['matches'] for r in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
