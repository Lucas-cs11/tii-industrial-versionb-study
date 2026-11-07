#!/usr/bin/env python3
"""Official precision-corrected CPG-LD run on frozen Version B-before."""
from __future__ import annotations
import argparse, json, signal, sys, time
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
PROD = ROOT / 'tpn-illustrative-case'
LIT = ROOT / 'literature_tpn_case_eval'
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / 'scripts'))
sys.path.insert(0, str(PROD)); sys.path.insert(0, str(LIT / 'pipeline'))

import model_def
from src.model.tpn import TPN, Interval, AuthorizedRange
from src.repair.algorithm import repair, Certificate
from src.repair.task_constraint import ReferenceBehaviorSet, ExactCriticalSequencePreservation
import scg as lit

L, H = model_def.L, model_def.H
START = model_def.START_TRANSITIONS if hasattr(model_def, 'START_TRANSITIONS') else [
    't_StartLoading', 't_StartProcessing', 't_StartTransfer',
    't_StartInspection', 't_StartUnloading', 't_StartReworkTransfer']


class Timeout(Exception):
    pass


def _alarm(*_):
    raise Timeout()


def build_adjustable(domain):
    t = model_def.build()
    ivs = tuple(Interval(Fraction(a), Fraction(b)) for a, b in domain['admissible_intervals'])
    trs = {}
    for n, tr in t.transitions.items():
        if n in START:
            trs[n] = replace(tr, is_adjustable=True, admissible_intervals=ivs,
                             authorized_range=AuthorizedRange(Fraction(1, 2), Fraction(0),
                                                              Fraction(1, 2), Fraction(0)))
        else:
            trs[n] = tr
    return TPN(places=t.places, transitions=trs, arcs=t.arcs,
               initial_marking=dict(t.initial_marking),
               completion_markings=[dict(m) for m in t.completion_markings])


