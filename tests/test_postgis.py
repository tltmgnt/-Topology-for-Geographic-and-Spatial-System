"""PostGIS SQL composition checks and opt-in live synthetic round trip."""
import importlib.util
import json
import os
import unittest
from unittest.mock import MagicMock
from spatial_topology.postgis import read_postgis
from test_engine2 import fixture


@unittest.skipUnless(importlib.util.find_spec('psycopg'), 'optional PostGIS extra absent')
class PostGISTests(unittest.TestCase):
    def test_quoted_identifiers_and_snapshot(self):
        data, _ = fixture()
        rows = [(f['id'], f['properties'], json.dumps(f['geometry']), 4326, 2) for f in data['features']]
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.__iter__.return_value = iter(rows)
        self.assertEqual(read_postgis(connection, 'public', 'weird";DROP TABLE x;--'), data)
        query = cursor.execute.call_args.args[0].as_string()
        self.assertIn('"weird"";DROP TABLE x;--"', query)
        self.assertIn('ST_SRID', query)
        self.assertIn('LIMIT 1401', query)

    def test_wrong_srid_rejected(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.__iter__.return_value = iter([('A', {'kind':'node'}, '{"type":"Point","coordinates":[0,0]}', 3857, 2)])
        with self.assertRaises(ValueError):
            read_postgis(connection, 'public', 'features')

    @unittest.skipUnless(os.environ.get('SPATIAL_TOPOLOGY_TEST_DSN'), 'live PostGIS test DSN absent')
    def test_live_postgis(self):
        import psycopg
        data, _ = fixture()
        with psycopg.connect(os.environ['SPATIAL_TOPOLOGY_TEST_DSN']) as connection:
            # All synthetic fixtures are transaction-local and rolled back.
            connection.execute('CREATE TEMP TABLE topology_test(feature_id text, properties jsonb, geom geometry)')
            for feature in data['features']:
                connection.execute('INSERT INTO topology_test VALUES(%s,%s,ST_SetSRID(ST_GeomFromGeoJSON(%s),4326))',
                                   (feature['id'], json.dumps(feature['properties']), json.dumps(feature['geometry'])))
            captured = read_postgis(connection, 'pg_temp', 'topology_test')
            self.assertEqual({f['id']: f for f in captured['features']}, {f['id']: f for f in data['features']})
            connection.rollback()
