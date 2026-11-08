"""Deterministic undirected multigraph analysis and explicit requirement gaps."""
import hashlib
import heapq
import json
from .model import parse_network, parse_requirements

ENGINE_VERSION = '0.1.0'


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def adjacency(network, requirements):
    disabled = set(requirements['disabled_nodes'])
    graph = {name: [] for name in sorted(network.nodes) if name not in disabled}
    for edge in sorted(network.edges.values(), key=lambda e: e.id):
        if edge.id not in requirements['disabled_edges'] and edge.source in graph and edge.target in graph:
            graph[edge.source].append((edge.target, edge.id, edge.distance_m))
            graph[edge.target].append((edge.source, edge.id, edge.distance_m))
    return graph


def components(graph, skip_node=None, skip_edge=None):
    remaining = set(graph) - {skip_node}
    groups = []
    while remaining:
        start = min(remaining)
        found, pending = {start}, [start]
        remaining.remove(start)
        while pending:
            node = pending.pop()
            for other, edge, _ in graph[node]:
                if other != skip_node and edge != skip_edge and other in remaining:
                    remaining.remove(other)
                    found.add(other)
                    pending.append(other)
        groups.append(sorted(found))
    return groups


def shortest_path(graph, source, target):
    if source not in graph or target not in graph:
        return None
    distances, previous, visited = {source: 0.0}, {}, set()
    pending = [(0.0, source)]
    while pending:
        cost, node = heapq.heappop(pending)
        if node in visited:
            continue
        visited.add(node)
        if node == target:
            nodes, edges = [target], []
            while nodes[-1] != source:
                parent, edge = previous[nodes[-1]]
                nodes.append(parent)
                edges.append(edge)
            return {'nodes': list(reversed(nodes)), 'edges': list(reversed(edges)),
                    'distance_m': cost}
        for other, edge, weight in graph[node]:
            candidate = cost + weight
            if other not in visited and candidate < distances.get(other, float('inf')):
                distances[other] = candidate
                previous[other] = (node, edge)
                heapq.heappush(pending, (candidate, other))
    return None


def build_report(geojson, requirements):
    if type(requirements) is dict and requirements.get('schema_version') == 2:
        from .engine2 import build_report_v2
        return build_report_v2(geojson, requirements)
    network = parse_network(geojson)
    policy = parse_requirements(requirements, network)
    graph = adjacency(network, policy)
    groups = components(graph)
    count = len(groups)
    active_edges = sorted({edge for neighbors in graph.values() for _, edge, _ in neighbors})
    bridges = [edge for edge in active_edges if len(components(graph, skip_edge=edge)) > count]
    articulations = [node for node in sorted(graph) if len(components(graph, skip_node=node)) > count]
    missing = sorted(set(policy['required_nodes']) - set(network.nodes))
    unavailable = sorted(set(policy['required_nodes']) & set(policy['disabled_nodes']))
    checks, gaps = [], []
    for node in missing:
        gaps.append({'code': 'MISSING_REQUIRED_NODE', 'subject': node})
    for node in unavailable:
        gaps.append({'code': 'UNAVAILABLE_REQUIRED_NODE', 'subject': node})
    for item in policy['required_paths']:
        route = shortest_path(graph, item['source'], item['target'])
        reasons = []
        if item['source'] not in network.nodes or item['target'] not in network.nodes:
            reasons.append('MISSING_ENDPOINT')
        elif item['source'] not in graph or item['target'] not in graph:
            reasons.append('UNAVAILABLE_ENDPOINT')
        elif route is None:
            reasons.append('NO_PATH')
        if route:
            # Compare unrounded distances to avoid boundary-induced false acceptance.
            if route['distance_m'] > item['max_distance_m']:
                reasons.append('DISTANCE_LIMIT_EXCEEDED')
            separating = sorted(set(route['edges']) & set(bridges))
            if item['require_redundancy'] and separating:
                reasons.append('SINGLE_EDGE_FAILURE_EXPOSURE')
            route = {**route, 'distance_m': round(route['distance_m'], 6)}
        else:
            separating = []
        checks.append({'requirement': item, 'status': 'FAIL' if reasons else 'PASS',
                       'reasons': reasons, 'route': route, 'separating_bridges': separating})
        gaps.extend({'code': reason, 'subject': item['id']} for reason in reasons)
    required_count = len(policy['required_nodes'])
    observed_count = required_count - len(missing) - len(unavailable)
    return {'schema_version': 1, 'engine_version': ENGINE_VERSION,
            'input_sha256': fingerprint(geojson), 'requirements_sha256': fingerprint(requirements),
            'status': 'GAPS_FOUND' if gaps else 'REQUIREMENTS_SATISFIED',
            'requirements': policy,
            'summary': {'nodes': len(network.nodes), 'edges': len(network.edges),
                        'active_nodes': len(graph), 'active_edges': len(active_edges),
                        'components': len(groups), 'gap_count': len(gaps)},
            'required_node_coverage': observed_count / required_count if required_count else None,
            'components': groups, 'isolated_nodes': sorted(node for node in graph if not graph[node]),
            'bridges': bridges, 'articulation_nodes': articulations,
            'disabled_nodes': policy['disabled_nodes'],
            'inactive_edges': sorted(set(network.edges) - set(active_edges)),
            'path_checks': checks, 'gaps': gaps,
            'execution_authorized': False,
            'limitations': ['Declared undirected topology; crossings do not imply junctions',
                            'Approximate spherical vertex-to-vertex distances, not travel time or survey precision',
                            'Redundancy means endpoint connectivity after any single active edge loss, not bounded detour length',
                            'Requirements satisfied is a scoped graph result, not real-world readiness or safety certification',
                            'Input hashes establish consistency, not source authenticity or completeness']}
