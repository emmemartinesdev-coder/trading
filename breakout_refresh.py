#!/usr/bin/env python3
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import json

# Solo i top 30 titoli S&P 500
tickers = ['AAPL','MSFT','GOOGL','AMZN','NVDA','META','TSLA','UNH','JNJ','JPM','BAC','V','MA','WMT','PG','HD','DIS','NFLX','ADBE','CRM','INTC','AMD','QCOM','AVGO','ORCL','CSCO','TXN','IBM','NOW']

def calc_atr(high, low, close, p=14):
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(p).mean()

results = []

print("Analizzando breakout S&P 500...")

for t in tickers:
    try:
        s = yf.Ticker(t)
        h = s.history('3mo', interval='1d')
        if len(h) < 30: continue
        
        h['atr'] = calc_atr(h['High'], h['Low'], h['Close'])
        h['vol_ma'] = h['Volume'].rolling(20).mean()
        
        c = h.iloc[-1]
        vol_ratio = c['Volume'] / h['vol_ma'].iloc[-1] if h['vol_ma'].iloc[-1] else 1
        
        recent_high = h['High'].tail(20).max()
        dist_high = (recent_high - c['Close']) / recent_high * 100
        
        target = s.info.get('targetMeanPrice', 0)
        upside = ((target - c['Close']) / c['Close']) * 100 if target else 0
        
        rr = upside / (c['atr'] * 0.5) if c['atr'] else 0
        
        results.append({
            'ticker': t,
            'name': s.info.get('shortName', t),
            'price': round(c['Close'], 2),
            'change': round((c['Close'] - h['Open'].iloc[-1])/h['Open'].iloc[-1]*100, 2),
            'vol_ratio': round(vol_ratio, 2),
            'atr': round(c['atr'], 2),
            'dist_high': round(dist_high, 2),
            'upside': round(upside, 2),
            'rr': round(rr, 2),
            'near_high': bool(dist_high < 3),
            'analyst_rating': s.info.get('recommendationKey', 'N/A')
        })
        print(f"  {t}: OK")
    except Exception as e:
        print(f"  {t}: Errore - {str(e)[:30]}")
        continue

# Ordina per RR ratio
results.sort(key=lambda x: x['rr'], reverse=True)

# Salva JSON
with open('breakout_refresh.json', 'w') as f:
    json.dump(results, f, indent=2)

print()
print('='*75)
print('RISK-REWARD BREAKOUT AGGIORNATO')
print(datetime.now().strftime('%Y-%m-%d %H:%M UTC'))
print('='*75)
print()

print("📊 TOP 15 PER RAPPORTO RISCHIO-RENDIMENTO:")
for i,r in enumerate(results[:15], 1):
    emoji = '🚀' if r['near_high'] else '📊'
    print(f"{i:2}. {r['ticker']:6} | Price: ${r['price']:7.2f} | Change: {r['change']:+6.2f}% | Vol: {r['vol_ratio']:.2f}x | Upside: {r['upside']:+6.1f}% | RR: {r['rr']:5.1f} {emoji}")

print()
print("🔥 TOP PER VOLUME (breakout confermato):")
vol_sorted = sorted(results, key=lambda x: x['vol_ratio'], reverse=True)
for r in vol_sorted[:5]:
    print(f"  {r['ticker']}: Vol {r['vol_ratio']}x, Upside {r['upside']}%, RR {r['rr']}")

print()
print("🎯 TOP NEAR HIGH (breakout imminente):")
nh_sorted = [r for r in results if r['near_high']]
nh_sorted.sort(key=lambda x: x['dist_high'])
for r in nh_sorted[:5]:
    print(f"  {r['ticker']}: Dist {r['dist_high']}% from high, Vol {r['vol_ratio']}x, Upside {r['upside']}%")