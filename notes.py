"""Book Notes commands - simple text-based, no callbacks needed."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from notes_db import add_note, get_notes_for_book, get_user_notes, delete_note

logger = logging.getLogger(__name__)

_stars = lambda n: "⭐" * n + "☆" * (5 - n)


async def cmd_addnote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Add a note: /addnote book - rating - note text"""
    text = update.message.text.replace("/addnote", "", 1).strip()
    if not text:
        await update.message.reply_text(
            "📝 Format: /addnote စာအုပ်နာမည် - rating - note\n"
            "ဥပမာ: /addnote မီဆိုဟင်းချို - 5 - ကောင်းတယ်"
        )
        return
    parts = text.split(" - ")
    if len(parts) < 2:
        await update.message.reply_text("❌ Format: /addnote စာအုပ် - rating - note")
        return
    book_title = parts[0].strip()
    try:
        rating = max(1, min(5, int(parts[1].strip())))
    except ValueError:
        await update.message.reply_text("❌ Rating 1-5 ထဲက ထည့်ပါ")
        return
    note_text = " - ".join(parts[2:]).strip() if len(parts) > 2 else ""
    user = update.effective_user
    note_id = add_note(user.id, user.username or user.first_name, book_title, rating, note_text)
    stars = _stars(rating)
    msg = f"✅ Note saved!\n📖 {book_title}\nRating: {stars}"
    if note_text:
        msg += f"\n📝 {note_text}"
    msg += f"\n🆔 #{note_id}"
    await update.message.reply_text(msg)


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
    lines = [f"📖 *{book_title}* — {len(notes)} notes\n"]
    for n in notes:
        username = n.get("username", "Anonymous")
        stars = _stars(n["rating"])
        text_preview = n["note_text"][:40] + "..." if len(n["note_text"]) > 40 else n["note_text"]
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
