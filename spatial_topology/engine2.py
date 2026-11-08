"""Opt-in v2 directed, weighted, bounded network assurance.

No optional geospatial or database package is imported by this module.
"""
from copy import deepcopy
from .analysis import fingerprint, components, shortest_path
from .model import fields, finite, identifier, parse_network, parse_requirements, unique_ids

VERSION = '2.0.0'
MAX_SCENARIOS = 32
MAX_POLYGONS = 100


def parse_v2(data):
    fields(data, {'type', 'features'})
    if data['type'] != 'FeatureCollection' or not isinstance(data['features'], list):
        raise ValueError('FeatureCollection required')
    if not 1 <= len(data['features']) <= 1400:
        raise ValueError('feature count outside v2 limits')
    base = {'type': 'FeatureCollection', 'features': []}
    options, polygons, seen = {}, [], set()
    for feature in data['features']:
        fields(feature, {'type', 'id', 'geometry', 'properties'})
        if feature['type'] != 'Feature':
            raise ValueError('Feature required')
        name = identifier(feature['id'])
        if name in seen:
            raise ValueError('duplicate feature ID')
        seen.add(name)
        geometry, props = feature['geometry'], feature['properties']
        fields(geometry, {'type', 'coordinates'})
        if geometry['type'] in ('Polygon', 'MultiPolygon'):
            fields(props, {'kind'}, {'label'})
            if props['kind'] != 'polygon':
                raise ValueError('polygon kind required')
            if 'label' in props:
                identifier(props['label'])
            polygons.append(feature)
            if len(polygons) > MAX_POLYGONS:
                raise ValueError('at most 100 polygons permitted')
            continue
        item = deepcopy(feature)
        if geometry['type'] == 'LineString':
            fields(props, {'kind', 'source', 'target'}, {'directed', 'cost'})
            directed = props.get('directed', False)
            if type(directed) is not bool:
                raise ValueError('directed must be a boolean')
            cost = finite(props['cost']) if 'cost' in props else None
            options[name] = (directed, cost)
            item['properties'] = {k: props[k] for k in ('kind', 'source', 'target')}
        base['features'].append(item)
    network = parse_network(base)
    from .polygons import validate_coordinates
    polygon_count, xs = validate_coordinates(polygons)
    xs.extend(n.coordinates[0] for n in network.nodes.values())
    xs.extend(p[0] for e in network.edges.values() for p in e.coordinates)
    vertices = len(network.nodes) + sum(len(e.coordinates) for e in network.edges.values()) + polygon_count
    if vertices > 20000 or max(xs) - min(xs) > 180:
        raise ValueError('combined regional geometry limits exceeded')
    return network, options, polygons


def policy_v2(data, network):
    fields(data, {'schema_version', 'required_nodes', 'required_paths', 'disabled_nodes', 'disabled_edges'},
           {'scenarios', 'provenance'})
    if type(data['schema_version']) is not int or data['schema_version'] != 2:
        raise ValueError('requirements schema version 2 required')
    legacy = {k: deepcopy(data[k]) for k in ('required_nodes', 'required_paths', 'disabled_nodes', 'disabled_edges')}
    legacy['schema_version'] = 1
    costs = {}
    if not isinstance(legacy['required_paths'], list):
        raise ValueError('bounded required paths required')
    for path in legacy['required_paths']:
        if not isinstance(path, dict):
            raise ValueError('path object required')
        if 'max_cost' in path:
            costs[identifier(path.get('id'))] = finite(path.pop('max_cost'))
    result = parse_requirements(legacy, network)
    result['schema_version'] = 2
    for path in result['required_paths']:
        if path['id'] in costs:
            path['max_cost'] = costs[path['id']]
    scenarios = data.get('scenarios', [])
    if not isinstance(scenarios, list) or len(scenarios) > MAX_SCENARIOS:
        raise ValueError('at most 32 explicit failure scenarios permitted')
    normalized, seen = [], set()
    for scenario in scenarios:
        fields(scenario, {'id', 'disabled_nodes', 'disabled_edges'})
        name = identifier(scenario['id'])
        if name in seen:
            raise ValueError('duplicate scenario ID')
        seen.add(name)
        nodes = unique_ids(scenario['disabled_nodes'], 300)
        edges = unique_ids(scenario['disabled_edges'], 1000)
        if set(nodes) - set(network.nodes) or set(edges) - set(network.edges):
            raise ValueError('unknown failure object')
        normalized.append({'id': name, 'disabled_nodes': nodes, 'disabled_edges': edges})
    result['scenarios'] = sorted(normalized, key=lambda s: s['id'])
    provenance = data.get('provenance', {})
    fields(provenance, set(), {'source', 'dataset_version', 'captured_at', 'source_sha256'})
    for key, value in provenance.items():
        identifier(value)
        if key == 'source_sha256' and (len(value) != 64 or any(c not in '0123456789abcdef' for c in value)):
            raise ValueError('source_sha256 must be a lowercase SHA256 digest')
    if 'captured_at' in provenance:
        from datetime import datetime
        try:
            timestamp = datetime.fromisoformat(provenance['captured_at'].replace('Z', '+00:00'))
        except ValueError as error:
            raise ValueError('captured_at requires an ISO8601 timestamp with timezone') from error
        if timestamp.tzinfo is None:
            raise ValueError('captured_at requires a timezone')
    # Bound the repeated traversal study as well as input bytes/counts.
    effort = (1 + len(normalized)) * max(1, len(result['required_paths'])) * (len(network.nodes) + len(network.edges)) ** 2
    if effort > 25000000:
        raise ValueError('v2 traversal budget exceeded; reduce scenarios, paths or network size')
    result['provenance'] = dict(provenance)
    return result


