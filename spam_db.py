"""Spam domains storage via GitHub (persistent across Railway deploys)."""

import json
import os
import base64
import urllib.request
import logging

logger = logging.getLogger(__name__)

GITHUB_REPO = "whispermmepub/saroatsin-bot"
SPAM_PATH = "spam_domains.json"
_data_cache = None
_data_sha = None


def init_spam_db():
    global _data_cache, _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        logger.info("Loading spam domains from GitHub...")
    else:
        logger.warning("NO GITHUB_TOKEN! Custom spam domains won't persist.")
    _data_cache = _load_from_github()
    count = len(_data_cache.get("domains", []))
    logger.info("Spam domains loaded: %d custom domains", count)


def _load_from_github():
    global _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"domains": []}
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{SPAM_PATH}"
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
            logger.info("spam_domains.json not found, creating new one")
            _data_sha = ""
            return {"domains": []}
        logger.error("GitHub API error: %s", e)
        return {"domains": []}
    except Exception as e:
        logger.error("Failed to load spam domains: %s", e)
        return {"domains": []}


def _save_to_github(data):
    global _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("No GITHUB_TOKEN, spam domains not saved")
        return False
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{SPAM_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        content = json.dumps(data, ensure_ascii=False, indent=2)
        payload = {
            "message": "Update spam domains via bot",
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
        logger.error("Failed to save spam domains: %s", e)
        return False


def add_spam_domain(domain):
    global _data_cache
    if _data_cache is None:
        _data_cache = {"domains": []}
    d = domain.lower().strip().replace("https://", "").replace("http://", "").rstrip("/")
    if d not in _data_cache["domains"]:
        _data_cache["domains"].append(d)
        _save_to_github(_data_cache)
        return True
    return False


def remove_spam_domain(domain):
    global _data_cache
    if _data_cache is None:
        _data_cache = {"domains": []}
    d = domain.lower().strip().replace("https://", "").replace("http://", "").rstrip("/")
    if d in _data_cache["domains"]:
        _data_cache["domains"].remove(d)
        _save_to_github(_data_cache)
        return True
    return False


def get_spam_domains():
    if _data_cache is None:
        return []
    return list(_data_cache.get("domains", []))
