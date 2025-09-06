import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import time
import threading
import queue
from typing import Dict, List, Optional, Callable
import logging
from attrs import define, field

logger = logging.getLogger(__name__)

# NLLB language codes for your church languages
LANGUAGE_CODES = {
    "english": "eng_Latn",
    "spanish": "spa_Latn",
    "turkish": "tur_Latn",
    "portuguese": "por_Latn",
    "korean": "kor_Hang",
    "chinese": "zho_Hans",
    "mandarin": "zho_Hans",  # Alias for Chinese
    "farsi": "pes_Arab",
    "persian": "pes_Arab",  # Alias for Farsi
    "russian": "rus_Cyrl",
    # Common language codes
    "en": "eng_Latn",
    "es": "spa_Latn",
    "tr": "tur_Latn",
    "pt": "por_Latn",
    "ko": "kor_Hang",
    "zh": "zho_Hans",
    "fa": "pes_Arab",
    "ru": "rus_Cyrl",
}


@define
class NLLBTranslator:
    """
    NLLB (No Language Left Behind) translator for a translation system.
    Optimized for Farsi, Chinese, and Turkish translation quality.
    """

    model_name: str = field(default="facebook/nllb-200-distilled-1.3B")
    device: str = field(default="auto")  # "auto", "cuda", "cpu"

    # Translation settings
    max_length: int = field(default=512)  # Maximum tokens for translation
    batch_size: int = field(default=4)  # Batch size for multiple translations

    # Model components
    model: Optional[AutoModelForSeq2SeqLM] = field(init=False, default=None)
    tokenizer: Optional[AutoTokenizer] = field(init=False, default=None)

    # Threading for async translation
    is_processing: bool = field(init=False, default=False)
    translation_queue: queue.Queue = field(init=False)
    result_queue: queue.Queue = field(init=False)
    processing_thread: Optional[threading.Thread] = field(init=False, default=None)
    translation_callback: Optional[Callable] = field(init=False, default=None)

    def __attrs_post_init__(self):
        """Initialize the NLLB translator."""
        # Auto-detect device
        if self.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(f"Initializing NLLB translator on {self.device}")

        # Initialize queues
        self.translation_queue = queue.Queue(maxsize=10)
        self.result_queue = queue.Queue()

        # Load model
        self._load_model()

    def _load_model(self):
        """Load the NLLB model and tokenizer."""
        try:
            logger.info(f"Loading NLLB model: {self.model_name}")
            start_time = time.time()

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)

            # Try loading with safetensors first (avoids torch.load security issue)
            try:
                logger.info("Attempting to load model with safetensors format...")
                self.model = AutoModelForSeq2SeqLM.from_pretrained(
                    self.model_name,
                    torch_dtype=(
                        torch.float16 if self.device == "cuda" else torch.float32
                    ),
                    device_map="auto" if self.device == "cuda" else None,
                    low_cpu_mem_usage=True,
                    use_safetensors=True,  # Force safetensors
                    trust_remote_code=False,
                )
                logger.info("Successfully loaded model with safetensors")

            except Exception as safetensors_error:
                logger.warning(f"Safetensors loading failed: {safetensors_error}")
                logger.info("Falling back to regular model loading...")

                # Fallback to regular loading (may trigger the torch.load warning)
                self.model = AutoModelForSeq2SeqLM.from_pretrained(
                    self.model_name,
                    torch_dtype=(
                        torch.float16 if self.device == "cuda" else torch.float32
                    ),
                    device_map="auto" if self.device == "cuda" else None,
                    low_cpu_mem_usage=True,
                    trust_remote_code=False,
                )

            if self.device == "cuda" and not hasattr(self.model, "device_map"):
                self.model = self.model.to(self.device)

            load_time = time.time() - start_time
            logger.info(f"NLLB model loaded in {load_time:.2f} seconds")

            # Get model info
            model_size = sum(p.numel() for p in self.model.parameters()) / 1e9
            logger.info(f"Model size: {model_size:.1f}B parameters")

        except Exception as e:
            logger.error(f"Failed to load NLLB model: {e}")
            logger.info("Trying alternative model (600M) as fallback...")

            # Try the 600M model as fallback
            try:
                fallback_model = "facebook/nllb-200-distilled-600M"
                logger.info(f"Loading fallback model: {fallback_model}")

                self.model = AutoModelForSeq2SeqLM.from_pretrained(
                    fallback_model,
                    torch_dtype=(
                        torch.float16 if self.device == "cuda" else torch.float32
                    ),
                    device_map="auto" if self.device == "cuda" else None,
                    low_cpu_mem_usage=True,
                    use_safetensors=True,
                )

                if self.device == "cuda" and not hasattr(self.model, "device_map"):
                    self.model = self.model.to(self.device)

                logger.info(f"Successfully loaded fallback model: {fallback_model}")

            except Exception as fallback_error:
                logger.error(f"Fallback model also failed: {fallback_error}")
                raise e  # Raise original error

    def get_language_code(self, language: str) -> str:
        """Convert language name to NLLB code."""
        lang_lower = language.lower().strip()
        if lang_lower in LANGUAGE_CODES:
            return LANGUAGE_CODES[lang_lower]
        else:
            logger.warning(f"Unknown language '{language}', using English as fallback")
            return LANGUAGE_CODES["english"]

    def translate_text(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        confidence_threshold: float = 0.1,
    ) -> Dict:
        """
        Translate a single text from source to target language.

        Args:
            text: Text to translate
            source_lang: Source language (name or code)
            target_lang: Target language (name or code)
            confidence_threshold: Minimum confidence for translation

        Returns:
            Dict with translation results
        """
        try:
            # Convert language names to codes
            src_code = self.get_language_code(source_lang)
            tgt_code = self.get_language_code(target_lang)

            # Skip translation if source and target are the same
            if src_code == tgt_code:
                return {
                    "source_text": text,
                    "translated_text": text,
                    "source_language": source_lang,
                    "target_language": target_lang,
                    "confidence": 1.0,
                    "processing_time": 0.0,
                    "skipped": True,
                }

            start_time = time.time()

            # Set source language for tokenizer
            self.tokenizer.src_lang = src_code

            # Tokenize input text
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_length,
            )

            if self.device == "cuda":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Get target language token ID
            # Handle different tokenizer types
            if hasattr(self.tokenizer, "lang_code_to_id"):
                # Older tokenizer API
                forced_bos_token_id = self.tokenizer.lang_code_to_id[tgt_code]
            elif hasattr(self.tokenizer, "convert_tokens_to_ids"):
                # Newer tokenizer API
                forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(tgt_code)
            else:
                # Fallback: try to find it in the tokenizer vocab
                if tgt_code in self.tokenizer.get_vocab():
                    forced_bos_token_id = self.tokenizer.get_vocab()[tgt_code]
                else:
                    logger.warning(
                        f"Could not find token ID for {tgt_code}, using default"
                    )
                    forced_bos_token_id = None

            # Generate translation
            with torch.no_grad():
                generated_tokens = self.model.generate(
                    **inputs,
                    forced_bos_token_id=forced_bos_token_id,
                    max_length=self.max_length,
                    num_beams=4,  # Good balance of quality vs speed
                    do_sample=False,  # Deterministic for consistency
                    early_stopping=True,
                )

            # Decode translation
            translated_text = self.tokenizer.batch_decode(
                generated_tokens, skip_special_tokens=True
            )[0]

            processing_time = time.time() - start_time

            # Calculate rough confidence (placeholder - NLLB doesn't provide confidence scores)
            confidence = 0.9 if len(translated_text.strip()) > 0 else 0.0

            result = {
                "source_text": text,
                "translated_text": translated_text,
                "source_language": source_lang,
                "target_language": target_lang,
                "source_code": src_code,
                "target_code": tgt_code,
                "confidence": confidence,
                "processing_time": processing_time,
                "skipped": False,
            }

            logger.info(
                f"Translated {source_lang}→{target_lang} in {processing_time:.2f}s"
            )
            logger.debug(f"'{text}' → '{translated_text}'")

            return result

        except Exception as e:
            logger.error(f"Translation error ({source_lang}→{target_lang}): {e}")
            return {
                "source_text": text,
                "translated_text": f"[Translation Error: {str(e)}]",
                "source_language": source_lang,
                "target_language": target_lang,
                "confidence": 0.0,
                "processing_time": 0.0,
                "error": str(e),
                "skipped": False,
            }

    def start_async_processing(self, callback: Optional[Callable] = None):
        """Start asynchronous translation processing."""
        if self.is_processing:
            logger.warning("Translation processing already running!")
            return

        self.translation_callback = callback
        self.is_processing = True

        # Start processing thread
        self.processing_thread = threading.Thread(
            target=self._translation_loop, daemon=True
        )
        self.processing_thread.start()

        logger.info("Started async NLLB translation processing")

    def stop_async_processing(self):
        """Stop asynchronous translation processing."""
        if not self.is_processing:
            return

        logger.info("Stopping NLLB translation processing...")
        self.is_processing = False

        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)

        logger.info("NLLB translation processing stopped")

    def queue_translation(
        self, text: str, source_lang: str, target_languages: List[str]
    ):
        """Queue a translation for async processing."""
        try:
            translation_item = {
                "text": text,
                "source_lang": source_lang,
                "target_languages": target_languages,
                "timestamp": time.time(),
            }

            self.translation_queue.put_nowait(translation_item)
            logger.debug(f"Queued translation: {source_lang} → {target_languages}")

        except queue.Full:
            logger.warning("Translation queue full, dropping translation request")

    def _translation_loop(self):
        """Main translation processing loop."""
        logger.info("NLLB translation loop started")

        while self.is_processing:
            try:
                # Get translation request
                translation_item = self.translation_queue.get(timeout=2.0)

                text = translation_item["text"]
                source_lang = translation_item["source_lang"]
                target_languages = translation_item["target_languages"]
                timestamp = translation_item["timestamp"]

                # Translate to each target language
                results = []
                for target_lang in target_languages:
                    result = self.translate_text(text, source_lang, target_lang)
                    result["request_timestamp"] = timestamp
                    results.append(result)

                    # Call callback for each translation
                    if self.translation_callback:
                        try:
                            self.translation_callback(result)
                        except Exception as e:
                            logger.error(f"Translation callback error: {e}")

                # Store results
                self.result_queue.put(
                    {
                        "source_text": text,
                        "source_lang": source_lang,
                        "translations": results,
                        "timestamp": timestamp,
                    }
                )

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in translation loop: {e}")

    def get_latest_results(self) -> Optional[Dict]:
        """Get the latest translation results."""
        try:
            return self.result_queue.get_nowait()
        except queue.Empty:
            return None

    def get_model_info(self) -> Dict:
        """Get information about the loaded model."""
        if not self.model:
            return {}

        model_size = sum(p.numel() for p in self.model.parameters()) / 1e9

        return {
            "model_name": self.model_name,
            "device": self.device,
            "parameters": f"{model_size:.1f}B",
            "supported_languages": len(LANGUAGE_CODES),
            "max_length": self.max_length,
            "dtype": (
                str(self.model.dtype) if hasattr(self.model, "dtype") else "unknown"
            ),
        }

    def cleanup(self):
        """Clean up resources."""
        self.stop_async_processing()


