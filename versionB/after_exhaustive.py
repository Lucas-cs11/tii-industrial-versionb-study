#!/usr/bin/env python3
"""Exhaustive-found Version B-after: tighten two control intervals to [0,0].

Separately labelled from the CPG-LD result.  Confirms with the production
COMPLETE_SET verifier and rechecks both normal and faulty completions with the
independent exact Fraction oracle.
"""
from __future__ import annotations
import json, sys, time
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / 'tpn-illustrative-case'))
sys.path.insert(0, str(ROOT / 'literature_tpn_case_eval' / 'pipeline'))
import models, analysis, freeze
from src.model.tpn import Interval
from src.verifier import verify

L, H = 10, 60
CHANGES = {'t_StartLoading': (0, 0), 't_StartUnloading': (0, 0)}


def build_after():
    t = freeze.build_before()
    for n, (lo, hi) in CHANGES.items():
        t = t.copy_with_interval(n, Interval(lo, hi))
    return t


def main():
    after = build_after()
    model = analysis.export(after, 'industrial_17P15T_versionB_after_exhaustive',
                            HERE / 'versionB_after_exhaustive.json')
    st = time.perf_counter()
    r = verify(after, L=L, H=H, complete_set=True)
    prod_time = time.perf_counter() - st
    cp = analysis.completion_paths(model, H=H)
    # independent check of the baseline pair set under the adjusted model:
    base = json.loads((HERE / 'results_before_complete_set.json').read_text())
    oracle = __import__('scg').FiringDomain(model)
    overlaps = 0
    for c in base['certificates']:
        try:
            a = oracle.interval(tuple(c['N'])); b = oracle.interval(tuple(c['F']))
        except ValueError:
            continue
        if max(a[0], b[0]) <= min(a[1], b[1]):
            overlaps += 1
    out = {
        'schema': 'tii-versionb-after-exhaustive/1',
        'method': 'EXHAUSTIVE (not CPG-LD): 2 control intervals tightened to [0,0]',
        'changes': {n: {'from': ['0', '3'], 'to': ['0', '0']} for n in CHANGES},
        'L': L, 'H': H,
        'production_verdict': r['result'],
        'enumeration_complete': r.get('enumeration_complete'),
        'certificates': len(r['certificates']),
        'scg_classes': r['stats']['scg_classes'],
        'scg_edges': r['stats']['scg_edges'],
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
    (HERE / 'results_after_exhaustive.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
