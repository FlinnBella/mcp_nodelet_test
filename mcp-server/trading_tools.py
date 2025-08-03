import asyncio
import json
from typing import Dict, Any
from website_connector import WebsiteConnector

class TradingTools:
    def __init__(self, website_connector: WebsiteConnector):
        self.website = website_connector
    
    async def buy_crypto(self, params: Dict[str, Any]) -> str:
        """Execute a buy order"""
        crypto = params.get("crypto")
        amount = params.get("amount")
        
        if not crypto or not amount:
            raise ValueError("Missing required parameters: crypto, amount")
        
        try:
            result = await self.website.execute_trade("buy", crypto, amount)
            return f"Successfully bought {amount} {crypto}. Result: {result}"
        except Exception as e:
            raise Exception(f"Buy order failed: {str(e)}")
    
    async def sell_crypto(self, params: Dict[str, Any]) -> str:
        """Execute a sell order"""
        crypto = params.get("crypto")
        amount = params.get("amount")
        
        if not crypto or not amount:
            raise ValueError("Missing required parameters: crypto, amount")
        
        try:
            result = await self.website.execute_trade("sell", crypto, amount)
            return f"Successfully sold {amount} {crypto}. Result: {result}"
        except Exception as e:
            raise Exception(f"Sell order failed: {str(e)}")
    
    async def hold(self, params: Dict[str, Any]) -> str:
        """Hold position (no action)"""
        reason = params.get("reason", "No specific reason provided")
        return f"Holding position. Reason: {reason}"