"""Custom help items storage via GitHub."""

import json
import os
import base64
import urllib.request
import logging

logger = logging.getLogger(__name__)

GITHUB_REPO = "whispermmepub/saroatsin-bot"
HELP_PATH = "help_data.json"
_data_cache = None
_data_sha = None


def init_help_db():
    global _data_cache, _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        logger.info("Loading custom help items from GitHub...")
    else:
        logger.warning("NO GITHUB_TOKEN! Custom help items won't persist.")
    _data_cache = _load_from_github()
    count = len(_data_cache.get("items", []))
    logger.info("Custom help items loaded: %d", count)


def _load_from_github():
    global _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"items": []}
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{HELP_PATH}"
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
            logger.info("help_data.json not found, creating new one")
            _data_sha = ""
            return {"items": []}
        logger.error("GitHub API error: %s", e)
        return {"items": []}
    except Exception as e:
        logger.error("Failed to load help items: %s", e)
        return {"items": []}


def _save_to_github(data):
    global _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("No GITHUB_TOKEN, help items not saved")
        return False
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{HELP_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        content = json.dumps(data, ensure_ascii=False, indent=2)
        payload = {
            "message": "Update custom help items via bot",
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
        logger.error("Failed to save help items: %s", e)
        return False


def add_help_item(command, description):
    global _data_cache
    if _data_cache is None:
        _data_cache = {"items": []}
    for item in _data_cache["items"]:
        if item["command"].lower() == command.lower():
            item["description"] = description
            _save_to_github(_data_cache)
            return "updated"
    _data_cache["items"].append({"command": command, "description": description})
    _save_to_github(_data_cache)
    return "added"


def remove_help_item(command):
    global _data_cache
    if _data_cache is None:
        _data_cache = {"items": []}
    before = len(_data_cache["items"])
    _data_cache["items"] = [
        i for i in _data_cache["items"]
        if i["command"].lower() != command.lower()
    ]
    if len(_data_cache["items"]) < before:
        _save_to_github(_data_cache)
        return True
    return False


def get_help_items():
    if _data_cache is None:
        return []
    return list(_data_cache.get("items", []))
