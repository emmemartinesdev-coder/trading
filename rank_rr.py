#!/usr/bin/env python3
import json

data = json.load(open('breakout_sp500_results.json'))

# Calcolo rapporto rischio-ritorno
risk_reward = []

for r in data:
    risk_proxy = r['atr'] * 0.5  # Attributo di rischio
    upside = r['upside_potential'] if r['upside_potential'] else 0
    rr_ratio = (upside - risk_proxy * 0.2) / risk_proxy if risk_proxy > 0 else 0
    risk_reward.append((r, rr_ratio))

# Ranking per RR ratio
risk_reward.sort(key=lambda x: x[1], reverse=True)

print('=' * 70)
print('RISK-REWARD RANKING - TOP BREAKOUT')
print('=' * 70)
print(f'\nGenerale RNG vs (ATR * 0.5) Ratio por più alto')

print('\nTop 15 RISK-REWARD:')
for i, (r, score) in enumerate(risk_reward[:15], 1):
    print(f'{i}) {r["ticker"]} - RR Ratio: {score:.2f} | Score: {r["breakout_score"]}/100 | Upside: +{r["upside_potential"] or 0}%')
    print(f'   Trend: {"🎯 Near High" if r["near_resistance"] == "True" else " "} | Vol: {r["volume_ratio"]}x | Rating: {r["analyst_rating"]}')

print('\n\n')

# Segmenti
tech = [e for e in data if e['ticker'] in ['AAPL','MSFT','GOOGL','AMZN','META','NVDA','TSLA','AVGO','ORCL']]
health = [e for e in data if e['ticker'] in ['UNH','JNJ','PFE','ABBV','BMY','MRK','GILD','MRNA']]
finance = [e for e in data if e['ticker'] in ['JPM','BAC','MS','GS','AXP','C','BK']]

segments = [
    ('TECHNOLOGY', tech),
    ('HEALTHCARE', health),
    ('FINANCE', finance)
]

for cat, group in segments:
    if group:
        sorted_g = sorted(group, key=lambda x: x['upside_potential'] if x['upside_potential'] else 0, reverse=True)
        best = sorted_g[0]
        print(f'\n{cat.upper()}: {best["ticker"]}')
        print(f'Upside: +{best["upside_potential"] or 0}% vs Target | Rating: {best["analyst_rating"]} | Vol: {best["volume_ratio"]}x')

print('\n' + '=' * 70)