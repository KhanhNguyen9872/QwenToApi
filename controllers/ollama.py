from flask import Blueprint, jsonify, Response, request, current_app
from utils.request_utils import parse_json_request


ollama_bp = Blueprint('ollama', __name__)


def parse_tools_to_text(tools):
    tools_text = ""
    for i, tool in enumerate(tools):
        if tool.get('type') == 'function':
            func = tool.get('function', {})
            name = func.get('name', '')
            description = func.get('description', '')
            parameters = func.get('parameters', {})

            tools_text += f"Function {i+1}: {name}\n"
            if description:
                tools_text += f"Description: {description}\n"

            if parameters:
                param_type = parameters.get('type', 'object')
                tools_text += f"Parameters (type: {param_type}):\n"

                props = parameters.get('properties', {})
                required = parameters.get('required', [])

                for prop_name, prop_info in props.items():
                    prop_type = prop_info.get('type', 'string')
                    prop_desc = prop_info.get('description', '')
                    is_required = prop_name in required

                    tools_text += f"  - {prop_name} ({prop_type})"
                    if is_required:
                        tools_text += " [required]"
                    if prop_desc:
                        tools_text += f": {prop_desc}"
                    tools_text += "\n"

                    if 'enum' in prop_info:
                        enum_values = prop_info['enum']
                        tools_text += f"    Values: {', '.join(enum_values)}\n"

            tools_text += "\n"

    return tools_text


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


@ollama_bp.route('/v1/models', methods=['GET', 'OPTIONS'])
def v1_list_models_shared():
    app = current_app
    get_cached_qwen_models = app.config['get_cached_qwen_models']
    SERVER_MODE = app.config.get('SERVER_MODE')

    if request.method == 'OPTIONS':
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    route_info = "GET /v1/models - List Models (shared)"

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
                    "created": int(__import__('time').time()),
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

@ollama_bp.route('/api/tags', methods=['GET'])
def ollama_list_models():
    app = current_app
    SERVER_MODE = app.config.get('SERVER_MODE')
    if SERVER_MODE != "ollama":
        return jsonify({"error": "Endpoint not available in current mode"}), 404

    get_cached_qwen_models = app.config['get_cached_qwen_models']
    logger = app.config['logger']

    try:
        qwen_models = get_cached_qwen_models()
        ollama_models = []
        from datetime import datetime
        for model in qwen_models:
            model_id = model.get('id', '')
            if model_id:
                modified_at = datetime.now().isoformat() + "+07:00"
                model_name_with_latest = f"{model_id}:latest"
                ollama_models.append({
                    "name": model_name_with_latest,
                    "model": model_name_with_latest,
                    "modified_at": modified_at,
                    "size": 4661224676,
                    "digest": "365c0bd3c000a25d28ddbf732fe1c6add414de7275464c4e4d1c3b5fcb5d8ad1",
                    "details": {
                        "parent_model": "",
                        "format": "gguf",
                        "family": "qwen",
                        "families": ["qwen"],
                        "parameter_size": "235B",
                        "quantization_level": "Q4_0"
                    }
                })

        return jsonify({"models": ollama_models})

    except Exception as e:
        logger.error(f"Error listing Ollama models: {e}")
        return jsonify({"error": str(e)}), 500


@ollama_bp.route('/api/version', methods=['GET'])
def ollama_version():
    app = current_app
    SERVER_MODE = app.config.get('SERVER_MODE')
    if SERVER_MODE != "ollama":
        return jsonify({"error": "Endpoint not available in current mode"}), 404

    return jsonify({"version":"0.11.7"})


