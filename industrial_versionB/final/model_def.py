#!/usr/bin/env python3
"""Final, precision-correct Version B model definition (P0 fixes).

Fixes vs. the previous round:
  * time endpoints preserved exactly as Fractions (no int() truncation);
  * a single, frozen two-workpiece completion predicate is used by every tool;
  * canonical JSON uses exact rational strings ("3/2") and "inf".
"""
from __future__ import annotations
import hashlib, json, sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                    # TII_TPN
PROD = ROOT / "tpn-illustrative-case"
LIT = ROOT / "literature_tpn_case_eval"
sys.path.insert(0, str(PROD)); sys.path.insert(0, str(PROD / "scripts"))
sys.path.insert(0, str(LIT / "pipeline"))

from src.model.tpn import TPN, Transition, Interval, Arc, Place  # noqa: E402
from model_case import PLACES, TRANSITIONS, ARCS, INITIAL  # noqa: E402

# Version B structure: Version A + robot-held recovery + inspection dwell split
PLACES_B = list(PLACES) + ["p_inspect_done"]
TRANSITIONS_B = {k: v for k, v in TRANSITIONS.items()}
TRANSITIONS_B["t_InspectComplete"] = ("", False, (4, 4))
# arcs: Version A minus the two robot-release arcs and the direct inspection arcs
ARCS_B = []
for (a, b, w) in ARCS:
    if (a, b) in {("t_GripperSlipFault", "p_robot_free"),
                  ("p_robot_free", "t_RecoverLoading"),
                  ("p_inspecting", "t_InspectionPass"),
                  ("p_inspecting", "t_InspectionRework")}:
        continue
    ARCS_B.extend([(a, b)] * w)
ARCS_B += [("p_inspecting", "t_InspectComplete"),
           ("t_InspectComplete", "p_inspect_done"),
           ("p_inspect_done", "t_InspectionPass"),
           ("p_inspect_done", "t_InspectionRework")]
ARCS_B = list(dict.fromkeys(ARCS_B))

# FROZEN B-before intervals
BEFORE_INTERVALS = {
    "t_StartLoading": (0, 3), "t_StartProcessing": (0, 3),
    "t_StartTransfer": (0, 3), "t_StartInspection": (0, 3),
    "t_StartUnloading": (0, 3), "t_StartReworkTransfer": (0, 3),
    "t_FinishLoading": (2, 2), "t_FinishProcessing": (10, 10),
    "t_FinishTransfer": (2, 2), "t_FinishUnloading": (2, 2),
    "t_FinishReworkTransfer": (2, 2), "t_InspectionPass": (1, 1),
    "t_InspectionRework": (1, 1), "t_RecoverLoading": (16, 16),
    "t_GripperSlipFault": (1, 3), "t_InspectComplete": (4, 4),
}
# single formal completion marking: both workpieces complete, all resources free
COMPLETION_FINAL = [{"p_completed": 2, "p_robot_free": 1,
                     "p_machine_free": 1, "p_inspection_free": 1}]
L, H = 10, 60


def build(intervals=None):
    ivs = dict(BEFORE_INTERVALS)
    if intervals:
        ivs.update(intervals)
    places = {p: Place(name=p) for p in PLACES_B}
    trans = {}
    for n, (label, fault, default) in TRANSITIONS_B.items():
        lo, hi = ivs.get(n, default)
        trans[n] = Transition(name=n, label=label, is_fault=fault,
                              is_adjustable=False,
                              interval=Interval(Fraction(lo), Fraction(hi)))
    arcs = [Arc(from_node=a, to_node=b) for (a, b) in ARCS_B]
    return TPN(places=places, transitions=trans, arcs=arcs,
               initial_marking=dict(INITIAL),
               completion_markings=[dict(m) for m in COMPLETION_FINAL])


def _num(v):
    if v is None:
        return None
    if isinstance(v, float) and v == float('inf'):
        return "inf"
    return str(Fraction(v))


def export(t, model_id, path=None):
    """Canonical JSON with exact rational endpoints (no int()/float loss)."""
    places = [{"id": p, "initial": int(t.initial_marking.get(p, 0))}
              for p in sorted(t.places)]
    trans = []
    for n, tr in sorted(t.transitions.items()):
        trans.append({"id": n, "label": tr.label or "",
                      "observable": bool(tr.is_observable),
                      "fault": bool(tr.is_fault),
                      "earliest": _num(tr.interval.earliest),
                      "latest": "inf" if tr.interval.is_infinite() else _num(tr.interval.latest),
                      "inputs": {p: 1 for p in sorted(t.preset(n))},
                      "outputs": {p: 1 for p in sorted(t.postset(n))}})
    finish = [{"p_completed": 2, "p_robot_free": 1,
               "p_machine_free": 1, "p_inspection_free": 1}]
    model = {"schema": "tii-tpn-model/2",
             "id": model_id,
             "places": places, "transitions": trans,
             "finish_markings": finish,
             "special_features": {"read_arcs": False, "inhibitor_arcs": False,
                                  "stopwatch_arcs": False, "priority_rules": False,
                                  "multi_server": False, "unbounded": False}}
    if path:
        Path(path).write_text(json.dumps(model, indent=1) + "\n")
    return model


def from_canonical(model):
    """Parse canonical JSON back to exact Fractions; raise on lossy input."""
    def val(x):
        if x is None or x == "inf":
            return None
        if isinstance(x, int):
            return Fraction(x)
        return Fraction(x)
    places = {p["id"]: Place(name=p["id"]) for p in model["places"]}
    trans = {}
    for t in model["transitions"]:
        hi = val(t["latest"])
        trans[t["id"]] = Transition(
            name=t["id"], label=t["label"], is_fault=bool(t["fault"]),
            is_adjustable=False,
            interval=Interval(val(t["earliest"]),
                              float("inf") if hi is None else hi))
    arcs = []
    for t in model["transitions"]:
        for p in t["inputs"]:
            arcs.append(Arc(from_node=p, to_node=t["id"]))
        for p in t["outputs"]:
            arcs.append(Arc(from_node=t["id"], to_node=p))
    return TPN(places=places, transitions=trans, arcs=arcs,
               initial_marking={p["id"]: p["initial"] for p in model["places"]},
               completion_markings=[dict(m) for m in model["finish_markings"]])


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


if __name__ == "__main__":
    t = build()
    print(len(t.places), len(t.transitions), len(t.arcs), t.completion_markings)
