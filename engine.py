"""Supply-independent point-in-time strategy backtester. Standard library only.

Rules are evaluated on a COMPLETED daily bar. Entries use the NEXT session's
adjusted open. Portfolio and liquidity simulations are exploratory research,
not executable orders or a claim of historical shortage detection.
"""
from __future__ import annotations
import csv, datetime as dt, json, math, statistics
from pathlib import Path
from dataclasses import dataclass

DEFAULT_CONFIG = {
    'name': 'Trend Breakout', 'mode': 'technical',
    'symbols': ['MU', 'LITE', 'ETN', 'FCX', 'ZIM'], 'benchmark': 'ACWI',
    'start': '2020-01-01',
    'rules': {'fast_sma': 20, 'slow_sma': 50, 'rsi_min': 50, 'rsi_max': 75,
              'breakout_days': 20, 'min_volume_ratio': 1.2,
              'min_relative_strength_20d': 0.0, 'max_prior_excess_30d': 0.30,
              'min_signal_count': 5, 'require_breakout': True},
    'trade': {'hold_sessions': 30, 'stop_atr': 2.5, 'take_atr': 5.0,
              'round_trip_cost_bps': 60, 'max_concurrent': 3},
    'evidence': {'lookback_days': 14}
}

def iso(s):
    if not s: return None
    return dt.date.fromisoformat(str(s)[:10])

def valid_config(cfg):
    if cfg.get('mode') not in ('technical', 'verified_evidence'):
        raise ValueError('mode must be technical or verified_evidence')
    rules, trade = cfg['rules'], cfg['trade']
    for k in ('fast_sma','slow_sma','breakout_days','min_signal_count'):
        if not 1 <= int(rules[k]) <= 250: raise ValueError('invalid '+k)
    if not 1 <= int(rules['min_signal_count']) <= 6:raise ValueError('min_signal_count must be 1..6')
    if rules['fast_sma']>=rules['slow_sma']:raise ValueError('Fast SMA must be below slow SMA')
    if not (0 <= float(rules['rsi_min']) < float(rules['rsi_max']) <= 100):raise ValueError('invalid RSI limits')
    if not 1 <= int(trade['hold_sessions']) <= 252:raise ValueError('invalid holding duration')
    if not 1 <= int(trade['max_concurrent']) <= 50:raise ValueError('invalid position count')
    if not 0 <= float(trade['round_trip_cost_bps']) <= 1000:raise ValueError('invalid cost')
    if not 0 <= float(trade['stop_atr']) <= 20 or not 0<=float(trade['take_atr'])<=30:raise ValueError('invalid ATR multiplier')
    if not cfg.get('symbols') or not cfg.get('benchmark'): raise ValueError('missing symbols/benchmark')
    return cfg

def clean_prices(raw):
    """Convert market-cache {symbol: [{date,open,high,low,close,volume}]} to clean bars."""
    out={}
    for symbol,items in raw.items():
        rows=[]
        for item in items:
            try:
                day=iso(item['date']);b={k:float(item[k]) for k in ('open','high','low','close','volume')}
                if all(math.isfinite(v) for v in b.values()) and min(b['open'],b['high'],b['low'],b['close'])>0 and b['volume']>=0:
                    rows.append(dict(date=day,**b))
            except (TypeError,ValueError,KeyError):continue
        out[symbol]=sorted({r['date']:r for r in rows}.values(), key=lambda r:r['date'])
    return out

def average(values):
    return sum(values)/len(values) if values else None

def rsi(closes, idx, period=14):
    if idx<period:return None
    changes=[closes[j]-closes[j-1] for j in range(idx-period+1,idx+1)]
    gains=sum(max(d,0) for d in changes)/period
    losses=sum(max(-d,0) for d in changes)/period
    return 100 if losses==0 else 100-100/(1+gains/losses)

def atr(bars,idx,period=14):
    if idx<period:return None
    trs=[]
    for j in range(idx-period+1,idx+1):
        b=bars[j];prev=bars[j-1]['close'];trs.append(max(b['high']-b['low'],abs(b['high']-prev),abs(b['low']-prev)))
    return average(trs)

