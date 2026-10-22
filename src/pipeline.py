"""Train/validate before touching test scores. Official split, global dedup, fixed seed."""
import csv,json,sqlite3,platform,time,sys,os
from collections import Counter,defaultdict
import numpy as np
import sklearn,joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support,confusion_matrix
from threadpoolctl import threadpool_limits
from common import ROOT,dump,sha,normalize
from adapter import ReviewAdapter
from cascade import moderate
CFG=json.loads((ROOT/'config/experiment.json').read_text()); ART=ROOT/'artifacts'
def metrics(y,p):
    pr,re,f,_=precision_recall_fscore_support(y,p,average='binary',zero_division=0)
    tn,fp,fn,tp=confusion_matrix(y,p,labels=[0,1]).ravel()
    return dict(n=len(y),precision=float(pr),recall=float(re),f1=float(f),tn=int(tn),fp=int(fp),fn=int(fn),tp=int(tp),false_positive_rate=float(fp/max(1,fp+tn)),false_negative_rate=float(fn/max(1,fn+tp)))
def rule(text): return int(any(x in text.lower() for x in CFG['rule_terms']))
def route(p,r,low,high):
    return 'block' if p>=high else ('pass' if p<=low and not r else 'review')
def main():
    start=time.perf_counter(); ART.mkdir(exist_ok=True)
    db=ART/'warehouse.sqlite'
    if db.exists(): db.unlink()
    con=sqlite3.connect(db); con.executescript((ROOT/'sql/schema.sql').read_text())
    groups=defaultdict(list); raw_counts={}; empty=0; rows=[]
    for name,split in [('train','train'),('dev','validation'),('test','test')]:
        source=list(csv.DictReader((ROOT/f'data/raw/{name}.csv').open(encoding='utf-8-sig'))); raw_counts[split]=len(source)
        for i,r in enumerate(source):
            text=r['TEXT']; norm=normalize(text); sid=f'cold-{name}-{i:05d}'
            if not norm or r['label'] not in ('0','1'):
                con.execute('INSERT INTO quality_exclusions VALUES(?,?,?)',(sid,'empty_or_invalid',None)); empty+=1; continue
            row=dict(id=sid,source_row=i,source_split=name,split=split,text=text,normalized_hash=sha(norm.encode()),source_label=int(r['label']),fine_label=int(r['fine-grained-label']) if 'fine-grained-label' in r else None,topic=r.get('topic',''))
            groups[row['normalized_hash']].append(row)
    conflict_groups=0; duplicate_rows=0; cross_groups=0
    priority={'test':0,'validation':1,'train':2}
    for group in groups.values():
        if len({r['split'] for r in group})>1: cross_groups+=1
        if len({r['source_label'] for r in group})>1:
            conflict_groups+=1
            con.executemany('INSERT INTO quality_exclusions VALUES(?,?,?)',[(r['id'],'conflicting_label',None) for r in group]);continue
        group.sort(key=lambda r:(priority[r['split']],r['source_row'])); keep=group[0]
        for r in group[1:]:
            duplicate_rows+=1; con.execute('INSERT INTO quality_exclusions VALUES(?,?,?)',(r['id'],'normalized_duplicate',keep['id']))
        fine=keep['fine_label']
        keep['policy_risk']={0:'其他非冒犯',1:'个人攻击',2:'群体攻击',3:'反偏见表达'}.get(fine,'冒犯（未细分）' if keep['source_label'] else '非冒犯（未细分）')
        rows.append(keep)
    cols=list(rows[0]);con.executemany('INSERT INTO samples('+','.join(cols)+') VALUES('+','.join('?'*len(cols))+')',[tuple(r[k] for k in cols) for r in rows]);con.commit()
    data={s:sorted([r for r in rows if r['split']==s],key=lambda r:r['id']) for s in priority}
    test_source=list(csv.DictReader((ROOT/'data/raw/test.csv').open(encoding='utf-8-sig')))
    fine_mismatch=sum(int(r['label']) != (int(r['fine-grained-label']) in (1,2)) for r in test_source)
    assert fine_mismatch==0,'Inconsistent fine label mapping'
    quality=dict(fine_binary_mismatches=fine_mismatch,missing_topic_rows=sum(not r['topic'] for r in rows),text_length_quantiles={str(k):float(np.percentile([len(r['text']) for r in rows],k)) for k in [0,50,95,100]},raw_counts=raw_counts,raw_total=sum(raw_counts.values()),retained_total=len(rows),retained_counts={s:len(v) for s,v in data.items()},invalid_rows=empty,conflict_groups=conflict_groups,duplicate_rows=duplicate_rows,cross_split_groups_before=cross_groups,cross_split_groups_after=0,labels={s:dict(Counter(r['source_label'] for r in v)) for s,v in data.items()},normalization='NFKC+lower+alphanumeric only; test > validation > train; conflicting binary groups removed',semantic_dedup=False)
    dump(ART/'quality.json',quality)
    split_manifest=[{k:r[k] for k in ('id','split','normalized_hash')} for r in rows];dump(ART/'split_manifest.json',split_manifest)
    xtrain=[r['text'] for r in data['train']]; ytrain=np.array([r['source_label'] for r in data['train']]);yval=np.array([r['source_label'] for r in data['validation']])
    vec=TfidfVectorizer(analyzer='char',ngram_range=(1,3),min_df=3,max_features=CFG['max_features'],sublinear_tf=True,dtype=np.float64)
    X=vec.fit_transform(xtrain); V=vec.transform([r['text'] for r in data['validation']]); search=[]; best=None
    with threadpool_limits(limits=1):
        for c in CFG['C_grid']:
            model=LogisticRegression(C=c,max_iter=500,random_state=CFG['seed'],solver='liblinear');model.fit(X,ytrain);pv=model.predict_proba(V)[:,1]
            for t in CFG['threshold_grid']:
                m=metrics(yval,pv>=t);search.append(dict(C=c,threshold=t,**m))
                if best is None or m['f1']>best[0]:best=(m['f1'],c,t,model,pv)
    _,c,threshold,model,pval=best
    # Select auto-decision thresholds only on validation, including rule override.
    rv=np.array([rule(r['text']) for r in data['validation']]);target=CFG['auto_precision_target']; min_n=CFG['minimum_validation_support']
    lows=[];highs=[]
    for t in np.linspace(0.01,0.99,99):
        safe=(pval<=t)&(rv==0);bad=pval>=t
        if safe.sum()>=min_n and (yval[safe]==0).mean()>=target:lows.append(float(t))
        if bad.sum()>=min_n and (yval[bad]==1).mean()>=target:highs.append(float(t))
    low=max(lows) if lows else -1.;high=min(highs) if highs else 2.
    if low>=high:low=min(low,threshold-0.01);high=max(high,threshold+0.01)
    policy=dict(version=CFG['policy_version'],C=c,binary_threshold=threshold,pass_threshold=low,block_threshold=high,selection='validation F1 for binary; max auto coverage at empirical 95% precision per auto action and >=50 validation support; rules prohibit auto-pass',validation_target=target)
    policy['validation_auto_pass_n']=int(((pval<=low)&(rv==0)).sum())
    policy['validation_auto_pass_precision']=float((yval[(pval<=low)&(rv==0)]==0).mean()) if low>=0 else None
    policy['validation_auto_block_n']=int((pval>=high).sum())
    policy['validation_auto_block_precision']=float(yval[pval>=high].mean()) if high<=1 else None
    dump(ART/'validation_search.json',search);dump(ART/'policy.json',policy)
    joblib.dump({'vectorizer':vec,'model':model,'policy':policy},ART/'model.joblib')
    # First test predictions occur only after selection is frozen above.
    test=data['test']; texts=[r['text'] for r in test];y=np.array([r['source_label'] for r in test]);t0=time.perf_counter()
    with threadpool_limits(limits=1): p=model.predict_proba(vec.transform(texts))[:,1]
    batch_ms=(time.perf_counter()-t0)*1000;rules=np.array([rule(t) for t in texts]);pred=(p>=threshold).astype(int)
    decisions=[route(float(pv),int(rv),low,high) for pv,rv in zip(p,rules)]
    summary={name:metrics(y,pr) for name,pr in [('rules',rules),('lightweight',pred)]}
    mask=np.array(decisions)!='review'; auto=np.array(decisions)=='block'
    summary['cascade_auto_only']=metrics(y[mask],auto[mask]) if mask.any() else None
    audit_path=ART/'adapter_audit.sqlite'
    if audit_path.exists():audit_path.unlink()
    adapter=ReviewAdapter(audit_path)
    cascade_results=[moderate(text,float(score),int(hit),policy,adapter) for text,score,hit in zip(texts,p,rules)]
    assert [v['decision'] for v in cascade_results]==decisions
    dump(ART/'cascade_decisions.json',[dict(sample_id=row['id'],**out) for row,out in zip(test,cascade_results)])
    adapter.db.close()
    counts=Counter(decisions);passed=np.array(decisions)=='pass';blocked=np.array(decisions)=='block'
    routing=dict(n=len(y),counts=dict(counts),rates={k:counts[k]/len(y) for k in ['pass','block','review']},auto_coverage=float(mask.mean()),auto_pass_offensive=int(y[passed].sum()),auto_block_safe=int((1-y[blocked]).sum()),pass_contamination=float(y[passed].mean()) if passed.any() else None,block_precision=float(y[blocked].mean()) if blocked.any() else None,leakage_over_all_offensive=int(y[passed].sum())/int(y.sum()),false_block_over_all_safe=int((1-y[blocked]).sum())/int((1-y).sum()),human_completed=0,actual_llm_calls=0,candidate_llm_requests=counts['review'],final_end_to_end_quality=None,release_gate='BLOCKED: test block precision below validation target; offline demo only')
    risks=[]
    for risk in sorted({r['policy_risk'] for r in test}):
        ix=np.array([r['policy_risk']==risk for r in test]);rr=metrics(y[ix],pred[ix]);rr.update(risk=risk,cascade_pass_offensive=int(y[ix&passed].sum()),cascade_block_safe=int((1-y[ix&blocked]).sum()),review=int((ix&~mask).sum()));
        # Fine labels are slices, not a four-class model: undefined metrics remain null.
        rr['precision']=None;rr['f1']=None
        if not y[ix].sum():rr['recall']=None;rr['false_negative_rate']=None
        if not (1-y[ix]).sum():rr['false_positive_rate']=None
        risks.append(rr)
    for i,r in enumerate(test):
        for name,sc,pr,dec in [('rules',float(rules[i]),int(rules[i]),'block' if rules[i] else 'pass'),('lightweight',float(p[i]),int(pred[i]),'block' if pred[i] else 'pass'),('cascade',float(p[i]),None if decisions[i]=='review' else int(auto[i]),decisions[i])]:
            con.execute('INSERT INTO predictions VALUES(?,?,?,?,?,?,?)',(r['id'],name,sc,pr,dec,int(rules[i]),CFG['policy_version']))
        if decisions[i]=='review':con.execute('INSERT INTO review_queue(sample_id,priority,reason,policy_version) VALUES(?,?,?,?)',(r['id'],float(p[i]),'rule_conflict' if rules[i] and p[i]<=low else 'uncertain',CFG['policy_version']))
    # Single item warm CPU timings, deterministic first 200 items, no network/human time.
    times=[]
    with threadpool_limits(limits=1):
        for text in texts[:200]:
            t0=time.perf_counter();score=model.predict_proba(vec.transform([text]))[0,1];route(score,rule(text),low,high);times.append((time.perf_counter()-t0)*1000)
    latency=dict(method='200 sequential single-item warm calls; vectorize + classifier + rules + route; perf_counter; one CPU thread; excludes startup, DB, network, human',n=len(times),p50_ms=float(np.percentile(times,50)),p95_ms=float(np.percentile(times,95)),batch_total_ms=batch_ms,batch_amortized_ms=batch_ms/len(y),actual_llm_latency_ms=None,actual_end_to_end_latency_ms=None)
    # Deterministic stratified bootstrap for the fixed lightweight test predictions.
    rng=np.random.default_rng(CFG['seed']);boots=[];pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0)
    for _ in range(400):
        ix=np.r_[rng.choice(pos,len(pos)),rng.choice(neg,len(neg))];boots.append(metrics(y[ix],pred[ix])['f1'])
    ci=[float(v) for v in np.percentile(boots,[2.5,97.5])]
    cost=CFG['cost_assumptions'];estimate=counts['review']*(cost['input_tokens']*cost['input_price_per_million']+cost['output_tokens']*cost['output_price_per_million'])/1e6
    env=dict(python=sys.version,sklearn=sklearn.__version__,numpy=np.__version__,platform=platform.platform(),machine=platform.machine(),processor=platform.processor(),cpu_count=os.cpu_count(),cpu_threads_used=1)
    result=dict(dataset='COLD 中文冒犯评论',seed=CFG['seed'],policy=policy,quality=quality,metrics=summary,routing=routing,risk_metrics=risks,latency=latency,lightweight_f1_bootstrap95=ci,cost=dict(actual_api_spend=0,estimated_scenario_spend=estimate,assumptions=cost,formula='candidate_requests * (input_tokens * input_price + output_tokens * output_price) / 1e6'),environment=env,duration_seconds=time.perf_counter()-start)
    con.execute('INSERT INTO experiment_metadata VALUES(?,?)',('policy',json.dumps(policy)));con.commit()
    queries=(ROOT/'sql/analysis.sql').read_text();sql_results={}
    con.row_factory=sqlite3.Row
    for block in queries.split('-- name: ')[1:]:
        name,q=block.split('\n',1);sql_results[name]=[dict(r) for r in con.execute(q)]
    dump(ART/'sql_results.json',sql_results);dump(ART/'results.json',result)
    with (ART/'predictions.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['sample_id','truth','fine_label','score','rule_prediction','model_prediction','route'])
        for i,r in enumerate(test):w.writerow([r['id'],int(y[i]),r['fine_label'],float(p[i]),int(rules[i]),int(pred[i]),decisions[i]])
    # Public-safe dashboard data contains no source text.
    errors=[dict(id=r['id'],truth=int(y[i]),prediction=int(pred[i]),risk=r['policy_risk'],score=round(float(p[i]),4),route=decisions[i]) for i,r in enumerate(test) if pred[i]!=y[i]]
    dump(ROOT/'dashboard/data.json',dict(**result,sql=sql_results,errors=errors))
    con.close();print(json.dumps(dict(metrics=summary,routing=routing,policy=policy,quality=quality),ensure_ascii=False,indent=2))
if __name__=='__main__': main()
