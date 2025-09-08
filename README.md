# 🌍 NLLB-to-Icecast Real-Time Translation System

A real-time audio translation system that captures live audio, transcribes it using OpenAI's Whisper, and translates it to multiple languages using Meta's NLLB (No Language Left Behind) model. The system features a modern web interface and WebSocket-based real-time streaming.

## 🎯 What It Does

- **Real-time Audio Capture**: Captures audio from your system's microphone or audio input devices
- **Speech-to-Text**: Transcribes audio using OpenAI Whisper with language auto-detection 
- **Multi-language Translation**: Translates transcribed text to multiple target languages using NLLB
- **Live Web Interface**: Modern Svelte-based frontend with real-time translation display
- **WebSocket Streaming**: Real-time communication between backend and frontend
- **Customizable Display**: Adjustable font sizes for translation text (from Small to Massive)
- **Audio Device Management**: Automatic detection and display of current audio input device

## 🏗️ Architecture

```
┌─────────────────┐    WebSocket     ┌──────────────────┐
│  Frontend (Web) │◄────────────────►│  Backend API     │
│  - Svelte UI    │    HTTP/REST     │  - FastAPI       │
│  - Translation  │                  │  - WebSocket     │
│  - Font Control │                  │  - Audio Pipeline│
└─────────────────┘                  └──────────────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │ Audio Processing │
                                    │ - Whisper STT    │
                                    │ - NLLB Translate │
                                    │ - Device Capture │
                                    └──────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** (with uv package manager)
- **Node.js** (for the frontend)
- **CUDA GPU** (recommended for faster inference)
- **Doppler CLI** (for environment management)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd NLLB-to-Icecast
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv sync
```

### 3. Environment Configuration with Doppler

Set up Doppler with your credentials and environment variables:

```bash
# Configure Doppler (replace with your actual credentials)
doppler configure

# The system expects certain environment variables through Doppler
# Configure your Doppler project with necessary API keys and settings
```

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
```

## 🔧 Running the Application

### Backend (API Server)

From the `backend` directory:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run with Doppler (recommended)
doppler run -- python -m nllb_to_icecast.run_api

# Or run directly (development)
python -m nllb_to_icecast.run_api --host 0.0.0.0 --port 8000 --reload
```

The backend will start at: `http://127.0.0.1:8000`

**API Documentation:**
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### Frontend (Web Interface)

From the `frontend` directory:

```bash
# Development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

The frontend will be available at: `http://localhost:5173` (development)

## 🎮 How to Use

1. **Start the Backend**: Run the API server using the commands above
2. **Start the Frontend**: Launch the web interface in development mode
3. **Select Languages**: 
   - Choose input language (or leave as "Auto-detect")
   - Select your desired output/translation language
4. **Adjust Display**: Use the "Translation Size" dropdown to customize font size
5. **Start Translation**: Click "🎤 Start Translation" to begin real-time processing
6. **Monitor**: Watch live transcription and translation appear in real-time

## 📋 Supported Languages

**Input Languages** (Auto-detection available):
- English, Spanish, Turkish, Portuguese, Korean, Chinese/Mandarin, Farsi/Persian, Russian, Japanese

**Output Languages**:
- Spanish, Turkish, Portuguese, Korean, Chinese/Mandarin, Farsi/Persian, Russian, English, Japanese

## 🔧 Development

### Backend Structure
```
backend/
├── src/nllb_to_icecast/
│   ├── api_gateway.py              # FastAPI application
│   ├── run_api.py                  # Application entry point
│   ├── audio_translation_orchestrator.py  # Main pipeline orchestrator
│   ├── audio/
│   │   └── capture.py              # Audio input handling
│   ├── processing/
│   │   ├── transcription.py        # Whisper integration
│   │   └── nllb_translator.py      # NLLB translation
│   └── streaming/                  # WebSocket handlers
├── pyproject.toml                  # Dependencies & project config
└── README.md                       # Backend-specific documentation
```

### Frontend Structure
```
frontend/
├── src/routes/
│   └── +page.svelte               # Main application interface
├── package.json                   # Node.js dependencies
└── README.md                      # Frontend-specific documentation
```

### Key Technologies

**Backend:**
- FastAPI for REST API and WebSocket handling
- Faster-Whisper for speech-to-text transcription
- Transformers + NLLB for translation
- PyTorch with CUDA support
- SoundDevice for audio capture

**Frontend:**
- SvelteKit for reactive UI
- WebSocket for real-time communication
- TypeScript for type safety

## 🌟 Features

### Translation Features
- ✅ Real-time audio capture and processing
- ✅ Automatic language detection
- ✅ Multi-language translation support  
- ✅ Live transcription confidence scores
- ✅ Translation confidence indicators
- ✅ Audio level monitoring
- ✅ Device status tracking

### UI Features
- ✅ Modern, responsive web interface
- ✅ Real-time WebSocket updates
- ✅ Customizable translation text size (6 size options)
- ✅ Language selection with visual indicators
- ✅ Connection status monitoring
- ✅ Audio device information display
- ✅ Error handling and user feedback

## 🔮 Future Enhancements

- [ ] Icecast streaming integration
- [ ] Translation history and export
- [ ] Multiple simultaneous translation pipelines
- [ ] Voice synthesis for translated text
- [ ] Advanced audio filtering and processing
- [ ] MacOS and Windows Application

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly (both backend API and frontend)
5. Submit a pull request

## 📄 License

This project uses Meta's NLLB model and OpenAI's Whisper. Please respect their respective licenses and usage terms.

---

**Built with ❤️ by Ryan Davis**

For detailed component-specific information, see the README files in the `backend/` and `frontend/` directories.
