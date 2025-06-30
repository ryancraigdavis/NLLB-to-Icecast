import sounddevice as sd
import wave
import threading
import queue
import time
import numpy as np
from typing import Optional, Callable, List
import logging
from attrs import define, field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@define
class AudioCapture:
    """
    Real-time audio capture for church translation system.
    Optimized for Whisper processing with 30-second rolling buffers.
    """

    sample_rate: int = field(default=16000)  # Whisper's preferred rate
    channels: int = field(default=1)  # Mono for efficiency
    chunk_size: int = field(default=1024)  # Buffer size
    buffer_duration: int = field(default=30)  # Whisper's window
    device_index: Optional[int] = field(default=None)

    # Private fields initialized after construction
    stream: Optional[sd.InputStream] = field(init=False, default=None)
    audio_queue: queue.Queue = field(init=False)
    rolling_buffer: np.ndarray = field(init=False)
    is_recording: bool = field(init=False, default=False)
    capture_thread: Optional[threading.Thread] = field(init=False, default=None)
    transcription_callback: Optional[Callable] = field(init=False, default=None)
    buffer_size: int = field(init=False)

    def __attrs_post_init__(self):
        """Initialize after attrs construction."""
        # Calculate buffer size in frames
        self.buffer_size = self.sample_rate * self.buffer_duration

        # Initialize threading and buffering
        self.audio_queue = queue.Queue()
        self.rolling_buffer = np.array([], dtype=np.float32)

    def list_audio_devices(self) -> List[dict]:
        """List all available audio input devices."""
        devices = []
        device_list = sd.query_devices()

        for i, device_info in enumerate(device_list):
            # Convert numpy structured array to dict for easier access
            max_inputs = int(device_info["max_input_channels"])
            if max_inputs > 0:  # Input device
                devices.append(
                    {
                        "index": i,
                        "name": str(device_info["name"]),
                        "channels": max_inputs,
                        "sample_rate": float(device_info["default_samplerate"]),
                        "hostapi": int(device_info["hostapi"]),
                    }
                )
        return devices

    def get_optimal_device(self) -> Optional[int]:
        """Find the best audio input device automatically."""
        devices = self.list_audio_devices()

        # Prefer professional audio interfaces (common church equipment)
        professional_keywords = [
            "focusrite",
            "behringer",
            "presonus",
            "motu",
            "rme",
            "zoom",
            "tascam",
        ]
        for device in devices:
            name_lower = device["name"].lower()
            if any(keyword in name_lower for keyword in professional_keywords):
                logger.info(f"Found professional interface: {device['name']}")
                return device["index"]

        # Fall back to default input device
        try:
            return sd.default.device[0]  # Input device
        except:
            return None

    def start_capture(self, callback: Optional[Callable] = None):
        """Start real-time audio capture."""
        if self.is_recording:
            logger.warning("Already recording!")
            return

        # Set device if not specified
        if self.device_index is None:
            self.device_index = self.get_optimal_device()
            if self.device_index is None:
                raise RuntimeError("No suitable audio input device found!")

        # Set callback
        self.transcription_callback = callback

        try:
            # Create audio stream
            self.stream = sd.InputStream(
                device=self.device_index,
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                dtype=np.float32,
                callback=self._audio_callback,
            )

            self.is_recording = True

            # Start processing thread
            self.capture_thread = threading.Thread(
                target=self._process_audio, daemon=True
            )
            self.capture_thread.start()

            # Start the stream
            self.stream.start()

            device_info = sd.query_devices(self.device_index)
            device_name = str(device_info["name"])
            logger.info(f"Started recording from: {device_name}")
            logger.info(f"Sample Rate: {self.sample_rate}Hz, Channels: {self.channels}")

        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            self.cleanup()
            raise

    def _audio_callback(self, indata, frames, time, status):
        """SoundDevice callback for real-time audio data."""
        if status:
            logger.warning(f"Audio callback status: {status}")

        # Flatten if multi-channel and convert to mono
        if self.channels == 1 and indata.shape[1] > 1:
            audio_data = np.mean(indata, axis=1)
        else:
            audio_data = indata.flatten()

        # Add to queue for processing
        self.audio_queue.put(audio_data.copy())

    def _process_audio(self):
        """Process audio data in separate thread."""
        while self.is_recording:
            try:
                # Get audio chunk with timeout
                audio_chunk = self.audio_queue.get(timeout=1.0)

                # Add to rolling buffer
                self.rolling_buffer = np.append(self.rolling_buffer, audio_chunk)

                # Maintain buffer size (30 seconds)
                if len(self.rolling_buffer) > self.buffer_size:
                    # Remove oldest samples
                    excess = len(self.rolling_buffer) - self.buffer_size
                    self.rolling_buffer = self.rolling_buffer[excess:]

                # Check if we have enough data for processing
                if (
                    len(self.rolling_buffer) >= self.sample_rate * 10
                ):  # At least 10 seconds
                    # Trigger callback if provided
                    if self.transcription_callback:
                        # Send copy to avoid threading issues
                        self.transcription_callback(self.rolling_buffer.copy())

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing audio: {e}")

    def stop_capture(self):
        """Stop audio capture."""
        if not self.is_recording:
            return

        logger.info("Stopping audio capture...")
        self.is_recording = False

        if self.stream:
            self.stream.stop()
            self.stream.close()

        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)

        logger.info("Audio capture stopped")

    def save_buffer_to_file(self, filename: str):
        """Save current rolling buffer to WAV file for testing."""
        if len(self.rolling_buffer) == 0:
            logger.warning("No audio data to save!")
            return

        # Convert to 16-bit PCM for WAV compatibility
        audio_int16 = (self.rolling_buffer * 32767).astype(np.int16)

        with wave.open(filename, "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

        logger.info(
            f"Saved {len(self.rolling_buffer)/self.sample_rate:.1f} seconds to {filename}"
        )

    def get_audio_level(self) -> float:
        """Get current audio level (RMS) for monitoring."""
        if len(self.rolling_buffer) == 0:
            return 0.0

        # Calculate RMS of recent samples (last 0.1 seconds)
        recent_samples = int(self.sample_rate * 0.1)
        if len(self.rolling_buffer) < recent_samples:
            recent_audio = self.rolling_buffer
        else:
            recent_audio = self.rolling_buffer[-recent_samples:]

        rms = np.sqrt(np.mean(recent_audio**2))
        return float(rms)

    def cleanup(self):
        """Clean up resources."""
        self.stop_capture()


# Test/Demo function
def test_capture():
    """Test the audio capture system."""

    def transcription_callback(audio_data):
        """Dummy callback to simulate transcription processing."""
        rms = np.sqrt(np.mean(audio_data**2))
        logger.info(f"Processing {len(audio_data)/16000:.1f}s of audio, RMS: {rms:.4f}")

    # Create capture instance
    capture = AudioCapture()

    # List available devices
    print("\nAvailable Audio Devices:")
    devices = capture.list_audio_devices()
    for device in devices:
        print(f"  {device['index']}: {device['name']} ({device['channels']} channels)")

    try:
        print("\nStarting audio capture...")
        print(
            "Speak into your microphone. The system will process 30-second rolling buffers."
        )
        print("Press Ctrl+C to stop and save audio sample.")

        # Start capture with callback
        capture.start_capture(callback=transcription_callback)

        # Monitor audio levels
        while True:
            time.sleep(1)
            level = capture.get_audio_level()
            print(f"Audio level: {'█' * int(level * 50):<50} {level:.4f}")

    except KeyboardInterrupt:
        print("\nStopping capture...")
        capture.stop_capture()
        capture.save_buffer_to_file("test_capture.wav")
        print("Audio saved to test_capture.wav")

    finally:
        capture.cleanup()


if __name__ == "__main__":
    test_capture()
