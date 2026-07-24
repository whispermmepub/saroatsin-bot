"""Author alias storage via GitHub (persistent across Railway deploys)."""

import json
import os
import base64
import urllib.request
import logging

logger = logging.getLogger(__name__)

GITHUB_REPO = "whispermmepub/saroatsin-bot"
ALIAS_PATH = "author_aliases.json"
_data_cache = None
_data_sha = None


def init_alias_db():
    global _data_cache, _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        logger.info("Loading author aliases from GitHub...")
    else:
        logger.warning("NO GITHUB_TOKEN! Author aliases won't persist.")
    _data_cache = _load_from_github()
    count = len(_data_cache.get("aliases", {}))
    logger.info("Author aliases loaded: %d aliases", count)


def _load_from_github():
    global _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"aliases": {}}
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{ALIAS_PATH}"
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
            logger.info("author_aliases.json not found, creating new one")
            _data_sha = ""
            return {"aliases": {}}
        logger.error("GitHub API error: %s", e)
        return {"aliases": {}}
    except Exception as e:
        logger.error("Failed to load author aliases: %s", e)
        return {"aliases": {}}


def _save_to_github(data):
    global _data_sha
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("No GITHUB_TOKEN, author aliases not saved")
        return False
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{ALIAS_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        content = json.dumps(data, ensure_ascii=False, indent=2)
        payload = {
            "message": "Update author aliases via bot",
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
        logger.error("Failed to save author aliases: %s", e)
        return False


def add_alias(alias, canonical):
    global _data_cache
    if _data_cache is None:
        _data_cache = {"aliases": {}}
    a = alias.lower().strip()
    c = canonical.lower().strip()
    if a and c:
        _data_cache["aliases"][a] = c
        _save_to_github(_data_cache)
        return True
    return False


def remove_alias(alias):
    global _data_cache
    if _data_cache is None:
        _data_cache = {"aliases": {}}
    a = alias.lower().strip()
    if a in _data_cache["aliases"]:
        del _data_cache["aliases"][a]
        _save_to_github(_data_cache)
        return True
    return False


def get_aliases():
    if _data_cache is None:
        return {}
    return dict(_data_cache.get("aliases", {}))


def resolve_alias(query):
    """Resolve a query through aliases. Returns (resolved_name, was_aliased)."""
    aliases = get_aliases()
    q = query.lower().strip()
    if q in aliases:
        return aliases[q], True
    return query, False
