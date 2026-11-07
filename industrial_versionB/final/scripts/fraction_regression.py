#!/usr/bin/env python3
"""Fraction precision regression: endpoint round-trip must be exact."""
from __future__ import annotations
import json, sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / 'scripts'))
import model_def

CASES = [("0", "0"), ("0", "1/2"), ("1/2", "1/2"), ("3/2", "3/2"),
         ("1", "3/2"), ("3/2", "2"), ("0", "inf")]


def main():
    results = []
    for lo, hi in CASES:
        t = model_def.build()
        from src.model.tpn import Interval
        t = t.copy_with_interval('t_StartInspection',
                                 Interval(Fraction(lo),
                                          float('inf') if hi == 'inf' else Fraction(hi)))
        model = model_def.export(t, f'roundtrip_{lo}_{hi}')
        parsed = model_def.from_canonical(model)
        again = model_def.export(parsed, f'roundtrip2_{lo}_{hi}')
        a = model['transitions']
        b = again['transitions']
        same = a == b
        # explicit lossy check: [1.5,1.5] must not become [1,1]
        target = next(x for x in a if x['id'] == 't_StartInspection')
        parsed_target = next(x for x in parsed.transitions['t_StartInspection'].interval.__dict__.items() or [] ) if False else None
        iv = parsed.transitions['t_StartInspection'].interval
        exact = (iv.earliest == Fraction(lo) and
                 ((hi == 'inf' and iv.is_infinite()) or (hi != 'inf' and iv.latest == Fraction(hi))))
        results.append({"earliest": lo, "latest": hi, "json_roundtrip_equal": same,
                        "exact_fraction": exact,
                        "serialized_earliest": target['earliest'],
                        "serialized_latest": target['latest']})
    ok = all(r['json_roundtrip_equal'] and r['exact_fraction'] for r in results)
    out = {"schema": "tii-fraction-roundtrip/1", "cases": results, "pass": ok}
    (HERE / 'results' / 'fraction_roundtrip_tests.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
