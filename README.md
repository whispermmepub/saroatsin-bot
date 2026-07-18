# Saroatsin Telegram Bot

whispermmepub.github.io/saroatsin-bot/ ကို Telegram Bot ဖြင့် ရှာဖွေနိုင်သည့် Bot

## Features

- စာရေးသူ နာမည် ရိုက်ထည့်ပါ → စာအုပ်များ ပြန်လည်ပြသပါမည်
- စာအုပ်နာမည် ရိုက်ထည့်ပါ → သက်ဆိုင်ရာ စာအုပ်များ ပြန်လည်ပြသပါမည်
- စာအုပ် link နှိပ်ရင် မူရင်း Telegram channel ထဲ ရောက်သွားပါမည်
- Group ထဲမှာ @botusername mention ပြီး ရှာနိုင်ပါသည်

## Deploy to Railway (Free)

1. GitHub ထဲ Push ပါ
2. https://railway.app မှာ Free account ဖွင့်ပါ
3. **New Project → Deploy from GitHub Repo** နှိပ်ပါ
4. GitHub repo ကို Connect ပါ
5. Variables tab ထဲမှာ:
   - `TELEGRAM_BOT_TOKEN` = သင့် bot token
6. Deploy ဖြစ်သွားပါမည်

24/7 အဆက်မပြတ် run ပါမည်။

## Local Run

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="your-token-here"
python bot.py
```
