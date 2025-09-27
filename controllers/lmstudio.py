from flask import Blueprint, jsonify, Response, request, current_app
import time
import uuid

from utils.request_utils import parse_json_request
from utils.context_manager import context_manager


lmstudio_bp = Blueprint('lmstudio', __name__)


def _make_display_data_short(data, max_len: int = 200):
    import copy
    try:
        display_data = copy.deepcopy(data) if data else {}
        if 'messages' in display_data and isinstance(display_data['messages'], list):
            for msg in display_data['messages']:
                if isinstance(msg, dict) and 'content' in msg:
                    content = msg['content']
                    if isinstance(content, str) and len(content) > max_len:
                        msg['content'] = content[:max_len] + "..."
        return display_data
    except Exception:
        return data


@lmstudio_bp.route('/v1/models', methods=['GET', 'OPTIONS'])
def list_models():
    app = current_app
    get_cached_qwen_models = app.config['get_cached_qwen_models']
    SERVER_MODE = app.config.get('SERVER_MODE')

    if request.method == 'OPTIONS':
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response


    models = get_cached_qwen_models()

    if SERVER_MODE == "ollama":
        formatted_models = []
        for model in models:
            model_id = model.get('id', '')
            if model_id:
                model_name_with_latest = f"{model_id}:latest"
                formatted_models.append({
                    "id": model_name_with_latest,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "library"
                })
    else:
        formatted_models = models

    response = jsonify({
        "object": "list",
        "data": formatted_models
    })
    response.headers['Content-Type'] = 'application/json'
    return response


@lmstudio_bp.route('/v1/models/<model_id>', methods=['GET'])
def get_model(model_id):
    app = current_app
    SERVER_MODE = app.config.get('SERVER_MODE')
    if SERVER_MODE != "lmstudio":
        return jsonify({"error": "Endpoint not available in current mode"}), 404

    get_cached_qwen_models = app.config['get_cached_qwen_models']
    logger = app.config['logger']

    try:
        qwen_models = get_cached_qwen_models()
        target_model = None
        for model in qwen_models:
            if model.get('id') == model_id:
                target_model = model
                break

        if not target_model:
            return jsonify({
                "error": {
                    "message": f"Model {model_id} not found",
                    "type": "invalid_request_error",
                    "code": "model_not_found"
                }
            }), 404

        model_info = target_model.get('info', {})
        meta = model_info.get('meta', {})
        capabilities = meta.get('capabilities', {})

        context_window = meta.get('max_context_length', 131072)

        if 'max_thinking_generation_length' in meta:
            reserved_output_space = meta.get('max_thinking_generation_length')
        elif 'max_summary_generation_length' in meta:
            reserved_output_space = meta.get('max_summary_generation_length')
        elif 'max_generation_length' in meta:
            reserved_output_space = meta.get('max_generation_length')
        else:
            reserved_output_space = 8192

        supports_thinking = capabilities.get('thinking', False) or capabilities.get('thinking_budget', False)

        lm_capabilities = {
            "vision": capabilities.get('vision', False),
            "function_calling": True,
            "json_output": True,
            "streaming": True,
            "document": capabilities.get('document', False),
            "video": capabilities.get('video', False),
            "audio": capabilities.get('audio', False),
            "citations": capabilities.get('citations', False)
        }

        model_config = {
            "id": model_id,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "qwen",
            "permission": [],
            "root": model_id,
            "parent": None,
            "contextWindow": context_window,
            "reservedOutputTokenSpace": reserved_output_space,
            "supportsSystemMessage": "system-role",
            "reasoningCapabilities": {
                "supportsReasoning": supports_thinking,
                "canTurnOffReasoning": supports_thinking,
                "canIOReasoning": supports_thinking,
                "openSourceThinkTags": ["<think>", "</think>"] if supports_thinking else []
            },
            "capabilities": lm_capabilities,
            "pricing": {"prompt": 0.0001, "completion": 0.0002}
        }

        response = jsonify(model_config)
        response.headers['Content-Type'] = 'application/json'
        return response

    except Exception as e:
        logger = app.config['logger']
        logger.error(f"Error getting model info for {model_id}: {e}")
        return jsonify({
            "error": {
                "message": f"Failed to get model information: {str(e)}",
                "type": "server_error"
            }
        }), 500


