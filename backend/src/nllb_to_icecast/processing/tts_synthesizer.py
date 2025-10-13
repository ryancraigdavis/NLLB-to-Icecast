"""
TTS Synthesizer using Piper for multilingual text-to-speech.
Optimized for Chinese (Mandarin) and Spanish with support for other languages.
"""

import io
import logging
import queue
import threading
import time
import wave
from pathlib import Path
from typing import Dict, List, Optional, Callable, Tuple
import numpy as np
from attrs import define, field
import subprocess
import json
import requests
import tarfile
import os

logger = logging.getLogger(__name__)


# Piper voice models optimized for quality and clarity
# Using HuggingFace URLs for direct model downloads
VOICE_MODELS = {
    # Chinese voices
    "zh": {
        "name": "zh_CN-huayan-medium",
        "model_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx",
        "config_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx.json",
        "quality": "medium",
        "sample_rate": 22050,
        "description": "Chinese (Mandarin) female voice, clear pronunciation"
    },

    # Spanish voices
    "es": {
        "name": "es_MX-ald-medium",
        "model_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_MX/ald/medium/es_MX-ald-medium.onnx",
        "config_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_MX/ald/medium/es_MX-ald-medium.onnx.json",
        "quality": "medium",
        "sample_rate": 22050,
        "description": "Spanish (Mexico) male voice, clear pronunciation"
    },

    # English voice (for testing/fallback)
    "en": {
        "name": "en_US-amy-low",
        "model_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/low/en_US-amy-low.onnx",
        "config_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/low/en_US-amy-low.onnx.json",
        "quality": "low",
        "sample_rate": 22050,
        "description": "English (US) female voice"
    }
}

# Language code mappings
LANGUAGE_TO_VOICE = {
    "chinese": "zh",
    "mandarin": "zh",
    "zh": "zh",
    "spanish": "es",
    "es": "es",
    "english": "en",
    "en": "en",
}


