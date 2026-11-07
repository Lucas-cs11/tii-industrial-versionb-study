#!/usr/bin/env python3
"""Bounded paper-CPG-LD run on Version B with a coarse, still-admissible grid.

Search budget: wall-clock cap (default 600 s) and a reduced candidate grid
inside the frozen domain (the full 28-interval grid makes one greedy sweep
dominate the paper deadline).  Status is reported honestly as
CPG_LD_SUCCESS / CPG_LD_INCONCLUSIVE_BUDGET / CPG_LD_FAILURE.
"""
from __future__ import annotations
import argparse, json, signal, sys, time
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / 'tpn-illustrative-case'))
sys.path.insert(0, str(ROOT / 'literature_tpn_case_eval' / 'pipeline'))
import models, analysis
from src.model.tpn import TPN, Transition, Interval, AuthorizedRange
from src.repair.algorithm import repair, Certificate
from src.repair.task_constraint import ReferenceBehaviorSet, ExactCriticalSequencePreservation
from dataclasses import replace
import scg as lit

L, H = 10, 60
START = ['t_StartLoading', 't_StartProcessing', 't_StartTransfer',
         't_StartInspection', 't_StartUnloading', 't_StartReworkTransfer']
GRID = [(0, 0), (0, 3), (1, 1), (2, 2), (3, 3), (Fraction(3, 2), Fraction(3, 2))]


class Timeout(Exception):
    pass


def _alarm(_signum, _frame):
    raise Timeout()


def build_adjustable():
    import freeze
    t = freeze.build_before()
    ivs = tuple(Interval(a, b) for (a, b) in GRID)
    trs = {}
    for n, tr in t.transitions.items():
        if n in START:
            trs[n] = replace(tr, is_adjustable=True, admissible_intervals=ivs,
                             authorized_range=AuthorizedRange(Fraction(0), Fraction(3),
                                                              Fraction(0), Fraction(3),
                                                              Fraction(1, 2)))
        else:
            trs[n] = tr
    return TPN(places=t.places, transitions=trs, arcs=t.arcs,
               initial_marking=dict(t.initial_marking),
               completion_markings=[dict(m) for m in t.completion_markings])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--timeout', type=int, default=600)
    ap.add_argument('--out', default='results_cpgld_bounded.json')
    args = ap.parse_args()
    t = build_adjustable()
    base = json.loads((HERE / 'results_before_complete_set.json').read_text())
    certs = [Certificate(phi=tuple(c['phi']), sigma_N=tuple(c['N']),
                         sigma_F=tuple(c['F']),
                         overlap=(Fraction(c['overlap'][0]), Fraction(c['overlap'][1])))
             for c in base['certificates'] if c.get('overlap')]
    verify_out = {'result': 'AMB', 'certificates': certs,
                  'certificate_mode': 'COMPLETE_SET', 'enumeration_complete': True}
    ref = ReferenceBehaviorSet.from_verification(verify_out, t, H,
                                                 model_id='versionB_before', L=L)
    constraint = ExactCriticalSequencePreservation(ref)
    base_model = analysis.export(t, 'base', '/tmp/vb_base.json')
    base_pairs = [(c.phi, c.sigma_N, c.sigma_F) for c in certs]
    log = []

    def verifier_fn(candidate):
        t0 = time.perf_counter()
        model = analysis.export(candidate, 'cand', '/tmp/vb_cand.json')
        oracle = lit.FiringDomain(model)
        out = []
        for (phi, sn, sf) in base_pairs:
            try:
                a = oracle.interval(sn); b = oracle.interval(sf)
            except ValueError:
                continue
            lo, hi = max(a[0], b[0]), min(a[1], b[1])
            if lo <= hi:
                out.append(Certificate(phi=tuple(phi), sigma_N=tuple(sn),
                                       sigma_F=tuple(sf), overlap=(lo, hi)))
        log.append({'t_s': round(time.perf_counter() - t0, 3),
                    'result': 'AMB' if out else 'VER', 'n_certs': len(out)})
        return {'result': 'AMB' if out else 'VER', 'certificates': out,
                'certificate_mode': 'COMPLETE_SET', 'enumeration_complete': True}

    status = 'CPG_LD_INCONCLUSIVE_BUDGET'
    repaired = None; iterations = 0; error = None
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(args.timeout)
    try:
        res = repair(t, certs, L, H, verifier_fn=verifier_fn,
                     task_constraint=constraint, reference_model=t,
                     metadata=ref, cache={})
        repaired = res.repaired_tpn
        iterations = res.iterations
        status = {'SUCCESS': 'CPG_LD_SUCCESS',
                  'FAILURE': 'CPG_LD_FAILURE',
                  'INCONCLUSIVE': 'CPG_LD_INCONCLUSIVE_BUDGET'}.get(res.status,
                                                                     'CPG_LD_INCONCLUSIVE_BUDGET')
        modified = res.modified_transitions
    except Timeout:
        modified = []; error = 'wall-clock cap reached'
    except Exception as exc:  # noqa: BLE001
        modified = []; error = f'{type(exc).__name__}: {exc}'
    finally:
        signal.alarm(0)

    changes = {}
    if repaired is not None:
        for n in t.transitions:
            a, b = t.transitions[n].interval, repaired.transitions[n].interval
            if (a.earliest, a.latest) != (b.earliest, b.latest):
                changes[n] = {'from': [str(a.earliest), str(a.latest)],
                              'to': [str(b.earliest), str(b.latest)]}
        analysis.export(repaired, 'versionB_after_cpgld_bounded',
                        HERE / 'versionB_after_cpgld_bounded.json')
    out = {'backend': 'surrogate-certificate-oracle (paper repair() API)',
           'candidate_grid': [[str(a), str(b)] for (a, b) in GRID],
           'timeout_s': args.timeout,
           'status': status, 'iterations': iterations,
           'modified_intervals': changes, 'verifier_calls': len(log),
           'log_tail': log[-10:], 'error': error}
    (HERE / args.out).write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: out[k] for k in ('status', 'iterations',
                                          'modified_intervals', 'verifier_calls', 'error')},
                     indent=1))


if __name__ == '__main__':
    main()
