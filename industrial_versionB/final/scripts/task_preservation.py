#!/usr/bin/env python3
"""Task-preservation audit for the CPG-LD B-after model (frozen B-before used, not the old one)."""
from __future__ import annotations
import json, sys
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / 'literature_tpn_case_eval' / 'pipeline'))
import model_def, scg as lit

L, H = model_def.L, model_def.H


def main():
    before = json.loads((HERE / 'models' / 'versionB_before.json').read_text())
    after = json.loads((HERE / 'models' / 'versionB_after.json').read_text())
    base = json.loads((HERE / 'results' / 'before_complete_set.json').read_text())
    normal = sorted({tuple(c['N']) for c in base['certificates']})
    faulty = sorted({tuple(c['F']) for c in base['certificates']})
    ob = lit.FiringDomain(before)
    oa = lit.FiringDomain(after)
    tr_after = {t['id']: t for t in after['transitions']}

    def retained(seq, oracle):
        try:
            iv = oracle.interval(seq)
        except ValueError:
            return None
        return {"sequence": list(seq), "interval": [str(iv[0]), str(iv[1])],
                "within_H": iv[0] <= H}

    def check(seqs, oracle, faulty_flag):
        out = []
        for seq in seqs:
            r = retained(seq, oracle)
            ok = (r is not None and r['within_H'] and
                  any(tr_after[t]['fault'] for t in seq) == faulty_flag)
            out.append({"ok": ok, "seq": r})
        return out

    n_ref = check(normal, oa, False)
    f_ref = check(faulty, oa, True)
    # independent normal/fault complete executions in the after model
    model = after
    g = lit.SCG(model, max_classes=200_000).build()
    finish = set(g.summary()['finish_classes'])
    adj = defaultdict(list)
    for (s, t, d) in g.edges:
        adj[s].append((t, d))
    tr = {t['id']: t for t in model['transitions']}

    def getpath(need_fault):
        start = (0, False); parent = {start: (None, None)}; q = [start]
        while q:
            cur = q.pop(0); cid, fs = cur
            if cid in finish and fs == need_fault:
                seq = []
                while parent[cur][0] is not None:
                    prev, t = parent[cur]; seq.append(t); cur = prev
                return list(reversed(seq))
            for t, d in adj[cid]:
                nxt = (d, fs or tr[t]['fault'])
                if nxt not in parent:
                    parent[nxt] = (cur, t); q.append(nxt)
        return None
    n_wit = getpath(False); f_wit = getpath(True)
    out = {
        'schema': 'tii-task-preservation/2',
        'reference_normal_sequences': len(normal),
        'reference_fault_sequences': len(faulty),
        'normal_retained': sum(1 for x in n_ref if x['ok']),
        'fault_retained': sum(1 for x in f_ref if x['ok']),
        'normal_reference_pass': all(x['ok'] for x in n_ref),
        'fault_reference_pass': all(x['ok'] for x in f_ref),
        'normal_complete_witness': n_wit,
        'fault_complete_witness': f_wit,
        'normal_witness_interval': [str(x) for x in oa.interval(n_wit)] if n_wit else None,
        'fault_witness_interval': [str(x) for x in oa.interval(f_wit)] if f_wit else None,
        'normal_witness_within_H': bool(n_wit and oa.interval(n_wit)[0] <= H),
        'fault_witness_within_H': bool(f_wit and oa.interval(f_wit)[0] <= H),
    }
    out['pass'] = (out['normal_reference_pass'] and out['fault_reference_pass']
                   and out['normal_witness_within_H'] and out['fault_witness_within_H'])
    (HERE / 'results' / 'task_preservation.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: out[k] for k in ('reference_normal_sequences', 'reference_fault_sequences',
                                          'normal_retained', 'fault_retained',
                                          'normal_witness_interval', 'fault_witness_interval',
                                          'normal_witness_within_H', 'fault_witness_within_H',
                                          'pass')}, indent=1))
    return 0 if out['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
