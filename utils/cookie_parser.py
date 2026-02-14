import json


def parse_cookie_items(cookie_list):
    cookie_pairs = []
    bearer_token = None
    for item in cookie_list:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        if not name or value is None:
            continue
        cookie_pairs.append(f"{name}={value}")
        if name in ("token", "__Secure-next-auth.session-token") and isinstance(value, str) and value:
            bearer_token = value
    cookie_header = "; ".join(cookie_pairs) if cookie_pairs else None
    return cookie_header, bearer_token


def coerce_cookie_list(cookie_raw):
    if cookie_raw is None:
        return None
    if isinstance(cookie_raw, str):
        text = cookie_raw.strip()
        try:
            return json.loads(text)
        except Exception:
            return None
    if isinstance(cookie_raw, list):
        return cookie_raw
    return None


def build_header(base_headers: dict, cookie_raw: str | None = None):
    """Build Qwen headers dynamically from cookie JSON array string.

    - base_headers: headers template without Cookie/authorization
    - cookie_raw: JSON array string saved from UI (optional). If None, will load from ui_settings.json
    Returns a new headers dict (base + Cookie + authorization + bx-ua/bx-umidtoken when set).
    """
    headers = dict(base_headers or {})
    settings = None
    # Auto-load from ui_settings.json if cookie not provided
    if cookie_raw is None:
        try:
            import os
            if os.path.exists("ui_settings.json"):
                with open("ui_settings.json", "r", encoding="utf-8") as f:
                    settings = json.load(f) or {}
                cookie_raw = settings.get("cookie")
        except Exception:
            cookie_raw = None

    cookie_list = coerce_cookie_list(cookie_raw)
    if cookie_list:
        cookie_header, token = parse_cookie_items(cookie_list)
        if cookie_header:
            headers["Cookie"] = cookie_header
        if token:
            headers["authorization"] = f"Bearer {token}"

    # Optional anti-bot headers: only send when set in Settings
    if settings is None:
        try:
            import os
            if os.path.exists("ui_settings.json"):
                with open("ui_settings.json", "r", encoding="utf-8") as f:
                    settings = json.load(f) or {}
        except Exception:
            settings = {}
    bx_ua = (settings.get("bx_ua") or "").strip()
    bx_umidtoken = (settings.get("bx_umidtoken") or "").strip()
    if bx_ua:
        headers["bx-ua"] = bx_ua
    else:
        headers.pop("bx-ua", None)
    if bx_umidtoken:
        headers["bx-umidtoken"] = bx_umidtoken
    else:
        headers.pop("bx-umidtoken", None)

    return headers

