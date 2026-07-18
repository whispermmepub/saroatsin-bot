"""Saroatsin Telegram Bot - Search books by author name or title."""

import os
import re
import json
import base64
import logging
import urllib.request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from scraper import fetch_books, search_books, get_authors

# ── Config ──────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
DATA_URL = "https://raw.githubusercontent.com/whispermmepub/wow-books/main/data.json"
GITHUB_REPO = "whispermmepub/wow-books"
DATA_PATH = "data.json"
RESULTS_PER_PAGE = 10
ADMIN_USERNAMES = ["wowepub"]

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Globals ─────────────────────────────────────────────
BOOKS = []
BOOKS_BY_AUTHOR = {}
RAW_DATA = []
BOT_USERNAME = ""


def load_books():
    global BOOKS, BOOKS_BY_AUTHOR, RAW_DATA
    logger.info("Fetching books from %s ...", DATA_URL)
    books, raw = fetch_books(DATA_URL)
    BOOKS = books
    RAW_DATA = raw
    logger.info("Loaded %d books from %d authors.", len(BOOKS), len({b["author"] for b in BOOKS}))
    BOOKS_BY_AUTHOR = {}
    for b in BOOKS:
        key = b["author"].lower()
        BOOKS_BY_AUTHOR.setdefault(key, []).append(b)


def push_to_github(data):
    """Push updated data.json to GitHub."""
    import subprocess
    token = os.environ.get("GITHUB_TOKEN", "")

    content = json.dumps(data, ensure_ascii=False, indent=2)

    # Get current file SHA
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Get current SHA
    req = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        current = json.loads(resp.read().decode("utf-8"))
        sha = current["sha"]

    # Update file
    payload = json.dumps({
        "message": f"Add book via Telegram bot",
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "sha": sha,
    }).encode("utf-8")

    req = urllib.request.Request(api_url, data=payload, headers=headers, method="PUT")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status == 200


def is_admin(update):
    """Check if user is admin."""
    user = update.effective_user
    if user.username in ADMIN_USERNAMES:
        return True
    return False


# ── Handlers ────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Saroatsin Bot*\n\n"
        "စာရေးသူ နာမည် (သို့) စာအုပ်နာမည် ရိုက်ထည့်ပါ\n"
        "ထို့နောက် စာအုပ်များ ပြန်လည်ပြသပါမည်\n\n"
        "💡 ဥပမာ - *ဇဏ်ခီ*\n\n"
        "📢 Group ထဲမှာ - @botusername စာရေးသူနာမည်\n\n"
        "/authors - စာရေးသူများ စာရင်း\n"
        "/search <keyword> - ရှာဖွေရန်\n"
        "/add author|title|link - စာအုပ်အသစ်ထည့်ရန်\n"
        "/stats - စာရင်းဇယား",
        parse_mode="Markdown",
    )


