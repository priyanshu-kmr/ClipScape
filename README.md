# ClipScape

A peer-to-peer clipboard synchronization tool. Each client continuously watches its local clipboard for changes; when a change is detected, it is pushed to Redis and relayed to all connected peers, keeping clipboards in sync across devices.

## Tech Stack

### Core (Python 3.13)

- **Clipboard capture** — per-OS backends (`src/clipboard/`): `pywin32` (Windows), `python-xlib` (Linux), `pyobjc-framework-Cocoa` (macOS), polled at a configurable interval.
- **P2P transport** — [`aiortc`](https://github.com/aiortc/aiortc) (WebRTC) for direct peer data channels; peer discovery and SDP signaling over UDP broadcast + TCP sockets on the local network (`src/network/`).
- **State/persistence** — Redis (`redis` client) stores user, device, and pending-clip records (`src/database/redis_manager.py`, `src/services/redis_service.py`).
- **Approval API** — FastAPI + Uvicorn expose a local HTTP API for the optional clip-approval queue (`src/services/approval_api_service.py`), consumed by the UI over CORS.
- **Supporting libs** — `pydantic` (data models), `ulid-py` (sortable unique IDs), `Pillow` (image clipboard content), `httpx` (HTTP client), `python-dotenv` (env config).
- **Testing** — `pytest` (`tests/`).

### UI (`ui/`)

- **Framework** — Next.js 16 (App Router) with React 19 and TypeScript.
- **Styling** — Tailwind CSS 4.
- **Data** — `ioredis` for Redis access, talking to the same Redis instance as the Python core.

## Architecture

```
Client A (clipboard watcher) --\                              /-- Client B (clipboard watcher)
                                 >-- Redis (state/queue) ------<
Client A <==== WebRTC data channel (aiortc) direct P2P ====> Client B
```

Clipboard changes are captured locally, written through Redis for persistence/coordination, and broadcast directly to connected peers over WebRTC data channels. Peer discovery and connection setup happen via LAN UDP broadcast and TCP-based SDP signaling.

## Running

```bash
pip install -r requirements.txt
python src/main.py
```

Run the UI separately:

```bash
cd ui
npm install
npm run dev
```

See `python src/main.py --help` for CLI options (port, poll interval, discovery interval, Redis toggle, approval UI).
