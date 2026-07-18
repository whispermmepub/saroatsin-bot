"""Book Notes commands for the Telegram bot."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from notes_db import (
    init_db,
    add_note,
    get_notes_for_book,
    get_user_notes,
    get_user_note_by_id,
    get_note_by_id,
    delete_note,
    delete_all_notes_for_book,
    search_notes,
    get_notes_with_book_info,
)

logger = logging.getLogger(__name__)

ADMIN_USERNAMES = ["wowepub"]

_stars = lambda n: "⭐" * n + "☆" * (5 - n)




def _is_admin(update):
    user = update.effective_user
    return user and user.username in ADMIN_USERNAMES


# ── /addnote မီဆိုဟင်းချို - 5  or  /addnote မီဆိုဟင်းချို - 5 - note text
async def cmd_addnote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Add a note: /addnote <book_title> - <rating> [- note text]"""
    try:
        text = update.message.text.replace("/addnote", "", 1).strip()
        if not text:
            await update.message.reply_text(
                "📝 Format: /addnote စာအုပ်နာမည် - rating\n"
                "ဥပမာ: /addnote မီဆိုဟင်းချို - 5\n"
                "သို့: /addnote မီဆိုဟင်းချို - 5 - ဆရာသင့်လူ ဘာသာပြန်တာ ကောင်းတယ်"
            )
            return

        # Support: /addnote book - rating - note text
        # Split by " - " from right, but keep note text if 3 parts
        parts = text.split(" - ")
        if len(parts) >= 3:
            book_title = parts[0].strip()
            try:
                rating = int(parts[1].strip())
                rating = max(1, min(5, rating))
            except ValueError:
                await update.message.reply_text("❌ Rating 1-5 ထဲက ထည့်ပါ")
                return
            note_text = " - ".join(parts[2:]).strip()
            # Save directly
            user = update.effective_user
            note_id = add_note(
                user.id,
                user.username or user.first_name or "Anonymous",
                book_title, rating, note_text
            )
            stars = _stars(rating)
            logger.info("Note saved directly: id=%d user=%s book=%s", note_id, user.username, book_title)
            sent = await update.message.reply_text(
                f"✅ *Note saved!*\n\n"
                f"📖 {book_title}\n"
                f"Rating: {stars}\n"
                f"📝 {note_text}\n\n"
                f"🆔 Note #{note_id}",
                parse_mode="Markdown",
            )
            return

        if " - " in text:
            parts2 = text.rsplit(" - ", 1)
            book_title = parts2[0].strip()
            try:
                rating = int(parts2[1].strip())
                rating = max(1, min(5, rating))
            except ValueError:
                await update.message.reply_text("❌ Rating 1-5 ထဲက ထည့်ပါ")
                return
        else:
            book_title = text.strip()
            rating = 5

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
    except Exception as e:
        logger.error("cmd_addnote error: %s", e)
        await update.message.reply_text("❌ Error ဖြစ်သွားတယ်")


