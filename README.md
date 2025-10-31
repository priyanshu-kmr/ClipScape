# ClipScape 📋

**Cross-platform clipboard synchronization across all your devices on the same network.**

ClipScape allows you to copy text, images, or files on one device and seamlessly paste them on any other device (Windows, macOS, or Linux) connected to the same local network. No internet connection required, no cloud services - just pure peer-to-peer synchronization.

## ✨ Features

- 🖥️ **Cross-Platform**: Works on Windows, macOS, and Linux
- 🔄 **Real-Time Sync**: Clipboard changes sync instantly across all devices
- 🔒 **Privacy First**: All data stays on your local network (P2P)
- 📝 **Multiple Content Types**: Supports text, images, and files
- 🚀 **Zero Configuration**: Auto-discovers devices on the same network
- ⚡ **Fast & Lightweight**: Minimal resource usage

## 🎯 Use Cases

- Copy code on your Mac, paste on your Windows PC
- Grab a screenshot on Windows, paste in Linux
- Share clipboard content between your laptop and desktop
- Quick file transfers between devices without USB or cloud storage

## 📋 Requirements

- Python 3.8 or higher
- All devices must be on the same local network
- Platform-specific dependencies (installed automatically):
  - **Windows**: `pywin32` for clipboard access
  - **Linux**: `xclip` or `wl-clipboard` (Wayland) installed on system
  - **macOS**: `pyobjc-framework-Cocoa` for clipboard access

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/priyanshu-kmr/ClipScape.git
cd ClipScape
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

**Linux users**: Also install system clipboard tools:

```bash
# For X11 (most Linux desktops)
sudo apt-get install xclip

# For Wayland
sudo apt-get install wl-clipboard
```

### 3. (Optional) Configure settings

```bash
cp .env.example .env
# Edit .env if you want to customize the port or device name
```

## 🎮 Usage

### Basic Usage

Run ClipScape on each device you want to sync:

```bash
python src/main.py
```

That's it! ClipScape will:

1. Start listening for other devices on the network
2. Auto-discover and connect to other ClipScape instances
3. Monitor your clipboard for changes
4. Sync clipboard content across all connected devices

### Advanced Options

```bash
# Specify a custom port (default: 9999)
python src/main.py --port 8888

# Set a custom device name
python src/main.py --name "My-Laptop"

# Change clipboard polling interval (default: 0.25s)
python src/main.py --poll-interval 0.5

# Change peer discovery interval (default: 30s)
python src/main.py --discovery-interval 60

# Enable verbose debug logging
python src/main.py --verbose
```

### Command Line Options

```
Options:
  -p, --port PORT              Network port (default: 9999)
  -n, --name NAME              Device name (default: hostname)
  -i, --poll-interval SECONDS  Clipboard poll interval (default: 0.25)
  -d, --discovery-interval SEC Peer discovery interval (default: 30.0)
  -v, --verbose                Enable debug logging
  -h, --help                   Show help message
```

## 🏗️ Architecture

ClipScape uses a modular, platform-agnostic architecture:

```
ClipScape/
├── src/
│   ├── main.py                    # Main application entry point
│   ├── clipboard/                 # Platform-specific clipboard implementations
│   │   ├── base.py                # Abstract base class
│   │   ├── factory.py             # Platform detection & factory
│   │   ├── windows.py             # Windows implementation
│   │   ├── linux.py               # Linux implementation
│   │   └── macos.py               # macOS implementation
│   ├── network/                   # P2P networking
│   │   ├── network.py             # Network manager (discovery, signaling)
│   │   └── peer.py                # Individual peer connection (WebRTC)
│   └── services/                  # High-level services
│       ├── ClipboardService.py    # Clipboard monitoring service
│       └── PeerNetworkService.py  # Network integration service
└── requirements.txt
```

### Key Components

1. **Clipboard Monitoring**: Polls the system clipboard and detects changes
2. **Peer Discovery**: Uses UDP broadcast to find other ClipScape instances
3. **P2P Connection**: WebRTC data channels for direct device-to-device communication
4. **Data Sync**: Base64-encoded JSON for reliable clipboard content transfer

## 🔧 How It Works

1. **Discovery Phase**:

   - Each ClipScape instance broadcasts a UDP discovery message
   - Responds to discovery requests with device information
   - Builds a list of available peers on the network

2. **Connection Phase**:

   - Uses WebRTC for peer-to-peer connections
   - Establishes direct data channels between devices
   - No central server required

3. **Synchronization Phase**:
   - Monitors local clipboard for changes
   - When clipboard changes, broadcasts to all connected peers
   - Peers receive and update their local clipboard
   - Echo prevention ensures no infinite loops

## 🛠️ Development

### Running Tests

```bash
pytest tests/
```

### Project Structure

- `clipboard/`: OS-specific clipboard reading and writing
- `network/`: P2P networking with WebRTC
- `services/`: Integration services that tie everything together
- `tests/`: Test files

## 🐛 Troubleshooting

### No peers discovered

- Ensure all devices are on the same network
- Check firewall settings (allow UDP/TCP on port 9999)
- Try specifying the same port on all devices

### Clipboard not syncing

- Check that ClipScape is running on all devices
- Verify clipboard access permissions (especially on macOS)
- Check logs with `--verbose` flag

### Linux clipboard issues

- Install `xclip` (X11) or `wl-clipboard` (Wayland)
- Check your display server with `echo $XDG_SESSION_TYPE`

### macOS permissions

- Grant Terminal/iTerm accessibility permissions in System Preferences > Privacy

## 📝 Limitations

- File clipboard support is limited (files are transferred as content, not references)
- Large files may take time to sync
- Network must allow UDP broadcast and TCP connections
- Clipboard history is not maintained (only current clipboard syncs)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- Uses [aiortc](https://github.com/aiortc/aiortc) for WebRTC implementation
- Platform clipboard access via native APIs and tools

---

**Made with ❤️ for seamless cross-platform productivity**
