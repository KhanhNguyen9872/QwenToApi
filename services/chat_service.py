import json
import time
import uuid
import requests
import logging
from models.request_state import RequestState
from services.qwen_service import qwen_service
from utils.ui_manager import ui_manager
from utils.chat_manager import chat_manager
from config import QWEN_HEADERS, QWEN_CHAT_COMPLETIONS_URL
from utils.cookie_parser import build_header

logger = logging.getLogger(__name__)

class ChatService:
    """Service xử lý chat completions"""
    
    def __init__(self):
        pass
    
    def stream_qwen_response(self, data, request_state=None):
        """Stream response from Qwen API with think mode support
        
        Think mode: When Qwen returns phase="think", the server will:
        - Send <think> tag when think mode starts
        - Stream content normally during think mode
        - Send </think> tag when think mode ends (status="finished")
        
        Answer mode: After think mode, Qwen switches to phase="answer" for normal response
        """
        model = data.get('model', 'qwen3-235b-a22b')
        
        # Tạo request state nếu chưa có
        if request_state is None:
            request_id = str(uuid.uuid4())
            request_state = RequestState(request_id, model)
                
        try:
            # Sử dụng chat_id hiện tại hoặc tạo mới nếu chưa có
            chat_id = chat_manager.get_current_chat_id()
            if not chat_id:
                chat_id = chat_manager.initialize_chat(model)
                if not chat_id:
                    logger.error("Failed to create new chat")
                    yield f"data: {json.dumps({'error': 'Failed to create new chat'})}\n\n"
                    return
            
            # Lấy parent_id hiện tại
            parent_id = chat_manager.get_current_parent_id()
            
            # Chuẩn bị request cho Qwen API
            qwen_data = qwen_service.prepare_qwen_request(data, chat_id, model, parent_id)
            
            
            # Gửi request đến Qwen API
            # Build headers with cookie from settings
            headers = build_header(QWEN_HEADERS)

            response = requests.post(
                f"{QWEN_CHAT_COMPLETIONS_URL}?chat_id={chat_id}",
                headers=headers,
                json=qwen_data,
                stream=True,
                timeout=300  # 5 phút timeout
            )
                        
            # Kiểm tra response content trước khi xử lý
            try:
                # Chỉ log response headers và status, không log content vì có thể là binary/compressed            
                # Kiểm tra content-type để xử lý phù hợp
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    try:
                        response_json = response.json()
                        
                        if not response_json.get('success', True):
                            error_code = response_json.get('data', {}).get('code', 'Unknown')
                            error_details = response_json.get('data', {}).get('details', 'Unknown error')
                            logger.error(f"Qwen API error: {error_code} - {error_details}")
                            
                            if error_code == "Bad_Request" and "chat is in progress" in error_details:
                                error_msg = "Chat is currently in progress. Please wait for the current request to complete."
                            elif error_code == "Bad_Request" and "parent_id" in error_details and "not exist" in error_details:
                                # Xử lý lỗi parent_id không tồn tại
                                logger.warning(f"Parent ID not exist error detected: {error_details}")
                                
                                # Tạo chat mới và reset parent_id
                                new_chat_id = chat_manager.create_new_chat(model)
                                if new_chat_id:
                                    # Gửi lại request với parent_id = None
                                    qwen_data = qwen_service.prepare_qwen_request(data, new_chat_id, model, None)
                                    
                                    retry_response = requests.post(
                                        f"{QWEN_CHAT_COMPLETIONS_URL}?chat_id={new_chat_id}",
                                        headers=headers,
                                        json=qwen_data,
                                        stream=True,
                                        timeout=300
                                    )
                                    
                                    if retry_response.status_code == 200:
                                        # Tiếp tục xử lý response từ retry
                                        response = retry_response
                                        # Tiếp tục xử lý response bình thường
                                        yield from self._process_qwen_stream_response(response, model, request_state)
                                        return
                                    else:
                                        logger.error(f"Retry failed with status: {retry_response.status_code}")
                                        error_msg = f"Failed to retry with new chat: {retry_response.status_code}"
                                        yield f"data: {json.dumps({'error': error_msg})}\n\n"
                                        return
                                else:
                                    logger.error("Failed to create new chat for retry")
                                    error_msg = "Failed to create new chat for retry"
                                    yield f"data: {json.dumps({'error': error_msg})}\n\n"
                                    return
                            else:
                                error_msg = f"Qwen API error: {error_code} - {error_details}"
                                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                                return
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing JSON response: {e}")
                else:
                    logger.info(f"Qwen API response is not JSON (content-type: {content_type})")
            except Exception as e:
                logger.error(f"Error reading response content: {e}")
            
            if response.status_code == 200:
                yield from self._process_qwen_stream_response(response, model, request_state)
            else:
                error_msg = f"Error from Qwen API: {response.status_code}"
                logger.error(f"Qwen API error: {response.status_code} - {response.text}")
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                
        except requests.exceptions.Timeout:
            error_msg = "Request timeout - server took too long to respond"
            logger.error("Qwen API request timeout")
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(f"Stream function error: {e}")
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
    
    def _process_qwen_stream_response(self, response, model, request_state):
        """Xử lý response streaming từ Qwen API"""
        chunk_count = 0
        # Thu thập nội dung assistant để đẩy vào Chat tab khi kết thúc
        collected_answer = []
        last_user_text = ""
        try:
            # Thử lấy user message cuối cùng từ request_state hoặc dữ liệu lưu cục bộ (không có: để server trích sau)
            pass
        except Exception:
            pass
        
        # Xử lý response content dựa trên encoding
        content_encoding = response.headers.get('content-encoding', '').lower()
        
        if content_encoding == 'br':
            # Brotli compression - xử lý streaming từng line riêng biệt
            try:
                import brotli
                logger.info("Processing Brotli compressed streaming response...")
                
                # Xử lý từng line streaming riêng biệt với timeout
                start_time = time.time()
                for line in response.iter_lines():
                    # Kiểm tra timeout mỗi 10 giây
                    if time.time() - start_time > 300:  # 5 phút timeout
                        logger.error("Stream reading timeout")
                        yield f"data: {json.dumps({'error': 'Stream reading timeout'})}\n\n"
                        return
                        
                    if line:
                        try:
                            # Raw data đã được decompress sẵn, chỉ cần decode
                            line_text = line.decode('utf-8')
                            
                            if line_text.startswith('data: '):
                                data_content = line_text[6:]  # Bỏ 'data: '
                                if data_content.strip():
                                    chunk_count += 1
                                    # Chuyển đổi response format để giống LM Studio
                                    try:
                                        qwen_data = json.loads(data_content)
                                        
                                        # Xử lý response.created để lấy parent_id và response_id
                                        if 'response.created' in qwen_data:
                                            response_created = qwen_data['response.created']
                                            parent_id = response_created.get('parent_id')
                                            response_id = response_created.get('response_id')
                                            if parent_id and response_id:
                                                chat_manager.update_parent_info(parent_id, response_id)
                                            continue  # Bỏ qua chunk này, không gửi về client
                                        
                                        if 'choices' in qwen_data and len(qwen_data['choices']) > 0:
                                            # Stream tất cả content như LM Studio thực sự làm
                                            delta = qwen_data['choices'][0].get('delta', {})
                                            finish_reason = qwen_data['choices'][0].get('finish_reason', None)
                                            phase = delta.get('phase', None)
                                            
                                            # Log phase nếu có thay đổi
                                            request_state.log_phase_change(phase)
                                            
                                            # Xử lý think mode
                                            if phase == "think":
                                                # Nếu bắt đầu think mode và chưa gửi <think> tag
                                                if not request_state.think_started:
                                                    request_state.think_started = True
                                                    # Gửi <think> tag
                                                    openai_format = {
                                                        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
                                                        "object": "chat.completion.chunk",
                                                        "created": int(time.time()),
                                                        "model": model,
                                                        "system_fingerprint": model,
                                                        "choices": [{
                                                            "index": 0,
                                                            "delta": {"content": "<think>"},
                                                            "logprobs": None,
                                                            "finish_reason": None
                                                        }]
                                                    }
                                                    yield f"data: {json.dumps(openai_format)}\n\n"
                                                
                                                # Gửi content trong think mode
                                                if 'content' in delta:
                                                    openai_format = {
                                                        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
                                                        "object": "chat.completion.chunk",
                                                        "created": int(time.time()),
                                                        "model": model,
                                                        "system_fingerprint": model,
                                                        "choices": [{
                                                            "index": 0,
                                                            "delta": {"content": delta['content']},
                                                            "logprobs": None,
                                                            "finish_reason": finish_reason
                                                        }]
                                                    }
                                                    # Thu thập content để hiển thị sau
                                                    try:
                                                        if 'content' in delta and isinstance(delta['content'], str):
                                                            collected_answer.append(delta['content'])
                                                    except Exception:
                                                        pass
                                                    yield f"data: {json.dumps(openai_format)}\n\n"
                                                
                                                # Nếu think mode kết thúc (status finished)
                                                if delta.get('status') == 'finished':
                                                    # Gửi </think> tag
                                                    openai_format = {
                                                        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
                                                        "object": "chat.completion.chunk",
                                                        "created": int(time.time()),
                                                        "model": model,
                                                        "system_fingerprint": model,
                                                        "choices": [{
                                                            "index": 0,
                                                            "delta": {"content": "</think>"},
                                                            "logprobs": None,
                                                            "finish_reason": None
                                                        }]
                                                    }
                                                    # Thu thập content để hiển thị sau
                                                    try:
                                                        if 'content' in delta and isinstance(delta['content'], str):
                                                            collected_answer.append(delta['content'])
                                                    except Exception:
                                                        pass
                                                    yield f"data: {json.dumps(openai_format)}\n\n"
                                                    # Reset think state
                                                    request_state.think_started = False
                                            elif phase == "answer" or phase is None:
                                                # Normal content (answer phase hoặc không có phase)
                                                if 'content' in delta:
                                                    # Format giống LM Studio
                                                    openai_format = {
                                                        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
                                                        "object": "chat.completion.chunk",
                                                        "created": int(time.time()),
                                                        "model": model,
                                                        "system_fingerprint": model,
                                                        "choices": [{
                                                            "index": 0,
                                                            "delta": {"content": delta['content']},
                                                            "logprobs": None,
                                                            "finish_reason": finish_reason
                                                        }]
                                                    }
                                                    yield f"data: {json.dumps(openai_format)}\n\n"
                                            
                                            # Nếu có finish_reason, gửi [DONE] message
                                            if finish_reason:
                                                # Khi kết thúc, đẩy lịch sử chat vào UI (user + full assistant)
                                                try:
                                                    full_answer = ''.join(collected_answer)
                                                    # Lấy user text cuối cùng từ chat_manager (nếu có)
                                                    try:
                                                        from utils.chat_manager import chat_manager as _cm
                                                        # Không có API lấy user message; fallback: để trống, client hiển thị vẫn OK
                                                        last_user_text = last_user_text or ""
                                                    except Exception:
                                                        last_user_text = last_user_text or ""
                                                    ui_manager.add_chat_messages(last_user_text, full_answer)
                                                except Exception:
                                                    pass
                                                yield "data: [DONE]\n\n"
                                                return
                                        else:
                                            pass
                                            # Bỏ qua các message không có choices
                                    except json.JSONDecodeError as e:
                                        logger.error(f"JSON decode error on chunk {chunk_count}: {e}")
                                        # Gửi error message format đúng
                                        error_format = {
                                            "error": {
                                                "message": f"Invalid JSON in response: {str(e)}",
                                                "type": "server_error"
                                            }
                                        }
                                        yield f"data: {json.dumps(error_format)}\n\n"
                                        return
                        except Exception as e:
                            logger.error(f"Error processing line: {e}")
                            continue
            except Exception as e:
                logger.error(f"Error in Brotli streaming: {e}")
                yield f"data: {json.dumps({'error': f'Streaming error: {str(e)}'})}\n\n"
                return
        else:
            # Xử lý response không nén
            logger.info("Processing uncompressed streaming response...")
            for line in response.iter_lines():
                if line:
                    try:
                        line_text = line.decode('utf-8')
                        if line_text.startswith('data: '):
                            data_content = line_text[6:]
                            if data_content.strip():
                                chunk_count += 1
                                try:
                                    qwen_data = json.loads(data_content)
                                    
                                    # Xử lý response.created
                                    if 'response.created' in qwen_data:
                                        response_created = qwen_data['response.created']
                                        parent_id = response_created.get('parent_id')
                                        response_id = response_created.get('response_id')
                                        if parent_id and response_id:
                                            chat_manager.update_parent_info(parent_id, response_id)
                                        continue
                                    
                                    if 'choices' in qwen_data and len(qwen_data['choices']) > 0:
                                        delta = qwen_data['choices'][0].get('delta', {})
                                        finish_reason = qwen_data['choices'][0].get('finish_reason', None)
                                        phase = delta.get('phase', None)
                                        
                                        request_state.log_phase_change(phase)
                                        
                                        if 'content' in delta:
                                            openai_format = {
                                                "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
                                                "object": "chat.completion.chunk",
                                                "created": int(time.time()),
                                                "model": model,
                                                "system_fingerprint": model,
                                                "choices": [{
                                                    "index": 0,
                                                    "delta": {"content": delta['content']},
                                                    "logprobs": None,
                                                    "finish_reason": finish_reason
                                                }]
                                            }
                                            yield f"data: {json.dumps(openai_format)}\n\n"
                                        
                                        if finish_reason:
                                            try:
                                                full_answer = ''.join(collected_answer)
                                                last_user_text = last_user_text or ""
                                                ui_manager.add_chat_messages(last_user_text, full_answer)
                                            except Exception:
                                                pass
                                            yield "data: [DONE]\n\n"
                                            return
                                except json.JSONDecodeError as e:
                                    logger.error(f"JSON decode error: {e}")
                                    continue
                    except Exception as e:
                        logger.error(f"Error processing line: {e}")
                        continue
    
    def _process_qwen_non_streaming_response(self, response, model):
        """Xử lý non-streaming response từ Qwen API"""
        qwen_response = response.json()
        
        # Xử lý response.created để lấy parent_id và response_id (cho non-streaming)
        if 'response' in qwen_response and 'created' in qwen_response['response']:
            response_created = qwen_response['response']['created']
            parent_id = response_created.get('parent_id')
            response_id = response_created.get('response_id')
            if parent_id and response_id:
                chat_manager.update_parent_info(parent_id, response_id)
        
        # Chuyển đổi response từ Qwen format sang OpenAI format
        openai_response = {
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": qwen_response.get('choices', [{}])[0].get('message', {}).get('content', '')
                },
                "finish_reason": "stop"
            }],
            "usage": qwen_response.get('usage', {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            })
        }
        return openai_response

    def _collect_full_content_via_stream(self, data, model):
        """Fallback: gọi Qwen ở chế độ streaming để gom full content cho non-streaming API."""
        try:
            # Sử dụng chat_id hiện tại hoặc tạo mới nếu chưa có
            chat_id = chat_manager.get_current_chat_id()
            if not chat_id:
                chat_id = chat_manager.initialize_chat(model)
                if not chat_id:
                    return ""

            parent_id = chat_manager.get_current_parent_id()
            qwen_data = qwen_service.prepare_qwen_request({**data, "stream": True, "incremental_output": True}, chat_id, model, parent_id)

            headers = build_header(QWEN_HEADERS)
            import requests
            response = requests.post(
                f"{QWEN_CHAT_COMPLETIONS_URL}?chat_id={chat_id}",
                headers=headers,
                json=qwen_data,
                stream=True,
                timeout=300
            )

            if response.status_code != 200:
                return ""

            full_content = []
            thinking_started = False

            for line in response.iter_lines():
                if not line:
                    continue
                line_str = line.decode('utf-8')
                if not line_str.startswith('data: '):
                    continue
                try:
                    chunk = json.loads(line_str[6:])
                except Exception:
                    continue
                if 'response.created' in chunk:
                    # cập nhật parent/response id nếu có
                    try:
                        response_created = chunk['response.created']
                        parent_id = response_created.get('parent_id')
                        response_id = response_created.get('response_id')
                        if parent_id and response_id:
                            chat_manager.update_parent_info(parent_id, response_id)
                    except Exception:
                        pass
                    continue
                try:
                    if chunk.get('choices') and chunk['choices'][0].get('delta'):
                        delta = chunk['choices'][0]['delta']
                        phase = delta.get('phase')
                        content = delta.get('content')
                        status = delta.get('status')
                        if phase == 'think':
                            if not thinking_started:
                                full_content.append('<think>')
                                thinking_started = True
                            if content:
                                full_content.append(content)
                            if status == 'finished' and thinking_started:
                                full_content.append('</think>')
                                thinking_started = False
                        else:
                            if content:
                                full_content.append(content)
                        finish_reason = chunk['choices'][0].get('finish_reason')
                        if finish_reason:
                            break
                except Exception:
                    continue

            return ''.join(full_content)
        except Exception:
            return ""
    
    def stream_qwen_response_non_streaming(self, data):
        """Non-streaming response from Qwen API"""
        model = data.get('model', 'qwen3-235b-a22b')
        
        try:
            # Sử dụng chat_id hiện tại hoặc tạo mới nếu chưa có
            chat_id = chat_manager.get_current_chat_id()
            if not chat_id:
                chat_id = chat_manager.initialize_chat(model)
                if not chat_id:
                    return {
                        "error": {
                            "message": "Failed to create new chat",
                            "type": "server_error"
                        }
                    }, 500
            
            # Lấy parent_id hiện tại
            parent_id = chat_manager.get_current_parent_id()
            
            # Chuẩn bị request cho Qwen API
            qwen_data = qwen_service.prepare_qwen_request(data, chat_id, model, parent_id)
            
            # Gửi request đến Qwen API
            headers = build_header(QWEN_HEADERS)

            response = requests.post(
                f"{QWEN_CHAT_COMPLETIONS_URL}?chat_id={chat_id}",
                headers=headers,
                json=qwen_data,
                timeout=300  # 5 phút timeout
            )
                        
            # Kiểm tra response content cho non-streaming
            try:
                
                # Kiểm tra content-type để xử lý phù hợp
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    try:
                        response_json = response.json()
                        
                        if not response_json.get('success', True):
                            error_code = response_json.get('data', {}).get('code', 'Unknown')
                            error_details = response_json.get('data', {}).get('details', 'Unknown error')
                            logger.error(f"Qwen API error: {error_code} - {error_details}")
                            
                            if error_code == "Bad_Request" and "chat is in progress" in error_details:
                                error_msg = "Chat is currently in progress. Please wait for the current request to complete."
                            elif error_code == "Bad_Request" and "parent_id" in error_details and "not exist" in error_details:
                                # Xử lý lỗi parent_id không tồn tại cho non-streaming
                                logger.warning(f"Parent ID not exist error detected: {error_details}")
                                
                                # Tạo chat mới và reset parent_id
                                new_chat_id = chat_manager.create_new_chat(model)
                                if new_chat_id:
                                    # Gửi lại request với parent_id = None
                                    qwen_data = qwen_service.prepare_qwen_request(data, new_chat_id, model, None)
                                    
                                    retry_response = requests.post(
                                        f"{QWEN_CHAT_COMPLETIONS_URL}?chat_id={new_chat_id}",
                                        headers=headers,
                                        json=qwen_data,
                                        timeout=300
                                    )
                                    
                                    if retry_response.status_code == 200:
                                        # Tiếp tục xử lý response từ retry
                                        response = retry_response
                                        # Tiếp tục xử lý response bình thường
                                        return self._process_qwen_non_streaming_response(response, model)
                                    else:
                                        logger.error(f"Retry failed with status: {retry_response.status_code}")
                                        error_msg = f"Failed to retry with new chat: {retry_response.status_code}"
                                        return {
                                            "error": {
                                                "message": error_msg,
                                                "type": "server_error"
                                            }
                                        }, 500
                                else:
                                    logger.error("Failed to create new chat for retry")
                                    error_msg = "Failed to create new chat for retry"
                                    return {
                                        "error": {
                                            "message": error_msg,
                                            "type": "server_error"
                                        }
                                    }, 500
                            else:
                                error_msg = f"Qwen API error: {error_code} - {error_details}"
                            
                            return {
                                "error": {
                                    "message": error_msg,
                                    "type": "server_error"
                                }
                            }, 500
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing JSON response: {e}")
                else:
                    logger.info(f"Qwen API response is not JSON (content-type: {content_type})")
            except Exception as e:
                logger.error(f"Error reading response content: {e}")
            
            if response.status_code == 200:
                result = self._process_qwen_non_streaming_response(response, model)
                try:
                    # Extract user message and assistant full content for chat history
                    user_text = ""
                    msgs = data.get('messages') or []
                    for m in reversed(msgs):
                        if isinstance(m, dict) and m.get('role') == 'user':
                            user_text = str(m.get('content') or '')
                            break
                    assistant_text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    # Fallback nếu content rỗng: gom lại qua stream
                    if not assistant_text:
                        assistant_text = self._collect_full_content_via_stream(data, model)
                        if assistant_text:
                            # cập nhật vào result để trả về cho client theo OpenAI format
                            try:
                                result['choices'][0]['message']['content'] = assistant_text
                                # usage tokens có thể không chính xác; giữ nguyên nếu có
                            except Exception:
                                pass
                    ui_manager.add_chat_messages(user_text, assistant_text)
                except Exception:
                    pass
                return result
            else:
                return {
                    "error": {
                        "message": f"Error from Qwen API: {response.status_code}",
                        "type": "server_error"
                    }
                }, 500
                
        except requests.exceptions.Timeout:
            return {
                "error": {
                    "message": "Request timeout - server took too long to respond",
                    "type": "server_error"
                }
            }, 408
        except Exception as e:
            return {
                "error": {
                    "message": f"Error: {str(e)}",
                    "type": "server_error"
                }
            }, 500

# Global chat service instance
chat_service = ChatService()