@lmstudio_bp.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    app = current_app
    app_obj = current_app._get_current_object()
    ui_manager = app.config['ui_manager']
    chat_service = app.config['chat_service']
    queue_manager = app.config['queue_manager']
    RequestState = app.config['RequestState']
    logger = app.config['logger']
    SERVER_MODE = app.config.get('SERVER_MODE')
    get_cached_qwen_models = app.config['get_cached_qwen_models']

    data = request.get_json()
    stream = data.get('stream', False)
    model = data.get('model', 'qwen3-235b-a22b')

    if SERVER_MODE == "ollama" and model.endswith(':latest'):
        model = model[:-7]
        data['model'] = model

    # Xử lý context limiting cho LM Studio endpoint
    try:
        messages = data.get('messages', [])
        if messages:
            cached_models = get_cached_qwen_models()
            trimmed_messages, context_info = context_manager.process_messages_for_context(
                messages, model, cached_models
            )
            
            if context_info.get('trimmed'):
                logger.info(f"Context trimmed for model {model} in LM Studio: {context_info}")
                data['messages'] = trimmed_messages
    except Exception as e:
        logger.warning(f"Error processing context limiting in LM Studio: {e}")

    route_info = f"POST /v1/chat/completions - Chat ({model}, stream: {stream})"
    ui_manager.update_route(route_info, _make_display_data_short(data))

    def stream_qwen_response_with_queue(data):
        request_id = str(uuid.uuid4())
        if not queue_manager.acquire_lock(request_id, data):
            yield f"data: {{\"error\": \"Server busy, request timed out\"}}\n\n"
            return
        try:
            request_state = RequestState(request_id, model)
            # Prepare client-facing fields
            server_mode = SERVER_MODE
            model_out = f"{model}:latest" if server_mode == "ollama" and not str(model).endswith(":latest") else model
            system_fingerprint = "fp_ollama" if server_mode == "ollama" else model
            # Stable short id per request
            import time as _time, json as _json
            created_ts = int(_time.time())
            completion_id = f"chatcmpl-{int(_time.time()*1000)%1000}"
            try:
                status = queue_manager.get_status()
                ui_manager.update_queue_status(True, status.get('queue_size', 0))
            except Exception:
                pass
            with app_obj.app_context():
                sent_done = False
                saw_stop = False
                for chunk in chat_service.stream_qwen_response(data, request_state):
                    try:
                        line = chunk.decode('utf-8') if isinstance(chunk, (bytes, bytearray)) else str(chunk)
                        if not line.startswith('data: '):
                            continue
                        payload = line[6:].strip()
                        if payload == '[DONE]':
                            # If upstream didn't send a final stop chunk, synthesize one
                            if not saw_stop:
                                out = {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": created_ts,
                                    "model": model_out,
                                    "system_fingerprint": system_fingerprint,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {
                                            "role": "assistant",
                                            "content": ""
                                        },
                                        "logprobs": None,
                                        "finish_reason": "stop"
                                    }]
                                }
                                yield 'data: ' + _json.dumps(out) + '\n\n'
                            yield 'data: [DONE]\n\n'
                            sent_done = True
                            break
                        obj = _json.loads(payload)
                        # Extract delta content and finish_reason
                        delta = ((obj.get('choices') or [{}])[0].get('delta')) or {}
                        finish_reason = (obj.get('choices') or [{}])[0].get('finish_reason')
                        if finish_reason == 'stop':
                            saw_stop = True
                        out = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created_ts,
                            "model": model_out,
                            "system_fingerprint": system_fingerprint,
                            "choices": [{
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "content": delta.get('content', '')
                                },
                                "logprobs": None,
                                "finish_reason": finish_reason
                            }]
                        }
                        yield 'data: ' + _json.dumps(out) + '\n\n'
                    except Exception:
                        # Fallback raw
                        yield chunk
                if not sent_done:
                    if not saw_stop:
                        out = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created_ts,
                            "model": model_out,
                            "system_fingerprint": system_fingerprint,
                            "choices": [{
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "content": ""
                                },
                                "logprobs": None,
                                "finish_reason": "stop"
                            }]
                        }
                        yield 'data: ' + _json.dumps(out) + '\n\n'
                    yield 'data: [DONE]\n\n'
        except Exception as e:
            logger.error(f"Error in stream_qwen_response_with_queue: {e}")
            yield f"data: {{\"error\": \"Stream error: {str(e)}\"}}\n\n"
        finally:
            queue_manager.release_lock(request_id)
            try:
                status = queue_manager.get_status()
                ui_manager.update_queue_status(False, status.get('queue_size', 0))
            except Exception:
                pass

    def stream_qwen_response_non_streaming_with_queue(data):
        request_id = str(uuid.uuid4())
        if not queue_manager.acquire_lock(request_id, data):
            return jsonify({"error": {"message": "Server busy, please try again later", "type": "server_error", "code": "server_busy"}}), 503
        try:
            try:
                status = queue_manager.get_status()
                ui_manager.update_queue_status(True, status.get('queue_size', 0))
            except Exception:
                pass
            result = chat_service.stream_qwen_response_non_streaming(data)
            
            # Handle tuple return (data, status) from service
            if isinstance(result, tuple) and len(result) >= 1:
                result = result[0]
            
            # Format response for LMStudio mode
            if SERVER_MODE == "ollama":
                result['model'] = model + ":latest"
                result['system_fingerprint'] = "fp_ollama"
            else:
                # LMStudio mode - use exact format
                result['system_fingerprint'] = model
                result['stats'] = {}
                
            return result
        except Exception as e:
            logger.error(f"Error in stream_qwen_response_non_streaming_with_queue: {e}")
            return jsonify({"error": {"message": f"Stream error: {str(e)}", "type": "server_error"}}), 500
        finally:
            queue_manager.release_lock(request_id)
            try:
                status = queue_manager.get_status()
                ui_manager.update_queue_status(False, status.get('queue_size', 0))
            except Exception:
                pass
                
    if stream:
        return Response(stream_qwen_response_with_queue(data), mimetype='text/plain', headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'Content-Type': 'text/event-stream'})
    else:
        return stream_qwen_response_non_streaming_with_queue(data)


