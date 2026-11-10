"""Pure original118 proposal boundary, NOT a fitted numerical policy.

The later owner must supply source-bound, paid numeric predictions. This code
never scores candidates, reads a NET, obtains labels, or fills missing classes.
"""
import hashlib
import json
import math
import re

Q=(25,50,75,100,125,150,200,250,300)

def need(value,message):
    if not value:raise ValueError(message)

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def identity(value):return hashlib.sha256(canonical(value)).hexdigest()

def request_contract(messages):
    """Bind only the original actual message bytes, including full feedback.

    Candidate extraction is for output legality. The complete messages remain
    the declared input; this is not an approved statistical feature encoder.
    """
    need(type(messages) is list and len(messages)==2,'Exact original two-message request required')
    need([m.get('role') for m in messages]==['system','user'],'Original role order')
    need(all(set(m)=={'role','content'} and type(m['content']) is str for m in messages),'No hidden input fields')
    text=messages[1]['content']
    primary=re.findall(r'^CANDIDATE_BUSES_YOU_MAY_USE: (\[[^\n]*\])$',text,re.M)
    repair=re.findall(r'^You must choose exactly one bus from this list: (\[[^\n]*\])$',text,re.M)
    need(len(primary)+len(repair)==1,'Unknown or ambiguous original request template')
    if primary:
        legal_q=re.findall(r'^ALLOWED_Q_MVAR_VALUES: (\[[^\n]*\])$',text,re.M);request_kind='PRIMARY'
    else:
        legal_q=re.findall(r'^You must choose one q_mvar from this list: (\[[^\n]*\])$',text,re.M);request_kind='FORMAT_REPAIR'
    need(len(legal_q)==1,'Unknown Q contract')
    buses=json.loads((primary or repair)[0]);qs=json.loads(legal_q[0])
    need(buses and all(type(b) is int and 0<=b<118 for b in buses) and buses==sorted(set(buses)),'Original finite candidate list')
    need(qs==list(Q),'Original source Q grid changed')
    catalog=[{'bus':str(b),'q_mvar':q} for b in buses for q in Q]
    return {'messages_sha256':identity(messages),'kind':request_kind,'candidate_buses':buses,
       'q_grid':list(Q),'candidate_catalog':catalog,'candidate_catalog_sha256':identity(catalog),
       'full_messages_retained':messages,'new_observed_fields':0,'proposal_slots':1,
       'unqueried_outcomes_or_NET_admitted':False}

def decode_admitted_scores(messages,receipt,*,expected_estimator_sha256,expected_training_manifest_sha256):
    """One declared numeric inference -> one original compact JSON proposal.

    No fallback, hidden query, null repair, class filling or class truncation.
    Complete action support is required before any empirical comparison.
    """
    contract=request_contract(messages)
    need(set(receipt)=={'status','messages_sha256','candidate_catalog_sha256','estimator_sha256',
        'training_manifest_sha256','scores','numeric_prediction_calls','extra_PF_queries','extra_observed_fields',
        'prediction_cost_ref'},'Complete declared numeric prediction receipt required')
    need(receipt['status']=='COMPLETE_SOURCE_BOUND_NUMERIC_PREDICTION','Missing/failed score cannot become an action')
    need(receipt['messages_sha256']==contract['messages_sha256'] and receipt['candidate_catalog_sha256']==contract['candidate_catalog_sha256'],'Wrong current request/action support')
    need(receipt['estimator_sha256']==expected_estimator_sha256 and len(expected_estimator_sha256)==64
         and receipt['training_manifest_sha256']==expected_training_manifest_sha256 and len(expected_training_manifest_sha256)==64,'Wrong frozen model/data')
    scores=receipt['scores'];need(type(scores) is list and len(scores)==len(contract['candidate_catalog']),'No omitted/unseen candidate class imputation')
    need(all(type(v) in (float,int) and math.isfinite(v) for v in scores),'All declared scores must be actual finite values')
    need(receipt['numeric_prediction_calls']==1 and receipt['extra_PF_queries']==0 and receipt['extra_observed_fields']==0,'One same-information proposal call only')
    cost=receipt['prediction_cost_ref'];need(type(cost) is dict and set(cost)=={'path','bytes','sha256'} and cost['path'] and type(cost['bytes']) is int and cost['bytes']>0 and len(cost['sha256'])==64,'Missing actual inference cost record')
    best=max(range(len(scores)),key=lambda i:scores[i]) # fixed original bus/Q order on ties
    action=contract['candidate_catalog'][best]
    return {'raw':json.dumps(action,separators=(',',':')),'candidate_index':best,
       'input_sha256':contract['messages_sha256'],'score_receipt_sha256':identity(receipt),
       'new_PF_model_training_calls_by_bridge':0,'strong_numeric_policy_fitted_or_validated_here':False}
