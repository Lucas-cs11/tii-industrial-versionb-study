#!/usr/bin/env python3
"""AMB certificate for the precision-corrected B-before, with independent replay."""
from __future__ import annotations
import json, sys
from fractions import Fraction
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / 'literature_tpn_case_eval' / 'pipeline'))
import scg as lit

L, H = 10, 60


def first_entry(model, seq):
    tr = {t['id']: t for t in model['transitions']}
    fin = model['finish_markings']
    m = {p['id']: p['initial'] for p in model['places']}
    def done(mm):
        for spec in fin:
            places = set(mm) | set(spec)
            if all(mm.get(p, 0) == spec.get(p, 0) for p in places):
                return True
        return False
    flags = [done(m)]
    for t in seq:
        for p, w in tr[t]['inputs'].items(): m[p] = m.get(p, 0) - w
        for p, w in tr[t]['outputs'].items(): m[p] = m.get(p, 0) + w
        flags.append(done(m))
    return flags


def main():
    model = json.loads((HERE / 'models' / 'versionB_before.json').read_text())
    base = json.loads((HERE / 'results' / 'before_complete_set.json').read_text())
    tr = {t['id']: t for t in model['transitions']}
    oracle = lit.FiringDomain(model)
    certs = [c for c in base['certificates'] if c.get('overlap')]
    cert = max(certs, key=lambda c: Fraction(c['overlap'][1]) - Fraction(c['overlap'][0]))
    sN, sF = tuple(cert['N']), tuple(cert['F'])
    ivN = oracle.interval(sN); ivF = oracle.interval(sF)
    lo, hi = max(ivN[0], ivF[0]), min(ivN[1], ivF[1])
    T = lo
    okN, schedN = oracle.feasible_at(sN, T, return_schedule=True)
    okF, schedF = oracle.feasible_at(sF, T, return_schedule=True)
    flagsN = first_entry(model, sN); flagsF = first_entry(model, sF)
    wordN = [tr[t]['label'] for t in sN if tr[t]['observable']]
    wordF = [tr[t]['label'] for t in sF if tr[t]['observable']]
    out = {
        'schema': 'tii-versionb-amb-certificate/2',
        'L': L, 'H': H, 'observable_word': wordN,
        'words_equal': wordN == wordF == list(cert['phi']),
        'normal_sequence': list(sN), 'fault_sequence': list(sF),
        'normal_firings': len(sN), 'fault_firings': len(sF),
        'normal_observable_events': len(wordN), 'fault_observable_events': len(wordF),
        'normal_has_fault': any(tr[t]['fault'] for t in sN),
        'fault_has_fault': any(tr[t]['fault'] for t in sF),
        'normal_interval': [str(ivN[0]), str(ivN[1])],
        'fault_interval': [str(ivF[0]), str(ivF[1])],
        'overlap': [str(lo), str(hi)],
        'common_completion_time_T': str(T),
        'normal_feasible_at_T': okN, 'fault_feasible_at_T': okF,
        'normal_schedule': [[t, str(v)] for t, v in schedN],
        'fault_schedule': [[t, str(v)] for t, v in schedF],
        'normal_first_entry_flags': flagsN, 'fault_first_entry_flags': flagsF,
        'normal_first_entry_only_last': (not any(flagsN[:-1])) and flagsN[-1],
        'fault_first_entry_only_last': (not any(flagsF[:-1])) and flagsF[-1],
        'within_H': ivN[0] <= H and ivF[0] <= H,
    }
    out['certificate_pass'] = bool(out['words_equal'] and not out['normal_has_fault']
                                   and out['fault_has_fault']
                                   and out['normal_first_entry_only_last']
                                   and out['fault_first_entry_only_last']
                                   and okN and okF and out['within_H'])
    (HERE / 'results' / 'before_amb_certificate.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: out[k] for k in ('observable_word', 'words_equal', 'normal_interval',
                                          'fault_interval', 'overlap', 'common_completion_time_T',
                                          'normal_feasible_at_T', 'fault_feasible_at_T',
                                          'normal_first_entry_only_last', 'fault_first_entry_only_last',
                                          'within_H', 'certificate_pass')}, indent=1))


if __name__ == '__main__':
    main()
