#!/usr/bin/env python3
"""
S&P 500 Breakout Scanner
Scansione azioni S&P500 per breakout e ritracciamento verso SMA20
Schedule: cron job ogni mattina alle 1:00
"""

import yfinance as yf
import pandas as pd
import numpy as np
import pandas_ta as ta
import requests
from datetime import datetime, timedelta
import time
import csv
import os
import sys

# ================== CONFIGURAZIONE ==================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "false").lower() == "true"
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", "")

SP500_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
DATA_DIR = "/root/.openclaw/workspace/data"
OUTPUT_DIR = "/root/.openclaw/workspace/output"

# Crea le directory se non esistono
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ================== FUNZIONI UTILITY ==================

def get_sp500_tickers():
    """Recupera la lista dei ticker S&P500 da Wikipedia"""
    print("📥 Recupero lista S&P500 da Wikipedia...")
    
    try:
        # Leggi la tabella da Wikipedia
        tables = pd.read_html(SP500_WIKIPEDIA_URL)
        df = tables[0]
        
        # Estrai ticker e nome
        tickers = df['Symbol'].tolist()
        names = df['Security'].tolist()
        
        # Pulisci i ticker (rimuovi spazi, caratteri speciali)
        cleaned_tickers = []
        cleaned_names = []
        for t, n in zip(tickers, names):
            ticker = str(t).strip().replace('.', '-')
            if ticker and ticker != 'nan':
                cleaned_tickers.append(ticker)
                cleaned_names.append(str(n).strip())
        
        print(f"✅ Trovati {len(cleaned_tickers)} ticker S&P500")
        return list(zip(cleaned_tickers, cleaned_names))
    
    except Exception as e:
        print(f"❌ Errore nel recupero lista: {e}")
        # Fallback: lista manuale di alcuni ticker principali
        return [
            ("AAPL", "Apple Inc."),
            ("MSFT", "Microsoft Corporation"),
            ("AMZN", "Amazon.com Inc."),
            ("GOOGL", "Alphabet Inc."),
            ("META", "Meta Platforms Inc."),
            ("NVDA", "NVIDIA Corporation"),
            ("TSLA", "Tesla Inc."),
            ("BRK.B", "Berkshire Hathaway"),
            ("JPM", "JPMorgan Chase & Co."),
            ("JNJ", "Johnson & Johnson"),
        ]

def download_stock_data(ticker, days=150):
    """Scarica i dati storici per un ticker"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_date, end=end_date, interval="1d")
        
        if df.empty or len(df) < 50:
            return None
        
        return df
    except Exception as e:
        return None

def calculate_indicators(df):
    """Calcola SMA20, RSI, ADX, DMI"""
    df = df.copy()
    
    # SMA
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    
    # RSI
    df['RSI'] = ta.rsi(df['Close'], length=14)
    
    # ADX e DMI
    adx_result = ta.adx(df['High'], df['Low'], df['Close'], length=14)
    df['ADX'] = adx_result['ADX_14']
    df['PLUS_DI'] = adx_result['DMP_14']
    df['MINUS_DI'] = adx_result['DMN_14']
    
    return df

def find_breakout(df, lookback=20):
    """Trova breakout nei'ultimi lookback giorni"""
    if df is None or len(df) < lookback + 10:
        return None, None, None
    
    df = calculate_indicators(df)
    
    for i in range(-lookback, 0):
        idx = len(df) + i
        
        # Verifica che ci siano abbastanza dati
        if idx < lookback:
            continue
        
        # Massimo dei 20 giorni precedenti
        start_idx = idx - lookback
        high_20 = df['High'].iloc[start_idx:idx].max()
        
        # Prezzo di chiusura e apertura del giorno i
        close = df['Close'].iloc[idx]
        open_price = df['Open'].iloc[idx]
        
        # Controllo breakout
        if close > high_20 and close > open_price:
            # Verifica che sia effettivamente un breakout (non troppo vecchio)
            breakout_date = df.index[idx]
            breakout_high = close
            
            # Verifica ritracciamento
            current_close = df['Close'].iloc[-1]
            sma20 = df['SMA20'].iloc[-1]
            
            if pd.isna(sma20):
                continue
            
            # Verifica che SMA20 > SMA50 (trend rialzista)
            sma50 = df['SMA50'].iloc[-1] if not pd.isna(df['SMA50'].iloc[-1]) else None
            if sma50 is None or sma20 <= sma50:
                continue
            
            # Il prezzo attuale è sotto il massimo del breakout?
            if current_close < breakout_high:
                # Entro il 5% della SMA20?
                deviation_pct = abs(current_close - sma20) / sma20 * 100
                
                if deviation_pct <= 5:
                    return {
                        'breakout_date': breakout_date,
                        'breakout_high': breakout_high,
                        'current_close': current_close,
                        'sma20': sma20,
                        'sma50': df['SMA50'].iloc[-1] if not pd.isna(df['SMA50'].iloc[-1]) else None,
                        'volume_5d': df['Volume'].iloc[-5:].mean(),
                        'volume_20d_before': df['Volume'].iloc[-25:-5].mean() if len(df) >= 25 else df['Volume'].iloc[:-5].mean(),
                        'rsi': df['RSI'].iloc[-1],
                        'rsi_prev': df['RSI'].iloc[-2],
                        'adx': df['ADX'].iloc[-1],
                        'plus_di': df['PLUS_DI'].iloc[-1],
                        'minus_di': df['MINUS_DI'].iloc[-1],
                    }
    
    return None

