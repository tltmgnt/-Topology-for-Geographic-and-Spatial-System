"""V2 directed assurance, replay, geometry and standards regression tests."""
import copy
import importlib.util
import hashlib
import json
from pathlib import Path
import random
import sqlite3
import struct
import tempfile
import unittest
from spatial_topology.analysis import build_report, canonical
from spatial_topology.engine2 import parse_v2, policy_v2, graph_for, evaluate
from spatial_topology.geopackage import read_geopackage, write_geopackage, geometry_from_blob, wkb
from spatial_topology.io import create_bundle, verify_bundle, compare_bundles
from spatial_topology.verification import verify_algorithms


def fixture():
    coords = {'A': [0, 0], 'B': [1, 0], 'C': [1, 1], 'D': [0, 1]}
    features = [{'type': 'Feature', 'id': n, 'properties': {'kind': 'node'},
                 'geometry': {'type': 'Point', 'coordinates': p}} for n, p in coords.items()]
    for name, source, target, cost in [('AB', 'A', 'B', 1), ('BC', 'B', 'C', 1), ('AC', 'A', 'C', 9), ('CD', 'C', 'D', 1)]:
        features.append({'type': 'Feature', 'id': name,
                         'properties': {'kind': 'edge', 'source': source, 'target': target, 'directed': True, 'cost': cost},
                         'geometry': {'type': 'LineString', 'coordinates': [coords[source], coords[target]]}})
    data = {'type': 'FeatureCollection', 'features': features}
    policy = {'schema_version': 2, 'required_nodes': ['A', 'C'], 'required_paths': [
        {'id': 'access', 'source': 'A', 'target': 'C', 'max_cost': 3,
         'max_distance_m': 1e9, 'require_redundancy': True}], 'disabled_nodes': [], 'disabled_edges': []}
    return data, policy


def polygon(name, ring, holes=()):
    return {'type': 'Feature', 'id': name, 'properties': {'kind': 'polygon'},
            'geometry': {'type': 'Polygon', 'coordinates': [ring, *holes]}}


