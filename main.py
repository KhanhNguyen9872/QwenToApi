from flask import Flask, request, Response, jsonify, g
from flask_cors import CORS
import uuid
import time
import socket
import logging
import json
import os
import argparse
import sys
import copy

# Import các module đã tách
from utils.logging_config import setup_logging
from utils.queue_manager import queue_manager
from utils.ui_manager import ui_manager
from utils.chat_manager import chat_manager
from services.qwen_service import qwen_service
from services.chat_service import chat_service
from services.ollama_service import ollama_service
from models.request_state import RequestState
from werkzeug.serving import make_server
import threading
from controllers.lmstudio import lmstudio_bp
from controllers.ollama import ollama_bp

# Parse command line arguments
def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Custom Server with Qwen API Integration')
    parser.add_argument('--background', action='store_true',
                       help='Run server in background mode (no terminal output)')
    parser.add_argument('--mode', choices=['lmstudio', 'ollama'],
                       help='Server mode (lmstudio or ollama)')
    parser.add_argument('--port', type=int,
                       help='Server port (default: 1235 for lmstudio, 11434 for ollama)')
    parser.add_argument('--host', default='0.0.0.0',
                       help='Server host (default: 0.0.0.0)')
    parser.add_argument('--start', action='store_true',
                       help='Auto-start the server')
    return parser.parse_args()

# Cấu hình Flask để trả về JSON đẹp
app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Cấu hình CORS để cho phép tất cả origin
CORS(app, origins="*", supports_credentials=True)

# Cấu hình để chấp nhận header request rất dài
app.config['MAX_CONTENT_LENGTH'] = 2048 * 1024 * 1024  # 2GB
app.config['MAX_CONTENT_PATH'] = None
app.config['MAX_COOKIE_SIZE'] = 2048 * 1024 * 1024  # 2GB

# Tăng giới hạn cho request body
app.config['MAX_CONTENT_LENGTH'] = None  # Không giới hạn

# Cấu hình thêm để xử lý request lớn
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Cấu hình để chấp nhận request không có Content-Type
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = 'application/json'

# Tắt kiểm tra Content-Type cho JSON
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
app.config['JSON_SORT_KEYS'] = False

# Expose shared services/state to controllers via app.config
app.config.update({
    'ui_manager': ui_manager,
    'qwen_service': qwen_service,
    'chat_service': chat_service,
    'ollama_service': ollama_service,
    'queue_manager': queue_manager,
    'RequestState': RequestState,
    'SERVER_MODE': None,
})

# Register blueprints
app.register_blueprint(lmstudio_bp)
app.register_blueprint(ollama_bp)

# Tăng giới hạn JSON serialization
import sys
sys.setrecursionlimit(10000)  # Tăng recursion limit

# Global variables
SERVER_MODE = None
BACKGROUND_MODE = False
args = None
HTTP_SERVER = None
HTTP_THREAD = None

# Global models cache
MODELS_CACHE = None
MODELS_CACHE_TIME = None
MODELS_CACHE_LOCK = threading.Lock()

def get_cached_qwen_models(force_refresh: bool = False):
    """Lấy danh sách models từ cache toàn cục; chỉ gọi Qwen 1 lần trừ khi refresh."""
    global MODELS_CACHE, MODELS_CACHE_TIME
    try:
        with MODELS_CACHE_LOCK:
            if MODELS_CACHE is None or force_refresh:
                models = qwen_service.get_models_from_qwen()
                MODELS_CACHE = models or []
                MODELS_CACHE_TIME = int(time.time())
            return MODELS_CACHE
    except Exception as e:
        logger.error(f"Error getting cached models: {e}")
        return MODELS_CACHE or []

# Make cached models accessor available to controllers
app.config['get_cached_qwen_models'] = get_cached_qwen_models

