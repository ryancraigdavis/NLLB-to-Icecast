import logging
import time
import argparse
import json
from typing import Dict, List, Optional, Callable
from attrs import define, field
import threading

from nllb_to_icecast.audio.capture import AudioCapture
from nllb_to_icecast.processing.transcription import WhisperTranscriber
from nllb_to_icecast.processing.nllb_translator import NLLBTranslator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@define
class TranslationPipeline:
    """
    Real-time church translation pipeline.
    Orchestrates: Audio Capture → Whisper Transcription → (Future: NLLB Translation) → Icecast Streaming
    """

    # Audio settings
    sample_rate: int = field(default=16000)
    device_index: Optional[int] = field(default=None)

    # Language settings
    source_language: Optional[str] = field(default=None)  # Auto-detect if None
    target_languages: List[str] = field(factory=list)  # Languages to translate to

    # Whisper settings
    whisper_model: str = field(default="large-v3")

    # Processing control
    is_running: bool = field(init=False, default=False)

    # Components
    audio_capture: Optional[AudioCapture] = field(init=False, default=None)
    transcriber: Optional[WhisperTranscriber] = field(init=False, default=None)
    translator: Optional[NLLBTranslator] = field(init=False, default=None)

    # Smart transcription handling
    last_transcription: str = field(init=False, default="")
    last_transcription_time: float = field(init=False, default=0.0)

    # Callbacks for external integration
    transcription_callback: Optional[Callable] = field(init=False, default=None)
    translation_callback: Optional[Callable] = field(init=False, default=None)

    def __attrs_post_init__(self):
        """Initialize the pipeline components."""
        logger.info("Initializing Church Translation Pipeline...")

        # Validate target languages
        if not self.target_languages:
            logger.warning("No target languages specified - transcription only mode")
        else:
            logger.info(f"Target languages: {', '.join(self.target_languages)}")

        # Initialize audio capture
        self.audio_capture = AudioCapture(
            sample_rate=self.sample_rate,
            device_index=self.device_index,
            channels=1,  # Mono for church audio
            buffer_duration=30,  # 30-second rolling buffer
        )

        # Initialize transcriber
        self.transcriber = WhisperTranscriber(
            model_size=self.whisper_model,
            language=self.source_language,
            device="auto",  # Auto-detect GPU/CPU
        )

        # Initialize NLLB translator if target languages specified
        if self.target_languages:
            logger.info("Initializing NLLB translator...")
            self.translator = NLLBTranslator(
                model_name="facebook/nllb-200-distilled-1.3B", device="auto"
            )

        logger.info("Pipeline components initialized")

    def start(
        self,
        transcription_callback: Optional[Callable] = None,
        translation_callback: Optional[Callable] = None,
    ):
        """Start the real-time translation pipeline."""

        if self.is_running:
            logger.warning("Pipeline already running!")
            return

        # Set callbacks
        self.transcription_callback = transcription_callback
        self.translation_callback = translation_callback

        try:
            logger.info("Starting translation pipeline...")

            # Start transcription processing
            self.transcriber.start_processing(callback=self._handle_transcription)

            # Start NLLB translator if available
            if self.translator:
                self.translator.start_async_processing(
                    callback=self._handle_translation_result
                )

            # Start audio capture (this connects to transcription)
            self.audio_capture.start_capture(callback=self._handle_audio)

            self.is_running = True
            logger.info("🎤 Translation pipeline is live!")
            logger.info(f"📡 Monitoring audio from: {self._get_audio_device_name()}")
            logger.info(f"🧠 Transcription model: {self.whisper_model}")
            if self.translator:
                logger.info("🌍 NLLB translator ready")
            logger.info("🔄 Ready for real-time church translation")

        except Exception as e:
            logger.error(f"Failed to start pipeline: {e}")
            self.stop()
            raise

    def _handle_audio(self, audio_data):
        """Handle audio data from AudioCapture → send to Whisper."""
        if self.transcriber and self.is_running:
            # Send audio to transcriber
            self.transcriber.process_audio_chunk(audio_data, self.sample_rate)

    def _is_transcription_duplicate_or_correction(
        self, new_text: str, timestamp: float
    ) -> tuple[bool, str]:
        """
        Check if new transcription is a duplicate or correction of previous one.
        Returns (is_duplicate, corrected_text)
        """
        if not self.last_transcription:
            return False, new_text

        # Check if this transcription came too soon after the last one (likely overlap)
        time_diff = timestamp - self.last_transcription_time
        if time_diff < 3.0:  # Less than 3 seconds apart

            # Calculate similarity using simple word overlap
            last_words = set(self.last_transcription.lower().split())
            new_words = set(new_text.lower().split())

            # If 70%+ words overlap, this is likely a correction/duplicate
            if last_words and new_words:
                overlap = len(last_words.intersection(new_words))
                similarity = overlap / max(len(last_words), len(new_words))

                if similarity > 0.7:
                    # This is likely a correction - use the longer/more complete version
                    if len(new_text) > len(self.last_transcription):
                        logger.info(f"🔧 Transcription correction detected:")
                        logger.info(f"   Previous: '{self.last_transcription}'")
                        logger.info(f"   Corrected: '{new_text}'")
                        return True, new_text  # Use the new, more complete version
                    else:
                        # New transcription is shorter, likely a duplicate
                        logger.info(f"🔄 Duplicate transcription detected, skipping")
                        return (
                            True,
                            self.last_transcription,
                        )  # Keep the previous version

        return False, new_text

    def _handle_transcription(self, transcription_result: Dict):
        """Handle transcription results from Whisper → process for translation."""

        # Extract transcription details
        text = transcription_result["text"].strip()
        language = transcription_result["language"]
        confidence = transcription_result["confidence"]
        lang_probability = transcription_result.get("language_probability", 0.0)
        rtf = transcription_result["real_time_factor"]
        timestamp = transcription_result["timestamp"]

        if not text:  # Skip empty transcriptions
            return

        # Check for duplicates or corrections
        is_duplicate, final_text = self._is_transcription_duplicate_or_correction(
            text, timestamp
        )

        if is_duplicate and final_text == self.last_transcription:
            # This is a duplicate we should skip
            return

        # Update our tracking
        self.last_transcription = final_text
        self.last_transcription_time = timestamp

        # Update the result with final text
        transcription_result["text"] = final_text
        transcription_result["is_correction"] = is_duplicate

        # Log transcription with correction info
        correction_indicator = " [CORRECTED]" if is_duplicate else ""
        logger.info(
            f"🎙️  [{language}] ({lang_probability:.2f}) {final_text}{correction_indicator}"
        )
        logger.info(
            f"⚡ Processed in {rtf:.2f}x real-time (confidence: {confidence:.2f})"
        )

        # Show language detection details
        if lang_probability < 0.7:
            logger.warning(
                f"⚠️  Low language confidence! Detected '{language}' with {lang_probability:.2f} probability"
            )

        # Call external transcription callback if provided
        if self.transcription_callback:
            try:
                self.transcription_callback(transcription_result)
            except Exception as e:
                logger.error(f"Transcription callback error: {e}")

        # Only translate if we have target languages and translator
        if self.target_languages and self.translator:
            # Send to NLLB for real translation
            self._handle_translation(transcription_result)
        elif self.target_languages:
            # Fallback to simulation if translator failed to initialize
            logger.warning("Translator not available, using simulation")
            self._simulate_translations(transcription_result)

    def _handle_translation(self, transcription_result: Dict):
        """Send transcription to NLLB for real translation."""
        if not self.translator:
            return

        text = transcription_result["text"]
        source_language = transcription_result["language"]

        # Map Whisper language codes to full language names for NLLB
        whisper_to_language = {
            "en": "english",
            "es": "spanish",
            "tr": "turkish",
            "pt": "portuguese",
            "ko": "korean",
            "zh": "chinese",
            "fa": "farsi",
            "ru": "russian",
        }

        # Convert Whisper language code to full name
        source_lang = whisper_to_language.get(source_language, source_language)

        logger.info(f"🔄 Sending to NLLB: {source_lang} → {self.target_languages}")

        # Queue translation for all target languages
        self.translator.queue_translation(
            text=text, source_lang=source_lang, target_languages=self.target_languages
        )

    def _handle_translation_result(self, translation_result: Dict):
        """Handle completed translation from NLLB."""
        source_text = translation_result["source_text"]
        translated_text = translation_result["translated_text"]
        source_lang = translation_result["source_language"]
        target_lang = translation_result["target_language"]
        processing_time = translation_result["processing_time"]
        confidence = translation_result["confidence"]

        logger.info(f"🌍 [{target_lang}] {translated_text}")
        logger.info(
            f"⚡ Translated in {processing_time:.2f}s (confidence: {confidence:.2f})"
        )

        # Call external translation callback if provided
        if self.translation_callback:
            try:
                self.translation_callback(translation_result)
            except Exception as e:
                logger.error(f"Translation callback error: {e}")

    def _simulate_translations(self, transcription_result: Dict):
        """Simulate translation results (placeholder for NLLB integration)."""
        if not self.target_languages:
            # No translations requested
            return

        original_text = transcription_result["text"]
        source_language = transcription_result["language"]

        # Only translate to specified target languages
        for target_lang in self.target_languages:
            if target_lang.lower() != source_language.lower():
                # Simulate translation result
                translation_result = {
                    "source_text": original_text,
                    "source_language": source_language,
                    "target_language": target_lang,
                    "translated_text": f"[{target_lang.upper()}] {original_text}",  # Placeholder
                    "translation_confidence": 0.95,  # Placeholder
                    "timestamp": transcription_result["timestamp"],
                }

                logger.info(
                    f"🌍 [{target_lang}] [SIMULATED] {translation_result['translated_text']}"
                )

                # Call external translation callback if provided
                if self.translation_callback:
                    try:
                        self.translation_callback(translation_result)
                    except Exception as e:
                        logger.error(f"Translation callback error: {e}")

    def stop(self):
        """Stop the translation pipeline."""
        if not self.is_running:
            return

        logger.info("Stopping translation pipeline...")
        self.is_running = False

        # Stop audio capture
        if self.audio_capture:
            self.audio_capture.stop_capture()

        # Stop transcription
        if self.transcriber:
            self.transcriber.stop_processing()

        # Stop translator
        if self.translator:
            self.translator.stop_async_processing()

        logger.info("Translation pipeline stopped")

    def get_status(self) -> Dict:
        """Get current pipeline status."""
        status = {
            "is_running": self.is_running,
            "sample_rate": self.sample_rate,
            "source_language": self.source_language,
            "target_languages": self.target_languages,
            "whisper_model": self.whisper_model,
        }

        if self.audio_capture:
            status["audio_level"] = self.audio_capture.get_audio_level()
            status["audio_device"] = self._get_audio_device_name()

        if self.transcriber:
            status["transcriber_info"] = self.transcriber.get_model_info()

        return status

    def _get_audio_device_name(self) -> str:
        """Get the name of the current audio device."""
        if not self.audio_capture:
            return "Unknown"

        try:
            import sounddevice as sd
            devices = self.audio_capture.list_audio_devices()
            device_index = self.audio_capture.device_index

            # If device_index is None, get the actual default device
            if device_index is None:
                try:
                    device_index = sd.default.device[0]  # Get default input device
                except:
                    return "System Default (Unknown)"

            # Find the device name by index
            for device in devices:
                if device["index"] == device_index:
                    device_name = device["name"]
                    # Check if this is the system default
                    try:
                        if device_index == sd.default.device[0]:
                            return f"{device_name} (System Default)"
                        else:
                            return device_name
                    except:
                        return device_name
                        
        except Exception as e:
            logger.error(f"Error getting device name: {e}")

        return "Default Device"

    def cleanup(self):
        """Clean up all resources."""
        self.stop()

        if self.audio_capture:
            self.audio_capture.cleanup()

        if self.transcriber:
            self.transcriber.cleanup()

        if self.translator:
            self.translator.cleanup()


