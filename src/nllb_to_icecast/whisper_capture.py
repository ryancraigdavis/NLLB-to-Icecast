import numpy as np
import whisper
import asyncio
import sounddevice as sd
from typing import Dict, List, Any, Optional
from attrs import field, define, Factory
from loguru import logger


@define
class WhisperTranscriptionService:
    """Service for transcribing audio using Whisper."""

    device: str = "cuda"
    model: whisper.Whisper = field(init=False)
    sample_rate: int = 16000
    is_processing: bool = False
    audio_buffer: list = Factory(list)
    buffer_duration: float = 0.0
    chunk_duration: float = 0.5
    audio_device: Optional[int] = None

    def __attrs_post_init__(self):
        """Initialize Whisper model for transcription."""
        logger.info(f"Initializing Whisper model Turbo on {self.device}")

        self.model = whisper.load_model("turbo", device=self.device)
        logger.info(f"Whisper model loaded successfully")

    def list_audio_devices(self) -> List[Dict]:
        """List all available audio input devices."""
        devices = sd.query_devices()
        input_devices = [
            {
                "index": i,
                "name": device.get("name", "Unknown"),
                "channels": device.get("max_input_channels", 0),
            }
            for i, device in enumerate(devices)
            if device.get("max_input_channels", 0) > 0
        ]
        return input_devices

    def select_audio_device(self, device_id: Optional[int] = None):
        """Select an audio device to use for recording."""
        if device_id is None:
            # Use default device
            self.audio_device = sd.default.device[0]
            device_info = sd.query_devices(self.audio_device)
        else:
            self.audio_device = device_id
            device_info = sd.query_devices(device_id)

        logger.info(
            f"Selected audio device: {device_info['name']} (ID: {self.audio_device})"
        )

    async def start_listening(self, duration=None):
        """Start listening on the selected audio device.

        Args:
            duration: Optional duration in seconds to listen for. If None, will listen indefinitely.
        """
        if self.audio_device is None:
            self.select_audio_device()

        logger.info(f"Starting audio capture from device {self.audio_device}")

        def audio_callback(indata, frames, time, status):
            """Callback for audio data from sounddevice."""
            if status:
                logger.warning(f"Audio status: {status}")

            # Convert to float32 if not already
            audio_data = indata.copy().astype(np.float32).flatten()
            # Process the audio data asynchronously
            asyncio.create_task(self.process_audio_chunk(audio_data.tobytes()))

        # Start the recording stream
        with sd.InputStream(
            device=self.audio_device,
            channels=1,
            samplerate=self.sample_rate,
            callback=audio_callback,
            blocksize=int(self.sample_rate * self.chunk_duration),
        ):
            try:
                # Wait for the specified duration or indefinitely
                if duration:
                    await asyncio.sleep(duration)
                else:
                    # Run forever until interrupted
                    await asyncio.Event().wait()
            except asyncio.CancelledError:
                logger.info("Audio capture cancelled")
            finally:
                # Process any remaining audio
                await self.finalize_processing()

    async def process_audio_chunk(self, audio_chunk: bytes) -> Optional[Dict[str, Any]]:
        """Process an audio chunk from WebSocket."""
        # Convert bytes to numpy array (assuming float32 format)
        try:
            audio_np = np.frombuffer(audio_chunk, dtype=np.float32)

            # Add to buffer
            self.audio_buffer.append(audio_np)
            chunk_duration = len(audio_np) / self.sample_rate
            self.buffer_duration += chunk_duration

            # Only process when we have enough audio (3+ seconds)
            if self.buffer_duration >= 3.0 and not self.is_processing:
                return await self._process_buffer()

            return None
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            return None

    async def finalize_processing(self) -> Optional[Dict[str, Any]]:
        """Process any remaining audio in the buffer."""
        if self.audio_buffer and not self.is_processing:
            return await self._process_buffer()
        return None

    async def _process_buffer(self) -> Dict[str, Any]:
        """Process accumulated audio buffer with Whisper."""
        self.is_processing = True

        try:
            # Combine all audio chunks
            combined_audio = np.concatenate(self.audio_buffer)

            # Whisper processing is CPU/GPU intensive, run in a thread pool
            result = await asyncio.to_thread(self.run_whisper_inference, combined_audio)

            # Reset buffer
            self.audio_buffer = []
            self.buffer_duration = 0.0

            return result
        except Exception as e:
            logger.error(f"Error in Whisper processing: {e}")
            return {"error": str(e), "text": "", "detected_language": ""}
        finally:
            self.is_processing = False

    def run_whisper_inference(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Run Whisper inference (called in a thread pool).

        Args:
            audio_data: Audio as numpy array

        Returns:
            Dictionary with transcription results
        """
        # Perform inference
        result = self.model.transcribe(
            audio_data,
            # Config options for better performance in meeting settings
            language=None,  # Auto-detect language
            task="transcribe",
            fp16=self.device == "cuda",  # Use fp16 on GPU for speed
            verbose=False,
        )

        return {
            "text": result["text"].strip(),
            "detected_language": result["language"],
            "segments": result["segments"],
            "confidence": result.get("confidence", 0.0),
        }


if __name__ == "__main__":
    # Example usage
    async def main():
        service = WhisperTranscriptionService()

        # List available audio devices
        devices = service.list_audio_devices()
        print("Available input devices:")
        for device in devices:
            print(
                f"{device['index']}: {device['name']} (channels: {device['channels']})"
            )

        # Select a device (or use default)
        service.select_audio_device()

        # Start listening from microphone
        print("Listening from microphone. Press Ctrl+C to stop...")
        try:
            # Listen for 30 seconds (or remove duration parameter to listen indefinitely)
            await service.start_listening(duration=30)
        except KeyboardInterrupt:
            print("Stopping...")

    asyncio.run(main())
