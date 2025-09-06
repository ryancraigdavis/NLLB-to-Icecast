# NLLB Translation API Gateway

Your real-time translation pipeline is now available as a REST API with WebSocket streaming!

## 🚀 Quick Start

### Start the API Server
```bash
# From the backend directory
source .venv/bin/activate
python -m nllb_to_icecast.run_api

# Or with custom settings
python -m nllb_to_icecast.run_api --host 0.0.0.0 --port 8000 --reload
```

The server will start at: `http://127.0.0.1:8000`

### API Documentation
- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

## 📡 WebSocket Connection

Connect to `ws://127.0.0.1:8000/ws` for real-time translation streaming.

### WebSocket Events
```json
// Transcription results
{
  "type": "transcription",
  "data": {
    "text": "Hello world",
    "language": "en",
    "confidence": 0.95,
    "language_probability": 0.99,
    "real_time_factor": 0.5,
    "timestamp": 1234567890,
    "is_correction": false
  }
}

// Translation results  
{
  "type": "translation",
  "data": {
    "source_text": "Hello world",
    "translated_text": "Hola mundo",
    "source_language": "english", 
    "target_language": "spanish",
    "confidence": 0.92,
    "processing_time": 0.15
  }
}

// Status updates
{
  "type": "status",
  "data": {
    "is_running": true,
    "source_language": "en",
    "target_languages": ["spanish", "french"],
    "audio_device": "Default Device"
  }
}

// Errors
{
  "type": "error", 
  "data": {
    "message": "Pipeline failed to start"
  }
}
```

## 🛠️ REST API Endpoints

### Get Audio Devices
```bash
curl -X GET "http://127.0.0.1:8000/audio/devices"
```

### Start Translation Pipeline
```bash
curl -X POST "http://127.0.0.1:8000/pipeline/start" \
  -H "Content-Type: application/json" \
  -d '{
    "source_language": null,
    "target_languages": ["spanish", "french"],
    "whisper_model": "large-v3",
    "device_index": null,
    "sample_rate": 16000
  }'
```

### Stop Pipeline  
```bash
curl -X POST "http://127.0.0.1:8000/pipeline/stop"
```

### Get Pipeline Status
```bash
curl -X GET "http://127.0.0.1:8000/pipeline/status"
```

### Health Check
```bash
curl -X GET "http://127.0.0.1:8000/health"
```

## 🌐 Frontend Integration

### JavaScript WebSocket Example
```javascript
const ws = new WebSocket('ws://127.0.0.1:8000/ws');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  
  if (msg.type === 'transcription') {
    console.log('Transcription:', msg.data.text);
    // Update UI with transcribed text
  }
  
  if (msg.type === 'translation') {
    console.log('Translation:', msg.data.translated_text);
    // Update UI with translated text
  }
};

// Start pipeline via REST API
fetch('http://127.0.0.1:8000/pipeline/start', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    source_language: null, // auto-detect
    target_languages: ['spanish', 'french'],
    whisper_model: 'large-v3'
  })
});
```

## 🎯 Next Steps for Frontend

1. **Create a React/Vue/HTML frontend** that:
   - Connects to the WebSocket for real-time updates
   - Displays transcription and translations as they stream in
   - Provides controls to start/stop the pipeline
   - Shows audio device selection

2. **Real-time Display Features**:
   - Live transcription text (with language detection)
   - Multi-language translation panels
   - Audio level indicators
   - Connection status
   - Error handling

3. **Future Enhancements**:
   - Audio streaming for Icecast integration
   - Recording/playback controls
   - Translation history
   - Multiple pipeline support

## 🔧 Development

The API automatically integrates with your existing `TranslationPipeline` class and maintains all the same audio processing, Whisper transcription, and NLLB translation functionality - just exposed via WebSocket and REST APIs now!