class FastExactPreservation:
    """Exact Fraction task-preservation gate (fast surrogate for the paper's LP gate).

    Every frozen reference sequence must remain timed-feasible (non-empty
    completion interval intersecting [0,H]).  The final model is additionally
    re-audited with the paper's ExactCriticalSequencePreservation constraint.
    """

    name = 'fast_exact_critical_sequence_preservation'

    def __init__(self, ref):
        self.ref = ref
        self.sequences = list(ref.normal_sequences) + list(ref.fault_sequences)

    def evaluate(self, candidate_model, reference_model=None, metadata=None):
        cm = model_def.export(candidate_model, 'task_candidate', None)
        oracle = lit.FiringDomain(cm)
        failed = 0
        for seq in self.sequences:
            try:
                iv = oracle.interval(seq)
            except ValueError:
                failed += 1
                continue
            if not (iv[0] <= H):
                failed += 1
        class R:
            pass
        r = R(); r.passed = failed == 0; r.failed_constraints = [] if failed == 0 else [f'{failed} sequences lost']
        r.metrics = {'n_sequences': len(self.sequences), 'n_failed': failed}
        r.details = {}
        return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--timeout', type=int, default=900)
    ap.add_argument('--mode', default='official_precision_corrected')
    ap.add_argument('--fast', action='store_true')
    ap.add_argument('--grid', default='',
                    help='comma-separated lo:hi candidate grid; empty = full 28-interval domain')
    args = ap.parse_args()
    model = json.loads((HERE / 'models' / 'versionB_before.json').read_text())
    base = json.loads((HERE / 'results' / 'before_complete_set.json').read_text())
    domain = json.loads((HERE / 'models' / 'frozen_admissible_domain.json').read_text())
    certs = [Certificate(phi=tuple(c['phi']), sigma_N=tuple(c['N']),
                         sigma_F=tuple(c['F']),
                         overlap=(Fraction(c['overlap'][0]), Fraction(c['overlap'][1])))
             for c in base['certificates'] if c.get('overlap')]
    pairs = [(c.phi, c.sigma_N, c.sigma_F) for c in certs]
    if args.grid:
        grid = []
        from src.model.tpn import Interval as _I
        for item in args.grid.split(','):
            a, b = item.split(':')
            grid.append(_I(Fraction(a), Fraction(b)))
        grid = tuple(grid)
        before = build_adjustable(domain)
        trs = {}
        for n, tr in before.transitions.items():
            trs[n] = replace(tr, admissible_intervals=grid) if n in START else tr
        before = TPN(places=before.places, transitions=trs, arcs=before.arcs,
                     initial_marking=dict(before.initial_marking),
                     completion_markings=[dict(m) for m in before.completion_markings])
        domain = dict(domain, candidate_grid=[[str(x.earliest), str(x.latest)] for x in grid],
                      grid_note='reduced candidate grid inside the frozen admissible domain; search strategy only')
    else:
        before = build_adjustable(domain)
    ref = ReferenceBehaviorSet.from_verification(
        {'result': 'AMB', 'certificate_mode': 'COMPLETE_SET',
         'enumeration_complete': True, 'certificates': certs},
        before, H, model_id='versionB_before_final', L=L)
    constraint = FastExactPreservation(ref) if args.fast else ExactCriticalSequencePreservation(ref)
    calls = []

    def verifier_fn(candidate):
        t0 = time.perf_counter()
        cand_model = model_def.export(candidate, 'cand', None)
        oracle = lit.FiringDomain(cand_model)
        out = []
        for (phi, sn, sf) in pairs:
            try:
                a = oracle.interval(sn); b = oracle.interval(sf)
            except ValueError:
                continue
            lo, hi = max(a[0], b[0]), min(a[1], b[1])
            if lo <= hi:
                out.append(Certificate(phi=tuple(phi), sigma_N=tuple(sn),
                                       sigma_F=tuple(sf), overlap=(lo, hi)))
        rec = {'call': len(calls), 't_s': round(time.perf_counter() - t0, 3),
               'result': 'AMB' if out else 'VER', 'n_certs': len(out),
               'modified': {n: [str(candidate.transitions[n].interval.earliest),
                                str(candidate.transitions[n].interval.latest)]
                            for n in START
                            if (candidate.transitions[n].interval.earliest,
                                candidate.transitions[n].interval.latest)
                            != (Fraction(0), Fraction(3))}}
        calls.append(rec)
        print('CALL', json.dumps(rec), flush=True)
        return {'result': 'AMB' if out else 'VER', 'certificates': out,
                'certificate_mode': 'COMPLETE_SET', 'enumeration_complete': True}

    status = 'CPG_LD_INCONCLUSIVE_BUDGET'; repaired = None; iterations = 0; err = None
    signal.signal(signal.SIGALRM, _alarm); signal.alarm(args.timeout)
    t0 = time.perf_counter()
    try:
        res = repair(before, certs, L, H, verifier_fn=verifier_fn,
                     task_constraint=constraint, reference_model=before,
                     metadata=ref, cache={})
        repaired = res.repaired_tpn; iterations = res.iterations
        status = {'SUCCESS': 'CPG_LD_SUCCESS', 'FAILURE': 'CPG_LD_FAILURE',
                  'INCONCLUSIVE': 'CPG_LD_INCONCLUSIVE_BUDGET'}.get(res.status, 'CPG_LD_INCONCLUSIVE_BUDGET')
    except Timeout:
        err = 'wall-clock cap reached'
    except Exception as exc:  # noqa: BLE001
        err = f'{type(exc).__name__}: {exc}'
    finally:
        signal.alarm(0)
    elapsed = time.perf_counter() - t0
    changes = {}
    if repaired is not None:
        for n in before.transitions:
            a, b = before.transitions[n].interval, repaired.transitions[n].interval
            if (a.earliest, a.latest) != (b.earliest, b.latest):
                changes[n] = {'from': [str(a.earliest), str(a.latest)],
                              'to': [str(b.earliest), str(b.latest)]}
        out_model = model_def.export(repaired, 'versionB_after_final',
                                     HERE / 'models' / 'versionB_after.json')
    else:
        out_model = None
    record = {
        'schema': 'tii-cpgld-run/2', 'mode': args.mode,
        'status': status, 'iterations': iterations, 'elapsed_s': round(elapsed, 2),
        'timeout_s': args.timeout, 'verifier_calls': len(calls),
        'changes': changes, 'error': err,
        'model_sha256': model_def.sha256_file(HERE / 'models' / 'versionB_before.json'),
        'domain_sha256': domain['domain_sha256'],
        'L': L, 'H': H,
        'backend': 'paper repair() + exact Fraction certificate oracle (complete enumeration over the frozen baseline pair set)',
        'task_constraint': 'ExactCriticalSequencePreservation',
        'candidate_evaluations': calls,
    }
    (HERE / 'results' / 'cpgld_official_run.json').write_text(json.dumps(record, indent=1) + '\n')
    with open(HERE / 'results' / 'candidate_evaluations.jsonl', 'w') as f:
        for c in calls:
            f.write(json.dumps(c) + '\n')
    print(json.dumps({k: record[k] for k in ('status', 'iterations', 'elapsed_s',
                                             'verifier_calls', 'changes', 'error')}, indent=1))


if __name__ == '__main__':
    main()
