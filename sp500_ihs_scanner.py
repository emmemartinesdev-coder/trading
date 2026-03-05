#!/usr/bin/env python3
"""
S&P 500 Inverse Head & Shoulders Scanner
Identifica pattern IHS (rialzista) sui timeframe daily
Analizza tutte le 503 azioni S&P500 ordinate per market cap
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
from pathlib import Path

# Telegram config
TELEGRAM_BOT_TOKEN = "8356765226:AAHJCAziToDKteBti2JkN3yaHy0No_2FEs0"
TELEGRAM_CHAT_ID = "494745285"

def load_sp500_tickers():
    """Carica la lista S&P500 da file o da Wikipedia"""
    ticker_file = Path(__file__).parent / 'sp500_tickers.json'
    
    if ticker_file.exists():
        with open(ticker_file) as f:
            return json.load(f)
    else:
        # Scarica da Wikipedia
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        response = requests.get(url, headers=headers)
        tables = pd.read_html(response.text)
        sp500 = tables[0]
        symbols = [s.replace('.', '-') for s in sp500['Symbol'].tolist()]
        
        with open(ticker_file, 'w') as f:
            json.dump(symbols, f, indent=2)
        
        return symbols

def send_telegram_message(message):
    """Invia messaggio su Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            print("✅ Messaggio inviato su Telegram")
        else:
            print(f"❌ Errore Telegram: {response.text}")
    except Exception as e:
        print(f"❌ Errore invio Telegram: {e}")

def find_local_minima(prices, window=5):
    """Trova minimi locali"""
    minima = []
    for i in range(window, len(prices) - window):
        if all(prices[i] <= prices[i+j] for j in range(-window, window+1) if j != 0):
            minima.append((i, prices[i]))
    return minima

def find_local_maxima(prices, window=5):
    """Trova massimi locali"""
    maxima = []
    for i in range(window, len(prices) - window):
        if all(prices[i] >= prices[i+j] for j in range(-window, window+1) if j != 0):
            maxima.append((i, prices[i]))
    return maxima

def detect_ihs_pattern(hist, lookback=60):
    """Rileva pattern Inverse Head & Shoulders"""
    if len(hist) < lookback:
        return None
    
    close = hist['Close'].values[-lookback:]
    highs = hist['High'].values[-lookback:]
    lows = hist['Low'].values[-lookback:]
    
    minima = find_local_minima(lows, window=3)
    maxima = find_local_maxima(highs, window=3)
    
    if len(minima) < 3 or len(maxima) < 2:
        return None
    
    minima_sorted = sorted(minima, key=lambda x: x[1])
    
    for i in range(len(minima_sorted) - 2):
        left_shoulder_idx, left_shoulder_low = minima_sorted[i]
        
        for j in range(i + 1, len(minima_sorted) - 1):
            head_idx, head_low = minima_sorted[j]
            
            if head_low >= left_shoulder_low:
                continue
            
            for k in range(j + 1, len(minima_sorted)):
                right_shoulder_idx, right_shoulder_low = minima_sorted[k]
                
                shoulder_diff = abs(right_shoulder_low - left_shoulder_low) / left_shoulder_low
                
                if shoulder_diff > 0.20:
                    continue
                
                head_depth = (left_shoulder_low - head_low) / left_shoulder_low
                if head_depth < 0.03:
                    continue
                
                if right_shoulder_idx <= head_idx:
                    continue
                
                left_shoulder_high = highs[left_shoulder_idx]
                right_shoulder_high = highs[right_shoulder_idx]
                neckline = max(left_shoulder_high, right_shoulder_high)
                
                current_price = close[-1]
                
                if current_price > neckline:
                    breakout_pct = (current_price - neckline) / neckline * 100
                    target = 2 * neckline - head_low
                    
                    return {
                        'pattern': 'IHS',
                        'left_shoulder': round(left_shoulder_low, 2),
                        'head': round(head_low, 2),
                        'right_shoulder': round(right_shoulder_low, 2),
                        'neckline': round(neckline, 2),
                        'current_price': round(current_price, 2),
                        'breakout_pct': round(breakout_pct, 2),
                        'target': round(target, 2),
                    }
    
    return None