@lmstudio_bp.route('/v1/completions', methods=['POST'])
@parse_json_request()
def v1_completions_shared():
    app = current_app
    app_obj = current_app._get_current_object()
    ui_manager = app.config['ui_manager']
    chat_service = app.config['chat_service']
    server_mode = app.config.get('SERVER_MODE')

    data = request.json_data or {}
    model = data.get('model', 'qwen3-235b-a22b')
    prompt = data.get('prompt', '')
    stream = data.get('stream', False)
    if server_mode == "ollama" and isinstance(model, str) and model.endswith(':latest'):
        model = model[:-7]

    route_info = f"POST /v1/completions - Text Completions ({model}, stream: {stream})"
    ui_manager.update_route(route_info, _make_display_data_short(data))

    openai_data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": stream,
        "temperature": (data.get('options') or {}).get('temperature', 0.7),
        "top_p": (data.get('options') or {}).get('top_p', 1.0),
        "max_tokens": (data.get('options') or {}).get('num_predict', 1000)
    }

    system_fingerprint = "fp_ollama" if server_mode == "ollama" else model
    model_out = f"{model}:latest" if server_mode == "ollama" and not str(model).endswith(":latest") else model

    if stream:
        import json as _json, time as _time
        created_ts = int(_time.time())
        completion_id = f"cmpl-{int(_time.time()*1000) % 1000}"

        def _to_sse():
            with app_obj.app_context():
                for line in chat_service.stream_qwen_response(openai_data):
                    try:
                        obj = _json.loads(line[6:]) if isinstance(line, (str, bytes)) and str(line).startswith('data: ') else _json.loads(line)
                    except Exception:
                        continue
                    text_piece = ''
                    try:
                        delta = (obj.get('choices') or [{}])[0].get('delta') or {}
                        text_piece = delta.get('content') or ''
                    except Exception:
                        text_piece = ''
                    finish_reason = (obj.get('choices') or [{}])[0].get('finish_reason')
                    out = {
                        "id": completion_id,
                        "object": "text_completion",
                        "created": created_ts,
                        "choices": [{"text": text_piece, "index": 0, "finish_reason": finish_reason}],
                        "model": model_out,
                        "system_fingerprint": system_fingerprint
                    }
                    yield "data: " + _json.dumps(out) + "\n\n"
                yield "data: [DONE]\n\n"

        return Response(_to_sse(), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'})

    # Non-streaming
    service_resp = chat_service.stream_qwen_response_non_streaming(openai_data)
    # Normalize tuple (data, status) to dict
    if isinstance(service_resp, tuple) and len(service_resp) >= 1:
        service_resp = service_resp[0]
    created_at = int(__import__('time').time())
    # service_resp is OpenAI-style chat completion; extract full content
    try:
        content = ((service_resp.get('choices') or [{}])[0].get('message') or {}).get('content', '')
        usage_obj = service_resp.get('usage') or {}
    except Exception:
        content, usage_obj = '', {}
    usage = {
        "prompt_tokens": int(usage_obj.get('prompt_tokens', 0)),
        "completion_tokens": int(usage_obj.get('completion_tokens', 0)),
        "total_tokens": int(usage_obj.get('total_tokens', 0))
    }
    non_stream_out = {
        "id": f"cmpl-{int(__import__('time').time()*1000) % 1000}",
        "object": "text_completion",
        "created": created_at,
        "model": model_out,
        "system_fingerprint": system_fingerprint,
        "choices": [{"text": content, "index": 0, "finish_reason": "stop"}],
        "usage": usage
    }
    
    # Add stats field for LMStudio mode
    if server_mode != "ollama":
        non_stream_out['stats'] = {}
    
    return jsonify(non_stream_out)


@lmstudio_bp.route('/v1/embeddings', methods=['POST'])
@parse_json_request()
def v1_embeddings():
    app = current_app
    server_mode = app.config.get('SERVER_MODE')

    data = request.json_data or {}
    model = data.get('model', '')
    inp = data.get('input', [])
    options = data.get('options') or {}
    truncate = options.get('truncate')

    # Normalize input shape
    if isinstance(inp, str):
        inp = [inp]

    # Internal model normalization: strip :latest only in ollama mode for internal use
    effective_model = model
    if server_mode == "ollama" and isinstance(effective_model, str) and effective_model.endswith(':latest'):
        effective_model = effective_model[:-7]

    # Deterministic pseudo-embeddings similar to ollama /api/embed
    import time as _t, hashlib, random
    start_ns = _t.perf_counter_ns()
    dim = 768

    def _embed_text(text: str):
        seed_bytes = hashlib.sha256(text.encode('utf-8', 'ignore')).digest()
        seed_int = int.from_bytes(seed_bytes[:8], 'big', signed=False)
        rnd = random.Random(seed_int)
        return [rnd.uniform(-0.05, 0.05) for _ in range(dim)]

    # Apply optional truncate hint (no-op for now; placeholder for parity)
    texts = inp
    if truncate is True:
        # Simple safe cap to emulate truncation behavior (does not affect determinism much)
        texts = [s if not isinstance(s, str) else s[:8192] for s in texts]

    embeddings = [_embed_text(s if isinstance(s, str) else str(s)) for s in texts]

    # Usage estimates (prompt tokens ~= whitespace-separated tokens)
    try:
        prompt_tokens = sum(len(str(x).split()) for x in texts)
    except Exception:
        prompt_tokens = 0

    total_duration = _t.perf_counter_ns() - start_ns
    _ = total_duration  # kept for parity; not exposed in OpenAI embedding response

    # Response model name per mode convention
    if server_mode == "ollama":
        model_out = model if (isinstance(model, str) and model.endswith(':latest')) else (f"{effective_model}:latest" if effective_model else "")
    else:
        # LMStudio mode: no :latest suffix
        model_out = effective_model

    return jsonify({
        "object": "list",
        "data": [
            {"object": "embedding", "embedding": emb, "index": idx}
            for idx, emb in enumerate(embeddings)
        ],
        "model": model_out,
        "usage": {"prompt_tokens": int(prompt_tokens), "total_tokens": int(prompt_tokens)}
    })


