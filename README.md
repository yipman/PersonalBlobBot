# 🧠 Personal Blob AI & TheBlob

<div align="center">
  
  ![Personal Blob AI Logo](https://i.imgur.com/xYTG9kF.png)

  **Your personal AI memory system - Store, retrieve and share knowledge with semantic search**

  [![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-✓-blue)](https://core.telegram.org/bots/api)
  
</div>

## 📋 Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Setup Instructions](#setup-instructions)
- [Usage Guide](#usage-guide)
- [Commands](#commands)
- [Advanced Features](#advanced-features)
- [Technical Notes](#technical-notes)
- [Contributing](#contributing)

## 🌟 Overview

Personal Blob AI is a Telegram bot that lets you create your personal knowledge database with advanced semantic search capabilities. Think of it as your second brain that remembers everything you share with it. The system consists of two main components:

- **Blobby** (Telegram Bot): Your personal AI assistant that helps you store and retrieve information.
- **TheBlob**: A public knowledge repository where users can share information with the community.

## 🏗️ Architecture

```
┌─────────────────┐      ┌────────────────┐      ┌──────────────┐
│  Telegram Bot   │◄────►│  Personal AI   │◄────►│  Database    │
│    Interface    │      │    System      │      │   (SQLite)   │
└─────────────────┘      └────────────────┘      └──────────────┘
                                ▲
                                │
                                ▼
       ┌───────────────────────────────────────────┐
       │      Local AI Services (API Layer)        │
       └───────────────────────────────────────────┘
                 ▲                    ▲
                 │                    │
    ┌────────────┘                    └───────────┐
    ▼                                            ▼
┌─────────────┐                          ┌────────────────┐
│ Text Models │                          │  Vision Models │
└─────────────┘                          └────────────────┘
```

## ✨ Features

### MyBlob (Private Storage)
- **Store various content types**: Text, images, documents, and more
- **Automatic summarization**: AI-generated summaries for quick review
- **Semantic search**: Find information based on meaning, not just keywords
- **Deep thinking**: AI analysis of connections between your stored information
- **Voice output**: Listen to your stored information

### TheBlob (Public Repository)
- **Share knowledge**: Make your blobs publicly accessible
- **Community learning**: Access insights shared by others
- **Privacy control**: Easily unshare content when needed

## 🛠️ Setup Instructions

### Prerequisites
- Python 3.9+
- Local Ollama instance with supported models (see [Ollama](https://github.com/ollama/ollama))
- Telegram Bot Token

### Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/personal-blob-ai.git
cd personal-blob-ai
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `config.py` file with your Telegram bot token:
```python
BOT_TOKEN = "your_telegram_bot_token_here"
```

4. Run the bot:
```bash
python personalblobbot.py
```

## 📱 Usage Guide

### Getting Started
1. Start a chat with the bot by sending `/start`
2. The bot will guide you through available commands
3. Send any text, image, or document to store it in MyBlob
4. Use `/ask` to search through your stored information

### Storing Information
Send any of the following to the bot:
- **Text messages**: Stored directly
- **Images**: Automatically analyzed with vision AI
- **Documents**: Stored for future retrieval

### Retrieving Information
Use natural language queries to find what you're looking for:
- `/ask where did I put my passport?`
- `/ask what was that recipe for chocolate cake?`

### Sharing to TheBlob
After storing content, you can:
- Click "Share to TheBlob" button to make it public
- Use `/share [blob_id]` command manually

## 🔍 Commands

| Command | Description |
|---------|-------------|
| `/start` | Start interacting with Personal Blob AI |
| `/help` | Show help message with available commands |
| `/store [text]` | Store text information to MyBlob (private) |
| `/share [blob_id]` | Share information to TheBlob (public) |
| `/unshare [blob_id]` | Remove blob from TheBlob (make private) |
| `/ask [question]` | Ask questions about stored information |
| `/list` | List your stored blobs |
| `/theblob` | Get link to TheBlob website |

## 🚀 Advanced Features

### Deep Thinking
The bot can analyze connections between different pieces of information:
1. Store related content in MyBlob
2. Click "Deep Think 🤔" on any stored content
3. Get AI analysis showing connections and insights

### Voice Output
Listen to your content instead of reading:
1. Click "🔊 Listen" button on any message
2. The bot will generate and send audio files of the content

### Vision Analysis
When you send an image, the bot:
1. Analyzes what's in the image
2. Generates a detailed description
3. Stores both image and analysis for future reference

## 🔧 Technical Notes

### Storage Structure
- User data is stored in `~/.personalblobai/[user_id]/`
- SQLite database maintains metadata and content relationships
- Vector embeddings enable semantic search

### AI Models
- Text processing: Powered by local Ollama models
- Image analysis: Vision models for content recognition
- Audio generation: Text-to-speech for voice output

### Privacy
- Private blobs are only accessible to their creator
- Shared blobs become available to all users through TheBlob
- All processing happens locally for enhanced privacy

## 👥 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

<div align="center">
  Made with ❤️ by Your Name
</div>