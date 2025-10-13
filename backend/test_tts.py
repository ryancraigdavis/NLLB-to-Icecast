#!/usr/bin/env python3
"""
Test script for Piper TTS synthesis with English, Chinese, and Spanish.
"""

import sys
import os
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from nllb_to_icecast.processing.tts_synthesizer import PiperTTSSynthesizer

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_tts_synthesis():
    """Test TTS synthesis for all three languages."""

    print("\n" + "=" * 60)
    print("Testing Piper TTS Synthesis")
    print("=" * 60)

    # Create synthesizer
    synthesizer = PiperTTSSynthesizer()

    # Test cases for church/sacrament meeting content
    test_cases = [
        {
            "language": "en",
            "text": "We are grateful to gather together on this Sabbath day to worship and renew our covenants.",
            "description": "English - Church greeting"
        },
        {
            "language": "es",
            "text": "Estamos agradecidos de reunirnos en este día de reposo para adorar y renovar nuestros convenios.",
            "description": "Spanish - Church greeting (translated)"
        },
        {
            "language": "zh",
            "text": "我们很感激能在这个安息日聚集在一起崇拜并更新我们的圣约。",
            "description": "Chinese - Church greeting (translated)"
        }
    ]

    # Create output directory for audio files
    output_dir = Path("tts_output")
    output_dir.mkdir(exist_ok=True)

    print(f"\nOutput directory: {output_dir.absolute()}\n")

    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test['description']}")
        print(f"Language: {test['language']}")
        print(f"Text: {test['text']}")
        print("-" * 40)

        start_time = time.time()

        # Synthesize speech
        audio_data = synthesizer.synthesize_speech(
            text=test['text'],
            language=test['language']
        )

        synthesis_time = time.time() - start_time

        if audio_data:
            # Save to file
            output_file = output_dir / f"test_{i}_{test['language']}.wav"
            with open(output_file, 'wb') as f:
                f.write(audio_data)

            file_size_kb = len(audio_data) / 1024
            print(f"✓ Success!")
            print(f"  - Synthesis time: {synthesis_time:.2f} seconds")
            print(f"  - Audio size: {file_size_kb:.1f} KB")
            print(f"  - Saved to: {output_file}")

            # Estimate duration (rough calculation for WAV)
            # WAV at 22050 Hz, 16-bit mono ≈ 44100 bytes/second
            estimated_duration = file_size_kb * 1024 / 44100
            print(f"  - Estimated duration: {estimated_duration:.1f} seconds")
        else:
            print(f"✗ Failed to synthesize speech")

    # Test async processing
    print("\n" + "=" * 60)
    print("Testing Async TTS Processing")
    print("=" * 60)

    results = []

    def tts_callback(result):
        """Callback for async TTS completion."""
        results.append(result)
        lang = result['language']
        size = len(result['audio_data']) / 1024
        print(f"  ✓ Async TTS completed for {lang}: {size:.1f} KB in {result['processing_time']:.2f}s")

    # Start async processing
    synthesizer.start_async_processing(callback=tts_callback)

    # Queue multiple synthesis requests
    print("\nQueueing async synthesis requests...")

    synthesizer.queue_synthesis(
        "The sacrament helps us remember Jesus Christ and His sacrifice for us.",
        "en",
        {"purpose": "sacrament_talk"}
    )

    synthesizer.queue_synthesis(
        "El sacramento nos ayuda a recordar a Jesucristo y Su sacrificio por nosotros.",
        "es",
        {"purpose": "sacrament_talk"}
    )

    synthesizer.queue_synthesis(
        "圣餐帮助我们记住耶稣基督和他为我们所做的牺牲。",
        "zh",
        {"purpose": "sacrament_talk"}
    )

    # Wait for processing
    print("Processing...")
    time.sleep(10)

    # Save async results
    print(f"\nAsync results: {len(results)} completed")
    for i, result in enumerate(results, 1):
        output_file = output_dir / f"async_{i}_{result['language']}.wav"
        with open(output_file, 'wb') as f:
            f.write(result['audio_data'])
        print(f"  - Saved: {output_file}")

    # Cleanup
    synthesizer.cleanup()

    print("\n" + "=" * 60)
    print(f"Test complete! Audio files saved to: {output_dir.absolute()}")
    print("=" * 60)
    print("\nYou can play the audio files with:")
    print("  ffplay <filename>  # If ffmpeg is installed")
    print("  aplay <filename>   # On Linux")
    print("  afplay <filename>  # On macOS")


if __name__ == "__main__":
    test_tts_synthesis()