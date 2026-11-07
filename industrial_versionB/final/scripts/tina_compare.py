#!/usr/bin/env python3
"""TINA 4.0.0 -W comparison for final before/after (integer-valued endpoints)."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / 'scripts'))
import model_def
from src.scg.builder import build_scg
TINA = '/Volumes/tina-4.0.0/nd.app/Contents/MacOS/bin/tina'
ENV = dict(os.environ, DYLD_LIBRARY_PATH='/Volumes/tina-4.0.0/nd.app/Contents/MacOS/lib')


def net_text(model, path):
    lines = [f"net {model['id']}"]
    for t in model['transitions']:
        lab = f" : {t['label']}" if t['label'] else ""
        lines.append(f"tr {t['id']}{lab} [{t['earliest']},{t['latest']}] " +
                     ' '.join(t['inputs']) + ' -> ' + ' '.join(t['outputs']))
    for p in model['places']:
        if p['initial']:
            lines.append(f"pl {p['id']} ({p['initial']})")
    Path(path).write_text('\n'.join(lines) + '\n')


def stats(net, mode):
    r = subprocess.run([TINA, mode, str(net)], capture_output=True, text=True, env=ENV, timeout=300)
    txt = r.stdout + r.stderr
    st = tr = None
    for line in txt.splitlines():
        toks = line.replace('#', ' ').split()
        if toks[:1] == ['states'] and st is None: st = int(toks[1])
        if toks[:1] == ['transitions'] and tr is None: tr = int(toks[1])
    return {'states': st, 'edges': tr, 'returncode': r.returncode}


def main():
    out = {'schema': 'tii-versionb-tina-final/1'}
    for name in ('before', 'after'):
        model = json.loads((HERE / 'models' / f'versionB_{name}.json').read_text())
        net = HERE / 'results' / f'versionB_{name}.net'
        net_text(model, net)
        t = model_def.from_canonical(model)
        g = build_scg(t)
        modes = {m: stats(net, m) for m in ('-W', '-S', '-E', '-M', '-R')}
        out[name] = {'production_scg': {'classes': len(g.classes), 'edges': len(g.edges)},
                     'tina': modes,
                     'W_match': modes['-W']['states'] == len(g.classes)
                                and modes['-W']['edges'] == len(g.edges)}
    out['pass'] = all(out[n]['W_match'] for n in ('before', 'after'))
    (HERE / 'results' / 'tina_equivalence.json').write_text(json.dumps(out, indent=1) + '\n')
    md = ['# TINA comparison (Version B final)', '',
          '| model | production SCG | TINA -W | match | TINA -S | -E | -M | -R |',
          '|---|---|---|---|---|---|---|---|']
    for n in ('before', 'after'):
        r = out[n]
        md.append(f"| {n} | {r['production_scg']['classes']}/{r['production_scg']['edges']} | "
                  f"{r['tina']['-W']['states']}/{r['tina']['-W']['edges']} | {r['W_match']} | "
                  f"{r['tina']['-S']['states']}/{r['tina']['-S']['edges']} | "
                  f"{r['tina']['-E']['states']}/{r['tina']['-E']['edges']} | "
                  f"{r['tina']['-M']['states']}/{r['tina']['-M']['edges']} | "
                  f"{r['tina']['-R']['states']}/{r['tina']['-R']['edges']} |")
    (HERE / 'results' / 'tina_equivalence.md').write_text('\n'.join(md) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
