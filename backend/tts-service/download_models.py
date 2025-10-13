#!/usr/bin/env python3
"""
Download Piper voice models for Chinese and Spanish at Docker build time.
"""

import os
import requests
from pathlib import Path

MODELS_DIR = Path("/app/models")

# Voice models to download - using correct URLs
VOICE_MODELS = {
    "zh_CN-huayan-medium": {
        "model": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx",
        "config": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx.json",
    },
    "es_MX-ald-medium": {
        "model": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_MX/ald/medium/es_MX-ald-medium.onnx",
        "config": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_MX/ald/medium/es_MX-ald-medium.onnx.json",
    },
    "en_US-amy-low": {
        "model": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/low/en_US-amy-low.onnx",
        "config": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/low/en_US-amy-low.onnx.json",
    }
}


def download_file(url: str, destination: Path):
    """Download a file from URL to destination."""
    print(f"Downloading {destination.name}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0

    with open(destination, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total_size > 0 and downloaded % (1024 * 1024) < 8192:
                percent = (downloaded / total_size) * 100
                print(f"  Progress: {percent:.1f}%", end='\r')

    print(f"\n  ✓ Downloaded {destination.name}")


def main():
    """Download all voice models."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    for model_name, urls in VOICE_MODELS.items():
        print(f"\n📦 Setting up {model_name}")
        model_dir = MODELS_DIR / model_name
        model_dir.mkdir(parents=True, exist_ok=True)

        # Download model file
        model_path = model_dir / f"{model_name}.onnx"
        if not model_path.exists():
            download_file(urls["model"], model_path)
        else:
            print(f"  ✓ {model_name}.onnx already exists")

        # Download config file
        config_path = model_dir / f"{model_name}.onnx.json"
        if not config_path.exists():
            download_file(urls["config"], config_path)
        else:
            print(f"  ✓ {model_name}.onnx.json already exists")

    print("\n✅ All models downloaded successfully!")
    print("Available models:")
    for model_name in VOICE_MODELS.keys():
        print(f"  - {model_name}")


if __name__ == "__main__":
    main()