@ollama_bp.route('/api/ps', methods=['GET'])
def ollama_list_running_models():
    app = current_app
    SERVER_MODE = app.config.get('SERVER_MODE')
    if SERVER_MODE != "ollama":
        return jsonify({"error": "Endpoint not available in current mode"}), 404

    get_cached_qwen_models = app.config['get_cached_qwen_models']
    logger = app.config['logger']

    try:
        qwen_models = get_cached_qwen_models()
        from datetime import datetime, timedelta
        running_models = []
        for model in qwen_models:
            model_id = model.get('id', '')
            if model_id:
                expires_at = (datetime.now() + timedelta(minutes=30)).isoformat() + "+07:00"
                model_name_with_latest = f"{model_id}:latest"
                running_models.append({
                    "name": model_name_with_latest,
                    "model": model_name_with_latest,
                    "size": 6654289920,
                    "digest": "365c0bd3c000a25d28ddbf732fe1c6add414de7275464c4e4d1c3b5fcb5d8ad1",
                    "details": {
                        "parent_model": "",
                        "format": "gguf",
                        "family": "qwen",
                        "families": ["qwen"],
                        "parameter_size": "235B",
                        "quantization_level": "Q4_0"
                    },
                    "expires_at": expires_at,
                    "size_vram": 6654289920
                })
        return jsonify({"models": running_models})
    except Exception as e:
        logger.error(f"Error listing running Ollama models: {e}")
        return jsonify({"error": str(e)}), 500


@ollama_bp.route('/api/show', methods=['POST'])
@parse_json_request()
def ollama_show_model():
    app = current_app
    SERVER_MODE = app.config.get('SERVER_MODE')
    if SERVER_MODE != "ollama":
        return jsonify({"error": "Endpoint not available in current mode"}), 404

    get_cached_qwen_models = app.config['get_cached_qwen_models']
    logger = app.config['logger']

    data = request.json_data
    model_name = data.get('name', '') or data.get('model', '')
    if model_name.endswith(':latest'):
        model_name = model_name[:-7]

    try:
        qwen_models = get_cached_qwen_models()
        target_model = None
        for model in qwen_models:
            if model.get('id') == model_name:
                target_model = model
                break
        if not target_model:
            return jsonify({"error": f"Model {model_name} not found"}), 404

        model_info = target_model.get('info', {})
        meta = model_info.get('meta', {})
        
        # Demo license - short version for testing
        demo_license = "DEMO LICENSE AGREEMENT\n\nThis is a demo model for testing purposes.\n\nBy using this model, you agree to use it responsibly and in accordance with applicable laws.\n\nThis model is provided 'as is' without any warranties."
        
        # Generate modelfile content
        modelfile_content = f"""# Modelfile generated by "ollama show"
# To build a new Modelfile based on this, replace FROM with:
# FROM {model_name}:latest

FROM {model_name}
TEMPLATE "{{ if .System }}<|start_header_id|>system<|end_header_id|>

{{ .System }}<|eot_id|>{{ end }}{{ if .Prompt }}<|start_header_id|>user<|end_header_id|>

{{ .Prompt }}<|eot_id|>{{ end }}<|start_header_id|>assistant<|end_header_id|>

{{ .Response }}<|eot_id|>"
PARAMETER num_keep 24
PARAMETER stop "<|start_header_id|>"
PARAMETER stop "<|end_header_id|>"
PARAMETER stop "<|eot_id|>"
LICENSE "{demo_license}\""""

        ollama_model_info = {
            "license": demo_license,
            "modelfile": modelfile_content,
            "parameters": f"num_keep                       24\nstop                           \"<|start_header_id|>\"\nstop                           \"<|end_header_id|>\"\nstop                           \"<|eot_id|>\"",
            "template": "{{ if .System }}<|start_header_id|>system<|end_header_id|>\n\n{{ .System }}<|eot_id|>{{ end }}{{ if .Prompt }}<|start_header_id|>user<|end_header_id|>\n\n{{ .Prompt }}<|eot_id|>{{ end }}<|start_header_id|>assistant<|end_header_id|>\n\n{{ .Response }}<|eot_id|>",
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": "qwen",
                "families": ["qwen"],
                "parameter_size": str(meta.get('max_context_length', 131072)),
                "quantization_level": "Q4_0"
            },
            "model_info": {
                "general.architecture": "qwen",
                "general.file_type": 2,
                "general.parameter_count": meta.get('max_context_length', 131072) * 1000,
                "general.quantization_version": 2,
                "qwen.attention.head_count": 32,
                "qwen.attention.head_count_kv": 8,
                "qwen.attention.layer_norm_rms_epsilon": 0.00001,
                "qwen.block_count": 32,
                "qwen.context_length": meta.get('max_context_length', 131072),
                "qwen.embedding_length": 4096,
                "qwen.feed_forward_length": 14336,
                "qwen.rope.dimension_count": 128,
                "qwen.rope.freq_base": 500000,
                "qwen.vocab_size": 128256,
                "tokenizer.ggml.bos_token_id": 128000,
                "tokenizer.ggml.eos_token_id": 128009,
                "tokenizer.ggml.merges": None,
                "tokenizer.ggml.model": "gpt2",
                "tokenizer.ggml.pre": "qwen-bpe",
                "tokenizer.ggml.token_type": None,
                "tokenizer.ggml.tokens": None
            },
            "tensors": [
                {"name": "token_embd.weight", "type": "Q4_0", "shape": [4096, 128256]},
                {"name": "blk.0.attn_norm.weight", "type": "F32", "shape": [4096]},
                {"name": "blk.0.ffn_down.weight", "type": "Q4_0", "shape": [14336, 4096]},
                {"name": "blk.0.ffn_gate.weight", "type": "Q4_0", "shape": [4096, 14336]},
                {"name": "blk.0.ffn_up.weight", "type": "Q4_0", "shape": [4096, 14336]},
                {"name": "blk.0.ffn_norm.weight", "type": "F32", "shape": [4096]},
                {"name": "blk.0.attn_k.weight", "type": "Q4_0", "shape": [4096, 1024]},
                {"name": "blk.0.attn_output.weight", "type": "Q4_0", "shape": [4096, 4096]},
                {"name": "blk.0.attn_q.weight", "type": "Q4_0", "shape": [4096, 4096]},
                {"name": "blk.0.attn_v.weight", "type": "Q4_0", "shape": [4096, 1024]},
                {"name": "output.weight", "type": "Q6_K", "shape": [4096, 128256]},
                {"name": "output_norm.weight", "type": "F32", "shape": [4096]}
            ],
            "capabilities": ["completion"],
            "modified_at": "2025-01-27T12:00:00.0000000+07:00"
        }
        return jsonify(ollama_model_info)
    except Exception as e:
        logger.error(f"Error showing Ollama model {model_name}: {e}")
        return jsonify({"error": str(e)}), 500


