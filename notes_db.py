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


def init_db():
    global _data_cache, _data_sha, _last_load
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        logger.info("GITHUB_TOKEN found, loading notes from GitHub...")
    else:
        logger.warning("NO GITHUB_TOKEN found! Notes will NOT persist!")
    _data_cache = _load_from_github()
    _last_load = time.time()
    count = len(_data_cache.get("notes", []))
    logger.info("Notes loaded: %d notes, SHA: %s", count, _data_sha or "none")


def _load_from_github():
    global _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
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
            logger.info("notes_data.json not found, creating new one")
            _data_sha = ""
            return {"notes": []}
        logger.error("GitHub API error: %s", e)
        return {"notes": []}
    except Exception as e:
        logger.error("Failed to load notes: %s", e)
        return {"notes": []}


def _save_to_github(data):
    global _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("No GITHUB_TOKEN, notes not saved")
        return False
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{NOTES_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        content = json.dumps(data, ensure_ascii=False, indent=2)
        payload = {
            "message": "Update notes via bot",
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
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            _data_sha = result.get("content", {}).get("sha", _data_sha)
            return True
    except Exception as e:
        logger.error("Failed to save notes: %s", e)
        return False


def add_note(user_id, username, book_title, rating, note_text):
    global _data_cache
    if _data_cache is None:
        _data_cache = {"notes": []}
    note_id = max((n["id"] for n in _data_cache.get("notes", [])), default=0) + 1
    note = {
        "id": note_id,
        "user_id": user_id,
        "username": username,
        "book_title": book_title,
        "rating": rating,
        "note_text": note_text,
    }
    _data_cache.setdefault("notes", []).append(note)
    _save_to_github(_data_cache)
    return note_id


def get_notes_for_book(book_title):
    if _data_cache is None:
        return []
    return [n for n in _data_cache.get("notes", []) if n["book_title"] == book_title]


def get_user_notes(user_id):
    if _data_cache is None:
        return []
    return [n for n in _data_cache.get("notes", []) if n["user_id"] == user_id]


def delete_note(note_id, user_id=None):
    global _data_cache
    if _data_cache is None:
        return False
    notes = _data_cache.get("notes", [])
    for i, n in enumerate(notes):
        if n["id"] == note_id:
            if user_id and n["user_id"] != user_id:
                return False
            notes.pop(i)
            _save_to_github(_data_cache)
            return True
    return False


def get_note_by_id(note_id):
    if _data_cache is None:
        return None
    for n in _data_cache.get("notes", []):
        if n["id"] == note_id:
            return n
    return None


def count_notes():
    if _data_cache is None:
        return 0
    return len(_data_cache.get("notes", []))


def count_note_users():
    if _data_cache is None:
        return 0
    return len(set(n["user_id"] for n in _data_cache.get("notes", [])))
