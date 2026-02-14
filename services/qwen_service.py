import requests
import time
import uuid
import json
import logging
import os
import base64
import hashlib
from urllib.parse import urlparse, parse_qs, unquote_plus
from config import QWEN_HEADERS, QWEN_MODELS_URL, QWEN_NEW_CHAT_URL, QWEN_CHAT_COMPLETIONS_URL, QWEN_COMPLETIONS_BODY_VERSION, QWEN_REFERER_NEW_CHAT, TMP_FOLDER, curl_user_agent
from utils.cookie_parser import build_header

logger = logging.getLogger(__name__)

"""Cache global cho files đã upload: [{ 'file_url': str, 'hashed': str }]"""
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
            # Clear cache files khi tạo chat mới
            global images_hashed
            try:
                cache_size = len(images_hashed)
                images_hashed.clear()
                logger.info(f"Cleared file cache ({cache_size} files)")
            except Exception:
                images_hashed = []
                logger.info("Reset file cache")

            chat_data = {
                "title": "New Chat",
                "models": [model],
                "chat_mode": "normal",
                "chat_type": "t2t",
                "timestamp": int(time.time() * 1000),
                "project_id": ""
            }
            headers = build_header(QWEN_HEADERS)
            headers["Referer"] = QWEN_REFERER_NEW_CHAT
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
            "version": QWEN_COMPLETIONS_BODY_VERSION,
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
            # Upload files lên 0x0.st nếu có
            try:
                files_to_upload = []
                
                # Ảnh từ cấp cao (/api/generate)
                images = data.get('images', []) or []
                for img in images:
                    files_to_upload.append({'type': 'image', 'data': img})
                
                # Files từ từng message (/api/chat)
                try:
                    for _m in messages or []:
                        if isinstance(_m, dict):
                            # Ảnh từ message
                            if _m.get('images'):
                                imgs = _m.get('images')
                                if isinstance(imgs, list):
                                    for img in imgs:
                                        files_to_upload.append({'type': 'image', 'data': img})
                                else:
                                    files_to_upload.append({'type': 'image', 'data': imgs})
                            
                            # Text files từ message
                            if _m.get('files'):
                                text_files = _m.get('files')
                                if isinstance(text_files, list):
                                    for file in text_files:
                                        files_to_upload.append({'type': 'file', 'data': file})
                                else:
                                    files_to_upload.append({'type': 'file', 'data': text_files})
                except Exception as _e:
                    logger.warning(f"Collect message files failed: {_e}")
                
                if files_to_upload:
                    # Đảm bảo thư mục tạm
                    try:
                        if not os.path.isdir(TMP_FOLDER):
                            os.makedirs(TMP_FOLDER, exist_ok=True)
                    except Exception as _e:
                        logger.warning(f"Cannot create tmp folder {TMP_FOLDER}: {_e}")

                    for file_item in files_to_upload:
                        file_type = file_item.get('type', 'image')
                        file_data = file_item.get('data')
                        
                        if not file_data:
                            continue
                        # Decode base64 (hỗ trợ data URL)
                        file_bytes = None
                        ext = "bin"
                        content_type = "application/octet-stream"
                        
                        try:
                            if isinstance(file_data, str) and file_data.startswith("data:") and ";base64," in file_data:
                                header, b64data = file_data.split(",", 1)
                                try:
                                    mime = header.split(":", 1)[1].split(";")[0]
                                    content_type = mime
                                    # Lấy extension từ MIME type
                                    if "/" in mime:
                                        mime_type = mime.split("/", 1)[1]
                                        if mime_type == "jpeg":
                                            ext = "jpg"
                                        elif mime_type == "png":
                                            ext = "png"
                                        elif mime_type == "gif":
                                            ext = "gif"
                                        elif mime_type == "webp":
                                            ext = "webp"
                                        elif mime_type == "svg+xml":
                                            ext = "svg"
                                        elif mime_type == "plain":
                                            ext = "txt"
                                        elif mime_type == "python":
                                            ext = "py"
                                        elif mime_type == "javascript":
                                            ext = "js"
                                        elif mime_type == "css":
                                            ext = "css"
                                        elif mime_type == "html":
                                            ext = "html"
                                        elif mime_type == "json":
                                            ext = "json"
                                        elif mime_type == "xml":
                                            ext = "xml"
                                        elif mime_type == "csv":
                                            ext = "csv"
                                        elif mime_type == "pdf":
                                            ext = "pdf"
                                        elif mime_type == "zip":
                                            ext = "zip"
                                        elif mime_type == "x-icon":
                                            ext = "ico"
                                        elif mime_type == "x-bat":
                                            ext = "bat"
                                        elif mime_type == "x-sh":
                                            ext = "sh"
                                        elif mime_type == "x-powershell":
                                            ext = "ps1"
                                        elif mime_type == "x-cmd":
                                            ext = "cmd"
                                        elif mime_type == "x-bash":
                                            ext = "sh"
                                        elif mime_type == "x-zsh":
                                            ext = "zsh"
                                        elif mime_type == "x-fish":
                                            ext = "fish"
                                        elif mime_type == "x-yaml":
                                            ext = "yml"
                                        elif mime_type == "x-toml":
                                            ext = "toml"
                                        elif mime_type == "x-ini":
                                            ext = "ini"
                                        elif mime_type == "x-config":
                                            ext = "conf"
                                        elif mime_type == "x-log":
                                            ext = "log"
                                        elif mime_type == "x-markdown":
                                            ext = "md"
                                        elif mime_type == "x-rst":
                                            ext = "rst"
                                        elif mime_type == "x-asciidoc":
                                            ext = "adoc"
                                        else:
                                            ext = mime_type
                                except Exception:
                                    pass
                                file_bytes = base64.b64decode(b64data)
                            elif isinstance(file_data, str):
                                file_bytes = base64.b64decode(file_data)
                            elif isinstance(file_data, bytes):
                                file_bytes = file_data
                            else:
                                continue
                        except Exception as _e:
                            logger.warning(f"Cannot decode file base64: {_e}")
                            continue
                        
                        # Detect file type từ content nếu chưa có extension rõ ràng
                        if ext == "bin" and file_bytes:
                            try:
                                # Thử detect từ magic bytes
                                if file_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                                    ext = "png"
                                    content_type = "image/png"
                                elif file_bytes.startswith(b'\xff\xd8\xff'):
                                    ext = "jpg"
                                    content_type = "image/jpeg"
                                elif file_bytes.startswith(b'GIF87a') or file_bytes.startswith(b'GIF89a'):
                                    ext = "gif"
                                    content_type = "image/gif"
                                elif file_bytes.startswith(b'RIFF') and file_bytes[8:12] == b'WEBP':
                                    ext = "webp"
                                    content_type = "image/webp"
                                elif file_bytes.startswith(b'%PDF'):
                                    ext = "pdf"
                                    content_type = "application/pdf"
                                elif file_bytes.startswith(b'PK\x03\x04'):
                                    ext = "zip"
                                    content_type = "application/zip"
                                elif file_bytes.startswith(b'#!/usr/bin/env python') or file_bytes.startswith(b'#!python'):
                                    ext = "py"
                                    content_type = "text/x-python"
                                elif file_bytes.startswith(b'#!/bin/bash') or file_bytes.startswith(b'#!/usr/bin/bash') or file_bytes.startswith(b'#!/bin/sh'):
                                    ext = "sh"
                                    content_type = "text/x-sh"
                                elif file_bytes.startswith(b'@echo off') or file_bytes.startswith(b'@echo on'):
                                    ext = "bat"
                                    content_type = "text/x-bat"
                                elif file_bytes.startswith(b'#Requires') or file_bytes.startswith(b'param(') or file_bytes.startswith(b'function '):
                                    ext = "ps1"
                                    content_type = "text/x-powershell"
                                elif file_bytes.startswith(b'<?xml'):
                                    ext = "xml"
                                    content_type = "application/xml"
                                elif file_bytes.startswith(b'{') or file_bytes.startswith(b'['):
                                    ext = "json"
                                    content_type = "application/json"
                                elif file_bytes.startswith(b'<!DOCTYPE') or file_bytes.startswith(b'<html'):
                                    ext = "html"
                                    content_type = "text/html"
                                elif file_bytes.startswith(b'/*') or file_bytes.startswith(b'@import'):
                                    ext = "css"
                                    content_type = "text/css"
                                elif file_bytes.startswith(b'function') or file_bytes.startswith(b'var ') or file_bytes.startswith(b'const '):
                                    ext = "js"
                                    content_type = "application/javascript"
                                elif file_bytes.startswith(b'---') and b'\n' in file_bytes:
                                    ext = "yml"
                                    content_type = "text/x-yaml"
                                elif file_bytes.startswith(b'# ') and b'\n' in file_bytes:
                                    ext = "md"
                                    content_type = "text/x-markdown"
                                elif file_bytes.startswith(b'#') and b'\n' in file_bytes:
                                    # Có thể là text file với comments
                                    ext = "txt"
                                    content_type = "text/plain"
                                else:
                                    # Thử decode như text
                                    try:
                                        text_content = file_bytes.decode('utf-8')
                                        if text_content.isprintable() or '\n' in text_content:
                                            ext = "txt"
                                            content_type = "text/plain"
                                    except:
                                        pass
                            except Exception as _e:
                                logger.warning(f"Error detecting file type: {_e}")

                        # Hash nội dung file để kiểm tra cache
                        try:
                            hashed = hashlib.sha256(file_bytes).hexdigest()
                            logger.info(f"File hash: {hashed[:8]}... (size: {len(file_bytes)} bytes, type: {file_type})")
                        except Exception:
                            hashed = None
                            logger.warning("Cannot calculate file hash")

                        # Nếu đã upload trước đó, tái sử dụng URL
                        try:
                            if hashed:
                                logger.info(f"Looking for hash: {hashed[:8]}... in cache ({len(images_hashed)} items)")
                                for i, cache_item in enumerate(images_hashed):
                                    cache_hash = cache_item.get('hashed')
                                    if cache_hash:
                                        logger.info(f"Cache item {i}: {cache_hash[:8]}...")
                                        if cache_hash == hashed:
                                            cached = cache_item
                                            logger.info(f"MATCH FOUND! Using cached image: {cached.get('file_url')}")
                                            break
                                else:
                                    cached = None
                                    logger.info(f"No cache match found for hash: {hashed[:8]}...")
                            else:
                                cached = None
                        except Exception as _e:
                            cached = None
                            logger.warning(f"Error checking cache: {_e}")

                        if cached and cached.get('file_url'):
                            logger.info(f"Using cached file URL: {cached.get('file_url')}")
                            # Lấy filename từ URL
                            cached_url = cached.get('file_url')
                            url_filename = cached_url.split('/')[-1].split('?')[0] if '/' in cached_url else f"cached_{uuid.uuid4().hex}.{ext}"
                            
                            uploaded_files.append({
                                "type": file_type,
                                "file": {
                                    "created_at": int(time.time() * 1000),
                                    "data": {},
                                    "filename": url_filename,
                                    "hash": None,
                                    "id": str(uuid.uuid4()),
                                    "user_id": str(uuid.uuid4()),
                                    "meta": {
                                        "name": url_filename,
                                        "size": len(file_bytes),
                                        "content_type": content_type
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
                                "size": len(file_bytes),
                                "error": "",
                                "itemId": str(uuid.uuid4()),
                                "file_type": content_type,
                                "showType": "image" if content_type.startswith("image/") else "file",
                                "file_class": "vision" if content_type.startswith("image/") else "document",
                                "uploadTaskId": str(uuid.uuid4())
                            })
                            continue

                        # Lưu file tạm
                        ts_ms = int(time.time() * 1000)
                        filename = f"{file_type.upper()}_{ts_ms}_{uuid.uuid4().hex}.{ext}"
                        tmp_path = os.path.join(TMP_FOLDER, filename)
                        try:
                            with open(tmp_path, "wb") as f:
                                f.write(file_bytes)
                        except Exception as _e:
                            logger.warning(f"Cannot write temp file {tmp_path}: {_e}")
                            continue

                        # Upload lên 0x0.st
                        try:
                            with open(tmp_path, 'rb') as f:
                                files = {'file': (filename, f, content_type)}
                                headers = {
                                    'User-Agent': curl_user_agent,
                                    'Accept': '*/*'
                                }
                                response = requests.post('https://0x0.st', files=files, headers=headers, timeout=30)
                                
                                if response.status_code == 200:
                                    file_url = response.text.strip()
                                    if file_url.startswith('http'):
                                        logger.info(f"Upload {file_type} {filename} -> {file_url}")
                                        # Lấy filename từ URL
                                        url_filename = file_url.split('/')[-1].split('?')[0] if '/' in file_url else filename
                                        
                                        uploaded_files.append({
                                            "type": file_type,
                                            "file": {
                                                "created_at": int(time.time() * 1000),
                                                "data": {},
                                                "filename": url_filename,
                                                "hash": None,
                                                "id": str(uuid.uuid4()),
                                                "user_id": str(uuid.uuid4()),
                                                "meta": {
                                                    "name": url_filename,
                                                    "size": len(file_bytes),
                                                    "content_type": content_type
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
                                            "size": len(file_bytes),
                                            "error": "",
                                            "itemId": str(uuid.uuid4()),
                                            "file_type": content_type,
                                            "showType": "image" if content_type.startswith("image/") else "file",
                                            "file_class": "vision" if content_type.startswith("image/") else "document",
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
                                                logger.info(f"Cache size: {len(images_hashed)} files")
                                        except Exception as _e:
                                            logger.warning(f"Failed to save to cache: {_e}")
                                    else:
                                        logger.warning(f"Invalid response from 0x0.st for {filename}: {file_url}")
                                else:
                                    logger.warning(f"Upload to 0x0.st failed for {filename}: {response.status_code} - {response.text}")
                        except Exception as _e:
                            logger.warning(f"Upload {file_type} to 0x0.st failed for {filename}: {_e}")
                        finally:
                            # Xóa file tạm
                            try:
                                if os.path.exists(tmp_path):
                                    os.remove(tmp_path)
                            except Exception as _e:
                                logger.warning(f"Cannot remove temp file {tmp_path}: {_e}")

                    if uploaded_files:
                        qwen_msg["files"] = uploaded_files
            except Exception as e:
                logger.error(f"Error handling images upload: {e}")
            
            qwen_data["messages"].append(qwen_msg)
        
        return qwen_data

# Global Qwen service instance
qwen_service = QwenService()
