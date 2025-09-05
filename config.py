import uuid
x_request_id = str(uuid.uuid4())

# Application version
VERSION = "1.0.3"
TMP_FOLDER = "./tmp"

# URLs
QWEN_API_BASE = "https://chat.qwen.ai/api"
QWEN_MODELS_URL = f"{QWEN_API_BASE}/models"
QWEN_NEW_CHAT_URL = f"{QWEN_API_BASE}/v2/chats/new"
QWEN_CHAT_COMPLETIONS_URL = f"{QWEN_API_BASE}/v2/chat/completions"

user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
qwen_version = "0.0.191"
qwen_host = "chat.qwen.ai"
qwen_origin = "https://chat.qwen.ai"
qwen_referer = "https://chat.qwen.ai/c/guest"
curl_user_agent = "curl/8.12.1"

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
