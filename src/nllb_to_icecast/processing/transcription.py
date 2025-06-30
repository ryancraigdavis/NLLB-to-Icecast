from faster_whisper import WhisperModel
import torch
import numpy as np
from typing import Optional, Dict, List, Callable, Union
import logging
from attrs import define, field
import threading
import queue
import time

logger = logging.getLogger(__name__)

@define
class WhisperTranscriber:
    """
    Real-time Whisper transcription for church translation system.
    Uses faster-whisper for better performance and Python 3.12 compatibility.
    """
    
    model_size: str = field(default="large-v3")
    device: str = field(default="auto")  # "auto", "cuda", "cpu"
    compute_type: str = field(default="auto")  # "auto", "float16", "int8"
    language: Optional[str] = field(default=None)  # Auto-detect language
    
    # Processing settings
    chunk_length_s: float = field(default=30.0)  # Whisper's optimal window
    min_chunk_length_s: float = field(default=10.0)  # Minimum for processing
    
    # Private fields
    model: Optional[WhisperModel] = field(init=False, default=None)
    is_processing: bool = field(init=False, default=False)
    audio_queue: queue.Queue = field(init=False)
    result_queue: queue.Queue = field(init=False)
    processing_thread: Optional[threading.Thread] = field(init=False, default=None)
    transcription_callback: Optional[Callable] = field(init=False, default=None)
    
    def __attrs_post_init__(self):
        """Initialize after attrs construction."""
        # Auto-detect device and compute type
        if self.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        if self.compute_type == "auto":
            if self.device == "cuda":
                self.compute_type = "float16"  # Fast on GPU
            else:
                self.compute_type = "int8"     # Fast on CPU
        
        logger.info(f"Using device: {self.device}, compute_type: {self.compute_type}")
        
        # Initialize queues
        self.audio_queue = queue.Queue(maxsize=5)  # Limit memory usage
        self.result_queue = queue.Queue()
        
        # Load model
        self._load_model()
    
    def _load_model(self):
        """Load the faster-whisper model."""
        try:
            logger.info(f"Loading faster-whisper {self.model_size} model...")
            start_time = time.time()
            
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=None,  # Use default cache
                local_files_only=False
            )
            
            load_time = time.time() - start_time
            logger.info(f"Model loaded in {load_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Failed to load faster-whisper model: {e}")
            raise
    
    def start_processing(self, callback: Optional[Callable] = None):
        """Start the transcription processing thread."""
        if self.is_processing:
            logger.warning("Already processing!")
            return
        
        self.transcription_callback = callback
        self.is_processing = True
        
        # Start processing thread
        self.processing_thread = threading.Thread(
            target=self._process_audio_loop, 
            daemon=True
        )
        self.processing_thread.start()
        
        logger.info("Started Whisper transcription processing")
    
    def stop_processing(self):
        """Stop the transcription processing."""
        if not self.is_processing:
            return
        
        logger.info("Stopping transcription processing...")
        self.is_processing = False
        
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
        
        logger.info("Transcription processing stopped")
    
    def process_audio_chunk(self, audio_data: np.ndarray, sample_rate: int = 16000):
        """
        Add audio chunk for processing.
        Called by AudioCapture callback.
        """
        # Convert to float32 if needed
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        
        # Normalize audio
        if np.max(np.abs(audio_data)) > 0:
            audio_data = audio_data / np.max(np.abs(audio_data))
        
        # Check minimum length
        duration = len(audio_data) / sample_rate
        if duration < self.min_chunk_length_s:
            logger.debug(f"Audio chunk too short: {duration:.1f}s < {self.min_chunk_length_s}s")
            return
        
        try:
            # Add to processing queue (non-blocking)
            audio_item = {
                'audio': audio_data,
                'sample_rate': sample_rate,
                'timestamp': time.time()
            }
            self.audio_queue.put_nowait(audio_item)
            logger.debug(f"Queued audio chunk: {duration:.1f}s")
            
        except queue.Full:
            logger.warning("Audio queue full, dropping chunk")
    
    def _process_audio_loop(self):
        """Main processing loop running in separate thread."""
        logger.info("Transcription processing loop started")
        
        while self.is_processing:
            try:
                # Get audio from queue with timeout
                audio_item = self.audio_queue.get(timeout=1.0)
                
                # Process the audio
                result = self._transcribe_chunk(audio_item)
                
                if result and result['text'].strip():
                    # Add to result queue
                    self.result_queue.put(result)
                    
                    # Call callback if provided
                    if self.transcription_callback:
                        try:
                            self.transcription_callback(result)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
    
    def _transcribe_chunk(self, audio_item: Dict) -> Optional[Dict]:
        """Transcribe a single audio chunk using faster-whisper."""
        try:
            audio_data = audio_item['audio']
            sample_rate = audio_item['sample_rate']
            timestamp = audio_item['timestamp']
            
            # Resample to 16kHz if needed (Whisper's requirement)
            if sample_rate != 16000:
                # Simple resampling (for production, use proper resampling)
                target_length = int(len(audio_data) * 16000 / sample_rate)
                audio_data = np.interp(
                    np.linspace(0, len(audio_data), target_length),
                    np.arange(len(audio_data)),
                    audio_data
                )
            
            # Pad or trim to 30 seconds max (Whisper's limit)
            max_samples = 16000 * 30  # 30 seconds at 16kHz
            if len(audio_data) > max_samples:
                audio_data = audio_data[:max_samples]
            
            start_time = time.time()
            
            # Transcribe with faster-whisper
            segments, info = self.model.transcribe(
                audio_data,
                language=self.language,
                beam_size=5,
                word_timestamps=True
            )
            
            # Convert segments to list (faster-whisper returns generator)
            segments_list = list(segments)
            
            processing_time = time.time() - start_time
            audio_duration = len(audio_data) / 16000
            
            # Combine text from all segments
            full_text = " ".join([segment.text for segment in segments_list])
            
            # Calculate average confidence
            avg_confidence = 0.0
            if segments_list:
                confidences = [segment.avg_logprob for segment in segments_list if hasattr(segment, 'avg_logprob')]
                if confidences:
                    avg_confidence = float(np.exp(np.mean(confidences)))
            
            # Extract useful information
            transcription_result = {
                'text': full_text.strip(),
                'language': info.language,
                'language_probability': info.language_probability,
                'segments': [
                    {
                        'start': seg.start,
                        'end': seg.end,
                        'text': seg.text,
                        'avg_logprob': seg.avg_logprob if hasattr(seg, 'avg_logprob') else 0.0
                    }
                    for seg in segments_list
                ],
                'processing_time': processing_time,
                'audio_duration': audio_duration,
                'real_time_factor': processing_time / audio_duration,
                'timestamp': timestamp,
                'confidence': avg_confidence
            }
            
            logger.info(
                f"Transcribed {audio_duration:.1f}s in {processing_time:.2f}s "
                f"(RTF: {transcription_result['real_time_factor']:.2f}x) "
                f"Language: {transcription_result['language']} ({info.language_probability:.2f})"
            )
            
            return transcription_result
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
    
    def _calculate_avg_confidence(self, segments: List[Dict]) -> float:
        """Calculate average confidence from segments."""
        if not segments:
            return 0.0
        
        confidences = []
        for segment in segments:
            if 'avg_logprob' in segment:
                # Convert log probability to confidence (rough approximation)
                confidence = np.exp(segment['avg_logprob'])
                confidences.append(confidence)
        
        return float(np.mean(confidences)) if confidences else 0.0
    
    def get_latest_transcription(self) -> Optional[Dict]:
        """Get the latest transcription result."""
        try:
            return self.result_queue.get_nowait()
        except queue.Empty:
            return None
    
    def get_model_info(self) -> Dict:
        """Get information about the loaded model."""
        if not self.model:
            return {}
        
        info = {
            'model_size': self.model_size,
            'device': self.device,
            'compute_type': self.compute_type,
            'language': self.language
        }
        
        return info
    
    def cleanup(self):
        """Clean up resources."""
        self.stop_processing()
        # Model cleanup is handled by Python's garbage collector

