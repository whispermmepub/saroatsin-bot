"""Saroatsin Telegram Bot - Search books + Group management."""

import os
import random
import re
import json
import base64
import logging
import asyncio
import urllib.request
from urllib.parse import urlparse
from datetime import datetime
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
    ChatMemberHandler,
    ContextTypes,
    filters,
)

from scraper import fetch_books, search_books, get_authors
from notes import (
    cmd_addnote, cmd_note, cmd_mynote, cmd_delnote,
    cmd_searchnote, notes_callback, handle_note_reply,
)

# ── Config ──────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
DATA_URL = "https://raw.githubusercontent.com/whispermmepub/wow-books/main/data.json"
GITHUB_REPO = "whispermmepub/wow-books"
DATA_PATH = "data.json"
RESULTS_PER_PAGE = 10
ADMIN_USERNAMES = ["wowepub"]
NOTES_ENABLED = True

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
WELCOME_MSGS = [
    "🎉 {name} ကို ကြိုဆိုပါတယ်!",
    "🌟 {name} welcome! စာအုပ်တွေ ဖတ်ချင်ရင် bot ကို သုံးကြည့်ပါ",
    "👋 {name} ပါဝင်လာပါပြီ! စာရေးသူ/စာအုပ် ရှာဖို့ bot ကို mention ပါ",
]
GOOD_MORNING = "🌅 မင်္ဂလာနံနက်ခင်းပါ! ဒီနေ့ ဘယ်စာအုပ်ဖတ်မလဲ?"
GOOD_NIGHT = "🌙 ညချမ်းပါ! စာအုပ်ကောင်းတစ်အုပ်နဲ့ အနားယူပါ"


def load_books():
    global BOOKS, BOOKS_BY_AUTHOR, RAW_DATA
    logger.info("Fetching books from %s ...", DATA_URL)
    try:
        books, raw = fetch_books(DATA_URL)
        BOOKS = books
        RAW_DATA = raw
        logger.info("Loaded %d books from %d authors.", len(BOOKS), len({b["author"] for b in BOOKS}))
        BOOKS_BY_AUTHOR = {}
        for b in BOOKS:
            key = b["author"].lower()
            BOOKS_BY_AUTHOR.setdefault(key, []).append(b)
    except Exception as e:
        logger.error("Failed to load books: %s", e)
        if not BOOKS:
            logger.warning("No books loaded, using empty list")


def push_to_github(data):
    """Push updated data.json to GitHub."""
    token = os.environ.get("GITHUB_TOKEN", "")
    content = json.dumps(data, ensure_ascii=False, indent=2)
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    req = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        current = json.loads(resp.read().decode("utf-8"))
        sha = current["sha"]
    payload = json.dumps({
        "message": "Add book via Telegram bot",
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "sha": sha,
    }).encode("utf-8")
    req = urllib.request.Request(api_url, data=payload, headers=headers, method="PUT")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status == 200


def is_admin(update):
    user = update.effective_user
    return user.username in ADMIN_USERNAMES


# ── Group Management ─────────────────────────────────────
async def on_new_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Welcome new members."""
    if not update.message or not update.message.new_chat_members:
        return
    chat_id = update.effective_chat.id
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        name = member.first_name or member.username or "friend"
        msg = random.choice(WELCOME_MSGS).format(name=name)
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning("Cannot delete service msg: %s", e)
        try:
            await ctx.bot.send_message(chat_id=chat_id, text=msg)
        except Exception as e:
            logger.error("Welcome msg failed for %s: %s", chat_id, e)


async def on_left_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Goodbye message."""
    if not update.message or not update.message.left_chat_member:
        return
    member = update.message.left_chat_member
    if member.is_bot:
        return
    name = member.first_name or member.username or "friend"
    chat_id = update.effective_chat.id
    try:
        await update.message.delete()
    except Exception as e:
        logger.warning("Cannot delete service msg: %s", e)
    try:
        await ctx.bot.send_message(chat_id=chat_id, text=f"👋 {name} ထွက်သွားပါပြီ")
    except Exception as e:
        logger.error("Goodbye msg failed: %s", e)




# ── Spam Protection ──────────────────────────────────────
ALLOWED_DOMAINS = [
    "facebook.com", "fb.com", "fb.watch",
    "youtube.com", "youtu.be",
    "twitter.com", "x.com",
    "tiktok.com",
    "blogspot.com", "whispermmepub.github.io", "saroatsin.com",
    "wikipedia.org",
]

ALLOWED_TG_CHANNELS = ["TheBookR", "refthebook"]

BLOCKED_DOMAINS = [
    "google.com", "google.co", "bit.ly", "tinyurl.com",
    "t.me",
    "pornhub.com", "xvideos.com", "xnxx.com", "xhamster.com",
    "redtube.com", "youporn.com", "brazzers.com",
]

URL_RE = re.compile(r"https?://\S+")


