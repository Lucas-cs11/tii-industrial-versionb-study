#!/usr/bin/env python3
"""Correct Version B network figure: arcs use their own source/target ids."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / 'figures'
MODEL = HERE / 'models' / 'versionB_before.json'
AFTER = HERE / 'models' / 'versionB_after.json'


def load(path):
    return json.loads(Path(path).read_text())


def build_dot(model):
    resources = {'p_robot_free', 'p_machine_free', 'p_inspection_free'}
    added = {'p_inspect_done', 't_InspectComplete'}
    lines = ['digraph VersionB {', 'rankdir=LR;',
             'graph [fontname="Helvetica", nodesep=0.20, ranksep=0.40, splines=true, pad=0.1];',
             'node [fontname="Helvetica", fontsize=8];',
             'edge [arrowsize=0.55, color="#40546b"];']
    for p in model['places']:
        pid = p['id']
        fill = '#fde9d9' if pid in added else ('#dbe4ee' if pid in resources else '#ffffff')
        label = pid + (f"\\n({p['initial']})" if p['initial'] else '')
        lines.append(f'"{pid}" [shape=circle, style=filled, fillcolor="{fill}", label="{label}"];')
    for t in model['transitions']:
        tid = t['id']
        if t['fault']:
            fill, color, font = '#f6e3d3', '#b5651d', '#8a4a12'
        elif t['observable']:
            fill, color, font = '#e6f0e2', '#2f6b3a', '#1d4424'
        else:
            fill, color, font = ('#fde9d9' if tid in added else '#f2f5f9'), '#04182e', '#04182e'
        lo, hi = t['earliest'], t['latest']
        lab = tid + f"\\n[{lo},{hi}]"
        if t['label']:
            lab += f"\\n/{t['label']}/"
        lines.append(f'"{tid}" [shape=box, style="rounded,filled", fillcolor="{fill}", '
                     f'color="{color}", fontcolor="{font}", label="{lab}"];')
    for t in model['transitions']:
        for p, w in t['inputs'].items():
            tail = f' [label="{w}"]' if w > 1 else ''
            lines.append(f'"{p}" -> "{t["id"]}"{tail};')
        for p, w in t['outputs'].items():
            tail = f' [label="{w}"]' if w > 1 else ''
            lines.append(f'"{t["id"]}" -> "{p}"{tail};')
    lines.append('}')
    return '\n'.join(lines) + '\n'


def main():
    OUT.mkdir(exist_ok=True)
    model = load(MODEL)
    dot = OUT / 'versionB_network.dot'
    dot.write_text(build_dot(model))
    for fmt in ('svg', 'pdf', 'eps'):
        subprocess.run(['dot', f'-T{fmt}', str(dot), '-o', str(OUT / f'versionB_network.{fmt}')], check=True)
    subprocess.run(['dot', '-Tpng', '-Gdpi=600', str(dot), '-o', str(OUT / 'versionB_network.png')], check=True)
    print('wrote network figure to', OUT)


if __name__ == '__main__':
    main()
