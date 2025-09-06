#!/usr/bin/env python3
"""
Simple script to run the NLLB Translation API server.
"""
import argparse
import sys
from nllb_to_icecast.api_gateway import run_server

def main():
    parser = argparse.ArgumentParser(description="Run NLLB Translation API server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    
    args = parser.parse_args()
    
    print("🚀 Starting NLLB Translation API Server")
    print("=" * 50)
    print(f"📡 Server URL: http://{args.host}:{args.port}")
    print(f"🔌 WebSocket: ws://{args.host}:{args.port}/ws") 
    print(f"📖 API Docs: http://{args.host}:{args.port}/docs")
    print("=" * 50)
    print()
    
    try:
        run_server(host=args.host, port=args.port, reload=args.reload)
    except KeyboardInterrupt:
        print("\n✅ Server stopped!")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()