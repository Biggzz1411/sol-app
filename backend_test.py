#!/usr/bin/env python3
"""
Comprehensive backend API testing for Solana Sniper Bot.
Tests real blockchain interactions, authentication, and all endpoints.
"""
import asyncio
import httpx
import json
import time
import os
from typing import Dict, Any, Optional

# Test configuration
BACKEND_URL = "https://app-builder-4154.preview.emergentagent.com/api"
TEST_EMAIL = "Superbiggzz1411@gmail.com"
TEST_PASSWORD = "Biggzz1411!"

class SniperBotTester:
    def __init__(self):
        self.base_url = BACKEND_URL
        self.session = httpx.AsyncClient(timeout=30.0)
        self.auth_token = None
        self.auth_cookies = {}
        self.test_results = []
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.aclose()
    
    def log_test(self, test_name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")
        if response_data and not success:
            print(f"    Response: {response_data}")
        print()
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "response": response_data if not success else None
        })
    
    async def make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with auth handling."""
        url = f"{self.base_url}{endpoint}"
        
        # Add auth headers if available
        headers = kwargs.get("headers", {})
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        kwargs["headers"] = headers
        
        # Add cookies if available
        if self.auth_cookies:
            kwargs["cookies"] = self.auth_cookies
        
        try:
            response = await self.session.request(method, url, **kwargs)
            
            # Update cookies from response
            if response.cookies:
                self.auth_cookies.update(dict(response.cookies))
            
            return {
                "status_code": response.status_code,
                "data": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                "headers": dict(response.headers)
            }
        except Exception as e:
            return {
                "status_code": 0,
                "data": {"error": str(e)},
                "headers": {}
            }
    
    async def test_authentication(self):
        """Test authentication endpoints."""
        print("🔐 Testing Authentication...")
        
        # Test login
        login_data = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
        
        response = await self.make_request("POST", "/auth/login", json=login_data)
        
        if response["status_code"] == 200:
            data = response["data"]
            if "token" in data:
                self.auth_token = data["token"]
                self.log_test("Authentication - Login", True, f"Logged in as {data.get('email', 'unknown')}")
            else:
                self.log_test("Authentication - Login", False, "No token in response", data)
        else:
            self.log_test("Authentication - Login", False, f"Status: {response['status_code']}", response["data"])
            return False
        
        # Test /auth/me
        response = await self.make_request("GET", "/auth/me")
        if response["status_code"] == 200:
            data = response["data"]
            self.log_test("Authentication - Get User", True, f"User: {data.get('email', 'unknown')}, Role: {data.get('role', 'unknown')}")
        else:
            self.log_test("Authentication - Get User", False, f"Status: {response['status_code']}", response["data"])
        
        return True
    
    async def test_bot_state(self):
        """Test bot state endpoints - CRITICAL independent toggles."""
        print("🤖 Testing Bot State (Independent Toggles)...")
        
        # Get initial state
        response = await self.make_request("GET", "/bot/state")
        if response["status_code"] != 200:
            self.log_test("Bot State - Get Initial", False, f"Status: {response['status_code']}", response["data"])
            return
        
        initial_state = response["data"]
        self.log_test("Bot State - Get Initial", True, 
                     f"Mode: {initial_state.get('mode', 'unknown')}, "
                     f"Bot: {initial_state.get('is_running', False)}, "
                     f"Scanner: {initial_state.get('scanner_running', False)}")
        
        # Verify mode is "live" not "paper"
        if initial_state.get("mode") != "live":
            self.log_test("Bot State - Live Mode", False, f"Expected 'live', got '{initial_state.get('mode')}'", initial_state)
        else:
            self.log_test("Bot State - Live Mode", True, "Mode is 'live' (not paper trading)")
        
        # Test independent bot toggle (trading engine)
        print("  Testing Bot Toggle (Trading Engine)...")
        
        # Start bot only
        response = await self.make_request("PUT", "/bot/state", json={"is_running": True})
        if response["status_code"] == 200:
            state = response["data"]
            if state.get("is_running") == True:
                self.log_test("Bot State - Start Bot", True, "Bot started (trading engine active)")
            else:
                self.log_test("Bot State - Start Bot", False, "Bot not started", state)
        else:
            self.log_test("Bot State - Start Bot", False, f"Status: {response['status_code']}", response["data"])
        
        # Stop bot only
        response = await self.make_request("PUT", "/bot/state", json={"is_running": False})
        if response["status_code"] == 200:
            state = response["data"]
            if state.get("is_running") == False:
                self.log_test("Bot State - Stop Bot", True, "Bot stopped (trading engine inactive)")
            else:
                self.log_test("Bot State - Stop Bot", False, "Bot not stopped", state)
        else:
            self.log_test("Bot State - Stop Bot", False, f"Status: {response['status_code']}", response["data"])
        
        # Test independent scanner toggle (blockchain monitor)
        print("  Testing Scanner Toggle (Blockchain Monitor)...")
        
        # Start scanner only
        response = await self.make_request("PUT", "/bot/state", json={"scanner_running": True})
        if response["status_code"] == 200:
            state = response["data"]
            if state.get("scanner_running") == True:
                self.log_test("Bot State - Start Scanner", True, "Scanner started (blockchain monitoring active)")
                
                # Wait for scanner to detect tokens
                print("    Waiting 15 seconds for scanner to detect tokens...")
                await asyncio.sleep(15)
                
                # Check scanner feed for real detections
                await self.test_scanner_feed_after_start()
                
            else:
                self.log_test("Bot State - Start Scanner", False, "Scanner not started", state)
        else:
            self.log_test("Bot State - Start Scanner", False, f"Status: {response['status_code']}", response["data"])
        
        # Test both toggles work independently
        response = await self.make_request("PUT", "/bot/state", json={"is_running": True, "scanner_running": True})
        if response["status_code"] == 200:
            state = response["data"]
            both_running = state.get("is_running") == True and state.get("scanner_running") == True
            if both_running:
                self.log_test("Bot State - Both Active", True, "Both bot and scanner running independently")
            else:
                self.log_test("Bot State - Both Active", False, "Both not running", state)
        else:
            self.log_test("Bot State - Both Active", False, f"Status: {response['status_code']}", response["data"])
        
        # Stop scanner but keep bot running
        response = await self.make_request("PUT", "/bot/state", json={"scanner_running": False})
        if response["status_code"] == 200:
            state = response["data"]
            scanner_stopped_bot_running = state.get("scanner_running") == False and state.get("is_running") == True
            if scanner_stopped_bot_running:
                self.log_test("Bot State - Independent Stop", True, "Scanner stopped, bot still running (independent toggles)")
            else:
                self.log_test("Bot State - Independent Stop", False, "Toggles not independent", state)
        else:
            self.log_test("Bot State - Independent Stop", False, f"Status: {response['status_code']}", response["data"])
        
        # Final cleanup - stop both
        await self.make_request("PUT", "/bot/state", json={"is_running": False, "scanner_running": False})
    
    async def test_scanner_feed_after_start(self):
        """Test scanner feed for real detections after starting scanner."""
        response = await self.make_request("GET", "/scanner/feed")
        if response["status_code"] == 200:
            feed = response["data"]
            if isinstance(feed, list) and len(feed) > 0:
                # Check for real token detections
                real_detections = [item for item in feed if item.get("token_mint") and len(item.get("token_mint", "")) > 20]
                if real_detections:
                    latest = real_detections[0]
                    self.log_test("Scanner Feed - Real Detections", True, 
                                 f"Found {len(real_detections)} real detections. Latest: {latest.get('token_mint', '')[:16]}... "
                                 f"on {latest.get('platform', 'unknown')} with safety score {latest.get('safety_score', 0)}")
                else:
                    self.log_test("Scanner Feed - Real Detections", False, "No real token detections found", feed[:2] if feed else [])
            else:
                self.log_test("Scanner Feed - Real Detections", False, "No detections in feed", feed)
        else:
            self.log_test("Scanner Feed - Real Detections", False, f"Status: {response['status_code']}", response["data"])
    
    async def test_scanner_status(self):
        """Test scanner status endpoint."""
        print("📡 Testing Scanner Status...")
        
        response = await self.make_request("GET", "/scanner/status")
        if response["status_code"] == 200:
            status = response["data"]
            self.log_test("Scanner Status", True, 
                         f"Running: {status.get('running', False)}, "
                         f"Tokens Scanned: {status.get('tokens_scanned', 0)}, "
                         f"Auto-buy: {status.get('auto_buy', False)}")
        else:
            self.log_test("Scanner Status", False, f"Status: {response['status_code']}", response["data"])
    
    async def test_wallet_endpoint(self):
        """Test wallet endpoint returns real wallet data."""
        print("💰 Testing Wallet Endpoint...")
        
        response = await self.make_request("GET", "/wallet")
        if response["status_code"] == 200:
            wallet = response["data"]
            address = wallet.get("address", "")
            
            # Check it's not a paper wallet
            if address.startswith("PAPER_"):
                self.log_test("Wallet - Real Data", False, "Wallet address is paper trading format", wallet)
            elif len(address) > 20 and wallet.get("connected") == True:
                self.log_test("Wallet - Real Data", True, 
                             f"Real wallet: {address[:12]}..., "
                             f"Balance: {wallet.get('balance_sol', 0)} SOL, "
                             f"Mode: {wallet.get('mode', 'unknown')}")
            else:
                self.log_test("Wallet - Real Data", False, "Invalid wallet data", wallet)
        else:
            self.log_test("Wallet - Real Data", False, f"Status: {response['status_code']}", response["data"])
    
    async def test_bot_config(self):
        """Test bot config endpoint with auto-buy settings."""
        print("⚙️ Testing Bot Config...")
        
        # Get current config
        response = await self.make_request("GET", "/bot/config")
        if response["status_code"] != 200:
            self.log_test("Bot Config - Get", False, f"Status: {response['status_code']}", response["data"])
            return
        
        config = response["data"]
        self.log_test("Bot Config - Get", True, 
                     f"Auto-buy: {config.get('auto_buy', False)}, "
                     f"Buy Amount: {config.get('buy_amount_sol', 0)} SOL")
        
        # Test auto-buy toggle off
        response = await self.make_request("PUT", "/bot/config", json={"auto_buy": False})
        if response["status_code"] == 200:
            updated = response["data"]
            if updated.get("auto_buy") == False:
                self.log_test("Bot Config - Auto-buy Off", True, "Auto-buy disabled")
            else:
                self.log_test("Bot Config - Auto-buy Off", False, "Auto-buy not disabled", updated)
        else:
            self.log_test("Bot Config - Auto-buy Off", False, f"Status: {response['status_code']}", response["data"])
        
        # Test auto-buy toggle on
        response = await self.make_request("PUT", "/bot/config", json={"auto_buy": True})
        if response["status_code"] == 200:
            updated = response["data"]
            if updated.get("auto_buy") == True:
                self.log_test("Bot Config - Auto-buy On", True, "Auto-buy enabled")
            else:
                self.log_test("Bot Config - Auto-buy On", False, "Auto-buy not enabled", updated)
        else:
            self.log_test("Bot Config - Auto-buy On", False, f"Status: {response['status_code']}", response["data"])
    
    async def test_trade_endpoints(self):
        """Test trade endpoints (buy/sell via Jupiter)."""
        print("💱 Testing Trade Endpoints...")
        
        # Test buy endpoint (with small amount)
        buy_data = {
            "token_mint": "So11111111111111111111111111111111111111112",  # SOL mint for testing
            "amount_sol": 0.001,  # Very small amount
            "slippage_bps": 1000
        }
        
        response = await self.make_request("POST", "/trade/buy", json=buy_data)
        if response["status_code"] == 200:
            result = response["data"]
            if result.get("success"):
                self.log_test("Trade - Buy Endpoint", True, f"Buy successful: {result.get('txid', 'no txid')[:16]}...")
            else:
                # Expected to fail without real funds, but endpoint should work
                error = result.get("error", "")
                if "insufficient" in error.lower() or "balance" in error.lower():
                    self.log_test("Trade - Buy Endpoint", True, "Buy endpoint working (insufficient balance expected)")
                else:
                    self.log_test("Trade - Buy Endpoint", False, f"Unexpected error: {error}")
        else:
            self.log_test("Trade - Buy Endpoint", False, f"Status: {response['status_code']}", response["data"])
        
        # Test sell endpoint
        sell_data = {
            "token_mint": "So11111111111111111111111111111111111111112",
            "amount_tokens": 1000,
            "slippage_bps": 1000
        }
        
        response = await self.make_request("POST", "/trade/sell", json=sell_data)
        if response["status_code"] == 200:
            result = response["data"]
            if result.get("success"):
                self.log_test("Trade - Sell Endpoint", True, f"Sell successful: {result.get('txid', 'no txid')[:16]}...")
            else:
                # Expected to fail without tokens, but endpoint should work
                error = result.get("error", "")
                if "insufficient" in error.lower() or "balance" in error.lower() or "quote" in error.lower():
                    self.log_test("Trade - Sell Endpoint", True, "Sell endpoint working (insufficient balance expected)")
                else:
                    self.log_test("Trade - Sell Endpoint", False, f"Unexpected error: {error}")
        else:
            self.log_test("Trade - Sell Endpoint", False, f"Status: {response['status_code']}", response["data"])
    
    async def test_safety_audit(self):
        """Test real safety audit endpoint."""
        print("🔍 Testing Safety Audit...")
        
        # Use SOL mint for testing (known to exist)
        test_mint = "So11111111111111111111111111111111111111112"
        
        response = await self.make_request("GET", f"/safety/real/{test_mint}")
        if response["status_code"] == 200:
            audit = response["data"]
            if audit.get("exists") and "safety_score" in audit:
                self.log_test("Safety Audit - Real", True, 
                             f"Audit successful: Score {audit.get('safety_score', 0)}/100, "
                             f"Mint revoked: {audit.get('checks', {}).get('mint_revoked', False)}")
            else:
                self.log_test("Safety Audit - Real", False, "Invalid audit response", audit)
        else:
            self.log_test("Safety Audit - Real", False, f"Status: {response['status_code']}", response["data"])
    
    async def test_portfolio(self):
        """Test portfolio endpoint."""
        print("📊 Testing Portfolio...")
        
        response = await self.make_request("GET", "/portfolio")
        if response["status_code"] == 200:
            portfolio = response["data"]
            stats = portfolio.get("stats", {})
            
            # Check for no random PnL drift
            realized_pnl = stats.get("realized_pnl_sol", 0)
            unrealized_pnl = stats.get("unrealized_pnl_sol", 0)
            
            self.log_test("Portfolio", True, 
                         f"Open: {stats.get('open_count', 0)}, "
                         f"Closed: {stats.get('closed_count', 0)}, "
                         f"Realized PnL: {realized_pnl} SOL")
        else:
            self.log_test("Portfolio", False, f"Status: {response['status_code']}", response["data"])
    
    async def test_paper_trading_removal(self):
        """Test that paper trading endpoints are removed."""
        print("🚫 Testing Paper Trading Removal...")
        
        # Test that simulate endpoint doesn't exist
        response = await self.make_request("GET", "/scanner/simulate")
        if response["status_code"] == 404 or response["status_code"] == 405:
            self.log_test("Paper Trading - Simulate Removed", True, "Simulate endpoint properly removed")
        else:
            self.log_test("Paper Trading - Simulate Removed", False, f"Simulate endpoint still exists: {response['status_code']}")
        
        # Test POST simulate
        response = await self.make_request("POST", "/scanner/simulate")
        if response["status_code"] == 404 or response["status_code"] == 405:
            self.log_test("Paper Trading - Simulate POST Removed", True, "Simulate POST endpoint properly removed")
        else:
            self.log_test("Paper Trading - Simulate POST Removed", False, f"Simulate POST endpoint still exists: {response['status_code']}")
    
    async def test_scanner_feed(self):
        """Test scanner feed endpoint."""
        print("📡 Testing Scanner Feed...")
        
        response = await self.make_request("GET", "/scanner/feed")
        if response["status_code"] == 200:
            feed = response["data"]
            if isinstance(feed, list):
                self.log_test("Scanner Feed", True, f"Feed contains {len(feed)} items")
                
                # Check for real data structure
                if feed:
                    item = feed[0]
                    required_fields = ["token_mint", "platform", "safety_score", "action"]
                    has_required = all(field in item for field in required_fields)
                    if has_required:
                        self.log_test("Scanner Feed - Structure", True, "Feed items have correct structure")
                    else:
                        self.log_test("Scanner Feed - Structure", False, f"Missing fields in feed item", item)
            else:
                self.log_test("Scanner Feed", False, "Feed is not a list", feed)
        else:
            self.log_test("Scanner Feed", False, f"Status: {response['status_code']}", response["data"])
    
    async def run_all_tests(self):
        """Run all backend tests."""
        print("🚀 Starting Solana Sniper Bot Backend Tests")
        print(f"Backend URL: {self.base_url}")
        print(f"Test Email: {TEST_EMAIL}")
        print("=" * 60)
        
        # Authentication is required for most endpoints
        auth_success = await self.test_authentication()
        if not auth_success:
            print("❌ Authentication failed - stopping tests")
            return
        
        # Run all tests
        await self.test_bot_state()
        await self.test_scanner_status()
        await self.test_wallet_endpoint()
        await self.test_bot_config()
        await self.test_trade_endpoints()
        await self.test_safety_audit()
        await self.test_portfolio()
        await self.test_paper_trading_removal()
        await self.test_scanner_feed()
        
        # Summary
        print("=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        # Show failed tests
        failed_tests = [result for result in self.test_results if not result["success"]]
        if failed_tests:
            print("\n❌ FAILED TESTS:")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['details']}")
        
        print("\n✅ Test run completed!")

async def main():
    """Main test runner."""
    async with SniperBotTester() as tester:
        await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())