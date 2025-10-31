import json
import uuid
from typing import Optional, Callable
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer, RTCDataChannel


class ClipScapePeer:

    def __init__(self, peer_id: str, peer_name: str = "Unknown"):
        self.peer_id = peer_id
        self.peer_name = peer_name
        self.is_connected = False
        self._chunk_buffer = {}

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
            if state in ["failed", "closed", "disconnected"]:
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
            if self.on_open_callback:
                self.on_open_callback()

        @channel.on("message")
        def on_message(message):
            if isinstance(message, str) and message.startswith("__CHUNK__"):
                try:
                    chunk_data = json.loads(message[9:])
                    chunk_id = chunk_data["id"]
                    chunk_index = chunk_data["index"]
                    total_chunks = chunk_data["total"]
                    chunk_content = chunk_data["data"]

                    if chunk_id not in self._chunk_buffer:
                        self._chunk_buffer[chunk_id] = {}

                    self._chunk_buffer[chunk_id][chunk_index] = chunk_content

                    if len(self._chunk_buffer[chunk_id]) == total_chunks:
                        full_message = "".join(
                            self._chunk_buffer[chunk_id][i]
                            for i in range(total_chunks)
                        )
                        del self._chunk_buffer[chunk_id]

                        if self.on_message_callback:
                            self.on_message_callback(full_message)
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
            chunk_size = 16000
            if len(message) <= chunk_size:
                self.data_channel.send(message)
                return True

            chunk_id = str(uuid.uuid4())[:8]
            total_chunks = (len(message) + chunk_size - 1) // chunk_size

            for i in range(total_chunks):
                start = i * chunk_size
                end = min(start + chunk_size, len(message))
                chunk = message[start:end]

                chunk_msg = "__CHUNK__" + json.dumps({
                    "id": chunk_id,
                    "index": i,
                    "total": total_chunks,
                    "data": chunk
                })
                self.data_channel.send(chunk_msg)

            return True
        except Exception:
            return False

    def send_json(self, data: dict) -> bool:
        try:
            message = json.dumps(data)
            return self.send_message(message)
        except Exception:
            return False

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