@ollama_bp.route('/api/generate', methods=['POST'])
@parse_json_request()
def ollama_generate():
    app = current_app
    SERVER_MODE = app.config.get('SERVER_MODE')
    if SERVER_MODE != "ollama":
        return jsonify({"error": "Endpoint not available in current mode"}), 404

    ui_manager = app.config['ui_manager']
    ollama_service = app.config['ollama_service']

    data = request.json_data
    model = data.get('model', 'qwen3-235b-a22b')
    prompt = data.get('prompt', '')
    template = data.get('template', '')
    stream = data.get('stream', True)
    suffix = data.get('suffix')
    images = data.get('images')
    format_opt = data.get('format')
    options = data.get('options')
    system = data.get('system')
    context = data.get('context')
    images = data.get('images', [])
    raw = data.get('raw')
    keep_alive = data.get('keep_alive')
    if model.endswith(':latest'):
        model = model[:-7]

    route_info = f"POST /api/generate - Ollama Generate ({model}, stream: {stream})"
    ui_manager.update_route(route_info, _make_display_data_short(data))

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if prompt:
        messages.append({"role": "prompt", "content": prompt})
    if template:
        messages.append({"role": "template", "content": template})

    openai_data = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "incremental_output": True,
        "temperature": data.get('temperature', 0.7),
        "top_p": data.get('top_p', 1.0),
        "max_tokens": data.get('num_predict', 1000)
    }

    # Attach advanced options if present
    if options is not None:
        openai_data["options"] = options
    if template is not None:
        openai_data["template"] = template
    if context is not None:
        openai_data["context"] = context
    if raw is not None:
        openai_data["raw"] = raw
    if keep_alive is not None:
        openai_data["keep_alive"] = keep_alive
    if suffix is not None:
        openai_data["suffix"] = suffix
    if images is not None:
        openai_data["images"] = images
    if format_opt == 'json':
        openai_data["response_format"] = {"type": "json_object"}

    if stream:
        import json as _json
        def _transform_stream():
            for line in ollama_service.stream_ollama_response(openai_data):
                try:
                    obj = _json.loads(line)
                except Exception:
                    yield line
                    continue
                # If already in expected format with 'response', pass through and normalize model
                if 'response' in obj:
                    obj['model'] = data.get('model', model)
                    yield _json.dumps(obj) + "\n"
                    continue
                # If error from service, forward as-is
                if 'error' in obj:
                    yield _json.dumps(obj) + "\n"
                    continue
                transformed = {
                    "model": data.get('model', model)
                }
                if 'created_at' in obj:
                    transformed["created_at"] = obj["created_at"]
                # Map message.content -> response if present
                msg = obj.get('message') or {}
                if isinstance(msg, dict) and 'content' in msg:
                    transformed['response'] = msg.get('content')
                # done flags and reasons
                if 'done' in obj:
                    transformed['done'] = obj['done']
                if 'done_reason' in obj:
                    transformed['done_reason'] = obj['done_reason']
                # include context if present; otherwise empty list for compatibility
                if 'context' in obj:
                    transformed['context'] = obj['context']
                else:
                    transformed['context'] = []
                # timings / counters if available
                for k in ("total_duration","load_duration","prompt_eval_count","prompt_eval_duration","eval_count","eval_duration"):
                    if k in obj:
                        transformed[k] = obj[k]
                yield _json.dumps(transformed) + "\n"
        return Response(_transform_stream(), mimetype='application/json', headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'})
    else:
        # Non-streaming: adapt service response shape to Ollama /generate
        service_resp = ollama_service.stream_ollama_response_non_streaming(openai_data)
        try:
            created_at = service_resp.get('created_at')
            message = service_resp.get('message') or {}
            content = message.get('content', '')
            out = {
                "model": data.get('model', model),
                "created_at": created_at,
                "response": content,
                "done": True,
                "done_reason": service_resp.get('done_reason', 'stop'),
                "context": service_resp.get('context', [])
            }
            for k in ("total_duration","load_duration","prompt_eval_count","prompt_eval_duration","eval_count","eval_duration"):
                if k in service_resp:
                    out[k] = service_resp[k]
            return jsonify(out)
        except Exception:
            return jsonify(service_resp)


@ollama_bp.route('/api/chat', methods=['POST'])
@parse_json_request()
def ollama_chat():
    app = current_app
    SERVER_MODE = app.config.get('SERVER_MODE')
    if SERVER_MODE != "ollama":
        return jsonify({"error": "Endpoint not available in current mode"}), 404

    ui_manager = app.config['ui_manager']
    ollama_service = app.config['ollama_service']

    data = request.json_data
    model = data.get('model', 'qwen3-235b-a22b')
    messages = data.get('messages', [])
    stream = data.get('stream', True)
    tools = data.get('tools', [])
    if model.endswith(':latest'):
        model = model[:-7]

    route_info = f"POST /api/chat - Ollama Chat ({model}, stream: {stream})"
    ui_manager.update_route(route_info, _make_display_data_short(data))

    if tools:
        tools_text = parse_tools_to_text(tools)
        if messages:
            last_message = messages[-1]
            if last_message.get('role') == 'user':
                last_message['content'] = f"{last_message['content']}\n\nAvailable tools:\n{tools_text}"

    openai_data = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "temperature": data.get('temperature', 0.7),
        "top_p": data.get('top_p', 1.0),
        "max_tokens": data.get('num_predict', 1000)
    }

    if stream:
        return Response(
            ollama_service.stream_ollama_response(openai_data),
            mimetype='application/json',
            headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'}
        )
    else:
        return ollama_service.stream_ollama_response_non_streaming(openai_data)


