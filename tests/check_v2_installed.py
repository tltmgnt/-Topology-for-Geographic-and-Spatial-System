"""Installed v2 CLI offline replay, failure exit status and GeoPackage interchange."""
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        def run(args, expected=0):
            result = subprocess.run([sys.executable, '-I', '-m', 'spatial_topology', *map(str,args)],
                                    cwd=path, capture_output=True, text=True)
            if result.returncode != expected:
                raise AssertionError(result.stderr or result.stdout)
            return json.loads(result.stdout)
        run(['analyze', root/'examples/network-v2.geojson', '--requirements', root/'examples/requirements-v2.json', '--output', path/'review'], 1)
        self_check = run(['verify', path/'review'])
        assert self_check['bundle_consistent']
        report = json.loads((path/'review/report.json').read_text())
        assert report['independent_verification']['status'] == 'PASS'
        assert report['scenarios'][0]['status'] == 'GAPS_FOUND'
        if shutil.which('node'):
            subprocess.run(['node', str(root/'tests/check_v2_interaction.cjs'), str(path/'review/review.html')], check=True)
        run(['export-gpkg', root/'examples/network-v2.geojson', '--output', path/'network.gpkg'])
        run(['import-gpkg', path/'network.gpkg', '--output', path/'network.geojson'])
        assert json.loads((path/'network.geojson').read_text()) == json.loads((root/'examples/network-v2.geojson').read_text())
    print('Installed v2 scenario replay and GeoPackage workflows passed')


if __name__ == '__main__':
    main()