# Test function
def test_nllb_translator():
    """Test the NLLB translator with content."""

    # Test sentences
    test_sentences = [
        "Hello, how are you?",
        "Carlos Sainz is a great Formula 1 driver.",
        "I hope we can take this rocket to Mars one day.",
        "Nuclear fusion could be the future of energy.",
    ]

    # Create translator
    translator = NLLBTranslator()

    # Test single translation
    print("\n🌍 NLLB Translation Test")
    print("=" * 60)

    info = translator.get_model_info()
    print("Model Info:")
    for key, value in info.items():
        print(f"  {key}: {value}")

    # Test translations to priority languages
    test_languages = ["farsi", "chinese", "turkish", "spanish"]

    for sentence in test_sentences[:2]:  # Test first 2 sentences
        print(f"\n📝 Original: {sentence}")
        print("-" * 40)

        for target_lang in test_languages:
            result = translator.translate_text(
                text=sentence, source_lang="english", target_lang=target_lang
            )

            print(f"🌍 {target_lang.title()}: {result['translated_text']}")
            print(
                f"   ⏱️  {result['processing_time']:.2f}s | Confidence: {result['confidence']:.2f}"
            )

    # Test async processing
    print(f"\n🔄 Testing Async Translation Processing...")

    def translation_callback(result):
        print(f"📨 Async: {result['source_language']} → {result['target_language']}")
        print(f"   {result['translated_text']}")

    translator.start_async_processing(callback=translation_callback)

    # Queue some translations
    translator.queue_translation(
        text="The sacrament helps us remember Jesus Christ.",
        source_lang="english",
        target_languages=["farsi", "chinese"],
    )

    # Wait for processing
    time.sleep(5)

    # Cleanup
    translator.cleanup()
    print("\n✅ NLLB Translation test complete!")


if __name__ == "__main__":
    test_nllb_translator()
