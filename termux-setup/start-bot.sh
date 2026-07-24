#!/data/data/com.termux/files/usr/bin/bash
cd $HOME/saroatsin-bot

# Auto-update before starting
echo "🔄 Checking for updates..."
git pull origin main --quiet 2>/dev/null && echo "✅ Updated!" || echo "⚠️  Update failed, running current version"

# Load env vars
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo ""
echo "📖 Starting Saroatsin Bot..."
python bot.py
