"""Synthetic controller contracts; passing tests do not certify scientific claims."""
import base64
import copy
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from researchos.core import Controller, STATES, ATTACKS, canonical, digest, policy_default, replay, state_distance
from researchos.pilot import receipt, scenario, probes
from researchos.io import write_bundle, verify_bundle, load
from researchos.experiments import evaluate


def operation(op, data, actor='validator', **extra):
    return {'op':op,'actor':actor,'data':data,**extra}


def register(c, cid='k'):
    return c.apply(operation('register',{'id':cid,'statement':'Synthetic test assertion','provenance':['fixture:test'],
        'confidence':0.9,'assurance_scope':'Synthetic unit-test policy only'},'author'))


def evidence(c, cid='k', identifier='v', kind='validation', actor='validator', **extra):
    return c.apply(operation('evidence',receipt(cid,identifier,{'fixture':identifier},kind=kind,**extra),actor))


def complete_evidence(c, cid='k'):
    evidence(c,cid,cid+'-validation')
    for attack in ATTACKS:
        evidence(c,cid,cid+'-'+attack,'attack','adversary',attack_class=attack,distance=0.01)
    evidence(c,cid,cid+'-replication','reproduction','reproducer',method='separate-test-method',
             run_id='run-2',group='separate-declared-group')


def promote(c,cid='k', final='ASSURED'):
    events=[]
    for target in STATES[1:STATES.index(final)+1]:
        events.append(c.apply(operation('transition',{'claim':cid,'target':target},'reviewer' if target in ('VALIDATED','STABLE','ASSURED') else 'validator')))
    return events


class StateMachineTests(unittest.TestCase):
    def setUp(self): self.c=Controller(policy_default(),'2026-11-08T00:00:00Z')

    def test_complete_declared_policy_path(self):
        register(self.c); complete_evidence(self.c)
        self.assertTrue(all(e['outcome']=='PASS' for e in promote(self.c)))
        report=self.c.report()
        self.assertEqual(report['state']['claims']['k']['state'],'ASSURED')
        self.assertFalse(report['execution_authorized']); self.assertFalse(report['clinical_use_authorized'])
        self.assertEqual(report['assurance_blockers']['k'],[])

    def test_every_state_pair_has_only_adjacent_successors(self):
        # Check all 64 forward/reverse/self pairs using reached, well-evidenced states.
        for source,target in itertools.product(STATES,repeat=2):
            c=Controller(policy_default(),'2026-11-08T00:00:00Z'); register(c); complete_evidence(c)
            if source!='GENERATED': promote(c,final=source)
            event=c.apply(operation('transition',{'claim':'k','target':target},'reviewer' if target in ('VALIDATED','STABLE','ASSURED') else 'validator'))
            self.assertEqual(event['outcome']=='PASS',STATES.index(target)==STATES.index(source)+1,(source,target))

    def test_missing_evidence_is_uncertain_not_pass(self):
        register(self.c)
        self.c.apply(operation('transition',{'claim':'k','target':'UNVERIFIED'}))
        before=self.c.snapshot()
        event=self.c.apply(operation('transition',{'claim':'k','target':'SUPPORTED'}))
        self.assertEqual(event['outcome'],'UNCERTAIN'); self.assertEqual(self.c.snapshot(),before)
        self.assertIn('INSUFFICIENT_CURRENT_VALIDATION',event['reasons'])

    def test_confidence_is_not_acceptance(self):
        register(self.c); self.c.apply(operation('transition',{'claim':'k','target':'UNVERIFIED'}))
        self.assertEqual(self.c.apply(operation('transition',{'claim':'k','target':'SUPPORTED'}))['outcome'],'UNCERTAIN')

    def test_authorization_and_stale_version(self):
        register(self.c); before=self.c.snapshot()
        event=self.c.apply(operation('transition',{'claim':'k','target':'UNVERIFIED'},'author'))
        self.assertEqual(event['outcome'],'FAIL'); self.assertEqual(self.c.snapshot(),before)
        self.assertEqual(self.c.apply(operation('transition',{'claim':'k','target':'UNVERIFIED'},expected_version=0))['outcome'],'FAIL')
        self.assertEqual(self.c.apply(operation('transition',{'claim':'k','target':'UNVERIFIED'},expected_version=1))['outcome'],'PASS')

    def test_snapshot_is_detached(self):
        register(self.c); snapshot=self.c.snapshot(); snapshot['claims']['k']['state']='ASSURED'
        self.assertEqual(self.c.snapshot()['claims']['k']['state'],'GENERATED')

    def test_failed_evidence_contests_assured_claim(self):
        register(self.c); complete_evidence(self.c); promote(self.c)
        evidence(self.c,identifier='counterexample',result='FAIL')
        self.assertEqual(self.c.snapshot()['claims']['k']['state'],'CONTESTED')
        event=self.c.apply(operation('transition',{'claim':'k','target':'UNVERIFIED'}))
        self.assertEqual(event['outcome'],'UNCERTAIN')

    def test_resolution_requires_new_evidence_and_review(self):
        register(self.c); evidence(self.c)
        self.c.apply(operation('challenge',{'claim':'k','id':'challenge','reason':'Synthetic contradiction','attack_class':'contradiction_injection'},'adversary'))
        self.assertEqual(self.c.apply(operation('resolve',{'claim':'k','challenge':'challenge','evidence':'v'},'reviewer'))['outcome'],'FAIL')
        evidence(self.c,identifier='resolution')
        self.assertEqual(self.c.apply(operation('resolve',{'claim':'k','challenge':'challenge','evidence':'resolution'},'reviewer'))['outcome'],'PASS')
        self.assertEqual(self.c.apply(operation('transition',{'claim':'k','target':'UNVERIFIED'}))['outcome'],'PASS')

    def test_revision_invalidates_evidence(self):
        register(self.c); complete_evidence(self.c); promote(self.c)
        self.c.apply(operation('revise',{'claim':'k','statement':'Changed claim','provenance':['fixture:changed'],'confidence':0.5,'assurance_scope':'Synthetic'},'author'))
        claim=self.c.snapshot()['claims']['k']; self.assertEqual(claim['version'],2)
        self.assertEqual(claim['state'],'UNVERIFIED'); self.assertEqual(self.c.density('k')['density'],0)
        self.assertEqual(evidence(self.c,identifier='old-version')['outcome'],'FAIL')

    def test_time_reassessment_reopens_expired_claim(self):
        register(self.c); complete_evidence(self.c); promote(self.c)
        event=self.c.apply(operation('reassess',{'as_of':'2026-12-08T00:00:00Z'},'reviewer'))
        self.assertEqual(event['outcome'],'PASS')
        self.assertEqual(self.c.snapshot()['claims']['k']['state'],'CONTESTED')
        self.assertEqual(self.c.density('k')['density'],0)
        self.assertEqual(self.c.apply(operation('reassess',{'as_of':'2026-11-01T00:00:00Z'},'reviewer'))['outcome'],'FAIL')

    def test_latest_uncertain_required_validation_blocks(self):
        register(self.c); evidence(self.c); evidence(self.c,identifier='uncertain',result='UNCERTAIN')
        events=promote(self.c,final='SUPPORTED')
        self.assertEqual(events[-1]['outcome'],'UNCERTAIN')

    def test_attack_epsilon_and_reproduction_separation(self):
        register(self.c); complete_evidence(self.c)
        evidence(self.c,identifier='wide-attack',kind='attack',actor='adversary',attack_class='source_poisoning',distance=0.1)
        events=promote(self.c,final='STABLE')
        self.assertEqual(events[-1]['outcome'],'UNCERTAIN')
        self.assertIn('ATTACK_DISTANCE_OUTSIDE_EPSILON',events[-1]['reasons'])
        c=Controller(policy_default(),'2026-11-08T00:00:00Z'); register(c); evidence(c)
        for attack in ATTACKS: evidence(c,identifier=attack,kind='attack',actor='adversary',attack_class=attack,distance=0.01)
        evidence(c,identifier='same-run',kind='reproduction',actor='reproducer')
        self.assertIn('SEPARATE_REPRODUCTION_MISSING',promote(c,final='REPRODUCED')[-1]['reasons'])