class EngineTests(unittest.TestCase):
    def test_preserved_v1_bundle_bytes(self):
        from spatial_topology.io import bundle_contents, read_json
        root = Path(__file__).resolve().parents[1]
        # Confirmed against the original main checkout before the v2 upgrade.
        expected = {
            'requirements': '8e3d2eabc6b0f0ea77a102815a234a2d7fc8fc28edbd1e664a51a8726e9f7f3c',
            'gaps': '572b97a8c6625362e99fdbca93dc756b603ad05b775e708aef9f906131cb67c1',
            'outage': '4be81115a87ee48c6e97930936ccbfc24ce2e4a47b47b60b73550f0c02066557'}
        for name, digest in expected.items():
            files, _ = bundle_contents(read_json(root/'examples/network.geojson'),
                                       read_json(root/f'examples/{name}.json'))
            hashes = {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}
            self.assertEqual(hashlib.sha256(canonical(hashes)).hexdigest(), digest)

    def test_directed_cost_and_directional_redundancy(self):
        data, policy = fixture()
        report = build_report(data, policy)
        self.assertEqual(report['path_checks'][0]['route']['edges'], ['AB', 'BC'])
        self.assertEqual(report['path_checks'][0]['route']['cost'], 2)
        self.assertEqual(report['path_checks'][0]['separating_edges'], [])
        self.assertEqual(report['resilience']['single_edge_survival_ratio'], 1)
        self.assertEqual(report['resilience']['single_node_survival_ratio'], .5)
        self.assertEqual(report['strong_components'], [['A'], ['B'], ['C'], ['D']])
        policy['required_paths'][0].update(source='C', target='A')
        self.assertEqual(build_report(data, policy)['path_checks'][0]['reasons'], ['NO_PATH'])

    def test_weak_bridges_do_not_prove_directed_redundancy(self):
        data, policy = fixture()
        # A->C and B->C form a weak cycle, but A->B has only the direct edge.
        policy['required_paths'][0].update(target='B')
        report = build_report(data, policy)
        self.assertNotIn('AB', report['bridges'])
        self.assertEqual(report['path_checks'][0]['separating_edges'], ['AB'])
        self.assertIn('SINGLE_EDGE_FAILURE_EXPOSURE', report['path_checks'][0]['reasons'])

    def test_parallel_edges_and_zero_cost_cycle(self):
        data, policy = fixture()
        parallel = copy.deepcopy(data['features'][4])
        parallel['id'] = 'AB2'
        parallel['properties']['cost'] = 0
        data['features'].append(parallel)
        for f in data['features'][4:]:
            f['properties']['directed'] = False
        report = build_report(data, policy)
        self.assertEqual(report['path_checks'][0]['route']['cost'], 1)
        self.assertEqual(report['path_checks'][0]['separating_edges'], [])
        self.assertEqual(report['strong_components'], [['A', 'B', 'C', 'D']])

    def test_simultaneous_failures_are_additive_and_do_not_mutate(self):
        data, policy = fixture()
        policy['disabled_edges'] = ['CD']
        policy['scenarios'] = [{'id': 'combined', 'disabled_nodes': ['B'], 'disabled_edges': ['AC']}]
        original = copy.deepcopy((data, policy))
        report = build_report(data, policy)
        scenario = report['scenarios'][0]
        self.assertEqual(scenario['inactive_edges'], ['AB', 'AC', 'BC', 'CD'])
        self.assertEqual(scenario['path_checks'][0]['reasons'], ['NO_PATH'])
        self.assertEqual(report['status'], 'REQUIREMENTS_SATISFIED')
        self.assertEqual(report['study_status'], 'GAPS_FOUND')
        self.assertEqual((data, policy), original)

    def test_cost_limit_uses_unrounded_cost_and_distance_is_separate(self):
        data, policy = fixture()
        policy['required_paths'][0]['max_cost'] = 2 - 1e-10
        report = build_report(data, policy)
        self.assertEqual(report['path_checks'][0]['reasons'], ['COST_LIMIT_EXCEEDED'])
        self.assertGreater(report['path_checks'][0]['route']['distance_m'], 200000)

    def test_missing_endpoint_and_null_score(self):
        data, policy = fixture()
        policy['required_paths'][0]['target'] = 'missing'
        report = build_report(data, policy)
        self.assertEqual(report['path_checks'][0]['reasons'], ['MISSING_ENDPOINT'])
        self.assertIsNone(report['resilience']['single_edge_survival_ratio'])

    def test_validation(self):
        data, policy = fixture()
        for value in [True, -1, float('nan'), '2']:
            bad = copy.deepcopy(data)
            bad['features'][4]['properties']['cost'] = value
            with self.assertRaises(ValueError):
                build_report(bad, policy)
        bad = copy.deepcopy(data)
        bad['features'][4]['properties']['directed'] = 1
        with self.assertRaises(ValueError):
            build_report(bad, policy)
        for scenario in [{'id': 'x', 'disabled_nodes': ['unknown'], 'disabled_edges': []},
                         {'id': 'x', 'disabled_nodes': [], 'disabled_edges': ['AB', 'AB']}]:
            with self.assertRaises(ValueError):
                build_report(data, {**policy, 'scenarios': [scenario]})
        with self.assertRaises(ValueError):
            build_report(data, {**policy, 'provenance': {'captured_at': '2026-11-08'}})

    def test_replay_and_tamper(self):
        data, policy = fixture()
        data['features'][0]['properties']['label'] = '</script><script>alert(1)</script>'
        policy['provenance'] = {'source': 'synthetic', 'dataset_version': '1', 'captured_at': '2026-11-08T00:00:00Z'}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bundle'
            original = create_bundle(path, data, policy)
            self.assertEqual(verify_bundle(path), original)
            html = (path / 'review.html').read_text()
            self.assertEqual(html.count('<script>'), 1)
            self.assertIn('sha256-', html)
            self.assertIn('&lt;/script&gt;', html)
            (path / 'report.json').write_text('{}')
            with self.assertRaises(ValueError):
                verify_bundle(path)

    def test_independent_verifier_rejects_corruption(self):
        data, policy = fixture()
        network, options, _ = parse_v2(data)
        normalized = policy_v2(policy, network)
        report = evaluate(network, options, normalized)
        report['path_checks'][0]['route']['cost'] = 4
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            verify_algorithms(network, options, normalized, report)

    def test_random_graphs_against_exhaustive_simple_paths(self):
        rng = random.Random(1729)
        for _ in range(30):
            data, policy = fixture()
            data['features'] = data['features'][:4]
            coords = {f['id']: f['geometry']['coordinates'] for f in data['features']}
            for a in coords:
                for b in coords:
                    if a != b and rng.random() < .4:
                        data['features'].append({'type': 'Feature', 'id': a+b,
                            'properties': {'kind': 'edge', 'source': a, 'target': b, 'directed': True, 'cost': rng.randrange(5)},
                            'geometry': {'type': 'LineString', 'coordinates': [coords[a], coords[b]]}})
            report = build_report(data, policy)
            routes = []
            def walk(node, seen, cost):
                if node == 'C':
                    routes.append(cost)
                    return
                for f in data['features'][4:]:
                    p = f['properties']
                    if p['source'] == node and p['target'] not in seen:
                        walk(p['target'], seen | {p['target']}, cost + p['cost'])
            walk('A', {'A'}, 0)
            route = report['path_checks'][0]['route']
            self.assertEqual(None if route is None else route['cost'], min(routes) if routes else None)


