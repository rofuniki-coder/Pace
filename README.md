# Pace 🎙️

**Keep in pace with your words.**

Pace is a lightweight, high-performance Speech-to-Text (STT) desktop application designed for zero-latency transcription. Built with Electron and Python, it uses OpenAI's Whisper model (via `faster-whisper`) to provide local, private, and incredibly fast transcription directly into any active window.

## ✨ Features

- **Zero-Cache Mechanism**: Fundamentally incapable of "remembering" old audio. Every session is atomic and purged instantly.
- **Low-Level Hardware Tracking**: Uses Windows `GetAsyncKeyState` API for ultra-responsive hotkey detection.
- **Direct Typing**: Bypasses the system clipboard to type directly into your active window—no "clipboard ghosts" or delayed pastes.
- **Minimalist UI**: A beautiful, floating pill-container that stays out of your way until you need it.
- **Privacy First**: All transcriptions happen locally on your machine. Nothing is sent to the cloud.
- **Zombie Process Protection**: Automatically cleans up orphaned background processes to ensure stability.

## 🚀 Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/) (v18 or higher recommended)
- [Python 3.11+](https://www.python.org/)
- FFmpeg (required by `faster-whisper`)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/rofuniki-coder/Pace.git
   cd Pace
   ```

2. Install Node.js dependencies:
   ```bash
   npm install
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   npm start
   ```

## ⌨️ How to Use

- **Global Hotkey**: Hold `Ctrl + Alt` to start recording. Release to stop and type instantly.
- **Manual Toggle**: Click the floating pill UI to start/stop recording.
- **Context Menu**: Right-click the pill to view history, hide the app for an hour, or check for updates.

## 🤝 Contributing

We welcome contributions! Whether it's fixing bugs, adding features, or improving documentation, feel free to open a Pull Request or an Issue.

1. Fork the project.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

## 📄 License

This project is licensed under the MIT License.

---

Built with ❤️ by [rofuniki-coder](https://github.com/rofuniki-coder)
