"""Notes storage via GitHub (persistent across Railway deploys)."""

import json
import os
import base64
import urllib.request
import logging
import time

logger = logging.getLogger(__name__)

GITHUB_REPO = "whispermmepub/saroatsin-bot"
NOTES_PATH = "notes_data.json"
_data_cache = None
_data_sha = None
_last_load = 0


def _get_conn():
    """Compatibility stub - not used."""
    pass


def init_db():
    """Load notes from GitHub on startup."""
    global _data_cache, _data_sha, _last_load
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        logger.info("GITHUB_TOKEN found, loading notes from GitHub...")
    else:
        logger.warning("NO GITHUB_TOKEN found! Notes will NOT persist!")
    _data_cache = _load_from_github()
    _last_load = time.time()
    logger.info("Notes loaded: %d notes, SHA: %s", _count_notes(), _data_sha or "none")


def _load_from_github():
    """Fetch notes_data.json from GitHub."""
    global _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("No GITHUB_TOKEN - notes will not persist across deploys")
        return {"notes": []}
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{NOTES_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            _data_sha = result.get("sha", "")
            content = base64.b64decode(result["content"]).decode("utf-8")
            return json.loads(content)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.info("notes_data.json not found on GitHub, creating new one")
            _data_sha = ""
            return {"notes": []}
        logger.error("Failed to load notes from GitHub: %s", e)
        return {"notes": []}
    except Exception as e:
        logger.error("Failed to load notes from GitHub: %s", e)
        return {"notes": []}


def _save_to_github(data):
    """Push notes_data.json to GitHub."""
    global _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("No GITHUB_TOKEN - notes not saved")
        return False
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{NOTES_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    # Get current SHA
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            _data_sha = result.get("sha", "")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            _data_sha = ""
        else:
            logger.error("Failed to get SHA: %s", e)
            return False
    except Exception as e:
        logger.error("Failed to get SHA: %s", e)
        return False

    content = json.dumps(data, ensure_ascii=False, indent=2)
    payload = {
        "message": "Update notes via Telegram bot",
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
    }
    if _data_sha:
        payload["sha"] = _data_sha
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            _data_sha = result.get("sha", "")
            return True
    except Exception as e:
        logger.error("Failed to save notes to GitHub: %s", e)
        return False


def _count_notes():
    if not _data_cache:
        return 0
    return len([n for n in _data_cache.get("notes", []) if not n.get("deleted")])


def _ensure_data():
    global _data_cache
    if _data_cache is None:
        _data_cache = {"notes": []}
    return _data_cache


def add_note(user_id, username, book_title, rating, note_text):
    data = _ensure_data()
    note_id = max((n["id"] for n in data["notes"]), default=0) + 1
    note = {
        "id": note_id,
        "user_id": user_id,
        "username": username,
        "book_title": book_title,
        "rating": rating,
        "note_text": note_text,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deleted": False,
    }
    data["notes"].append(note)
    saved = _save_to_github(data)
    logger.info("Note saved: id=%d saved_to_github=%s total=%d", note_id, saved, len(data["notes"]))
    return note_id


def get_notes_for_book(book_title):
    data = _ensure_data()
    return [
        n for n in data["notes"]
        if not n.get("deleted") and n["book_title"].strip().lower() == book_title.strip().lower()
    ]


def get_user_notes(user_id):
    data = _ensure_data()
    return [
        n for n in data["notes"]
        if not n.get("deleted") and n["user_id"] == user_id
    ]


def get_user_note_by_id(user_id, note_id):
    data = _ensure_data()
    for n in data["notes"]:
        if n["id"] == note_id and n["user_id"] == user_id and not n.get("deleted"):
            return n
    return None

def get_note_by_id(note_id):
    data = _ensure_data()
    for n in data["notes"]:
        if n["id"] == note_id and not n.get("deleted"):
            return n
    return None


def delete_note(note_id, user_id=None):
    data = _ensure_data()
    for n in data["notes"]:
        if n["id"] == note_id:
            if user_id and n["user_id"] != user_id:
                continue
            n["deleted"] = True
    _save_to_github(data)


def delete_all_notes_for_book(book_title):
    data = _ensure_data()
    count = 0
    for n in data["notes"]:
        if not n.get("deleted") and n["book_title"].strip().lower() == book_title.strip().lower():
            n["deleted"] = True
            count += 1
    _save_to_github(data)
    return count


def search_notes(keyword):
    data = _ensure_data()
    kw = keyword.lower()
    return [
        n for n in data["notes"]
        if not n.get("deleted")
        and (kw in n["book_title"].lower() or kw in n["note_text"].lower())
    ]


def get_notes_with_book_info():
    data = _ensure_data()
    books = {}
    for n in data["notes"]:
        if not n.get("deleted"):
            bt = n["book_title"]
            books.setdefault(bt, []).append(n)
    return books
