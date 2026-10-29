"""Read original artifacts and check internal consistency, without rewriting them.

An internally consistent artifact is not proof of its historical authenticity or
physical validation. Every check reports its scope; missing data is an error.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import statistics
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / 'report/results'
STUDY = ROOT / 'outputs/study_20000'
METRICS = ('cost', 'aux_wh', 'aging_exposure_s', 'violation_percent',
           'shield_firing_percent', 'max_temperature_c', 'spatial_delta_c', 'duration_s')


def stamp():
    return datetime.now(timezone.utc).isoformat()


def relative(path):
    return Path(path).relative_to(ROOT).as_posix()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def recorded_episodes():
    rows = list(read_json(RESULTS / 'policy_evaluations.json'))
    for name in ('pid', 'null', 'bangbang', 'mpc'):
        for mode in ('raw', 'shielded'):
            rows.extend(dict(row, seed=None) for row in
                        read_json(RESULTS / f'{name}_{mode}_evaluation.json'))
    return rows


def aggregate(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row['controller'], row['shield'])].append(row)
    output = []
    for (name, shield), group in sorted(groups.items()):
        seeds = defaultdict(list)
        for row in group:
            seeds[row.get('seed')].append(row)
        result = dict(algo=name, shield=shield, n_seeds=len(seeds),
                      episodes_per_seed=len(group) // len(seeds))
        for metric in METRICS:
            values = ([statistics.mean(r[metric] for r in seed_rows)
                       for seed_rows in seeds.values()] if len(seeds) > 1
                      else [r[metric] for r in group])
            result[f'{metric}_mean'] = statistics.mean(values)
            result[f'{metric}_std'] = statistics.stdev(values) if len(values) > 1 else 0.
        result['std_definition'] = ('between training-seed episode means' if len(seeds) > 1
                                    else 'between evaluation episodes')
        output.append(result)
    return output


def get_runs(include_curves=True):
    runs = []
    for algorithm in ('ppo', 'sac', 'td3'):
        for seed in range(5):
            folder = STUDY / f'{algorithm}_mixed_seed{seed}'
            for metadata_path in sorted(folder.glob('*/metadata.json')):
                base = metadata_path.parent
                metadata = read_json(metadata_path)
                checkpoint = base / 'latest.pt'
                events = sorted((base / 'tensorboard').glob('*/events.out.tfevents.*'))
                curve, error = [], None
                if include_curves:
                    try:
                        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
                        values = {}
                        for path in events:
                            accumulator = EventAccumulator(str(path), size_guidance={'scalars': 0})
                            accumulator.Reload()
                            tags = accumulator.Tags().get('scalars', [])
                            if 'eval/return' in tags:
                                values.update({r.step: dict(step=r.step, value=r.value, wall_time=r.wall_time)
                                               for r in accumulator.Scalars('eval/return')})
                        curve = [values[key] for key in sorted(values)]
                    except Exception as exc:
                        error = f'{type(exc).__name__}: {exc}'
                valid_zip = False
                if checkpoint.is_file():
                    try:
                        with zipfile.ZipFile(checkpoint) as archive:
                            valid_zip = archive.testzip() is None
                    except zipfile.BadZipFile:
                        pass
                runs.append(dict(algorithm=algorithm, seed=seed, path=relative(base),
                                 metadata=metadata, checkpoint=relative(checkpoint),
                                 checkpoint_bytes=checkpoint.stat().st_size if checkpoint.is_file() else 0,
                                 checkpoint_sha256=digest(checkpoint) if checkpoint.is_file() else None,
                                 checkpoint_container_valid=valid_zip,
                                 events=[relative(p) for p in events], curve=curve,
                                 curve_error=error,
                                 config=relative(base / '.hydra/config.yaml')))
    return runs


def find_run(algorithm, seed):
    paths = sorted((STUDY / f'{algorithm}_mixed_seed{seed}').glob('*/latest.pt'))
    if len(paths) != 1:
        raise ValueError(f'Expected one checkpoint for {algorithm} seed {seed}; found {len(paths)}')
    return paths[0]


def audit(comparisons, episodes, runs):
    checks = []

    def check(name, ok, detail, sources):
        checks.append(dict(name=name, status='pass' if ok else 'fail', detail=detail, sources=sources))

    recorded = read_csv(RESULTS / 'controller_comparison.csv')
    mismatches = []
    for saved in recorded:
        calculated = next((r for r in comparisons if r['algo'] == saved['algo'] and
                           r['shield'] == (saved['shield'].lower() == 'true')), None)
        for metric in METRICS:
            for suffix in ('mean', 'std'):
                key = f'{metric}_{suffix}'
                if calculated is None or not math.isclose(float(saved[key]), calculated[key], rel_tol=1e-9, abs_tol=1e-8):
                    mismatches.append(f"{saved['algo']}/{saved['shield']}/{key}")
    check('Aggregated means reproduce from episode records', len(recorded) == len(comparisons) and not mismatches,
          f'{len(recorded)} controller/mode rows; {len(METRICS)} means and standard deviations checked per row. Differences: {mismatches}',
          ['report/results/controller_comparison.csv', 'report/results/policy_evaluations.json'])
    manifest = read_json(ROOT / 'data/evaluation_episodes.json')
    expected_ids = {row['id'] for row in manifest}
    groups = defaultdict(list)
    for row in episodes:
        groups[(row['controller'], row.get('seed'), row['shield'])].append(row['episode_id'])
    check('Every evaluated controller uses the fixed eight episodes',
          len(expected_ids) == 8 and all(len(ids) == 8 and set(ids) == expected_ids for ids in groups.values()),
          f'{len(groups)} controller/seed/mode groups checked, including duplicate/missing episode detection.',
          ['data/evaluation_episodes.json', 'report/results/policy_evaluations.json'])
    check('Recorded training containers and event scalars are readable',
          len(runs) == 15 and all(r['checkpoint_container_valid'] and r['curve'] and
                                max(p['step'] for p in r['curve']) == r['metadata']['completed_steps'] for r in runs),
          'Checks ZIP integrity and event steps against metadata; does not certify historical authenticity or load every actor.',
          [r['path'] for r in runs])
    tex = (ROOT / 'deliverables/IEEE_BTMS_Manuscript.tex').read_text(encoding='utf-8-sig')
    labels = {'Sampling MPC': 'mpc', 'Tuned PID': 'pid', 'TD3': 'td3', 'SAC': 'sac',
              'PPO': 'ppo', 'Null with shield': 'null', 'Null': 'null', 'Bang-bang': 'bangbang'}
    for table, shield in (('shielded', True), ('raw', False)):
        block = tex.split('\\label{tab:' + table + '}')[1].split('\\end{table}')[0]
        failures, count = [], 0
        for line in block.splitlines():
            fields = [s.strip() for s in line.split('&')]
            if fields[0] not in labels:
                continue
            values = [float(re.search(r'[\d.]+', field).group()) for field in fields[1:]]
            row = next(r for r in comparisons if r['algo'] == labels[fields[0]] and r['shield'] == shield)
            expected = ([row['cost_mean'], row['aux_wh_mean'], row['shield_firing_percent_mean']]
                        if shield else [row['cost_mean'], row['violation_percent_mean']])
            tolerances = [0.05000001, 0.05000001, 0.00500001] if shield else [0.05000001, 0.00500001]
            count += 1
            if len(values) != len(expected) or not all(abs(a-b) <= tol for a, b, tol in zip(values, expected, tolerances)):
                failures.append(dict(controller=fields[0], paper=values, calculated=expected))
        check(f'Manuscript {table} table matches recalculated values', count == 7 and not failures,
              f'{count} rows checked at printed precision. Differences: {failures}',
              ['deliverables/IEEE_BTMS_Manuscript.tex', 'report/results/controller_comparison.csv'])
    hashes = []
    for name in ('udds', 'hwfet', 'us06', 'nedc'):
        meta = read_json(ROOT / f'data/cycles/{name}.json')
        hashes.append(dict(cycle=name, ok=digest(ROOT / f'data/cycles/{name}.csv') == meta['csv_sha256']))
    for name in ('udds', 'hwfet', 'us06'):
        meta = read_json(ROOT / f'data/cycles/{name}.json')
        hashes.append(dict(source=name, ok=digest(ROOT / f'data/cycles/{name}.source.txt') == meta['source_sha256']))
    nedc = read_json(ROOT / 'data/cycles/nedc.json')
    for name, source in zip(('ece', 'eudc'), nedc['sources']):
        hashes.append(dict(source=name, ok=digest(ROOT / f'data/cycles/{name}.source.txt') == source['source_sha256']))
    check('Driving CSVs and retained source hashes match provenance', all(h['ok'] for h in hashes),
          json.dumps(hashes) + ' Local integrity check; no new remote download.',
          ['data/cycles/udds.json', 'data/cycles/hwfet.json', 'data/cycles/us06.json', 'data/cycles/nedc.json'])
    return dict(checked_at=stamp(), checks=checks,
                scope='Internal consistency of saved artifacts and the current TeX result tables. This is not a proof that nothing was fabricated historically.',
                limits=['No physical battery measurements or hardware validation.',
                        'Literature references and DOCX/PPTX/PDF versions are outside this automated table audit.',
                        'Saved benchmarks are recorded laptop results, not fresh timings or ECU certification.',
                        'Mean episode percentages give each episode equal weight; they are not pooled time-weighted percentages.',
                        'Thermal/cooling parameters and aging exposure are modeling assumptions; aging is not capacity loss.',
                        'Historical test claims are separate from the timestamped current test report.'])


def artifact_catalog(runs):
    paths = [ROOT / 'README.md', ROOT / 'deliverables/IEEE_BTMS_Manuscript.tex',
             ROOT / 'deliverables/IEEE_BTMS_Manuscript.json', ROOT / 'deliverables/IEEE_BTMS_References.json',
             ROOT / 'output/pdf/IEEE_BTMS_Research_Paper_Formatted.pdf', ROOT / 'docs/ARCHITECTURE.md',
             ROOT / 'docs/IMPLEMENTATION_STATUS.md', ROOT / 'docs/TRACEABILITY_REVIEW.md',
             ROOT / 'requirements.txt', ROOT / 'data/evaluation_episodes.json', ROOT / 'data/tuning_episodes.json']
    paths += sorted(RESULTS.glob('*.json')) + sorted(RESULTS.glob('*.csv')) + sorted(RESULTS.glob('*.png'))
    for run in runs:
        base = ROOT / run['path']
        paths += [base / 'metadata.json', base / '.hydra/config.yaml', ROOT / run['checkpoint']]
        paths += [ROOT / p for p in run['events']]
        paths += sorted((base / 'checkpoints').glob('*/model.zip'))
    for name in ('udds', 'hwfet', 'us06', 'nedc'):
        paths += [ROOT / f'data/cycles/{name}.csv', ROOT / f'data/cycles/{name}.json']
    paths += [ROOT / f'data/cycles/{name}.source.txt' for name in ('udds', 'hwfet', 'us06', 'ece', 'eudc')]
    for name in ('test_report.json', 'reproduction.json', 'browser_test.json', 'mpc_spotcheck.json', 'static_test.json'):
        paths.append(ROOT / 'report/dashboard' / name)
    for name in ('simulation-desktop.png', 'simulation-mobile.png', 'results-desktop.png',
                 'training-desktop.png', 'evidence-desktop.png'):
        paths.append(ROOT / 'report/dashboard/screenshots' / name)
    paths += [ROOT / 'btms' / '__init__.py']
    paths += [ROOT / 'btms/train.py', ROOT / 'btms/configs/config.yaml']
    for directory in ('agent', 'scenario'):
        paths += list((ROOT / 'btms/configs' / directory).glob('*.yaml'))
    paths += [ROOT / 'btms/dashboard/web' / name for name in ('index.html', 'style.css', 'app.js')]
    for directory in ('plant', 'envs', 'controllers', 'agents', 'analysis', 'utils', 'dashboard'):
        paths += list((ROOT / 'btms' / directory).glob('*.py'))
    paths += list((ROOT / 'tests').glob('test_*.py'))
    paths += [ROOT / 'docs/DASHBOARD.md', ROOT / 'docs/PAPER_EVIDENCE_AUDIT.md']
    paths += [ROOT / 'scripts/build_research_paper.py', ROOT / 'scripts/check_research_paper.py',
              ROOT / 'deliverables/IEEE_BTMS_Submission_Notes.md', ROOT / 'requirements-paper.txt']
    paths += [ROOT / f'report/paper_revision/figures/figure_{n}.png' for n in range(1,7)]
    paths += [ROOT / 'report/paper_revision' / name for name in
              ('validation.json','build_manifest.json','REVISION.md','visual_review.json','dashboard_check.json')]
    paths += [ROOT / f'report/dashboard/replays/{name}_{episode}_{mode}.json'
              for name in ('sac','pid') for episode in ('hot_s701','fastcharge_s701')
              for mode in ('shielded','raw')]
    paths = sorted(set(p for p in paths if p.is_file()))
    return [dict(path=relative(p), bytes=p.stat().st_size, sha256=digest(p)) for p in paths]


def build_evidence():
    episodes = recorded_episodes()
    comparisons = aggregate(episodes)
    runs = get_runs()
    audit_result = audit(comparisons, episodes, runs)
    optional = {}
    for name in ('test_report', 'reproduction', 'browser_test', 'mpc_spotcheck', 'static_test'):
        path = ROOT / 'report/dashboard' / f'{name}.json'
        optional[name] = read_json(path) if path.is_file() else None
    paper_report=ROOT/'report/paper_revision/validation.json'
    optional['paper_revision']=read_json(paper_report) if paper_report.is_file() else None
    if optional['paper_revision']:
        registry=read_json(ROOT/'deliverables/IEEE_BTMS_References.json')['references']
        optional['paper_revision']['reference_count']=len(registry)
        optional['paper_revision']['recent_reference_count']=sum(r.get('year',0)>=2025 for r in registry)
    return dict(generated_at=stamp(), data_kind='recorded simulation artifacts',
                comparisons=comparisons, episodes=episodes, runs=runs,
                evaluation_manifest=read_json(ROOT / 'data/evaluation_episodes.json'),
                benchmark=read_json(RESULTS / 'deployment_benchmark_sac_seed0.json'),
                hardness=read_json(RESULTS / 'hardness_gate.json'),
                cycles=[dict(cycle=n, **read_json(ROOT / f'data/cycles/{n}.json'))
                        for n in ('udds', 'hwfet', 'us06', 'nedc')],
                audit=audit_result, artifacts=artifact_catalog(runs), **optional)


def main():
    destination = ROOT / 'report/dashboard'
    destination.mkdir(parents=True, exist_ok=True)
    data = build_evidence()
    (destination / 'evidence.json').write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(data['audit'], indent=2))
    if any(c['status'] == 'fail' for c in data['audit']['checks']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
