"""
Peer node implementation for ClipScape P2P network.

This module handles individual peer connections using WebRTC.
"""

import json
from typing import Optional, Callable, Any
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer, RTCDataChannel


class ClipScapePeer:
    """
    Represents a single peer connection in the ClipScape network.
    
    Handles WebRTC connection setup, data channel management, and message passing.
    """
    
    def __init__(self, peer_id: str, peer_name: str = "Unknown", ice_servers: list = None):
        """
        Initialize a peer connection.
        
        Args:
            peer_id: Unique identifier for this peer (usually "ip:port")
            peer_name: Human-readable name of the peer
            ice_servers: List of STUN/TURN servers for ICE negotiation
        """
        self.peer_id = peer_id
        self.peer_name = peer_name
        self.is_connected = False
        self.is_offerer = False
        
        # Configure WebRTC
        if ice_servers is None:
            ice_servers = [RTCIceServer(urls="stun:stun.l.google.com:19302")]
        
        config = RTCConfiguration(iceServers=ice_servers)
        self.pc = RTCPeerConnection(configuration=config)
        
        # Data channel
        self.data_channel: Optional[RTCDataChannel] = None
        
        # Callbacks
        self.on_message_callback: Optional[Callable[[str], None]] = None
        self.on_open_callback: Optional[Callable[[], None]] = None
        self.on_close_callback: Optional[Callable[[], None]] = None
        
        # Setup connection state handlers
        self._setup_connection_handlers()
    
    def _setup_connection_handlers(self):
        """Setup WebRTC connection event handlers."""
        
        @self.pc.on("connectionstatechange")
        async def on_connection_state_change():
            state = self.pc.connectionState
            print(f"[{self.peer_id}] Connection state: {state}")
            
            if state == "connected":
                self.is_connected = True
                if self.on_open_callback:
                    self.on_open_callback()
            elif state in ["failed", "closed"]:
                self.is_connected = False
                if self.on_close_callback:
                    self.on_close_callback()
        
        @self.pc.on("datachannel")
        def on_datachannel(channel: RTCDataChannel):
            """Handle incoming data channel (for answerer role)."""
            print(f"[{self.peer_id}] Received data channel: {channel.label}")
            self.data_channel = channel
            self._setup_data_channel_handlers(channel)
    
    def _setup_data_channel_handlers(self, channel: RTCDataChannel):
        """Setup data channel event handlers."""
        
        @channel.on("open")
        def on_open():
            print(f"[{self.peer_id}] Data channel opened")
            self.is_connected = True
            if self.on_open_callback:
                self.on_open_callback()
        
        @channel.on("message")
        def on_message(message):
            print(f"[{self.peer_id}] Received: {message[:100]}...")  # Truncate long messages
            if self.on_message_callback:
                self.on_message_callback(message)
        
        @channel.on("close")
        def on_close():
            print(f"[{self.peer_id}] Data channel closed")
            self.is_connected = False
            if self.on_close_callback:
                self.on_close_callback()
    
    async def create_offer(self) -> dict:
        """
        Create a WebRTC offer (offerer role).
        
        Returns:
            dict: Offer SDP in JSON format
        """
        self.is_offerer = True
        
        # Create data channel
        self.data_channel = self.pc.createDataChannel("clipscape")
        self._setup_data_channel_handlers(self.data_channel)
        
        # Create and set local description
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        
        return {
            "type": "offer",
            "sdp": self.pc.localDescription.sdp
        }
    
    async def handle_offer(self, offer_sdp: str) -> dict:
        """
        Handle incoming WebRTC offer (answerer role).
        
        Args:
            offer_sdp: SDP string from the offer
            
        Returns:
            dict: Answer SDP in JSON format
        """
        self.is_offerer = False
        
        # Set remote description
        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=offer_sdp, type="offer")
        )
        
        # Create and set local description (answer)
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        
        return {
            "type": "answer",
            "sdp": self.pc.localDescription.sdp
        }
    
    async def handle_answer(self, answer_sdp: str):
        """
        Handle incoming WebRTC answer (offerer role).
        
        Args:
            answer_sdp: SDP string from the answer
        """
        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=answer_sdp, type="answer")
        )
    
    def send_message(self, message: str) -> bool:
        """
        Send a message through the data channel.
        
        Args:
            message: Message to send
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.data_channel or self.data_channel.readyState != "open":
            print(f"[{self.peer_id}] Cannot send: data channel not open")
            return False
        
        try:
            self.data_channel.send(message)
            return True
        except Exception as e:
            print(f"[{self.peer_id}] Error sending message: {e}")
            return False
    
    def send_json(self, data: dict) -> bool:
        """
        Send JSON data through the data channel.
        
        Args:
            data: Dictionary to serialize and send
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            message = json.dumps(data)
            return self.send_message(message)
        except Exception as e:
            print(f"[{self.peer_id}] Error sending JSON: {e}")
            return False
    
    def on_message(self, callback: Callable[[str], None]):
        """Register a callback for incoming messages."""
        self.on_message_callback = callback
    
    def on_open(self, callback: Callable[[], None]):
        """Register a callback for connection open."""
        self.on_open_callback = callback
    
    def on_close(self, callback: Callable[[], None]):
        """Register a callback for connection close."""
        self.on_close_callback = callback
    
    async def close(self):
        """Close the peer connection."""
        if self.data_channel:
            self.data_channel.close()
        await self.pc.close()
        self.is_connected = False
        print(f"[{self.peer_id}] Connection closed")
    
    def __repr__(self):
        status = "connected" if self.is_connected else "disconnected"
        role = "offerer" if self.is_offerer else "answerer"
        return f"<ClipScapePeer {self.peer_name} ({self.peer_id}) - {status}, {role}>"
