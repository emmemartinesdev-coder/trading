#!/usr/bin/env python3
"""
Mean Reversion Scanner con Filtro RSI <= 30
Identifica titoli in ipervenduto che potrebbero revertire alla media
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

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

def calculate_moving_average(prices, period=50):
    """Calcola la media mobile"""
    return prices.rolling(window=period).mean()

def mean_reversion_score(row, close, upper_band, lower_band, sma):
    """Calcola score di mean reversion"""
    score = 0
    
    # RSI ipervenduto (principale filtro richiesto)
    if row['RSI'] <= 30:
        score += 40
        if row['RSI'] <= 25:
            score += 10
    
    # Prezzo sotto banda inferiore di Bollinger
    if close < lower_band:
        score += 20
        if close < (lower_band * 0.95):
            score += 10
    
    # Prezzo sotto media mobile a 50 giorni
    if close < sma:
        score += 15
        if close < (sma * 0.95):
            score += 10
    
    # Distanza dalla banda superiore (opportunità di upside)
    band_width = upper_band - lower_band
    if band_width > 0:
        distance_from_lower = (close - lower_band) / band_width
        if distance_from_lower < 0.2:
            score += 5
    
    return score

def scan_mean_reversion(tickers, period='3mo'):
    """
    Scanner principale per pattern mean reversion
    
    Filtri:
    - RSI <= 30 (richiesto)
    - Prezzo sotto media mobile 50
    - Prezzo sotto/near banda inferiore Bollinger
    - Volume anomalo (opzionale)
    """
    results = []
    
    print(f"🔍 Scanner Mean Reversion - RSI <= 30")
    print(f"📊 Analisi di {len(tickers)} titoli...")
    print("-" * 60)
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval='1d')
            
            if len(hist) < 60:
                continue
            
            # Calcola indicatori
            hist['RSI'] = calculate_rsi(hist['Close'])
            hist['Upper_BB'], hist['Lower_BB'], hist['SMA_50'] = calculate_bollinger_bands(hist['Close'])
            hist['SMA_200'] = calculate_moving_average(hist['Close'], 200)
            
            # Prendi l'ultimo valore
            current = hist.iloc[-1]
            
            # Filtro RSI obbligatorio
            if current['RSI'] > 30:
                continue
            
            # Calcola score di mean reversion
            score = mean_reversion_score(
                current, 
                current['Close'],
                current['Upper_BB'],
                current['Lower_BB'],
                current['SMA_50']
            )
            
            # Calcola metriche aggiuntive
            distance_from_sma_50 = ((current['Close'] - current['SMA_50']) / current['SMA_50']) * 100
            distance_from_lower_bb = ((current['Close'] - current['Lower_BB']) / current['Lower_BB']) * 100
            
            # Calcolo momentum recente (ultimi 5 giorni)
            if len(hist) >= 5:
                recent_momentum = ((current['Close'] - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100
            else:
                recent_momentum = 0
            
            result = {
                'ticker': ticker,
                'name': stock.info.get('shortName', ticker),
                'price': round(current['Close'], 2),
                'rsi': round(current['RSI'], 2),
                'sma_50': round(current['SMA_50'], 2),
                'sma_200': round(current['SMA_200'], 2) if pd.notna(current['SMA_200']) else None,
                'lower_bb': round(current['Lower_BB'], 2),
                'upper_bb': round(current['Upper_BB'], 2),
                'distance_from_sma_50_pct': round(distance_from_sma_50, 2),
                'distance_from_lower_bb_pct': round(distance_from_lower_bb, 2),
                'mean_reversion_score': score,
                'recent_momentum_5d': round(recent_momentum, 2),
                'volume_avg_20d': round(hist['Volume'].tail(20).mean(), 0),
                'volume_today': round(current.get('Volume', 0), 0) if pd.notna(current.get('Volume')) else None,
                'analyst_rating': stock.info.get('recommendationKey', 'N/A'),
                'target_price': stock.info.get('targetMeanPrice', None),
                'upside_potential': None
            }
            
            # Calcola upside potential se abbiamo target price
            if result['target_price'] and result['target_price'] > 0:
                result['upside_potential'] = round(((result['target_price'] - current['Close']) / current['Close']) * 100, 2)
            
            results.append(result)
            
        except Exception as e:
            print(f"⚠️ Errore con {ticker}: {str(e)[:50]}")
            continue
    
    # Ordina per score (più alto = migliore opportunità)
    results.sort(key=lambda x: x['mean_reversion_score'], reverse=True)
    
    return results

def format_results_mean_reversion(results, top_n=20):
    """Formatta i risultati per l'invio"""
    if not results:
        return "❌ Nessun titolo trovato con RSI <= 30 e pattern mean reversion."
    
    output = []
    output.append("=" * 70)
    output.append("📈 SCANNER MEAN REVERSION - RSI <= 30 (IPERVENDUTO)")
    output.append("=" * 70)
    output.append(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    output.append(f"Totali trovati: {len(results)}")
    output.append("-" * 70)
    
    for i, res in enumerate(results[:top_n], 1):
        output.append(f"\n{i}. {res['ticker']} - {res['name']}")
        output.append(f"   💰 Prezzo: ${res['price']}")
        output.append(f"   📊 RSI (14): {res['rsi']} {'🟢' if res['rsi'] <= 25 else '🟡'}")
        output.append(f"   📉 SMA 50: ${res['sma_50']} ({res['distance_from_sma_50_pct']}%)")
        if res['sma_200']:
            output.append(f"   📉 SMA 200: ${res['sma_200']}")
        output.append(f"   📊 Lower BB: ${res['lower_bb']}")
        output.append(f"   🎯 Score MR: {res['mean_reversion_score']}/100")
        output.append(f"   📈 Momentum 5D: {res['recent_momentum_5d']}%")
        
        if res['upside_potential']:
            output.append(f"   🎯 Upside vs Target: +{res['upside_potential']}%")
        if res['analyst_rating'] != 'N/A':
            output.append(f"   ⭐ Rating Analisti: {res['analyst_rating']}")
    
    output.append("\n" + "=" * 70)
    output.append("💡 NOTA: RSI <= 30 indica condizioni di ipervenduto.")
    output.append("   Il prezzo potrebbe presto revertire verso la media mobile.")
    output.append("   Confronto con supporti e volumi per conferma.")
    output.append("=" * 70)
    
    return "\n".join(output)

# Lista titoli per scanner (puoi espandere questa lista)
DEFAULT_TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'NFLX', 'AMD', 'INTC',
    'CRM', 'ORCL', 'CSCO', 'ADBE', 'PYPL', 'QCOM', 'TXN', 'AMAT', 'MU', 'AVGO',
    'IBM', 'NOW', 'INTU', 'SNPS', 'CDNS', 'KEYS', 'ANSS', 'GLW', 'CDNS', 'FTNT',
    'PANW', 'FTNT', 'CHKP', 'SPLK', 'ZM', 'DOCU', 'OKTA', 'CRWD', 'NET', 'DKNG',
    'SQ', 'SHOP', 'COIN', 'HOOD', 'PLTR', 'U', 'DDOG', 'SNOW', 'MDB', 'EPAM',
    'WDAY', 'TEAM', 'PATH', 'SPLK', 'ANSS', 'VEEV', 'CDNA', 'EXAS', 'DGX', 'LH',
    'DVA', 'CNC', 'CI', 'HUM', 'ABC', 'MCK', 'CAH', 'MRK', 'LLY', 'JNJ',
    'UNH', 'ABBV', 'PFE', 'AMGN', 'GILD', 'VRTX', 'REGN', 'BIIB', 'MRNA', 'BNTX'
]

if __name__ == "__main__":
    # Test dello scanner
    print("Testing Mean Reversion Scanner...")
    results = scan_mean_reversion(DEFAULT_TICKERS[:30])  # Test con 30 titoli
    formatted = format_results_mean_reversion(results)
    print(formatted)
    
    # Salva anche in JSON per uso programmatico
    with open('mean_reversion_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print("\n💾 Risultati salvati in 'mean_reversion_results.json'")