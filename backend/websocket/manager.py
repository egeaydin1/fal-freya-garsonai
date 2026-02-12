from fastapi import WebSocket
from typing import Dict, Set
import json

class ConnectionManager:
    def __init__(self):
        # Store active connections by table_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Store restaurant connections for order updates
        self.restaurant_connections: Dict[int, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, table_id: str):
        await websocket.accept()
        if table_id not in self.active_connections:
            self.active_connections[table_id] = set()
        self.active_connections[table_id].add(websocket)
    
    async def connect_restaurant(self, websocket: WebSocket, restaurant_id: int):
        await websocket.accept()
        if restaurant_id not in self.restaurant_connections:
            self.restaurant_connections[restaurant_id] = set()
        self.restaurant_connections[restaurant_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, table_id: str):
        if table_id in self.active_connections:
            self.active_connections[table_id].discard(websocket)
            if not self.active_connections[table_id]:
                del self.active_connections[table_id]
    
    def disconnect_restaurant(self, websocket: WebSocket, restaurant_id: int):
        if restaurant_id in self.restaurant_connections:
            self.restaurant_connections[restaurant_id].discard(websocket)
            if not self.restaurant_connections[restaurant_id]:
                del self.restaurant_connections[restaurant_id]
    
    async def send_to_table(self, table_id: str, message: dict):
        if table_id in self.active_connections:
            for connection in self.active_connections[table_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass
    
    async def send_to_restaurant(self, restaurant_id: int, message: dict):
        if restaurant_id in self.restaurant_connections:
            for connection in self.restaurant_connections[restaurant_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass

manager = ConnectionManager()
