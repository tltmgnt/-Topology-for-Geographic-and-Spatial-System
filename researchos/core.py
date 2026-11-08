"""TECT v0.1: explicit offline epistemic transitions, not a truth oracle."""
import base64
import copy
from datetime import datetime
import hashlib
import json
import math

VERSION = '0.1.0'
STATES = ('GENERATED','UNVERIFIED','SUPPORTED','ADVERSARIAL_TEST','REPRODUCED','VALIDATED','STABLE','ASSURED')
OUTCOMES = ('PASS','FAIL','UNCERTAIN')
ATTACKS = ('source_poisoning','contradiction_injection','assumption_violation')
RELATIONS = ('supports','derives','depends_on','reproduces','qualifies','contradicts','invalidates')


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n'


def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()


def text(value):
    if not isinstance(value,str) or not value.strip() or value!=value.strip() or len(value)>4096:
        raise ValueError('Expected a trimmed nonempty string of at most 4096 characters')
    return value


def unit(value):
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:
        raise ValueError('Expected a finite number in [0,1]')
    return float(value)


def date(value):
    value=text(value)
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None: raise ValueError('Timestamps require a timezone')
    return result


def fields(obj,required,optional=()):
    if not isinstance(obj,dict) or not set(required)<=set(obj) or set(obj)-set(required)-set(optional):
        raise ValueError('Missing or unknown fields')


def policy_default():
    return {'actors':{'author':['author'],'validator':['validator'],'adversary':['adversary'],
                      'reproducer':['reproducer'],'reviewer':['reviewer']},
            'minimum_density':0.2,'minimum_groups':1,'epsilon':0.1,
            'required_attacks':list(ATTACKS),'required_validations':['domain-adapter-v1']}


