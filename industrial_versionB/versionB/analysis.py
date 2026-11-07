"""Helpers: export a candidate TPN to canonical JSON and compute completion intervals."""
from __future__ import annotations
import json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "tpn-illustrative-case"
LIT = ROOT / "literature_tpn_case_eval"
sys.path.insert(0, str(PROD)); sys.path.insert(0, str(PROD / "scripts"))
sys.path.insert(0, str(LIT / "pipeline"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import models  # noqa: E402
import scg as lit  # noqa: E402


def export(t, name, path):
    places = [{"id": p, "initial": int(t.initial_marking.get(p, 0))} for p in sorted(t.places)]
    trans = []
    for n, tr in sorted(t.transitions.items()):
        trans.append({"id": n, "label": tr.label or "", "observable": bool(tr.is_observable),
                      "fault": bool(tr.is_fault), "earliest": int(tr.interval.earliest),
                      "latest": None if tr.interval.is_infinite() else int(tr.interval.latest),
                      "inputs": {p: 1 for p in sorted(t.preset(n))},
                      "outputs": {p: 1 for p in sorted(t.postset(n))}})
    cm = [dict(m) for m in t.completion_markings]
    model = {"schema": "tii-tpn-model/1", "id": name, "places": places,
             "transitions": trans, "finish_markings": cm,
             "special_features": {}}
    Path(path).write_text(json.dumps(model, indent=1))
    return model


def completion_paths(model, H=45, L=10):
    g = lit.SCG(model, max_classes=200_000).build()
    finish = set(g.summary()["finish_classes"])
    adj = defaultdict(list)
    for (s, t, d) in g.edges:
        adj[s].append((t, d))
    tr = {x["id"]: x for x in model["transitions"]}
    oracle = lit.FiringDomain(model)
    out = {}
    for label, need in (("normal", False), ("fault", True)):
        start = (0, False)
        parent = {start: (None, None)}
        q = [start]
        found = None
        while q:
            cur = q.pop(0)
            cid, fs = cur
            if cid in finish and fs == need:
                seq = []
                while parent[cur][0] is not None:
                    prev, t = parent[cur]
                    seq.append(t)
                    cur = prev
                found = list(reversed(seq))
                break
            for t, d in adj[cid]:
                nxt = (d, fs or tr[t]["fault"])
                if nxt not in parent:
                    parent[nxt] = (cur, t)
                    q.append(nxt)
        if found is None:
            out[label] = None
            continue
        iv = oracle.interval(found)
        out[label] = {"sequence": found, "length": len(found),
                      "observable": sum(1 for t in found if tr[t]["observable"]),
                      "interval": [str(iv[0]), str(iv[1])],
                      "within_H": iv[0] <= H}
    out["scg_classes"] = len(g.classes)
    out["scg_edges"] = len(g.edges)
    return out


def analyze_candidate(name, H=45):
    t = models.build(name)
    model = export(t, name, f"/tmp/{name}.json")
    return t, completion_paths(model, H=H)
