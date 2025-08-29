import requests
import time
import uuid
import json
import logging
from config import QWEN_HEADERS, QWEN_MODELS_URL, QWEN_NEW_CHAT_URL, QWEN_CHAT_COMPLETIONS_URL
from utils.cookie_parser import build_header

logger = logging.getLogger(__name__)

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
            combined_content = "\n\n".join(context_parts)
            
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
            qwen_data["messages"].append(qwen_msg)
        
        return qwen_data

# Global Qwen service instance
qwen_service = QwenService()
