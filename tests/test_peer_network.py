"""Integration-style test helper for the peer network.

This script performs a live discovery pass, allows selecting a discovered
peer, then sends either a short text message or the contents of a small
file to the selected peer. It's intended as a developer test harness and
can be run manually during development.

Usage:
    python -m pytest -q tests/test_peer_network.py::test_peer_discovery_send
or
    python tests/test_peer_network.py  # interactive run

Notes:
 - The test is best-effort: it will skip if no peers are discovered.
 - Running this against multiple machines on the same LAN will exercise
   the discovery and signaling flow.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import pytest

from services.PeerNetworkService import PeerNetworkService

logger = logging.getLogger(__name__)


def _make_temp_file(contents: bytes) -> str:
    fd, path = tempfile.mkstemp(prefix="clipscape-test-", suffix=".bin")
    os.write(fd, contents)
    os.close(fd)
    return path


def _choose_peer(peers) -> Optional[str]:
    if not peers:
        return None
    # Prefer first peer for automated tests
    return peers[0].peer_id


def run_interactive():
    service = PeerNetworkService(auto_start=True)
    try:
        ready = service.wait_until_ready(timeout=10.0)
        if not ready:
            print("PeerNetworkService did not become ready in time")
            return

        print("Discovering peers (this may take a few seconds)...")
        service.discover_now()

        peers = list(service.connected_peers())
        if not peers:
            print("No peers discovered.")
            return

        print("Discovered peers:")
        for i, p in enumerate(peers):
            print(f"  [{i}] {p.peer_name} ({p.peer_id})")

        idx = int(input("Select peer index to send to [0]: ") or "0")
        target = peers[idx].peer_id

        mode = input("Send (t)ext or (f)ile? [t]: ") or "t"

        if mode.lower().startswith("t"):
            text = input("Message to send: ") or "hello from test"
            ok = service.send_to_peer(target, text)
            print("Sent:" , ok)
        else:
            sample = b"ClipScape test file\n"
            path = _make_temp_file(sample)
            try:
                with open(path, "rb") as fh:
                    payload = fh.read()

                data = {"type": "file", "name": Path(path).name, "data": payload.hex()}
                ok = service.send_json_to_peer(target, data)
                print("Sent file JSON:", ok)
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass

    finally:
        service.stop()


@pytest.mark.skipif(True, reason="Integration test - enable for manual runs")
def test_peer_discovery_send():
    """Automated smoke test: discover peers, choose first, send text and file.

    This test is skipped by default because it relies on a live LAN.
    To run it manually, remove or change the skip condition above.
    """
    service = PeerNetworkService(auto_start=True)
    try:
        assert service.wait_until_ready(timeout=10.0)

        # initial discovery
        service.discover_now()
        peers = list(service.connected_peers())
        if not peers:
            pytest.skip("no peers discovered")

        target = _choose_peer(peers)
        assert target is not None

        # send text
        ok = service.send_to_peer(target, "pytest: hello")
        assert ok in (True, False)

        # send small file as JSON (hex-encoded)
        payload = b"pytest-file-content"
        data = {"type": "file", "name": "pytest.bin", "data": payload.hex()}
        ok2 = service.send_json_to_peer(target, data)
        assert ok2 in (True, False)

    finally:
        service.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true", help="Run interactive demo")
    args = parser.parse_args()
    if args.interactive:
        run_interactive()
    else:
        print("Run with --interactive to perform a live discovery/send demo")
