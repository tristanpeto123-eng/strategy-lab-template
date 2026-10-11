import datetime as dt,json,sys,tempfile,unittest,csv
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from engine import backtest,valid_config,indicators,clean_prices,evidence_events,allowed_evidence
from train import train_model

class BacktestTests(unittest.TestCase):
    def setUp(self):
        base=dt.date(2025,1,1)
        # Stable weekday bars with controlled rising stock and benchmark series.
        ds=[base+dt.timedelta(days=i) for i in range(550) if (base+dt.timedelta(days=i)).weekday()<5]
        self.raw={}
        for sym,slope in [('MU',0.45),('ACWI',0.12)]:
            rows=[]
            for i,d in enumerate(ds):
                px=100+i*slope
                rows.append({'date':d.isoformat(),'open':px-0.12,'high':px+0.6,'low':px-0.5,'close':px,'volume':1000+(800 if i%7==0 else 0)})
            self.raw[sym]=rows
        self.cfg={'name':'Test','mode':'technical','symbols':['MU'],'benchmark':'ACWI','start':'2025-01-01',
                  'rules':{'fast_sma':10,'slow_sma':30,'rsi_min':10,'rsi_max':100,
                           'breakout_days':5,'min_volume_ratio':0.5,'min_relative_strength_20d':0,
                           'max_prior_excess_30d':1.0,'min_signal_count':4,'require_breakout':True},
                  'trade':{'hold_sessions':10,'stop_atr':0,'take_atr':0,'round_trip_cost_bps':60,'max_concurrent':1},
                  'evidence':{'lookback_days':14}}
    def test_charts_produce_valid_signals(self):
        result=backtest(self.raw,self.cfg)
        self.assertGreater(result['stats']['trades'],0)
        for t in result['trades']:
            self.assertLess(t['signal_date'],t['entry_date'])
            self.assertLessEqual(t['entry_date'],t['exit_date'])
    def test_evidence_mode_without_verification_has_no_trades(self):
        self.cfg['mode']='verified_evidence'
        r=backtest(self.raw,self.cfg,[])
        self.assertEqual(0,r['stats']['trades'])
    def test_event_postdate_cannot_enter_earlier(self):
        self.cfg['mode']='verified_evidence'
        event={'event_id':'x','ticker':'MU','theme':'memory','available':dt.date(2025,10,1),'published':dt.date(2025,9,30)}
        self.assertFalse(allowed_evidence([event],'MU',dt.date(2025,9,29),14))
        self.assertTrue(allowed_evidence([event],'MU',dt.date(2025,10,2),14))
    def test_event_verification_rejects_missing_source_and_bad_times(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'events.csv'
            with path.open('w') as f:
                f.write('event_id,theme,ticker,source_url,source_published_at,publicly_available_at,verified\n')
                f.write('a,memory,MU,https://example.org/1,2025-01-01,2025-01-02,true\n')
                f.write('b,memory,MU,https://example.org/2,2025-01-03,2025-01-02,true\n')
                f.write('c,memory,MU,https://example.org/3,2025-01-01,2025-01-02,false\n')
            e=evidence_events(path)
            self.assertEqual(len(e),1)
            self.assertEqual(e[0]['event_id'],'a')
    def test_no_future_price_changes_past_indicators(self):
        p=clean_prices(self.raw)
        bm={b['date']:b for b in p['ACWI']}
        base=indicators(p['MU'],110,bm,self.cfg['rules'])
        for j in range(111,len(p['MU'])):
            p['MU'][j]['close']*=3
        new=indicators(p['MU'],110,bm,self.cfg['rules'])
        self.assertEqual(base,new)
    def test_model_locked_without_verified_cases(self):
        self.assertEqual(train_model([])['status'],'LOCKED')
    def test_cost_reduces_net_returns(self):
        r1=backtest(self.raw,self.cfg)['trades']
        self.cfg['trade']['round_trip_cost_bps']=100
        r2=backtest(self.raw,self.cfg)['trades']
        self.assertEqual(len(r1),len(r2))
        self.assertAlmostEqual(r1[0]['net_return_pct']-r2[0]['net_return_pct'],.4,places=2)
    def test_entry_next_bar(self):
        r=backtest(self.raw,self.cfg)['trades']
        self.assertTrue(r)
        for t in r:self.assertNotEqual(t['signal_date'],t['entry_date'])
    def test_rejects_invalid_parameters(self):
        self.cfg['rules']['fast_sma']=50
        with self.assertRaises(ValueError):valid_config(self.cfg)

if __name__=='__main__':unittest.main()
