"""Actual domain computation plus isolated controller probes, no invented reproduction."""
import base64
import copy
import hashlib
from .core import Controller, canonical, policy_default, replay, ATTACKS


def receipt(cid, identifier, payload, kind='validation', result='PASS', **extra):
    content=canonical(payload).encode()
    return {'id':identifier,'claim':cid,'claim_version':1,'kind':kind,'result':result,
            'source':'local:domain-pilot','method':'domain-adapter-v1','run_id':'local-run-1',
            'group':'same-local-execution','weight':1.0,'quality':1.0,'reliability':1.0,'independence':0.5,
            'observed_at':'2026-11-08T00:00:00Z','expires_at':'2026-12-08T00:00:00Z',
            'content_base64':base64.b64encode(content).decode(),'sha256':hashlib.sha256(content).hexdigest(),**extra}


def probes(controller, cid):
    """Three actual controller regression attacks; not domain robustness evidence."""
    results=[]
    for kind in ATTACKS:
        c=copy.deepcopy(controller); before=c.snapshot()
        if kind=='source_poisoning':
            evidence=receipt(cid,'poison',{'fixture':'corrupted content'},sha256='0'*64)
            event=c.apply({'op':'evidence','actor':'validator','data':evidence})
            passed=event['outcome']=='FAIL' and c.snapshot()==before
        else:
            event=c.apply({'op':'challenge','actor':'adversary','data':{'claim':cid,'id':'probe-'+kind,'reason':'Synthetic '+kind,'attack_class':kind}})
            attempted=c.apply({'op':'transition','actor':'reviewer','data':{'claim':cid,'target':'ASSURED'}})
            passed=event['outcome']=='PASS' and c.snapshot()['claims'][cid]['state']=='CONTESTED' and attempted['outcome']!='PASS'
        results.append({'attack_class':kind,'scope':'controller-regression-only','detector_result':'PASS' if passed else 'FAIL',
                        'decision':event['outcome'],'reason':event['reasons']})
    return results


def scenario():
    from .domain import check
    from pathlib import Path
    from . import domain
    payload=check()
    payload['adapter_sha256']=hashlib.sha256(Path(domain.__file__).read_bytes()).hexdigest()
    if not isinstance(payload,dict) or type(payload.get('passed')) is not bool: raise ValueError('Domain adapter must return a Boolean passed receipt')
    payload['controller_probes_are_not_domain_tests']=True
    cid='domain-pilot'
    operations=[{'op':'register','actor':'author','data':{'id':cid,'statement':payload['statement'],
                'provenance':['local:researchos/domain.py'],'confidence':0.5,
                'assurance_scope':'Offline synthetic software check; no operational authorization'}},
                {'op':'transition','actor':'validator','data':{'claim':cid,'target':'UNVERIFIED'}},
                {'op':'evidence','actor':'validator','data':receipt(cid,'computed-check',payload,result='PASS' if payload['passed'] else 'FAIL')}]
    result={'schema_version':1,'as_of':'2026-11-08T00:00:00Z','policy':policy_default(),'operations':operations}
    controller=replay(result)
    for target in ('SUPPORTED','ADVERSARIAL_TEST','REPRODUCED'):
        op={'op':'transition','actor':'validator','data':{'claim':cid,'target':target}}
        operations.append(op); controller.apply(op)
    # These probe receipts are captured as evidence about the controller only.
    # They do not satisfy domain attack gates or reproduction requirements.
    operations.append({'op':'evidence','actor':'validator','data':receipt(cid,'controller-probe-record',probes(controller,cid),independence=0.0,method='controller-regression-probes')})
    # Recording new evidence correctly requires review. Re-enter supported/testing;
    # retain the final UNCERTAIN decision for absent domain tests/reproduction.
    for target in ('SUPPORTED','ADVERSARIAL_TEST','REPRODUCED'):
        operations.append({'op':'transition','actor':'validator','data':{'claim':cid,'target':target}})
    return result
