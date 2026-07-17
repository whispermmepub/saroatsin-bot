# Saroatsin Telegram Bot

whispermmepub.github.io/saroatsin-bot/ ကို Telegram Bot ဖြင့် ရှာဖွေနိုင်သည့် Bot

## Features

- စာရေးသူ နာမည် ရိုက်ထည့်ပါ → စာအုပ်များ ပြန်လည်ပြသပါမည်
- စာအုပ်နာမည် ရိုက်ထည့်ပါ → သက်ဆိုင်ရာ စာအုပ်များ ပြန်လည်ပြသပါမည်
- စာအုပ် link နှိပ်ရင် မူရင်း Telegram channel ထဲ ရောက်သွားပါမည်
- `/authors` - စာရေးသူ ၁၈၃ ဦးအားလုံး စာရင်း
- `/search <keyword>` - keyword ဖြင့် ရှာဖွေရန်
- `/refresh` - ဒေတာ ပြန်လည်ဖတ်ရှုရန်

## Setup

### 1. BotFather မှ Bot Token ယူပါ

1. Telegram ထဲ `@BotFather` ကို ရှာပါ
2. `/newbot` command ရိုက်ပါ
3. Bot name နှင့် username ထည့်ပါ
4. Token ကို copy ယူပါ

### 2. Run Bot

```bash
# Token set ပါ
export TELEGRAM_BOT_TOKEN="your-bot-token-here"

# Install dependencies
pip install python-telegram-bot

# Run
python bot.py
```

## Usage

1. Bot ကို `/start` ဖြင့် စတင်ပါ
2. စာရေးသူ နာမည် ရိုက်ထည့်ပါ (ဥပမာ - `ဇဏ်ခီ`)
3. စာအုပ်များ list ပြလာပါမည်
4. စာအုပ် link နှိပ်ရင် Telegram channel ထဲ ရောက်သွားပါမည်

## File Structure

```
bot/
├── bot.py          # Telegram bot main code
├── scraper.py      # Website scraper
├── requirements.txt
└── README.md
```
