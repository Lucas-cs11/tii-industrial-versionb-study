#!/usr/bin/env python3
"""Freeze Version B-before model and its ILLUSTRATIVE_ADMISSIBLE_ADJUSTMENT domain."""
from __future__ import annotations
import hashlib, json, sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tpn-illustrative-case"))
sys.path.insert(0, str(HERE.parents[1] / "literature_tpn_case_eval" / "pipeline"))
import models
import analysis
from src.model.tpn import Interval

L, H = 10, 60
START = ['t_StartLoading', 't_StartProcessing', 't_StartTransfer',
         't_StartInspection', 't_StartUnloading', 't_StartReworkTransfer']
FROZEN = {
    't_FinishLoading': (2, 2), 't_FinishProcessing': (10, 10),
    't_FinishTransfer': (2, 2), 't_FinishUnloading': (2, 2),
    't_FinishReworkTransfer': (2, 2), 't_InspectionPass': (1, 1),
    't_InspectionRework': (1, 1), 't_RecoverLoading': (16, 16),
    't_GripperSlipFault': (1, 3), 't_InspectComplete': (4, 4),
}


def build_before():
    t = models.build('B1v4')
    for n, (lo, hi) in FROZEN.items():
        t = t.copy_with_interval(n, Interval(lo, hi))
    for n in START:
        t = t.copy_with_interval(n, Interval(0, 3))
    return t


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def main():
    t = build_before()
    model = analysis.export(t, 'industrial_17P15T_versionB_before', HERE / 'versionB_before.json')
    # .net export for TINA
    lines = [f"net {model['id']}"]
    for tr in model['transitions']:
        lab = f" : {tr['label']}" if tr['label'] else ""
        l = 'w' if tr['latest'] is None else tr['latest']
        lines.append(f"tr {tr['id']}{lab} [{tr['earliest']},{l}] "
                     + ' '.join(tr['inputs']) + ' -> ' + ' '.join(tr['outputs']))
    for pl in model['places']:
        if pl['initial']:
            lines.append(f"pl {pl['id']} ({pl['initial']})")
    (HERE / 'versionB_before.net').write_text('\n'.join(lines) + '\n')

    # frozen domain
    grid = []
    x = Fraction(0)
    while x <= 3:
        grid.append(x)
        x += Fraction(1, 2)
    intervals = [[str(a), str(b)] for i, a in enumerate(grid) for b in grid[i:]]
    domain = {
        'schema': 'tii-adjustment-domain/1',
        'domain_id': 'VERSION_B_ILLUSTRATIVE_ADMISSIBLE_ADJUSTMENT',
        'model_id': model['id'],
        'structure': {'places': len(model['places']), 'transitions': len(model['transitions']),
                      'arcs': sum(len(t['inputs']) + len(t['outputs']) for t in model['transitions'])},
        'L': L, 'H': H,
        'adjustable_transitions': START,
        'process_meaning': 'start/hand-off delay between an operation becoming enabled and the robot/machine/station actually starting it',
        'frozen_intervals': {n: [str(FROZEN[n][0]), str(FROZEN[n][1])] for n in FROZEN},
        'current_intervals': {n: ['0', '3'] for n in START},
        'authorized_endpoint_range': [['0', '0'], ['0', '3']],
        'admissible_intervals': intervals,
        'resolution_s': '1/2',
        'adjustment_kind': 'tighten-only (endpoint grid inside the authorized range)',
        'max_modified_transitions': len(START),
        'time_cost_objective': 'sum of endpoint displacement',
        'task_preservation': 'exact critical sequence preservation + fault-free completion p_completed=2 with all resources free inside H',
        'fault_frozen': {'t_GripperSlipFault': ['1', '3']},
        'observation_frozen': True,
        'structure_frozen': True,
    }
    payload = json.dumps(domain, sort_keys=True, separators=(',', ':')).encode()
    domain['domain_sha256'] = hashlib.sha256(payload).hexdigest()
    (HERE / 'DOMAIN_B.json').write_text(json.dumps(domain, indent=1) + '\n')

    manifest = {
        'schema': 'tii-versionb-frozen/1',
        'model_file': 'versionB_before.json',
        'model_sha256': sha256(HERE / 'versionB_before.json'),
        'net_sha256': sha256(HERE / 'versionB_before.net'),
        'domain_file': 'DOMAIN_B.json',
        'domain_sha256': domain['domain_sha256'],
        'L': L, 'H': H,
        'counts': domain['structure'],
        'fault': {'t_GripperSlipFault': ['1', '3'], 'recovery': ['16', '16']},
        'completion': 'p_completed=2 with all resources free (first entry)',
        'observable_alphabet': sorted({tr['label'] for tr in model['transitions'] if tr['observable']}),
    }
    (HERE / 'FROZEN_B.json').write_text(json.dumps(manifest, indent=1) + '\n')
    print(json.dumps(manifest, indent=1))


if __name__ == '__main__':
    main()
