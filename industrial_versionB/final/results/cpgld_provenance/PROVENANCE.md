# CPG-LD run provenance (P0 fix)

Three records are kept separate; the old failure is not renamed.

| record | file | status | notes |
|---|---|---|---|
| original failed run | `original_failed_run.json` | `FAILURE` (0 verifier calls, no adjustable transitions configured) | preserved from the previous round; not a success |
| precision-uncorrected full-grid attempt | `precision_uncorrected_full_grid_attempt.log` | incomplete (wall-clock cap) | endpoints were int-truncated by the old exporter |
| independent success replay | `independent_success_replay.json` | `CPG_LD_SUCCESS` (2 iterations, 11 calls) | previous round, exact-oracle backend, coarse grid |
| **official precision-corrected rerun** | `official_precision_corrected_run.json` | **`CPG_LD_SUCCESS`** (2 iterations, 10 calls, 84.98 s) | exact rational endpoints; frozen domain SHA; production COMPLETE_SET confirms VER |
| final task audit | `../after_complete_set.json` | `exact_critical_sequence_preservation`: 87/87 normal, 88/88 faulty, PASS | paper constraint |

The official rerun uses the paper's `repair()` with an exact Fraction
certificate oracle as the verifier backend (complete enumeration over the
frozen baseline pair set, valid under interval-tightening monotonicity). The
final model is re-verified with the **production** COMPLETE_SET verifier and
with the **paper task-preservation constraint**. The final changes are
`t_StartLoading [0,3]→[0,2]` and `t_StartProcessing [0,3]→[2,2]`, both inside
the frozen domain and both exact rational endpoints.
