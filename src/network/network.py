"""
Network management for ClipScape P2P network.

This module handles peer discovery, signaling, and network coordination.
"""

import asyncio
import socket
import json
import os
from typing import List, Tuple, Optional, Dict, Callable
from network.peer import ClipScapePeer
from pathlib import Path
from dotenv import load_dotenv


# Load .env from the repository root (two parents up from this file)
try:
    REPO_ROOT = Path(__file__).resolve().parents[2]
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
    else:
        load_dotenv()  # fallback to default behavior
except Exception:
    pass

# Network constants
DELIM = b"\n---END_SDP---\n"
BROADCAST_MSG = b"CLIPSCAPE_DISCOVER"

# Use NETWORK_PORT from .env / environment, fallback to 9999
try:
    NETWORK_PORT = int(os.getenv("NETWORK_PORT", "9999"))
except ValueError:
    NETWORK_PORT = 9999

BROADCAST_PORT = NETWORK_PORT
DEFAULT_SIGNAL_PORT = NETWORK_PORT


class ClipScapeNetwork:
    """
    Manages the ClipScape P2P network.
    
    Handles peer discovery via UDP broadcast, signaling via TCP,
    and maintains connections to all discovered peers.
    """
    
    def __init__(self, signaling_port: int = DEFAULT_SIGNAL_PORT, device_name: Optional[str] = None):
        """
        Initialize the network manager.
        
        Args:
            signaling_port: TCP port for signaling server
            device_name: Human-readable name for this device
        """
        self.signaling_port = signaling_port
        self.device_name = device_name or socket.gethostname()
        
        # Peer management
        self.peers: Dict[str, ClipScapePeer] = {}
        
        # Server components
        self.server: Optional[asyncio.Server] = None
        self.udp_responder_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Callbacks
        self.on_peer_connected_callback: Optional[Callable[[ClipScapePeer], None]] = None
        self.on_peer_disconnected_callback: Optional[Callable[[str], None]] = None
        self.on_message_callback: Optional[Callable[[str, str], None]] = None
    
    def get_local_ip(self) -> str:
        """
        Get the local IP address.
        
        Returns:
            str: Local IP address
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
        finally:
            s.close()
    
    async def udp_discover(self, timeout: float = 2.0) -> List[Tuple[str, int, str]]:
        """
        Broadcast discovery and collect replies.
        
        Args:
            timeout: How long to wait for responses
            
        Returns:
            List of tuples (ip, port, device_name)
        """
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        
        try:
            # Send broadcast to global and subnet broadcast addresses
            sock.sendto(BROADCAST_MSG, ("255.255.255.255", BROADCAST_PORT))
            
            ip = self.get_local_ip()
            parts = ip.split(".")
            if len(parts) == 4:
                subnet_bcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                try:
                    sock.sendto(BROADCAST_MSG, (subnet_bcast, BROADCAST_PORT))
                except Exception:
                    pass
            
            # Collect responses
            found = []
            end = loop.time() + timeout
            
            while loop.time() < end:
                try:
                    data, addr = sock.recvfrom(1024)
                except socket.timeout:
                    break
                
                if data.startswith(b"CLIPSCAPE_ANNOUNCE:"):
                    try:
                        payload = data.decode().split("CLIPSCAPE_ANNOUNCE:")[1]
                        name, port = payload.rsplit(":", 1)
                        
                        # Don't discover ourselves
                        if addr[0] != self.get_local_ip():
                            found.append((addr[0], int(port), name))
                    except Exception as e:
                        print(f"Error parsing announcement: {e}")
                        continue
            
            return found
        finally:
            sock.close()
    
    async def udp_responder(self):
        """
        Respond to UDP discovery requests.
        
        Runs in background and responds to broadcast discovery messages.
        """
        loop = asyncio.get_running_loop()
        
        def udp_responder_sync():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("", BROADCAST_PORT))
                s.settimeout(1.0)  # Allow periodic checking
                
                while self.running:
                    try:
                        data, addr = s.recvfrom(1024)
                        if data == BROADCAST_MSG:
                            reply = f"CLIPSCAPE_ANNOUNCE:{self.device_name}:{self.signaling_port}".encode()
                            s.sendto(reply, addr)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
            finally:
                s.close()
        
        await loop.run_in_executor(None, udp_responder_sync)
    
    async def handle_signaling(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Handle incoming signaling connections (receive offers).
        
        Args:
            reader: Stream reader for incoming data
            writer: Stream writer for outgoing data
        """
        peer_addr = writer.get_extra_info('peername')
        peer_id = f"{peer_addr[0]}:{peer_addr[1]}"
        
        try:
            # Read offer
            raw = await reader.readuntil(DELIM)
            raw = raw[:-len(DELIM)]
            obj = json.loads(raw.decode())
            
            if obj.get("type") == "offer":
                # Create peer and handle offer
                peer = ClipScapePeer(peer_id=peer_id, peer_name="Unknown")
                
                # Setup peer callbacks
                self._setup_peer_callbacks(peer)
                
                # Handle the offer and create answer
                answer = await peer.handle_offer(obj["sdp"])
                
                # Send answer back
                writer.write(json.dumps(answer).encode() + DELIM)
                await writer.drain()
                
                # Store peer
                self.peers[peer_id] = peer
                print(f"Answered connection from {peer_id}")
                
                # Notify callback
                if self.on_peer_connected_callback:
                    self.on_peer_connected_callback(peer)
        
        except Exception as e:
            print(f"Error handling signaling from {peer_id}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def connect_to_peer(self, ip: str, port: int, name: str) -> bool:
        """
        Connect to a discovered peer as offerer.
        
        Args:
            ip: Peer IP address
            port: Peer signaling port
            name: Peer device name
            
        Returns:
            bool: True if connection successful
        """
        peer_id = f"{ip}:{port}"
        
        # Don't reconnect if already connected
        if peer_id in self.peers:
            print(f"Already connected to {peer_id}")
            return True
        
        try:
            # Create peer
            peer = ClipScapePeer(peer_id=peer_id, peer_name=name)
            
            # Setup callbacks
            self._setup_peer_callbacks(peer)
            
            # Create offer
            offer = await peer.create_offer()
            
            # Send offer via TCP signaling
            reader, writer = await asyncio.open_connection(ip, port)
            writer.write(json.dumps(offer).encode() + DELIM)
            await writer.drain()
            
            # Receive answer
            raw = await reader.readuntil(DELIM)
            raw = raw[:-len(DELIM)]
            answer_obj = json.loads(raw.decode())
            
            if answer_obj.get("type") == "answer":
                await peer.handle_answer(answer_obj["sdp"])
                
                # Store peer
                self.peers[peer_id] = peer
                print(f"Connected to {name} ({peer_id})")
                
                # Notify callback
                if self.on_peer_connected_callback:
                    self.on_peer_connected_callback(peer)
                
                writer.close()
                await writer.wait_closed()
                return True
        
        except Exception as e:
            print(f"Failed to connect to {name} ({ip}:{port}): {e}")
            return False
    
    def _setup_peer_callbacks(self, peer: ClipScapePeer):
        """Setup callbacks for a peer."""
        
        def on_message(message: str):
            if self.on_message_callback:
                self.on_message_callback(peer.peer_id, message)
        
        def on_close():
            peer_id = peer.peer_id
            if peer_id in self.peers:
                del self.peers[peer_id]
            if self.on_peer_disconnected_callback:
                self.on_peer_disconnected_callback(peer_id)
        
        peer.on_message(on_message)
        peer.on_close(on_close)
    
    async def start(self):
        """
        Start the network manager.
        
        Starts UDP responder and TCP signaling server.
        """
        self.running = True
        
        # Start UDP responder for discovery
        self.udp_responder_task = asyncio.create_task(self.udp_responder())
        
        # Start TCP signaling server
        self.server = await asyncio.start_server(
            self.handle_signaling, "0.0.0.0", self.signaling_port
        )
        
        addrs = ", ".join(str(sock.getsockname()) for sock in self.server.sockets)
        print(f"ClipScape network listening on {addrs}")
        print(f"Device name: {self.device_name}")
        
        # Return server task
        return asyncio.create_task(self.server.serve_forever())
    
    async def discover_and_connect(self, timeout: float = 2.0):
        """
        Discover peers and connect to them.
        
        Args:
            timeout: Discovery timeout in seconds
        """
        print(f"Discovering ClipScape peers...")
        found = await self.udp_discover(timeout=timeout)
        
        if not found:
            print("No peers found.")
            return
        
        print(f"Found {len(found)} peer(s):")
        for ip, port, name in found:
            print(f"  {name} @ {ip}:{port}")
            await self.connect_to_peer(ip, port, name)
    
    def broadcast_message(self, message: str) -> int:
        """
        Broadcast a message to all connected peers.
        
        Args:
            message: Message to broadcast
            
        Returns:
            int: Number of peers that received the message
        """
        success_count = 0
        for peer in self.peers.values():
            if peer.send_message(message):
                success_count += 1
        return success_count
    
    def broadcast_json(self, data: dict) -> int:
        """
        Broadcast JSON data to all connected peers.
        
        Args:
            data: Dictionary to serialize and broadcast
            
        Returns:
            int: Number of peers that received the data
        """
        success_count = 0
        for peer in self.peers.values():
            if peer.send_json(data):
                success_count += 1
        return success_count
    
    def send_to_peer(self, peer_id: str, message: str) -> bool:
        """
        Send a message to a specific peer.
        
        Args:
            peer_id: Peer identifier
            message: Message to send
            
        Returns:
            bool: True if sent successfully
        """
        peer = self.peers.get(peer_id)
        if peer:
            return peer.send_message(message)
        return False
    
    def get_connected_peers(self) -> List[ClipScapePeer]:
        """
        Get list of all connected peers.
        
        Returns:
            List of ClipScapePeer objects
        """
        return [peer for peer in self.peers.values() if peer.is_connected]
    
    def on_peer_connected(self, callback: Callable[[ClipScapePeer], None]):
        """Register a callback for new peer connections."""
        self.on_peer_connected_callback = callback
    
    def on_peer_disconnected(self, callback: Callable[[str], None]):
        """Register a callback for peer disconnections."""
        self.on_peer_disconnected_callback = callback
    
    def on_message(self, callback: Callable[[str, str], None]):
        """Register a callback for incoming messages (peer_id, message)."""
        self.on_message_callback = callback
    
    async def stop(self):
        """Stop the network manager and close all connections."""
        self.running = False
        
        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Stop UDP responder
        if self.udp_responder_task:
            self.udp_responder_task.cancel()
            try:
                await self.udp_responder_task
            except asyncio.CancelledError:
                pass
        
        # Close all peer connections
        for peer in list(self.peers.values()):
            await peer.close()
        self.peers.clear()
        
        print("Network stopped")
