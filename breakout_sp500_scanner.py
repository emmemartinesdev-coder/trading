#!/usr/bin/env python3
"""
Breakout Scanner per S&P 500
Identifica titoli che stanno emergendo da consolidamenti convolumi anomali
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

def calculate_atr(high, low, close, period=14):
    """Calcola l'Average True Range"""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def calculate_volume_ratio(volume, period=20):
    """Calcola rapporto volume vs media"""
    return volume / volume.rolling(window=period).mean()

def calculate_volatility(high, low, close, period=20):
    """Calcola volatilità implicita"""
    returns = close.pct_change()
    volatility = returns.rolling(window=period).std() * np.sqrt(252)
    return volatility

def calculate_support_resistance(high, low, period=20):
    """Identifica supporti e resistenze"""
    rolling_high = high.rolling(window=period).max()
    rolling_low = low.rolling(window=period).min()
    return rolling_high.iloc[-1], rolling_low.iloc[-1]

def breakout_score(row, close, volume_ratio, atr, volatility):
    """Calcola score di breakout"""
    score = 0
    
    # Volume anomalo (breakout richiede volume)
    if volume_ratio > 1.5:
        score += 30
        if volume_ratio > 2.0:
            score += 10
        elif volume_ratio > 2.5:
            score += 5
    
    # Prezzo vicino a massimo recente (resistenza)
    if row['near_resistance']:
        score += 25
        if row['resistance_break']:
            score += 15
    
    # Consolidamento recente (base di accumulo)
    if row['consolidation']:
        score += 15
    
    # Volatilità in espansione
    if row['volatility_expansion']:
        score += 10
    
    # Momentum positivo
    if row['momentum_positive']:
        score += 5
    
    # Volume crescente negli ultimi 3 giorni
    if row['volume_increasing']:
        score += 5
    
    return score

