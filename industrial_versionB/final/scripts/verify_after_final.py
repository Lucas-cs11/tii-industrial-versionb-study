#!/usr/bin/env python3
"""Production COMPLETE_SET + independent oracle for the final CPG-LD B-after."""
from __future__ import annotations
import json, sys, time
from fractions import Fraction
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / 'scripts'))
sys.path.insert(0, str(ROOT / 'tpn-illustrative-case'))
sys.path.insert(0, str(ROOT / 'literature_tpn_case_eval' / 'pipeline'))
import model_def, scg as lit
from src.verifier import verify
from src.repair.task_constraint import ReferenceBehaviorSet, ExactCriticalSequencePreservation
from src.repair.algorithm import Certificate

L, H = model_def.L, model_def.H


def main():
    before_json = json.loads((HERE / 'models' / 'versionB_before.json').read_text())
    after_json = json.loads((HERE / 'models' / 'versionB_after.json').read_text())
    after = model_def.from_canonical(after_json)
    st = time.perf_counter(); r = verify(after, L=L, H=H, complete_set=True); dt = time.perf_counter() - st
    # reference behavior set from corrected baseline certificates
    base = json.loads((HERE / 'results' / 'before_complete_set.json').read_text())
    certs = [Certificate(phi=tuple(c['phi']), sigma_N=tuple(c['N']), sigma_F=tuple(c['F']),
                         overlap=(Fraction(c['overlap'][0]), Fraction(c['overlap'][1])))
             for c in base['certificates'] if c.get('overlap')]
    ref = ReferenceBehaviorSet.from_verification(
        {'result': 'AMB', 'certificate_mode': 'COMPLETE_SET',
         'enumeration_complete': True, 'certificates': certs},
        model_def.build(), H, model_id='versionB_before_final', L=L)
    constraint = ExactCriticalSequencePreservation(ref)
    res = constraint.evaluate(after, model_def.build(), ref)
    out = {
        'schema': 'tii-versionb-after-final/1',
        'model_sha256': model_def.sha256_file(HERE / 'models' / 'versionB_after.json'),
        'L': L, 'H': H,
        'production_verdict': r['result'],
        'enumeration_complete': r.get('enumeration_complete'),
        'certificates': len(r['certificates']),
        'scg_classes': r['stats']['scg_classes'], 'scg_edges': r['stats']['scg_edges'],
        'runtime_s': round(dt, 2),
        'task_constraint': {'name': constraint.name, 'passed': res.passed,
                            'failed_constraints': res.failed_constraints,
                            'metrics': res.metrics},
        'changes': {n: {'from': [str(model_def.build().transitions[n].interval.earliest),
                                 str(model_def.build().transitions[n].interval.latest)],
                        'to': [str(after.transitions[n].interval.earliest),
                               str(after.transitions[n].interval.latest)]}
                    for n in ('t_StartLoading', 't_StartProcessing')},
    }
    task = json.loads((HERE / 'results' / 'task_preservation.json').read_text())
    out['normal_completion'] = task['normal_witness_interval']
    out['fault_completion'] = task['fault_witness_interval']
    out['nonvacuous_task_preservation'] = task['pass']
    (HERE / 'results' / 'after_complete_set.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
