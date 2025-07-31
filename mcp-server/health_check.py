#!/usr/bin/env python3
import asyncio
import websockets
import sys

async def check_health():
    try:
        async with websockets.connect('ws://localhost:8001', open_timeout=3) as ws:
            print("OK")
            return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False

if __name__ == "__main__":
    if asyncio.run(check_health()):
        sys.exit(0)
    else:
        sys.exit(1)