def scan_breakout_sp500(tickers, period='3mo'):
    """
    Scanner principale per pattern breakout S&P 500
    
    Filtri:
    - Prezzo vicino a massimo recente (breakout da resistenza)
    - Volume anomalo (>1.5x media)
    - Consolidamento recente
    - Volatilità in espansione
    """
    results = []
    
    print(f"🔍 Scanner Breakout S&P 500")
    print(f"📊 Analisi di {len(tickers)} titoli...")
    print("-" * 60)
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval='1d')
            
            if len(hist) < 30:
                continue
            
            # Calcola indicatori
            hist['ATR'] = calculate_atr(hist['High'], hist['Low'], hist['Close'])
            hist['Volume_Ratio'] = calculate_volume_ratio(hist['Volume'])
            hist['Volatility'] = calculate_volatility(hist['High'], hist['Low'], hist['Close'])
            hist['SMA_20'] = hist['Close'].rolling(window=20).mean()
            hist['SMA_50'] = hist['Close'].rolling(window=50).mean()
            
            # Calcola metriche di breakout
            current = hist.iloc[-1]
            prev_5 = hist.iloc[-6:-1] if len(hist) >= 6 else hist.iloc[-3:]
            
            # Supporto/Resistenza
            recent_high = hist['High'].tail(20).max()
            recent_low = hist['Low'].tail(20).min()
            
            # Verifica se il prezzo è vicino al massimo recente
            distance_to_high = (recent_high - current['Close']) / recent_high * 100
            near_resistance = distance_to_high < 3  # Entro 3% dal massimo
            
            # Verifica se ha rotto il massimo recente
            resistance_break = current['Close'] > recent_high
            
            # Consolidamento (prezzo in range ristretto)
            if len(hist) >= 20:
                price_range = (hist['Close'].tail(20).max() - hist['Close'].tail(20).min()) / hist['Close'].tail(20).mean() * 100
                consolidation = price_range < 15  # Range sotto il 15%
            else:
                consolidation = False
            
            # Espansione volatilità
            current_volatility = current['Volatility']
            avg_volatility = hist['Volatility'].tail(10).mean()
            volatility_expansion = current_volatility > (avg_volatility * 1.2)
            
            # Momentum positivo
            momentum_positive = current['Close'] > hist['Close'].iloc[-5] if len(hist) >= 5 else False
            
            # Volume crescente negli ultimi giorni
            recent_volume = hist['Volume'].tail(3).mean()
            prev_volume = hist['Volume'].tail(10).iloc[:-3].mean() if len(hist) >= 10 else recent_volume
            volume_increasing = recent_volume > prev_volume
            
            # Breakout score
            row_data = {
                'near_resistance': near_resistance,
                'resistance_break': resistance_break,
                'consolidation': consolidation,
                'volatility_expansion': volatility_expansion,
                'momentum_positive': momentum_positive,
                'volume_increasing': volume_increasing
            }
            
            score = breakout_score(row_data, current['Close'], current['Volume_Ratio'], current['ATR'], current_volatility)
            
            # Calcola metriche aggiuntive
            distance_from_sma_20 = ((current['Close'] - current['SMA_20']) / current['SMA_20']) * 100
            distance_from_sma_50 = ((current['Close'] - current['SMA_50']) / current['SMA_50']) * 100
            
            # Calcolo distanza massimo precedente
            if len(hist) >= 5:
                prev_high_diff = (current['Close'] - hist['High'].iloc[-5]) / current['Close'] * 100
            else:
                prev_high_diff = 0
            
            result = {
                'ticker': ticker,
                'name': stock.info.get('shortName', ticker),
                'price': round(current['Close'], 2),
                'day_change_pct': round(((current['Close'] - hist['Open'].iloc[-1]) / hist['Open'].iloc[-1]) * 100, 2) if pd.notna(hist['Open'].iloc[-1]) else None,
                'volume_ratio': round(current['Volume_Ratio'], 2),
                'atr': round(current['ATR'], 2),
                'volatility': round(current['Volatility'] * 100, 2),
                'sma_20': round(current['SMA_20'], 2),
                'sma_50': round(current['SMA_50'], 2) if pd.notna(current['SMA_50']) else None,
                'recent_high': round(recent_high, 2),
                'recent_low': round(recent_low, 2),
                'distance_to_high_pct': round(distance_to_high, 2),
                'near_resistance': near_resistance,
                'resistance_break': resistance_break,
                'consolidation': consolidation,
                'volatility_expansion': volatility_expansion,
                'momentum_positive': momentum_positive,
                'volume_increasing': volume_increasing,
                'breakout_score': score,
                'distance_from_sma_20_pct': round(distance_from_sma_20, 2),
                'distance_from_sma_50_pct': round(distance_from_sma_50, 2),
                'analyst_rating': stock.info.get('recommendationKey', 'N/A'),
                'target_price': stock.info.get('targetMeanPrice', None),
                'upside_potential': None
            }
            
            # Calcola upside potential
            if result['target_price'] and result['target_price'] > 0:
                result['upside_potential'] = round(((result['target_price'] - current['Close']) / current['Close']) * 100, 2)
            
            results.append(result)
            
        except Exception as e:
            print(f"⚠️ Errore con {ticker}: {str(e)[:50]}")
            continue
    
    # Ordina per score (più alto = migliore opportunità)
    results.sort(key=lambda x: x['breakout_score'], reverse=True)
    
    return results

