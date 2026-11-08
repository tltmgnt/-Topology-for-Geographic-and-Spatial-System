"""Known-graph, geometry, input integrity and end-to-end acceptance tests."""
import contextlib
import copy
import io
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import unittest
from spatial_topology.analysis import adjacency, build_report, canonical, shortest_path
from spatial_topology.io import MAX_BYTES, compare_bundles, create_bundle, decode, read_json, verify_bundle
from spatial_topology.model import distance, parse_network, parse_requirements
from spatial_topology.render import render_html
from spatial_topology.__main__ import main

ROOT = Path(__file__).resolve().parents[1]


def sample():
    return read_json(ROOT / 'examples/network.geojson'), read_json(ROOT / 'examples/requirements.json')


def node(name, point):
    return {'type': 'Feature', 'id': name, 'properties': {'kind': 'node'},
            'geometry': {'type': 'Point', 'coordinates': point}}


def edge(name, source, target, a, b):
    return {'type': 'Feature', 'id': name, 'properties': {'kind': 'edge', 'source': source, 'target': target},
            'geometry': {'type': 'LineString', 'coordinates': [a, b]}}


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.data, self.policy = sample()

    def test_known_components_bridges_and_articulation(self):
        report = build_report(self.data, self.policy)
        self.assertEqual(report['components'], [['A', 'B', 'C', 'D'], ['E']])
        self.assertEqual(report['isolated_nodes'], ['E'])
        self.assertEqual(report['bridges'], ['CD'])
        self.assertEqual(report['articulation_nodes'], ['C'])
        self.assertEqual(report['status'], 'REQUIREMENTS_SATISFIED')
        self.assertFalse(report['execution_authorized'])

    def test_shortest_path_and_edge_redundancy(self):
        report = build_report(self.data, self.policy)
        checks = {item['requirement']['id']: item for item in report['path_checks']}
        self.assertEqual(checks['access-D']['route']['nodes'], ['A', 'C', 'D'])
        self.assertEqual(checks['access-D']['separating_bridges'], ['CD'])
        self.assertEqual(checks['resilient-C']['separating_bridges'], [])
        self.assertTrue(all(item['status'] == 'PASS' for item in checks.values()))

    def test_explicit_missingness_and_disconnected_routes(self):
        report = build_report(self.data, read_json(ROOT / 'examples/gaps.json'))
        self.assertEqual(report['status'], 'GAPS_FOUND')
        self.assertAlmostEqual(report['required_node_coverage'], 2 / 3)
        self.assertEqual({g['code'] for g in report['gaps']},
                         {'MISSING_REQUIRED_NODE', 'SINGLE_EDGE_FAILURE_EXPOSURE', 'NO_PATH', 'MISSING_ENDPOINT'})
        self.assertEqual(len(report['gaps']), 4)

    def test_outage_changes_topology_without_mutating_input(self):
        original = copy.deepcopy(self.data)
        report = build_report(self.data, read_json(ROOT / 'examples/outage.json'))
        self.assertEqual(report['inactive_edges'], ['BC', 'CD'])
        self.assertIn({'code': 'UNAVAILABLE_REQUIRED_NODE', 'subject': 'D'}, report['gaps'])
        self.assertIn({'code': 'UNAVAILABLE_ENDPOINT', 'subject': 'access-D'}, report['gaps'])
        self.assertEqual(original, self.data)

    def test_route_distance_limit_uses_unrounded_value(self):
        net = parse_network(self.data)
        graph = adjacency(net, self.policy)
        length = shortest_path(graph, 'A', 'C')['distance_m']
        req = {'id': 'boundary', 'source': 'A', 'target': 'C',
               'max_distance_m': length - 1e-9, 'require_redundancy': False}
        self.policy['required_paths'] = [req]
        self.assertIn('DISTANCE_LIMIT_EXCEEDED', build_report(self.data, self.policy)['path_checks'][0]['reasons'])
        req['max_distance_m'] = length
        self.assertEqual(build_report(self.data, self.policy)['path_checks'][0]['status'], 'PASS')

    def test_parallel_edges_are_not_bridges(self):
        self.data['features'].append(edge('parallel-CD', 'C', 'D', [-122, 37.01], [-122, 37.02]))
        report = build_report(self.data, self.policy)
        self.assertEqual(report['bridges'], [])
        self.assertEqual(report['articulation_nodes'], ['C'])

    def test_inactive_parallel_edge_does_not_supply_redundancy(self):
        self.data['features'].append(edge('parallel-CD', 'C', 'D', [-122, 37.01], [-122, 37.02]))
        self.policy['disabled_edges'] = ['parallel-CD']
        self.assertEqual(build_report(self.data, self.policy)['bridges'], ['CD'])

    def test_geometry_crossing_is_not_a_junction(self):
        data = {'type': 'FeatureCollection', 'features': [node('a', [0, 0]), node('b', [1, 1]),
                node('c', [0, 1]), node('d', [1, 0]), edge('ab', 'a', 'b', [0, 0], [1, 1]),
                edge('cd', 'c', 'd', [0, 1], [1, 0])]}
        policy = {'schema_version': 1, 'required_nodes': ['a'], 'required_paths': [],
                  'disabled_nodes': [], 'disabled_edges': []}
        self.assertEqual(build_report(data, policy)['components'], [['a', 'b'], ['c', 'd']])

    def test_all_disabled_and_single_node(self):
        self.policy['disabled_nodes'] = ['A', 'B', 'C', 'D', 'E']
        report = build_report(self.data, self.policy)
        self.assertEqual(report['components'], [])
        self.assertEqual(report['required_node_coverage'], 0)
        self.assertEqual(report['bridges'], [])
        data = {'type': 'FeatureCollection', 'features': [node('a', [0, 0])]}
        policy = {'schema_version': 1, 'required_nodes': ['a'], 'required_paths': [],
                  'disabled_nodes': [], 'disabled_edges': []}
        report = build_report(data, policy)
        self.assertEqual(report['articulation_nodes'], [])
        self.assertEqual(report['status'], 'REQUIREMENTS_SATISFIED')

    def test_zero_length_distinct_nodes_terminate(self):
        data = {'type': 'FeatureCollection', 'features': [node('a', [0, 0]), node('b', [0, 0]),
                edge('ab', 'a', 'b', [0, 0], [0, 0])]}
        policy = {'schema_version': 1, 'required_nodes': [], 'required_paths': [
            {'id': 'zero', 'source': 'a', 'target': 'b', 'max_distance_m': 0, 'require_redundancy': False}],
            'disabled_nodes': [], 'disabled_edges': []}
        report = build_report(data, policy)
        self.assertEqual(report['path_checks'][0]['route']['distance_m'], 0)
        self.assertEqual(report['status'], 'REQUIREMENTS_SATISFIED')

    def test_deterministic_feature_order(self):
        report = build_report(self.data, self.policy)
        self.data['features'].reverse()
        reordered = build_report(self.data, self.policy)
        # Source fingerprint intentionally records the changed input array order.
        report.pop('input_sha256')
        reordered.pop('input_sha256')
        self.assertEqual(report, reordered)

    def test_great_circle_reference_cases(self):
        self.assertEqual(distance((0, 0), (0, 0)), 0)
        self.assertAlmostEqual(distance((0, 0), (1, 0)), 111195.0802335, places=5)
        self.assertAlmostEqual(distance((0, 0), (180, 0)), 20015114.4420359, places=5)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.data, self.policy = sample()

    def test_invalid_coordinate_values(self):
        for coordinates in ([181, 0], [0, 91], [True, 0], [float('nan'), 0], [0, 0, 0],
                            [float('inf'), 0], ['0', 0], [10**500, 0]):
            with self.subTest(coordinates=coordinates):
                data = copy.deepcopy(self.data)
                data['features'][0]['geometry']['coordinates'] = coordinates
                with self.assertRaises(ValueError):
                    parse_network(data)

    def test_invalid_geometry_topology_and_duplicate_ids(self):
        mutations = [lambda d: d['features'].append(copy.deepcopy(d['features'][0])),
                     lambda d: d['features'][-1]['properties'].update(source='missing'),
                     lambda d: d['features'][-1]['properties'].update(source='D'),
                     lambda d: d['features'][-1]['geometry']['coordinates'][0].__setitem__(0, -123),
                     lambda d: d['features'][0]['geometry'].update(type='Polygon'),
                     lambda d: d.update(crs='EPSG:3857')]
        for mutate in mutations:
            data = copy.deepcopy(self.data)
            mutate(data)
            with self.assertRaises(ValueError):
                parse_network(data)

    def test_antimeridian_and_extent_rejected(self):
        data = {'type': 'FeatureCollection', 'features': [node('a', [179, 0]), node('b', [-179, 0]),
                edge('ab', 'a', 'b', [179, 0], [-179, 0])]}
        with self.assertRaises(ValueError):
            parse_network(data)

    def test_strict_requirements(self):
        network = parse_network(self.data)
        changes = [{'schema_version': True}, {'schema_version': 2}, {'disabled_nodes': ['missing']},
                   {'disabled_edges': ['missing']}, {'required_nodes': ['A', 'A']},
                   {'unexpected': True}, {'required_nodes': [], 'required_paths': []}]
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    parse_requirements({**self.policy, **change}, network)
        for field, value in [('max_distance_m', -1), ('max_distance_m', True),
                             ('require_redundancy', 1), ('target', 'A')]:
            policy = copy.deepcopy(self.policy)
            policy['required_paths'][0][field] = value
            with self.assertRaises(ValueError):
                parse_requirements(policy, network)

    def test_duplicate_and_nonfinite_json_rejected(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":{"x":1,"x":1}}', b'{"a":NaN}', b'{"a":1e999}', b'\xff',
                    ('[' * 70 + '0' + ']' * 70).encode()):
            with self.subTest(raw=raw[:30]):
                with self.assertRaises(ValueError):
                    decode(raw)

    def test_file_size_and_regular_file_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'oversize'
            with path.open('wb') as stream:
                stream.truncate(MAX_BYTES + 1)
            with self.assertRaises(ValueError):
                read_json(path)
            with self.assertRaises((ValueError, OSError)):
                read_json(Path(directory))

    def test_limits_fail_before_graph_analysis(self):
        self.data['features'] += [node('extra-' + str(n), [0, 0]) for n in range(301)]
        with self.assertRaises(ValueError):
            parse_network(self.data)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.data, self.policy = sample()
        self.temp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'run'

    def test_full_bundle_recomputes_and_preserves_status(self):
        expected = create_bundle(self.path, self.data, self.policy)
        self.assertEqual(expected, verify_bundle(self.path))
        self.assertTrue((self.path / 'review.html').is_file())
        self.assertEqual(len(list(self.path.iterdir())), 5)

    def test_gap_bundle_is_consistent_without_passing_requirements(self):
        report = create_bundle(self.path, self.data, read_json(ROOT / 'examples/gaps.json'))
        self.assertEqual(report['status'], 'GAPS_FOUND')
        self.assertEqual(verify_bundle(self.path)['status'], 'GAPS_FOUND')

    def test_existing_directory_is_preserved(self):
        self.path.mkdir()
        sentinel = self.path / 'keep'
        sentinel.write_text('retain')
        with self.assertRaises(FileExistsError):
            create_bundle(self.path, self.data, self.policy)
        self.assertEqual(sentinel.read_text(), 'retain')

    def test_each_file_tamper_is_detected(self):
        for name in ('report.json', 'review.html', 'manifest.json', 'requirements.json', 'input.geojson'):
            with self.subTest(name=name):
                path = self.path / name
                if not self.path.exists():
                    create_bundle(self.path, self.data, self.policy)
                original = path.read_bytes()
                path.write_bytes(original + b' ')
                with self.assertRaises(ValueError):
                    verify_bundle(self.path)
                path.write_bytes(original)

    def test_rehashed_forged_report_does_not_verify(self):
        create_bundle(self.path, self.data, self.policy)
        report = read_json(self.path / 'report.json')
        report['bridges'] = []
        raw = canonical(report)
        (self.path / 'report.json').write_bytes(raw)
        manifest = read_json(self.path / 'manifest.json')
        manifest['files']['report.json'] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
        (self.path / 'manifest.json').write_bytes(canonical(manifest))
        with self.assertRaises(ValueError):
            verify_bundle(self.path)

    def test_extra_file_and_symlink_rejected(self):
        create_bundle(self.path, self.data, self.policy)
        extra = self.path / 'extra'
        extra.write_text('unexpected')
        with self.assertRaises(ValueError):
            verify_bundle(self.path)
        extra.unlink()
        target = Path(self.temp.name) / 'report'
        target.write_bytes((self.path / 'report.json').read_bytes())
        (self.path / 'report.json').unlink()
        try:
            (self.path / 'report.json').symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):
            verify_bundle(self.path)

    def test_html_escapes_untrusted_labels(self):
        self.data['features'][0]['properties']['label'] = '<script>alert(1)</script>'
        report = build_report(self.data, self.policy)
        html = render_html(self.data, report)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('src="http', html)

    def test_schematic_svg_is_well_formed(self):
        report = build_report(self.data, self.policy)
        html = render_html(self.data, report)
        start, end = html.index('<svg'), html.index('</svg>') + len('</svg>')
        svg = ET.fromstring(html[start:end])
        self.assertEqual(len(svg.findall('circle')), 5)
        self.assertEqual(len(svg.findall('polyline')), 4)
        self.assertIn('class="map"', html)

    def test_cli_exit_codes_and_offline_replay(self):
        for filename, expected in [('requirements.json', 0), ('gaps.json', 1)]:
            destination = Path(self.temp.name) / filename
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['analyze', str(ROOT / 'examples/network.geojson'), '--requirements',
                                       str(ROOT / 'examples' / filename), '--output', str(destination)]), expected)
                self.assertEqual(main(['verify', str(destination)]), 0)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['verify', str(Path(self.temp.name) / 'absent')]), 2)

    def test_verified_outage_comparison(self):
        create_bundle(self.path, self.data, self.policy)
        other = Path(self.temp.name) / 'outage'
        create_bundle(other, self.data, read_json(ROOT / 'examples/outage.json'))
        result = compare_bundles(self.path, other)
        self.assertFalse(result['acceptance_criteria_changed'])
        self.assertTrue(result['new_gaps'])
        self.assertEqual(result['baseline_status'], 'REQUIREMENTS_SATISFIED')
        self.assertEqual(result['scenario_status'], 'GAPS_FOUND')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['compare', str(self.path), str(other)]), 0)

    def test_comparison_flags_changed_criteria_and_rejects_other_network(self):
        create_bundle(self.path, self.data, self.policy)
        other = Path(self.temp.name) / 'gaps'
        create_bundle(other, self.data, read_json(ROOT / 'examples/gaps.json'))
        self.assertTrue(compare_bundles(self.path, other)['acceptance_criteria_changed'])
        self.data['features'][0]['properties']['label'] = 'changed source'
        third = Path(self.temp.name) / 'different'
        create_bundle(third, self.data, self.policy)
        with self.assertRaises(ValueError):
            compare_bundles(self.path, third)

    def test_module_entrypoint(self):
        result = subprocess.run([sys.executable, '-m', 'spatial_topology', 'analyze',
                    str(ROOT / 'examples/network.geojson'), '--requirements',
                    str(ROOT / 'examples/requirements.json'), '--output', str(self.path)],
                    capture_output=True, text=True, cwd=ROOT, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'REQUIREMENTS_SATISFIED')


if __name__ == '__main__':
    unittest.main()
