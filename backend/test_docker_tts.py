#!/usr/bin/env python3
"""
Test script for Docker-based Piper TTS service.
Run this after starting the Docker container with:
  docker-compose -f docker-compose.tts.yml up tts
"""

import requests
import base64
import json
from pathlib import Path
import time


def test_tts_service(host: str = "http://localhost:8001"):
    """Test the TTS service with various languages."""

    print("=" * 60)
    print("Testing Docker TTS Service")
    print(f"Host: {host}")
    print("=" * 60)

    # Check if service is running
    try:
        response = requests.get(f"{host}/")
        print(f"\n✅ Service Status: {response.json()}")
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to TTS service at {host}")
        print("Make sure to run: docker-compose -f docker-compose.tts.yml up tts")
        return

    # Check available models
    response = requests.get(f"{host}/models")
    print(f"\n📦 Available Models:")
    models = response.json()["models"]
    for lang, info in models.items():
        status = "✓" if info["exists"] else "✗"
        print(f"  {status} {lang}: {info['name']}")

    # Test sentences for church content
    test_cases = [
        {
            "text": "We are grateful to gather together on this Sabbath day.",
            "language": "en",
            "description": "English"
        },
        {
            "text": "Estamos agradecidos de reunirnos en este día de reposo.",
            "language": "es",
            "description": "Spanish"
        },
        {
            "text": "我们很感激能在这个安息日聚集在一起。",
            "language": "zh",
            "description": "Chinese (Mandarin)"
        }
    ]

    # Create output directory
    output_dir = Path("tts-test-output")
    output_dir.mkdir(exist_ok=True)

    print(f"\n🔊 Testing TTS Synthesis:")
    print(f"Output directory: {output_dir.absolute()}")

    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. {test['description']}:")
        print(f"   Text: {test['text']}")

        start_time = time.time()

        # Test base64 response
        response = requests.post(
            f"{host}/synthesize",
            json={
                "text": test["text"],
                "language": test["language"],
                "output_format": "base64"
            }
        )

        if response.status_code == 200:
            data = response.json()
            synthesis_time = time.time() - start_time

            # Decode and save audio
            audio_data = base64.b64decode(data["audio_base64"])
            output_file = output_dir / f"test_{i}_{test['language']}.wav"

            with open(output_file, "wb") as f:
                f.write(audio_data)

            print(f"   ✅ Success!")
            print(f"   Time: {synthesis_time:.2f}s")
            print(f"   Duration: {data.get('duration_seconds', 0):.1f}s")
            print(f"   Saved: {output_file}")
        else:
            print(f"   ❌ Failed: {response.text}")

    # Test streaming
    print(f"\n🔄 Testing Streaming API:")
    response = requests.post(
        f"{host}/synthesize/stream",
        json={
            "text": "This is a streaming test.",
            "language": "en"
        },
        stream=True
    )

    if response.status_code == 200:
        output_file = output_dir / "test_stream.wav"
        with open(output_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"   ✅ Streaming works! Saved: {output_file}")
    else:
        print(f"   ❌ Streaming failed")

    # Test batch processing
    print(f"\n📦 Testing Batch Processing:")
    batch_request = [
        {"text": "First message.", "language": "en"},
        {"text": "Segundo mensaje.", "language": "es"},
        {"text": "第三条消息。", "language": "zh"}
    ]

    response = requests.post(f"{host}/batch", json=batch_request)
    if response.status_code == 200:
        results = response.json()["results"]
        for r in results:
            status = "✅" if r["success"] else "❌"
            print(f"   {status} {r['language']}: {r['text']}")
    else:
        print(f"   ❌ Batch processing failed")

    print("\n" + "=" * 60)
    print("✅ TTS Service Test Complete!")
    print(f"Audio files saved to: {output_dir.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    import sys

    host = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
    test_tts_service(host)