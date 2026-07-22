"""Fetch books data from whispermmepub/wow-books data.json."""

import json
import urllib.request
import time
import logging

DATA_URL = "https://raw.githubusercontent.com/whispermmepub/wow-books/main/data.json"

logger = logging.getLogger(__name__)


def fetch_books(url=DATA_URL, retries=3, delay=5):
    """Fetch and parse all books from the JSON data source with retry.
    Returns (books_list, raw_data)."""
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            books = []
            for author_entry in raw:
                author = author_entry.get("author", "")
                for book in author_entry.get("books", []):
                    books.append({
                        "author": author,
                        "title": book.get("title", ""),
                        "link": book.get("link", ""),
                    })
            return books, raw
        except Exception as e:
            last_err = e
            logger.warning("Attempt %d/%d failed to fetch books: %s", attempt + 1, retries, e)
            if attempt < retries - 1:
                time.sleep(delay)
    logger.error("All %d attempts to fetch books failed: %s", retries, last_err)
    return [], []


def search_books(books, query):
    """Search books by author name or title (case-insensitive, space-insensitive partial match)."""
    q = query.lower().strip()
    if not q:
        return []
    # Normalize: remove spaces for flexible matching
    q_nospace = q.replace(" ", "")
    return [
        b for b in books
        if q in b["author"].lower() or q in b["title"].lower()
        or q_nospace in b["author"].lower().replace(" ", "")
        or q_nospace in b["title"].lower().replace(" ", "")
    ]


def get_authors(books):
    """Return sorted unique author names with book counts."""
    counts = {}
    for b in books:
        counts[b["author"]] = counts.get(b["author"], 0) + 1
    return sorted(counts.items(), key=lambda x: (-x[1], x[0]))
