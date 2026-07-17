"""Saroatsin Telegram Bot - Search books by author name or title."""

import os
import re
import signal
import logging
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
WEBSITE_URL = "https://whispermmepub.github.io/saroatsin-bot/"
RESULTS_PER_PAGE = 10

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Globals ─────────────────────────────────────────────
BOOKS = []
BOOKS_BY_AUTHOR = {}
BOT_USERNAME = ""


def load_books():
    global BOOKS, BOOKS_BY_AUTHOR
    logger.info("Fetching books from %s ...", WEBSITE_URL)
    BOOKS = fetch_books(WEBSITE_URL)
    logger.info("Loaded %d books from %d authors.", len(BOOKS), len({b["author"] for b in BOOKS}))
    BOOKS_BY_AUTHOR = {}
    for b in BOOKS:
        key = b["author"].lower()
        BOOKS_BY_AUTHOR.setdefault(key, []).append(b)


# ── Handlers ────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Saroatsin Bot*\n\n"
        "စာရေးသူ နာမည် (သို့) စာအုပ်နာမည် ရိုက်ထည့်ပါ\n"
        "ထို့နောက် စာအုပ်များ ပြန်လည်ပြသပါမည်\n\n"
        "💡 ဥပမာ - *ဇဏ်ခီ*\n"
        "💡 ဥပမာ - *ချစ်တီး*\n\n"
        "📢 Group ထဲမှာ - @botusername စာရေးသူနာမည်\n\n"
        "/authors - စာရေးသူများ စာရင်း\n"
        "/search <keyword> - ရှာဖွေရန်",
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
        # In groups, only respond when the bot is mentioned
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
        BotCommand("refresh", "ဒေတာပြန်ဖတ်ရန်"),
    ]
    await application.bot.set_my_commands(commands)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling an update:", exc_info=context.error)


def main():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        print("Error: Set TELEGRAM_BOT_TOKEN env var first.")
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
    app.add_handler(CommandHandler("refresh", cmd_refresh))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # Ignore SIGTERM so nohup/systemd can manage lifecycle
    signal.signal(signal.SIGTERM, signal.SIG_IGN)

    logger.info("Bot is starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
