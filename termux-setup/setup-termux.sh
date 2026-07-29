#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# Saroatsin Bot - Termux Setup Script
# ============================================
# ဒီ script ကို Termux ထဲမှာ run ပါ:
#   bash setup-termux.sh
# ============================================

set -e

REPO_URL="https://github.com/whispermmepub/saroatsin-bot.git"
BOT_DIR="$HOME/saroatsin-bot"

echo "📖 Saroatsin Bot Termux Setup"
echo "=============================="

# Step 1: Install dependencies
echo ""
echo "📦 Step 1: Installing packages..."
pkg update -y
pkg install -y python git

# Step 2: Install Python packages
echo ""
echo "🐍 Step 2: Installing Python packages..."
pip install --upgrade pip
pip install "python-telegram-bot[job-queue]>=20.0" "APScheduler>=3.10.0"

# Step 3: Clone or update repo
echo ""
if [ -d "$BOT_DIR/.git" ]; then
    echo "🔄 Step 3: Updating existing repo..."
    cd "$BOT_DIR"
    git pull origin main
else
    echo "📥 Step 3: Cloning repo..."
    rm -rf "$BOT_DIR"
    git clone "$REPO_URL" "$BOT_DIR"
    cd "$BOT_DIR"
fi

# Step 4: Setup environment
echo ""
echo "🔑 Step 4: Environment setup..."

# Prompt for bot token
echo ""
echo "📝 Telegram Bot Token ထည့်ပါ (https://t.me/BotFather က token)"
read -p "TELEGRAM_BOT_TOKEN: " BOT_TOKEN_INPUT

# Create .env file
echo "Creating .env file..."
cat > "$BOT_DIR/.env" << ENVEOF
TELEGRAM_BOT_TOKEN=${BOT_TOKEN_INPUT}
GITHUB_TOKEN=
ENVEOF
echo "✅ .env file created."

echo ""
echo "⚠️  GITHUB_TOKEN ကို ထည့်ချင်ရင် ဒီမှာပြင်ပါ:"
echo "   nano $BOT_DIR/.env"

# Create/update start script
cat > "$BOT_DIR/start.sh" << 'START'
#!/data/data/com.termux/files/usr/bin/bash
cd $HOME/saroatsin-bot

# Load env vars
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "📖 Starting Saroatsin Bot..."
echo "   Press Ctrl+C to stop"
python bot.py
START
chmod +x "$BOT_DIR/start.sh"

# Step 5: Done
echo ""
echo "✅ Setup complete!"
echo ""
echo "=============================="
echo "🚀 To start the bot:"
echo "   cd ~/saroatsin-bot"
echo "   bash start.sh"
echo ""
echo "🔄 To update later:"
echo "   cd ~/saroatsin-bot"
echo "   git pull origin main"
echo "=============================="