def load_ui_settings():
    """Đọc cấu hình từ ui_settings.json"""
    try:
        import json
        with open('ui_settings.json', 'r', encoding='utf-8') as f:
            settings = json.load(f)
        return settings
    except Exception as e:
        logger.warning(f"Không thể đọc ui_settings.json: {e}")
        # Trả về giá trị mặc định
        return {
            "ip_address": "127.0.0.1",
            "port": 11434,
            "mode": "ollama"
        }

def get_max_context_length(host: str = None, port: int = None):
    """Lấy max context length từ tất cả models và set environment variables"""
    try:
        # Đọc config từ ui_settings.json
        settings = load_ui_settings()
        
        # Sử dụng host/port từ tham số hoặc từ config
        if host is None:
            host = settings.get("ip_address", "127.0.0.1")
        if port is None:
            port = settings.get("port", 11434)
        
        models = get_cached_qwen_models()
        if not models:
            logger.warning("Không có models nào để lấy context length")
            return None
        
        context_lengths = []
        for model in models:
            try:
                info = model.get('info', {})
                meta = info.get('meta', {})
                max_context = meta.get('max_context_length')
                if max_context and isinstance(max_context, (int, float)):
                    context_lengths.append(int(max_context))
                    logger.info(f"Model {model.get('id', 'unknown')}: context_length = {max_context}")
            except Exception as e:
                logger.warning(f"Lỗi khi lấy context length từ model {model.get('id', 'unknown')}: {e}")
        
        if context_lengths:
            max_context = max(context_lengths)
            logger.info(f"Max context length từ tất cả models: {max_context}")
            
            # Tạo host string
            host_string = f"http://{host}:{port}"
            
            # Set environment variables cho process hiện tại
            os.environ['OLLAMA_CONTEXT_LENGTH'] = str(max_context)
            os.environ['OLLAMA_HOST'] = host_string
            os.environ['OLLAMA_ORIGINS'] = host_string
            
            # Set environment variables cho system (Windows/Linux)
            try:
                if os.name == 'nt':  # Windows
                    import subprocess
                    # Set user environment variables
                    subprocess.run([
                        'setx', 'OLLAMA_CONTEXT_LENGTH', str(max_context)
                    ], check=True, capture_output=True)
                    subprocess.run([
                        'setx', 'OLLAMA_HOST', host_string
                    ], check=True, capture_output=True)
                    subprocess.run([
                        'setx', 'OLLAMA_ORIGINS', host_string
                    ], check=True, capture_output=True)
                    logger.info(f"Đã set OLLAMA environment variables vào Windows user environment:")
                    logger.info(f"  OLLAMA_CONTEXT_LENGTH = {max_context}")
                    logger.info(f"  OLLAMA_HOST = {host_string}")
                    logger.info(f"  OLLAMA_ORIGINS = {host_string}")
                else:  # Linux/Unix
                    import subprocess
                    # Set user environment variables trong ~/.bashrc hoặc ~/.profile
                    home_dir = os.path.expanduser('~')
                    bashrc_path = os.path.join(home_dir, '.bashrc')
                    profile_path = os.path.join(home_dir, '.profile')
                    
                    env_lines = [
                        f'export OLLAMA_CONTEXT_LENGTH={max_context}\n',
                        f'export OLLAMA_HOST={host_string}\n',
                        f'export OLLAMA_ORIGINS={host_string}\n'
                    ]
                    
                    # Thêm vào .bashrc nếu tồn tại
                    if os.path.exists(bashrc_path):
                        with open(bashrc_path, 'a') as f:
                            for line in env_lines:
                                f.write(line)
                        logger.info(f"Đã thêm OLLAMA environment variables vào ~/.bashrc")
                    
                    # Thêm vào .profile nếu tồn tại
                    if os.path.exists(profile_path):
                        with open(profile_path, 'a') as f:
                            for line in env_lines:
                                f.write(line)
                        logger.info(f"Đã thêm OLLAMA environment variables vào ~/.profile")
                    
                    # Set cho session hiện tại
                    os.environ['OLLAMA_CONTEXT_LENGTH'] = str(max_context)
                    os.environ['OLLAMA_HOST'] = host_string
                    os.environ['OLLAMA_ORIGINS'] = host_string
                    logger.info(f"Đã set OLLAMA environment variables cho session hiện tại:")
                    logger.info(f"  OLLAMA_CONTEXT_LENGTH = {max_context}")
                    logger.info(f"  OLLAMA_HOST = {host_string}")
                    logger.info(f"  OLLAMA_ORIGINS = {host_string}")
                    
            except Exception as e:
                logger.warning(f"Không thể set system environment variables: {e}")
                logger.info(f"Đã set OLLAMA environment variables cho process hiện tại:")
                logger.info(f"  OLLAMA_CONTEXT_LENGTH = {max_context}")
                logger.info(f"  OLLAMA_HOST = {host_string}")
                logger.info(f"  OLLAMA_ORIGINS = {host_string}")
            
            return max_context
        else:
            logger.warning("Không tìm thấy context length nào từ models")
            return None
            
    except Exception as e:
        logger.error(f"Lỗi khi lấy max context length: {e}")
        return None

