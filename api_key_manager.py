"""Manage multiple Gemini API keys; auto-switch on quota/rate-limit (429) errors."""
import sys

# Current index into the list of keys (module-level so LLM and STT share state)
_current_index = 0
_keys: list[str] = []


def _is_quota_error(exc: BaseException) -> bool:
    """True if exception indicates quota exceeded or rate limit (429)."""
    msg = str(exc).lower()
    if "429" in msg or "resource_exhausted" in msg or "quota" in msg or "rate limit" in msg:
        return True
    # google.generativeai may wrap in different exceptions
    for attr in ("message", "reason", "code"):
        if hasattr(exc, attr):
            v = str(getattr(exc, attr, "")).lower()
            if "429" in v or "resource_exhausted" in v or "quota" in v or "rate limit" in v:
                return True
    return False


def init_keys(config: dict) -> None:
    """Initialize key list from config. Use gemini_api_keys (list) for multiple keys and auto-switch; else gemini_api_key (string)."""
    global _keys, _current_index
    keys = config.get("gemini_api_keys")
    new_keys = []
    if isinstance(keys, list):
        new_keys = [k.strip() for k in keys if isinstance(k, str) and k.strip() and not k.strip().startswith("YOUR_")]
    if not new_keys:
        single = config.get("gemini_api_key") or ""
        if isinstance(single, str) and single.strip() and not single.strip().startswith("YOUR_"):
            new_keys = [single.strip()]
            
    if new_keys != _keys:
        _keys = new_keys
        _current_index = 0


def get_keys() -> list[str]:
    """Return current list of valid keys (may be empty)."""
    return list(_keys)


def get_current_key() -> str | None:
    """Return the key currently in use, or None if no keys."""
    if not _keys:
        return None
    return _keys[_current_index % len(_keys)]


def switch_to_next_key() -> str | None:
    """On quota/rate-limit: switch to next key and return it. Returns None if only one key or all keys already tried."""
    global _current_index
    if len(_keys) <= 1:
        return None
    _current_index = (_current_index + 1) % len(_keys)
    key = _keys[_current_index]
    print(f"[API] Switched to next Gemini key (index {_current_index + 1}/{len(_keys)}).", file=sys.stderr)
    return key


def is_quota_error(exc: BaseException) -> bool:
    """Public helper: True if this exception means we should try the next API key."""
    return _is_quota_error(exc)
