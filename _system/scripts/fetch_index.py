#!/usr/bin/env python3
"""获取指数行情的独立脚本，带 5 秒超时保护"""
import tushare as ts, json, sys
ts.set_token(open('/Users/shisan/.openclaw/workspace/data/tushare_token.txt').read().strip())
pro = ts.pro_api()
results = {}
for tc in ['000001.SH','399001.SZ','399006.SZ','000688.SH']:
    try:
        df = pro.index_daily(ts_code=tc, start_date='20260603', end_date='20260603')
        if df is not None and len(df) > 0:
            results[tc] = {'close': float(df.iloc[0]['close']), 'pct_chg': float(df.iloc[0]['pct_chg'])}
    except:
        pass
json.dump(results, open('/tmp/index_data.json','w'))
print(f'fetched {len(results)} indices')