# Parse arguments first
args = parse_arguments()

# Setup logging based on background mode
def setup_logging_with_background():
    """Setup logging based on background mode"""
    global BACKGROUND_MODE
    if args.background:
        BACKGROUND_MODE = True
        # Redirect all output to null in background mode
        import os
        import sys
        
        # Redirect stdout and stderr to null
        if os.name == 'nt':  # Windows
            null_device = 'NUL'
        else:  # Unix/Linux/Mac
            null_device = '/dev/null'
        
        # Open null device
        null_fd = os.open(null_device, os.O_RDWR)
        
        # Redirect stdout and stderr
        os.dup2(null_fd, sys.stdout.fileno())
        os.dup2(null_fd, sys.stderr.fileno())
        
        # Close the null device
        os.close(null_fd)
        
        # Setup minimal logging for background mode
        logging.basicConfig(
            level=logging.ERROR,  # Only log errors
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.devnull, mode='w'),  # Log to null
                logging.NullHandler()  # No console output
            ]
        )
        return logging.getLogger(__name__)
    else:
        # Normal logging setup
        return setup_logging()

logger = setup_logging_with_background()
app.config['logger'] = logger

def _ui_log(message: str, level: str = "info"):
    """Log ra logger và cố gắng đẩy vào GUI Logs tab nếu khả dụng."""
    try:
        # Ghi ra file/console theo level
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)

        # Đẩy vào UI nếu có
        try:
            ui = getattr(ui_manager, 'current_ui', None)
            if ui and hasattr(ui, 'log'):
                ui.log(message, level=level)
        except Exception:
            pass
    except Exception:
        pass

# Embedded server control for GUI
def start_embedded(host: str, port: int):
    """Start Flask app using Werkzeug make_server in background thread."""
    global HTTP_SERVER, HTTP_THREAD
    try:
        if HTTP_SERVER is not None:
            return True
        
        # Lấy max context length và set environment variables trước khi start server
        max_context = get_max_context_length(host, port)
        if max_context:
            _ui_log(f"✅ Đã set OLLAMA environment variables:")
            _ui_log(f"  OLLAMA_CONTEXT_LENGTH = {max_context}")
            _ui_log(f"  OLLAMA_HOST = {host}:{port}")
            _ui_log(f"  OLLAMA_ORIGINS = {host}:{port}")
        else:
            _ui_log("⚠️ Không thể lấy max context length từ models", level="warning")
        
        HTTP_SERVER = make_server(host, port, app)
        import threading
        HTTP_THREAD = threading.Thread(target=HTTP_SERVER.serve_forever, daemon=True)
        HTTP_THREAD.start()
        _ui_log(f"🟢 Flask started (embedded) on {host}:{port}")
        return True
    except Exception as e:
        HTTP_SERVER = None
        HTTP_THREAD = None
        _ui_log(f"Failed to start embedded server: {e}", level="error")
        return False