# Test function
def test_transcription():
    """Test the transcription system with a dummy audio file."""
    import numpy as np
    
    print("Testing transcription system...")
    print("=" * 50)
    
    # Test both CPU and GPU if available
    devices_to_test = ["cpu"]
    if torch.cuda.is_available():
        devices_to_test.append("cuda")
    
    for device in devices_to_test:
        print(f"\n--- Testing with device: {device} ---")
        
        try:
            # Create transcriber
            transcriber = WhisperTranscriber(
                model_size="base",  # Use smaller model for testing
                device=device,
                language="en"
            )
            
            def transcription_callback(result):
                """Handle transcription results."""
                print(f"\n=== TRANSCRIPTION ({device.upper()}) ===")
                print(f"Language: {result['language']}")
                print(f"Text: {result['text']}")
                print(f"Confidence: {result['confidence']:.3f}")
                print(f"Processing: {result['processing_time']:.2f}s")
                print(f"Real-time factor: {result['real_time_factor']:.2f}x")
                print("=" * 50)
            
            # Start processing
            transcriber.start_processing(callback=transcription_callback)
            
            print("Transcriber ready! Model info:")
            info = transcriber.get_model_info()
            for key, value in info.items():
                print(f"  {key}: {value}")
            
            print(f"\nGenerating test audio for {device}...")
            
            # Generate some test audio (white noise for demo)
            sample_rate = 16000
            duration = 15  # seconds
            test_audio = np.random.random(sample_rate * duration).astype(np.float32) * 0.1
            
            # In real usage, this would be called by AudioCapture
            transcriber.process_audio_chunk(test_audio, sample_rate)
            
            print(f"Processing test audio on {device}... (this will show transcription of silence/noise)")
            
            # Wait for processing
            time.sleep(8)
            
            # Stop transcriber
            transcriber.cleanup()
            print(f"✓ {device.upper()} test completed")
            
        except Exception as e:
            print(f"✗ {device.upper()} test failed: {e}")
            if "cudnn" in str(e).lower():
                print("  → This is a cuDNN issue, install: sudo apt-get install libcudnn9-dev-cuda-12")
            continue
    
    print(f"\nTranscription testing complete!")

if __name__ == "__main__":
    test_transcription()
