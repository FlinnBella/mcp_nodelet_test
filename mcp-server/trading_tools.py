import asyncio
import json
from typing import Dict, Any
from website_connector import WebsiteConnector

class TradingTools:
    def __init__(self, website_connector: WebsiteConnector):
        self.website = website_connector
    
    async def crypto_buy(self, params: Dict[str, Any]) -> str:
        """Execute a buy order"""
        symbol = params.get("symbol")
        amount = params.get("amount")
        
        if not symbol or not amount:
            raise ValueError("Missing required parameters: symbol, amount")
        
        try:
            result = await self.website.execute_trade("buy", symbol, amount)
            return f"Successfully bought {amount} {symbol}. Result: {result}"
        except Exception as e:
            raise Exception(f"Buy order failed: {str(e)}")
    
    async def crypto_sell(self, params: Dict[str, Any]) -> str:
        """Execute a sell order"""
        symbol = params.get("symbol")
        amount = params.get("amount")
        
        if not symbol or not amount:
            raise ValueError("Missing required parameters: symbol, amount")
        
        try:
            result = await self.website.execute_trade("sell", symbol, amount)
            return f"Successfully sold {amount} {symbol}. Result: {result}"
        except Exception as e:
            raise Exception(f"Sell order failed: {str(e)}")
    
    async def crypto_hold(self, params: Dict[str, Any]) -> str:
        """Hold position (no action)"""
        reason = params.get("reason", "No specific reason provided")
        return f"Holding position. Reason: {reason}"