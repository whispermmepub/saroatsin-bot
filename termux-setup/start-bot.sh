#!/data/data/com.termux/files/usr/bin/bash
pkill -9 -f python 2>/dev/null
cd ~/saroatsin-bot && git pull
export TELEGRAM_BOT_TOKEN="8644464116:AAGQqzYiRGhTcpOit47AAJW845sBfCSZiX8"
python bot.py
