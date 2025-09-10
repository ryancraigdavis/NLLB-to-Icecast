#!/usr/bin/env python3
"""
Production startup script for NLLB Translation API server.
"""
import logging
import sys
import uvicorn
from nllb_to_icecast.config.settings import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Start the production server."""
    settings = get_settings()
    
    logger.info("🚀 Starting NLLB Translation API Server (Production)")
    logger.info("=" * 60)
    logger.info(f"📡 Host: {settings.host}")
    logger.info(f"🔌 Port: {settings.port}")
    logger.info(f"🌍 Environment: {settings.environment}")
    logger.info(f"🔧 Log Level: {settings.log_level}")
    logger.info(f"🎯 CORS Origins: {settings.cors_origins}")
    logger.info("=" * 60)
    
    try:
        uvicorn.run(
            "nllb_to_icecast.api_gateway:app",
            host=settings.host,
            port=settings.port,
            reload=settings.reload,
            log_level=settings.log_level.lower(),
            access_log=True,
            use_colors=True,
            timeout_keep_alive=settings.connection_timeout
        )
    except KeyboardInterrupt:
        logger.info("\n✅ Server stopped gracefully!")
    except Exception as e:
        logger.error(f"\n❌ Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()