from enum import Enum
from typing import Dict, List, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio
from datetime import datetime
import logging
from pydantic import BaseModel

from churns.api.schemas import WebSocketMessage, WSMessageType, StageProgressUpdate
from churns.api.database import RunStatus, StageStatus

logger = logging.getLogger(__name__)


class WSMessageType(str, Enum):
    """WebSocket message types"""
    STAGE_UPDATE = "stage_update"
    RUN_COMPLETE = "run_complete"
    RUN_ERROR = "run_error"
    STATUS_UPDATE = "status_update"
    PING = "ping"
    # Caption generation events
    CAPTION_UPDATE = "caption_update"
    CAPTION_COMPLETE = "caption_complete"
    CAPTION_ERROR = "caption_error"


class WebSocketMessage(BaseModel):
    """WebSocket message format"""
    type: WSMessageType
    run_id: str
    data: dict


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.connection_run_ids: Dict[WebSocket, str] = {}
    
    async def connect(self, websocket: WebSocket, run_id: str):
        """Connect a new WebSocket client"""
        await websocket.accept()
        
        if run_id not in self.active_connections:
            self.active_connections[run_id] = set()
        self.active_connections[run_id].add(websocket)
        self.connection_run_ids[websocket] = run_id
        
        logger.info(f"New WebSocket connection for run {run_id}")
    
    def disconnect(self, websocket: WebSocket, run_id: str):
        """Disconnect a WebSocket client"""
        if run_id in self.active_connections:
            self.active_connections[run_id].discard(websocket)
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]
        
        if websocket in self.connection_run_ids:
            del self.connection_run_ids[websocket]
        
        logger.info(f"WebSocket disconnected for run {run_id}")
    
    async def send_message_to_run(self, run_id: str, message: WebSocketMessage):
        """Send a message to all connections for a specific run"""
        if run_id not in self.active_connections:
            logger.debug(f"No active connections for run {run_id}")
            return
        
        # Convert message to JSON
        message_data = message.model_dump_json()
        
        # Send to all connections for this run
        disconnected_connections = []
        for connection in self.active_connections[run_id]:
            try:
                await connection.send_text(message_data)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket for run {run_id}: {e}")
                disconnected_connections.append(connection)
        
        # Clean up disconnected connections
        for connection in disconnected_connections:
            self.disconnect(connection, run_id)
    
    async def send_stage_update(self, run_id: str, stage_update: StageProgressUpdate):
        """Send a stage progress update"""
        message = WebSocketMessage(
            type=WSMessageType.STAGE_UPDATE,
            run_id=run_id,
            data=stage_update.model_dump()
        )
        await self.send_message_to_run(run_id, message)
    
    async def send_run_complete(self, run_id: str, final_results: Optional[dict] = None):
        """Send run completion notification"""
        message = WebSocketMessage(
            type=WSMessageType.RUN_COMPLETE,
            run_id=run_id,
            data=final_results or {}
        )
        await self.send_message_to_run(run_id, message)
    
    async def send_run_error(self, run_id: str, error_message: str, error_details: Optional[dict] = None):
        """Send run error notification"""
        message = WebSocketMessage(
            type=WSMessageType.RUN_ERROR,
            run_id=run_id,
            data={
                "error_message": error_message,
                "error_details": error_details or {},
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        await self.send_message_to_run(run_id, message)
    
    async def send_status_update(self, run_id: str, status: RunStatus, is_active: bool, error_message: Optional[str] = None):
        """Send run status update"""
        message = WebSocketMessage(
            type=WSMessageType.STATUS_UPDATE,
            run_id=run_id,
            data={
                "status": status,
                "is_active": is_active,
                "error_message": error_message,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        await self.send_message_to_run(run_id, message)
    
    async def ping_connections(self, run_id: str):
        """Send ping to keep connections alive"""
        message = WebSocketMessage(
            type=WSMessageType.PING,
            run_id=run_id,
            data={"timestamp": datetime.utcnow().isoformat()}
        )
        await self.send_message_to_run(run_id, message)
    
    def get_connection_count(self, run_id: str) -> int:
        """Get number of active connections for a run"""
        return len(self.active_connections.get(run_id, []))
    
    def get_all_active_runs(self) -> List[str]:
        """Get list of all runs with active connections"""
        return list(self.active_connections.keys())


# Global connection manager instance
connection_manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, run_id: str):
    """WebSocket endpoint handler"""
    await connection_manager.connect(websocket, run_id)
    
    try:
        # Send initial ping to confirm connection
        await connection_manager.ping_connections(run_id)
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (for future interactive features)
                data = await websocket.receive_text()
                
                # For now, just echo back (could add commands like pause/cancel)
                try:
                    client_message = json.loads(data)
                    logger.debug(f"Received client message for run {run_id}: {client_message}")
                    
                    # Handle client commands if needed
                    if client_message.get("type") == "ping":
                        await connection_manager.ping_connections(run_id)
                        
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received from client for run {run_id}: {data}")
                    
            except asyncio.TimeoutError:
                # Send periodic pings to keep connection alive
                await connection_manager.ping_connections(run_id)
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for run {run_id}")
    except Exception as e:
        logger.error(f"WebSocket error for run {run_id}: {e}")
    finally:
        connection_manager.disconnect(websocket, run_id) 