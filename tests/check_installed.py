"""Exercise installed CLI outside the checkout, including expected gap exit status."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        for requirements, expected in [('requirements.json', 0), ('gaps.json', 1), ('outage.json', 1)]:
            output = Path(directory) / requirements
            command = [sys.executable, '-I', '-m', 'spatial_topology', 'analyze',
                       str(root / 'examples/network.geojson'), '--requirements',
                       str(root / 'examples' / requirements), '--output', str(output)]
            result = subprocess.run(command, cwd=directory, capture_output=True, text=True, check=False)
            if result.returncode != expected:
                raise AssertionError(result.stderr or result.stdout)
            verification = subprocess.run([sys.executable, '-I', '-m', 'spatial_topology', 'verify', str(output)],
                                          cwd=directory, capture_output=True, text=True, check=False)
            if verification.returncode != 0 or not json.loads(verification.stdout)['bundle_consistent']:
                raise AssertionError(verification.stderr or verification.stdout)
        comparison = subprocess.run([sys.executable, '-I', '-m', 'spatial_topology', 'compare',
                                     str(Path(directory) / 'requirements.json'), str(Path(directory) / 'outage.json')],
                                    cwd=directory, capture_output=True, text=True, check=False)
        if comparison.returncode != 0 or json.loads(comparison.stdout)['acceptance_criteria_changed']:
            raise AssertionError(comparison.stderr or comparison.stdout)
    print('Installed package baseline, gap, outage and comparison workflows passed')


if __name__ == '__main__':
    main()
