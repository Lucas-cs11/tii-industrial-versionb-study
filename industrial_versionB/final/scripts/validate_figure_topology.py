#!/usr/bin/env python3
"""Bidirectional exact arc-set validation between model and generated DOT/PDF."""
from __future__ import annotations
import json, re, subprocess, sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / 'figures'
MODEL = HERE / 'models' / 'versionB_before.json'


def model_arcs(model):
    arcs = Counter()
    for t in model['transitions']:
        for p, w in t['inputs'].items():
            arcs[(p, t['id'], int(w))] += 1
        for p, w in t['outputs'].items():
            arcs[(t['id'], p, int(w))] += 1
    return arcs


ARC_RE = re.compile(r'^\s*"([^"]+)"\s*->\s*"([^"]+)"(?:\s*\[label="(\d+)"\])?\s*;')


def dot_arcs():
    arcs = Counter()
    for line in (OUT / 'versionB_network.dot').read_text().splitlines():
        m = ARC_RE.match(line)
        if m:
            arcs[(m.group(1), m.group(2), int(m.group(3) or 1))] += 1
    return arcs


def main():
    model = json.loads(MODEL.read_text())
    ma = model_arcs(model)
    da = dot_arcs()
    missing = ma - da
    extra = da - ma
    issues = []
    if len(model['places']) != 18:
        issues.append(f"model places {len(model['places'])} != 18")
    if len(model['transitions']) != 16:
        issues.append(f"model transitions {len(model['transitions'])} != 16")
    if missing:
        for arc, n in list(missing.items())[:10]:
            issues.append(f"MISSING ARC {arc[0]}->{arc[1]} weight {arc[2]} x{n}")
    if extra:
        for arc, n in list(extra.items())[:10]:
            issues.append(f"EXTRA ARC {arc[0]}->{arc[1]} weight {arc[2]} x{n}")
    for fmt in ('svg', 'pdf', 'eps', 'png'):
        p = OUT / f'versionB_network.{fmt}'
        if not p.exists() or p.stat().st_size == 0:
            issues.append(f"missing/empty {fmt}")
    try:
        ElementTree.parse(OUT / 'versionB_network.svg')
    except Exception as e:  # noqa: BLE001
        issues.append(f"SVG parse error: {e}")
    try:
        txt = subprocess.run(['pdftotext', str(OUT / 'versionB_network.pdf'), '-'],
                             capture_output=True, text=True, check=True).stdout
        for item in [p['id'] for p in model['places']] + [t['id'] for t in model['transitions']]:
            if txt.count(item) < 1:
                issues.append(f"PDF text missing id {item}")
    except Exception as e:  # noqa: BLE001
        issues.append(f"PDF text check failed: {e}")
    report = {
        'schema': 'tii-figure-topology/1',
        'model_arcs': len(ma), 'dot_arcs': len(da),
        'missing_arcs': len(missing), 'extra_arcs': len(extra),
        'place_ids_in_pdf': None, 'issues': issues,
        'pass': not issues,
    }
    (HERE / 'results' / 'figure_topology.json').write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps(report, indent=1))
    if issues:
        return 1
    print('FIGURE_TOPOLOGY_PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
