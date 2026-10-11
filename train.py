"""Research-only supervised learning on independently verified historical shortage events.

Labels are 90-calendar-day benchmark excess returns. Prices must not enter
features unless known at event public availability time. No trained model is
produced when there are insufficient resolved and independently verified cases.
"""
from __future__ import annotations
import datetime as dt, json, math, statistics
from pathlib import Path
from engine import evidence_events,clean_prices,indicators,iso

COST_BPS=60;MIN_ROWS=80;EMBARGO_DAYS=90

def rows_from_events(raw,evs,benchmark='ACWI'):
    p=clean_prices(raw);bm={b['date']:b for b in p.get(benchmark,[])}
    records=[];seen=set()
    for e in sorted(evs,key=lambda x:(x['available'],x['ticker'],x['event_id'])):
        if e['event_id'] in seen:continue
        seen.add(e['event_id'])
        bars=p.get(e['ticker'],[])
        available=e['available']
        # Historical report timing is often day-granularity only: use PRIOR session bar.
        pre=[i for i,b in enumerate(bars) if b['date']<available]
        nexts=[i for i,b in enumerate(bars) if b['date']>available]
        if not pre or not nexts:continue
        i=pre[-1];entry=nexts[0]
        feat=indicators(bars,i,bm,{'fast_sma':20,'slow_sma':50,'rsi_min':40,'rsi_max':80,
                                'min_volume_ratio':1,'min_relative_strength_20d':0,
                                'breakout_days':20,'max_prior_excess_30d':10,'min_signal_count':1,
                                'require_breakout':False})
        if feat is None or feat['relative_strength_20d'] is None:continue
        target=bars[entry]['date']+dt.timedelta(days=90)
        exits=[idx for idx,b in enumerate(bars) if b['date']>=target]
        if not exits:continue
        k=exits[0]
        if (bars[k]['date']-target).days>7:continue
        startday=bars[entry]['date'];endday=bars[k]['date']
        if startday not in bm or endday not in bm:continue
        rs=bars[k]['close']/bars[entry]['open']-1
        rb=bm[endday]['close']/bm[startday]['open']-1
        excess=rs-rb-COST_BPS/10000
        lab=1 if excess>0.05 else 0 if excess<=0 else None
        records.append({'event_id':e['event_id'],'sector':e.get('theme') or 'unknown',
                        'ticker':e['ticker'],'signal_day':available.isoformat(),
                        'entry_day':startday.isoformat(),'outcome_known_day':endday.isoformat(),
                        'excess_pct':round(excess*100,3),'label':lab,
                        'features':{'rsi':feat['rsi'],'volume_ratio':feat['volume_ratio'],
                                    'relative_strength_20d':feat['relative_strength_20d'],
                                    'prior_excess_30d':feat['prior_excess_30d'],
                                    'breakout':int(feat['breakout']),
                                    'sma_fast_over_slow':int(feat['sma_fast']>feat['sma_slow'])},
                        'source_url':e.get('source_url'),'evidence_verified':True})
    return records

def train_model(rows):
    good=sorted([r for r in rows if r['label'] is not None],key=lambda r:(r['signal_day'],r['event_id']))
    pos=sum(x['label']==1 for x in good);neg=sum(x['label']==0 for x in good)
    result={'status':'LOCKED','verified_resolved_events':len(good),'winners':pos,'losers':neg,
            'sector_count':len({x['sector'] for x in good}),'minimum_events':MIN_ROWS,
            'warning':'Price labels measure benchmark-relative outcomes, not whether shortages caused returns.'}
    if len(good)<MIN_ROWS or pos<20 or neg<20 or result['sector_count']<3:
        result['reason']='Need 80+ dated independent episodes, >=20 wins and >=20 losses across >=3 sectors.'
        return result
    split=int(len(good)*0.8);test=good[split:];cut=iso(test[0]['signal_day'])
    train=[r for r in good[:split] if iso(r['outcome_known_day'])<cut-dt.timedelta(days=EMBARGO_DAYS)]
    result.update(train_events=len(train),holdout_events=len(test))
    if len(train)<50 or len({x['label'] for x in train})<2 or len({x['label'] for x in test})<2:
        result['reason']='90-day embargoed chronological holdout has insufficient events or classes.'
        return result
    try:
        import numpy as np
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score,brier_score_loss
    except ImportError as ex:
        result['reason']='Install numpy and scikit-learn for training: '+str(ex)
        return result
    keys=['rsi','volume_ratio','relative_strength_20d','prior_excess_30d','breakout','sma_fast_over_slow']
    def xy(src):
        return np.array([[float(r['features'].get(k) or 0) for k in keys] for r in src]),np.array([r['label'] for r in src])
    xtr,ytr=xy(train);xte,yte=xy(test)
    model=make_pipeline(StandardScaler(),LogisticRegression(C=0.2,max_iter=500,class_weight=None))
    model.fit(xtr,ytr)
    prob=model.predict_proba(xte)[:,1]
    baseline=sum(ytr)/len(ytr)
    brier=float(brier_score_loss(yte,prob));base=float(brier_score_loss(yte,[baseline]*len(yte)))
    auc=float(roc_auc_score(yte,prob))
    # Outperformance over constant base-rate only. NOT a portfolio-performance result.
    result.update(status='RESEARCH_HOLDOUT_EVALUATED',holdout_auc=round(auc,4),
                  holdout_brier=round(brier,4),baseline_brier=round(base,4),
                  beats_base_rate_brier=brier<base,feature_names=keys,
                  model_is_not_deployed=True,
                  reason='Research evaluation only. Multiple independent forward walk-forward cohorts still needed before deployment.')
    return result
