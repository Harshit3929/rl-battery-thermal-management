"""Create a portable evidence viewer with explicitly recorded rollout replays."""
from __future__ import annotations

import json
import shutil
import zipfile
from .evidence import ROOT, build_evidence


def main():
    destination = ROOT / 'dashboard-site'
    destination.mkdir(exist_ok=True)
    web = ROOT / 'btms/dashboard/web'
    for name in ('index.html', 'style.css', 'app.js'):
        shutil.copy2(web / name, destination / name)
    data = build_evidence()
    (destination / 'evidence.json').write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')
    for artifact in data['artifacts']:
        path = destination / 'artifacts' / artifact['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / artifact['path'], path)
    replay_source = ROOT / 'report/dashboard/replays'
    # Index only actual exported files, including ones produced before a resumed
    # verification. Missing rollouts are not replaced or synthesized.
    replay_index = []
    for name in ('sac', 'pid'):
        for episode in ('hot_s701', 'fastcharge_s701'):
            for mode in ('shielded', 'raw'):
                filename = f'{name}_{episode}_{mode}.json'
                if (replay_source / filename).is_file():
                    replay_index.append(dict(file=filename, label=f'{name.upper()} · {episode} · {mode}'))
    if replay_index:
        (replay_source / 'index.json').write_text(json.dumps(replay_index, indent=2), encoding='utf-8')
    if (replay_source / 'index.json').is_file():
        replay_destination = destination / 'replays'
        replay_destination.mkdir(exist_ok=True)
        for row in json.loads((replay_source / 'index.json').read_text()):
            shutil.copy2(replay_source / row['file'], replay_destination / row['file'])
        shutil.copy2(replay_source / 'index.json', replay_destination / 'index.json')
    instructions = ('RL Battery Lab — recorded evidence edition\n\n'
                    'Serve this directory: python -m http.server 8766 --bind 127.0.0.1\n'
                    'Open http://127.0.0.1:8766 . Do not open index.html directly as a file.\n'
                    'This edition includes actual exported Python simulations as recorded replays.\n'
                    'Fresh simulation requires the main project: python -m btms.dashboard\n'
                    'The artifacts/ folder includes source, inputs and saved actors, without a Python environment.\n'
                    'For fresh execution, install requirements in artifacts/ and run the module from there.\n'
                    'No physical battery measurements are included.\n')
    (destination / 'READ_ME.txt').write_text(instructions, encoding='utf-8')
    archive = ROOT / 'deliverables/RL_Battery_Lab_Evidence.zip'
    # Only files just copied from an explicit allowlist are packaged.
    files = [destination / name for name in ('index.html', 'style.css', 'app.js', 'evidence.json', 'READ_ME.txt')]
    files += [destination / 'artifacts' / a['path'] for a in data['artifacts']]
    if (replay_source / 'index.json').is_file():
        files += [destination / 'replays/index.json']
        files += [destination / 'replays' / row['file'] for row in json.loads((replay_source / 'index.json').read_text())]
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in files:
            zipped.write(path, path.relative_to(destination))
    print(f'Evidence viewer: {destination}\nPortable archive: {archive} ({archive.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
