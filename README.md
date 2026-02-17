# QwenToApi

<div align="center">
  <img src="qwen.ico" alt="QwenToApi Logo" width="100" />
  <h1>QwenToApi</h1>
  <p><strong>Advanced Qwen API Wrapper & Server</strong> <br /> Integrate Qwen with LM Studio and Ollama formats via a modern GUI.</p>
</div>

<div align="center">

[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows-blue.svg)]()
[![Language](https://img.shields.io/badge/language-Python-blue.svg)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)]()

</div>

## 🌟 Introduction

**QwenToApi** is a custom server implementation that wraps the Qwen AI model allows it to function as a drop-in replacement for **LM Studio** and **Ollama** APIs. It provides a robust bridge/proxy with a modern graphical user interface (GUI) for management and monitoring.

Designed for power users, it supports advanced features like "Think Mode", image processing, and real-time request queuing.

## ✨ Key Features

-   **🔄 Dual Operation Modes**:
    -   **LM Studio Mode**: Emulates LM Studio API on port `1235`.
    -   **Ollama Mode**: Emulates Ollama API on port `11434`.
-   **🖥️ Modern Dashboard (GUI)**:
    -   **Real-time Status**: Monitor server health, current route, and active requests.
    -   **Queue Management**: Visual request queue system with timeouts.
    -   **Logs**: Live server logs and filtering.
-   **🧠 Advanced Capabilities**:
    -   **Think Mode**: Native support for Qwen's `<think>` tags in streaming responses.
    -   **Image Support**: Handles Base64 image inputs (Ollama mode).
    -   **Context Management**: Auto-detection and setting of context length.
-   **🛠️ System Integration**:
    -   **Background Mode**: Run silently without a GUI.
    -   **Environment Sync**: Automatically sets `OLLAMA_HOST` and `OLLAMA_CONTEXT_LENGTH` system variables.

## 🚀 Getting Started

### Prerequisites

-   Windows 10/11 (Required for GUI)
-   Python 3.7+
-   Internet connection (for Qwen API access)

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/khanhnguyen9872/custom_server_lmstudio.git
    cd custom_server_lmstudio
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

### Usage

**GUI Mode (Recommended):**
```bash
python main.py
```

**Command Line (Headless):**
```bash
python server.py --mode ollama --port 11434 --background
```

## 🎮 GUI Controls

-   **Dashboard**: Overview of server status and request queue.
-   **Logs**: detailed system logs.
-   **Settings**: Configure IP, Port, UI Scaling, and Qwen Cookies.

| Shortcut | Action |
| :--- | :--- |
| `Ctrl+S` | Start Server |
| `Ctrl+Q` | Stop Server |
| `Ctrl+N` | New Chat |
| `Ctrl+M` | Show Models |

## 🔌 API Endpoints

The server exposes standard compatible endpoints:

-   **LM Studio / OpenAI Compatible**:
    -   `/v1/chat/completions`
    -   `/v1/models`
-   **Ollama Compatible**:
    -   `/api/generate`
    -   `/api/chat`
    -   `/api/tags`

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## ✍️ Author

**Nguyễn Văn Khánh** (KhanhNguyen9872)

-   GitHub: [@KhanhNguyen9872](https://github.com/KhanhNguyen9872)

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
