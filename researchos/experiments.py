"""Compute descriptive metrics from explicitly supplied labeled observations."""
import math
from .core import fields, text

CONDITIONS=('human_tools','single_model','unstructured_multi_agent','researchos')


def evaluate(records):
    if not isinstance(records,list) or not records or len(records)>10000: raise ValueError('1 to 10000 observations required')
    seen=set(); grouped={c:[] for c in CONDITIONS}
    required=('task_id','condition','synthetic','accepted','ground_truth','seconds','reviewer_hours','reproduction_tested','reproduced','failure_present','failure_detected','audit_seconds')
    for r in records:
        fields(r,required); text(r['task_id'])
        if r['condition'] not in CONDITIONS: raise ValueError('Unknown experimental condition')
        key=(r['condition'],r['task_id'])
        if key in seen: raise ValueError('Duplicate condition/task observation')
        seen.add(key)
        for name in ('synthetic','accepted','reproduction_tested','reproduced','failure_present','failure_detected'):
            if type(r[name]) is not bool: raise ValueError('Boolean flags required')
        if r['ground_truth'] is not None and type(r['ground_truth']) is not bool: raise ValueError('ground_truth must be true, false or null')
        for name in ('seconds','reviewer_hours','audit_seconds'):
            if type(r[name]) not in (int,float) or not math.isfinite(r[name]) or r[name]<0: raise ValueError('Nonnegative finite measurements required')
        if r['seconds']<=0 or (r['reproduced'] and not r['reproduction_tested']) or (r['failure_detected'] and not r['failure_present']): raise ValueError('Inconsistent observation')
        grouped[r['condition']].append(r)
    summaries={}
    for condition,rows in grouped.items():
        accepted=[r for r in rows if r['accepted']]
        labeled=[r for r in accepted if r['ground_truth'] is not None]
        validated=sum(r['ground_truth'] is True for r in accepted)
        seconds=sum(r['seconds'] for r in rows); tested=sum(r['reproduction_tested'] for r in rows)
        present=sum(r['failure_present'] for r in rows)
        summaries[condition]={'observations':len(rows),'synthetic_observations':sum(r['synthetic'] for r in rows),
            'accepted_ground_truth_coverage':len(labeled)/len(accepted) if accepted else None,
            'validated_results_per_second':validated/seconds if seconds else None,
            'false_claim_rate_among_labeled_accepted':sum(r['ground_truth'] is False for r in labeled)/len(labeled) if labeled else None,
            'reproduction_rate':sum(r['reproduced'] for r in rows)/tested if tested else None,
            'failure_detection_rate':sum(r['failure_detected'] for r in rows)/present if present else None,
            'mean_audit_seconds':sum(r['audit_seconds'] for r in rows)/len(rows) if rows else None,
            'reviewer_hours_per_validated_result':sum(r['reviewer_hours'] for r in rows)/validated if validated else None}
    tasksets=[{r['task_id'] for r in grouped[c]} for c in CONDITIONS]
    return {'schema_version':1,'conditions':summaries,'matched_tasks_across_all_conditions':sorted(set.intersection(*tasksets)),
            'all_conditions_have_identical_tasks':bool(tasksets[0]) and all(s==tasksets[0] for s in tasksets),
            'interpretation':'Descriptive supplied observations; no statistical significance, independence or causal benefit established'}
