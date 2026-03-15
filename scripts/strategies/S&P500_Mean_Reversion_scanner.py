#!/usr/bin/env python3
"""
S&P 500 Mean Reversion Scanner
Identifica azioni con:
- RSI < 30 (ipervenduto)
- Prezzo vicino alla banda inferiore di Bollinger
Fornisce SL, TP e Rischio/Rendimento
"""

import yfinance as yf
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
from pathlib import Path

# Telegram config (usa variabili d'ambiente o valori di default)
import os
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8475258962:AAG46md8dRyuL4Koh6YsEyaby7VwKvtj0S4")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "494745285")

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

def calculate_rsi(prices, period=14):
    """Calcola l'RSI con metodo Wilder (standard)"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Wilder's smoothing (exponential weighted moving average)
    alpha = 1 / period
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_bollinger_bands(prices, window=20, num_std=2):
    """Calcola le Bande di Bollinger"""
    sma = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()
    upper_band = sma + (std * num_std)
    lower_band = sma - (std * num_std)
    return upper_band, lower_band, sma

def calculate_sl_tp(price, lower_bb, ma20):
    """Calcola Stop Loss e Take Profit per setup mean reversion"""
    # SL sotto la banda inferiore di Bollinger
    sl = lower_bb * 0.98
    if sl >= price:
        sl = price * 0.97
    
    # TP alla media mobile (MA20)
    tp = ma20
    
    risk = price - sl
    rr_ratio = (tp - price) / risk if risk > 0 else 0
    
    return round(sl, 2), round(tp, 2), round(rr_ratio, 2)

def get_mean_reversion_stocks(tickers, lookback_days=60, rsi_threshold=30):
    """Trova stock con setup mean reversion: RSI < 30 e prezzo vicino lower BB"""
    mean_reversions = []
    
    print(f"📊 Scanning {len(tickers)} tickers for mean reversion...")
    print(f"   Filtri: RSI < {rsi_threshold}, prezzo vicino lower BB")
    print()
    
    for i, ticker in enumerate(tickers):
        if (i + 1) % 50 == 0:
            print(f"   Processed {i + 1}/{len(tickers)}...")
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=f"{lookback_days}d", interval='1d')
            
            if len(hist) < 30:
                continue
            
            # Calcola RSI con metodo Wilder
            hist['RSI'] = calculate_rsi(hist['Close'])
            
            # Calcola Bollinger Bands
            hist['BB_Upper'], hist['BB_Lower'], hist['MA20'] = calculate_bollinger_bands(hist['Close'])
            
            current_price = hist['Close'].iloc[-1]
            current_rsi = hist['RSI'].iloc[-1]
            lower_bb = hist['BB_Lower'].iloc[-1]
            upper_bb = hist['BB_Upper'].iloc[-1]
            ma20 = hist['MA20'].iloc[-1]
            
            # Filtro 1: RSI < 30
            if current_rsi >= rsi_threshold:
                continue
            
            # Filtro 2: prezzo vicino alla banda inferiore (entro 5% sopra)
            if current_price > lower_bb * 1.05:
                continue
            
            # Calcola distanza dalla lower BB
            pct_from_lower_bb = ((current_price - lower_bb) / lower_bb) * 100
            
            # Calcola SL, TP, R/R
            sl, tp, rr = calculate_sl_tp(current_price, lower_bb, ma20)
            
            # Momentum 5 giorni
            momentum = 0
            if len(hist) >= 5:
                momentum = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100
            
            # Ottieni market cap
            try:
                info = stock.info
                market_cap = info.get('marketCap', 0) or 0
            except:
                market_cap = 0
            
            mean_reversions.append({
                'Ticker': ticker,
                'Price': round(current_price, 2),
                'RSI': round(current_rsi, 2),
                'BB_Lower': round(lower_bb, 2),
                'BB_Upper': round(upper_bb, 2),
                'MA20': round(ma20, 2),
                'Dist Lower BB %': round(pct_from_lower_bb, 2),
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
    print("🔍 S&P 500 MEAN REVERSION SCANNER")
    print("   RSI < 30 + prezzo vicino Lower BB")
    print("=" * 60)
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()
    
    tickers = load_sp500_tickers()
    mean_reversions = get_mean_reversion_stocks(tickers)
    
    if mean_reversions:
        df = pd.DataFrame(mean_reversions)
        # Ordina per R/R ratio (migliori prima)
        df = df.sort_values('RR', ascending=False)
        
        print(f"\n✅ Trovati {len(mean_reversions)} Mean Reversion:\n")
        print("=" * 70)
        
        for _, row in df.head(20).iterrows():
            print(f"📉 {row['Ticker']:5s} | ${row['Price']:7.2f} | RSI: {row['RSI']:5.2f} | Lower BB: ${row['BB_Lower']:.2f} | Dist: {row['Dist Lower BB %']:+.2f}%")
            print(f"   🛡️ SL: ${row['SL']} | 🎯 TP: ${row['TP']} | ⚖️ R/R: {row['RR']}:1")
            print()
        
        # Prepara messaggio Telegram
        msg = f"📊 *S&P 500 Mean Reversion Scanner*\n_{datetime.now().strftime('%d/%m/%Y %H:%M')}_\n\n"
        msg += f"*Filtri:* RSI < 30 + prezzo vicino Lower BB\n\n"
        msg += f"*✅ {len(mean_reversions)} Setup Trovati:*\n\n"
        
        for _, row in df.head(15).iterrows():
            emoji = "⚠️" if row['RR'] < 1.5 else "📉"
            msg += f"{emoji} *{row['Ticker']}* ${row['Price']}\n"
            msg += f"   RSI: {row['RSI']} | Lower BB: ${row['BB_Lower']} | {row['Dist Lower BB %']:+.1f}%\n"
            msg += f"   🛡️ SL: ${row['SL']} | 🎯 TP: ${row['TP']} | ⚖️ R/R: {row['RR']}:1\n\n"
        
        if len(mean_reversions) > 15:
            msg += f"_...e altri {len(mean_reversions) - 15} setup_"
        
        send_telegram_message(msg)
        
    else:
        print("❌ Nessun setup mean reversion trovato oggi.")
        msg = f"📊 *S&P 500 Mean Reversion Scanner*\n_{datetime.now().strftime('%d/%m/%Y %H:%M')}_\n\n"
        msg += "Nessun setup trovato (RSI < 30 + prezzo vicino Lower BB)"
        send_telegram_message(msg)
    
    # Salva risultati
    if mean_reversions:
        df.to_csv('mean_reversion_sp500_results.csv', index=False)
        print(f"\n💾 Risultati salvati in mean_reversion_sp500_results.csv")

if __name__ == "__main__":
    main()