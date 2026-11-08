"""Strict bounded regional GeoJSON network and requirement contracts."""
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

MAX_NODES = 300
MAX_EDGES = 1000
MAX_VERTICES = 20000


def fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        raise ValueError('missing or unknown fields')


def identifier(value):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 200:
        raise ValueError('trimmed identifier of 1 to 200 characters required')
    return value


def finite(value, low=0.0, high=1e12):
    if type(value) not in (int, float):
        raise ValueError('finite number required')
    try:
        valid = math.isfinite(value) and low <= value <= high
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('number outside permitted range')
    return float(value)


def position(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('two dimensional longitude latitude position required')
    return (finite(value[0], -180, 180), finite(value[1], -90, 90))


def distance(a, b):
    """Approximate great-circle segment length using a fixed mean-radius sphere."""
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(min(1.0, max(0.0, h))))


@dataclass(frozen=True)
class Node:
    id: str
    coordinates: tuple
    label: str


@dataclass(frozen=True)
class Edge:
    id: str
    source: str
    target: str
    coordinates: tuple
    distance_m: float


@dataclass(frozen=True)
class Network:
    nodes: Mapping[str, Node]
    edges: Mapping[str, Edge]


def parse_network(data):
    """Accept the documented GeoJSON subset; topology is explicit, never inferred."""
    fields(data, {'type', 'features'})
    if data['type'] != 'FeatureCollection' or not isinstance(data['features'], list):
        raise ValueError('FeatureCollection required')
    if not 1 <= len(data['features']) <= MAX_NODES + MAX_EDGES:
        raise ValueError('feature count outside limits')
    nodes, edges, ids, vertices = {}, {}, set(), 0
    pending = []
    for feature in data['features']:
        fields(feature, {'type', 'id', 'properties', 'geometry'})
        if feature['type'] != 'Feature':
            raise ValueError('Feature required')
        name = identifier(feature['id'])
        if name in ids:
            raise ValueError('duplicate feature ID')
        ids.add(name)
        geometry, props = feature['geometry'], feature['properties']
        fields(geometry, {'type', 'coordinates'})
        if geometry['type'] == 'Point':
            fields(props, {'kind'}, {'label'})
            if props['kind'] != 'node':
                raise ValueError('Point kind must be node')
            label = props.get('label', name)
            identifier(label)
            nodes[name] = Node(name, position(geometry['coordinates']), label)
            vertices += 1
        elif geometry['type'] == 'LineString':
            fields(props, {'kind', 'source', 'target'})
            if props['kind'] != 'edge':
                raise ValueError('LineString kind must be edge')
            source, target = identifier(props['source']), identifier(props['target'])
            if source == target:
                raise ValueError('self edges are not supported')
            coords = geometry['coordinates']
            if not isinstance(coords, list) or not 2 <= len(coords) <= MAX_VERTICES:
                raise ValueError('LineString needs bounded vertices')
            points = tuple(position(p) for p in coords)
            if any(abs(a[0] - b[0]) > 180 for a, b in zip(points, points[1:])):
                raise ValueError('antimeridian crossing requires preprocessing')
            length = sum(distance(a, b) for a, b in zip(points, points[1:]))
            pending.append(Edge(name, source, target, points, length))
            vertices += len(points)
        else:
            raise ValueError('only Point and LineString geometries supported')
        if vertices > MAX_VERTICES:
            raise ValueError('total vertex limit exceeded')
    if not nodes or len(nodes) > MAX_NODES or len(pending) > MAX_EDGES:
        raise ValueError('node or edge count outside limits')
    longitudes = [node.coordinates[0] for node in nodes.values()]
    longitudes += [point[0] for edge in pending for point in edge.coordinates]
    if max(longitudes) - min(longitudes) > 180:
        raise ValueError('regional extent must not span more than 180 longitude degrees')
    for edge in pending:
        if edge.source not in nodes or edge.target not in nodes:
            raise ValueError('edge endpoint does not exist')
        if edge.coordinates[0] != nodes[edge.source].coordinates or edge.coordinates[-1] != nodes[edge.target].coordinates:
            raise ValueError('geometry endpoints must exactly match referenced nodes')
        edges[edge.id] = edge
    return Network(MappingProxyType(nodes), MappingProxyType(edges))


def unique_ids(values, limit):
    if not isinstance(values, list) or len(values) > limit:
        raise ValueError('bounded identifier array required')
    result = [identifier(value) for value in values]
    if len(set(result)) != len(result):
        raise ValueError('duplicate identifier')
    return sorted(result)


def parse_requirements(data, network):
    fields(data, {'schema_version', 'required_nodes', 'required_paths', 'disabled_nodes', 'disabled_edges'})
    if isinstance(data['schema_version'], bool) or not isinstance(data['schema_version'], int) or data['schema_version'] != 1:
        raise ValueError('requirements schema version 1 required')
    result = {'schema_version': 1}
    for key, limit in [('required_nodes', MAX_NODES), ('disabled_nodes', MAX_NODES), ('disabled_edges', MAX_EDGES)]:
        result[key] = unique_ids(data[key], limit)
    if set(result['disabled_nodes']) - set(network.nodes) or set(result['disabled_edges']) - set(network.edges):
        raise ValueError('cannot disable an unknown node or edge')
    paths = data['required_paths']
    if not isinstance(paths, list) or len(paths) > 100:
        raise ValueError('at most 100 required paths permitted')
    seen, normalized = set(), []
    for path in paths:
        fields(path, {'id', 'source', 'target', 'max_distance_m', 'require_redundancy'})
        name = identifier(path['id'])
        if name in seen:
            raise ValueError('duplicate path requirement')
        seen.add(name)
        source, target = identifier(path['source']), identifier(path['target'])
        if source == target:
            raise ValueError('path endpoints must differ')
        maximum = finite(path['max_distance_m'])
        if not isinstance(path['require_redundancy'], bool):
            raise ValueError('require_redundancy must be a boolean')
        normalized.append({'id': name, 'source': source, 'target': target,
                           'max_distance_m': maximum, 'require_redundancy': path['require_redundancy']})
    if not result['required_nodes'] and not normalized:
        raise ValueError('at least one explicit requirement is required')
    result['required_paths'] = sorted(normalized, key=lambda p: p['id'])
    return result
