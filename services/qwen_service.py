import requests
import time
import uuid
import json
import logging
import os
import base64
import hashlib
from urllib.parse import urlparse, parse_qs, unquote_plus
from config import QWEN_HEADERS, QWEN_MODELS_URL, QWEN_NEW_CHAT_URL, QWEN_CHAT_COMPLETIONS_URL, TMP_FOLDER, curl_user_agent
from utils.cookie_parser import build_header

logger = logging.getLogger(__name__)

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
                cache_size = len(images_hashed)
                images_hashed.clear()
                logger.info(f"Cleared image cache ({cache_size} images)")
            except Exception:
                images_hashed = []
                logger.info("Reset image cache")

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
                    "thinking_enabled": False,
                    "output_schema": "phase"
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
            # Upload ảnh lên 0x0.st nếu có
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

                    for img in images:
                        # Decode base64 (hỗ trợ data URL)
                        img_bytes = None
                        ext = "jpg"
                        try:
                            if isinstance(img, str) and img.startswith("data:") and ";base64," in img:
                                header, b64data = img.split(",", 1)
                                try:
                                    mime = header.split(":", 1)[1].split(";")[0]
                                    if "/" in mime:
                                        ext = mime.split("/", 1)[1] or ext
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
                            logger.info(f"Image hash: {hashed[:8]}... (size: {len(img_bytes)} bytes)")
                        except Exception:
                            hashed = None
                            logger.warning("Cannot calculate image hash")

                        # Nếu đã upload trước đó, tái sử dụng URL
                        try:
                            if hashed:
                                cached = next((it for it in images_hashed if it.get('hashed') == hashed), None)
                                if cached:
                                    logger.info(f"Found cached image: {cached.get('file_url')}")
                                else:
                                    logger.info(f"No cache found for hash: {hashed[:8]}...")
                            else:
                                cached = None
                        except Exception:
                            cached = None

                        if cached and cached.get('file_url'):
                            logger.info(f"Using cached image URL: {cached.get('file_url')}")
                            # Lấy filename từ URL
                            cached_url = cached.get('file_url')
                            url_filename = cached_url.split('/')[-1].split('?')[0] if '/' in cached_url else f"cached_{uuid.uuid4().hex}.{ext}"
                            
                            uploaded_files.append({
                                "type": "image",
                                "file": {
                                    "created_at": int(time.time() * 1000),
                                    "data": {},
                                    "filename": url_filename,
                                    "hash": None,
                                    "id": str(uuid.uuid4()),
                                    "user_id": str(uuid.uuid4()),
                                    "meta": {
                                        "name": url_filename,
                                        "size": len(img_bytes),
                                        "content_type": f"image/{ext}"
                                    },
                                    "update_at": int(time.time() * 1000)
                                },
                                "id": str(uuid.uuid4()),
                                "url": cached_url,
                                "name": url_filename,
                                "collection_name": "",
                                "progress": 0,
                                "status": "uploaded",
                                "greenNet": "success",
                                "size": len(img_bytes),
                                "error": "",
                                "itemId": str(uuid.uuid4()),
                                "file_type": f"image/{ext}",
                                "showType": "image",
                                "file_class": "vision",
                                "uploadTaskId": str(uuid.uuid4())
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

                        # Upload lên 0x0.st
                        try:
                            with open(tmp_path, 'rb') as f:
                                files = {'file': (filename, f, 'image/jpeg')}
                                headers = {
                                    'User-Agent': curl_user_agent,
                                    'Accept': '*/*'
                                }
                                response = requests.post('https://0x0.st', files=files, headers=headers, timeout=30)
                                
                                if response.status_code == 200:
                                    file_url = response.text.strip()
                                    if file_url.startswith('http'):
                                        logger.info(f"Upload image {filename} -> {file_url}")
                                        # Lấy filename từ URL
                                        url_filename = file_url.split('/')[-1].split('?')[0] if '/' in file_url else filename
                                        
                                        uploaded_files.append({
                                            "type": "image",
                                            "file": {
                                                "created_at": int(time.time() * 1000),
                                                "data": {},
                                                "filename": url_filename,
                                                "hash": None,
                                                "id": str(uuid.uuid4()),
                                                "user_id": str(uuid.uuid4()),
                                                "meta": {
                                                    "name": url_filename,
                                                    "size": len(img_bytes),
                                                    "content_type": f"image/{ext}"
                                                },
                                                "update_at": int(time.time() * 1000)
                                            },
                                            "id": str(uuid.uuid4()),
                                            "url": file_url,
                                            "name": url_filename,
                                            "collection_name": "",
                                            "progress": 0,
                                            "status": "uploaded",
                                            "greenNet": "success",
                                            "size": len(img_bytes),
                                            "error": "",
                                            "itemId": str(uuid.uuid4()),
                                            "file_type": f"image/{ext}",
                                            "showType": "image",
                                            "file_class": "vision",
                                            "uploadTaskId": str(uuid.uuid4())
                                        })
                                        # Lưu vào cache toàn cục
                                        try:
                                            if hashed and file_url:
                                                images_hashed.append({
                                                    "file_url": file_url,
                                                    "hashed": hashed
                                                })
                                                logger.info(f"Saved to cache: {hashed[:8]}... -> {file_url}")
                                                logger.info(f"Cache size: {len(images_hashed)} images")
                                        except Exception as _e:
                                            logger.warning(f"Failed to save to cache: {_e}")
                                    else:
                                        logger.warning(f"Invalid response from 0x0.st for {filename}: {file_url}")
                                else:
                                    logger.warning(f"Upload to 0x0.st failed for {filename}: {response.status_code} - {response.text}")
                        except Exception as _e:
                            logger.warning(f"Upload image to 0x0.st failed for {filename}: {_e}")
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
