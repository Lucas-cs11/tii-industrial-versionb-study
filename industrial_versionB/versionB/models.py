#!/usr/bin/env python3
"""Version B candidate models built on top of the frozen Version A structure.

Version A remains untouched.  Each B candidate is an independent TPN built from
the same place/transition tuples plus the minimal control mechanism that makes
the fault delay enter the task-critical chain.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "tpn-illustrative-case"
sys.path.insert(0, str(PROD)); sys.path.insert(0, str(PROD / "scripts"))
from src.model.tpn import TPN, Transition, Interval, Arc, Place  # noqa: E402
from model_case import PLACES, TRANSITIONS, ARCS, INITIAL, COMPLETION, build as build_A  # noqa: E402


def _mk(places, transitions, arcs, completion):
    return TPN(places={p: Place(name=p) for p in places},
               transitions={n: Transition(name=n, label=lab, is_fault=fault,
                                          is_adjustable=False, interval=Interval(lo, hi))
                            for n, (lab, fault, (lo, hi)) in transitions.items()},
               arcs=[Arc(from_node=a, to_node=b) for a, b in arcs],
               initial_marking=dict(INITIAL),
               completion_markings=[dict(m) for m in completion])


def _arcs_set(arcs):
    return list(dict.fromkeys(arcs))


def build_B1():
    """B1: the shared robot stays occupied during slip recovery.

    Version A releases the robot at the fault instant and re-acquires it for
    recovery, so the other workpiece can use the robot while the faulted one
    recovers -> fault delay hidden in makespan slack.  B1 keeps the robot
    occupied for the whole fault+recovery interval.
    """
    places = PLACES + ["p_robot_held"]
    trans = dict(TRANSITIONS)
    arcs = []
    for (a, b, w) in ARCS:
        if (a, b) in {("t_GripperSlipFault", "p_robot_free"),
                      ("p_robot_free", "t_RecoverLoading")}:
            continue
        arcs.extend([(a, b)] * w)
    # The robot is already held from StartLoading until the operation ends;
    # the fault keeps it occupied for the whole recovery and only the recovery
    # releases it.
    arcs += [("t_GripperSlipFault", "p_robot_held"),
             ("p_robot_held", "t_RecoverLoading"),
             ("t_RecoverLoading", "p_robot_free")]
    return _mk(places, trans, _arcs_set(arcs), COMPLETION)


def build_B2():
    """B2: hidden machine tool/positioning fault with real recovery occupancy.

    The machine token is already held during processing; the unobservable tool
    fault stops the operation and the machine remains occupied through the
    recovery, then processing restarts.
    """
    places = PLACES + ["p_machine_recovery"]
    trans = dict(TRANSITIONS)
    trans["t_ToolFault"] = ("", True, (4, 12))
    trans["t_ToolRecover"] = ("", False, (3, 5))
    arcs = [(a, b) for (a, b, w) in ARCS for _ in range(w)] + [
        ("p_processing", "t_ToolFault"), ("t_ToolFault", "p_machine_recovery"),
        ("p_machine_recovery", "t_ToolRecover"), ("t_ToolRecover", "p_processing"),
    ]
    return _mk(places, trans, _arcs_set(arcs), COMPLETION)


def build_B3():
    """B3: controlled shared hand-off at the unload station.

    The single unload station is an explicit shared resource; the two
    workpieces must be released through it, coupling their completion order.
    """
    places = PLACES + ["p_unload_free"]
    trans = dict(TRANSITIONS)
    arcs = []
    for (a, b, w) in ARCS:
        arcs.extend([(a, b)] * w)
    # StartUnloading acquires the station, FinishUnloading releases it.
    arcs = [x for x in arcs if x != ("p_robot_free", "t_StartUnloading")]
    arcs += [("p_robot_free", "t_StartUnloading"), ("p_unload_free", "t_StartUnloading"),
             ("t_FinishUnloading", "p_unload_free")]
    completion = [dict(m, p_unload_free=1) for m in COMPLETION]
    base = _mk(places, trans, _arcs_set(arcs), completion)
    base.initial_marking["p_unload_free"] = 1
    return base


CANDIDATES = {"B1": build_B1, "B2": build_B2, "B3": build_B3}


def build(name):
    if name == "A":
        return build_A()
    return CANDIDATES[name]()


if __name__ == "__main__":
    for name in ("A", "B1", "B2", "B3"):
        t = build(name)
        print(name, len(t.places), len(t.transitions), len(t.arcs))


def build_B1min():
    """B1-min: robot is held through fault + recovery, no extra marker place.

    StartLoading already removes the robot token; the fault must therefore not
    release it, and the recovery must not re-acquire it.  The robot becomes
    free only when FinishLoading (normal) or the post-recovery FinishLoading
    fires.  The fault can be attempted again after a recovery, so the SCG is
    the honest timed behaviour (no artificial one-shot restriction).
    """
    places = list(PLACES)
    trans = dict(TRANSITIONS)
    arcs = []
    for (a, b, w) in ARCS:
        if (a, b) in {("t_GripperSlipFault", "p_robot_free"),
                      ("p_robot_free", "t_RecoverLoading")}:
            continue
        arcs.extend([(a, b)] * w)
    return _mk(places, trans, arcs, COMPLETION)


def build_B2p():
    """B2': one-shot hidden tool fault during machining, machine held in recovery."""
    places = PLACES + ["p_tool_fault", "p_processing_resumed"]
    trans = dict(TRANSITIONS)
    trans["t_ToolFault"] = ("", True, (4, 12))
    trans["t_ToolRecover"] = ("", False, (3, 5))
    trans["t_FinishRecovered"] = ("machining_done", False, (4, 6))
    arcs = [(a, b) for (a, b, w) in ARCS for _ in range(w)]
    arcs += [
        ("p_processing", "t_ToolFault"), ("t_ToolFault", "p_tool_fault"),
        ("p_tool_fault", "t_ToolRecover"), ("t_ToolRecover", "p_processing_resumed"),
        ("p_processing_resumed", "t_FinishRecovered"),
        ("t_FinishRecovered", "p_wait_transfer"),
        ("t_FinishRecovered", "p_machine_free"),
    ]
    return _mk(places, trans, arcs, COMPLETION)


