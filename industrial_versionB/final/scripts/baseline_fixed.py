#!/usr/bin/env python3
"""Precision-correct baseline: B-before SCG + COMPLETE_SET with frozen completion."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[0] / 'final'))
sys.path.insert(0, str(HERE.parents[1] / 'tpn-illustrative-case'))
sys.path.insert(0, str(HERE.parents[1] / 'literature_tpn_case_eval' / 'pipeline'))
import model_def, scg as lit
from src.scg.builder import build_scg
from src.verifier import verify

L, H = model_def.L, model_def.H


def main():
    before = model_def.build()
    model = model_def.export(before, 'versionB_before_final', HERE / 'models' / 'versionB_before.json')
    (HERE / 'models').mkdir(exist_ok=True)
    st = time.perf_counter(); g = build_scg(before); scg_time = time.perf_counter() - st
    ist = time.perf_counter(); ig = lit.SCG(json.loads((HERE / 'models' / 'versionB_before.json').read_text())).build(); indep_time = time.perf_counter() - ist
    st = time.perf_counter(); r = verify(before, L=L, H=H, complete_set=True); prod_time = time.perf_counter() - st
    certs = [{'phi': list(c.phi), 'N': list(c.sigma_N), 'F': list(c.sigma_F),
              'overlap': [str(c.overlap[0]), str(c.overlap[1])] if c.overlap else None}
             for c in r['certificates']]
    out = {
        'schema': 'tii-versionb-baseline-final/1',
        'model_sha256': model_def.sha256_file(HERE / 'models' / 'versionB_before.json'),
        'L': L, 'H': H,
        'counts': {'places': len(before.places), 'transitions': len(before.transitions), 'arcs': len(before.arcs)},
        'completion_markings': before.completion_markings,
        'production_scg': {'classes': len(g.classes), 'edges': len(g.edges), 'runtime_s': round(scg_time, 2)},
        'independent_scg': {'classes': len(ig.classes), 'edges': len(ig.edges), 'runtime_s': round(indep_time, 2)},
        'production_complete_set': {'verdict': r['result'],
                                    'enumeration_complete': r.get('enumeration_complete'),
                                    'certificates': len(r['certificates']),
                                    'stats': {k: r['stats'][k] for k in r['stats'] if 'runtime' not in k},
                                    'runtime_s': round(prod_time, 2)},
        'certificates': certs,
    }
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / 'before_complete_set.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: out[k] for k in ('model_sha256', 'counts', 'production_scg',
                                          'independent_scg', 'production_complete_set')}, indent=1))


if __name__ == '__main__':
    main()
