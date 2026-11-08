"""Optional GEOS-backed planar polygon topology; never imported for graph-only studies."""
from .model import position


def validate_coordinates(features):
    count, xs = 0, []
    for feature in features:
        geometry = feature['geometry']
        parts = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
        if not isinstance(parts, list) or not parts:
            raise ValueError('nonempty polygon coordinates required')
        for polygon in parts:
            if not isinstance(polygon, list) or not polygon:
                raise ValueError('polygon rings required')
            for ring in polygon:
                if not isinstance(ring, list) or len(ring) < 4:
                    raise ValueError('closed polygon ring with at least four positions required')
                points = [position(p) for p in ring]
                if points[0] != points[-1]:
                    raise ValueError('polygon ring must be closed')
                if any(abs(a[0] - b[0]) > 180 for a, b in zip(points, points[1:])):
                    raise ValueError('antimeridian polygon requires preprocessing')
                count += len(points)
                xs.extend(p[0] for p in points)
                if count > 20000:
                    raise ValueError('polygon vertex limit exceeded')
    if xs and max(xs) - min(xs) > 180:
        raise ValueError('polygon extent exceeds regional limits')
    return count, xs


def relationships_for(features, network):
    _, xs = validate_coordinates(features)
    xs.extend(p[0] for e in network.edges.values() for p in e.coordinates)
    xs.extend(n.coordinates[0] for n in network.nodes.values())
    if max(xs) - min(xs) > 180:
        raise ValueError('combined regional extent exceeds 180 degrees')
    try:
        from shapely.geometry import shape, Point, LineString
    except ImportError as error:
        raise ValueError('polygon analysis requires the optional spatial-topology[geometry] extra') from error
    shapes = []
    for feature in sorted(features, key=lambda f: f['id']):
        geometry = shape(feature['geometry'])
        if geometry.is_empty or not geometry.is_valid or geometry.area <= 0:
            raise ValueError('polygon must be valid, nonempty and have positive planar area')
        shapes.append((feature['id'], geometry))
    result = []
    for i, (name, polygon) in enumerate(shapes):
        for other, candidate in shapes[i + 1:]:
            predicates = {
                'equals': polygon.equals(candidate), 'touches': polygon.touches(candidate),
                'overlaps': polygon.overlaps(candidate), 'disjoint': polygon.disjoint(candidate),
                'contains': polygon.contains(candidate), 'within': polygon.within(candidate),
                'shared_boundary': polygon.boundary.intersection(candidate.boundary).length > 0,
            }
            result.append({'source': name, 'target': other, 'relations': sorted(k for k, v in predicates.items() if v)})
        for node in sorted(network.nodes.values(), key=lambda n: n.id):
            point = Point(node.coordinates)
            if polygon.covers(point):
                result.append({'source': name, 'target': node.id,
                               'relations': ['contains_node' if polygon.contains(point) else 'boundary_node']})
        for edge in sorted(network.edges.values(), key=lambda e: e.id):
            line = LineString(edge.coordinates)
            if polygon.intersects(line):
                result.append({'source': name, 'target': edge.id,
                               'relations': ['covers_edge' if polygon.covers(line) else 'intersects_edge']})
    return result
