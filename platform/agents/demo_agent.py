"""Demo agent - the integration template for Team 2.

Shows the full lifecycle a real agent uses: register, heartbeat, subscribe to
inbound messages, and exchange encrypted hello/byebye messages with a peer.

Run the platform first (from platform/):

    uvicorn app.main:app

Then start two agents in separate terminals:

    python -m agents.demo_agent --id agent_a --peer agent_b --initiate
    python -m agents.demo_agent --id agent_b --peer agent_a

The ``--initiate`` agent kicks off the conversation; the other replies. Watch
the dashboard at http://127.0.0.1:8000/ to see both agents, their heartbeats,
and the encrypted message traffic.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Allow "python -m agents.demo_agent" from the platform/ root and direct runs.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.comms import AgentComms, InboundMessage  # noqa: E402


async def run(agent_id: str, peer: str, base_url: str, token: str, initiate: bool) -> None:
    comms = AgentComms(agent_id=agent_id, role="demo", base_url=base_url, token=token)

    async def on_hello(msg: InboundMessage) -> None:
        print(f"[{agent_id}] <- HELLO from {msg.sender}: {msg.payload}")
        comms.set_status("busy")
        await asyncio.sleep(1.0)
        await comms.send(to=msg.sender, msg_type="hello_ack",
                         payload={"text": f"hi {msg.sender}, {agent_id} here"})
        comms.set_status("idle")

    async def on_hello_ack(msg: InboundMessage) -> None:
        print(f"[{agent_id}] <- HELLO_ACK from {msg.sender}: {msg.payload}")
        await asyncio.sleep(1.0)
        await comms.send(to=msg.sender, msg_type="byebye", payload={"text": "byebye!"})

    async def on_byebye(msg: InboundMessage) -> None:
        print(f"[{agent_id}] <- BYEBYE from {msg.sender}: {msg.payload}")

    comms.on("hello", on_hello)
    comms.on("hello_ack", on_hello_ack)
    comms.on("byebye", on_byebye)

    await comms.register()
    await comms.start(heartbeat_interval_s=4.0)
    print(f"[{agent_id}] registered and listening (peer={peer}, initiate={initiate})")

    if initiate:
        await asyncio.sleep(2.0)  # give the peer time to come online
        print(f"[{agent_id}] -> HELLO to {peer}")
        await comms.send(to=peer, msg_type="hello", payload={"text": "hello there"})

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await comms.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="ContinuumX demo agent")
    parser.add_argument("--id", required=True, help="this agent's id")
    parser.add_argument("--peer", required=True, help="peer agent id to talk to")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token", default="dev-agent-token")
    parser.add_argument("--initiate", action="store_true", help="start the conversation")
    args = parser.parse_args()

    try:
        asyncio.run(run(args.id, args.peer, args.base_url, args.token, args.initiate))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
