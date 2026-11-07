#!/usr/bin/env python3
"""Freeze final Version B-before model and admissible adjustment domain.

All time endpoints are exact rationals; no int()/float conversion is used.
"""
from __future__ import annotations
import hashlib, json, subprocess, sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
PROD = ROOT / 'tpn-illustrative-case'
LIT = ROOT / 'literature_tpn_case_eval'
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / 'scripts'))
import model_def

L, H = model_def.L, model_def.H
START = ['t_StartLoading', 't_StartProcessing', 't_StartTransfer',
         't_StartInspection', 't_StartUnloading', 't_StartReworkTransfer']


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def build_domain():
    grid = [Fraction(i, 2) for i in range(7)]
    intervals = [[str(a), str(b)] for i, a in enumerate(grid) for b in grid[i:]]
    domain = {
        'schema': 'tii-adjustment-domain/2',
        'domain_id': 'VERSION_B_FINAL_ILLUSTRATIVE_ADMISSIBLE_ADJUSTMENT',
        'adjustable_transitions': START,
        'current_intervals': {n: ['0', '3'] for n in START},
        'authorized_endpoint_range': [['0', '0'], ['0', '3']],
        'admissible_intervals': intervals,
        'resolution_s': '1/2',
        'precision_protocol': 'exact rational endpoints; no integer/float rounding',
        'adjustment_kind': 'tighten-only',
        'max_modified_transitions': len(START),
        'L': L, 'H': H,
        'task_preservation': 'ExactCriticalSequencePreservation + non-empty normal and faulty complete executions inside H',
        'completion_marking': model_def.COMPLETION_FINAL[0],
        'fault_set': ['t_GripperSlipFault'],
        'observable_alphabet': sorted({lab for lab, fault, iv in model_def.TRANSITIONS_B.values() if lab}),
    }
    payload = json.dumps(domain, sort_keys=True, separators=(',', ':')).encode()
    domain['domain_sha256'] = hashlib.sha256(payload).hexdigest()
    return domain


def main():
    (HERE / 'models').mkdir(exist_ok=True)
    before = model_def.build()
    model = model_def.export(before, 'versionB_before_final', HERE / 'models' / 'versionB_before.json')
    domain = build_domain()
    (HERE / 'models' / 'frozen_admissible_domain.json').write_text(json.dumps(domain, indent=1) + '\n')
    prod_commit = subprocess.run(['git', '-C', str(PROD), 'rev-parse', 'HEAD'],
                                 capture_output=True, text=True).stdout.strip()
    lit_commit = subprocess.run(['git', '-C', str(LIT), 'rev-parse', 'HEAD'],
                                capture_output=True, text=True).stdout.strip()
    src = {}
    for rel in ('src/scg/builder.py', 'src/verifier.py', 'src/repair/algorithm.py',
                'src/repair/task_constraint.py', 'src/exact_confirmation/lp_solver.py',
                'scripts/model_case.py'):
        p = PROD / rel
        if p.exists():
            src[rel] = sha(p)
    engine = {
        'production_commit': prod_commit,
        'production_source_sha256': src,
        'independent_engine_repo': 'literature_tpn_case_eval',
        'independent_engine_commit': lit_commit,
        'independent_engine_file_sha256': {
            'pipeline/scg.py': sha(LIT / 'pipeline' / 'scg.py'),
            'pipeline/oracle.py': sha(LIT / 'pipeline' / 'oracle.py')},
        'versionB_model_sha256': sha(HERE / 'models' / 'versionB_before.json'),
        'versionB_domain_sha256': domain['domain_sha256'],
        'L': L, 'H': H,
        'fault': {'t_GripperSlipFault': ['1', '3']},
        'completion_marking': model_def.COMPLETION_FINAL[0],
        'observable_alphabet': domain['observable_alphabet'],
        'counts': {'places': 18, 'transitions': 16, 'arcs': 45},
    }
    (HERE / 'models' / 'freeze_manifest.json').write_text(json.dumps(engine, indent=1) + '\n')
    print(json.dumps({k: engine[k] for k in ('production_commit', 'versionB_model_sha256',
                                             'versionB_domain_sha256', 'L', 'H',
                                             'counts')}, indent=1))


if __name__ == '__main__':
    main()