def stop_embedded(timeout: float = 2.0):
    """Stop embedded Werkzeug server without exiting the process."""
    global HTTP_SERVER, HTTP_THREAD
    try:
        srv, th = HTTP_SERVER, HTTP_THREAD
        HTTP_SERVER = None
        HTTP_THREAD = None
        if srv is not None:
            try:
                srv.shutdown()
            except Exception:
                pass
        if th is not None and th.is_alive():
            try:
                th.join(timeout)
            except Exception:
                pass
        _ui_log("🔴 Flask stopped (embedded)")
        return True
    except Exception as e:
        _ui_log(f"Failed to stop embedded server: {e}", level="error")
        return False

# Override để bỏ qua kiểm tra Content-Type
@app.before_request
def before_request():
    """Override để xử lý request không có Content-Type"""
    # Log request cơ bản và đánh dấu thời điểm bắt đầu
    try:
        g._req_start_time = time.time()
        # --- Xử lý query params ---
        params_keys = ''
        try:
            args_dict = request.args.to_dict(flat=True)  # convert ImmutableMultiDict -> dict
            params_keys = '{' + ', '.join(args_dict.keys()) + '}' if args_dict else '{}'
        except Exception:
            params_keys = '{}'
        
        try:
            raw_body = request.get_data(as_text=True)
            body_keys = ""
            try:
                # Chỉ lấy key nếu là JSON
                data = json.loads(raw_body)
                if isinstance(data, dict):
                    body_keys = '{' + ', '.join(data.keys()) + '}'
                elif isinstance(data, list):
                    # Nếu gửi list of dict, lấy key của object đầu tiên
                    body_keys = '{' + ', '.join(data[0].keys()) + '}' if data else ''
                else:
                    body_keys = ''
            except Exception:
                body_keys = ''
        except Exception:
            body_keys = ""
        
        _ui_log(f"➡️ {request.method} {request.path} | ip={request.remote_addr} | params={params_keys} | body={body_keys}", level="info")
    except Exception:
        pass

    # Sync SERVER_MODE from GUI/terminal UI state (ui_settings.json driven)
    try:
        ui = getattr(ui_manager, 'current_ui', None)
        if ui is not None and hasattr(ui, 'mode'):
            mode_value = getattr(ui, 'mode', None)
            if mode_value in ("ollama", "lmstudio"):
                app.config['SERVER_MODE'] = mode_value
    except Exception:
        pass

    if request.method == 'POST' and request.path.startswith('/api/'):
        # Nếu là POST request đến Ollama API và không có Content-Type
        if not request.content_type or 'application/json' not in request.content_type:
            # Set Content-Type để Flask không báo lỗi
            request.environ['CONTENT_TYPE'] = 'application/json'

@app.after_request
def after_request(response):
    """Log status và thời gian xử lý cho mọi request"""
    try:
        start = getattr(g, '_req_start_time', None)
        elapsed_ms = int((time.time() - start) * 1000) if start else -1
    except Exception:
        pass
    return response

@app.route('/', methods=['GET'])
def root():
    """Root endpoint"""
    route_info = "GET / - Root"
    ui_manager.update_route(route_info)
    if SERVER_MODE == "ollama":
        return "Ollama is running"
    else:
        return "LM Studio is running"