def format_results_breakout(results, top_n=20):
    """Formatta i risultati per l'invio"""
    if not results:
        return "❌ Nessun titolo trovato con pattern di breakout."
    
    output = []
    output.append("=" * 70)
    output.append("🚀 SCANNER BREAKOUT S&P 500")
    output.append("=" * 70)
    output.append(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    output.append(f"Totali trovati: {len(results)}")
    output.append("-" * 70)
    
    for i, res in enumerate(results[:top_n], 1):
        # Indicatori visivi
        indicators = []
        if res['resistance_break']:
            indicators.append("🟢 Breakout")
        elif res['near_resistance']:
            indicators.append("🟡 Near High")
        if res['volume_ratio'] > 1.5:
            indicators.append(f"📊 Vol {res['volume_ratio']}x")
        if res['consolidation']:
            indicators.append("📐 Consolidamento")
        if res['volatility_expansion']:
            indicators.append("📈 Volatilità ↑")
        if res['momentum_positive']:
            indicators.append("💹 Momentum +")
        
        output.append(f"\n{i}. {res['ticker']} - {res['name']}")
        output.append(f"   💰 Prezzo: ${res['price']}")
        if res['day_change_pct']:
            change_emoji = "🟢" if res['day_change_pct'] > 0 else "🔴"
            output.append(f"   {change_emoji} Oggi: {res['day_change_pct']:+.2f}%")
        output.append(f"   📊 Volume: {res['volume_ratio']}x media")
        output.append(f"   📏 SMA 20: ${res['sma_20']} ({res['distance_from_sma_20_pct']:+.1f}%)")
        if res['sma_50']:
            output.append(f"   📏 SMA 50: ${res['sma_50']} ({res['distance_from_sma_50_pct']:+.1f}%)")
        output.append(f"   🎯 Score Breakout: {res['breakout_score']}/100")
        output.append(f"   🔧 ATR: ${res['atr']} | Volatilità: {res['volatility']}%")
        output.append(f"   🏆 High 20d: ${res['recent_high']} (dist: {res['distance_to_high_pct']}%)")
        
        if indicators:
            output.append(f"   ✨ Segnali: {' | '.join(indicators)}")
        
        if res['upside_potential']:
            output.append(f"   🎯 Upside vs Target: +{res['upside_potential']}%")
        if res['analyst_rating'] != 'N/A':
            output.append(f"   ⭐ Rating: {res['analyst_rating']}")
    
    output.append("\n" + "=" * 70)
    output.append("💡 NOTA: Breakout = prezzo esce da consolidamento con volume.")
    output.append("   Near High = prezzo vicino a resistenza, monitora rottura.")
    output.append("   Volume >1.5x conferma movimento direzionale.")
    output.append("=" * 70)
    
    return "\n".join(output)

# Lista titoli S&P 500 principali
DEFAULT_SP500_TICKERS = [
    # Tech
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AVGO', 'ORCL', 'ADBE',
    'CRM', 'CSCO', 'INTC', 'AMD', 'QCOM', 'TXN', 'IBM', 'NOW', 'INTU', 'SNPS',
    
    # Healthcare
    'UNH', 'JNJ', 'LLY', 'PFE', 'ABBV', 'MRK', 'TMO', 'ABT', 'DHR', 'BMY',
    'AMGN', 'GILD', 'VRTX', 'REGN', 'CVS', 'CI', 'HUM', 'MCK', 'ABC', 'CNC',
    
    # Finance
    'JPM', 'BAC', 'WFC', 'MS', 'GS', 'BLK', 'SCHW', 'AXP', 'V', 'MA',
    'COF', 'USB', 'PNC', 'TFC', 'SPGI', 'CME', 'CB', 'MMC', 'AON', 'MET',
    
    # Consumer
    'WMT', 'COST', 'TGT', 'HD', 'LOW', 'NKE', 'SBUX', 'MCD', 'KO', 'PEP',
    'PG', 'CL', 'KMB', 'GIS', 'K', 'MDLZ', 'KHC', 'HSY', 'DG', 'DLTR',
    
    # Energy & Utilities
    'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'VLO', 'PSX', 'OXY', 'DVN',
    'NEE', 'DUK', 'SO', 'D', 'AEP', 'EXC', 'SRE', 'XEL', 'ED', 'PEG',
    
    # Industrial
    'BA', 'CAT', 'DE', 'MMM', 'GE', 'HON', 'UPS', 'FDX', 'LMT', 'RTX',
    'NSC', 'UNP', 'CSX', 'NEE', 'GD', 'ITW', 'EMR', 'ETN', 'PH', 'ROK',
    
    # Real Estate & Other
    'AMT', 'PLD', 'CCI', 'EQIX', 'PSA', 'SPG', 'O', 'WELL', 'DLR', 'AVB'
]

if __name__ == "__main__":
    # Test dello scanner
    print("Testing Breakout S&P 500 Scanner...")
    results = scan_breakout_sp500(DEFAULT_SP500_TICKERS[:50])  # Test con 50 titoli
    formatted = format_results_breakout(results)
    print(formatted)
    
    # Salva anche in JSON
    with open('breakout_sp500_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print("\n💾 Risultati salvati in 'breakout_sp500_results.json'")