# QwenToApi - Qwen API Integration

Server tùy chỉnh tích hợp với Qwen API, hỗ trợ cả LM Studio và Ollama format với giao diện GUI hiện đại.

## 🚀 Tính năng

- **Dual Mode**: Hỗ trợ cả LM Studio (port 1235) và Ollama (port 11434)
- **Modern GUI**: Giao diện người dùng hiện đại với responsive design
- **Think Mode**: Hỗ trợ tính năng suy nghĩ của Qwen với `<think>` tags
- **Image Support**: Hỗ trợ xử lý hình ảnh base64 (Ollama mode)
- **Queue System**: Hệ thống xếp hàng để xử lý request đồng thời
- **Background Mode**: Chạy server trong background không có output
- **Real-time Monitoring**: Theo dõi trạng thái server và queue real-time
- **Model Management**: Hiển thị và quản lý models với copy functionality
- **Chat Management**: Quản lý chat sessions với chat ID tracking

## 📋 Yêu cầu hệ thống

- Python 3.7+
- Windows 10/11 (GUI mode)
- Internet connection để truy cập Qwen API

## 🛠️ Cài đặt

```bash
# Clone repository
git clone https://github.com/khanhnguyen9872/custom_server_lmstudio.git
cd custom_server_lmstudio

# Cài đặt dependencies
pip install -r requirements.txt
```

## 🎮 Sử dụng

### GUI Mode (Khuyến nghị)
```bash
python main.py
```

### Terminal Mode
```bash
python server.py
```

### Background Mode
```bash
python server.py --background
```

### Command Line Arguments

```bash
# Chạy trong background mode (không có output)
python server.py --background

# Chỉ định mode
python server.py --mode lmstudio
python server.py --mode ollama

# Chỉ định port
python server.py --port 1235
python server.py --port 11434

# Chỉ định host
python server.py --host 127.0.0.1

# Kết hợp nhiều argument
python server.py --background --mode ollama --port 11434
```

## 🖥️ GUI Features

### Dashboard Tab
- **Server Status**: Hiển thị trạng thái server real-time
- **Current Route**: Theo dõi route và request body hiện tại
- **Queue Status**: Hiển thị trạng thái queue và thời gian xử lý
- **Chat Controls**: Quản lý chat sessions

### Logs Tab
- **Real-time Logs**: Hiển thị logs server theo thời gian thực
- **Log Management**: Clear logs và filter

### Settings Tab
- **Server Configuration**: Cấu hình IP, port, mode
- **UI Scale**: Điều chỉnh kích thước giao diện (100% - 200%)
- **Cookie Management**: Quản lý Qwen cookie
- **Model Cache**: Refresh model cache

### Keyboard Shortcuts
- `Ctrl+S` - Start Server
- `Ctrl+Q` - Stop Server
- `Ctrl+N` - New Chat
- `Ctrl+M` - Show Models
- `Ctrl+R` - Show Routes
- `F1` - Show Help
- `F2` - Show About
- `F5` - Refresh Status
- `Escape` - Close Popups

## 🔌 API Endpoints

### LM Studio Mode (port 1235)

- `GET /` - Root endpoint
- `GET /v1/models` - Danh sách models
- `GET /v1/models/{model_id}` - Thông tin model
- `POST /v1/chat/completions` - Chat completions
- `POST /v1/completions` - Text completions (deprecated)
- `POST /v1/embeddings` - Embeddings (not supported)

### Ollama Mode (port 11434)

- `GET /` - Root endpoint
- `GET /api/version` - Phiên bản Ollama
- `GET /api/tags` - Danh sách models
- `GET /api/ps` - Models đang chạy
- `POST /api/show` - Thông tin model
- `POST /api/generate` - Generate response
- `POST /api/chat` - Chat endpoint
- `GET|POST /v1/*` - With All API of LM Studio

## 🧠 Think Mode

