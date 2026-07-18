"""Fetch books data from whispermmepub/wow-books data.json."""

import json
import urllib.request

DATA_URL = "https://raw.githubusercontent.com/whispermmepub/wow-books/main/data.json"


def fetch_books(url=DATA_URL):
    """Fetch and parse all books from the JSON data source.
    Returns (books_list, raw_data)."""
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


def search_books(books, query):
    """Search books by author name or title (case-insensitive, partial match)."""
    q = query.lower().strip()
    if not q:
        return []
    return [
        b for b in books
        if q in b["author"].lower() or q in b["title"].lower()
    ]


def get_authors(books):
    """Return sorted unique author names with book counts."""
    counts = {}
    for b in books:
        counts[b["author"]] = counts.get(b["author"], 0) + 1
    return sorted(counts.items(), key=lambda x: (-x[1], x[0]))