def get_ihs_stocks(tickers, lookback_days=60):
    """Trova stock con pattern IHS"""
    ihs_patterns = []
    
    print(f"📊 Scanning {len(tickers)} tickers for Inverse Head & Shoulders...")
    
    for i, ticker in enumerate(tickers):
        if (i + 1) % 50 == 0:
            print(f"   Processed {i + 1}/{len(tickers)}...")
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=f"{lookback_days+10}d", interval='1d')
            
            if len(hist) < lookback_days:
                continue
            
            pattern = detect_ihs_pattern(hist, lookback_days)
            
            if pattern:
                pattern['Ticker'] = ticker
                sl = min(pattern['right_shoulder'], pattern['head']) * 0.99
                rr = (pattern['target'] - pattern['current_price']) / (pattern['current_price'] - sl)
                
                pattern['SL'] = round(sl, 2)
                pattern['RR'] = round(rr, 2)
                
                # Ottieni market cap
                try:
                    info = stock.info
                    pattern['MarketCap'] = info.get('marketCap', 0) or 0
                except:
                    pattern['MarketCap'] = 0
                
                ihs_patterns.append(pattern)
                
        except Exception as e:
            continue
    
    return ihs_patterns

def main():
    print("=" * 60)
    print("🔍 S&P 500 INVERSE HEAD & SHOULDERS SCANNER (FULL)")
    print("=" * 60)
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()
    
    tickers = load_sp500_tickers()
    ihs_patterns = get_ihs_stocks(tickers)
    
    if ihs_patterns:
        # Ordina per market cap (più importanti prima)
        ihs_patterns = sorted(ihs_patterns, key=lambda x: x.get('MarketCap', 0), reverse=True)
        
        print(f"\n✅ Trovati {len(ihs_patterns)} Pattern IHS:\n")
        print("=" * 60)
        
        for p in ihs_patterns[:20]:
            mcap_b = p.get('MarketCap', 0) / 1e9
            print(f"🟢 {p['Ticker']:6s} | ${p['current_price']:8.2f} | Neckline: ${p['neckline']:7.2f} | Breakout: {p['breakout_pct']:+6.2f}% | MCap: ${mcap_b:.0f}B | SL: ${p['SL']:.2f} | TP: ${p['target']:.2f} | R/R: {p['RR']:.2f}:1")
        
        print("\n" + "=" * 60)
        
        # Format output per Telegram (top 15 per market cap)
        msg = f"📊 *S&P 500 Inverse Head & Shoulders Scanner*\n_{datetime.now().strftime('%d/%m/%Y %H:%M')}_\n\n"
        msg += f"*✅ {len(ihs_patterns)} Pattern IHS Rialzisti:*\n\n"
        
        for p in ihs_patterns[:15]:
            emoji = "🚀" if p['breakout_pct'] > 2 else "⚡"
            msg += f"{emoji} *{p['Ticker']}* ${p['current_price']:.2f}\n"
            msg += f"   Neckline: ${p['neckline']:.2f} | Breakout: {p['breakout_pct']:+.1f}%\n"
            msg += f"   🛡️ SL: ${p['SL']:.2f} | 🎯 TP: ${p['target']:.2f} | ⚖️ R/R: {p['RR']:.1f}:1\n\n"
        
        if len(ihs_patterns) > 15:
            msg += f"_...e altri {len(ihs_patterns) - 15} pattern_"
        
    else:
        msg = "📊 *S&P 500 Inverse Head & Shoulders Scanner*\n_{}_\n\nNessun pattern IHS rilevato oggi.".format(datetime.now().strftime('%d/%m/%Y %H:%M'))
    
    print("\n" + msg)
    send_telegram_message(msg)
    return msg

if __name__ == "__main__":
    main()
