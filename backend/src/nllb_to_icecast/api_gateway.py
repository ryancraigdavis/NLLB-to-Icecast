import asyncio
import json
import logging
from typing import Dict, List, Optional, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import threading

from nllb_to_icecast.audio_translation_orchestrator import TranslationPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for REST API
class PipelineConfig(BaseModel):
    source_language: Optional[str] = None
    target_languages: List[str] = []
    whisper_model: str = "large-v3"
    device_index: Optional[int] = None
    sample_rate: int = 16000

class PipelineStatus(BaseModel):
    is_running: bool
    source_language: Optional[str]
    target_languages: List[str]
    whisper_model: str
    audio_device: Optional[str] = None
    audio_level: Optional[float] = None

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict] = None

# WebSocket event types
class WebSocketEvent(BaseModel):
    type: str  # "transcription", "translation", "status", "error"
    data: Dict

class ConnectionManager:
    """Manages WebSocket connections for real-time streaming."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")
    
    async def broadcast(self, event: WebSocketEvent):
        """Broadcast an event to all connected clients."""
        if not self.active_connections:
            return
        
        message = event.model_dump_json()
        disconnected = set()
        
        for connection in self.active_connections.copy():
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket client: {e}")
                disconnected.add(connection)
        
        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

# Global instances
app = FastAPI(title="NLLB Translation API", version="0.1.0")
connection_manager = ConnectionManager()
pipeline: Optional[TranslationPipeline] = None
pipeline_lock = threading.Lock()

# Event loop reference for thread-safe async calls
main_loop: Optional[asyncio.AbstractEventLoop] = None

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread-safe async broadcasting
def schedule_broadcast(event: WebSocketEvent):
    """Schedule an async broadcast from a sync context."""
    if main_loop and not main_loop.is_closed():
        asyncio.run_coroutine_threadsafe(
            connection_manager.broadcast(event), 
            main_loop
        )

# WebSocket callback handlers
def transcription_callback(result: Dict):
    """Handle transcription results and broadcast to WebSocket clients."""
    event = WebSocketEvent(
        type="transcription",
        data={
            "text": result["text"],
            "language": result["language"],
            "confidence": result["confidence"],
            "language_probability": result.get("language_probability", 0.0),
            "real_time_factor": result["real_time_factor"],
            "timestamp": result["timestamp"],
            "is_correction": result.get("is_correction", False)
        }
    )
    
    # Schedule broadcast from thread-safe context
    schedule_broadcast(event)

def translation_callback(result: Dict):
    """Handle translation results and broadcast to WebSocket clients."""
    event = WebSocketEvent(
        type="translation",
        data={
            "source_text": result["source_text"],
            "translated_text": result["translated_text"],
            "source_language": result["source_language"],
            "target_language": result["target_language"],
            "confidence": result["confidence"],
            "processing_time": result["processing_time"]
        }
    )
    
    # Schedule broadcast from thread-safe context
    schedule_broadcast(event)

async def broadcast_status(status_data: Dict):
    """Broadcast status updates to WebSocket clients."""
    event = WebSocketEvent(type="status", data=status_data)
    await connection_manager.broadcast(event)

async def broadcast_error(error_message: str):
    """Broadcast error messages to WebSocket clients."""
    event = WebSocketEvent(type="error", data={"message": error_message})
    await connection_manager.broadcast(event)

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time translation streaming."""
    await connection_manager.connect(websocket)
    
    try:
        # Send current status on connection
        if pipeline:
            status = pipeline.get_status()
            await websocket.send_text(
                WebSocketEvent(type="status", data=status).model_dump_json()
            )
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages (could be used for client commands in future)
                data = await websocket.receive_text()
                # For now, just echo back or ignore
                logger.info(f"Received WebSocket message: {data}")
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await broadcast_error(f"WebSocket error: {str(e)}")
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        connection_manager.disconnect(websocket)

# REST API endpoints
@app.get("/audio/devices")
async def list_audio_devices():
    """List available audio input devices."""
    try:
        from nllb_to_icecast.audio.capture import AudioCapture
        capture = AudioCapture()
        devices = capture.list_audio_devices()
        
        return ApiResponse(
            success=True,
            message="Audio devices retrieved successfully",
            data={"devices": devices}
        )
    except Exception as e:
        logger.error(f"Error listing audio devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/pipeline/start")
async def start_pipeline(config: PipelineConfig):
    """Start the translation pipeline with the given configuration."""
    global pipeline
    
    with pipeline_lock:
        if pipeline and pipeline.is_running:
            raise HTTPException(status_code=400, detail="Pipeline is already running")
        
        try:
            # Create new pipeline instance
            pipeline = TranslationPipeline(
                sample_rate=config.sample_rate,
                device_index=config.device_index,
                source_language=config.source_language,
                target_languages=config.target_languages,
                whisper_model=config.whisper_model
            )
            
            # Start pipeline in a separate thread to avoid blocking
            def start_pipeline_thread():
                try:
                    pipeline.start(
                        transcription_callback=transcription_callback,
                        translation_callback=translation_callback
                    )
                except Exception as e:
                    logger.error(f"Pipeline error: {e}")
                    asyncio.create_task(broadcast_error(f"Pipeline error: {str(e)}"))
            
            thread = threading.Thread(target=start_pipeline_thread, daemon=True)
            thread.start()
            
            # Wait a bit to see if startup succeeds
            await asyncio.sleep(1)
            
            if not pipeline.is_running:
                raise Exception("Failed to start pipeline")
            
            # Broadcast status update
            status = pipeline.get_status()
            await broadcast_status(status)
            
            return ApiResponse(
                success=True,
                message="Translation pipeline started successfully",
                data=status
            )
            
        except Exception as e:
            logger.error(f"Failed to start pipeline: {e}")
            await broadcast_error(f"Failed to start pipeline: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/pipeline/stop")
async def stop_pipeline():
    """Stop the translation pipeline."""
    global pipeline
    
    with pipeline_lock:
        if not pipeline:
            raise HTTPException(status_code=400, detail="No pipeline instance")
        
        if not pipeline.is_running:
            raise HTTPException(status_code=400, detail="Pipeline is not running")
        
        try:
            pipeline.stop()
            
            # Broadcast status update
            status = pipeline.get_status()
            await broadcast_status(status)
            
            return ApiResponse(
                success=True,
                message="Translation pipeline stopped successfully",
                data=status
            )
            
        except Exception as e:
            logger.error(f"Failed to stop pipeline: {e}")
            await broadcast_error(f"Failed to stop pipeline: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/pipeline/status")
async def get_pipeline_status():
    """Get current pipeline status."""
    global pipeline
    
    if not pipeline:
        return ApiResponse(
            success=True,
            message="No pipeline instance",
            data={"is_running": False}
        )
    
    try:
        status = pipeline.get_status()
        return ApiResponse(
            success=True,
            message="Pipeline status retrieved successfully",
            data=status
        )
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "NLLB Translation API"}

# Startup/shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    global main_loop
    main_loop = asyncio.get_event_loop()
    logger.info("🚀 NLLB Translation API started")
    logger.info("📡 WebSocket endpoint: /ws")
    logger.info("🔧 REST API endpoints: /pipeline/*, /audio/devices")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global pipeline
    
    logger.info("🛑 Shutting down NLLB Translation API")
    
    if pipeline:
        try:
            pipeline.cleanup()
        except Exception as e:
            logger.error(f"Error during pipeline cleanup: {e}")

def run_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Run the FastAPI server."""
    logger.info(f"Starting server on http://{host}:{port}")
    uvicorn.run("nllb_to_icecast.api_gateway:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    run_server(reload=True)