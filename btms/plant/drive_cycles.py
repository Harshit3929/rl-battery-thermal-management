"""Download official speed schedules, retaining source hashes and unit conversions.

UDDS is the urban schedule, not the full FTP-75 (which includes a soak/repeat).
NEDC is assembled from four official ECE urban schedules and one EUDC schedule.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen
import numpy as np
from .vehicle import Vehicle

DATA = Path(__file__).resolve().parents[2] / 'data' / 'cycles'
SOURCES = {
    'udds': ('https://www.epa.gov/sites/default/files/2015-10/uddscol.txt', 'mph'),
    'hwfet': ('https://www.epa.gov/sites/default/files/2015-10/hwycol.txt', 'mph'),
    'us06': ('https://www.epa.gov/system/files/other-files/2025-03/us06col.txt', 'mph'),
    'ece': ('https://www.epa.gov/sites/default/files/2015-10/ececol.txt', 'kph'),
    'eudc': ('https://www.epa.gov/sites/default/files/2015-10/eudccol.txt', 'kph'),
}


def parse_trace(text, units):
    rows = []
    for line in text.splitlines():
        fields = line.replace(',', ' ').split()
        if len(fields) != 2:
            continue
        try:
            rows.append(tuple(map(float, fields)))
        except ValueError:
            continue
    data = np.asarray(rows)
    if len(data) < 2 or not np.all(np.diff(data[:, 0]) > 0):
        raise ValueError('Trace must contain strictly increasing timestamps')
    data[:, 1] *= .44704 if units == 'mph' else 1 / 3.6
    return data


def download():
    DATA.mkdir(parents=True, exist_ok=True)
    parts, provenance = {}, {}
    for name, (url, units) in SOURCES.items():
        raw = urlopen(url, timeout=60).read()
        text = raw.decode('utf-8-sig')
        # Refuse an unexpected source-unit change instead of mislabelling data.
        header = '\n'.join(text.splitlines()[:3]).lower()
        expected = ('mph',) if units == 'mph' else ('kph', 'km/h', 'km/hr')
        if not any(token in header for token in expected):
            raise ValueError(f'Inspect source units for {name}: {header}')
        parts[name] = parse_trace(text, units)
        (DATA / f'{name}.source.txt').write_bytes(raw)
        provenance[name] = dict(source_url=url, source_units=units,
              source_sha256=hashlib.sha256(raw).hexdigest(), provenance='real')
    urban, extra = parts['ece'], parts['eudc']
    segments = []
    offset = 0.
    for segment in [urban]*4+[extra]:
        copied = segment.copy()
        copied[:, 0] -= copied[0, 0]
        copied[:, 0] += offset
        segments.append(copied if not segments else copied[1:])
        offset = copied[-1, 0]
    parts['nedc'] = np.concatenate(segments)
    provenance['nedc'] = dict(provenance='real', assembly='ECE x4 + EUDC x1; shared endpoints omitted',
                             sources=[provenance['ece'], provenance['eudc']])
    for name in ['udds', 'hwfet', 'us06', 'nedc']:
        path = DATA / f'{name}.csv'
        np.savetxt(path, parts[name], delimiter=',', header='time_s,speed_mps', comments='', fmt='%.8f')
        provenance[name]['csv_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        (DATA / f'{name}.json').write_text(json.dumps(provenance[name], indent=2))


def load_cycle(name):
    data = np.loadtxt(DATA / f'{name}.csv', delimiter=',', skiprows=1)
    meta = json.loads((DATA / f'{name}.json').read_text())
    actual = hashlib.sha256((DATA / f'{name}.csv').read_bytes()).hexdigest()
    if actual != meta['csv_sha256']:
        raise ValueError(f'Cycle hash mismatch: {name}')
    return data, meta


def power_trace(name, grade=0.):
    data, meta = load_cycle(name)
    # Interval midpoint speed makes inertial work exactly delta(1/2 m v squared).
    dt = np.diff(data[:, 0])
    speed = (data[1:, 1]+data[:-1, 1])/2
    acceleration = np.diff(data[:, 1])/dt
    return data[:-1, 0], dt, Vehicle().battery_power(speed, acceleration, grade), meta


def report():
    rows = []
    for name in ['udds', 'hwfet', 'us06', 'nedc']:
        data, _ = load_cycle(name)
        _, dt, power, meta = power_trace(name)
        distance = np.sum((data[1:, 1]+data[:-1, 1])/2*dt)/1000
        consumption = float(np.sum(power*dt)/3.6e6/distance*100)
        rows.append(dict(cycle=name, duration_s=float(dt.sum()), distance_km=float(distance),
                         kwh_per_100km=consumption, provenance=meta['provenance']))
    print(json.dumps(rows, indent=2))
    destination = DATA.parent.parent/'report'/'results'
    destination.mkdir(parents=True, exist_ok=True)
    (destination/'cycle_report.json').write_text(json.dumps(rows, indent=2))
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    if args.download:
        download()
    if args.report:
        report()