class GeoPackageTests(unittest.TestCase):
    def test_roundtrip_all_supported_geometries(self):
        data, policy = fixture()
        poly = polygon('zone', [[0, 0], [2, 0], [2, 2], [0, 0]])
        multi = copy.deepcopy(poly)
        multi['id'] = 'multi'
        multi['geometry'] = {'type': 'MultiPolygon', 'coordinates': [poly['geometry']['coordinates']]}
        data['features'] += [poly, multi]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'network.gpkg'
            write_geopackage(path, data)
            self.assertEqual(read_geopackage(path), data)
            with self.assertRaises(FileExistsError):
                write_geopackage(path, data)
            conn = sqlite3.connect(path)
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            conn.close()

    def test_rejects_truncation_trailing_bytes_and_srid(self):
        geometry = {'type': 'Point', 'coordinates': [0, 0]}
        blob = b'GP\0\1' + struct.pack('<i', 4326) + wkb(geometry)
        for bad in [blob[:-1], blob+b'X', blob[:4]+struct.pack('<i',3857)+blob[8:]]:
            with self.assertRaises(ValueError):
                geometry_from_blob(bad)
        big = b'GP\0\0' + struct.pack('>i', 4326) + struct.pack('>BI2d',0,1,2,3)
        self.assertEqual(geometry_from_blob(big)['coordinates'], [2,3])


@unittest.skipUnless(importlib.util.find_spec('shapely'), 'optional geometry extra absent')
class PolygonTests(unittest.TestCase):
    def test_touch_shared_boundary_containment_overlap_and_hole(self):
        data, policy = fixture()
        data['features'] += [
            polygon('P', [[0,0],[2,0],[2,2],[0,2],[0,0]]),
            polygon('Q', [[2,0],[3,0],[3,2],[2,2],[2,0]]),
            polygon('R', [[.5,.5],[1.5,.5],[1.5,1.5],[.5,1.5],[.5,.5]]),
            polygon('S', [[1,1],[3,1],[3,3],[1,3],[1,1]])]
        report = build_report(data, policy)
        pairs = {(r['source'], r['target']): r['relations'] for r in report['polygon_relationships']}
        self.assertEqual(pairs['P','Q'], ['shared_boundary','touches'])
        self.assertEqual(pairs['P','R'], ['contains'])
        self.assertIn('overlaps', pairs['P','S'])
        self.assertEqual(pairs['P','A'], ['boundary_node'])
        data['features'] = data['features'][:8] + [polygon('H', [[-1,-1],[2,-1],[2,2],[-1,2],[-1,-1]],
            [[[.5,.5],[1.5,.5],[1.5,1.5],[.5,1.5],[.5,.5]]])]
        pairs = {(r['source'], r['target']): r['relations'] for r in build_report(data,policy)['polygon_relationships']}
        self.assertNotIn(('H','C'), pairs)

    def test_rejects_self_intersection_and_unclosed_rings(self):
        data, policy = fixture()
        for ring in [[[0,0],[2,2],[0,2],[2,0],[0,0]], [[0,0],[2,0],[2,2],[0,2]]]:
            bad = copy.deepcopy(data)
            bad['features'].append(polygon('invalid', ring))
            with self.assertRaises(ValueError):
                build_report(bad, policy)