class EvidenceAndGraphTests(unittest.TestCase):
    def setUp(self): self.c=Controller(policy_default(),'2026-11-08T00:00:00Z'); register(self.c)

    def test_poisoned_expired_unknown_fields_fail_closed(self):
        for extra in [{'sha256':'0'*64},{'expires_at':'2026-11-08T00:00:00Z'},{'quality':-1},{'ignored':'not allowed'}]:
            before=self.c.snapshot(); event=evidence(self.c,**extra)
            self.assertEqual(event['outcome'],'FAIL'); self.assertEqual(self.c.snapshot(),before)

    def test_correlated_groups_and_duplicate_content_cluster_transitively(self):
        evidence(self.c,identifier='a')
        # Same content, different group: cannot count as a separate source.
        same=receipt('k','b',{'fixture':'a'},group='different')
        self.c.apply(operation('evidence',same))
        # Bridges the declared groups with a distinct artifact.
        evidence(self.c,identifier='c',group='different')
        self.assertEqual(self.c.density('k')['declared_correlation_clusters'],1)
        self.assertAlmostEqual(self.c.density('k')['density'],0.5)

    def test_dependency_failure_propagates_and_cycles_rejected(self):
        register(self.c,'dependent'); register(self.c,'leaf')
        for a,b in [('k','dependent'),('dependent','leaf')]:
            self.assertEqual(self.c.apply(operation('relation',{'source':a,'target':b,'relation':'depends_on'}))['outcome'],'PASS')
        self.assertEqual(self.c.apply(operation('relation',{'source':'leaf','target':'k','relation':'supports'}))['outcome'],'FAIL')
        evidence(self.c,identifier='failed-upstream',result='FAIL')
        for claim in self.c.snapshot()['claims'].values(): self.assertEqual(claim['state'],'CONTESTED')
        event=self.c.apply(operation('transition',{'claim':'dependent','target':'UNVERIFIED'}))
        self.assertEqual(event['outcome'],'PASS')
        event=self.c.apply(operation('transition',{'claim':'dependent','target':'SUPPORTED'}))
        self.assertIn('DEPENDENCY_NOT_READY:k',event['reasons'])

    def test_prerequisite_gates_and_reasoning_degree(self):
        register(self.c,'dependent'); evidence(self.c)
        before=self.c.density('k')['density']
        self.c.apply(operation('relation',{'source':'k','target':'dependent','relation':'derives'}))
        self.assertEqual(self.c.density('k')['density'],before/2)

    def test_controller_probes_are_real_and_leave_original_unchanged(self):
        before=self.c.snapshot(); result=probes(self.c,'k')
        self.assertEqual(self.c.snapshot(),before)
        self.assertEqual({r['attack_class'] for r in result},set(ATTACKS))
        self.assertTrue(all(r['detector_result']=='PASS' for r in result))

    def test_projection_distance(self):
        a=self.c.snapshot(); evidence(self.c); b=self.c.snapshot()
        self.assertEqual(state_distance(a,a),0)
        self.assertGreater(state_distance(a,b),0)
        self.assertEqual(state_distance(a,b),state_distance(b,a))