def analyze_volume(volume_5d, volume_20d):
    """Analizza il volume per il ritracciamento"""
    if volume_20d is None or volume_20d == 0:
        return "NEUTRO", 0
    
    ratio = volume_5d / volume_20d
    
    if ratio < 0.80:
        return "RIMBALZO_PROBABILE", 1
    else:
        return "CONTINUAZIONE_VERSO_SMA50", -1

def analyze_rsi(rsi, rsi_prev):
    """Analizza RSI"""
    if pd.isna(rsi) or pd.isna(rsi_prev):
        return "NEUTRO", 0
    
    if 40 <= rsi <= 55 and rsi > rsi_prev:
        return "RIMBALZO_PROBABILE", 1
    elif rsi < 40 and rsi < rsi_prev:
        return "CONTINUAZIONE_VERSO_SMA50", -1
    else:
        return "NEUTRO", 0

def analyze_adx(adx, plus_di, minus_di):
    """Analizza ADX e DMI"""
    if pd.isna(adx):
        return "NEUTRO", 0
    
    if adx < 20:
        return "RIMBALZO_PROBABILE", 1
    elif adx > 25 and minus_di > plus_di:
        return "CONTINUAZIONE_VERSO_SMA50", -1
    else:
        return "NEUTRO", 0

def classify_final(volume_score, rsi_score, adx_score):
    """Classificazione finale basata sui punteggi"""
    total = volume_score + rsi_score + adx_score
    
    if total >= 2:
        return "🟢 RIMBALZO_SMA20"
    elif total >= 0:
        return "🟡 INCERTO"
    else:
        return "🔴 VERSO_SMA50"

def format_alert(ticker, name, data, volume_signal, rsi_signal, adx_signal, classification):
    """Formatta l'alert per la stampa"""
    breakout_date = data['breakout_date'].strftime('%Y-%m-%d') if hasattr(data['breakout_date'], 'strftime') else str(data['breakout_date'])
    
    alert = f"""
==================================================
🔔 ALERT: {ticker} — {name}
==================================================
Prezzo attuale: ${data['current_close']:.2f}
SMA20: ${data['sma20']:.2f}
SMA50: ${data['sma50']:.2f}
Data breakout: {breakout_date}
Massimo breakout: ${data['breakout_high']:.2f}

📊 Indicatori:
Volume: {volume_signal}
RSI(14): {data['rsi']:.2f} → {rsi_signal}
ADX(14): {data['adx']:.2f} → {adx_signal}

🏁 Classificazione finale: {classification}
==================================================
"""
    return alert

