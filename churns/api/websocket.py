from typing import Dict, List, Optional
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio
from datetime import datetime
import logging

from churns.api.schemas import WebSocketMessage, WSMessageType, StageProgressUpdate

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for pipeline runs"""
    
    def __init__(self):
        # Dictionary mapping run_id to list of websocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, run_id: str):
        """Accept a new WebSocket connection for a specific run"""
        await websocket.accept()
        
        if run_id not in self.active_connections:
            self.active_connections[run_id] = []
        
        self.active_connections[run_id].append(websocket)
        logger.info(f"WebSocket connected for run {run_id}. Total connections: {len(self.active_connections[run_id])}")
    
    def disconnect(self, websocket: WebSocket, run_id: str):
        """Remove a WebSocket connection"""
        if run_id in self.active_connections:
            if websocket in self.active_connections[run_id]:
                self.active_connections[run_id].remove(websocket)
                logger.info(f"WebSocket disconnected for run {run_id}. Remaining connections: {len(self.active_connections[run_id])}")
            
            # Clean up empty connection lists
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]
    
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
                "error_details": error_details or {}
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