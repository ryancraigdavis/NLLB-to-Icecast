import logging
import time
from typing import Dict, List, Optional, Callable
from attrs import define, field
import threading
import argparse

# Import our modules (adjust paths as needed)
from nllb_to_icecast.audio.capture import AudioCapture
from nllb_to_icecast.processing.transcription import WhisperTranscriber

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
    target_languages: List[str] = field(factory=list)     # Languages to translate to
    
    # Whisper settings  
    whisper_model: str = field(default="large-v3")
    
    # Processing control
    is_running: bool = field(init=False, default=False)
    
    # Components
    audio_capture: Optional[AudioCapture] = field(init=False, default=None)
    transcriber: Optional[WhisperTranscriber] = field(init=False, default=None)
    
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
            buffer_duration=30  # 30-second rolling buffer
        )
        
        # Initialize transcriber
        self.transcriber = WhisperTranscriber(
            model_size=self.whisper_model,
            language=self.source_language,
            device="auto"  # Auto-detect GPU/CPU
        )
        
        logger.info("Pipeline components initialized")
    
    def start(self, 
              transcription_callback: Optional[Callable] = None,
              translation_callback: Optional[Callable] = None):
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
            
            # Start audio capture (this connects to transcription)
            self.audio_capture.start_capture(callback=self._handle_audio)
            
            self.is_running = True
            logger.info("🎤 Translation pipeline is live!")
            logger.info(f"📡 Monitoring audio from: {self._get_audio_device_name()}")
            logger.info(f"🧠 Transcription model: {self.whisper_model}")
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
    
    def _handle_transcription(self, transcription_result: Dict):
        """Handle transcription results from Whisper → process for translation."""
        
        # Log transcription with more detail
        text = transcription_result['text'].strip()
        language = transcription_result['language']
        confidence = transcription_result['confidence']
        lang_probability = transcription_result.get('language_probability', 0.0)
        rtf = transcription_result['real_time_factor']
        
        if text:  # Only process non-empty transcriptions
            logger.info(f"🎙️  [{language}] ({lang_probability:.2f}) {text}")
            logger.info(f"⚡ Processed in {rtf:.2f}x real-time (confidence: {confidence:.2f})")
            
            # Show language detection details
            if lang_probability < 0.7:
                logger.warning(f"⚠️  Low language confidence! Detected '{language}' with {lang_probability:.2f} probability")
            
            # Call external transcription callback if provided
            if self.transcription_callback:
                try:
                    self.transcription_callback(transcription_result)
                except Exception as e:
                    logger.error(f"Transcription callback error: {e}")
            
            # TODO: Send to NLLB for translation
            # self._handle_translation(transcription_result)
            
            # For now, simulate translation results
            self._simulate_translations(transcription_result)
    
    def _simulate_translations(self, transcription_result: Dict):
        """Simulate translation results (placeholder for NLLB integration)."""
        if not self.target_languages:
            # No translations requested
            return
            
        original_text = transcription_result['text']
        source_language = transcription_result['language']
        
        # Only translate to specified target languages
        for target_lang in self.target_languages:
            if target_lang.lower() != source_language.lower():
                # Simulate translation result
                translation_result = {
                    'source_text': original_text,
                    'source_language': source_language,
                    'target_language': target_lang,
                    'translated_text': f"[{target_lang.upper()}] {original_text}",  # Placeholder
                    'translation_confidence': 0.95,  # Placeholder
                    'timestamp': transcription_result['timestamp']
                }
                
                logger.info(f"🌍 [{target_lang}] [SIMULATED] {translation_result['translated_text']}")
                
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
        
        logger.info("Translation pipeline stopped")
    
    def get_status(self) -> Dict:
        """Get current pipeline status."""
        status = {
            'is_running': self.is_running,
            'sample_rate': self.sample_rate,
            'source_language': self.source_language,
            'target_languages': self.target_languages,
            'whisper_model': self.whisper_model
        }
        
        if self.audio_capture:
            status['audio_level'] = self.audio_capture.get_audio_level()
            status['audio_device'] = self._get_audio_device_name()
        
        if self.transcriber:
            status['transcriber_info'] = self.transcriber.get_model_info()
        
        return status
    
    def _get_audio_device_name(self) -> str:
        """Get the name of the current audio device."""
        if not self.audio_capture:
            return "Unknown"
        
        try:
            devices = self.audio_capture.list_audio_devices()
            device_index = self.audio_capture.device_index
            
            if device_index is not None:
                for device in devices:
                    if device['index'] == device_index:
                        return device['name']
        except:
            pass
        
        return "Default Device"
    
    def cleanup(self):
        """Clean up all resources."""
        self.stop()
        
        if self.audio_capture:
            self.audio_capture.cleanup()
        
        if self.transcriber:
            self.transcriber.cleanup()

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
        """
    )
    
    parser.add_argument(
        'source_language',
        nargs='?',
        default=None,
        help='Source language (e.g., "en", "es", "auto" for auto-detect, or empty for interactive)'
    )
    
    parser.add_argument(
        'target_languages',
        nargs='?', 
        default=None,
        help='Target language(s) - single language or comma-separated list (e.g., "spanish" or "spanish,turkish,farsi")'
    )
    
    parser.add_argument(
        '--model',
        default='large-v3',
        choices=['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3'],
        help='Whisper model size (default: large-v3)'
    )
    
    parser.add_argument(
        '--device',
        type=int,
        default=None,
        help='Audio device index (use --list-devices to see options)'
    )
    
    parser.add_argument(
        '--list-devices',
        action='store_true',
        help='List available audio devices and exit'
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
        print(f"      Channels: {device['channels']}, Sample Rate: {device['sample_rate']:.0f}Hz")
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
    if source == '' or source == 'auto':
        source = None
    
    # Target languages
    print("\n📤 Target Languages (available):")
    available_targets = ['spanish', 'turkish', 'portuguese', 'korean', 'mandarin', 'farsi', 'russian']
    for i, lang in enumerate(available_targets, 1):
        print(f"  {i}. {lang}")
    
    print("\nEnter target languages:")
    print("  - Single: spanish")
    print("  - Multiple: spanish,turkish,farsi") 
    print("  - None: (press enter for transcription only)")
    
    targets_input = input("\nTarget languages: ").strip()
    if targets_input:
        target_languages = [lang.strip() for lang in targets_input.split(',')]
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
        if source_language and source_language.lower() == 'auto':
            source_language = None
        
        if args.target_languages:
            target_languages = [lang.strip() for lang in args.target_languages.split(',')]
        else:
            target_languages = []
    
    # Show configuration
    print("\n🔧 Pipeline Configuration:")
    print(f"   Source Language: {source_language or 'auto-detect'}")
    print(f"   Target Languages: {', '.join(target_languages) if target_languages else 'none (transcription only)'}")
    print(f"   Whisper Model: {args.model}")
    
    def transcription_handler(result):
        """Handle transcription results."""
        print(f"\n🎤 TRANSCRIPTION:")
        print(f"   [{result['language']}] {result['text']}")
        print(f"   Confidence: {result['confidence']:.3f} | Speed: {result['real_time_factor']:.2f}x")
    
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
        device_index=args.device
    )
    
    try:
        # Show audio device info
        print(f"\n🎤 Audio Device: {pipeline._get_audio_device_name()}")
        
        # Start pipeline
        pipeline.start(
            transcription_callback=transcription_handler,
            translation_callback=translation_handler
        )
        
        print("\n🔴 LIVE: Pipeline is running...")
        print("💡 Speak into your microphone")
        print("⏹️  Press Ctrl+C to stop")
        
        # Monitor status
        while True:
            time.sleep(2)
            status = pipeline.get_status()
            audio_level = status.get('audio_level', 0)
            
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
