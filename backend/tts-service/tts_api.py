#!/usr/bin/env python3
"""
FastAPI service for Piper TTS.
Provides REST API for text-to-speech synthesis.
"""

import subprocess
import base64
import io
import wave
import logging
from pathlib import Path
from typing import Optional, Dict
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tempfile
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Piper TTS Service", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
MODELS_DIR = Path("/app/models")
OUTPUT_DIR = Path("/app/output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Available voice models
VOICE_MODELS = {
    "zh": "zh_CN-huayan-medium",
    "chinese": "zh_CN-huayan-medium",
    "mandarin": "zh_CN-huayan-medium",
    "es": "es_MX-ald-medium",
    "spanish": "es_MX-ald-medium",
    "en": "en_US-amy-low",
    "english": "en_US-amy-low",
}

# Request models
class TTSRequest(BaseModel):
    text: str
    language: str = "en"
    output_format: str = "wav"  # wav, base64, or raw

class TTSResponse(BaseModel):
    success: bool
    message: str
    audio_base64: Optional[str] = None
    sample_rate: int = 22050
    duration_seconds: Optional[float] = None


def synthesize_with_piper(text: str, language: str) -> Optional[bytes]:
    """
    Synthesize speech using Piper CLI.

    Args:
        text: Text to synthesize
        language: Language code

    Returns:
        WAV audio data as bytes or None if failed
    """
    # Get model name
    model_name = VOICE_MODELS.get(language.lower(), VOICE_MODELS["en"])
    model_path = MODELS_DIR / model_name / f"{model_name}.onnx"
    config_path = MODELS_DIR / model_name / f"{model_name}.onnx.json"

    if not model_path.exists():
        logger.error(f"Model not found: {model_path}")
        return None

    try:
        # Run Piper command
        result = subprocess.run(
            [
                "piper",
                "--model", str(model_path),
                "--config", str(config_path),
                "--output-raw"
            ],
            input=text.encode('utf-8'),
            capture_output=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(f"Piper error: {result.stderr.decode()}")
            return None

        # Convert raw audio to WAV
        raw_audio = result.stdout
        audio_buffer = io.BytesIO()

        with wave.open(audio_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(22050)  # Sample rate
            wav_file.writeframes(raw_audio)

        audio_buffer.seek(0)
        return audio_buffer.read()

    except subprocess.TimeoutExpired:
        logger.error("Piper synthesis timeout")
        return None
    except Exception as e:
        logger.error(f"Synthesis error: {e}")
        return None


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Piper TTS",
        "status": "running",
        "available_languages": list(VOICE_MODELS.keys())
    }


@app.get("/models")
async def list_models():
    """List available voice models."""
    models = {}
    for lang_code, model_name in VOICE_MODELS.items():
        model_path = MODELS_DIR / model_name / f"{model_name}.onnx"
        models[lang_code] = {
            "name": model_name,
            "exists": model_path.exists(),
            "path": str(model_path)
        }
    return {"models": models}


@app.post("/synthesize")
async def synthesize(request: TTSRequest):
    """
    Synthesize speech from text.

    Args:
        request: TTSRequest with text, language, and output_format

    Returns:
        Audio file or base64 encoded audio
    """
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    logger.info(f"Synthesizing {len(request.text)} chars in {request.language}")

    # Synthesize audio
    audio_data = synthesize_with_piper(request.text, request.language)

    if not audio_data:
        raise HTTPException(status_code=500, detail="Failed to synthesize audio")

    # Return based on requested format
    if request.output_format == "base64":
        # Return base64 encoded audio in JSON
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        # Estimate duration (rough calculation)
        duration = len(audio_data) / (22050 * 2)  # 22050 Hz, 16-bit mono

        return TTSResponse(
            success=True,
            message="Audio synthesized successfully",
            audio_base64=audio_base64,
            duration_seconds=duration
        )

    elif request.output_format == "wav":
        # Return WAV file directly
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename=tts_{request.language}.wav"
            }
        )

    else:
        raise HTTPException(status_code=400, detail=f"Invalid output format: {request.output_format}")


@app.post("/synthesize/stream")
async def synthesize_stream(request: TTSRequest):
    """
    Synthesize speech and return as audio stream.
    Always returns WAV format for streaming.
    """
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    logger.info(f"Stream synthesizing {len(request.text)} chars in {request.language}")

    # Synthesize audio
    audio_data = synthesize_with_piper(request.text, request.language)

    if not audio_data:
        raise HTTPException(status_code=500, detail="Failed to synthesize audio")

    # Stream the audio
    return StreamingResponse(
        io.BytesIO(audio_data),
        media_type="audio/wav"
    )


@app.post("/batch")
async def batch_synthesize(requests: list[TTSRequest]):
    """
    Synthesize multiple texts in batch.
    Returns all as base64 encoded.
    """
    results = []

    for req in requests:
        try:
            audio_data = synthesize_with_piper(req.text, req.language)
            if audio_data:
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                results.append({
                    "text": req.text[:50] + "..." if len(req.text) > 50 else req.text,
                    "language": req.language,
                    "success": True,
                    "audio_base64": audio_base64
                })
            else:
                results.append({
                    "text": req.text[:50] + "..." if len(req.text) > 50 else req.text,
                    "language": req.language,
                    "success": False,
                    "error": "Synthesis failed"
                })
        except Exception as e:
            results.append({
                "text": req.text[:50] + "..." if len(req.text) > 50 else req.text,
                "language": req.language,
                "success": False,
                "error": str(e)
            })

    return {"results": results}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)