"""Whitelisted domains storage via GitHub (persistent across Railway deploys)."""

import json
import os
import base64
import urllib.request
import logging

logger = logging.getLogger(__name__)

GITHUB_REPO = "whispermmepub/saroatsin-bot"
WL_PATH = "whitelisted_domains.json"

# Default whitelisted domains (always allowed)
DEFAULT_WHITELIST = [
    "facebook.com", "fb.com", "fb.watch",
    "youtube.com", "youtu.be",
    "twitter.com", "x.com",
    "tiktok.com",
    "blogspot.com", "whispermmepub.github.io", "saroatsin.com",
    "wikipedia.org",
]

# Whitelisted bots (forward messages from these bots are allowed)
WHITELISTED_BOTS = ["wowepubsearch_bot", "MissRose_bot"]

_data_cache = None
_data_sha = None


def init_whitelist_db():
    global _data_cache, _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        logger.info("Loading whitelist from GitHub...")
    else:
        logger.warning("NO GITHUB_TOKEN! Whitelist won't persist.")
    _data_cache = _load_from_github()
    # Ensure defaults are always present
    if _data_cache is None:
        _data_cache = {"domains": list(DEFAULT_WHITELIST)}
    else:
        for d in DEFAULT_WHITELIST:
            if d not in _data_cache["domains"]:
                _data_cache["domains"].append(d)
    count = len(_data_cache.get("domains", []))
    logger.info("Whitelist loaded: %d domains", count)


def _load_from_github():
    global _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"domains": list(DEFAULT_WHITELIST)}
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{WL_PATH}"
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
            logger.info("whitelisted_domains.json not found, creating new one")
            _data_sha = ""
            return {"domains": list(DEFAULT_WHITELIST)}
        logger.error("GitHub API error: %s", e)
        return {"domains": list(DEFAULT_WHITELIST)}
    except Exception as e:
        logger.error("Failed to load whitelist: %s", e)
        return {"domains": list(DEFAULT_WHITELIST)}


def _save_to_github(data):
    global _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("No GITHUB_TOKEN, whitelist not saved")
        return False
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{WL_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        content = json.dumps(data, ensure_ascii=False, indent=2)
        payload = {
            "message": "Update whitelist via bot",
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
        logger.error("Failed to save whitelist: %s", e)
        return False


def add_to_whitelist(domain):
    global _data_cache
    if _data_cache is None:
        _data_cache = {"domains": list(DEFAULT_WHITELIST)}
    d = domain.lower().strip().replace("https://", "").replace("http://", "").rstrip("/")
    if d and d not in _data_cache["domains"]:
        _data_cache["domains"].append(d)
        _save_to_github(_data_cache)
        return True
    return False


def remove_from_whitelist(domain):
    global _data_cache
    if _data_cache is None:
        _data_cache = {"domains": list(DEFAULT_WHITELIST)}
    d = domain.lower().strip().replace("https://", "").replace("http://", "").rstrip("/")
    # Cannot remove default domains
    if d in DEFAULT_WHITELIST:
        return False
    if d in _data_cache["domains"]:
        _data_cache["domains"].remove(d)
        _save_to_github(_data_cache)
        return True
    return False


def get_whitelist():
    if _data_cache is None:
        return list(DEFAULT_WHITELIST)
    return list(_data_cache.get("domains", DEFAULT_WHITELIST))


def is_domain_whitelisted(url_str):
    """Check if a URL's domain is in the whitelist."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url_str)
        host = (parsed.hostname or "").lower()
        path = parsed.path.lower()
    except Exception:
        return False
    wl = get_whitelist()
    for d in wl:
        if d in host:
            # Special case for t.me channels
            if host == "t.me":
                for ch in ["thebookr", "refthebook"]:
                    if path.startswith("/" + ch) or path.startswith("/" + ch + "/"):
                        return True
                return False
            return True
    return False


def is_forward_allowed(bot_username):
    """Check if a forwarded message from this bot is allowed."""
    return bot_username in WHITELISTED_BOTS
