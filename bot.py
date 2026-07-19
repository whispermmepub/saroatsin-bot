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

AUTO_DELETE_SECONDS = 30
from notes import cmd_addnote, cmd_note, cmd_mynote, cmd_delnote, handle_note_reply, notes_callback

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


async def schedule_delete(message, seconds=AUTO_DELETE_SECONDS):
    await asyncio.sleep(seconds)
    try:
        await message.delete()
        logger.info("Auto-deleted message %s", message.message_id)
    except Exception as e:
        logger.warning("Failed to auto-delete message %s: %s", message.message_id, e)


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
        sent = await update.message.reply_text("ban ချင်တဲ့ message ကို reply ပြီး /ban ရိုက်ပါ")
        asyncio.create_task(schedule_delete(sent))


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
        sent = await update.message.reply_text(f"❌ Unban မလုပ်နိုင်ပါ: {e}")
        asyncio.create_task(schedule_delete(sent))


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
    sent = await update.message.reply_text(f"✅ Welcome message ပြင်ပြီးပါပြီ:\n\n{msg}")
    asyncio.create_task(schedule_delete(sent))


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
    sent = await update.message.reply_text(
        "📖 *Saroatsin Bot*\n\n"
        "စာရေးသူ နာမည် (သို့) စာအုပ်နာမည် ရိုက်ထည့်ပါ\n\n"
        "📢 Group ထဲမှာ - @botusername စာရေးသူနာမည်\n\n"
        "/authors - စာရေးသူများ\n"
        "/search <keyword> - ရှာဖွေရန်\n"
        "/add စာရေးသူ - စာအုပ် - link - စာအုပ်အသစ်ထည့်\n"
        "/del စာရေးသူ - စာအုပ် - link - စာအုပ်ဖျက်\n"
        "/ban - ban ရန် (reply)\n"
        "/unban @username - unban ရန်\n"
        "/setwelcome message - welcome message ပြင်\n"
        "/stats - စာရင်းဇယား",
        parse_mode="Markdown",
    )
    asyncio.create_task(schedule_delete(sent))


async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Add a new book. Format: /add author|title|link"""
    if not is_admin(update):
        await update.message.reply_text("❌ Admin သာ ထည့်ခွင့်ရှိပါတယ်")
        return
    if not ctx.args:
        await update.message.reply_text(
            "အသုံးပြုပုံ - /add စာရေးသူ - စာအုပ်နာမည် - link\n\n"
            "ဥပမာ - /add ဇဏ်ခီ - အသစ်စာအုပ် - https://t.me/TheBookR/999?single"
        )
        return
    text = update.message.text.replace("/add", "", 1).strip()
    parts = text.split(" - ")
    if len(parts) < 3:
        await update.message.reply_text("❌ Format: /add စာရေးသူ - စာအုပ် - link")
        return
    author = parts[0].strip()
    title = parts[1].strip()
    link = parts[2].strip()
    if not author or not title or not link:
        await update.message.reply_text("❌ အကုန်ဖြည့်ပါ")
        return
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
        sent = await update.message.reply_text(f"❌ Error: {e}")
        asyncio.create_task(schedule_delete(sent))