CANDIDATES.update({"B1min": build_B1min, "B2p": build_B2p})


def build_B1v2():
    """B1-v2: 19P/16T robot-recovery-occupancy variant.

    Split recovery into a re-grip step and a controlled resume step; an explicit
    ``p_robot_held`` token records that the shared robot stays occupied from the
    slip until the resume, so the other workpiece cannot use it.
    """
    places = PLACES + ["p_robot_held", "p_regrip_done"]
    trans = {k: v for k, v in TRANSITIONS.items() if k != "t_RecoverLoading"}
    trans["t_Regrip"] = ("", False, (0, 0))      # interval frozen by the study
    trans["t_Resume"] = ("", False, (0, 0))      # interval frozen by the study
    arcs = []
    for (a, b, w) in ARCS:
        if (a, b) in {("t_GripperSlipFault", "p_robot_free"),
                      ("p_robot_free", "t_RecoverLoading"),
                      ("p_grip_recovery", "t_RecoverLoading"),
                      ("t_RecoverLoading", "p_loading")}:
            continue
        arcs.extend([(a, b)] * w)
    arcs += [("t_GripperSlipFault", "p_robot_held"),
             ("p_grip_recovery", "t_Regrip"), ("t_Regrip", "p_regrip_done"),
             ("p_regrip_done", "t_Resume"), ("p_robot_held", "t_Resume"),
             ("t_Resume", "p_loading"), ("t_Resume", "p_robot_free")]
    return _mk(places, trans, list(dict.fromkeys(arcs)), COMPLETION)


CANDIDATES["B1v2"] = build_B1v2


def build_B1v3():
    """B1-v3: 18P/16T robot-hold variant with split recovery, no marker place.

    Fault: p_loading -> p_grip_recovery (robot stays held, no release).
    Regrip: p_grip_recovery -> p_regrip_done.
    Resume: p_regrip_done -> p_loading + p_robot_free.
    Normal FinishLoading releases the robot as before.
    """
    places = PLACES + ["p_regrip_done"]
    trans = {k: v for k, v in TRANSITIONS.items() if k != "t_RecoverLoading"}
    trans["t_Regrip"] = ("", False, (0, 0))
    trans["t_Resume"] = ("", False, (0, 0))
    arcs = []
    for (a, b, w) in ARCS:
        if (a, b) in {("t_GripperSlipFault", "p_robot_free"),
                      ("p_robot_free", "t_RecoverLoading"),
                      ("p_grip_recovery", "t_RecoverLoading"),
                      ("t_RecoverLoading", "p_loading")}:
            continue
        arcs.extend([(a, b)] * w)
    arcs += [("p_grip_recovery", "t_Regrip"), ("t_Regrip", "p_regrip_done"),
             ("p_regrip_done", "t_Resume"), ("t_Resume", "p_loading"),
             ("t_Resume", "p_robot_free")]
    return _mk(places, trans, list(dict.fromkeys(arcs)), COMPLETION)


CANDIDATES["B1v3"] = build_B1v3


def build_B1v4():
    """B1-v4 (18P/16T): robot held through fault+recovery, plus an explicit
    inspection-dwell / decision split (industrial inspection station refinement).

    Structure = B1-min (robot not released at the slip, released only when the
    post-recovery loading completes) + p_inspect_done and t_InspectComplete.
    """
    base = build_B1min()
    places = list(base.places) + ["p_inspect_done"]
    trans = dict(TRANSITIONS)
    trans["t_InspectComplete"] = ("", False, (4, 4))
    arcs = []
    for (a, b, w) in ARCS:
        if (a, b) in {("t_GripperSlipFault", "p_robot_free"),
                      ("p_robot_free", "t_RecoverLoading"),
                      ("p_inspecting", "t_InspectionPass"),
                      ("p_inspecting", "t_InspectionRework")}:
            continue
        arcs.extend([(a, b)] * w)
    arcs += [("p_inspecting", "t_InspectComplete"),
             ("t_InspectComplete", "p_inspect_done"),
             ("p_inspect_done", "t_InspectionPass"),
             ("p_inspect_done", "t_InspectionRework")]
    return _mk(places, trans, list(dict.fromkeys(arcs)), COMPLETION)


CANDIDATES["B1v4"] = build_B1v4