def is_url_allowed(url: str) -> bool:
    """Check if a URL should be allowed (not spam)."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()

    # Allowed domains
    if any(d in host for d in ALLOWED_DOMAINS):
        return True

    # Allowed Telegram channels
    if host == "t.me":
        for ch in ALLOWED_TG_CHANNELS:
            if path.startswith("/" + ch.lower()) or path.startswith("/" + ch.lower() + "/"):
                return True
        return False

    # Blocked domains
    if any(d in host for d in BLOCKED_DOMAINS):
        return False

    return True


async def spam_filter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Auto-delete messages with non-allowed links in groups."""
    if not update.message or not update.message.text:
        return
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        return
    text = update.message.text or ""
    urls = URL_RE.findall(text)
    if not urls:
        return
    for url in urls:
        if is_url_allowed(url):
            continue
        logger.info("Spam detected in %s: %s", chat.id, url)
        try:
            await update.message.delete()
            logger.info("Spam deleted successfully")
        except Exception as e:
            logger.error("Failed to delete spam: %s", e)
        return


async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ban a user. Reply to user's message with /ban"""
    if not is_admin(update):
        await update.message.reply_text("❌ Admin သာ ban ခွင့်ရှိပါတယ်")
        return

    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        try:
            await ctx.bot.ban_chat_member(
                chat_id=update.effective_chat.id,
                user_id=user.id,
            )
            await update.message.reply_text(f"🚫 {user.first_name} ကို ban ပြီးပါပြီ")
        except Exception as e:
            await update.message.reply_text(f"❌ Ban မလုပ်နိုင်ပါ: {e}")
    else:
        await update.message.reply_text("ban ချင်တဲ့ message ကို reply ပြီး /ban ရိုက်ပါ")


async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Unban a user by user ID or username."""
    if not is_admin(update):
        await update.message.reply_text("❌ Admin သာ unban ခွင့်ရှိပါတယ်")
        return
    if not ctx.args:
        await update.message.reply_text("အသုံးပြုပုံ - /unban @username")
        return
    target = ctx.args[0]
    try:
        if target.startswith("@"):
            chat_member = await ctx.bot.get_chat_member(update.effective_chat.id, target)
            user_id = chat_member.user.id
        else:
            user_id = int(target)
        await ctx.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user_id,
        )
        await update.message.reply_text(f"✅ {target} ကို unban ပြီးပါပြီ")
    except Exception as e:
        await update.message.reply_text(f"❌ Unban မလုပ်နိုင်ပါ: {e}")


async def cmd_setwelcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Set custom welcome message. /setwelcome မင်္ဂလာပါ {name}"""
    if not is_admin(update):
        await update.message.reply_text("❌ Admin သာ setting ပြင်ခွင့်ရှိပါတယ်")
        return
    if not ctx.args:
        await update.message.reply_text(
            "အသုံးပြုပုံ - /setwelcome မင်္ဂလာပါ {name} စာအုပ်တွေ ဖတ်ပါ\n\n"
            "{name} = ဝင်လာတဲ့သူနာမည် အလိုလိုပါမယ်"
        )
        return
    msg = " ".join(ctx.args)
    WELCOME_MSGS.clear()
    WELCOME_MSGS.append(msg)
    await update.message.reply_text(f"✅ Welcome message ပြင်ပြီးပါပြီ:\n\n{msg}")


# ── Scheduled Messages ──────────────────────────────────
async def good_morning(ctx: ContextTypes.DEFAULT_TYPE):
    """Send morning greeting to all groups."""
    chat_ids = ctx.bot_data.get("group_chat_ids", [])
    for chat_id in chat_ids:
        try:
            await ctx.bot.send_message(chat_id=chat_id, text=GOOD_MORNING)
        except Exception as e:
            logger.error("Morning msg failed for %s: %s", chat_id, e)


async def good_night(ctx: ContextTypes.DEFAULT_TYPE):
    """Send night greeting to all groups."""
    chat_ids = ctx.bot_data.get("group_chat_ids", [])
    for chat_id in chat_ids:
        try:
            await ctx.bot.send_message(chat_id=chat_id, text=GOOD_NIGHT)
        except Exception as e:
            logger.error("Night msg failed for %s: %s", chat_id, e)