@ollama_bp.route('/api/delete', methods=['DELETE'])
@parse_json_request()
def ollama_delete_model():
    app = current_app
    SERVER_MODE = app.config.get('SERVER_MODE')
    if SERVER_MODE != "ollama":
        return jsonify({"error": "Endpoint not available in current mode"}), 404

    data = request.json_data or {}
    model = data.get('model', '')

    return jsonify({"error": f"model '{model}' not found"}), 404


@ollama_bp.route('/api/pull', methods=['POST'])
@parse_json_request()
def ollama_pull_model():
    app = current_app
    SERVER_MODE = app.config.get('SERVER_MODE')
    if SERVER_MODE != "ollama":
        return jsonify({"error": "Endpoint not available in current mode"}), 404

    return jsonify({"status": "pulling manifest"})


@ollama_bp.route('/api/push', methods=['POST'])
@parse_json_request()
def ollama_push_model():
    app = current_app
    SERVER_MODE = app.config.get('SERVER_MODE')
    if SERVER_MODE != "ollama":
        return jsonify({"error": "Endpoint not available in current mode"}), 404

    return jsonify({"status": "success"})


@ollama_bp.route('/api/create', methods=['POST'])
@parse_json_request()
def ollama_create_model():
    app = current_app
    SERVER_MODE = app.config.get('SERVER_MODE')
    if SERVER_MODE != "ollama":
        return jsonify({"error": "Endpoint not available in current mode"}), 404

    data = request.json_data or {}
    quantize = data.get('quantize')

    import json as _json

    def _stream_create():
        if quantize:
            yield _json.dumps({"status": f"quantizing F16 model to {quantize}"}) + "\n"
        # Simulate steps
        yield _json.dumps({"status": "creating new layer sha256:667b0c1932bc6ffc593ed1d03f895bf2dc8dc6df21db3042284a6f4416b06a29"}) + "\n"
        yield _json.dumps({"status": "using existing layer sha256:11ce4ee3e170f6adebac9a991c22e22ab3f8530e154ee669954c4bc73061c258"}) + "\n"
        yield _json.dumps({"status": "using existing layer sha256:0ba8f0e314b4264dfd19df045cde9d4c394a52474bf92ed6a3de22a4ca31a177"}) + "\n"
        yield _json.dumps({"status": "using existing layer sha256:56bb8bd477a519ffa694fc449c2413c6f0e1d3b1c88fa7e3c9d88d3ae49d4dcb"}) + "\n"
        yield _json.dumps({"status": "creating new layer sha256:455f34728c9b5dd3376378bfb809ee166c145b0b4c1f1a6feca069055066ef9a"}) + "\n"
        yield _json.dumps({"status": "writing manifest"}) + "\n"
        yield _json.dumps({"status": "success"}) + "\n"

    return Response(
        _stream_create(),
        mimetype='application/json',
        headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'}
    )


