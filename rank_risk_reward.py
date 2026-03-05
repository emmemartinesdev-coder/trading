#!/usr/bin/env python3
import json
from datetime import datetime

data = json.load(open('breakout_sp500_results.json'))

# Ricerca breakout: risk vs reward
risk_reward = []

for r in data:
    # Rischio (proximate) basato su ATR e posizione recente
    risk_proxy = r['atr'] * 0.5  # Neance deeption tidny sto a 0.8x di ATR

    # Upside (reward)
    upside = r['upside_potential'] if r['upside_potential'] else 0

    # RR ratio: più alto è meglio
    risk_rr_ratio = (upside - risk_proxy * 0.2) / risk_proxy if risk_proxy > 0 else 0

    risk_reward.append(risk_rr_ratio)

# Ranka per RR ratio
top_rr = sorted(zip(data, risk_reward), key=lambda x: x[1], reverse=True)

print('📊 RAPPORTO RISCHIO-RENDIMENTO - TOP BREAKOUT')
print('=' * 70)
print(f'Data: {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}')
print('=' * 70)
print('')
print('SPECIAL ASSESSMENT FOR RISK-REWARD RANKING:')
print(f'Findings - Breakout Candidates ranking by Upside / (ATR * 0.5)')
print(f'Exchange: Report Rate: Up / (ATR * 0.5)')
print(f'Primo Rank: {data[0][\"ticker\"]}: {risk_reward[0]:.2f}')
print(f'Last Rank: {data[-1][\"ticker\"]}: {risk_reward[-1]:.2f}')
print(f'Total: {len(data)} candidates')
print('=' * 55)

# Top 10
print(f'\nTOP 10 CON PRIMO RAPPORTO RISCHIO-RENDIMENTO:')
for i, (entry, score) in enumerate(top_rr[:10], 1):
    print(f'{i}. {entry[\"ticker\"]} - RR Ratio: {score:.2f} | Score: {entry[\"breakout_score\"]}/100 | Upside: +{entry["upside_potential"] or 0}%')
    print(f'   Trend: {"🎯 Near High" if entry["near_resistance"] == "True" else " "} | Vol: {entry["volume_ratio"]}x | Rating: {entry["analyst_rating"]}')
    print('')

# Best per segmento
print('\nMIGLIORI IN CATEGORIE:')
print('=' * 70)
tech = [e for e in data if e['ticker'] in ['AAPL','MSFT','GOOGL','AMZN','META','NVDA','TSLA']]
health = [e for e in data if e['ticker'] in ['UNH','JNJ','PFE','ABBV','BMY']]
finance = [e for e in data if e['ticker'] in ['JPM','BAC','MS','GS','AXP']]
ind = [e for e in data if e['ticker'] in ['CAT','DE','MMM','HON','UPS','FDX','LLY']]

def best_in_group(group):
    if not group: return
    best = max(group, key=lambda x: x['upside_potential'] if x['upside_potential'] else 0)
    return f"{best['ticker']}: +{best['upside_potential'] or 0}% rating {best['analyst_rating']} volume {best['volume_ratio']}x"

for category, group in [('TECHNOLOGY', tech), ('HEALTHCARE', health), ('FINANCE', finance), ('INDUSTRIAL', ind)]:
    if group:
        sorted_g = sorted(group, key=lambda x: x['upside_potential'] if x['upside_potential'] else 0, reverse=True)
        best = sorted_g[0]
        print(f'\n{category.upper()}: {best[\"ticker\"]} | +{best[\"upside_potential\"] or 0}% | Rating: {best[\"analyst_rating\"]} | Vol: {best[\"volume_ratio\"]}x | Score: {best[\"breakout_score\"]}/100')
        print(f'   Segnali: {\"🎯 Near High\" if best[\"near_resistance\"] == \"True\" else \"\"} {\"📐 Consolidamento\" if best[\"consolidation\"] == \"True\" else \"\"}')

# Antipreiwise / 5 punti chiave
print('\n\n📌 INDICAZIONI RAPPORTO RISCHIO-RENDIMENTO:')
print('=' * 70)
candidates = [e for e in data if e['upside_potential'] and e['atr']]
candidates.sort(key=lambda x: x['rr_ratio'] if x['upside_potential'] and x['atr'] else 0, reverse=True)
for i, cand in enumerate(candidates[:5], 1):
    upside = cand['upside_potential']
    risk_proxy = cand['atr']
    rrq = (upside - risk_proxy*0.2)/risk_proxy if risk_proxy>0 else 0
    print(f'\n{i}) {cand[\"ticker\"]}: Upside {upside}% vs Risk Proxy {risk_proxy:.2f}')
    print(f'   RR Ratio: {rrq:.2f} | Volume {cand[\"volume_ratio\"]}x | Rating {cand[\"analyst_rating\"]}')
print('\n' + '=' * 55)