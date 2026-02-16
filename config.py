import os
import uuid
x_request_id = str(uuid.uuid4())

# Application version
VERSION = "1.0.5"
TMP_FOLDER = "./tmp"

# URLs
QWEN_API_BASE = "https://chat.qwen.ai/api"
QWEN_MODELS_URL = f"{QWEN_API_BASE}/models"
QWEN_NEW_CHAT_URL = f"{QWEN_API_BASE}/v2/chats/new"
QWEN_CHAT_COMPLETIONS_URL = f"{QWEN_API_BASE}/v2/chat/completions"

# Request body version for v2/chat/completions (required by Qwen API)
QWEN_COMPLETIONS_BODY_VERSION = "2.1"

user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
qwen_version = "0.2.0"
qwen_host = "chat.qwen.ai"
qwen_origin = "https://chat.qwen.ai"
qwen_referer = "https://chat.qwen.ai/c/guest"
QWEN_REFERER_NEW_CHAT = "https://chat.qwen.ai/c/new-chat"
curl_user_agent = "curl/8.12.1"

# Optional anti-bot headers for Qwen web API (set via env or leave default for bx-v)
QWEN_BX_V = os.environ.get("QWEN_BX_V", "2.5.36")
QWEN_BX_UA = os.environ.get("QWEN_BX_UA", "")
QWEN_BX_UMIDTOKEN = os.environ.get("QWEN_BX_UMIDTOKEN", "")

QWEN_HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "content-type": "application/json; charset=UTF-8",
    "DNT": "1",
    "Host": qwen_host,
    "Origin": qwen_origin,
    "Referer": qwen_referer,
    "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "source": "web",
    "User-Agent": user_agent,
    "version": qwen_version,
    "x-accel-buffering": "no",
    "x-request-id": x_request_id,
}
if QWEN_BX_V:
    QWEN_HEADERS["bx-v"] = QWEN_BX_V
if QWEN_BX_UA:
    QWEN_HEADERS["bx-ua"] = QWEN_BX_UA
if QWEN_BX_UMIDTOKEN:
    QWEN_HEADERS["bx-umidtoken"] = QWEN_BX_UMIDTOKEN
