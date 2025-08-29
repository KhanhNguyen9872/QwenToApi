import requests
import time
import uuid
import json
import logging
import os
import base64
import hashlib
from urllib.parse import urlparse, parse_qs, unquote_plus
from config import QWEN_HEADERS, QWEN_MODELS_URL, QWEN_NEW_CHAT_URL, QWEN_CHAT_COMPLETIONS_URL, TMP_FOLDER
from utils.cookie_parser import build_header

logger = logging.getLogger(__name__)

def _parse_url_params(url: str) -> dict:
    try:
        parsed = urlparse(url)
        query_dict = parse_qs(parsed.query, keep_blank_values=True)
        decoded_params = {k: [unquote_plus(v) for v in vals] for k, vals in query_dict.items()}
        simple_params = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in decoded_params.items()}
        return simple_params
    except Exception:
        return {}

"""Cache global cho ảnh đã upload: [{ 'file_url': str, 'hashed': str }]"""
images_hashed = []

class QwenService:
    """Service để tương tác với Qwen API"""
    
    def __init__(self):
        self.models_cache = None
    
    def get_models_from_qwen(self):
        """Lấy danh sách models từ Qwen API"""
        try:
            headers = build_header(QWEN_HEADERS)
            response = requests.get(QWEN_MODELS_URL, headers=headers)
            
            if response.status_code == 200:
                models_data = response.json()
                
                # Chuyển đổi format từ Qwen sang OpenAI
                openai_models = []
                for model in models_data.get('data', []):
                    # Chỉ lấy model active
                    info = model.get('info', {}) or {}
                    if not info.get('is_active', False):
                        continue

                    meta = info.get('meta', {}) or {}

                    # Lấy context length
                    max_context_length = meta.get('max_context_length')

                    # Lấy generation length với thứ tự ưu tiên
                    gen_len = meta.get('max_generation_length')
                    if gen_len is None:
                        gen_len = meta.get('max_thinking_generation_length')
                    if gen_len is None:
                        gen_len = meta.get('max_summary_generation_length')

                    # Lấy capabilities và abilities (nếu có)
                    capabilities = meta.get('capabilities', {}) or {}
                    abilities = meta.get('abilities', {}) or {}
                    max_thinking_generation_length = meta.get('max_thinking_generation_length')

                    # Gắn vào info.meta rút gọn để UI dùng
                    openai_models.append({
                        "id": model.get('id', 'qwen3-235b-a22b'),
                        "object": "model",
                        "owned_by": "organization_owner",
                        "info": {
                            "meta": {
                                "max_context_length": max_context_length,
                                "max_generation_length": gen_len,
                                "max_thinking_generation_length": max_thinking_generation_length,
                                "capabilities": capabilities,
                                "abilities": abilities
                            }
                        }
                    })
                self.models_cache = openai_models
                return openai_models
            else:
                logger.error(f"Qwen API error: {response.status_code} - {response.text}")
                # Fallback nếu API không hoạt động - trả về models giống LM Studio
                return []
        except Exception as e:
            logger.error(f"Error fetching models from Qwen API: {e}")
            return []
    
    def create_new_chat(self, model="qwen3-235b-a22b"):
        """Tạo chat mới từ Qwen API với model được chỉ định"""
        try:
            # Clear cache ảnh khi tạo chat mới
            global images_hashed
            try:
                images_hashed.clear()
            except Exception:
                images_hashed = []

            chat_data = {
                "title": "New Chat",
                "models": [model],
                "chat_mode": "guest",
                "chat_type": "t2t",
                "timestamp": int(time.time() * 1000)
            }
            
            headers = build_header(QWEN_HEADERS)
            response = requests.post(QWEN_NEW_CHAT_URL, headers=headers, json=chat_data)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    chat_id = result['data']['id']
                    return chat_id
                else:
                    logger.error(f"Failed to create chat: {result}")
            else:
                logger.error(f"Create chat error: {response.status_code} - {response.text}")
            return None
        except Exception as e:
            logger.error(f"Error creating new chat: {e}")
            return None
    
    def prepare_qwen_request(self, data, chat_id, model, parent_id=None):
        """Chuẩn bị request data cho Qwen API"""
        qwen_data = {
            "stream": data.get('stream', False),
            "incremental_output": data.get('stream', False),
            "chat_id": chat_id,
            "chat_mode": "normal",  # Thay đổi từ "guest" sang "normal"
            "model": model,
            "parent_id": parent_id,  # Sử dụng parent_id nếu có
            "messages": [],
            "timestamp": int(time.time())
        }
        
        # Xử lý tất cả messages để tạo context đầy đủ
        messages = data.get('messages', [])
        
        if messages:
            # Tạo context từ tất cả messages
            context_parts = []
            
            for i, msg in enumerate(messages):
                role = msg.get('role', '')
                content = msg.get('content', '')
                
                if role == 'system':
                    # System message - thêm vào đầu context
                    context_parts.append(f"System: {content}")
                elif role == 'user':
                    # User message - thêm vào context
                    context_parts.append(f"User: {content}")
                elif role == 'template':
                    # Assistant message - thêm vào context
                    context_parts.append(f"Assistant: {content}")
                elif role == 'prompt':
                    # Prompt message - thêm vào context
                    context_parts.append(f"Prompt: {content}")
                elif role == 'assistant':
                    # Assistant message - thêm vào context
                    context_parts.append(f"Assistant: {content}")
                else:
                    logger.warning(f"Unknown role: {role}")
            
            # Kết hợp tất cả context
            combined_content = ""
            for i in context_parts:
                combined_content += "```\n" + i + "\n```\n"
            
            qwen_msg = {
                "fid": str(uuid.uuid4()),
                "parentId": parent_id,  # Sử dụng parent_id nếu có
                "childrenIds": [],
                "role": "user",  # Luôn là user role cho Qwen
                "content": combined_content,
                "user_action": "chat",
                "files": [],
                "timestamp": int(time.time()),
                "models": [model],
                "chat_type": "t2t",
                "feature_config": {
                    "thinking_enabled": True,
                    "output_schema": "phase",
                    "thinking_budget": 2048
                },
                "extra": {
                    "meta": {
                        "subChatType": "t2t"
                    }
                },
                "sub_chat_type": "t2t",
                "parent_id": parent_id  # Sử dụng parent_id nếu có
            }

            uploaded_files = []
            # Upload ảnh lên Qwen nếu có
            try:
                images = []
                # Ảnh từ cấp cao (/api/generate)
                images.extend(data.get('images', []) or [])
                # Ảnh từ từng message (/api/chat)
                try:
                    for _m in messages or []:
                        if isinstance(_m, dict) and _m.get('images'):
                            imgs = _m.get('images')
                            if isinstance(imgs, list):
                                images.extend(imgs)
                            else:
                                images.append(imgs)
                except Exception as _e:
                    logger.warning(f"Collect message images failed: {_e}")
                if images:
                    # Đảm bảo thư mục tạm
                    try:
                        if not os.path.isdir(TMP_FOLDER):
                            os.makedirs(TMP_FOLDER, exist_ok=True)
                    except Exception as _e:
                        logger.warning(f"Cannot create tmp folder {TMP_FOLDER}: {_e}")

                    sts_url = "https://chat.qwen.ai/api/v2/files/getstsToken"
                    base_headers = build_header(QWEN_HEADERS)

                    for img in images:
                        # Decode base64 (hỗ trợ data URL)
                        img_bytes = None
                        ext = "jpg"
                        mime_type = "image/jpeg"
                        try:
                            if isinstance(img, str) and img.startswith("data:") and ";base64," in img:
                                header, b64data = img.split(",", 1)
                                try:
                                    mime = header.split(":", 1)[1].split(";")[0]
                                    if "/" in mime:
                                        ext = mime.split("/", 1)[1] or ext
                                        mime_type = mime or mime_type
                                except Exception:
                                    pass
                                img_bytes = base64.b64decode(b64data)
                            elif isinstance(img, str):
                                img_bytes = base64.b64decode(img)
                            elif isinstance(img, bytes):
                                img_bytes = img
                            else:
                                continue
                        except Exception as _e:
                            logger.warning(f"Cannot decode image base64: {_e}")
                            continue

                        # Hash nội dung ảnh để kiểm tra cache
                        try:
                            hashed = hashlib.sha256(img_bytes).hexdigest()
                        except Exception:
                            hashed = None

                        # Nếu đã upload trước đó, tái sử dụng URL
                        try:
                            if hashed:
                                cached = next((it for it in images_hashed if it.get('hashed') == hashed), None)
                            else:
                                cached = None
                        except Exception:
                            cached = None

                        if cached and cached.get('file_url'):
                            uploaded_files.append({
                                "name": f"CACHED_{uuid.uuid4().hex}.{ext}",
                                "size": len(img_bytes),
                                "type": "image",
                                "url": cached.get('file_url')
                            })
                            continue

                        # Lưu file tạm
                        ts_ms = int(time.time() * 1000)
                        filename = f"IMG_{ts_ms}_{uuid.uuid4().hex}.{ext}"
                        tmp_path = os.path.join(TMP_FOLDER, filename)
                        try:
                            with open(tmp_path, "wb") as f:
                                f.write(img_bytes)
                        except Exception as _e:
                            logger.warning(f"Cannot write temp image {tmp_path}: {_e}")
                            continue

                        filesize = len(img_bytes)

                        payload = {
                            "filename": filename,
                            "filesize": filesize,
                            "filetype": "image"
                        }

                        # Gọi getstsToken
                        file_url = None
                        security_token = None
                        try:
                            resp = requests.post(sts_url, json=payload, headers=base_headers, timeout=1)
                            resp_json = resp.json() if resp is not None else {}
                            if isinstance(resp_json, dict) and resp_json.get("success") is True:
                                file_url = ((resp_json.get("data") or {}).get("file_url"))
                                security_token = ((resp_json.get("data") or {}).get("security_token"))
                        except Exception as _e:
                            logger.warning(f"getstsToken failed for {filename}: {_e}")

                        if not file_url:
                            continue

                        # Tạo authorization từ file_url
                        auth_params = _parse_url_params(file_url)
                        try:
                            authorization = f"{auth_params.get('x-oss-signature-version')} Credential={auth_params.get('x-oss-credential')},Signature={auth_params.get('x-oss-signature')}"
                        except Exception:
                            authorization = None

                        # PUT file lên Qwen
                        put_url = None
                        try:
                            # Header đầy đủ theo yêu cầu OSS
                            put_headers = {}
                            if authorization:
                                put_headers["authorization"] = authorization
                            # Headers từ QWEN_HEADERS
                            try:
                                put_headers["Accept"] = QWEN_HEADERS.get("Accept", "*/*")
                                put_headers["Accept-Encoding"] = QWEN_HEADERS.get("Accept-Encoding", "gzip, deflate, br, zstd")
                                if QWEN_HEADERS.get("Accept-Language"):
                                    put_headers["Accept-Language"] = QWEN_HEADERS.get("Accept-Language")
                                if QWEN_HEADERS.get("Origin"):
                                    put_headers["Origin"] = QWEN_HEADERS.get("Origin")
                                if QWEN_HEADERS.get("Referer"):
                                    put_headers["Referer"] = QWEN_HEADERS.get("Referer")
                                if QWEN_HEADERS.get("User-Agent"):
                                    put_headers["User-Agent"] = QWEN_HEADERS.get("User-Agent")
                                # Optional fetch hints
                                if QWEN_HEADERS.get("sec-ch-ua"):
                                    put_headers["sec-ch-ua"] = QWEN_HEADERS.get("sec-ch-ua")
                                if QWEN_HEADERS.get("sec-ch-ua-mobile"):
                                    put_headers["sec-ch-ua-mobile"] = QWEN_HEADERS.get("sec-ch-ua-mobile")
                                if QWEN_HEADERS.get("sec-ch-ua-platform"):
                                    put_headers["sec-ch-ua-platform"] = QWEN_HEADERS.get("sec-ch-ua-platform")
                                put_headers["Sec-Fetch-Dest"] = "empty"
                                put_headers["Sec-Fetch-Mode"] = "cors"
                                put_headers["Sec-Fetch-Site"] = "cross-site"
                            except Exception:
                                pass

                            # OSS required headers
                            put_headers["x-oss-content-sha256"] = "UNSIGNED-PAYLOAD"
                            if auth_params.get("x-oss-date"):
                                put_headers["x-oss-date"] = auth_params.get("x-oss-date")
                            if security_token:
                                put_headers["x-oss-security-token"] = security_token
                            # Not strictly required but mimic browser
                            put_headers["x-oss-user-agent"] = "aliyun-sdk-js/6.23.0 Chrome 139.0.0.0 on Windows 10 64-bit"
                            put_headers["Connection"] = "keep-alive"

                            # Content-Type theo loại ảnh
                            put_headers["Content-Type"] = mime_type
                            # Host header
                            put_headers["Host"] = "qwen-webui-prod.oss-accelerate.aliyuncs.com"
                            put_url = file_url.split("?", 1)[0]
                            put_resp = requests.put(put_url, headers=put_headers, data=img_bytes, timeout=1)
                            logger.info(f"PUT image {filename} -> {put_resp.status_code}")
                            uploaded_files.append({
                                "name": filename,
                                "size": filesize,
                                "type": "image",
                                "url": put_url
                            })
                            # Lưu vào cache toàn cục
                            try:
                                if hashed and put_url:
                                    images_hashed.append({
                                        "file_url": put_url,
                                        "hashed": hashed
                                    })
                            except Exception:
                                pass

                            # Xác thực bằng GET sau khi upload
                            try:
                                # Ưu tiên GET base URL; nếu không 200 thì thử GET full signed URL
                                get_headers = {}
                                try:
                                    get_headers["Accept"] = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
                                    get_headers["Accept-Encoding"] = QWEN_HEADERS.get("Accept-Encoding", "gzip, deflate, br, zstd")
                                    if QWEN_HEADERS.get("Accept-Language"):
                                        get_headers["Accept-Language"] = QWEN_HEADERS.get("Accept-Language")
                                    if QWEN_HEADERS.get("Referer"):
                                        get_headers["Referer"] = QWEN_HEADERS.get("Referer")
                                    if QWEN_HEADERS.get("User-Agent"):
                                        get_headers["User-Agent"] = QWEN_HEADERS.get("User-Agent")
                                    if QWEN_HEADERS.get("sec-ch-ua"):
                                        get_headers["sec-ch-ua"] = QWEN_HEADERS.get("sec-ch-ua")
                                    if QWEN_HEADERS.get("sec-ch-ua-mobile"):
                                        get_headers["sec-ch-ua-mobile"] = QWEN_HEADERS.get("sec-ch-ua-mobile")
                                    if QWEN_HEADERS.get("sec-ch-ua-platform"):
                                        get_headers["sec-ch-ua-platform"] = QWEN_HEADERS.get("sec-ch-ua-platform")
                                    get_headers["Sec-Fetch-Dest"] = "image"
                                    get_headers["Sec-Fetch-Mode"] = "no-cors"
                                    get_headers["Sec-Fetch-Site"] = "cross-site"
                                except Exception:
                                    pass

                                get_resp = requests.get(put_url, headers=get_headers, timeout=1)
                                if get_resp.status_code != 200:
                                    # Thử lại với full URL có query (nếu cần token)
                                    try:
                                        get_resp2 = requests.get(file_url, headers=get_headers, timeout=1)
                                        logger.info(f"GET verify image (fallback) {filename} -> {get_resp2.status_code}")
                                    except Exception as _e:
                                        logger.warning(f"GET verify (fallback) failed for {filename}: {_e}")
                                else:
                                    logger.info(f"GET verify image {filename} -> {get_resp.status_code}")
                            except Exception as _e:
                                logger.warning(f"GET verify failed for {filename}: {_e}")
                        except Exception as _e:
                            logger.warning(f"Upload image to Qwen failed for {filename}: {_e}")
                        finally:
                            # Xóa file tạm
                            try:
                                if os.path.exists(tmp_path):
                                    os.remove(tmp_path)
                            except Exception as _e:
                                logger.warning(f"Cannot remove temp image {tmp_path}: {_e}")

                    if uploaded_files:
                        qwen_msg["files"] = uploaded_files
            except Exception as e:
                logger.error(f"Error handling images upload: {e}")
            
            print(uploaded_files)
            qwen_data["messages"].append(qwen_msg)
        
        return qwen_data

# Global Qwen service instance
qwen_service = QwenService()
