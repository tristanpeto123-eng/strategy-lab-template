#!/usr/bin/env python3
"""GitHub Actions CLI entrypoint. Writes research results; no broker permissions."""
import argparse,datetime as dt,json,sys,traceback
from pathlib import Path
from engine import backtest,valid_config,evidence_events
from train import rows_from_events,train_model
ROOT=Path(__file__).resolve().parent

def download_prices(symbols,start,end):
    import yfinance as yf
    start_date=dt.date.fromisoformat(start)-dt.timedelta(days=450)
    end_date=dt.date.fromisoformat(end)+dt.timedelta(days=3)
    output={};errors=[]
    for sym in sorted(set(symbols)):
        try:
            hist=yf.Ticker(sym).history(start=start_date.isoformat(),end=end_date.isoformat(),interval='1d',auto_adjust=True,actions=False,timeout=25)
            if hist.empty:raise ValueError('No returned daily history')
            rows=[]
            for d,r in hist.iterrows():
                try:
                    z={'date':d.date().isoformat(),'open':float(r['Open']),'high':float(r['High']),
                       'low':float(r['Low']),'close':float(r['Close']),'volume':float(r['Volume'])}
                    if all(v==v for v in list(z.values())[1:]):rows.append(z)
                except (KeyError,ValueError,TypeError):continue
            if len(rows)<75:raise ValueError(f'Insufficient returned daily bars: {len(rows)}')
            output[sym]=rows
        except Exception as e:errors.append(f'{sym}: {type(e).__name__}: {str(e)[:180]}')
    return output,errors

def run(args):
    config=valid_config(json.loads((ROOT/args.strategy).read_text()))
    end=args.end or dt.date.today().isoformat();config['end']=end
    candidates=[]
    for p in sorted((ROOT/'strategies').glob('*.json')):
        try:
            cfg=valid_config(json.loads(p.read_text()))
            cfg['end']=end;candidates.append((str(p.relative_to(ROOT)),cfg))
        except (ValueError,KeyError,TypeError) as exc:
            print('SKIPPED invalid preset',p,exc,file=sys.stderr)
    if args.strategy not in [name for name,_ in candidates]: candidates.append((args.strategy,config))
    evs=evidence_events(ROOT/'data/verified_events.csv')
    if args.prices:
        cache=json.loads(Path(args.prices).read_text());errors=[]
    else:
        cache,errors=download_prices(sorted(set(sym for _,c in candidates for sym in c['symbols']+[c['benchmark']])),min(c['start'] for _,c in candidates),end)
    if config['benchmark'] not in cache:
        raise RuntimeError('Benchmark unavailable: '+repr(errors))
    (ROOT/'data').mkdir(exist_ok=True)
    (ROOT/'results').mkdir(exist_ok=True)
    (ROOT/'data/chart_cache.json').write_text(json.dumps(cache,separators=(',',':'))+'\n')
    result=backtest(cache,config,evs)
    # Split on time, never select a winning rule based on the unseen holdout.
    # Technical-only comparisons are a descriptive baseline, not verified shortage research.
    leaderboard=[]
    (ROOT/'results'/'strategies').mkdir(parents=True,exist_ok=True)
    for name,cfg in candidates:
        res=backtest(cache,cfg,evs)
        trades=res['trades']
        start_day=dt.date.fromisoformat(cfg['start'])
        end_day=dt.date.fromisoformat(end)
        holdout_start=start_day+dt.timedelta(days=int((end_day-start_day).days*.8))
        embargo_start=holdout_start-dt.timedelta(days=90)
        insample=[x for x in trades if dt.date.fromisoformat(x['exit_date'])<embargo_start]
        holdout=[x for x in trades if dt.date.fromisoformat(x['entry_date'])>=holdout_start]
        def mean_ex(xs):return round(sum(t['excess_pct'] for t in xs)/len(xs),3) if xs else None
        record={'strategy_file':name,'name':cfg['name'],'mode':cfg['mode'],
                'all_trades':len(trades),'in_sample_trades':len(insample),'holdout_trades':len(holdout),
                'mean_excess_insample_pct':mean_ex(insample),'mean_excess_holdout_pct':mean_ex(holdout),
                'holdout_start':holdout_start.isoformat(),'embargo_days':90,
                'do_not_select_using_holdout':True}
        leaderboard.append(record)
        slug=Path(name).stem.replace('/','_')
        (ROOT/'results'/'strategies'/f'{slug}.json').write_text(json.dumps(res,indent=2)+'\n')
    (ROOT/'results'/'leaderboard.json').write_text(json.dumps({'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),
       'strategies':leaderboard,'warning':'In-sample performance is not a forward forecast; 90-day embargo is applied to this descriptive holdout.'},indent=2)+'\n')
    case_rows=rows_from_events(cache,evs,config['benchmark'])
    trained=train_model(case_rows)
    status={'generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
            'strategy_file':args.strategy,'price_provider':'Yahoo Finance via yfinance; free unofficial data feed',
            'market_data_errors':errors,'available_symbols':sorted(cache),
            'verified_events_loaded':len(evs),'training_model':trained['status'],
            'mode':config['mode'],'warning':'No live trades; technical chart simulation is not proof of supply causality.'}
    (ROOT/'results/latest.json').write_text(json.dumps(result,indent=2)+'\n')
    (ROOT/'results/model_status.json').write_text(json.dumps(trained,indent=2)+'\n')
    (ROOT/'results/status.json').write_text(json.dumps(status,indent=2)+'\n')
    print(json.dumps({'status':status,'trades':result['stats']['trades']},indent=2))
    if errors: print('WARNING: Some symbols missing, verify completeness',file=sys.stderr)
    if not args.prices and errors:
        raise RuntimeError('Partial price download: do not treat results as full backtest. '+repr(errors))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--strategy',default='strategies/trend_breakout.json');p.add_argument('--end');p.add_argument('--prices',help='Offline fixture JSON instead of download');args=p.parse_args()
    try:run(args)
    except Exception as exc:
        (ROOT/'results').mkdir(exist_ok=True)
        (ROOT/'results/status.json').write_text(json.dumps({'status':'ERROR','error':str(exc),'generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()})+'\n')
        print('ERROR:',exc,file=sys.stderr);sys.exit(1)
