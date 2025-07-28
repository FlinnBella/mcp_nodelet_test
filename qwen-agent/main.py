import asyncio
from agent import QwenTradingAgent

async def main():
    agent = QwenTradingAgent()
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())