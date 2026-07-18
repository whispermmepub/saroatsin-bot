"""SQLite database handler for Book Notes."""

import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes_data.sqlite3")


def _get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            book_title TEXT NOT NULL,
            rating INTEGER DEFAULT 5,
            note_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user ON notes(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_book ON notes(book_title COLLATE NOCASE)")
    conn.commit()
    conn.close()
    logger.info("Notes database initialized at %s", DB_PATH)


def add_note(user_id, username, book_title, rating, note_text):
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO notes (user_id, username, book_title, rating, note_text) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, book_title, rating, note_text),
        )
        conn.commit()
        note_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return note_id
    finally:
        conn.close()


def get_notes_for_book(book_title):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, user_id, username, rating, note_text, created_at FROM notes WHERE TRIM(LOWER(book_title)) = TRIM(LOWER(?)) AND deleted = 0 ORDER BY created_at DESC",
        (book_title,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_notes(user_id):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, book_title, rating, note_text, created_at FROM notes WHERE user_id = ? AND deleted = 0 ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_note_by_id(user_id, note_id):
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, user_id, username, book_title, rating, note_text, created_at FROM notes WHERE id = ? AND user_id = ? AND deleted = 0",
        (note_id, user_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_note(note_id, user_id=None):
    conn = _get_conn()
    if user_id:
        conn.execute("UPDATE notes SET deleted = 1 WHERE id = ? AND user_id = ?", (note_id, user_id))
    else:
        conn.execute("UPDATE notes SET deleted = 1 WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()


def delete_all_notes_for_book(book_title):
    conn = _get_conn()
    cursor = conn.execute("UPDATE notes SET deleted = 1 WHERE book_title = ? AND deleted = 0", (book_title,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


def search_notes(keyword):
    conn = _get_conn()
    like = f"%{keyword}%"
    rows = conn.execute(
        "SELECT id, user_id, username, book_title, rating, note_text, created_at FROM notes WHERE deleted = 0 AND (book_title LIKE ? OR note_text LIKE ?) ORDER BY created_at DESC",
        (like, like),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_notes_with_book_info():
    """Group notes by book_title for admin delete view."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, user_id, username, book_title, rating, note_text FROM notes WHERE deleted = 0 ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    books = {}
    for r in rows:
        r = dict(r)
        bt = r["book_title"]
        books.setdefault(bt, []).append(r)
    return books