@app.route('/', methods=['OPTIONS'])
def root_options():
    """OPTIONS for root endpoint"""
    route_info = "OPTIONS / - Root"
    ui_manager.update_route(route_info)
    
    response = Response()
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@app.route('/__shutdown', methods=['POST'])
def shutdown():
    """Shutdown server with robust fallback (works even without werkzeug handle)."""
    try:
        route_info = "POST /__shutdown - Shutdown"
        ui_manager.update_route(route_info)

        # Try werkzeug shutdown first
        func = request.environ.get('werkzeug.server.shutdown')
        if func is not None:
            try:
                func()
                return jsonify({"status": "shutting down"})
            except Exception as e:
                logger.warning(f"Werkzeug shutdown failed: {e}")

        # Fallback: hard-exit the process shortly after responding
        try:
            import threading, os, time as _time
            def _delayed_exit():
                try:
                    _time.sleep(0.2)
                finally:
                    os._exit(0)
            threading.Thread(target=_delayed_exit, daemon=True).start()
            return jsonify({"status": "shutting down (fallback)"})
        except Exception as e:
            logger.error(f"Fallback shutdown failed: {e}")
            return jsonify({"error": str(e)}), 500

    except Exception as e:
        logger.error(f"Shutdown error: {e}")
        return jsonify({"error": str(e)}), 500

def parse_tools_to_text(tools):
    """Parse tools thành text format"""
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
                    
                    # Handle enum values
                    if 'enum' in prop_info:
                        enum_values = prop_info['enum']
                        tools_text += f"    Values: {', '.join(enum_values)}\n"
            
            tools_text += "\n"
    
    return tools_text

def _make_display_data_short(data, max_len: int = 200):
    """Tạo bản sao rút gọn data chỉ để hiển thị trong UI, không ảnh hưởng dữ liệu gốc."""
    try:
        display_data = copy.deepcopy(data) if data else {}
        # Truncate long messages for display
        if 'messages' in display_data and isinstance(display_data['messages'], list):
            for msg in display_data['messages']:
                if isinstance(msg, dict) and 'content' in msg:
                    content = msg['content']
                    if isinstance(content, str) and len(content) > max_len:
                        msg['content'] = content[:max_len] + "..."
        return display_data
    except Exception:
        # Nếu có lỗi, trả về data gốc để tránh chặn log
        return data

def parse_json_request():
    """Decorator để parse JSON request không cần Content-Type"""
    def decorator(f):
        import functools
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                if request.content_type and 'application/json' in request.content_type:
                    # Nếu có Content-Type application/json, dùng get_json()
                    request.json_data = request.get_json()
                else:
                    # Nếu không có Content-Type, parse từ raw data
                    raw_data = request.get_data(as_text=True)
                    if raw_data:
                        request.json_data = json.loads(raw_data)
                    else:
                        request.json_data = {}
            except Exception as e:
                return jsonify({"error": f"Invalid JSON: {str(e)}"}), 400
            return f(*args, **kwargs)
        return wrapper
    return decorator

def ask_server_mode():
    """Hỏi người dùng chọn mode server hoặc sử dụng argument"""
    global SERVER_MODE
    
    # Nếu có argument --mode, sử dụng luôn
    if args.mode:
        SERVER_MODE = args.mode
        app.config['SERVER_MODE'] = SERVER_MODE
        if SERVER_MODE == "lmstudio":
            if not BACKGROUND_MODE:
                print("✅ Đã chọn LM Studio Mode - Port 1235")
            return 1235
        else:
            if not BACKGROUND_MODE:
                print("✅ Đã chọn Ollama Mode - Port 11434")
            return 11434
    
    # Nếu có argument --port, xác định mode dựa trên port
    if args.port:
        if args.port == 1235:
            SERVER_MODE = "lmstudio"
            app.config['SERVER_MODE'] = SERVER_MODE
            if not BACKGROUND_MODE:
                print("✅ Đã chọn LM Studio Mode - Port 1235")
            return 1235
        elif args.port == 11434:
            SERVER_MODE = "ollama"
            app.config['SERVER_MODE'] = SERVER_MODE
            if not BACKGROUND_MODE:
                print("✅ Đã chọn Ollama Mode - Port 11434")
            return 11434
        else:
            # Port tùy chỉnh, hỏi mode
            pass
    
    # Trong background mode, default to lmstudio nếu không có argument
    if BACKGROUND_MODE:
        SERVER_MODE = "lmstudio"
        app.config['SERVER_MODE'] = SERVER_MODE
        return 1235
    
    # Hỏi người dùng chọn mode nếu không có argument
    print("\n" + "="*50)
    print("🤖 CUSTOM SERVER - CHỌN MODE")
    print("="*50)
    print("1. LM Studio Mode (port 1235)")
    print("2. Ollama Mode (port 11434)")
    print("="*50)
    
    while True:
        try:
            choice = input("Chọn mode (1 hoặc 2): ").strip()
            if choice == "1":
                SERVER_MODE = "lmstudio"
                app.config['SERVER_MODE'] = SERVER_MODE
                print("✅ Đã chọn LM Studio Mode - Port 1235")
                return 1235
            elif choice == "2":
                SERVER_MODE = "ollama"
                app.config['SERVER_MODE'] = SERVER_MODE
                print("✅ Đã chọn Ollama Mode - Port 11434")
                return 11434
            else:
                print("❌ Vui lòng chọn 1 hoặc 2")
        except KeyboardInterrupt:
            print("\n🛑 Thoát chương trình")
            sys.exit(0)