### LM Studio
```json
{
  "model": "qwen3-235b-a22b",
  "messages": [{"role": "user", "content": "Hãy suy nghĩ về câu hỏi này"}],
  "stream": true
}
```

Response sẽ có `<think>` tags:
```
<think>Đang suy nghĩ về câu hỏi...</think>
Câu trả lời của tôi là...
```

### Ollama
```json
{
  "model": "qwen3-235b-a22b",
  "messages": [{"role": "user", "content": "Hãy suy nghĩ về câu hỏi này"}],
  "stream": true
}
```

Response sẽ có `thinking` field:
```json
{
  "model": "qwen3-235b-a22b",
  "message": {
    "role": "assistant",
    "thinking": "Đang suy nghĩ về câu hỏi...",
    "content": "Câu trả lời của tôi là..."
  }
}
```

## 📊 Queue System

Server sử dụng hệ thống xếp hàng để xử lý request đồng thời:
- **Timeout**: 2 phút
- **Request timeout**: 60 giây
- **Concurrent processing**: Chỉ xử lý 1 request tại một thời điểm
- **Real-time monitoring**: Hiển thị trạng thái queue trong GUI

## 📝 Logs

- **File logs**: Được lưu trong thư mục `logs/` với format ngày tháng
- **GUI logs**: Hiển thị real-time trong tab Logs
- **Log rotation**: Tự động quản lý kích thước logs

## 🔧 Configuration

### Settings File
Các cài đặt được lưu trong `ui_settings.json`:
- UI Scale
- IP Address
- Port
- Server Mode
- Selected Model
- Cookie Value

### Cookie Setup
1. Mở Qwen chat trong browser
2. Copy cookie từ Developer Tools
3. Paste vào Settings tab trong GUI
4. Save configuration

## 🚨 Troubleshooting

### Server không khởi động
- Kiểm tra port có đang được sử dụng không
- Kiểm tra cookie trong Settings
- Kiểm tra kết nối internet
- Chạy với quyền administrator nếu cần

### Request bị timeout
- Server đang xử lý request khác
- Đợi 2 phút hoặc restart server
- Kiểm tra trạng thái queue trong GUI

### Think mode không hoạt động
- Đảm bảo model hỗ trợ think mode
- Kiểm tra response format
- Thử với model khác

### GUI không hiển thị
- Kiểm tra Python version (3.7+)
- Cài đặt tkinter: `pip install tk`
- Chạy trên Windows 10/11

## 📦 Build

### Windows Executable
```bash
# Sử dụng Nuitka
python -m nuitka --onefile --windows-icon-from-ico=qwen.ico main.py

# Hoặc sử dụng PyInstaller
pyinstaller --onefile --windowed --icon=qwen.ico main.py
```

## 🤝 Contributing

1. Fork repository
2. Tạo feature branch
3. Commit changes
4. Push to branch
5. Tạo Pull Request

## 📄 License

MIT License - Xem file [LICENSE](LICENSE) để biết thêm chi tiết.

## 👨‍💻 Developer

**KhanhNguyen9872**

- GitHub: [@khanhnguyen9872](https://github.com/khanhnguyen9872)
- Repository: [custom_server_lmstudio](https://github.com/khanhnguyen9872/custom_server_lmstudio)

## 🔄 Changelog

### v1.0.1
- ✨ Thêm GUI hiện đại với responsive design
- 🎯 Hiển thị phiên bản trong UI
- 📊 Real-time monitoring dashboard
- 🎮 Keyboard shortcuts
- 🔧 Settings management
- 📝 Log viewer
- 🧠 Chat management
- 🎨 UI scaling (100% - 200%)
- 📱 Responsive layout
- 🔄 Model cache refresh

### v1.0.0
- 🚀 Initial release
- 🔌 Dual mode support (LM Studio & Ollama)
- 🧠 Think mode implementation
- 🖼️ Image support
- 📊 Queue system
- 🔧 Background mode