def evidence_events(path):
    """Load verified independent events. Unverified or ambiguous timestamps excluded."""
    events=[]
    if not Path(path).exists(): return events
    with open(path,encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            if str(row.get('verified','')).strip().lower()!='true':continue
            if not row.get('source_url','').startswith(('https://','http://')):continue
            if not row.get('ticker','') or not row.get('event_id',''):continue
            available=iso(row.get('publicly_available_at'))
            published=iso(row.get('source_published_at'))
            if not available or not published or published>available:continue
            events.append({**row,'available':available,'published':published})
    return events

def allowed_evidence(events,ticker,day,lookback):
    return [e for e in events if e['ticker']==ticker and dt.timedelta(0)<=day-e['available']<=dt.timedelta(days=int(lookback))]

def indicators(bars,index,benchmark_by_date,rules):
    fast=int(rules['fast_sma']);slow=int(rules['slow_sma']);window=int(rules['breakout_days'])
    if index<max(slow,window,30,20,14):return None
    now=bars[index];close=now['close'];history=bars[:index+1]
    dates=[row['date'] for row in history]
    closes=[row['close'] for row in history]
    smf=average(closes[-fast:]);sms=average(closes[-slow:])
    r=rsi(closes,index);a=atr(bars,index)
    past_vol=[b['volume'] for b in bars[index-20:index]]
    avg_vol=average(past_vol)
    vol_ratio=now['volume']/avg_vol if avg_vol and avg_vol>0 else None
    breakout=close>max(closes[index-window:index])
    prev=bars[index-20]
    if now['date'] in benchmark_by_date and prev['date'] in benchmark_by_date:
        bm=benchmark_by_date
        rs=close/prev['close']-bm[now['date']]['close']/bm[prev['date']]['close']
    else:rs=None
    prev30=bars[index-30]
    prior_excess=close/prev30['close']-bm[now['date']]['close']/bm[prev30['date']]['close'] if now['date'] in benchmark_by_date and prev30['date'] in benchmark_by_date else None
    gates=[close>smf,smf>sms,rules['rsi_min']<=r<=rules['rsi_max'],vol_ratio is not None and vol_ratio>=rules['min_volume_ratio'],rs is not None and rs>=rules['min_relative_strength_20d'],breakout]
    return {'sma_fast':round(smf,4),'sma_slow':round(sms,4),'rsi':round(r,2),'atr':round(a,4),
            'volume_ratio':round(vol_ratio,3) if vol_ratio is not None else None,
            'relative_strength_20d':round(rs,5) if rs is not None else None,
            'prior_excess_30d':round(prior_excess,5) if prior_excess is not None else None,
            'breakout':breakout,'score':sum(gates),'gates':gates}

def signal_ok(feats,rules):
    if feats is None or feats['relative_strength_20d'] is None or feats['prior_excess_30d'] is None:return False
    if feats['prior_excess_30d']>rules['max_prior_excess_30d']:return False
    if rules['require_breakout'] and not feats['breakout']:return False
    return feats['score']>=int(rules['min_signal_count'])

def exit_trade(bars,entry_index,feat,trade):
    """Return exit index, exit px and reason; conservative stop-first on same candle."""
    entry=bars[entry_index]['open'];at=feat['atr'];sl=entry-at*float(trade['stop_atr']) if trade['stop_atr'] else None
    tp=entry+at*float(trade['take_atr']) if trade['take_atr'] else None
    end=min(len(bars)-1,entry_index+int(trade['hold_sessions'])-1)
    for j in range(entry_index,end+1):
        b=bars[j]
        if sl is not None and b['open']<=sl:return j,b['open'],'GAP_STOP'
        if tp is not None and b['open']>=tp:return j,b['open'],'GAP_TARGET'
        if sl is not None and b['low']<=sl:return j,sl,'STOP'
        if tp is not None and b['high']>=tp:return j,tp,'TARGET'
    return end,bars[end]['close'],'TIME'

def backtest(raw,config,verified_events=None):
    cfg=valid_config(config)
    prices=clean_prices(raw);bm={row['date']:row for row in prices.get(cfg['benchmark'],[])}
    trade=cfg['trade'];rules=cfg['rules'];events=verified_events or []
    starts=iso(cfg.get('start')) or dt.date(1900,1,1)
    ends=iso(cfg.get('end')) or dt.date(2999,12,31)
    opportunities=[];dropped={'no_verified_evidence':0,'insufficient_bars_or_chart':0,'benchmark_missing':0}
    for ticker in cfg['symbols']:
        bars=prices.get(ticker,[])
        for i in range(len(bars)-1):
            day=bars[i]['date']
            if day<starts or day>ends:continue
            if cfg['mode']=='verified_evidence' and not allowed_evidence(events,ticker,day,cfg['evidence']['lookback_days']):
                dropped['no_verified_evidence']+=1;continue
            feat=indicators(bars,i,bm,rules)
            if not signal_ok(feat,rules):continue
            entry_index=i+1;entryday=bars[entry_index]['date']
            if not bm.get(entryday):dropped['benchmark_missing']+=1;continue
            end_index,exitpx,reason=exit_trade(bars,entry_index,feat,trade)
            exitday=bars[end_index]['date']
            if exitday not in bm:dropped['benchmark_missing']+=1;continue
            entrypx=bars[entry_index]['open'];net=exitpx/entrypx-1-trade['round_trip_cost_bps']/10000
            br=bm[exitday]['close']/bm[entryday]['open']-1
            opportunities.append({'ticker':ticker,'signal_date':day.isoformat(),'entry_date':entryday.isoformat(),
                                  'exit_date':exitday.isoformat(),'entry_px':round(entrypx,4), 'exit_px':round(exitpx,4),
                                  'exit_reason':reason,'net_return_pct':round(net*100,3),
                                  'benchmark_return_pct':round(br*100,3),'excess_pct':round((net-br)*100,3),
                                  'score':feat['score'],'features':feat,
                                  'evidence_ids':[e['event_id'] for e in allowed_evidence(events,ticker,day,cfg['evidence']['lookback_days'])] if cfg['mode']=='verified_evidence' else []})
    # Evaluate in chronological order, prohibit overlapping same-stock positions and cap live positions.
    opportunities.sort(key=lambda x:(x['entry_date'],x['ticker'],x['signal_date']))
    kept=[]
    for cand in opportunities:
        open_positions=[t for t in kept if t['entry_date']<=cand['entry_date']<=t['exit_date']]
        if any(t['ticker']==cand['ticker'] for t in open_positions):continue
        if len(open_positions)>=int(trade['max_concurrent']):continue
        kept.append(cand)
    vals=[t['net_return_pct'] for t in kept];excess=[t['excess_pct'] for t in kept]
    n=len(kept)
    stats={'trades':n,'win_rate_pct':round(100*sum(x>0 for x in vals)/n,2) if n else None,
           'mean_trade_pct':round(average(vals),3) if n else None,
           'mean_excess_pct':round(average(excess),3) if n else None,
           'median_excess_pct':round(statistics.median(excess),3) if n else None,
           'fraction_beating_benchmark':round(100*sum(x>0 for x in excess)/n,2) if n else None,
           'note':'Trade-average metrics, not portfolio CAGR or risk-adjusted alpha. Signals are retrospective simulation; slippage and news timestamps may differ in practice.'}
    return {'config':cfg,'stats':stats,'trades':kept,'rejected_counts':dropped,
            'evidence_events_loaded':len(events),'chart_data_symbol_count':len(prices),'notes':[
            'No lookahead: completed signal close, entry next open; stop-first conservative intraday tie.',
            'Market data is survivorship-biased if symbols are selected from today; compare against proper historical universe.',
            'Verified evidence mode requires explicitly verified and publicly dated events; no events means no evidence trades.',
            'This is a research backtest, not a proof of profitability or a live order.']}
