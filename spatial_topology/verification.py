"""Independent Bellman-Ford and edge-removal closure checks for v2 paths.

Does not call the production adjacency, Dijkstra, or reachability implementations.
"""
import math


def verify_algorithms(network, options, policy, result):
    nodes = sorted(set(network.nodes) - set(policy['disabled_nodes']))
    arcs = []
    for e in network.edges.values():
        if e.id in policy['disabled_edges'] or e.source not in nodes or e.target not in nodes:
            continue
        directed, cost = options[e.id]
        weight = e.distance_m if cost is None else cost
        arcs.append((e.source, e.target, e.id, weight))
        if not directed:
            arcs.append((e.target, e.source, e.id, weight))
    checked = 0
    for check in result['path_checks']:
        item = check['requirement']
        source, target = item['source'], item['target']
        distances = {n: float('inf') for n in nodes}
        if source in distances:
            distances[source] = 0.0
        for _ in range(max(0, len(nodes) - 1)):
            changed = False
            for a, b, _, cost in arcs:
                if distances[a] + cost < distances[b]:
                    distances[b] = distances[a] + cost
                    changed = True
            if not changed:
                break
        route = check['route']
        expected = distances.get(target, float('inf'))
        if (route is None) != math.isinf(expected):
            raise ValueError('independent verification: reachability mismatch')
        if route is not None:
            route_nodes, route_edges = route['nodes'], route['edges']
            if (not route_nodes or route_nodes[0] != source or route_nodes[-1] != target
                    or len(route_nodes) != len(route_edges) + 1 or len(set(route_nodes)) != len(route_nodes)):
                raise ValueError('independent verification: invalid route sequence')
            actual_cost = 0.0
            actual_distance = 0.0
            for a, b, edge in zip(route_nodes, route_nodes[1:], route_edges):
                choices = [cost for x, y, e, cost in arcs if (x, y, e) == (a, b, edge)]
                if len(choices) != 1:
                    raise ValueError('independent verification: invalid route arc')
                actual_cost += choices[0]
                actual_distance += network.edges[edge].distance_m
            if not math.isclose(route['cost'], actual_cost, rel_tol=1e-12, abs_tol=0.000001):
                raise ValueError('independent verification: route sum mismatch')
            if not math.isclose(route['distance_m'], actual_distance, rel_tol=1e-12, abs_tol=0.000001):
                raise ValueError('independent verification: distance mismatch')
            if not math.isclose(route['cost'], expected, rel_tol=1e-12, abs_tol=0.000001):
                raise ValueError('independent verification: cost mismatch')
            separating = []
            for removed in route['edges']:
                seen = {source}
                for _ in nodes:
                    expanded = seen | {b for a, b, edge, _ in arcs if a in seen and edge != removed}
                    if expanded == seen:
                        break
                    seen = expanded
                if target not in seen:
                    separating.append(removed)
            if sorted(separating) != check['separating_edges']:
                raise ValueError('independent verification: redundancy mismatch')
        checked += 1
    return {'status': 'PASS', 'checked_paths': checked,
            'methods': ['Bellman-Ford costs', 'fixed-point closure after individual edge removal'],
            'scope': 'baseline path reachability, minimum costs and separating edges; not a full report audit'}