def send_telegram_alert(alert_text):
    """Invia alert via Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram non configurato, skip invio")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": alert_text,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Errore invio Telegram: {e}")
        return False

def send_email_alert(alert_text, subject):
    """Invia alert via email"""
    if not EMAIL_ENABLED:
        return False
    
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = subject
        
        msg.attach(MIMEText(alert_text, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"❌ Errore invio email: {e}")
        return False

def save_to_csv(results, filename):
    """Salva i risultati su CSV"""
    if not results:
        print("⚠️ Nessun risultato da salvare")
        return
    
    fieldnames = [
        'Ticker', 'Nome', 'Prezzo', 'SMA20', 'SMA50', 
        'Data_Breakout', 'Max_Breakout', 'Volume_Signal', 
        'RSI', 'RSI_Signal', 'ADX', 'ADX_Signal', 'Classificazione_Finale'
    ]
    
    try:
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for r in results:
                writer.writerow({
                    'Ticker': r['ticker'],
                    'Nome': r['name'],
                    'Prezzo': r['data']['current_close'],
                    'SMA20': r['data']['sma20'],
                    'SMA50': r['data']['sma50'],
                    'Data_Breakout': r['data']['breakout_date'].strftime('%Y-%m-%d') if hasattr(r['data']['breakout_date'], 'strftime') else str(r['data']['breakout_date']),
                    'Max_Breakout': r['data']['breakout_high'],
                    'Volume_Signal': r['volume_signal'],
                    'RSI': r['data']['rsi'],
                    'RSI_Signal': r['rsi_signal'],
                    'ADX': r['data']['adx'],
                    'ADX_Signal': r['adx_signal'],
                    'Classificazione_Finale': r['classification']
                })
        
        print(f"✅ Risultati salvati su {filename}")
    except Exception as e:
        print(f"❌ Errore salvataggio CSV: {e}")

# ================== MAIN ==================

def main():
    print("=" * 60)
    print("🚀 S&P 500 BREAKOUT SCANNER")
    print(f"📅 Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Recupera lista ticker
    tickers_data = get_sp500_tickers()
    
    results = []
    errors = []
    processed = 0
    
    print(f"\n📊 Inizio scansione di {len(tickers_data)} azioni...")
    print("-" * 40)
    
    for i, (ticker, name) in enumerate(tickers_data):
        processed += 1
        
        # Progress update ogni 50 ticker
        if processed % 50 == 0:
            print(f"⏳ Processati {processed}/{len(tickers_data)} ticker...")
        
        # Rate limiting
        time.sleep(0.2)
        
        try:
            # Scarica dati
            df = download_stock_data(ticker)
            
            if df is None:
                errors.append(f"{ticker}: dati non disponibili")
                continue
            
            # Trova breakout
            breakout_data = find_breakout(df)
            
            if breakout_data is None:
                continue
            
            # Analizza indicatori
            volume_signal, volume_score = analyze_volume(
                breakout_data['volume_5d'], 
                breakout_data['volume_20d_before']
            )
            
            rsi_signal, rsi_score = analyze_rsi(
                breakout_data['rsi'],
                breakout_data['rsi_prev']
            )
            
            adx_signal, adx_score = analyze_adx(
                breakout_data['adx'],
                breakout_data['plus_di'],
                breakout_data['minus_di']
            )
            
            # Classificazione finale
            classification = classify_final(volume_score, rsi_score, adx_score)
            
            # Crea risultato
            result = {
                'ticker': ticker,
                'name': name,
                'data': breakout_data,
                'volume_signal': volume_signal,
                'volume_score': volume_score,
                'rsi_signal': rsi_signal,
                'rsi_score': rsi_score,
                'adx_signal': adx_signal,
                'adx_score': adx_score,
                'classification': classification
            }
            
            results.append(result)
            
            # Formatta e stampa alert
            alert = format_alert(ticker, name, breakout_data, volume_signal, rsi_signal, adx_signal, classification)
            print(alert)
            
            # Invia notifiche
            send_telegram_alert(alert)
            
        except Exception as e:
            errors.append(f"{ticker}: {str(e)}")
            continue
    
    # Riepilogo
    print("\n" + "=" * 60)
    print("📊 RIEPILOGO SCANSIONE")
    print("=" * 60)
    print(f"Ticker processati: {processed}/{len(tickers_data)}")
    print(f"Breakout rilevati: {len(results)}")
    print(f"Errori: {len(errors)}")
    
    if errors:
        print("\n⚠️ Errori:")
        for err in errors[:10]:  # Mostra solo i primi 10
            print(f"  - {err}")
    
    # Salva CSV
    today = datetime.now().strftime('%Y%m%d')
    csv_filename = os.path.join(OUTPUT_DIR, f"sp500_breakout_alerts_{today}.csv")
    save_to_csv(results, csv_filename)
    
    # Invia riepilogo se ci sono risultati
    if results:
        summary = f"🔔 <b>S&P 500 Breakout Scanner</b>\n\n"
        summary += f"📅 {datetime.now().strftime('%Y-%m-%d')}\n"
        summary += f"✅ Breakout trovati: {len(results)}\n\n"
        
        # Raggruppa per classificazione
        green = [r for r in results if 'RIMBALZO_SMA20' in r['classification']]
        yellow = [r for r in results if 'INCERTO' in r['classification']]
        red = [r for r in results if 'VERSO_SMA50' in r['classification']]
        
        if green:
            summary += f"🟢 RIMBALZO_SMA20: {len(green)}\n"
            for r in green[:3]:
                summary += f"  • {r['ticker']}: ${r['data']['current_close']:.2f}\n"
        
        if yellow:
            summary += f"\n🟡 INCERTO: {len(yellow)}\n"
            for r in yellow[:3]:
                summary += f"  • {r['ticker']}: ${r['data']['current_close']:.2f}\n"
        
        if red:
            summary += f"\n🔴 VERSO_SMA50: {len(red)}\n"
            for r in red[:3]:
                summary += f"  • {r['ticker']}: ${r['data']['current_close']:.2f}\n"
        
        send_telegram_alert(summary)
    
    print("\n✅ Scansione completata!")
    
    return len(results)

if __name__ == "__main__":
    main()