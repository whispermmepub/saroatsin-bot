"""Scrape books data from whispermmepub.github.io/saroatsin-bot/"""

import re
import json
import urllib.request
from html.parser import HTMLParser

URL = "https://whispermmepub.github.io/saroatsin-bot/"


class BookScraper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.books = []          # list of {author, title, link}
        self._current_author = None
        self._current_book = None
        self._in_book_text = False
        self._in_read_btn = False
        self._current_href = None

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)

        if tag == "div" and attr_dict.get("class") == "author-section":
            self._current_author = attr_dict.get("data-author", "")

        if tag == "span" and attr_dict.get("class") == "book-text":
            self._in_book_text = True
            self._current_book = attr_dict.get("data-raw", "")

        if tag == "a" and attr_dict.get("class") == "read-btn":
            self._in_read_btn = True
            self._current_href = attr_dict.get("href", "")

    def handle_endtag(self, tag):
        if tag == "span" and self._in_book_text:
            self._in_book_text = False

        if tag == "a" and self._in_read_btn:
            self._in_read_btn = False
            if self._current_author and self._current_book and self._current_href:
                self.books.append({
                    "author": self._current_author,
                    "title": self._current_book,
                    "link": self._current_href,
                })
            self._current_href = None

    def handle_data(self, data):
        if self._in_book_text and self._current_book is None:
            self._current_book = data.strip()


def fetch_books(url=URL):
    """Fetch and parse all books from the website."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8")

    parser = BookScraper()
    parser.feed(html)
    return parser.books


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
