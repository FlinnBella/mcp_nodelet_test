import asyncio
from agent import MCPToKaggleBridge

async def main():
    agent = MCPToKaggleBridge()
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())