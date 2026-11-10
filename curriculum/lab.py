"""Offline curriculum answer key. Synthetic checks, never operational approval."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
for base in (ROOT, ROOT / "src", ROOT / "layer-b"):
    sys.path.insert(0, str(base))
CASES = []

def check(name, actual, expected):
    passed = actual == expected
    CASES.append({"case": name, "actual": actual, "expected": expected, "passed": passed})
    if not passed:
        raise AssertionError(f"{name}: expected {expected!r}, got {actual!r}")

def rejects(name, call, error=ValueError):
    try:
        call()
    except error:
        check(name, error.__name__, error.__name__)
    else:
        raise AssertionError(f"{name}: expected {error.__name__}")




def run():
    from spatial_topology.analysis import components, shortest_path
    # Explicit synthetic adjacency: edge costs are supplied metres, not travel times.
    graph = {"a":[("b","ab",2.0)],"b":[("a","ab",2.0),("c","bc",3.0)],
             "c":[("b","bc",3.0)],"d":[]}
    check("isolated vertex remains visible", components(graph), [["a","b","c"],["d"]])
    check("weighted route a-to-c", shortest_path(graph,"a","c"),
          {"nodes":["a","b","c"],"edges":["ab","bc"],"distance_m":5.0})
    check("edge bc is a separating bridge", components(graph,skip_edge="bc"), [["a","b"],["c"],["d"]])
    check("vertex b separates the chain", components(graph,skip_node="b"), [["a"],["c"],["d"]])
    check("unreachable endpoint returns explicit missing route", shortest_path(graph,"a","d"), None)
    check("zero-length self route", shortest_path(graph,"a","a")["distance_m"], 0.0)

if __name__ == "__main__":
    if sys.argv[1:] not in ([], ["--verify"]):
        raise SystemExit("Usage: python curriculum/lab.py [--verify]")
    run()
    report = {"schema_version": 1, "status": "PASS", "case_count": len(CASES),
              "cases": CASES, "scope": "Synthetic curriculum checks only"}
    if sys.argv[1:] == ["--verify"]:
        expected = json.loads((Path(__file__).parent / "expected.json").read_text())
        if report != expected:
            raise AssertionError("Observed answers differ from curriculum/expected.json")
    print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))
