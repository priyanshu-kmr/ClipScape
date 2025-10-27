# ClipScape Network Module - Refactored

This directory contains the refactored P2P networking implementation for ClipScape.

## Structure

```
network/
├── __init__.py        # Package exports
├── peer.py            # Individual peer connection (ClipScapePeer)
├── network.py         # Network management (ClipScapeNetwork)
└── README.md          # This file

network.py (root)      # CLI interface and backward compatibility
```

## Architecture

The refactoring separates concerns into two main classes:

### 1. `ClipScapePeer` (network/peer.py)

Represents a single peer-to-peer WebRTC connection.

**Responsibilities:**
- WebRTC connection setup (offer/answer negotiation)
- Data channel management
- Message sending/receiving
- Connection state tracking

**Key Methods:**
- `create_offer()` - Create WebRTC offer (as offerer)
- `handle_offer(sdp)` - Handle incoming offer and create answer (as answerer)
- `handle_answer(sdp)` - Handle incoming answer (as offerer)
- `send_message(msg)` - Send text message
- `send_json(data)` - Send JSON data
- `on_message(callback)` - Register message callback
- `close()` - Close the connection

**Example:**
```python
from network.peer import ClipScapePeer

# Create a peer
peer = ClipScapePeer(peer_id="192.168.1.100:9999", peer_name="Alice's PC")

# Register callbacks
peer.on_message(lambda msg: print(f"Received: {msg}"))
peer.on_open(lambda: print("Connected!"))

# Create offer (as offerer)
offer = await peer.create_offer()
# ... send offer via signaling ...

# Or handle offer (as answerer)
answer = await peer.handle_offer(offer_sdp)
# ... send answer back ...

# Send messages
peer.send_message("Hello!")
peer.send_json({"type": "clipboard", "data": "..."})
```

### 2. `ClipScapeNetwork` (network/network.py)

Manages the entire P2P network.

**Responsibilities:**
- Peer discovery (UDP broadcast)
- Signaling server (TCP)
- Multiple peer management
- Network-wide message broadcasting

**Key Methods:**
- `start()` - Start network services
- `stop()` - Stop network and close all connections
- `udp_discover(timeout)` - Discover peers via UDP broadcast
- `connect_to_peer(ip, port, name)` - Connect to a specific peer
- `discover_and_connect()` - Discover and connect to all peers
- `broadcast_message(msg)` - Send message to all peers
- `broadcast_json(data)` - Send JSON to all peers
- `send_to_peer(peer_id, msg)` - Send to specific peer
- `get_connected_peers()` - Get list of connected peers
- `on_peer_connected(callback)` - Register callback for new connections
- `on_message(callback)` - Register callback for incoming messages

**Example:**
```python
from network import ClipScapeNetwork

# Create network
network = ClipScapeNetwork(signaling_port=9999, device_name="My PC")

# Register callbacks
network.on_peer_connected(lambda peer: print(f"New peer: {peer.peer_name}"))
network.on_message(lambda peer_id, msg: print(f"{peer_id}: {msg}"))

# Start network
await network.start()

# Discover and connect to peers
await network.discover_and_connect()

# Broadcast messages
network.broadcast_message("Hello everyone!")
network.broadcast_json({"type": "clipboard_update", "data": "..."})

# Stop network
await network.stop()
```

## CLI Interface (network.py in root)

The root `network.py` provides a command-line interface for testing.

**Usage:**
```bash
# Interactive mode
python network.py --interactive

# Discovery mode (finds peers and waits)
python network.py --port 9999

# With custom device name
python network.py --name "Alice's Laptop" --interactive
```

**Interactive Commands:**
- `discover` - Discover and connect to peers
- `peers` - List connected peers
- `send <message>` - Broadcast message to all peers
- `quit` - Exit

## Protocol Flow

### Discovery (UDP)
```
1. Node A broadcasts CLIPSCAPE_DISCOVER on port 9999
2. Node B receives broadcast
3. Node B responds with CLIPSCAPE_ANNOUNCE:<name>:<port>
4. Node A receives announcement
```

### Connection Setup (TCP + WebRTC)
```
1. Node A connects to Node B's signaling port (TCP)
2. Node A creates WebRTC offer and sends via TCP
3. Node B receives offer, creates answer
4. Node B sends answer back via TCP
5. WebRTC ICE negotiation happens
6. Data channel opens
7. P2P connection established (direct or via STUN/TURN)
```

### Messaging (WebRTC Data Channel)
```
1. Either node sends message via data channel
2. Message is received by peer
3. Callback is triggered
```

## Integration Example

```python
import asyncio
from network import ClipScapeNetwork
from platforms import get_clipboard_item

async def sync_clipboard():
    # Create network
    network = ClipScapeNetwork()
    
    # Handle incoming clipboard data
    def on_clipboard_message(peer_id, message):
        data = json.loads(message)
        if data.get("type") == "clipboard":
            # Update local clipboard
            print(f"Received clipboard from {peer_id}")
    
    network.on_message(on_clipboard_message)
    
    # Start network
    await network.start()
    await network.discover_and_connect()
    
    # Monitor clipboard and broadcast changes
    last_clipboard = None
    while True:
        await asyncio.sleep(0.5)
        
        clipboard = get_clipboard_item()
        if clipboard.payload != last_clipboard:
            # Clipboard changed, broadcast it
            data = {
                "type": "clipboard",
                "payload": clipboard.payload.hex(),
                "metadata": clipboard.metaData
            }
            network.broadcast_json(data)
            last_clipboard = clipboard.payload

asyncio.run(sync_clipboard())
```

## Benefits of Refactoring

1. **Separation of Concerns**
   - Peer logic isolated from network management
   - Single Responsibility Principle

2. **Testability**
   - Can test individual peer connections
   - Can mock network for testing

3. **Reusability**
   - `ClipScapePeer` can be used standalone
   - `ClipScapeNetwork` can manage any peer type

4. **Extensibility**
   - Easy to add new peer types
   - Easy to add new network discovery methods

5. **Maintainability**
   - Clear boundaries between components
   - Easier to debug and understand

## Dependencies

- `aiortc` - WebRTC implementation
- `asyncio` - Async/await support
- Python 3.7+

## Future Enhancements

- [ ] Add encryption for messages
- [ ] Implement TURN server support for NAT traversal
- [ ] Add peer authentication
- [ ] Implement peer reputation system
- [ ] Add bandwidth throttling
- [ ] Support multiple data channels per peer
- [ ] Add connection recovery/reconnection logic
- [ ] Implement peer discovery via mDNS/Bonjour
- [ ] Add WebSocket signaling as alternative to TCP
