#!/usr/bin/env python3
"""
S&P 500 Mean Reversion Scanner
Identifica azioni in ipervendute che potrebbero rimbalzare verso la media mobile
Analizza tutte le 503 azioni S&P500 ordinate per market cap
"""

import yfinance as yf
import pandas as pd
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

def calculate_sl_tp(price, ma20, lookback_low):
    """Calcola Stop Loss e Take Profit per setup mean reversion"""
    sl = lookback_low * 0.99
    if sl >= price:
        sl = price * 0.98
    tp = ma20
    risk = price - sl
    rr_ratio = (tp - price) / risk if risk > 0 else 0
    return round(sl, 2), round(tp, 2), round(rr_ratio, 2)

def get_mean_reversion_stocks(tickers, lookback_days=20, oversold_threshold=-0.05):
    """Trova stock in ipervenduta (sotto la media mobile)"""
    mean_reversions = []
    
    print(f"📊 Scanning {len(tickers)} tickers for mean reversion...")
    
    for i, ticker in enumerate(tickers):
        if (i + 1) % 50 == 0:
            print(f"   Processed {i + 1}/{len(tickers)}...")
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=f"{lookback_days+10}d", interval='1d')
            
            if len(hist) < lookback_days:
                continue
            
            hist['MA20'] = hist['Close'].rolling(window=lookback_days).mean()
            
            current_price = hist['Close'].iloc[-1]
            ma20 = hist['MA20'].iloc[-1]
            
            # Controlla se è sotto la MA (ipervenduto)
            if current_price < ma20 * (1 + oversold_threshold):
                pct_below_ma = ((ma20 - current_price) / ma20) * 100
                
                momentum = 0
                if len(hist) >= 5:
                    momentum = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100
                
                low_20d = hist['Low'].iloc[-lookback_days:].min()
                sl, tp, rr = calculate_sl_tp(current_price, ma20, low_20d)
                
                # Ottieni market cap
                try:
                    info = stock.info
                    market_cap = info.get('marketCap', 0) or 0
                except:
                    market_cap = 0
                
                mean_reversions.append({
                    'Ticker': ticker,
                    'Price': round(current_price, 2),
                    'MA20': round(ma20, 2),
                    'Below MA %': round(pct_below_ma, 2),
                    'Momentum 5d %': round(momentum, 2),
                    'MarketCap': market_cap,
                    'SL': sl,
                    'TP': tp,
                    'RR': rr
                })
                
        except Exception as e:
            continue
    
    return mean_reversions

def main():
    print("=" * 60)
    print("🔍 S&P 500 MEAN REVERSION SCANNER (FULL)")
    print("=" * 60)
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()
    
    tickers = load_sp500_tickers()
    mean_reversions = get_mean_reversion_stocks(tickers)
    
    if mean_reversions:
        df = pd.DataFrame(mean_reversions)
        # Ordina per market cap (più importanti prima)
        df = df.sort_values('MarketCap', ascending=False)
        
        print(f"\n✅ Trovati {len(mean_reversions)} Mean Reversion:\n")
        print("=" * 60)
        
        for _, row in df.head(20).iterrows():
            mcap_b = row['MarketCap'] / 1e9 if row['MarketCap'] > 0 else 0
            print(f"📉 {row['Ticker']:6s} | ${row['Price']:8.2f} | MA20: ${row['MA20']:7.2f} | -{row['Below MA %']:5.2f}% | MCap: ${mcap_b:.0f}B | SL: ${row['SL']:.2f} | TP: ${row['TP']:.2f} | R/R: {row['RR']}:1")
        
        print("\n" + "=" * 60)
        
        # Format output per Telegram (top 15 per market cap)
        msg = f"📊 *S&P 500 Mean Reversion Scanner*\n_{datetime.now().strftime('%d/%m/%Y %H:%M')}_\n\n"
        msg += f"*✅ {len(mean_reversions)} Setup Mean Reversion:*\n\n"
        
        for _, row in df.head(15).iterrows():
            emoji = "⚠️" if row['Below MA %'] > 8 else "📉"
            msg += f"{emoji} *{row['Ticker']}* ${row['Price']:.2f}\n"
            msg += f"   MA20: ${row['MA20']:.2f} | -{row['Below MA %']:.1f}%\n"
            msg += f"   🛡️ SL: ${row['SL']:.2f} | 🎯 TP: ${row['TP']:.2f} | ⚖️ R/R: {row['RR']}:1\n\n"
        
        if len(mean_reversions) > 15:
            msg += f"_...e altri {len(mean_reversions) - 15} setup_"
        
    else:
        msg = "📊 *S&P 500 Mean Reversion Scanner*\n_{}_\n\nNessun setup mean reversion trovato oggi.".format(datetime.now().strftime('%d/%m/%Y %H:%M'))
    
    print("\n" + msg)
    send_telegram_message(msg)
    return msg

if __name__ == "__main__":
    main()
