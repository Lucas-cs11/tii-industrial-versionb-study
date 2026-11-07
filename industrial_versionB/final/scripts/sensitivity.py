#!/usr/bin/env python3
"""L/H sensitivity matrix for the frozen Version B before/after models."""
from __future__ import annotations
import json, sys, time
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / 'scripts'))
sys.path.insert(0, str(ROOT / 'tpn-illustrative-case'))
sys.path.insert(0, str(ROOT / 'literature_tpn_case_eval' / 'pipeline'))
import model_def, scg as lit
from src.verifier import verify

CONFIGS = [(10, 60), (12, 60), (14, 60), (14, 75), (14, 90)]


def rework_info(model, H):
    g = lit.SCG(model, max_classes=200_000).build()
    finish = set(g.summary()['finish_classes'])
    adj = defaultdict(list)
    for (s, t, d) in g.edges:
        adj[s].append((t, d))
    tr = {t['id']: t for t in model['transitions']}
    oracle = lit.FiringDomain(model)
    # any path reaching a marking with a rework token (inspection_rework fired)
    rework_classes = [c['id'] for c in g.classes
                      if any(p in c['marking'] and c['marking'][p] for p in
                             ('p_rework_queue', 'p_rework_transfer'))]
    reachable = bool(rework_classes)
    witness = None
    # find shortest path that fires t_InspectionRework and continues to completion
    for cid in rework_classes:
        # path to this class with t_InspectionRework in it
        start = 0; parent = {start: (None, None)}; q = [start]
        found = None
        while q:
            c = q.pop(0)
            if c == cid:
                seq = []
                while parent[c][0] is not None:
                    prev, t = parent[c]; seq.append(t); c = prev
                seq = list(reversed(seq))
                if 't_InspectionRework' in seq:
                    found = seq
                break
            for t, d in adj[c]:
                if d not in parent:
                    parent[d] = (c, t); q.append(d)
        if found:
            try:
                iv = oracle.interval(found)
            except ValueError:
                continue
            witness = {'sequence': found, 'length': len(found),
                       'observable': sum(1 for t in found if tr[t]['observable']),
                       'interval': [str(iv[0]), str(iv[1])],
                       'within_H': iv[0] <= H}
            break
    return {'rework_structurally_reachable': reachable,
            'rework_timed_witness': witness,
            'earliest_rework_interval': witness['interval'] if witness else None,
            'min_observable_length_rework': witness['observable'] if witness else None}


def run(model_name, model_json, L, H):
    sys.path.insert(0, str(HERE))
    if model_name == 'before':
        t = model_def.build()
    else:
        t = model_def.from_canonical(model_json)
    st = time.perf_counter(); r = verify(t, L=L, H=H, complete_set=True); dt = time.perf_counter() - st
    oracle = lit.FiringDomain(model_json)
    tr = {x['id']: x for x in model_json['transitions']}
    certs = []
    for c in r['certificates']:
        try:
            ivN = oracle.interval(c.sigma_N); ivF = oracle.interval(c.sigma_F)
            ok = max(ivN[0], ivF[0]) <= min(ivN[1], ivF[1])
            word = [tr[x]['label'] for x in c.sigma_N if tr[x]['observable']]
        except ValueError:
            ok = False; ivN = ivF = None; word = []
        certs.append({'phi': list(c.phi), 'N': list(c.sigma_N), 'F': list(c.sigma_F),
                      'oracle_overlap_ok': ok,
                      'oracle_interval_N': [str(x) for x in ivN] if ivN else None,
                      'oracle_interval_F': [str(x) for x in ivF] if ivF else None})
    return {
        'L': L, 'H': H, 'verdict': r['result'],
        'enumeration_complete': r.get('enumeration_complete'),
        'certificates': len(r['certificates']),
        'oracle_checked': len(certs),
        'oracle_all_overlap': all(x['oracle_overlap_ok'] for x in certs),
        'stats': {k: r['stats'][k] for k in
                  ('scg_classes', 'scg_edges', 'candidate_words',
                   'candidate_words_processed', 'temporal_states',
                   'terminal_pairs', 'lp_calls')},
        'runtime_s': round(dt, 2),
        'first_certificates': certs[:3],
        'rework': rework_info(model_json, H),
    }


def main():
    before = json.loads((HERE / 'models' / 'versionB_before.json').read_text())
    after = json.loads((HERE / 'models' / 'versionB_after.json').read_text())
    (HERE / 'results' / 'sensitivity').mkdir(parents=True, exist_ok=True)
    rows = [('L', 'H', 'model', 'verdict', 'enum_complete', 'certificates',
             'scg_classes', 'scg_edges', 'candidate_words', 'runtime_s', 'rework_timed')]
    for L, H in CONFIGS:
        for name, mj in (('before', before), ('after', after)):
            try:
                r = run(name, mj, L, H)
            except Exception as exc:  # noqa: BLE001
                r = {'L': L, 'H': H, 'verdict': 'ERROR', 'error': f'{type(exc).__name__}: {exc}'}
            (HERE / 'results' / 'sensitivity' / f'{name}_L{L}_H{H}.json').write_text(json.dumps(r, indent=1) + '\n')
            rows.append((L, H, name, r.get('verdict'), r.get('enumeration_complete'),
                         r.get('certificates'), r.get('stats', {}).get('scg_classes'),
                         r.get('stats', {}).get('scg_edges'),
                         r.get('stats', {}).get('candidate_words'), r.get('runtime_s'),
                         bool(r.get('rework', {}).get('rework_timed_witness'))))
            print('done', L, H, name, r.get('verdict'), r.get('certificates'),
                  r.get('runtime_s'), flush=True)
    with open(HERE / 'results' / 'lh_matrix.csv', 'w') as f:
        for row in rows:
            f.write(','.join('' if x is None else str(x) for x in row) + '\n')
    print('matrix written')


if __name__ == '__main__':
    main()