class Controller:
    """Actor names are supplied identities, not authentication credentials.

    Snapshot copies prevent accidental mutation. The caller controlling Python
    internals or the scenario remains trusted. Every rejected operation is logged.
    """
    def __init__(self, policy, as_of):
        fields(policy,('actors','minimum_density','minimum_groups','epsilon','required_attacks','required_validations'))
        if not isinstance(policy['actors'],dict) or not policy['actors']: raise ValueError('Actors required')
        roles={'author','validator','adversary','reproducer','reviewer'}
        for actor,assigned in policy['actors'].items():
            text(actor)
            if not isinstance(assigned,list) or not assigned or any(r not in roles for r in assigned):
                raise ValueError('Unknown actor role')
        unit(policy['minimum_density']); unit(policy['epsilon'])
        if policy['minimum_density']<=0 or policy['epsilon']<=0: raise ValueError('Positive thresholds required')
        if type(policy['minimum_groups']) is not int or not 1<=policy['minimum_groups']<=16: raise ValueError('Invalid minimum_groups')
        if not isinstance(policy['required_attacks'],list) or not policy['required_attacks'] or len(set(policy['required_attacks']))!=len(policy['required_attacks']) or any(a not in ATTACKS for a in policy['required_attacks']):
            raise ValueError('Nonempty unique registered attack classes required')
        if not isinstance(policy['required_validations'],list) or not policy['required_validations'] or len(set(policy['required_validations']))!=len(policy['required_validations']): raise ValueError('Unique required validation methods required')
        for method in policy['required_validations']: text(method)
        date(as_of)
        self.policy=copy.deepcopy(policy); self.as_of=as_of
        self._state={'version':0,'claims':{},'evidence':{},'relations':[]}
        self.ledger=[]
        self.root=digest({'engine_version':VERSION,'policy':policy,'as_of':as_of})

    def snapshot(self): return copy.deepcopy(self._state)

    def _has(self,actor,role): return role in self.policy['actors'].get(actor,[])

    def _valid(self,e):
        return date(e['observed_at'])<=date(self.as_of)<date(e['expires_at'])

    def _evidence(self,claim):
        return [e for e in self._state['evidence'].values() if e['claim']==claim['id'] and e['claim_version']==claim['version'] and self._valid(e)]

    def density(self,claim_id):
        claim=self._state['claims'][claim_id]
        selected=[e for e in self._evidence(claim) if e['kind']=='validation' and e['result']=='PASS']
        # Correlation clusters connect same declared group OR identical bytes.
        clusters=[]
        for e in selected:
            touching=[c for c in clusters if any(x['group']==e['group'] or x['sha256']==e['sha256'] for x in c)]
            merged=[e]+[x for c in touching for x in c]
            clusters=[c for c in clusters if c not in touching]+[merged]
        degree=sum(r['source']==claim_id or r['target']==claim_id for r in self._state['relations'])
        score=sum(max(e['weight']*e['quality']*e['reliability']*e['independence'] for e in c) for c in clusters)/(1+degree)
        return {'density':score,'declared_correlation_clusters':len(clusters),'reasoning_degree':degree}

    def _invalidate(self,claim_id,reason,contested=True):
        queue=[claim_id]; seen=set()
        while queue:
            cid=queue.pop(0)
            if cid in seen: continue
            seen.add(cid); claim=self._state['claims'][cid]
            claim['state']='CONTESTED' if contested or any(not c['resolved'] for c in claim['challenges']) else 'UNVERIFIED'
            claim['reassessment_reasons'].append(reason)
            for r in self._state['relations']:
                if r['source']==cid and r['relation'] not in ('contradicts','invalidates'): queue.append(r['target'])

    def _blockers(self,claim,target):
        reasons=[]; current_evidence=self._evidence(claim)
        if target!='UNVERIFIED':
            if not claim['provenance']: reasons.append('PROVENANCE_MISSING')
            if any(not c['resolved'] for c in claim['challenges']): reasons.append('UNRESOLVED_CHALLENGE')
            for r in self._state['relations']:
                if r['target']==claim['id'] and r['relation'] not in ('contradicts','invalidates'):
                    upstream=self._state['claims'][r['source']]
                    minimum='SUPPORTED' if target in ('SUPPORTED','ADVERSARIAL_TEST') else 'VALIDATED'
                    if upstream['state'] not in STATES or STATES.index(upstream['state'])<STATES.index(minimum): reasons.append('DEPENDENCY_NOT_READY:'+upstream['id'])
            for method in self.policy['required_validations']:
                attempts=[e for e in current_evidence if e['kind']=='validation' and e['method']==method]
                if not attempts or max(attempts,key=lambda e:e['recorded_sequence'])['result']!='PASS': reasons.append('REQUIRED_VALIDATION_NOT_PASSED:'+method)
            coverage=self.density(claim['id'])
            if coverage['density']<self.policy['minimum_density'] or coverage['declared_correlation_clusters']<self.policy['minimum_groups']:
                reasons.append('INSUFFICIENT_CURRENT_VALIDATION')
        if target in ('REPRODUCED','VALIDATED','STABLE','ASSURED'):
            for attack in self.policy['required_attacks']:
                attempts=[e for e in current_evidence if e['kind']=='attack' and e['attack_class']==attack]
                if not attempts or max(attempts,key=lambda e:e['recorded_sequence'])['result']!='PASS': reasons.append('ATTACK_NOT_PASSED:'+attack)
            validation=[e for e in current_evidence if e['kind']=='validation' and e['result']=='PASS']
            reproduction=[e for e in current_evidence if e['kind']=='reproduction' and e['result']=='PASS']
            # Declared separation plus different bytes; not proof of scientific independence.
            if not any(all(e[k]!=v[k] for k in ('actor','run_id','method','group','sha256')) for e in reproduction for v in validation):
                reasons.append('SEPARATE_REPRODUCTION_MISSING')
        if target in ('STABLE','ASSURED'):
            attacks=[e for e in current_evidence if e['kind']=='attack' and e['result']=='PASS']
            if any(e['distance']>=self.policy['epsilon'] for e in attacks): reasons.append('ATTACK_DISTANCE_OUTSIDE_EPSILON')
        if target=='ASSURED' and not claim['assurance_scope']: reasons.append('ASSURANCE_SCOPE_MISSING')
        return sorted(set(reasons))

    def apply(self,operation):
        canonical(operation) # Reject non-JSON transport values before any mutation.
        if len(self.ledger)>=2000: raise ValueError('Ledger operation limit reached')
        before=self.snapshot(); before_hash=digest(before); before_time=self.as_of
        operation=copy.deepcopy(operation); outcome='FAIL'; reasons=[]
        try:
            fields(operation,('op','actor','data'),('expected_version',))
            if 'expected_version' in operation and (type(operation['expected_version']) is not int or operation['expected_version']!=before['version']):
                raise ValueError('STALE_STATE_VERSION')
            actor=text(operation['actor']); op=text(operation['op']); data=operation['data']
            if actor not in self.policy['actors']: raise ValueError('UNAUTHORIZED_ACTOR')
            outcome,reasons=self._execute(op,actor,data)
            if outcome=='PASS': self._state['version']+=1
            else: self._state=before
        except (ValueError,TypeError,KeyError,OverflowError) as exc:
            self._state=before; self.as_of=before_time; outcome='FAIL'; reasons=[str(exc)]
        entry={'sequence':len(self.ledger),'timestamp':self.as_of,'operation':operation,
               'outcome':outcome,'reasons':reasons,'before':before_hash,'after':digest(self._state),
               'previous_hash':self.ledger[-1]['hash'] if self.ledger else self.root}
        entry['hash']=digest(entry); self.ledger.append(entry)
        return copy.deepcopy(entry)

    def _execute(self,op,actor,data):
        if op=='register':
            fields(data,('id','statement','provenance','confidence','assurance_scope'))
            if not self._has(actor,'author'): raise ValueError('AUTHOR_ROLE_REQUIRED')
            cid=text(data['id']); text(data['statement']); unit(data['confidence'])
            if cid in self._state['claims'] or len(self._state['claims'])>=128: raise ValueError('Duplicate claim or claim limit')
            if not isinstance(data['provenance'],list) or any(not isinstance(p,str) or not p.strip() for p in data['provenance']): raise ValueError('Invalid provenance')
            if not isinstance(data['assurance_scope'],str): raise ValueError('Invalid assurance_scope')
            self._state['claims'][cid]={**copy.deepcopy(data),'version':1,'state':'GENERATED','challenges':[],
                                      'reassessment_reasons':[],'last_validation_at':None}
        elif op=='evidence':
            required=('id','claim','claim_version','kind','result','source','method','run_id','group','weight','quality','reliability','independence','observed_at','expires_at','content_base64','sha256')
            fields(data,required,('attack_class','distance'))
            role={'validation':'validator','reproduction':'reproducer','attack':'adversary'}.get(data['kind'])
            if not role or not self._has(actor,role): raise ValueError('EVIDENCE_ROLE_REQUIRED')
            for key in ('id','claim','source','method','run_id','group'): text(data[key])
            claim=self._state['claims'][data['claim']]
            if type(data['claim_version']) is not int or data['claim_version']!=claim['version']: raise ValueError('STALE_CLAIM_VERSION')
            if data['id'] in self._state['evidence'] or len(self._state['evidence'])>=1024: raise ValueError('Duplicate evidence or evidence limit')
            if data['result'] not in OUTCOMES: raise ValueError('Invalid result')
            for key in ('weight','quality','reliability','independence'): unit(data[key])
            if date(data['expires_at'])<=date(data['observed_at']): raise ValueError('Invalid evidence interval')
            if not self._valid(data): raise ValueError('EVIDENCE_NOT_CURRENT')
            if not isinstance(data['content_base64'],str) or len(data['content_base64'])>90000: raise ValueError('Invalid artifact size')
            try: content=base64.b64decode(data['content_base64'],validate=True)
            except Exception as exc: raise ValueError('Invalid base64') from exc
            if not content or len(content)>65536 or hashlib.sha256(content).hexdigest()!=data['sha256']: raise ValueError('EVIDENCE_CONTENT_MISMATCH')
            if data['kind']=='attack':
                if data.get('attack_class') not in ATTACKS: raise ValueError('Unknown attack class')
                unit(data.get('distance'))
            elif 'attack_class' in data or 'distance' in data: raise ValueError('Attack-only fields')
            if sum(len(e['content_base64']) for e in self._state['evidence'].values())+len(data['content_base64'])>1400000: raise ValueError('Total evidence byte limit')
            self._state['evidence'][data['id']]={**copy.deepcopy(data),'actor':actor,'recorded_sequence':len(self.ledger)}
            if data['result']=='FAIL':
                claim['challenges'].append({'id':data['id'],'reason':'Failed '+data['kind'],'resolved':False,'recorded_sequence':len(self.ledger)})
                self._invalidate(claim['id'],'FAILED_EVIDENCE:'+data['id'])
            elif claim['state'] not in ('GENERATED','UNVERIFIED','CONTESTED'):
                self._invalidate(claim['id'],'NEW_EVIDENCE_REQUIRES_REVIEW',False)
        elif op=='transition':
            fields(data,('claim','target'))
            claim=self._state['claims'][data['claim']]; target=data['target']; state=claim['state']
            role='reviewer' if target in ('VALIDATED','STABLE','ASSURED') else 'validator'
            if not self._has(actor,role): raise ValueError('TRANSITION_ROLE_REQUIRED:'+role)
            if target not in STATES: raise ValueError('Unknown target state')
            if state=='CONTESTED':
                if target!='UNVERIFIED': raise ValueError('CONTESTED_REQUIRES_REASSESSMENT')
                if any(not c['resolved'] for c in claim['challenges']): return 'UNCERTAIN',['UNRESOLVED_CHALLENGE']
            elif state not in STATES or STATES.index(target)!=STATES.index(state)+1: raise ValueError('NON_ADJACENT_TRANSITION')
            reasons=self._blockers(claim,target)
            if reasons: return 'UNCERTAIN',reasons
            claim['state']=target
            if target=='VALIDATED': claim['last_validation_at']=self.as_of
        elif op=='challenge':
            fields(data,('claim','id','reason','attack_class'))
            if not self._has(actor,'adversary'): raise ValueError('ADVERSARY_ROLE_REQUIRED')
            text(data['id']); text(data['reason'])
            if data['attack_class'] not in ATTACKS: raise ValueError('Unknown attack class')
            claim=self._state['claims'][data['claim']]
            if any(c['id']==data['id'] for c in claim['challenges']): raise ValueError('Duplicate challenge')
            claim['challenges'].append({'id':data['id'],'reason':data['reason'],'resolved':False,'recorded_sequence':len(self.ledger)})
            self._invalidate(claim['id'],'CHALLENGE:'+data['id'])
        elif op=='resolve':
            fields(data,('claim','challenge','evidence'))
            if not self._has(actor,'reviewer'): raise ValueError('REVIEWER_ROLE_REQUIRED')
            claim=self._state['claims'][data['claim']]
            evidence=self._state['evidence'][data['evidence']]
            if evidence not in self._evidence(claim) or evidence['result']!='PASS' or evidence['kind']!='validation': raise ValueError('Current passing resolution evidence required')
            challenges=[c for c in claim['challenges'] if c['id']==data['challenge'] and not c['resolved']]
            if not challenges: raise ValueError('Unknown unresolved challenge')
            if evidence['recorded_sequence']<=challenges[0]['recorded_sequence']: raise ValueError('Resolution evidence must postdate the challenge')
            challenges[0].update(resolved=True,resolution_evidence=data['evidence'])
        elif op=='revise':
            fields(data,('claim','statement','provenance','confidence','assurance_scope'))
            if not self._has(actor,'author'): raise ValueError('AUTHOR_ROLE_REQUIRED')
            claim=self._state['claims'][data['claim']]; text(data['statement']); unit(data['confidence'])
            if not isinstance(data['provenance'],list) or any(not isinstance(p,str) or not p.strip() for p in data['provenance']) or not isinstance(data['assurance_scope'],str): raise ValueError('Invalid provenance or scope')
            claim.update({k:copy.deepcopy(data[k]) for k in ('statement','provenance','confidence','assurance_scope')})
            claim['version']+=1; claim['last_validation_at']=None
            self._invalidate(claim['id'],'CLAIM_REVISED',False)
        elif op=='relation':
            fields(data,('source','target','relation'))
            if not self._has(actor,'validator'): raise ValueError('VALIDATOR_ROLE_REQUIRED')
            source,target=data['source'],data['target']
            if source==target or source not in self._state['claims'] or target not in self._state['claims'] or data['relation'] not in RELATIONS: raise ValueError('Invalid relation')
            if data in self._state['relations'] or len(self._state['relations'])>=512: raise ValueError('Duplicate relation or relation limit')
            if data['relation'] not in ('contradicts','invalidates'):
                queue=[target]; seen=set()
                while queue:
                    node=queue.pop()
                    if node==source: raise ValueError('CYCLIC_PREREQUISITE')
                    if node in seen: continue
                    seen.add(node)
                    queue.extend(r['target'] for r in self._state['relations'] if r['source']==node and r['relation'] not in ('contradicts','invalidates'))
            self._state['relations'].append(copy.deepcopy(data))
            if data['relation'] in ('contradicts','invalidates'):
                self._state['claims'][target]['challenges'].append({'id':'relation:'+str(len(self._state['relations'])),'reason':data['relation']+' from '+source,'resolved':False,'recorded_sequence':len(self.ledger)})
            self._invalidate(target,'RELATION_CHANGED',data['relation'] in ('contradicts','invalidates'))
            # Reasoning degree affects source density as well as target density.
            self._invalidate(source,'REASONING_DEGREE_CHANGED',False)
        elif op=='reassess':
            fields(data,('as_of',))
            if not self._has(actor,'reviewer'): raise ValueError('REVIEWER_ROLE_REQUIRED')
            if date(data['as_of'])<date(self.as_of): raise ValueError('Assessment time cannot move backward')
            self.as_of=data['as_of']
            for cid,claim in self._state['claims'].items():
                if claim['state'] in STATES[2:] and self._blockers(claim,claim['state']):
                    self._invalidate(cid,'ASSESSMENT_EXPIRED_OR_BLOCKED')
        else: raise ValueError('Unknown operation')
        return 'PASS',[]

    def report(self):
        state=self.snapshot(); densities={cid:self.density(cid) for cid in state['claims']}
        burden={'unsupported':sum(c['state'] not in ('VALIDATED','STABLE','ASSURED') for c in state['claims'].values()),
                'contradictions':sum(not x['resolved'] for c in state['claims'].values() for x in c['challenges']),
                'provenance_deficiency':sum(not c['provenance'] for c in state['claims'].values()),
                'governance_deficiency':sum(c['state']=='ASSURED' and bool(self._blockers(c,'ASSURED')) for c in state['claims'].values()),
                'unresolved_attack_classes':sum(not any(e['kind']=='attack' and e.get('attack_class')==a and e['result']=='PASS' for e in self._evidence(c)) for c in state['claims'].values() for a in self.policy['required_attacks'])}
        return {'schema_version':1,'engine_version':VERSION,'as_of':self.as_of,'state':state,
                'density':densities,'assurance_blockers':{cid:self._blockers(c,'ASSURED') for cid,c in state['claims'].items()},'potential':{'terms':burden,'equal_weight_sum':sum(burden.values())},
                'ledger_root':self.root,'ledger_head':self.ledger[-1]['hash'] if self.ledger else self.root,
                'transition_outcomes':{o:sum(e['outcome']==o for e in self.ledger) for o in OUTCOMES},
                'execution_authorized':False,'clinical_use_authorized':False,
                'limits':'Local declared-policy acceptance only; not truth, authentication, independent certification or operational approval'}