def graph_for(network, options, policy, weak=False):
    graph = {n: [] for n in sorted(network.nodes) if n not in policy['disabled_nodes']}
    for edge in sorted(network.edges.values(), key=lambda e: e.id):
        if edge.id in policy['disabled_edges'] or edge.source not in graph or edge.target not in graph:
            continue
        directed, cost = options[edge.id]
        weight = edge.distance_m if cost is None else cost
        graph[edge.source].append((edge.target, edge.id, weight))
        if weak or not directed:
            graph[edge.target].append((edge.source, edge.id, weight))
    return graph


def reachable(graph, start, skip_edge=None, skip_node=None):
    if start not in graph or start == skip_node:
        return set()
    found, pending = {start}, [start]
    while pending:
        node = pending.pop()
        for other, edge, _ in graph[node]:
            if other != skip_node and edge != skip_edge and other not in found:
                found.add(other)
                pending.append(other)
    return found


def strong_components(graph):
    reach = {n: reachable(graph, n) for n in graph}
    remaining, result = set(graph), []
    while remaining:
        node = min(remaining)
        group = sorted(n for n in remaining if n in reach[node] and node in reach[n])
        remaining.difference_update(group)
        result.append(group)
    return result


def evaluate(network, options, policy):
    graph = graph_for(network, options, policy)
    weak = graph_for(network, options, policy, weak=True)
    groups = components(weak)
    active = sorted({e for neighbors in graph.values() for _, e, _ in neighbors})
    bridges = [e for e in active if len(components(weak, skip_edge=e)) > len(groups)]
    articulations = [n for n in graph if len(components(weak, skip_node=n)) > len(groups)]
    gaps, checks = [], []
    missing = sorted(set(policy['required_nodes']) - set(network.nodes))
    unavailable = sorted(set(policy['required_nodes']) & set(policy['disabled_nodes']))
    for code, names in [('MISSING_REQUIRED_NODE', missing), ('UNAVAILABLE_REQUIRED_NODE', unavailable)]:
        gaps.extend({'code': code, 'subject': n} for n in names)
    for item in policy['required_paths']:
        source, target = item['source'], item['target']
        route = shortest_path(graph, source, target)
        reasons, separating = [], []
        if source not in network.nodes or target not in network.nodes:
            reasons.append('MISSING_ENDPOINT')
        elif source not in graph or target not in graph:
            reasons.append('UNAVAILABLE_ENDPOINT')
        elif route is None:
            reasons.append('NO_PATH')
        if route is not None:
            cost = route['distance_m']  # Generic Dijkstra weight; distance is separately summed.
            length = sum(network.edges[e].distance_m for e in route['edges'])
            if length > item['max_distance_m']:
                reasons.append('DISTANCE_LIMIT_EXCEEDED')
            if 'max_cost' in item and cost > item['max_cost']:
                reasons.append('COST_LIMIT_EXCEEDED')
            separating = sorted(e for e in route['edges'] if target not in reachable(graph, source, skip_edge=e))
            if item['require_redundancy'] and separating:
                reasons.append('SINGLE_EDGE_FAILURE_EXPOSURE')
            route = {**route, 'cost': round(cost, 6), 'distance_m': round(length, 6)}
        checks.append({'requirement': item, 'status': 'FAIL' if reasons else 'PASS', 'reasons': reasons,
                       'route': route, 'separating_edges': separating})
        gaps.extend({'code': reason, 'subject': item['id']} for reason in reasons)
    # Scores describe only baseline reachable required ordered pairs. Endpoint failures count as loss.
    pairs = [(p['requirement']['source'], p['requirement']['target']) for p in checks if p['route'] is not None]
    def survival(objects, node_failure=False):
        if not pairs or not objects:
            return None
        passed = 0
        for obj in objects:
            cache = {}
            for source, target in pairs:
                if source not in cache:
                    cache[source] = reachable(graph, source, skip_node=obj if node_failure else None,
                                              skip_edge=None if node_failure else obj)
                passed += target in cache[source]
        return passed / (len(pairs) * len(objects))
    coverage = len(policy['required_nodes'])
    return {'status': 'GAPS_FOUND' if gaps else 'REQUIREMENTS_SATISFIED',
            'summary': {'nodes': len(network.nodes), 'edges': len(network.edges), 'active_nodes': len(graph),
                        'active_edges': len(active), 'components': len(groups), 'gap_count': len(gaps)},
            'components': groups, 'strong_components': strong_components(graph),
            'isolated_nodes': sorted(n for n in weak if not weak[n]),
            'bridges': bridges, 'articulation_nodes': articulations,
            'disabled_nodes': policy['disabled_nodes'], 'inactive_edges': sorted(set(network.edges) - set(active)),
            'path_checks': checks, 'gaps': gaps,
            'required_node_coverage': (coverage - len(missing) - len(unavailable)) / coverage if coverage else None,
            'resilience': {'scope': 'baseline reachable required paths; endpoint failures count as loss',
                           'required_paths': len(checks), 'reachable_paths': len(pairs),
                           'reachability_ratio': len(pairs) / len(checks) if checks else None,
                           'single_edge_survival_ratio': survival(active),
                           'single_node_survival_ratio': survival(sorted(graph), True)}}