async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Add a new book. Format: /add author|title|link"""
    if not is_admin(update):
        await update.message.reply_text("❌ Admin သာ ထည့်ခွင့်ရှိပါတယ်")
        return

    if not ctx.args:
        await update.message.reply_text(
            "အသုံးပြုပုံ - /add စာရေးသူ|စာအုပ်နာမည်|link\n\n"
            "ဥပမာ - /add ဇဏ်ခီ|အသစ်စာအုပ်|https://t.me/TheBookR/999?single"
        )
        return

    raw_input = " ".join(ctx.args)
    parts = raw_input.split("|")

    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Format: /add စာရေးသူ|စာအုပ်နာမည်|link\n"
            "pipe (|) နဲ့ ခွဲထည့်ပါ"
        )
        return

    author = parts[0].strip()
    title = parts[1].strip()
    link = parts[2].strip()

    if not author or not title or not link:
        await update.message.reply_text("❌ အကုန်ဖြည့်ပါ — စာရေးသူ|စာအုပ်|link")
        return

    await update.message.reply_text("⏳ GitHub ထဲ ထည့်နေပါတယ်...")

    # Add to RAW_DATA
    author_found = False
    for entry in RAW_DATA:
        if entry["author"].lower() == author.lower():
            entry["books"].append({"title": title, "link": link})
            author_found = True
            break

    if not author_found:
        RAW_DATA.append({
            "author": author,
            "books": [{"title": title, "link": link}]
        })

    # Push to GitHub
    try:
        success = push_to_github(RAW_DATA)
        if success:
            load_books()
            await update.message.reply_text(
                f"✅ ထည့်ပြီးပါပြီ!\n\n"
                f"✍️ စာရေးသူ: {author}\n"
                f"📖 စာအုပ်: {title}\n"
                f"🔗 {link}\n\n"
                f"📊 စုစုပေါင်း {len(BOOKS)} စာအုပ် ရှိပါပြီ"
            )
        else:
            await update.message.reply_text("❌ GitHub push မအောင်မြင်ပါ")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not BOOKS:
        load_books()
    author_count = len({b["author"] for b in BOOKS})
    await update.message.reply_text(
        f"📊 *Saroatsin Bot Stats*\n\n"
        f"📖 စာအုပ်: {len(BOOKS)}\n"
        f"✍️ စာရေးသူ: {author_count}",
        parse_mode="Markdown",
    )


async def cmd_authors(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not BOOKS:
        load_books()
    authors = get_authors(BOOKS)
    page = 0
    text, markup = _author_page(authors, page)
    await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def cmd_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("အသုံးပြုပုံ - /search < keyword >")
        return
    query = " ".join(ctx.args)
    await _do_search(update, ctx, query)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle plain text in private chat and bot mentions in groups."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    is_group = update.effective_chat.type in ("group", "supergroup")

    if is_group:
        mention_pattern = rf"@{re.escape(BOT_USERNAME)}\b\s*"
        match = re.search(mention_pattern, text, re.IGNORECASE)
        if not match:
            return
        query = text[match.end():].strip()
        if not query:
            await update.message.reply_text(
                "စာရေးသူ နာမည် (သို့) စာအုပ်နာမည် ထည့်ပါ\n"
                f"ဥပမာ - @{BOT_USERNAME} ဇဏ်ခီ"
            )
            return
    else:
        query = text

    if not query:
        return
    await _do_search(update, ctx, query)


async def _do_search(update, ctx, query):
    if not BOOKS:
        load_books()

    key = query.lower().strip()
    results = []

    if key in BOOKS_BY_AUTHOR:
        results = BOOKS_BY_AUTHOR[key]
    else:
        results = search_books(BOOKS, query)

    if not results:
        await update.message.reply_text(
            f"❌ \"{query}\" နှင့် ကိုက်ညီသော စာအုပ် မတွေ့ပါ။\n"
            f"စာရေးသူ သို့မဟုတ် စာအုပ်နာမည် ပြန်စစ်ပါ။"
        )
        return

    page = 0
    text, markup = _results_page(results, query, page)
    await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")


def _results_page(results, query, page):
    total = len(results)
    start = page * RESULTS_PER_PAGE
    end = min(start + RESULTS_PER_PAGE, total)
    page_items = results[start:end]
    total_pages = (total + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE

    lines = [f"🔍 *{query}* — {total} စာအုပ်တွေ့ပါသည်\n"]
    for i, b in enumerate(page_items, start=start + 1):
        lines.append(f"{i}. {b['title']}")

    text = "\n".join(lines)

    buttons = []
    for b in page_items:
        buttons.append([
            InlineKeyboardButton(f"📖 {b['title'][:30]}", url=b["link"])
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ နောက်တစ်မျက်နှာ", callback_data=f"r|{query}|{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("နောက်တစ်မျက်နှာ ▶️", callback_data=f"r|{query}|{page + 1}"))
    if nav:
        buttons.append(nav)

    markup = InlineKeyboardMarkup(buttons) if buttons else None
    return text, markup


def _author_page(authors, page):
    total = len(authors)
    start = page * RESULTS_PER_PAGE
    end = min(start + RESULTS_PER_PAGE, total)
    page_items = authors[start:end]
    total_pages = (total + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE

    lines = [f"✍️ *စာရေးသူများ* — {total} ဦး\n"]
    for name, count in page_items:
        lines.append(f"• {name} ({count})")

    text = "\n".join(lines)

    buttons = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ နောက်တစ်မျက်နှာ", callback_data=f"a|{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("နောက်တစ်မျက်နှာ ▶️", callback_data=f"a|{page + 1}"))
    if nav:
        buttons.append(nav)

    markup = InlineKeyboardMarkup(buttons) if buttons else None
    return text, markup


async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data:
        return

    parts = data.split("|", 2)

    if parts[0] == "r" and len(parts) == 3:
        search_query = parts[1]
        page = int(parts[2])
        results = search_books(BOOKS, search_query)
        if not results:
            await query.edit_message_text("ဒေတာ ပြန်လည်ရှာဖွေနေပါသည်...")
            return
        text, markup = _results_page(results, search_query, page)
        await query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")

    elif parts[0] == "a" and len(parts) == 2:
        page = int(parts[1])
        authors = get_authors(BOOKS)
        text, markup = _author_page(authors, page)
        await query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")


async def cmd_refresh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    load_books()
    await update.message.reply_text(f"✅ {len(BOOKS)} စာအုပ် ပြန်လည်ဖတ်ရှုပြီးပါပြီ")


async def post_init(application: Application):
    global BOT_USERNAME
    me = await application.bot.get_me()
    BOT_USERNAME = me.username
    logger.info("Bot username: @%s", BOT_USERNAME)

    commands = [
        BotCommand("start", "စတင်ရန်"),
        BotCommand("authors", "စာရေးသူများ"),
        BotCommand("search", "စာအုပ်ရှာရန်"),
        BotCommand("add", "စာအုပ်အသစ်ထည့်ရန်"),
        BotCommand("refresh", "ဒေတာပြန်ဖတ်ရန်"),
        BotCommand("stats", "စာရင်းဇယား"),
    ]
    await application.bot.set_my_commands(commands)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling an update:", exc_info=context.error)


def main():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        return

    load_books()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("authors", cmd_authors))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("refresh", cmd_refresh))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    logger.info("Bot is starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
