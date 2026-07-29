#!/data/data/com.termux/files/usr/bin/bash
cd ~/saroatsin-bot && git pull

# Load environment variables from .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# TELEGRAM_BOT_TOKEN must be set in .env file
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "Error: TELEGRAM_BOT_TOKEN not found in .env file"
    echo "Please add: TELEGRAM_BOT_TOKEN=your_bot_token_here"
    exit 1
fi

pkill -9 -f python 2>/dev/null
python bot.py
