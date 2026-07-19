"""Book Notes commands - simple text-based, no callbacks needed."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from notes_db import add_note, get_notes_for_book, get_user_notes, delete_note

logger = logging.getLogger(__name__)

_stars = lambda n: "⭐" * n + "☆" * (5 - n)


async def cmd_addnote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Step 1: /addnote book - rating  (or /addnote book rating)
    Bot replies asking for note text. User replies to save."""
    text = update.message.text.replace("/addnote", "", 1).strip()
    if not text:
        await update.message.reply_text(
            "📝 Format:\n"
            "/addnote မီဆိုဟင်းချို - 5\n"
            "/addnote မီဆိုဟင်းချို 5\n"
            "ပြီးရင် reply မှာ note စာထည့်ပါ"
        )
        return

    # Try " - " separator first
    parts_dash = text.split(" - ")
    if len(parts_dash) >= 2:
        book_title = parts_dash[0].strip()
        try:
            rating = max(1, min(5, int(parts_dash[1].strip())))
        except ValueError:
            await update.message.reply_text("❌ Rating 1-5 ထဲက ထည့်ပါ")
            return
    else:
        # Space-separated: /addnote book 5
        tokens = text.split()
        if len(tokens) < 2:
            await update.message.reply_text("❌ Format: /addnote စာအုပ် rating")
            return
        rating_idx = None
        for i, t in enumerate(tokens):
            if t.isdigit() and 1 <= int(t) <= 5:
                rating_idx = i
        if rating_idx is None:
            await update.message.reply_text("❌ Rating 1-5 ထဲက ထည့်ပါ")
            return
        book_title = " ".join(tokens[:rating_idx]).strip()
        if not book_title:
            await update.message.reply_text("❌ စာအုပ်နာမည် ထည့်ပါ")
            return
        rating = max(1, min(5, int(tokens[rating_idx])))

    # Save pending state, wait for user reply
    ctx.user_data["pending_note"] = {
        "book_title": book_title,
        "rating": rating,
    }
    stars = _stars(rating)
    await update.message.reply_text(
        f"📝 *{book_title}* အတွက် note content ကို reply ပြီးရေးပါ\n"
        f"Rating: {stars}",
        parse_mode="Markdown",
    )


async def handle_note_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Step 2: Handle reply text to save note. Returns True if handled."""
    if "pending_note" not in ctx.user_data:
        return False

    pending = ctx.user_data.pop("pending_note")
    note_text = update.message.text.strip()
    if not note_text:
        await update.message.reply_text("❌ Note content ထည့်ပါ")
        return True

    user = update.effective_user
    book_title = pending["book_title"]
    rating = pending["rating"]
    note_id = add_note(user.id, user.username or user.first_name, book_title, rating, note_text)
    stars = _stars(rating)
    await update.message.reply_text(
        f"✅ Note saved!\n📖 {book_title}\nRating: {stars}\n📝 {note_text}\n🆔 #{note_id}"
    )
    return True


async def cmd_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show notes for a book: /note book_title"""
    if not ctx.args:
        await update.message.reply_text("🔍 Format: /note စာအုပ်နာမည်")
        return
    book_title = " ".join(ctx.args)
    notes = get_notes_for_book(book_title)
    if not notes:
        await update.message.reply_text(f"📭 \"{book_title}\" အတွက် note မရှိသေးပါ")
        return
    if len(notes) == 1:
        n = notes[0]
        username = n.get("username", "Anonymous")
        stars = _stars(n["rating"])
        msg = f"📖 *{book_title}*\n\n👤 {username} {stars}\n\n{n["note_text"]}"
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        lines = [f"📖 *{book_title}* — {len(notes)} notes\n"]
        for n in notes:
            username = n.get("username", "Anonymous")
            stars = _stars(n["rating"])
            text_preview = n["note_text"][:80] + "..." if len(n["note_text"]) > 80 else n["note_text"]
            lines.append(f"• {username} {stars} — {text_preview}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_mynote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show user's own notes: /mynote"""
    user_id = update.effective_user.id
    notes = get_user_notes(user_id)
    if not notes:
        await update.message.reply_text("📭 သင့် note များ မရှိသေးပါ")
        return
    lines = ["📝 *Your Notes*\n"]
    for n in notes:
        stars = _stars(n["rating"])
        lines.append(f"📖 {n['book_title']} {stars}")
        if n["note_text"]:
            lines.append(f"   {n['note_text'][:50]}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_delnote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Delete a note: /delnote note_id"""
    if not ctx.args:
        await update.message.reply_text("🗑️ Format: /delnote note_id\nID ကို /mynote မှာ ကြည့်ပါ")
        return
    try:
        note_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID ကို ဂဏန်းထည့်ပါ")
        return
    user_id = update.effective_user.id
    if delete_note(note_id, user_id=user_id):
        await update.message.reply_text(f"✅ Note #{note_id} ဖျက်ပြီးပါပြီ")
    else:
        await update.message.reply_text("❌ Note မတွေ့ပါ (ကိုယ့် noteသာ ဖျက်နိုင်ပါတယ်)")
