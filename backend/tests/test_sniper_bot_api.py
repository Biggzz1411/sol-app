"""
Backend API Tests for Solana Sniper Bot
Tests: Health, Bot State, Bot Config, Scanner, Portfolio, Logs, Wallet, Stats
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL').rstrip('/')

class TestHealth:
    """Health check endpoint"""
    
    def test_health_endpoint(self):
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "sniper-bot-backend"
        print("✓ Health check passed")


class TestBotState:
    """Bot state management tests"""
    
    def test_get_bot_state(self):
        response = requests.get(f"{BASE_URL}/api/bot/state")
        assert response.status_code == 200
        data = response.json()
        assert "is_running" in data
        assert "mode" in data
        assert data["mode"] in ["paper", "live"]
        print(f"✓ Bot state retrieved: running={data['is_running']}, mode={data['mode']}")
    
    def test_update_bot_state_start(self):
        # Start the bot
        response = requests.put(
            f"{BASE_URL}/api/bot/state",
            json={"is_running": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] == True
        assert "started_at" in data
        print("✓ Bot started successfully")
        
        # Verify persistence
        get_response = requests.get(f"{BASE_URL}/api/bot/state")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["is_running"] == True
        print("✓ Bot state persisted correctly")
    
    def test_update_bot_state_mode(self):
        # Change mode to live
        response = requests.put(
            f"{BASE_URL}/api/bot/state",
            json={"mode": "live"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "live"
        print("✓ Bot mode changed to live")
        
        # Change back to paper
        response = requests.put(
            f"{BASE_URL}/api/bot/state",
            json={"mode": "paper"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "paper"
        print("✓ Bot mode changed back to paper")


class TestBotConfig:
    """Bot configuration tests"""
    
    def test_get_bot_config(self):
        response = requests.get(f"{BASE_URL}/api/bot/config")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "strategy" in data
        assert "buy_amount_sol" in data
        assert "slippage_bps" in data
        assert "max_open_positions" in data
        assert "platform_pumpfun" in data
        assert "platform_raydium" in data
        assert "platform_pumpswap" in data
        print(f"✓ Config retrieved: strategy={data['strategy']}, buy_amount={data['buy_amount_sol']}")
    
    def test_update_bot_config(self):
        # Update config
        update_payload = {
            "strategy": "aggressive",
            "buy_amount_sol": 0.1,
            "max_open_positions": 10
        }
        response = requests.put(
            f"{BASE_URL}/api/bot/config",
            json=update_payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["strategy"] == "aggressive"
        assert data["buy_amount_sol"] == 0.1
        assert data["max_open_positions"] == 10
        print("✓ Config updated successfully")
        
        # Verify persistence
        get_response = requests.get(f"{BASE_URL}/api/bot/config")
        get_data = get_response.json()
        assert get_data["strategy"] == "aggressive"
        assert get_data["buy_amount_sol"] == 0.1
        print("✓ Config changes persisted")
        
        # Reset to balanced
        requests.put(
            f"{BASE_URL}/api/bot/config",
            json={"strategy": "balanced", "buy_amount_sol": 0.05, "max_open_positions": 5}
        )


class TestScanner:
    """Scanner feed and simulation tests"""
    
    def test_get_scanner_feed(self):
        response = requests.get(f"{BASE_URL}/api/scanner/feed?limit=50")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Scanner feed retrieved: {len(data)} detections")
    
    def test_simulate_detection_bot_not_running(self):
        # Stop bot first
        requests.put(f"{BASE_URL}/api/bot/state", json={"is_running": False})
        
        response = requests.post(f"{BASE_URL}/api/scanner/simulate")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"] == "Bot is not running"
        print("✓ Simulate correctly requires bot to be running")
    
    def test_simulate_detection_success(self):
        # Start bot
        requests.put(f"{BASE_URL}/api/bot/state", json={"is_running": True})
        time.sleep(0.5)
        
        # Simulate detection
        response = requests.post(f"{BASE_URL}/api/scanner/simulate")
        assert response.status_code == 200
        data = response.json()
        
        # Verify detection structure
        assert "token_mint" in data
        assert "token_name" in data
        assert "platform" in data
        assert "safety_score" in data
        assert "action" in data
        assert data["action"] in ["sniped", "rejected"]
        assert data["platform"] in ["pump.fun", "raydium", "pumpswap"]
        print(f"✓ Detection simulated: {data['token_name']} - {data['action']} (score: {data['safety_score']})")
        
        # Verify it appears in feed
        feed_response = requests.get(f"{BASE_URL}/api/scanner/feed?limit=10")
        feed_data = feed_response.json()
        assert len(feed_data) > 0
        latest = feed_data[0]
        assert latest["token_mint"] == data["token_mint"]
        print("✓ Detection appears in scanner feed")


class TestPortfolio:
    """Portfolio and position tests"""
    
    def test_get_portfolio(self):
        response = requests.get(f"{BASE_URL}/api/portfolio")
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "open_positions" in data
        assert "closed_positions" in data
        assert "stats" in data
        assert isinstance(data["open_positions"], list)
        assert isinstance(data["closed_positions"], list)
        
        stats = data["stats"]
        assert "total_sniped" in stats
        assert "win_rate" in stats
        assert "realized_pnl_sol" in stats
        assert "unrealized_pnl_sol" in stats
        print(f"✓ Portfolio retrieved: {stats['total_sniped']} sniped, {stats['open_count']} open, {stats['closed_count']} closed")
    
    def test_close_position(self):
        # Get open positions
        portfolio_response = requests.get(f"{BASE_URL}/api/portfolio")
        portfolio_data = portfolio_response.json()
        open_positions = portfolio_data["open_positions"]
        
        if len(open_positions) == 0:
            # Create a position first by simulating
            requests.put(f"{BASE_URL}/api/bot/state", json={"is_running": True})
            for _ in range(5):
                sim_response = requests.post(f"{BASE_URL}/api/scanner/simulate")
                sim_data = sim_response.json()
                if sim_data.get("action") == "sniped":
                    break
                time.sleep(0.3)
            
            # Refresh portfolio
            portfolio_response = requests.get(f"{BASE_URL}/api/portfolio")
            portfolio_data = portfolio_response.json()
            open_positions = portfolio_data["open_positions"]
        
        if len(open_positions) > 0:
            position_id = open_positions[0]["id"]
            
            # Close position
            response = requests.post(f"{BASE_URL}/api/portfolio/close/{position_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "closed"
            assert data["close_reason"] == "manual_close"
            print(f"✓ Position closed: {data['token_name']}")
            
            # Verify it moved to closed
            verify_response = requests.get(f"{BASE_URL}/api/portfolio")
            verify_data = verify_response.json()
            closed_ids = [p["id"] for p in verify_data["closed_positions"]]
            assert position_id in closed_ids
            print("✓ Position moved to closed list")
        else:
            print("⚠ No open positions to test close (all simulations rejected)")


class TestLogs:
    """Activity logs tests"""
    
    def test_get_logs(self):
        response = requests.get(f"{BASE_URL}/api/logs?limit=100")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            log_entry = data[0]
            assert "level" in log_entry
            assert "message" in log_entry
            assert "timestamp" in log_entry
            print(f"✓ Logs retrieved: {len(data)} entries")
        else:
            print("✓ Logs endpoint working (empty)")
    
    def test_clear_logs(self):
        response = requests.delete(f"{BASE_URL}/api/logs")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print("✓ Logs cleared")
        
        # Verify logs are empty
        get_response = requests.get(f"{BASE_URL}/api/logs")
        get_data = get_response.json()
        assert len(get_data) == 0
        print("✓ Logs confirmed empty after clear")


class TestWallet:
    """Wallet endpoint tests"""
    
    def test_get_wallet(self):
        response = requests.get(f"{BASE_URL}/api/wallet")
        assert response.status_code == 200
        data = response.json()
        
        assert "address" in data
        assert "balance_sol" in data
        assert "mode" in data
        assert data["mode"] in ["paper", "live"]
        print(f"✓ Wallet retrieved: {data['balance_sol']} SOL, mode={data['mode']}")


class TestStats:
    """Stats endpoint tests"""
    
    def test_get_stats(self):
        response = requests.get(f"{BASE_URL}/api/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "is_running" in data
        assert "mode" in data
        assert "tokens_scanned" in data
        assert "tokens_sniped" in data
        assert "open_positions" in data
        assert "closed_positions" in data
        print(f"✓ Stats retrieved: {data['tokens_scanned']} scanned, {data['tokens_sniped']} sniped")


class TestSafetyAudit:
    """Safety audit endpoint tests"""
    
    def test_get_safety_audit(self):
        # Get a token from feed first
        feed_response = requests.get(f"{BASE_URL}/api/scanner/feed?limit=1")
        feed_data = feed_response.json()
        
        if len(feed_data) > 0:
            token_mint = feed_data[0]["token_mint"]
            
            response = requests.get(f"{BASE_URL}/api/safety/{token_mint}")
            assert response.status_code == 200
            data = response.json()
            
            assert "token_mint" in data
            assert "safety_score" in data
            assert "checks" in data
            checks = data["checks"]
            assert "mint_revoked" in checks
            assert "freeze_revoked" in checks
            assert "lp_burned" in checks
            print(f"✓ Safety audit retrieved for {data['token_name']}: score={data['safety_score']}")
        else:
            print("⚠ No tokens in feed to test safety audit")
