"""Bounded, dependency-free WGS84 GeoPackage feature interchange.

Reads/writes the engine feature contract, not arbitrary GIS attribute schemas.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import struct
from .analysis import canonical
from .engine2 import parse_v2
from .io import decode
from .polygons import validate_coordinates

MAX_GPKG_BYTES = 16 * 1024 * 1024
TYPES = {'Point': 1, 'LineString': 2, 'Polygon': 3, 'MultiPolygon': 6}


def validate(data):
    if len(canonical(data)) > 4 * 1024 * 1024:
        raise ValueError('captured GeoJSON exceeds input limit')
    network, _, polygons = parse_v2(data)
    count, xs = validate_coordinates(polygons)
    count += len(network.nodes) + sum(len(e.coordinates) for e in network.edges.values())
    xs += [n.coordinates[0] for n in network.nodes.values()]
    xs += [p[0] for e in network.edges.values() for p in e.coordinates]
    if count > 20000 or max(xs) - min(xs) > 180:
        raise ValueError('combined geometry limits exceeded')


def wkb(geometry):
    kind, coords = geometry['type'], geometry['coordinates']
    header = struct.pack('<BI', 1, TYPES[kind])
    def points(values):
        return struct.pack('<I', len(values)) + b''.join(struct.pack('<dd', *p) for p in values)
    if kind == 'Point':
        return header + struct.pack('<dd', *coords)
    if kind == 'LineString':
        return header + points(coords)
    if kind == 'Polygon':
        return header + struct.pack('<I', len(coords)) + b''.join(points(r) for r in coords)
    return header + struct.pack('<I', len(coords)) + b''.join(wkb({'type': 'Polygon', 'coordinates': p}) for p in coords)


def geometry_from_blob(blob):
    if not isinstance(blob, bytes) or len(blob) < 8 or blob[:3] != b'GP\x00':
        raise ValueError('GeoPackage version 0 geometry required')
    flags = blob[3]
    envelope = (flags >> 1) & 7
    if flags & 0xf0 or envelope > 4:
        raise ValueError('empty, extended or reserved geometry flags unsupported')
    endian = '<' if flags & 1 else '>'
    if struct.unpack(endian + 'i', blob[4:8])[0] != 4326:
        raise ValueError('only EPSG:4326 geometries supported')
    offset = 8 + (0, 32, 48, 48, 64)[envelope]
    vertices = 0
    def read(fmt):
        nonlocal offset
        size = struct.calcsize(fmt)
        if offset + size > len(blob):
            raise ValueError('truncated geometry')
        value = struct.unpack_from(fmt, blob, offset)
        offset += size
        return value
    def parse(depth=0):
        nonlocal vertices
        if depth > 1:
            raise ValueError('geometry nesting outside contract')
        order = read('B')[0]
        if order not in (0, 1):
            raise ValueError('invalid WKB byte order')
        prefix = '<' if order else '>'
        kind = read(prefix + 'I')[0]
        def count():
            size = read(prefix + 'I')[0]
            if size > 20000:
                raise ValueError('geometry count outside limits')
            return size
        def point():
            nonlocal vertices
            vertices += 1
            if vertices > 20000:
                raise ValueError('geometry vertex limit exceeded')
            return list(read(prefix + 'dd'))
        if kind == 1:
            return {'type': 'Point', 'coordinates': point()}
        if kind == 2:
            return {'type': 'LineString', 'coordinates': [point() for _ in range(count())]}
        if kind == 3:
            return {'type': 'Polygon', 'coordinates': [[point() for _ in range(count())] for _ in range(count())]}
        if kind == 6 and depth == 0:
            parts = [parse(depth + 1) for _ in range(count())]
            if any(p['type'] != 'Polygon' for p in parts):
                raise ValueError('MultiPolygon children must be polygons')
            return {'type': 'MultiPolygon', 'coordinates': [p['coordinates'] for p in parts]}
        raise ValueError('only 2D point, line and polygon WKB supported')
    result = parse()
    if offset != len(blob):
        raise ValueError('unexpected geometry trailing bytes')
    return result


def write_geopackage(path, data):
    validate(data)
    path = Path(path)
    # Reserve destination exclusively; never overwrite an existing database.
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    connection = None
    try:
        connection = sqlite3.connect(path)
        connection.executescript('''
PRAGMA application_id=1196444487;
PRAGMA user_version=10300;
CREATE TABLE gpkg_spatial_ref_sys(srs_name TEXT NOT NULL,srs_id INTEGER PRIMARY KEY,organization TEXT NOT NULL,organization_coordsys_id INTEGER NOT NULL,definition TEXT NOT NULL,description TEXT);
CREATE TABLE gpkg_contents(table_name TEXT PRIMARY KEY,data_type TEXT NOT NULL,identifier TEXT UNIQUE,description TEXT DEFAULT '',last_change DATETIME NOT NULL,min_x DOUBLE,min_y DOUBLE,max_x DOUBLE,max_y DOUBLE,srs_id INTEGER REFERENCES gpkg_spatial_ref_sys(srs_id));
CREATE TABLE gpkg_geometry_columns(table_name TEXT NOT NULL,column_name TEXT NOT NULL,geometry_type_name TEXT NOT NULL,srs_id INTEGER NOT NULL,z TINYINT NOT NULL,m TINYINT NOT NULL,PRIMARY KEY(table_name,column_name),FOREIGN KEY(table_name) REFERENCES gpkg_contents(table_name),FOREIGN KEY(srs_id) REFERENCES gpkg_spatial_ref_sys(srs_id));
CREATE TABLE topology_features(fid INTEGER PRIMARY KEY,feature_id TEXT NOT NULL UNIQUE,properties TEXT NOT NULL,geom BLOB NOT NULL);
''')
        wgs84 = 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433],AUTHORITY["EPSG","4326"]]'
        connection.executemany('INSERT INTO gpkg_spatial_ref_sys VALUES(?,?,?,?,?,?)', [
            ('Undefined Cartesian', -1, 'NONE', -1, 'undefined', None),
            ('Undefined geographic', 0, 'NONE', 0, 'undefined', None),
            ('WGS 84', 4326, 'EPSG', 4326, wgs84, None)])
        connection.execute('INSERT INTO gpkg_contents(table_name,data_type,identifier,last_change,srs_id) VALUES(?,?,?,?,?)',
                           ('topology_features', 'features', 'topology_features', datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'), 4326))
        connection.execute('INSERT INTO gpkg_geometry_columns VALUES(?,?,?,?,?,?)', ('topology_features', 'geom', 'GEOMETRY', 4326, 0, 0))
        for i, feature in enumerate(data['features']):
            blob = b'GP\x00\x01' + struct.pack('<i', 4326) + wkb(feature['geometry'])
            connection.execute('INSERT INTO topology_features VALUES(?,?,?,?)',
                               (i + 1, feature['id'], canonical(feature['properties']).decode(), blob))
        connection.commit()
        connection.close()
        connection = None
        if path.stat().st_size > MAX_GPKG_BYTES:
            raise ValueError('GeoPackage exceeds size bound')
    except Exception:
        if connection is not None:
            connection.close()
        path.unlink(missing_ok=True)
        raise


def read_geopackage(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_GPKG_BYTES:
        raise ValueError('bounded regular GeoPackage required')
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('PRAGMA trusted_schema=OFF')
        if connection.execute('PRAGMA application_id').fetchone()[0] != 1196444487:
            raise ValueError('GeoPackage application ID required')
        metadata = connection.execute('SELECT geometry_type_name,srs_id,z,m FROM gpkg_geometry_columns WHERE table_name=? AND column_name=?', ('topology_features', 'geom')).fetchall()
        if metadata != [('GEOMETRY', 4326, 0, 0)]:
            raise ValueError('engine WGS84 topology_features layer required')
        rows = connection.execute('SELECT feature_id,properties,geom FROM topology_features ORDER BY fid LIMIT 1401').fetchall()
        if len(rows) > 1400:
            raise ValueError('feature count outside limits')
        if any(not isinstance(props, str) for _, props, _ in rows):
            raise ValueError('GeoPackage properties must contain JSON text')
        data = {'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'id': name, 'properties': decode(props.encode()), 'geometry': geometry_from_blob(blob)}
            for name, props, blob in rows]}
        if len(canonical(data)) > 4 * 1024 * 1024:
            raise ValueError('captured GeoJSON exceeds bundle limits')
        validate(data)
        return data
    except sqlite3.Error as error:
        raise ValueError('invalid or unsupported GeoPackage') from error
    finally:
        connection.close()
