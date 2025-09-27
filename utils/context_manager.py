import json
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class ContextManager:
    """Quản lý context length và cắt bớt messages khi cần thiết"""
    
    def __init__(self):
        self.context_threshold = 0.88  # 88% của context length
    
    def estimate_token_count(self, text: str) -> int:
        """Ước lượng số token từ text (1 token ≈ 0.75 từ)"""
        if not text or not isinstance(text, str):
            return 0
        # Ước lượng: 1 token ≈ 0.75 từ
        word_count = len(text.strip().split())
        return max(1, int(word_count / 0.75))
    
    def get_model_context_length(self, model_id: str, cached_models: List[Dict]) -> int:
        """Lấy context length của model từ cached models"""
        try:
            for model in cached_models:
                if model.get('id') == model_id:
                    info = model.get('info', {})
                    meta = info.get('meta', {})
                    context_length = meta.get('max_context_length')
                    if context_length and isinstance(context_length, (int, float)):
                        return int(context_length)
            # Default context length nếu không tìm thấy
            return 131072
        except Exception as e:
            logger.warning(f"Error getting context length for model {model_id}: {e}")
            return 131072
    
    def calculate_messages_token_count(self, messages: List[Dict]) -> int:
        """Tính tổng số token của tất cả messages"""
        total_tokens = 0
        for message in messages:
            if isinstance(message, dict):
                content = message.get('content', '')
                if isinstance(content, str):
                    total_tokens += self.estimate_token_count(content)
                elif isinstance(content, list):
                    # Xử lý content dạng list (có thể chứa text và image)
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            text_content = item.get('text', '')
                            total_tokens += self.estimate_token_count(text_content)
        return total_tokens
    
    def should_trim_context(self, messages: List[Dict], model_id: str, cached_models: List[Dict]) -> Tuple[bool, int, int]:
        """
        Kiểm tra xem có cần cắt bớt context không
        Returns: (should_trim, current_tokens, max_tokens)
        """
        try:
            current_tokens = self.calculate_messages_token_count(messages)
            max_tokens = self.get_model_context_length(model_id, cached_models)
            threshold_tokens = int(max_tokens * self.context_threshold)
            
            should_trim = current_tokens > threshold_tokens
            
            if should_trim:
                logger.info(f"Context trimming needed: {current_tokens}/{max_tokens} tokens (threshold: {threshold_tokens})")
            
            return should_trim, current_tokens, max_tokens
        except Exception as e:
            logger.error(f"Error checking context trim: {e}")
            return False, 0, 131072
    
    def trim_messages_to_fit_context(self, messages: List[Dict], model_id: str, cached_models: List[Dict]) -> List[Dict]:
        """
        Cắt bớt messages để fit trong context length
        Giữ lại system message và các message gần nhất
        """
        try:
            if not messages:
                return messages
            
            max_tokens = self.get_model_context_length(model_id, cached_models)
            threshold_tokens = int(max_tokens * self.context_threshold)
            
            # Tách system messages và other messages
            system_messages = []
            other_messages = []
            
            for message in messages:
                if isinstance(message, dict) and message.get('role') == 'system':
                    system_messages.append(message)
                else:
                    other_messages.append(message)
            
            # Nếu chỉ có system messages, giữ nguyên
            if not other_messages:
                return messages
            
            # Bắt đầu với system messages
            trimmed_messages = system_messages.copy()
            current_tokens = self.calculate_messages_token_count(system_messages)
            
            # Thêm messages từ cuối lên cho đến khi đạt threshold
            for message in reversed(other_messages):
                message_tokens = self.estimate_token_count(
                    message.get('content', '') if isinstance(message.get('content'), str) 
                    else str(message.get('content', ''))
                )
                
                if current_tokens + message_tokens <= threshold_tokens:
                    trimmed_messages.insert(len(system_messages), message)
                    current_tokens += message_tokens
                else:
                    break
            
            # Đảm bảo có ít nhất 1 message (không phải system)
            if len(trimmed_messages) == len(system_messages) and other_messages:
                # Nếu chỉ còn system messages, thêm message cuối cùng
                trimmed_messages.append(other_messages[-1])
            
            logger.info(f"Trimmed messages from {len(messages)} to {len(trimmed_messages)} messages")
            return trimmed_messages
            
        except Exception as e:
            logger.error(f"Error trimming messages: {e}")
            return messages
    
    def process_messages_for_context(self, messages: List[Dict], model_id: str, cached_models: List[Dict]) -> Tuple[List[Dict], Dict[str, Any]]:
        """
        Xử lý messages và trả về trimmed messages cùng với thông tin context
        """
        try:
            should_trim, current_tokens, max_tokens = self.should_trim_context(messages, model_id, cached_models)
            
            context_info = {
                "original_message_count": len(messages),
                "current_tokens": current_tokens,
                "max_tokens": max_tokens,
                "threshold_tokens": int(max_tokens * self.context_threshold),
                "trimmed": should_trim
            }
            
            if should_trim:
                trimmed_messages = self.trim_messages_to_fit_context(messages, model_id, cached_models)
                context_info["trimmed_message_count"] = len(trimmed_messages)
                context_info["trimmed_tokens"] = self.calculate_messages_token_count(trimmed_messages)
                return trimmed_messages, context_info
            else:
                return messages, context_info
                
        except Exception as e:
            logger.error(f"Error processing messages for context: {e}")
            return messages, {"error": str(e)}

# Global context manager instance
context_manager = ContextManager()