def build_report_v2(geojson, requirements):
    network, options, polygons = parse_v2(geojson)
    policy = policy_v2(requirements, network)
    from .verification import verify_algorithms
    result = evaluate(network, options, policy)
    scenarios = []
    baseline_gaps = {(g['code'], g['subject']) for g in result['gaps']}
    for scenario in policy['scenarios']:
        combined = {**policy,
                    'disabled_nodes': sorted(set(policy['disabled_nodes']) | set(scenario['disabled_nodes'])),
                    'disabled_edges': sorted(set(policy['disabled_edges']) | set(scenario['disabled_edges']))}
        evaluation = evaluate(network, options, combined)
        evaluation['independent_verification'] = verify_algorithms(network, options, combined, evaluation)
        gaps = {(g['code'], g['subject']) for g in evaluation['gaps']}
        scenarios.append({'id': scenario['id'], **evaluation,
                          'new_gaps': [{'code': c, 'subject': s} for c, s in sorted(gaps - baseline_gaps)],
                          'resolved_gaps': [{'code': c, 'subject': s} for c, s in sorted(baseline_gaps - gaps)]})
    relationships = []
    if polygons:
        from .polygons import relationships_for
        relationships = relationships_for(polygons, network)
    verification = verify_algorithms(network, options, policy, result)
    return {'schema_version': 2, 'engine_version': VERSION,
            'input_sha256': fingerprint(geojson), 'requirements_sha256': fingerprint(requirements),
            'requirements': policy, **result, 'scenarios': scenarios, 'polygon_relationships': relationships,
            'study_status': 'GAPS_FOUND' if result['gaps'] or any(s['gaps'] for s in scenarios) else 'REQUIREMENTS_SATISFIED',
            'independent_verification': verification, 'execution_authorized': False,
            'provenance': {'declarations': policy['provenance'], 'authenticated': False},
            'limitations': ['Explicit topology; crossings do not imply junctions; bridges and articulations use weak connectivity',
                            'Routes minimize declared nonnegative cost; absent costs default to spherical metres',
                            'Distance and cost limits apply to the selected least-cost route, not constrained optimization',
                            'Single-edge redundancy is directed reachability, without a fallback distance or cost guarantee',
                            'Resilience ratios are scoped descriptive fractions, not probabilities or safety certification',
                            'Polygon predicates use planar longitude/latitude; no snapping or antimeridian support',
                            'Replay and independent algorithms check consistency, not source authenticity or completeness']}