#! routes moved to controllers blueprints



@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors and release lock"""
    route_info = "ERROR 500 - Internal Server Error"
    logger.error(f"ROUTE: {route_info}")
    ui_manager.update_route(route_info)
    
    logger.error(f"Internal server error: {error}")
    queue_manager.release_lock("error_handler")
    return jsonify({
        "error": {
            "message": "Internal server error",
            "type": "server_error"
        }
    }), 500


if __name__ == '__main__':
    # Parse arguments first
    args = parse_arguments()
    
    # Set background mode if specified
    if args.background:
        BACKGROUND_MODE = True
    
    # Lấy max context length và set environment variables khi chạy trực tiếp
    if not BACKGROUND_MODE:
        # Đọc host và port từ ui_settings.json
        max_context = get_max_context_length()
        if max_context:
            # Đọc lại settings để hiển thị thông tin chính xác
            settings = load_ui_settings()
            host = settings.get("ip_address", "127.0.0.1")
            port = settings.get("port", 11434)
            print(f"✅ Đã set OLLAMA environment variables:")
            print(f"  OLLAMA_CONTEXT_LENGTH = {max_context}")
            print(f"  OLLAMA_HOST = {host}:{port}")
            print(f"  OLLAMA_ORIGINS = {host}:{port}")
        else:
            print("⚠️ Không thể lấy max context length từ models")
    
    # Only GUI UI supported; exit if cannot initialize
    if not BACKGROUND_MODE:
        try:
            from utils.gui_ui import gui_ui
            if not gui_ui.is_display_available():
                logger.error("DISPLAY not available. GUI UI is required. Exiting.")
                raise SystemExit(1)

            # Set mode and port if specified in args
            if args.mode:
                port = 1235 if args.mode == "lmstudio" else 11434
                gui_ui.mode = args.mode
                gui_ui.port = port
            elif args.port:
                # Determine mode from port
                mode = "lmstudio" if args.port == 1235 else "ollama" if args.port == 11434 else None
                if mode:
                    gui_ui.mode = mode
                    gui_ui.port = args.port

            # Initialize GUI but don't start it yet
            if gui_ui.initialize():
                logger.info("GUI UI initialized successfully")

                # Register GUI with UI manager
                ui_manager.set_ui(gui_ui, 'gui')

                # Auto-start server if requested
                if args.start:
                    gui_ui._start_server()

                # Start GUI in main thread (this will block)
                gui_ui.run_main_loop()
            else:
                logger.error("Failed to initialize GUI UI. Exiting.")
                raise SystemExit(1)
        except SystemExit:
            raise
        except Exception as e:
            logger.error(f"Error initializing GUI: {e}")
            raise SystemExit(1)
