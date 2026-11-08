"""Exercise installed imports outside the checkout, including repository adapter."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    with tempfile.TemporaryDirectory() as directory:
        destination=Path(directory)/'bundle'
        pilot=subprocess.run([sys.executable,'-I','-m','researchos','pilot','--output',str(destination)],cwd=directory,capture_output=True,text=True)
        if pilot.returncode!=1: raise RuntimeError('Expected unresolved pilot exit 1: '+pilot.stderr)
        result=json.loads(pilot.stdout)
        if result['state']['claims']['domain-pilot']['state']!='ADVERSARIAL_TEST': raise RuntimeError('Pilot unexpectedly promoted or failed')
        if result['execution_authorized'] or result['clinical_use_authorized']: raise RuntimeError('Unexpected authorization')
        verified=subprocess.run([sys.executable,'-I','-m','researchos','verify',str(destination)],cwd=directory,capture_output=True,text=True)
        if verified.returncode or not json.loads(verified.stdout)['replay_consistent']: raise RuntimeError(verified.stderr)
        import base64
        receipt=json.loads(base64.b64decode(result['state']['evidence']['computed-check']['content_base64']))
        if not receipt['passed']: raise RuntimeError('Domain check failed')
        print(json.dumps({'installed_pilot_checked':True,'domain':receipt['domain'],'final_state':'ADVERSARIAL_TEST','replay_consistent':True}))


if __name__=='__main__': main()
