#!/bin/bash

# Daily scanners script - eseguito ogni mattina alle 5 UTC
cd /root/.openclaw/workspace

# Configurazione Telegram
export TELEGRAM_BOT_TOKEN="8475258962:AAG46md8dRyuL4Koh6YsEyaby7VwKvtj0S4"
export TELEGRAM_CHAT_ID="494745285"

echo "=== $(date) - Running Mean Reversion Scanner ==="
python3 "scripts/strategies/S&P500_Mean_Reversion_scanner.py"

echo "=== $(date) - Running Breakout Scanner (Advanced) ==="
python3 "scripts/strategies/S&P500_Breakout_filters.py"

echo "=== $(date) - Scanners completed ==="