# 🌍 NLLB Translation Frontend

A real-time translation interface built with Svelte that connects to your NLLB translation backend via WebSockets.

## ✅ Complete Features

🎤 **Language Selection**
- Input language dropdown (with auto-detect option)
- Output language dropdown (single target language)
- All supported NLLB languages included

🔌 **WebSocket Integration**
- Real-time connection to backend API
- Auto-reconnection on connection loss
- Live status indicator

⚡ **Real-Time Display**
- Live transcription with confidence scores
- Live translation with confidence scores
- Audio level visualization
- Language detection tags

🎮 **Control Interface**
- Start/Stop pipeline controls
- Error handling and user feedback
- Responsive design for mobile/desktop

## 🚀 Quick Start

### Prerequisites
- Backend API running on `http://127.0.0.1:8000`
- Node.js installed

### Development
```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Frontend will be available at: http://127.0.0.1:5173
```

### Production Build
```bash
npm run build
npm run preview
```

## 🔧 Usage

1. **Start Backend**: Make sure your NLLB API is running:
   ```bash
   cd ../backend
   source .venv/bin/activate
   python -m nllb_to_icecast.run_api
   ```

2. **Open Frontend**: Navigate to `http://127.0.0.1:5173`

3. **Select Languages**:
   - Choose input language (or leave as "Auto-detect")
   - Choose output language for translation

4. **Start Translation**: Click "🎤 Start Translation"

5. **Speak**: The interface will show:
   - Real-time transcription of your speech
   - Live translation to your selected language
   - Audio level meter
   - Confidence scores

6. **Stop**: Click "⏹️ Stop Translation" when done

## 🌐 API Integration

The frontend connects to these backend endpoints:
- `ws://127.0.0.1:8000/ws` - WebSocket for real-time streaming
- `POST /pipeline/start` - Start translation pipeline
- `POST /pipeline/stop` - Stop translation pipeline
- `GET /pipeline/status` - Get current status

## 📱 UI Components

- **Connection Status**: Shows backend connection health
- **Language Selectors**: Dropdown menus for language selection
- **Control Button**: Context-aware start/stop button
- **Audio Level**: Visual audio input meter
- **Transcription Panel**: Live speech-to-text results
- **Translation Panel**: Live translation results
- **Error Display**: User-friendly error messages

## 🎨 Styling

Clean, modern interface with:
- Responsive grid layout
- Color-coded language tags
- Confidence score indicators
- Smooth animations and transitions
- Mobile-friendly design

## 🔄 WebSocket Events

The frontend handles these real-time events:
- `transcription` - Live speech transcription
- `translation` - Live translation results
- `status` - Pipeline status updates
- `error` - Error messages

## 📋 Language Support

**Input Languages** (with auto-detect):
- English, Spanish, Turkish, Portuguese
- Korean, Chinese, Farsi, Russian

**Output Languages**:
- Spanish, Turkish, Portuguese, Korean
- Chinese/Mandarin, Farsi, Russian, English

Perfect for church services, conferences, or any real-time translation needs!