class LedgerAndCliTests(unittest.TestCase):
    def test_pilot_has_actual_domain_receipt_and_does_not_claim_assurance(self):
        data=scenario(); controller=replay(data); report=controller.report()
        payload=json.loads(base64.b64decode(report['state']['evidence']['computed-check']['content_base64']))
        self.assertTrue(payload['passed']); self.assertEqual(len(payload['adapter_sha256']),64)
        self.assertEqual(report['state']['claims']['domain-pilot']['state'],'ADVERSARIAL_TEST')
        self.assertIn('SEPARATE_REPRODUCTION_MISSING',report['assurance_blockers']['domain-pilot'])
        self.assertGreater(report['transition_outcomes']['UNCERTAIN'],0)

    def test_ledger_chains_accepted_and_blocked_events(self):
        data=scenario(); controller=replay(data); previous=controller.root
        for event in controller.ledger:
            self.assertEqual(event['previous_hash'],previous)
            stripped={k:v for k,v in event.items() if k!='hash'}
            self.assertEqual(digest(stripped),event['hash']); previous=event['hash']
        self.assertEqual(replay(data).report(),controller.report())

    def test_replay_detects_report_and_rehashed_ledger_forgery(self):
        with tempfile.TemporaryDirectory() as parent:
            path=Path(parent)/'bundle'; write_bundle(scenario(),path)
            self.assertEqual(verify_bundle(path)['schema_version'],1)
            ledger=load(path/'ledger.json'); ledger[-1]['outcome']='PASS'
            ledger[-1]['hash']=digest({k:v for k,v in ledger[-1].items() if k!='hash'})
            (path/'ledger.json').write_text(canonical(ledger))
            with self.assertRaises(ValueError): verify_bundle(path)
            with self.assertRaises(FileExistsError): write_bundle(scenario(),path)

    def test_duplicate_json_and_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory() as parent:
            path=Path(parent)/'input.json'
            for content in ['{"a":1,"a":2}','{"a":NaN}','{"a":1e999}']:
                path.write_text(content)
                with self.assertRaises(ValueError): load(path)

    def test_cli_pilot_and_verify_exit_semantics(self):
        with tempfile.TemporaryDirectory() as parent:
            path=Path(parent)/'bundle'
            result=subprocess.run([sys.executable,'-m','researchos','pilot','--output',str(path)],capture_output=True,text=True)
            self.assertEqual(result.returncode,1,result.stderr)
            result=subprocess.run([sys.executable,'-m','researchos','verify',str(path)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(json.loads(result.stdout)['replay_consistent'])


class ExperimentTests(unittest.TestCase):
    def record(self,**changes):
        return dict(task_id='fictional-task',condition='researchos',synthetic=True,accepted=True,ground_truth=True,
                    seconds=2,reviewer_hours=0.1,reproduction_tested=False,reproduced=False,
                    failure_present=False,failure_detected=False,audit_seconds=1,**changes)

    def test_missing_baselines_and_unknown_ground_truth_stay_explicit(self):
        result=evaluate([self.record()]); summary=result['conditions']['researchos']
        self.assertEqual(summary['validated_results_per_second'],0.5)
        self.assertIsNone(summary['reproduction_rate'])
        self.assertFalse(result['all_conditions_have_identical_tasks'])
        unknown=self.record(); unknown['ground_truth']=None
        self.assertIsNone(evaluate([unknown])['conditions']['researchos']['false_claim_rate_among_labeled_accepted'])

    def test_matched_condition_inventory_and_bad_measurements(self):
        rows=[]
        for condition in ('human_tools','single_model','unstructured_multi_agent','researchos'):
            r=self.record(); r['condition']=condition; rows.append(r)
        self.assertTrue(evaluate(rows)['all_conditions_have_identical_tasks'])
        invalid=self.record(); invalid['seconds']=0
        with self.assertRaises(ValueError): evaluate([invalid])
        with self.assertRaises(ValueError): evaluate(rows+[rows[0]])


if __name__=='__main__': unittest.main()
