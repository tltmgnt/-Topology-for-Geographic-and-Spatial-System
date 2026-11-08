"""Command-line network analysis and replay verification."""
import argparse
import json
import sys
from .io import compare_bundles, create_bundle, read_json, verify_bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    analyze = commands.add_parser('analyze', help='Create a new offline review bundle')
    analyze.add_argument('network')
    analyze.add_argument('--requirements', required=True)
    analyze.add_argument('--output', required=True)
    verify = commands.add_parser('verify', help='Recompute a bundle and compare every file')
    verify.add_argument('bundle')
    compare = commands.add_parser('compare', help='Compare two verified bundles from one network')
    compare.add_argument('baseline')
    compare.add_argument('scenario')
    export = commands.add_parser('export-gpkg', help='Export engine GeoJSON to a new WGS84 GeoPackage')
    export.add_argument('network')
    export.add_argument('--output', required=True)
    ingest = commands.add_parser('import-gpkg', help='Capture an engine GeoPackage as GeoJSON')
    ingest.add_argument('network')
    ingest.add_argument('--output', required=True)
    database = commands.add_parser('import-postgis', help='Capture a PostGIS relation into offline GeoJSON')
    database.add_argument('--schema', default='public')
    database.add_argument('--table', required=True)
    database.add_argument('--dsn-env', default='SPATIAL_TOPOLOGY_DSN')
    database.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'import-postgis':
            import os
            from .analysis import canonical
            from .postgis import read_postgis
            try:
                import psycopg
            except ImportError as error:
                raise ValueError('PostGIS import requires spatial-topology[postgis]') from error
            dsn = os.environ.get(args.dsn_env)
            if not dsn:
                raise ValueError('database connection environment variable is missing')
            try:
                with psycopg.connect(dsn, connect_timeout=10, options='-c default_transaction_read_only=on -c statement_timeout=30000') as connection:
                    data = read_postgis(connection, args.schema, args.table)
            except psycopg.Error as error:
                raise ValueError('PostGIS snapshot failed; check database access and source contract') from error
            with open(args.output, 'xb') as stream:
                stream.write(canonical(data))
            result, code = {'created': True, 'output': args.output}, 0
        elif args.command in ('export-gpkg', 'import-gpkg'):
            from .geopackage import read_geopackage, write_geopackage
            from .analysis import canonical
            if args.command == 'export-gpkg':
                write_geopackage(args.output, read_json(args.network))
            else:
                data = read_geopackage(args.network)
                with open(args.output, 'xb') as stream:
                    stream.write(canonical(data))
            result, code = {'created': True, 'output': args.output}, 0
        elif args.command == 'analyze':
            report = create_bundle(args.output, read_json(args.network), read_json(args.requirements))
            result = {'bundle_created': True, 'status': report['status'], 'summary': report['summary']}
            if 'study_status' in report:
                result['study_status'] = report['study_status']
            code = 1 if report['gaps'] or any(s['gaps'] for s in report.get('scenarios', [])) else 0
        elif args.command == 'compare':
            result = compare_bundles(args.baseline, args.scenario)
            code = 0
        else:
            report = verify_bundle(args.bundle)
            result = {'bundle_consistent': True, 'status': report['status'],
                      'execution_authorized': False, 'summary': report['summary']}
            code = 0
    except (ValueError, OSError) as error:
        print(json.dumps({'error': str(error), 'execution_authorized': False}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