# ── Handle reply text to save note
async def handle_note_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle reply text after /addnote."""
    if "pending_note" not in ctx.user_data:
        return False  # not handling this message

    pending = ctx.user_data.pop("pending_note")
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name or "Anonymous"
    book_title = pending["book_title"]
    rating = pending["rating"]
    note_text = update.message.text.strip()

    if not note_text:
        await update.message.reply_text("❌ Note content ထည့်ပါ")
        return True

    try:
        logger.info("Saving note: user=%s book=%s rating=%d", username, book_title, rating)
        note_id = add_note(user_id, username, book_title, rating, note_text)
        stars = _stars(rating)
        sent = await update.message.reply_text(
            f"✅ *Note saved!*\n\n"
            f"📖 {book_title}\n"
            f"Rating: {stars}\n"
            f"📝 {note_text}\n\n"
            f"🆔 Note #{note_id}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("add_note error: %s", e)
        await update.message.reply_text("❌ Note save မအောင်မြင်ပါ")
    return True


# ── /note မီဆိုဟင်းချို
async def cmd_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show notes for a book with numbered list."""
    try:
        book_title = " ".join(ctx.args).strip() if ctx.args else ""
        if not book_title:
            await update.message.reply_text(
                "📝 Format: /note စာအုပ်နာမည်\n"
                "ဥပမာ: /note မီဆိုဟင်းချို"
            )
            return

        logger.info("Searching notes for book: '%s'", book_title)
        notes = get_notes_for_book(book_title)
        if not notes:
            await update.message.reply_text(
                f"📭 *{book_title}* အတွက် note မရှိသေးဘူး\n\n"
                f"စတင်ရေးရန်: /addnote {book_title} - 5",
                parse_mode="Markdown",
            )
            return

        lines = [f"📝 *{book_title}* အတွက် Note {len(notes)} ခု\n"]
        buttons = []
        for i, n in enumerate(notes, 1):
            stars = _stars(n["rating"])
            username = n["username"] or "Anonymous"
            lines.append(f"{i}. 👤 {username} — {stars}")
            buttons.append([
                InlineKeyboardButton(
                    f"{i}. {username} — {stars}",
                    callback_data=f"noteview|{n['id']}"
                )
            ])

        buttons.append([InlineKeyboardButton("❌ ပိတ်ရန်", callback_data="noteclose")])
        header = "\n".join(lines)
        await update.message.reply_text(
            header,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("cmd_note error: %s", e)
        await update.message.reply_text("❌ Error ဖြစ်သွားတယ်")


# ── /mynote
async def cmd_mynote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show user's own notes grouped by book."""
    try:
        user_id = update.effective_user.id
        notes = get_user_notes(user_id)
        if not notes:
            await update.message.reply_text(
                "📭 သင့် note မရှိသေးဘူး\n\n"
                "စတင်ရေးရန်: /addnote စာအုပ်နာမည် - 5"
            )
            return

        groups = {}
        for n in notes:
            bt = n["book_title"]
            groups.setdefault(bt, []).append(n)

        lines = [f"📝 *My Notes ({len(notes)} total)*\n"]
        buttons = []
        for book, book_notes in groups.items():
            count = len(book_notes)
            avg = sum(n["rating"] for n in book_notes) / count
            stars = _stars(round(avg))
            lines.append(f"📖 {book} ({count}) {stars}")
            buttons.append([
                InlineKeyboardButton(
                    f"📖 {book} ({count})",
                    callback_data=f"mynotedetail|{book}"
                )
            ])

        buttons.append([InlineKeyboardButton("❌ ပိတ်ရန်", callback_data="noteclose")])
        await update.message.reply_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("cmd_mynote error: %s", e)
        await update.message.reply_text("❌ Error ဖြစ်သွားတယ်")


# ── /delnote  or  /delnote မီဆိုဟင်းချို
async def cmd_delnote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Delete notes - shows all user's notes to pick from."""
    try:
        book_title = " ".join(ctx.args).strip() if ctx.args else ""

        user = update.effective_user
        is_admin = _is_admin(update)

        if not book_title:
            # No book specified - show all user's notes to pick
            user_notes = get_user_notes(user.id)
            if not user_notes:
                await update.message.reply_text("📭 သင့် note မရှိသေးဘူး")
                return

            buttons = []
            for n in user_notes[:10]:
                stars = _stars(n["rating"])
                label = f"❌ {n['book_title']} {stars} — {n['note_text'][:20]}..."
                buttons.append([
                    InlineKeyboardButton(label, callback_data=f"userdel|{n['id']}")
                ])
            await update.message.reply_text(
                f"🗑️ ဖျက်ချင်တဲ့ note ကို နှိပ်ပါ:",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return

        if is_admin:
            # Admin sees all users' notes for that book
            all_notes = get_notes_for_book(book_title)
            if not all_notes:
                await update.message.reply_text(f"📭 *{book_title}* အတွက် note မရှိဘူး", parse_mode="Markdown")
                return

            buttons = []
            for n in all_notes:
                stars = _stars(n["rating"])
                username = n["username"] or "Anonymous"
                buttons.append([
                    InlineKeyboardButton(
                        f"❌ {username} — {stars}",
                        callback_data=f"admindel|{n['id']}|{book_title}"
                    )
                ])
            buttons.append([
                InlineKeyboardButton(
                    f"🗑️ Delete All ({len(all_notes)})",
                    callback_data=f"admin_delall|{book_title}"
                )
            ])
            buttons.append([InlineKeyboardButton("❌ ပိတ်ရန်", callback_data="noteclose")])
            await update.message.reply_text(
                f"🗑️ *Admin Delete — {book_title}*\n\n"
                f"ဖျက်ချင်တဲ့ note ကို နှိပ်ပါ:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown",
            )
        else:
            # Regular user sees only their own notes
            user_notes = [n for n in get_notes_for_book(book_title) if n["user_id"] == user.id]
            if not user_notes:
                await update.message.reply_text(
                    f"📭 *{book_title}* အတွက် သင့် note မရှိဘူး",
                    parse_mode="Markdown",
                )
                return

            buttons = []
            for n in user_notes:
                stars = _stars(n["rating"])
                buttons.append([
                    InlineKeyboardButton(
                        f"❌ {stars} — {n['note_text'][:30]}...",
                        callback_data=f"userdel|{n['id']}"
                    )
                ])
            buttons.append([InlineKeyboardButton("❌ ပိတ်ရန်", callback_data="noteclose")])
            await update.message.reply_text(
                f"🗑️ *{book_title}* — ဖျက်ချင်တဲ့ note ကို နှိပ်ပါ:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown",
            )

        user = update.effective_user
        is_admin = _is_admin(update)

        if is_admin:
            # Admin sees all users' notes for that book
            all_notes = get_notes_for_book(book_title)
            if not all_notes:
                await update.message.reply_text(f"📭 *{book_title}* အတွက် note မရှိဘူး", parse_mode="Markdown")
                return

            buttons = []
            for n in all_notes:
                stars = _stars(n["rating"])
                username = n["username"] or "Anonymous"
                buttons.append([
                    InlineKeyboardButton(
                        f"❌ {username} — {stars}",
                        callback_data=f"admindel|{n['id']}|{book_title}"
                    )
                ])
            buttons.append([
                InlineKeyboardButton(
                    f"🗑️ Delete All ({len(all_notes)})",
                    callback_data=f"admin_delall|{book_title}"
                )
            ])
            await update.message.reply_text(
                f"🗑️ *Admin Delete — {book_title}*\n\n"
                f"ဖျက်ချင်တဲ့ note ကို နှိပ်ပါ:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown",
            )
        else:
            # Regular user sees only their own notes
            user_notes = [n for n in get_notes_for_book(book_title) if n["user_id"] == user.id]
            if not user_notes:
                await update.message.reply_text(
                    f"📭 *{book_title}* အတွက် သင့် note မရှိဘူး",
                    parse_mode="Markdown",
                )
                return

            buttons = []
            for n in user_notes:
                stars = _stars(n["rating"])
                buttons.append([
                    InlineKeyboardButton(
                        f"❌ {stars} — {n['note_text'][:30]}...",
                        callback_data=f"userdel|{n['id']}"
                    )
                ])
            await update.message.reply_text(
                f"🗑️ *{book_title}* — ဖျက်ချင်တဲ့ note ကို နှိပ်ပါ:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown",
            )
    except Exception as e:
        logger.error("cmd_delnote error: %s", e)
        await update.message.reply_text("❌ Error ဖြစ်သွားတယ်")


# ── /searchnote keyword
async def cmd_searchnote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Search notes by keyword."""
    try:
        keyword = " ".join(ctx.args).strip() if ctx.args else ""
        if not keyword:
            await update.message.reply_text(
                "🔍 Format: /searchnote keyword\n"
                "ဥပမာ: /searchnote ခံစားချက်"
            )
            return

        notes = search_notes(keyword)
        if not notes:
            await update.message.reply_text(f"🔍 \"{keyword}\" နဲ့ ဆက်စပ် note မတွေ့ပါ")
            return

        lines = [f"🔍 *Search results for \"{keyword}\"* — {len(notes)} notes\n"]
        for n in notes[:10]:
            stars = _stars(n["rating"])
            username = n["username"] or "Anonymous"
            lines.append(f"📖 {n['book_title']} — {username} {stars}")
            lines.append(f'   "{n["note_text"][:50]}..."\n')

        if len(notes) > 10:
            lines.append(f"... and {len(notes) - 10} more")

        sent = await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error("cmd_searchnote error: %s", e)
        await update.message.reply_text("❌ Error ဖြစ်သွားတယ်")


# ── Callback handler for notes
async def notes_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle note-related callbacks."""
    query = update.callback_query
    data = query.data

    # Only handle notes-related callbacks - return BEFORE answering
    if not data or not any(data.startswith(p) for p in ["noteview", "userdel", "admindel", "admin_delall", "noteclose", "mynotedetail", "noop"]):
        return  # Let other callback handlers process this

    await query.answer()

    if data == "noop":
        return

    parts = data.split("|")

    # View individual note
    if parts[0] == "noteview" and len(parts) == 2:
        note_id = int(parts[1])
        r = get_note_by_id(note_id)
        if r:
            stars = _stars(r["rating"])
            username = r["username"] or "Anonymous"
            await query.edit_message_text(
                f"👤 {username} — {stars}\n\n"
                f"📖 {r['book_title']}\n\n"
                f'"{r["note_text"]}"\n\n'
                f"📅 {r['created_at'][:10]}",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text("❌ Note မတွေ့ပါ")

    # User delete their own note
    elif parts[0] == "userdel" and len(parts) == 2:
        note_id = int(parts[1])
        user_id = update.effective_user.id
        delete_note(note_id, user_id=user_id)
        await query.edit_message_text("✅ Note ဖျက်ပြီးပါပြီ")

    # Admin delete a note
    elif parts[0] == "admindel" and len(parts) == 3:
        note_id = int(parts[1])
        book_title = parts[2]
        delete_note(note_id)
        await query.edit_message_text(f"✅ Note #{note_id} ဖျက်ပြီးပါပြီ")

    # Admin delete all notes for a book
    elif parts[0] == "admin_delall" and len(parts) == 2:
        book_title = parts[1]
        count = delete_all_notes_for_book(book_title)
        await query.edit_message_text(f"✅ *{book_title}* ရဲ့ note {count} ခု အကုန်ဖျက်ပြီးပါပြီ", parse_mode="Markdown")

    # Close note message
    elif parts[0] == "noteclose":
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_text("✅ ပိတ်ပြီးပါပြီ")

    # User's mynote detail
    elif parts[0] == "mynotedetail" and len(parts) >= 2:
        book_title = parts[1]
        user_id = update.effective_user.id
        all_notes = get_notes_for_book(book_title)
        my_notes = [n for n in all_notes if n["user_id"] == user_id]
        if my_notes:
            lines = [f"📝 *{book_title}* — Your Notes\n"]
            for n in my_notes:
                stars = _stars(n["rating"])
                lines.append(f"{stars} — \"{n['note_text']}\"\n📅 {n['created_at'][:10]}\n")
            await query.edit_message_text("\n".join(lines), parse_mode="Markdown")
        else:
            await query.edit_message_text("📭 Note မတွေ့ပါ")