@define
class PiperTTSSynthesizer:
    """
    Text-to-Speech synthesizer using Piper for local, high-quality multilingual TTS.
    Optimized for church translation with focus on clarity and comprehension.
    """

    # Model settings
    models_dir: Path = field(default=Path.home() / ".cache" / "piper" / "models")
    default_voice: str = field(default="en")

    # Audio settings
    sample_rate: int = field(default=22050)
    speed: float = field(default=1.0)  # Speech speed multiplier
    pause_between_sentences: float = field(default=0.3)  # Seconds

    # Processing settings
    max_text_length: int = field(default=500)  # Max chars per chunk

    # Components
    loaded_models: Dict[str, Path] = field(factory=dict, init=False)
    is_processing: bool = field(default=False, init=False)
    tts_queue: queue.Queue = field(init=False)
    result_queue: queue.Queue = field(init=False)
    processing_thread: Optional[threading.Thread] = field(default=None, init=False)
    tts_callback: Optional[Callable] = field(default=None, init=False)
    piper_binary: Optional[str] = field(default=None, init=False)

    def __attrs_post_init__(self):
        """Initialize the TTS synthesizer."""
        logger.info("Initializing Piper TTS Synthesizer")

        # Create models directory
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # Initialize queues
        self.tts_queue = queue.Queue(maxsize=20)
        self.result_queue = queue.Queue()

        # Check if piper binary is available
        self.piper_binary = None
        if not self._check_piper_binary():
            logger.warning("Piper binary not found. TTS will not work without it.")
        else:
            logger.info(f"Using Piper binary at: {self.piper_binary}")

        logger.info("Piper TTS Synthesizer initialized")

    def _check_piper_binary(self) -> bool:
        """Check if piper binary is available in PATH or common locations."""
        # Check common locations for piper binary
        piper_paths = [
            os.path.expanduser("~/.local/bin/piper"),  # User local bin (where we have it)
            "piper",  # In PATH
            "/usr/local/bin/piper",  # System local bin
            "/usr/bin/piper",  # System bin
        ]

        for piper_path in piper_paths:
            try:
                result = subprocess.run(
                    [piper_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    logger.info(f"Piper binary found at {piper_path}")
                    self.piper_binary = piper_path
                    return True
            except (subprocess.SubprocessError, FileNotFoundError):
                continue

        return False

    def download_model(self, voice_key: str, force: bool = False) -> Path:
        """
        Download a Piper voice model if not already present.

        Args:
            voice_key: Key from VOICE_MODELS dict
            force: Force re-download even if exists

        Returns:
            Path to the model file
        """
        if voice_key not in VOICE_MODELS:
            logger.error(f"Unknown voice model: {voice_key}")
            raise ValueError(f"Unknown voice model: {voice_key}")

        voice_info = VOICE_MODELS[voice_key]
        model_name = voice_info["name"]
        model_dir = self.models_dir / model_name
        model_file = model_dir / f"{model_name}.onnx"
        config_file = model_dir / f"{model_name}.onnx.json"

        # Check if already downloaded
        if not force and model_file.exists() and config_file.exists():
            logger.info(f"Model {model_name} already exists")
            self.loaded_models[voice_key] = model_file
            return model_file

        # Download model
        logger.info(f"Downloading voice model: {model_name}")
        model_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Download model file
            logger.info(f"Downloading model file...")
            response = requests.get(voice_info["model_url"], stream=True)
            response.raise_for_status()

            with open(model_file, "wb") as f:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        if downloaded % (1024 * 1024) < 8192:  # Log every MB
                            logger.info(f"Download progress: {percent:.1f}%")

            # Download config file
            logger.info(f"Downloading config file...")
            response = requests.get(voice_info["config_url"])
            response.raise_for_status()
            with open(config_file, "wb") as f:
                f.write(response.content)

            logger.info(f"Successfully downloaded {model_name}")
            self.loaded_models[voice_key] = model_file
            return model_file

        except Exception as e:
            logger.error(f"Failed to download model {model_name}: {e}")
            # Clean up partial downloads
            if model_file.exists():
                model_file.unlink()
            if config_file.exists():
                config_file.unlink()
            raise

    def ensure_models_downloaded(self, languages: List[str]):
        """
        Ensure all required voice models are downloaded.

        Args:
            languages: List of language codes to prepare
        """
        for lang in languages:
            voice_key = LANGUAGE_TO_VOICE.get(lang.lower(), None)
            if voice_key:
                try:
                    self.download_model(voice_key)
                except Exception as e:
                    logger.error(f"Failed to download model for {lang}: {e}")

    def synthesize_speech(
        self,
        text: str,
        language: str = "en",
        output_format: str = "wav"
    ) -> Optional[bytes]:
        """
        Synthesize speech from text using Piper.

        Args:
            text: Text to synthesize
            language: Language code
            output_format: Output audio format (wav, raw)

        Returns:
            Audio data as bytes or None if failed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for TTS")
            return None

        # Get voice model for language
        voice_key = LANGUAGE_TO_VOICE.get(language.lower(), self.default_voice)

        # Ensure model is downloaded
        try:
            model_path = self.download_model(voice_key)
        except Exception as e:
            logger.error(f"Failed to get model for {language}: {e}")
            return None

        voice_info = VOICE_MODELS[voice_key]
        model_name = voice_info["name"]

        try:
            # Use Piper CLI directly (Python module not available for piper-tts package)
            return self._synthesize_with_cli(text, model_name, voice_info)
        except Exception as e:
            logger.error(f"Failed to synthesize speech: {e}")
            return None

    def _synthesize_with_cli(
        self,
        text: str,
        model_name: str,
        voice_info: Dict
    ) -> Optional[bytes]:
        """
        Synthesize using Piper CLI as fallback.
        """
        if not self.piper_binary:
            logger.error("Piper binary not found")
            return None

        try:
            model_path = self.models_dir / model_name / f"{model_name}.onnx"
            config_path = self.models_dir / model_name / f"{model_name}.onnx.json"

            # Run piper command with the correct binary path
            result = subprocess.run(
                [
                    self.piper_binary,
                    "--model", str(model_path),
                    "--config", str(config_path),
                    "--output-raw"
                ],
                input=text.encode('utf-8'),
                capture_output=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"Piper CLI error: {result.stderr.decode()}")
                return None

            # Convert raw audio to WAV
            raw_audio = result.stdout
            audio_buffer = io.BytesIO()

            with wave.open(audio_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(voice_info["sample_rate"])
                wav_file.writeframes(raw_audio)

            audio_buffer.seek(0)
            return audio_buffer.read()

        except Exception as e:
            logger.error(f"CLI synthesis failed: {e}")
            return None

    def start_async_processing(self, callback: Optional[Callable] = None):
        """Start asynchronous TTS processing."""
        if self.is_processing:
            logger.warning("TTS processing already running!")
            return

        self.tts_callback = callback
        self.is_processing = True

        # Start processing thread
        self.processing_thread = threading.Thread(
            target=self._tts_loop,
            daemon=True
        )
        self.processing_thread.start()

        logger.info("Started async Piper TTS processing")

    def stop_async_processing(self):
        """Stop asynchronous TTS processing."""
        if not self.is_processing:
            return

        logger.info("Stopping Piper TTS processing...")
        self.is_processing = False

        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)

        logger.info("Piper TTS processing stopped")

    def queue_synthesis(
        self,
        text: str,
        language: str,
        metadata: Optional[Dict] = None
    ):
        """Queue text for TTS synthesis."""
        try:
            tts_item = {
                "text": text,
                "language": language,
                "metadata": metadata or {},
                "timestamp": time.time()
            }

            self.tts_queue.put_nowait(tts_item)
            logger.debug(f"Queued TTS for {language}: {text[:50]}...")

        except queue.Full:
            logger.warning("TTS queue full, dropping synthesis request")

    def _tts_loop(self):
        """Main TTS processing loop."""
        logger.info("Piper TTS loop started")

        while self.is_processing:
            try:
                # Get TTS request
                tts_item = self.tts_queue.get(timeout=2.0)

                text = tts_item["text"]
                language = tts_item["language"]
                metadata = tts_item["metadata"]
                timestamp = tts_item["timestamp"]

                start_time = time.time()

                # Synthesize speech
                audio_data = self.synthesize_speech(text, language)

                if audio_data:
                    processing_time = time.time() - start_time

                    result = {
                        "text": text,
                        "language": language,
                        "audio_data": audio_data,
                        "audio_format": "wav",
                        "sample_rate": VOICE_MODELS.get(
                            LANGUAGE_TO_VOICE.get(language.lower(), "en"),
                            {}
                        ).get("sample_rate", 22050),
                        "processing_time": processing_time,
                        "timestamp": timestamp,
                        "metadata": metadata
                    }

                    # Store result
                    self.result_queue.put(result)

                    # Call callback if provided
                    if self.tts_callback:
                        try:
                            self.tts_callback(result)
                        except Exception as e:
                            logger.error(f"TTS callback error: {e}")

                    logger.info(
                        f"Synthesized {language} speech in {processing_time:.2f}s "
                        f"({len(text)} chars -> {len(audio_data)} bytes)"
                    )
                else:
                    logger.error(f"Failed to synthesize speech for {language}")

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in TTS loop: {e}")

    def get_latest_results(self) -> Optional[Dict]:
        """Get the latest TTS results."""
        try:
            return self.result_queue.get_nowait()
        except queue.Empty:
            return None

    def cleanup(self):
        """Clean up resources."""
        self.stop_async_processing()


def test_piper_tts():
    """Test the Piper TTS synthesizer."""
    import tempfile
    import sounddevice as sd

    logger.info("Testing Piper TTS Synthesizer")

    # Create synthesizer
    synthesizer = PiperTTSSynthesizer()

    # Test sentences
    test_cases = [
        ("Hello, this is a test of the text to speech system.", "en"),
        ("Hola, esta es una prueba del sistema de texto a voz.", "es"),
        ("你好，这是文字转语音系统的测试。", "zh"),
    ]

    print("\nPiper TTS Test")
    print("=" * 60)

    for text, language in test_cases:
        print(f"\nLanguage: {language}")
        print(f"Text: {text}")

        # Synthesize
        audio_data = synthesizer.synthesize_speech(text, language)

        if audio_data:
            print(f"Generated {len(audio_data)} bytes of audio")

            # Save to temp file for playback
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name

            print(f"Saved to: {temp_path}")

            # Optionally play audio (if sounddevice available)
            try:
                import wave
                with wave.open(temp_path, 'rb') as wf:
                    frames = wf.readframes(wf.getnframes())
                    audio_array = np.frombuffer(frames, dtype=np.int16)
                    sd.play(audio_array, wf.getframerate())
                    sd.wait()
                print("Audio played successfully")
            except Exception as e:
                print(f"Could not play audio: {e}")
        else:
            print("Failed to generate audio")

    # Test async processing
    print("\nTesting async processing...")

    def tts_callback(result):
        print(f"Async TTS completed for {result['language']}: {len(result['audio_data'])} bytes")

    synthesizer.start_async_processing(callback=tts_callback)

    # Queue some synthesis requests
    synthesizer.queue_synthesis(
        "This is an asynchronous test.",
        "en",
        {"test": True}
    )
    synthesizer.queue_synthesis(
        "这是异步测试。",
        "zh",
        {"test": True}
    )

    # Wait for processing
    time.sleep(10)

    # Cleanup
    synthesizer.cleanup()
    print("\nPiper TTS test complete!")


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Run test
    test_piper_tts()