async def track_group(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Track group chat IDs for scheduled messages."""
    if update.effective_chat.type in ("group", "supergroup"):
        chat_ids = ctx.bot_data.setdefault("group_chat_ids", [])
        cid = update.effective_chat.id
        if cid not in chat_ids:
            chat_ids.append(cid)
            logger.info("Tracked group %s for scheduled messages", cid)


# ── Book Commands ────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Saroatsin Bot*\n\n"
        "စာရေးသူ နာမည် (သို့) စာအုပ်နာမည် ရိုက်ထည့်ပါ\n\n"
        "📢 Group ထဲမှာ - @botusername စာရေးသူနာမည်\n\n"
        "/authors - စာရေးသူများ\n"
        "/search <keyword> - ရှာဖွေရန်\n"
        "/add author|title|link - စာအုပ်အသစ်ထည့်\n"
        "/ban - ban ရန် (reply)\n"
        "/unban @username - unban ရန်\n"
        "/setwelcome message - welcome message ပြင်\n"
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
        await update.message.reply_text("❌ Format: /add စာရေးသူ|စာအုပ်|link")
        return
    author = parts[0].strip()
    title = parts[1].strip()
    link = parts[2].strip()
    if not author or not title or not link:
        await update.message.reply_text("❌ အကုန်ဖြည့်ပါ")
        return
    await update.message.reply_text("⏳ GitHub ထဲ ထည့်နေပါတယ်...")
    author_found = False
    for entry in RAW_DATA:
        if entry["author"].lower() == author.lower():
            entry["books"].append({"title": title, "link": link})
            author_found = True
            break
    if not author_found:
        RAW_DATA.append({"author": author, "books": [{"title": title, "link": link}]})
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
    if not update.message or not update.message.text:
        return
    # Handle pending note reply
    if NOTES_ENABLED and "pending_note" in ctx.user_data:
        handled = await handle_note_reply(update, ctx)
        if handled:
            return
    text = update.message.text.strip()
    is_group = update.effective_chat.type in ("group", "supergroup")

    # Track group for scheduled messages
    if is_group:
        chat_ids = ctx.bot_data.setdefault("group_chat_ids", [])
        if update.effective_chat.id not in chat_ids:
            chat_ids.append(update.effective_chat.id)

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
        await update.message.reply_text("❌ စာအုပ်ဒေတာ မရှိသေးပါ။ /refresh ရိုက်ပါ")
        return
    key = query.lower().strip()
    results = []
    if key in BOOKS_BY_AUTHOR:
        results = BOOKS_BY_AUTHOR[key]
    else:
        results = search_books(BOOKS, query)
    if not results:
        await update.message.reply_text(
            f"❌ \"{query}\" နှင့် ကိုက်ညီသော စာအုပ် မတွေ့ပါ။"
        )
        return
    page = 0
    text, markup = _results_page(results, query, page)
    if markup:
        close_btn = [InlineKeyboardButton("❌ ပိတ်ရန်", callback_data="searchclose")]
        markup.inline_keyboard.append(close_btn)
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
        buttons.append([InlineKeyboardButton(f"📖 {b['title'][:30]}", url=b["link"])])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"r|{query}|{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"r|{query}|{page + 1}"))
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
        nav.append(InlineKeyboardButton("◀️", callback_data=f"a|{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"a|{page + 1}"))
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

    # Schedule morning (7 AM Myanmar = 00:30 UTC) and night (9 PM Myanmar = 14:30 UTC)
    from datetime import timezone, timedelta, time as dt_time
    MYANMAR_TZ = timezone(timedelta(hours=6, minutes=30))
    job_queue = application.job_queue
    job_queue.run_daily(good_morning, time=dt_time(hour=7, minute=0, tzinfo=MYANMAR_TZ))
    job_queue.run_daily(good_night, time=dt_time(hour=21, minute=0, tzinfo=MYANMAR_TZ))

    commands = [
        BotCommand("start", "စတင်ရန်"),
        BotCommand("authors", "စာရေးသူများ"),
        BotCommand("search", "စာအုပ်ရှာရန်"),
        BotCommand("add", "စာအုပ်အသစ်ထည့်ရန်"),
        BotCommand("ban", "Ban ရန်"),
        BotCommand("unban", "Unban ရန်"),
        BotCommand("setwelcome", "Welcome message ပြင်ရန်"),
        BotCommand("refresh", "ဒေတာပြန်ဖတ်ရန်"),
        BotCommand("stats", "စာရင်းဇယား"),
        BotCommand("addnote", "Note ရေးရန်"),
        BotCommand("note", "စာအုပ် Note ကြည့်ရန်"),
        BotCommand("mynote", "ကိုယ့် Note များ"),
        BotCommand("delnote", "Note ဖျက်ရန်"),
        BotCommand("searchnote", "Note ရှာရန်"),
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

    # Track groups for scheduled messages
    app.add_handler(MessageHandler(filters.ALL, track_group), group=-1)

    # Book commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("authors", cmd_authors))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("refresh", cmd_refresh))
    app.add_handler(CommandHandler("stats", cmd_stats))

    # Group management commands
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("setwelcome", cmd_setwelcome))

    # Group events
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_member))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, on_left_member))

    # Notes commands
    if NOTES_ENABLED:
        from notes_db import init_db
        init_db()
        app.add_handler(CommandHandler("addnote", cmd_addnote))
        app.add_handler(CommandHandler("note", cmd_note))
        app.add_handler(CommandHandler("mynote", cmd_mynote))
        app.add_handler(CommandHandler("delnote", cmd_delnote))
        app.add_handler(CommandHandler("searchnote", cmd_searchnote))
        app.add_handler(CallbackQueryHandler(notes_callback))

    # Track groups + search
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, spam_filter), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text), group=2)

    logger.info("Bot is starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
