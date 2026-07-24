"""Blocked keywords storage via GitHub (persistent across Railway deploys)."""

import json
import os
import base64
import urllib.request
import logging

logger = logging.getLogger(__name__)

GITHUB_REPO = "whispermmepub/saroatsin-bot"
KEYWORD_PATH = "blocked_keywords.json"
_data_cache = None
_data_sha = None


def init_keyword_db():
    global _data_cache, _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        logger.info("Loading blocked keywords from GitHub...")
    else:
        logger.warning("NO GITHUB_TOKEN! Blocked keywords won't persist.")
    _data_cache = _load_from_github()
    count = len(_data_cache.get("keywords", []))
    logger.info("Blocked keywords loaded: %d keywords", count)


def _load_from_github():
    global _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"keywords": []}
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{KEYWORD_PATH}"
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
            logger.info("blocked_keywords.json not found, creating new one")
            _data_sha = ""
            return {"keywords": []}
        logger.error("GitHub API error: %s", e)
        return {"keywords": []}
    except Exception as e:
        logger.error("Failed to load blocked keywords: %s", e)
        return {"keywords": []}


def _save_to_github(data):
    global _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("No GITHUB_TOKEN, blocked keywords not saved")
        return False
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{KEYWORD_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        content = json.dumps(data, ensure_ascii=False, indent=2)
        payload = {
            "message": "Update blocked keywords via bot",
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
        logger.error("Failed to save blocked keywords: %s", e)
        return False


def add_keyword(word):
    global _data_cache
    if _data_cache is None:
        _data_cache = {"keywords": []}
    w = word.lower().strip()
    if w and w not in _data_cache["keywords"]:
        _data_cache["keywords"].append(w)
        _save_to_github(_data_cache)
        return True
    return False


def remove_keyword(word):
    global _data_cache
    if _data_cache is None:
        _data_cache = {"keywords": []}
    w = word.lower().strip()
    if w in _data_cache["keywords"]:
        _data_cache["keywords"].remove(w)
        _save_to_github(_data_cache)
        return True
    return False


def get_keywords():
    if _data_cache is None:
        return []
    return list(_data_cache.get("keywords", []))
