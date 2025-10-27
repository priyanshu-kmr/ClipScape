# ClipScape Network Entry Point
import asyncio
from network import ClipScapeNetwork

ClipScapeNode = ClipScapeNetwork

async def run_interactive_node():
    network = ClipScapeNetwork()
    try:
        server_task = await network.start()
        print("\nCommands: discover, peers, send <msg>, quit")
        await asyncio.sleep(1)
        await network.discover_and_connect()
        loop = asyncio.get_running_loop()
        while True:
            try:
                cmd = await loop.run_in_executor(None, input, "\n> ")
                if not cmd.strip():
                    continue
                if cmd.lower() == "quit":
                    break
                elif cmd.lower() == "discover":
                    await network.discover_and_connect()
                elif cmd.lower() == "peers":
                    for peer in network.get_connected_peers():
                        print(f"  {peer.peer_name} ({peer.peer_id})")
                elif cmd.lower().startswith("send "):
                    count = network.broadcast_message(cmd[5:])
                    print(f"Sent to {count} peers")
            except EOFError:
                break
        server_task.cancel()
    finally:
        await network.stop()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9999)
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()
    try:
        if args.interactive:
            asyncio.run(run_interactive_node())
        else:
            async def run():
                network = ClipScapeNetwork(signaling_port=args.port)
                await network.start()
                await asyncio.sleep(1)
                await network.discover_and_connect()
                await asyncio.Event().wait()
            asyncio.run(run())
    except KeyboardInterrupt:
        print("\nExiting...")
