import json
import time
from typing import Optional, Callable, Any
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer, RTCDataChannel


class ClipScapePeer:

    def __init__(self, peer_id: str, peer_name: str = "Unknown", ice_servers: list = None):
        self.peer_id = peer_id
        self.peer_name = peer_name
        self.is_connected = False
        self.is_offerer = False
        self.last_pong_time = time.time()
        self.last_ping_time = 0

        if ice_servers is None:
            ice_servers = [RTCIceServer(urls="stun:stun.l.google.com:19302")]

        config = RTCConfiguration(iceServers=ice_servers)
        self.pc = RTCPeerConnection(configuration=config)
        self.data_channel: Optional[RTCDataChannel] = None
        self.on_message_callback: Optional[Callable[[str], None]] = None
        self.on_open_callback: Optional[Callable[[], None]] = None
        self.on_close_callback: Optional[Callable[[], None]] = None
        self._setup_connection_handlers()

    def _setup_connection_handlers(self):
        @self.pc.on("connectionstatechange")
        async def on_connection_state_change():
            state = self.pc.connectionState
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
            self.data_channel = channel
            self._setup_data_channel_handlers(channel)

    def _setup_data_channel_handlers(self, channel: RTCDataChannel):
        @channel.on("open")
        def on_open():
            self.is_connected = True
            self.last_pong_time = time.time()
            if self.on_open_callback:
                self.on_open_callback()

        @channel.on("message")
        def on_message(message):
            try:
                if message == "__PING__":
                    self.send_message("__PONG__")
                    return
                elif message == "__PONG__":
                    self.last_pong_time = time.time()
                    return
            except Exception:
                pass

            if self.on_message_callback:
                self.on_message_callback(message)

        @channel.on("close")
        def on_close():
            self.is_connected = False
            if self.on_close_callback:
                self.on_close_callback()

    async def create_offer(self) -> dict:
        self.is_offerer = True
        self.data_channel = self.pc.createDataChannel("clipscape")
        self._setup_data_channel_handlers(self.data_channel)
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        return {
            "type": "offer",
            "sdp": self.pc.localDescription.sdp
        }

    async def handle_offer(self, offer_sdp: str) -> dict:
        self.is_offerer = False
        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=offer_sdp, type="offer")
        )
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        return {
            "type": "answer",
            "sdp": self.pc.localDescription.sdp
        }

    async def handle_answer(self, answer_sdp: str):
        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=answer_sdp, type="answer")
        )

    def send_message(self, message: str) -> bool:
        if not self.data_channel or self.data_channel.readyState != "open":
            return False
        try:
            self.data_channel.send(message)
            return True
        except Exception:
            return False

    def send_json(self, data: dict) -> bool:
        try:
            message = json.dumps(data)
            return self.send_message(message)
        except Exception:
            return False

    def send_ping(self) -> bool:
        self.last_ping_time = time.time()
        return self.send_message("__PING__")

    def is_alive(self, timeout: float = 15.0) -> bool:
        if not self.is_connected:
            return False
        return (time.time() - self.last_pong_time) < timeout

    def on_message(self, callback: Callable[[str], None]):
        self.on_message_callback = callback

    def on_open(self, callback: Callable[[], None]):
        self.on_open_callback = callback

    def on_close(self, callback: Callable[[], None]):
        self.on_close_callback = callback

    async def close(self):
        if self.data_channel:
            self.data_channel.close()
        await self.pc.close()
        self.is_connected = False

    def __repr__(self):
        status = "connected" if self.is_connected else "disconnected"
        role = "offerer" if self.is_offerer else "answerer"
        return f"<ClipScapePeer {self.peer_name} ({self.peer_id}) - {status}, {role}>"
