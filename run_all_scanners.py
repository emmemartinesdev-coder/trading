#!/usr/bin/env python3
"""
Main Runner: Esegue entrambi gli scanner
- Mean Reversion Scanner (RSI <= 30)
- Breakout S&P 500 Scanner
"""

import sys
import os
from datetime import datetime

# Aggiungi la directory corrente al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mean_reversion_scanner import scan_mean_reversion, format_results_mean_reversion, DEFAULT_TICKERS as MR_TICKERS
from breakout_sp500_scanner import scan_breakout_sp500, format_results_breakout, DEFAULT_SP500_TICKERS as SP500_TICKERS

def run_all_scanners(send_results=False):
    """Esegue tutti gli scanner"""
    
    print("\n" + "=" * 80)
    print("🚀 SISTEMA DI SCANNER TRADING - BENZINGA TRADER")
    print("=" * 80)
    print(f"⏰ Esecuzione: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)
    
    all_results = {}
    
    # =====================================
    # 1. SCANNER MEAN REVERSION
    # =====================================
    print("\n🔄 Avvio Scanner Mean Reversion (RSI <= 30)...")
    mr_results = scan_mean_reversion(MR_TICKERS)
    all_results['mean_reversion'] = mr_results
    
    # Formatta e mostra risultati
    mr_formatted = format_results_mean_reversion(mr_results)
    print(mr_formatted)
    
    # =====================================
    # 2. SCANNER BREAKOUT S&P 500
    # =====================================
    print("\n\n🔄 Avvio Scanner Breakout S&P 500...")
    breakout_results = scan_breakout_sp500(SP500_TICKERS)
    all_results['breakout'] = breakout_results
    
    # Formatta e mostra risultati
    breakout_formatted = format_results_breakout(breakout_results)
    print(breakout_formatted)
    
    # =====================================
    # RIEPILOGO
    # =====================================
    print("\n\n" + "=" * 80)
    print("📊 RIEPILOGO SCANNER")
    print("=" * 80)
    print(f"Mean Reversion (RSI <= 30): {len(mr_results)} opportunità")
    print(f"Breakout S&P 500: {len(breakout_results)} opportunità")
    print("=" * 80)
    
    return all_results

def get_top_picks(all_results, top_n=10):
    """Restituisce i top picks combinati"""
    combined = []
    
    # Aggiungi mean reversion
    for res in all_results.get('mean_reversion', []):
        combined.append({
            'ticker': res['ticker'],
            'price': res['price'],
            'score': res['mean_reversion_score'],
            'type': 'MEAN REVERSION',
            'rsi': res['rsi'],
            'reason': f"RSI ipervenduto ({res['rsi']})"
        })
    
    # Aggiungi breakout
    for res in all_results.get('breakout', []):
        combined.append({
            'ticker': res['ticker'],
            'price': res['price'],
            'score': res['breakout_score'],
            'type': 'BREAKOUT',
            'rsi': None,
            'reason': f"Volume {res['volume_ratio']}x, Near High {res['distance_to_high_pct']}%"
        })
    
    # Ordina per score
    combined.sort(key=lambda x: x['score'], reverse=True)
    
    return combined[:top_n]

def format_telegram_message(all_results):
    """Formatta messaggio per Telegram"""
    message = []
    message.append("📈 *RISULTATI SCANNER TRADING*")
    message.append(f"_{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}_")
    message.append("")
    
    # Mean Reversion Top 5
    mr = all_results.get('mean_reversion', [])[:5]
    if mr:
        message.append("🔴 *MEAN REVERSION (RSI ≤ 30)*")
        for res in mr:
            emoji = "🟢" if res['rsi'] <= 25 else "🟡"
            message.append(f"{emoji} ${res['ticker']} - RSI: {res['rsi']} | Score: {res['mean_reversion_score']}/100")
        message.append("")
    
    # Breakout Top 5
    bo = all_results.get('breakout', [])[:5]
    if bo:
        message.append("🟢 *BREAKOUT S&P 500*")
        for res in bo:
            emoji = "🟢" if res['resistance_break'] else "🟡"
            message.append(f"{emoji} ${res['ticker']} | Vol: {res['volume_ratio']}x | Score: {res['breakout_score']}/100")
        message.append("")
    
    # Top Combined Picks
    top_picks = get_top_picks(all_results, 5)
    if top_picks:
        message.append("⭐ *TOP 5 COMBINATI*")
        for i, pick in enumerate(top_picks, 1):
            message.append(f"{i}. ${pick['ticker']} ({pick['type']}) - Score: {pick['score']}")
    
    return "\n".join(message)

if __name__ == "__main__":
    # Esegui tutti gli scanner
    results = run_all_scanners()
    
    # Formatta messaggio Telegram
    telegram_msg = format_telegram_message(results)
    print("\n\n📱 Messaggio Telegram:")
    print("-" * 40)
    print(telegram_msg)
    
    # Salva risultati
    import json
    from datetime import date
    
    output_file = f"scanner_results_{date.today()}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n💾 Risultati salvati in {output_file}")