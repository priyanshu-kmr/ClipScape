"""Command-line entry point."""

import argparse
import logging
import signal
import sys
from typing import Optional, Sequence

from app.application import ClipScapeApp
from app.config import AppConfig, default_port

logger = logging.getLogger(__name__)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ClipScape - Cross-platform clipboard synchronization"
    )

    parser.add_argument(
        "-p", "--port",
        type=int,
        default=default_port(),
        help="Network port for P2P communication (default: 9999)"
    )

    parser.add_argument(
        "-n", "--name",
        type=str,
        default=None,
        help="Device name (default: hostname)"
    )

    parser.add_argument(
        "-i", "--poll-interval",
        type=float,
        default=0.25,
        help="Clipboard polling interval in seconds (default: 0.25)"
    )

    parser.add_argument(
        "-d", "--discovery-interval",
        type=float,
        default=30.0,
        help="Peer discovery interval in seconds (default: 30.0)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug logging"
    )

    parser.add_argument(
        "--no-redis",
        action="store_true",
        help="Disable Redis clipboard persistence"
    )

    return parser.parse_args(argv)


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.INFO,
                        format='%(levelname)s: %(message)s')
    if verbose:
        logging.getLogger().setLevel(logging.INFO)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    configure_logging(args.verbose)

    app = ClipScapeApp(AppConfig.from_args(args))

    def signal_handler(signum, frame):
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        app.run_forever()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