def replay(scenario):
    fields(scenario,('schema_version','as_of','policy','operations'))
    if type(scenario['schema_version']) is not int or scenario['schema_version']!=1: raise ValueError('Unsupported schema version')
    if not isinstance(scenario['operations'],list) or len(scenario['operations'])>2000: raise ValueError('Invalid operation list')
    controller=Controller(scenario['policy'],scenario['as_of'])
    for op in scenario['operations']: controller.apply(op)
    return controller


def state_distance(first,second):
    """Illustrative distance on a projection; distinct metadata can have distance zero."""
    claims=set(first['claims'])|set(second['claims'])
    status=confidence=0.0
    for cid in claims:
        a,b=first['claims'].get(cid),second['claims'].get(cid)
        status += float(a is None or b is None or a['state']!=b['state'])
        confidence += 1.0 if a is None or b is None else abs(a['confidence']-b['confidence'])
    def jaccard(a,b):
        return len(a^b)/len(a|b) if a|b else 0.0
    relations=lambda s:{canonical(r) for r in s['relations']}
    evidence=lambda s:{(e['id'],e['sha256']) for e in s['evidence'].values()}
    return (status/max(1,len(claims))+confidence/max(1,len(claims))+
            jaccard(relations(first),relations(second))+jaccard(evidence(first),evidence(second)))/4
