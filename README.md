# Pace 🎙️

### Keep up with your thoughts.

<p align="center">

<img src="https://img.shields.io/github/stars/rofuniki-coder/Pace?style=for-the-badge&logo=github" />

<img src="https://img.shields.io/github/forks/rofuniki-coder/Pace?style=for-the-badge&logo=github" />

[<img src="https://img.shields.io/github/license/rofuniki-coder/Pace?style=for-the-badge" />
](https://img.shields.io/github/license/rofuniki-coder/Pace?style=for-the-badge&cacheSeconds=60)

<img src="https://img.shields.io/github/repo-size/rofuniki-coder/Pace?style=for-the-badge" />

<img src="https://img.shields.io/github/languages/top/rofuniki-coder/Pace?style=for-the-badge" />

<img src="https://img.shields.io/github/last-commit/rofuniki-coder/Pace?style=for-the-badge" />

</p>

**Pace** is a lightning-fast **local speech-to-text desktop application** built for seamless dictation anywhere on your system.

Powered by **Whisper (via faster-whisper)** and built with **Electron + Python**, Pace provides **instant transcription directly into your active window**.

No cloud.
No subscriptions.
No latency.

Just speak **Pace types.**

---

# ⚡ Why Pace?

Most dictation tools today rely on:

* cloud processing
* subscriptions
* closed ecosystems

Pace was built with a different philosophy.

✔ Local-first
✔ Open-source
✔ Community-driven
✔ Instant transcription

Your voice **never leaves your machine**.

---

# ✨ Features

## 🎤 Instant Dictation

Hold the hotkey, speak naturally, and release.

Your words appear **exactly where your cursor is**.

No switching apps.
No copy-paste.

---

## ⚡ Zero-Latency Transcription

Pace uses **faster-whisper** to run speech recognition locally with extremely low latency.

No network delays.
No waiting for servers.

---

## 🧠 Zero-Cache Audio Processing

Pace is fundamentally incapable of storing past audio.

Each session is:

1. recorded
2. transcribed
3. immediately discarded

No logs.
No recordings.
No hidden storage.

---

## ⌨️ Hardware-Level Hotkey Detection

Pace uses the Windows **GetAsyncKeyState API** for ultra-responsive hotkey detection.

This allows:

* instant recording start
* instant stop
* zero UI lag

---

## ✍️ Direct System Typing

Pace types **directly into your active window**.

It bypasses the clipboard entirely, eliminating:

* clipboard pollution
* delayed pastes
* “ghost” clipboard overwrites

---

## 🪶 Minimal Floating UI

A lightweight floating **pill interface** stays quietly on your screen.

Click to record.
Right-click for options.
Stay in your workflow.

---

## 🛡️ Privacy First

All transcription happens **locally**.

No data collection.
No telemetry.
No external servers.

---

## 🧟 Zombie Process Protection

Pace automatically detects and cleans orphaned background processes to ensure stability.

No lingering background tasks.

---

# 🔥 Why Pace Exists

Modern voice-dictation tools are powerful — but many come with trade-offs:

* subscription pricing
* cloud processing
* closed ecosystems
* limited transparency

Tools like Wispr Flow have demonstrated how powerful real-time dictation can be.

**Pace takes that idea further.**

Instead of a paid cloud product, Pace is designed as a **local, open alternative** that anyone can use, improve, and extend.

---

# ⚔️ Pace vs Paid Dictation Tools

| Feature           | Pace                                      | Paid Dictation Apps |
| ----------------- | ----------------------------------------- | ------------------- |
| Price             | **Free & open source**                    | Subscription        |
| Speech Processing | **Fully local**                           | Often cloud         |
| Privacy           | **Your data never leaves your machine**   | Depends on provider |
| Customization     | **Open source + community contributions** | Limited             |
| Latency           | **Near-instant local processing**         | Network dependent   |
| Extensibility     | **Hackable**                              | Closed ecosystem    |

---

# 🧠 The Philosophy

Pace is built on three core principles.

### 1️⃣ Your voice belongs to you

No servers.
No telemetry.
No hidden data collection.

---

### 2️⃣ Tools should be owned, not rented

You shouldn't need a **monthly subscription** to use your own voice.

---

### 3️⃣ Software gets better with community

Pace is designed to evolve through:

* contributions
* plugins
* community improvements

---

# 🌍 The Long-Term Vision

Pace isn't just another dictation tool.

The goal is to build the **best open-source speech-to-text workflow** for developers, writers, and creators.

Future plans include:

* plugin architecture
* smarter formatting commands
* multi-language dictation
* AI-assisted editing
* community-driven improvements

---

# 🚀 Getting Started

## Prerequisites

* Node.js (v18 or higher recommended)
* Python 3.11+
* FFmpeg (required by faster-whisper)

---

## Installation

Clone the repository

git clone [https://github.com/rofuniki-coder/Pace.git](https://github.com/rofuniki-coder/Pace.git)

cd Pace

Install Node dependencies

npm install

Install Python dependencies

pip install -r requirements.txt

Run the application

npm start

---

# ⌨️ How to Use

### Start Dictation

Hold:

Ctrl + Alt

Release to stop recording and instantly insert the transcription.

---

### Manual Toggle

Click the floating **Pace pill** to start or stop recording.

---

### Context Menu

Right-click the pill to:

* view transcription history
* hide the app for an hour
* check for updates

---

# 🧩 Built With

* Electron — Desktop interface
* Python — Speech processing backend
* Whisper (faster-whisper) — Local speech recognition
* FFmpeg — Audio processing

---

# ⭐ Star History

<p align="center">
<a href="https://star-history.com/#rofuniki-coder/Pace&Date">
<img src="https://api.star-history.com/svg?repos=rofuniki-coder/Pace&type=Date" width="600"/>
</a>
</p>

---

# 🤝 Contributing

Contributions are welcome.

Ways to contribute:

* fix bugs
* suggest features
* improve documentation
* submit pull requests

Steps:

1. Fork the repository
2. Create a new branch
3. Commit your changes
4. Push to your branch
5. Open a Pull Request

---

# 🌍 Community

If you find Pace useful:

⭐ Star the repository
🐛 Report issues
💡 Suggest features
🔧 Contribute improvements

Every contribution helps make **Pace the best open-source dictation tool.**

---

# 📄 License

This project is licensed under the **MIT License**.

---

# ❤️ Credits

Built by
**rofuniki-coder**

---

# Disclaimer

Wispr Flow is a trademark of its respective owners.
Pace is an independent open-source project and is **not affiliated with or endorsed by** Wispr Flow.

References to Wispr Flow are made strictly for **comparison purposes**.
