import asyncio
import socket
import json
import os
from typing import List, Tuple, Optional, Dict, Callable
from network.peer import ClipScapePeer
from pathlib import Path
from dotenv import load_dotenv

try:
    REPO_ROOT = Path(__file__).resolve().parents[2]
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
    else:
        load_dotenv()
except Exception:
    pass

DELIM = b"\n---END_SDP---\n"
BROADCAST_MSG = b"CLIPSCAPE_DISCOVER"

try:
    NETWORK_PORT = int(os.getenv("NETWORK_PORT", "9999"))
except ValueError:
    NETWORK_PORT = 9999

BROADCAST_PORT = NETWORK_PORT
DEFAULT_SIGNAL_PORT = NETWORK_PORT


class ClipScapeNetwork:

    def __init__(self, signaling_port: int = DEFAULT_SIGNAL_PORT, device_name: Optional[str] = None):
        self.signaling_port = signaling_port
        self.device_name = device_name or socket.gethostname()
        self.peers: Dict[str, ClipScapePeer] = {}
        self.server: Optional[asyncio.Server] = None
        self.udp_responder_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.running = False
        self.on_peer_connected_callback: Optional[Callable[[
            ClipScapePeer], None]] = None
        self.on_peer_disconnected_callback: Optional[Callable[[
            str], None]] = None
        self.on_message_callback: Optional[Callable[[str, str], None]] = None

    def get_local_ip(self) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
        finally:
            s.close()

    async def udp_discover(self, timeout: float = 2.0) -> List[Tuple[str, int, str]]:
        loop = asyncio.get_running_loop()
        sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)

        try:
            sock.sendto(BROADCAST_MSG, ("255.255.255.255", BROADCAST_PORT))

            ip = self.get_local_ip()
            parts = ip.split(".")
            if len(parts) == 4:
                subnet_bcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                try:
                    sock.sendto(BROADCAST_MSG, (subnet_bcast, BROADCAST_PORT))
                except Exception:
                    pass

            found = []
            seen_ips = set()
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

                        if addr[0] != self.get_local_ip() and addr[0] not in seen_ips:
                            found.append((addr[0], int(port), name))
                            seen_ips.add(addr[0])
                    except Exception:
                        continue

            return found
        finally:
            sock.close()

    async def udp_responder(self):
        loop = asyncio.get_running_loop()

        def udp_responder_sync():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("", BROADCAST_PORT))
                s.settimeout(1.0)

                while self.running:
                    try:
                        data, addr = s.recvfrom(1024)
                        if data == BROADCAST_MSG:
                            reply = f"CLIPSCAPE_ANNOUNCE:{self.device_name}:{self.signaling_port}".encode(
                            )
                            s.sendto(reply, addr)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
            finally:
                s.close()

        await loop.run_in_executor(None, udp_responder_sync)

    async def handle_signaling(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer_addr = writer.get_extra_info('peername')
        incoming_ip = peer_addr[0]

        try:
            raw = await asyncio.wait_for(
                reader.readuntil(DELIM),
                timeout=10.0
            )
            raw = raw[:-len(DELIM)]
            obj = json.loads(raw.decode())

            if obj.get("type") == "offer":
                remote_device_name = obj.get("device_name", "Unknown")
                remote_port = obj.get("signaling_port", peer_addr[1])

                peer_id = f"{incoming_ip}:{remote_port}"

                if peer_id in self.peers and self.peers[peer_id].is_connected:
                    writer.close()
                    await writer.wait_closed()
                    return

                peer = ClipScapePeer(
                    peer_id=peer_id, peer_name=remote_device_name)
                self._setup_peer_callbacks(peer)
                answer = await peer.handle_offer(obj["sdp"])

                answer_with_meta = {
                    **answer,
                    "device_name": self.device_name,
                    "signaling_port": self.signaling_port
                }

                writer.write(json.dumps(answer_with_meta).encode() + DELIM)
                await writer.drain()

                self.peers[peer_id] = peer

                if self.on_peer_connected_callback:
                    self.on_peer_connected_callback(peer)

        except asyncio.TimeoutError:
            pass
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def connect_to_peer(self, ip: str, port: int, name: str) -> bool:
        peer_id = f"{ip}:{port}"

        if peer_id in self.peers:
            return True

        try:
            peer = ClipScapePeer(peer_id=peer_id, peer_name=name)
            self._setup_peer_callbacks(peer)
            offer = await peer.create_offer()

            offer_with_meta = {
                **offer,
                "device_name": self.device_name,
                "signaling_port": self.signaling_port
            }

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=5.0
            )
            writer.write(json.dumps(offer_with_meta).encode() + DELIM)
            await writer.drain()

            raw = await asyncio.wait_for(
                reader.readuntil(DELIM),
                timeout=5.0
            )
            raw = raw[:-len(DELIM)]
            answer_obj = json.loads(raw.decode())

            if answer_obj.get("type") == "answer":
                await peer.handle_answer(answer_obj["sdp"])
                self.peers[peer_id] = peer

                if self.on_peer_connected_callback:
                    self.on_peer_connected_callback(peer)

                writer.close()
                await writer.wait_closed()
                return True

        except Exception:
            return False

        return False

    def _setup_peer_callbacks(self, peer: ClipScapePeer):
        def on_message(message: str):
            try:
                if self.on_message_callback:
                    self.on_message_callback(peer.peer_id, message)
            except Exception:
                pass

        def on_close():
            try:
                peer_id = peer.peer_id
                if peer_id in self.peers:
                    del self.peers[peer_id]
                if self.on_peer_disconnected_callback:
                    self.on_peer_disconnected_callback(peer_id)
            except Exception:
                pass

        peer.on_message(on_message)
        peer.on_close(on_close)

    async def heartbeat_loop(self):
        while self.running:
            await asyncio.sleep(5.0)

            dead_peers = []
            for peer_id, peer in list(self.peers.items()):
                if peer.is_connected:
                    if not peer.is_alive(timeout=20.0):
                        dead_peers.append(peer_id)
                    else:
                        peer.send_ping()

            for peer_id in dead_peers:
                peer = self.peers.get(peer_id)
                if peer:
                    await peer.close()
                if peer_id in self.peers:
                    del self.peers[peer_id]
                if self.on_peer_disconnected_callback:
                    try:
                        self.on_peer_disconnected_callback(peer_id)
                    except Exception:
                        pass

    async def start(self):
        self.running = True
        self.udp_responder_task = asyncio.create_task(self.udp_responder())
        self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())

        self.server = await asyncio.start_server(
            self.handle_signaling, "0.0.0.0", self.signaling_port
        )

        return asyncio.create_task(self.server.serve_forever())

    async def discover_and_connect(self, timeout=5.0):
        discovered = await self.udp_discover(timeout)
        for ip, port, name in discovered:
            peer_id = f"{ip}:{port}"

            if peer_id in self.peers:
                peer = self.peers[peer_id]
                if not peer.is_connected:
                    del self.peers[peer_id]
                    await self.connect_to_peer(ip, port, name)
            else:
                await self.connect_to_peer(ip, port, name)

    def broadcast_message(self, message: str) -> int:
        success_count = 0
        for peer in self.peers.values():
            if peer.send_message(message):
                success_count += 1
        return success_count

    def broadcast_json(self, data: dict) -> int:
        success_count = 0
        for peer in self.peers.values():
            if peer.send_json(data):
                success_count += 1
        return success_count

    def send_to_peer(self, peer_id: str, message: str) -> bool:
        peer = self.peers.get(peer_id)
        if peer:
            return peer.send_message(message)
        return False

    def get_connected_peers(self) -> List[ClipScapePeer]:
        return [peer for peer in self.peers.values() if peer.is_connected]

    def on_peer_connected(self, callback: Callable[[ClipScapePeer], None]):
        self.on_peer_connected_callback = callback

    def on_peer_disconnected(self, callback: Callable[[str], None]):
        self.on_peer_disconnected_callback = callback

    def on_message(self, callback: Callable[[str, str], None]):
        self.on_message_callback = callback

    async def stop(self):
        self.running = False

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        if self.udp_responder_task:
            self.udp_responder_task.cancel()
            try:
                await self.udp_responder_task
            except asyncio.CancelledError:
                pass

        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

        for peer in list(self.peers.values()):
            await peer.close()
        self.peers.clear()