def parse_arguments():
    """Parse command line arguments for the translation pipeline."""
    parser = argparse.ArgumentParser(
        description="Real-time Church Translation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # English to Spanish
  uv run python pipeline.py en spanish

  # Auto-detect to Turkish  
  uv run python pipeline.py auto turkish

  # English to multiple languages
  uv run python pipeline.py en spanish,turkish,farsi

  # Transcription only (no translation)
  uv run python pipeline.py en

  # Interactive mode (prompts for settings)
  uv run python pipeline.py
        """,
    )

    parser.add_argument(
        "source_language",
        nargs="?",
        default=None,
        help='Source language (e.g., "en", "es", "auto" for auto-detect, or empty for interactive)',
    )

    parser.add_argument(
        "target_languages",
        nargs="?",
        default=None,
        help='Target language(s) - single language or comma-separated list (e.g., "spanish" or "spanish,turkish,farsi")',
    )

    parser.add_argument(
        "--model",
        default="large-v3",
        choices=["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
        help="Whisper model size (default: large-v3)",
    )

    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Audio device index (use --list-devices to see options)",
    )

    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio devices and exit",
    )

    return parser.parse_args()


def list_audio_devices():
    """List available audio devices and exit."""
    from audio.capture import AudioCapture

    capture = AudioCapture()
    devices = capture.list_audio_devices()

    print("\n📡 Available Audio Input Devices:")
    print("=" * 50)
    for device in devices:
        print(f"  {device['index']:2d}: {device['name']}")
        print(
            f"      Channels: {device['channels']}, Sample Rate: {device['sample_rate']:.0f}Hz"
        )
    print("=" * 50)
    print("\nUse: --device <index> to select a specific device")


def interactive_setup():
    """Interactive setup for pipeline configuration."""
    print("\n🎵 Church Translation Pipeline - Interactive Setup")
    print("=" * 60)

    # Source language
    print("\n📥 Source Language:")
    print("  auto   - Auto-detect language")
    print("  en     - English")
    print("  es     - Spanish")
    print("  tr     - Turkish")
    print("  pt     - Portuguese")
    print("  ko     - Korean")
    print("  zh     - Chinese/Mandarin")
    print("  fa     - Farsi/Persian")
    print("  ru     - Russian")

    source = input("\nEnter source language (or 'auto'): ").strip().lower()
    if source == "" or source == "auto":
        source = None

    # Target languages
    print("\n📤 Target Languages (available):")
    available_targets = [
        "spanish",
        "turkish",
        "portuguese",
        "korean",
        "mandarin",
        "farsi",
        "russian",
    ]
    for i, lang in enumerate(available_targets, 1):
        print(f"  {i}. {lang}")

    print("\nEnter target languages:")
    print("  - Single: spanish")
    print("  - Multiple: spanish,turkish,farsi")
    print("  - None: (press enter for transcription only)")

    targets_input = input("\nTarget languages: ").strip()
    if targets_input:
        target_languages = [lang.strip() for lang in targets_input.split(",")]
    else:
        target_languages = []

    return source, target_languages


# Demo/Test function
def main():
    """Main function with command line argument support."""
    args = parse_arguments()

    # Handle special cases
    if args.list_devices:
        list_audio_devices()
        return

    # Determine source and target languages
    if args.source_language is None and args.target_languages is None:
        # Interactive mode
        source_language, target_languages = interactive_setup()
    else:
        # Command line mode
        source_language = args.source_language
        if source_language and source_language.lower() == "auto":
            source_language = None

        if args.target_languages:
            target_languages = [
                lang.strip() for lang in args.target_languages.split(",")
            ]
        else:
            target_languages = []

    # Show configuration
    print("\n🔧 Pipeline Configuration:")
    print(f"   Source Language: {source_language or 'auto-detect'}")
    print(
        f"   Target Languages: {', '.join(target_languages) if target_languages else 'none (transcription only)'}"
    )
    print(f"   Whisper Model: {args.model}")

    def transcription_handler(result):
        """Handle transcription results."""
        print(f"\n🎤 TRANSCRIPTION:")
        print(f"   [{result['language']}] {result['text']}")
        print(
            f"   Confidence: {result['confidence']:.3f} | Speed: {result['real_time_factor']:.2f}x"
        )

    def translation_handler(result):
        """Handle translation results."""
        print(f"\n🌍 TRANSLATION:")
        print(f"   {result['source_language']} → {result['target_language']}")
        print(f"   {result['translated_text']}")

    # Create pipeline with command line arguments
    pipeline = TranslationPipeline(
        whisper_model=args.model,
        source_language=source_language,
        target_languages=target_languages,
        device_index=args.device,
    )

    try:
        # Show audio device info
        print(f"\n🎤 Audio Device: {pipeline._get_audio_device_name()}")

        # Start pipeline
        pipeline.start(
            transcription_callback=transcription_handler,
            translation_callback=translation_handler,
        )

        print("\n🔴 LIVE: Pipeline is running...")
        print("💡 Speak into your microphone")
        print("⏹️  Press Ctrl+C to stop")

        # Monitor status
        while True:
            time.sleep(2)
            status = pipeline.get_status()
            audio_level = status.get("audio_level", 0)

            # Show audio level indicator
            level_bar = "█" * int(audio_level * 30)
            print(f"\r🎵 Audio: {level_bar:<30} {audio_level:.3f}", end="", flush=True)

    except KeyboardInterrupt:
        print("\n\n⏹️ Stopping pipeline...")

    finally:
        pipeline.cleanup()
        print("✅ Pipeline stopped!")


if __name__ == "__main__":
    main()
