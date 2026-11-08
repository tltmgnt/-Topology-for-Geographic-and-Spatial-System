"""Synthetic v2 full-report benchmark; run from the checkout root.

Reports elapsed wall time and traced Python peak bytes, without pass/fail timing thresholds.
"""
import json
from pathlib import Path
import sys
import time
import tracemalloc
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spatial_topology.analysis import build_report


def study(size):
    nodes = [{'type': 'Feature', 'id': str(i), 'properties': {'kind': 'node'},
              'geometry': {'type': 'Point', 'coordinates': [i / 1000, (i % 2) / 1000]}} for i in range(size)]
    edges = []
    for i in range(size):
        for step in (1, 2):
            target = (i + step) % size
            edges.append({'type': 'Feature', 'id': f'{i}-{target}',
                          'properties': {'kind': 'edge', 'source': str(i), 'target': str(target), 'directed': True, 'cost': step},
                          'geometry': {'type': 'LineString', 'coordinates': [nodes[i]['geometry']['coordinates'], nodes[target]['geometry']['coordinates']]}})
    policy = {'schema_version': 2, 'required_nodes': ['0'], 'required_paths': [
        {'id': 'access', 'source': '0', 'target': str(size - 1), 'max_distance_m': 1e9, 'require_redundancy': True}],
        'disabled_nodes': [], 'disabled_edges': []}
    return {'type': 'FeatureCollection', 'features': nodes + edges}, policy


if __name__ == '__main__':
    results = []
    for size in (16, 40, 80):
        data, policy = study(size)
        tracemalloc.start()
        start = time.perf_counter()
        result = build_report(data, policy)
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        results.append({'nodes': size, 'edges': size*2, 'seconds': round(elapsed, 4), 'python_peak_bytes': peak,
                        'independent_verification': result['independent_verification']['status']})
    print(json.dumps(results, indent=2))
