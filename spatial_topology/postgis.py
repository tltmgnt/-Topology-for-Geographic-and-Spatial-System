"""Optional read-only PostGIS snapshot adapter. No database dependency in core.

A source relation must expose feature_id, properties (JSON), geom (SRID 4326).
Connections/credentials are supplied by the caller and never stored in bundles.
"""
from .analysis import canonical
from .geopackage import validate
from .io import decode


def read_postgis(connection, schema, table):
    try:
        from psycopg import sql
    except ImportError as error:
        raise ValueError('PostGIS adapter requires spatial-topology[postgis]') from error
    for value in (schema, table):
        if not isinstance(value, str) or not value or len(value) > 63 or '\x00' in value:
            raise ValueError('bounded SQL identifier required')
    query = sql.SQL('SELECT feature_id, properties, ST_AsGeoJSON(geom, 15, 0), ST_SRID(geom), ST_NDims(geom) FROM {}.{} ORDER BY feature_id LIMIT 1401').format(sql.Identifier(schema), sql.Identifier(table))
    # Only SELECT is issued. Caller owns transaction isolation and connection lifecycle.
    with connection.cursor() as cursor:
        cursor.execute(query)
        features, size = [], 0
        for name, props, geometry, srid, dimensions in cursor:
            if len(features) >= 1400 or srid != 4326 or dimensions != 2:
                raise ValueError('bounded 2D EPSG:4326 source required')
            if isinstance(props, str):
                props = decode(props.encode())
            feature = {'type': 'Feature', 'id': name, 'properties': props,
                       'geometry': decode(geometry.encode()) if isinstance(geometry, str) else geometry}
            size += len(canonical(feature))
            if size > 4 * 1024 * 1024:
                raise ValueError('PostGIS snapshot exceeds input limit')
            features.append(feature)
    data = {'type': 'FeatureCollection', 'features': features}
    validate(data)
    return data
