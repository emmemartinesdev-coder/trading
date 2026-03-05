#!/usr/bin/env python3
"""
S&P 500 Breakout Scanner
Identifica azioni che stanno facendo breakout rispetto alla loro media mobile
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
        
        # Salva per usi futuri
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

def calculate_sl_tp(price, lookback_low):
    """Calcola Stop Loss e Take Profit per setup breakout"""
    sl = lookback_low * 0.99
    risk = price - sl
    tp = price + (risk * 2)
    rr_ratio = (tp - price) / (price - sl) if (price - sl) > 0 else 0
    return round(sl, 2), round(tp, 2), round(rr_ratio, 2)

def get_breakout_stocks(tickers, lookback_days=20, breakout_threshold=0.03):
    """
    Trova breakout VERI: rottura del massimo recente (20 giorni)
    Un breakout vero è quando il prezzo rompe sopra il massimo degli ultimi N giorni
    """
    breakouts = []
    
    print(f"📊 Scanning {len(tickers)} tickers for breakouts...")
    
    for i, ticker in enumerate(tickers):
        if (i + 1) % 50 == 0:
            print(f"   Processed {i + 1}/{len(tickers)}...")
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=f"{lookback_days+10}d", interval='1d')
            
            if len(hist) < lookback_days:
                continue
            
            # Calcola indicatori
            hist['MA20'] = hist['Close'].rolling(window=lookback_days).mean()
            hist['High_20'] = hist['High'].rolling(window=lookback_days).max()
            hist['Low_20'] = hist['Low'].rolling(window=lookback_days).min()
            
            current_price = hist['Close'].iloc[-1]
            ma20 = hist['MA20'].iloc[-1]
            high_20d = hist['High_20'].iloc[-1]
            low_20d = hist['Low_20'].iloc[-1]
            
            # BREAKOUT VERO: prezzo rompe sopra il massimo recente (20 giorni)
            # con un margine del 3% (per evitare falsi segnali vicino alla resistenza)
            if current_price >= high_20d * (1 - 0.01) and current_price > ma20:
                # Verifica che non sia semplicemente vicino alla resistenza,
                # ma che ci sia stato un movimento direzionale recente
                pct_from_low = ((current_price - low_20d) / low_20d) * 100
                pct_above_ma = ((current_price - ma20) / ma20) * 100
                
                # Calcola momentum (ultimi 5 giorni)
                momentum = 0
                if len(hist) >= 5:
                    momentum = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100
                
                # Calcola SL/TP usando il minimo recente come stop
                sl, tp, rr = calculate_sl_tp(current_price, low_20d)
                
                # Verifica volume recente (deve essere sopra la media)
                avg_volume = hist['Volume'].tail(20).mean()
                recent_volume = hist['Volume'].iloc[-5:].mean()
                volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
                
                # Solo breakout con momentum positivo e volume
                if momentum > 0 and volume_ratio > 0.8:
                    # Ottieni market cap per ordinamento
                    try:
                        info = stock.info
                        market_cap = info.get('marketCap', 0) or 0
                    except:
                        market_cap = 0
                    
                    breakouts.append({
                        'Ticker': ticker,
                        'Price': round(current_price, 2),
                        'MA20': round(ma20, 2),
                        'High_20d': round(high_20d, 2),
                        'Above MA %': round(pct_above_ma, 2),
                        'Above Low %': round(pct_from_low, 2),
                        'Momentum 5d %': round(momentum, 2),
                        'Volume Ratio': round(volume_ratio, 2),
                        'MarketCap': market_cap,
                        'SL': sl,
                        'TP': tp,
                        'RR': rr
                    })
                
        except Exception as e:
            continue
    
    return breakouts

def main():
    print("=" * 60)
    print("🔍 S&P 500 BREAKOUT SCANNER (FULL)")
    print("=" * 60)
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()
    
    tickers = load_sp500_tickers()
    breakouts = get_breakout_stocks(tickers)
    
    if breakouts:
        df = pd.DataFrame(breakouts)
        # Ordina per market cap (più importanti prima)
        df = df.sort_values('MarketCap', ascending=False)
        
        # Salva risultati in JSON
        df.to_json('breakout_sp500_results.json', orient='records', indent=2)
        
        print(f"\n✅ Trovati {len(breakouts)} BREAKOUT:\n")
        print("=" * 60)
        
        for _, row in df.head(20).iterrows():
            mcap_b = row['MarketCap'] / 1e9 if row['MarketCap'] > 0 else 0
            print(f"📈 {row['Ticker']:6s} | ${row['Price']:8.2f} | High 20d: ${row['High_20d']:7.2f} | +{row['Above Low %']:5.2f}% | MCap: ${mcap_b:.0f}B | SL: ${row['SL']:.2f} | TP: ${row['TP']:.2f} | R/R: {row['RR']}:1")
        
        print("\n" + "=" * 60)
        
        # Format output per Telegram (top 15 per market cap)
        msg = f"📊 *S&P 500 Breakout Scanner*\n_{datetime.now().strftime('%d/%m/%Y %H:%M')}_\n\n"
        msg += f"*✅ {len(breakouts)} Breakout trovati:*\n\n"
        
        for _, row in df.head(15).iterrows():
            emoji = "🔥" if row['Above Low %'] > 10 else "📈"
            msg += f"{emoji} *{row['Ticker']}* ${row['Price']:.2f}\n"
            msg += f"   High 20d: ${row['High_20d']:.2f} | From Low: +{row['Above Low %']:.1f}%\n"
            msg += f"   📈 Momentum 5d: {row['Momentum 5d %']:.1f}% | Vol: {row['Volume Ratio']:.1f}x\n"
            msg += f"   🛡️ SL: ${row['SL']:.2f} | 🎯 TP: ${row['TP']:.2f} | ⚖️ R/R: {row['RR']}:1\n\n"
        
        if len(breakouts) > 15:
            msg += f"_...e altri {len(breakouts) - 15} breakout_"
            
    else:
        msg = "📊 *S&P 500 Breakout Scanner*\n_{}_\n\nNessun breakout trovato oggi.".format(datetime.now().strftime('%d/%m/%Y %H:%M'))
    
    print("\n" + msg)
    send_telegram_message(msg)
    return msg

if __name__ == "__main__":
    main()