@ollama_bp.route('/api/embed', methods=['POST'])
@parse_json_request()
def ollama_embed():
    app = current_app
    SERVER_MODE = app.config.get('SERVER_MODE')
    if SERVER_MODE != "ollama":
        return jsonify({"error": "Endpoint not available in current mode"}), 404

    data = request.json_data or {}
    model = data.get('model', '')
    inp = data.get('input', [])
    if isinstance(inp, str):
        inp = [inp]

    # Generate deterministic pseudo-embeddings per input (non-zero, stable)
    import time as _t, hashlib, random
    start_ns = _t.perf_counter_ns()
    dim = 768

    def _embed_text(text: str):
        seed_bytes = hashlib.sha256(text.encode('utf-8', 'ignore')).digest()
        seed_int = int.from_bytes(seed_bytes[:8], 'big', signed=False)
        rnd = random.Random(seed_int)
        # Small range similar to typical normalized embeddings
        return [rnd.uniform(-0.05, 0.05) for _ in range(dim)]

    embeddings = [_embed_text(s if isinstance(s, str) else str(s)) for s in inp]
    total_duration = _t.perf_counter_ns() - start_ns
    load_duration = int(total_duration * 0.15)
    prompt_eval_count = sum(len(str(x).split()) for x in inp)

    # Normalize model name by removing :latest suffix
    if isinstance(model, str) and model.endswith(':latest'):
        model_out = model[:-7]
    else:
        model_out = model

    return jsonify({
        "model": model_out,
        "embeddings": embeddings,
        "total_duration": int(total_duration),
        "load_duration": int(load_duration),
        "prompt_eval_count": int(prompt_eval_count)
    })

