#!/usr/bin/env python3
"""Confirm the CPG-LD-adjusted Version B-after with the production COMPLETE_SET
and the independent exact oracle (non-vacuous task preservation)."""
from __future__ import annotations
import json, sys, time
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tpn-illustrative-case'))
sys.path.insert(0, str(ROOT / 'literature_tpn_case_eval' / 'pipeline'))
from src.verifier import verify
import analysis, scg as lit

L, H = 10, 60


def main():
    model = json.loads((HERE / 'versionB_after_cpgld_bounded.json').read_text())
    t = analysis.build_tpn_from_json(model) if hasattr(analysis, 'build_tpn_from_json') else None
    # rebuild through the canonical builder and patch intervals to exactly the JSON
    import freeze
    from src.model.tpn import Interval
    t = freeze.build_before()
    for tr in model['transitions']:
        a = t.transitions[tr['id']]
        if (int(a.interval.earliest), None if a.interval.is_infinite() else int(a.interval.latest)) != (tr['earliest'], tr['latest']):
            t = t.copy_with_interval(tr['id'], Interval(tr['earliest'], tr['latest']))
    st = time.perf_counter()
    r = verify(t, L=L, H=H, complete_set=True)
    prod_time = time.perf_counter() - st
    cp = analysis.completion_paths(model, H=H)
    base = json.loads((HERE / 'results_before_complete_set.json').read_text())
    oracle = lit.FiringDomain(model)
    overlaps = 0
    for c in base['certificates']:
        try:
            a = oracle.interval(tuple(c['N'])); b = oracle.interval(tuple(c['F']))
        except ValueError:
            continue
        if max(a[0], b[0]) <= min(a[1], b[1]):
            overlaps += 1
    out = {
        'schema': 'tii-versionb-after-cpgld/1',
        'method': 'paper repair() / CPG-LD (bounded coarse admissible grid), certificate oracle backend',
        'source': 'results_cpgld_bounded.json',
        'changes': {tr['id']: {'from': ['0', '3'],
                              'to': [str(tr['earliest']), str(tr['latest'])]}
                    for tr in model['transitions']
                    if tr['id'] in ('t_StartLoading', 't_StartProcessing')},
        'L': L, 'H': H,
        'production_verdict': r['result'],
        'enumeration_complete': r.get('enumeration_complete'),
        'certificates': len(r['certificates']),
        'scg_classes': r['stats']['scg_classes'], 'scg_edges': r['stats']['scg_edges'],
        'production_runtime_s': round(prod_time, 2),
        'normal_completion': cp['normal'] and {k: cp['normal'][k] for k in
                                               ('length', 'observable', 'interval', 'within_H')},
        'fault_completion': cp['fault'] and {k: cp['fault'][k] for k in
                                             ('length', 'observable', 'interval', 'within_H')},
        'baseline_pairs_still_overlapping': overlaps,
        'baseline_pairs_total': len(base['certificates']),
        'nonvacuous_task_preservation': bool(cp['normal'] and cp['fault']
                                             and cp['normal']['within_H'] and cp['fault']['within_H']),
    }
    (HERE / 'results_after_cpgld.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
