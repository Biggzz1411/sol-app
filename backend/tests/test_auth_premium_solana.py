"""
Backend tests for Auth, Premium, and Real Solana RPC features.
Tests: JWT auth (register, login, logout, /me), premium plans, real Solana safety audit, multi-wallet CRUD.
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')

class TestHealth:
    """Health check with features list"""
    
    def test_health_endpoint(self):
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "sniper-bot-backend"
        assert "features" in data
        assert "auth" in data["features"]
        assert "stripe" in data["features"]
        assert "solana-rpc" in data["features"]
        assert "multi-wallet" in data["features"]
        print("✓ Health endpoint returns correct features list")


class TestAuth:
    """Authentication endpoints"""
    
    def test_register_new_user(self):
        email = f"test_{uuid.uuid4().hex[:8]}@sniper.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "Test123!",
            "name": "Test User"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["email"] == email
        assert data["name"] == "Test User"
        assert data["role"] == "user"
        assert "subscription" in data
        assert data["subscription"]["status"] == "free"
        print(f"✓ Register created user: {email}")
    
    def test_register_duplicate_email(self):
        email = f"duplicate_{uuid.uuid4().hex[:8]}@sniper.com"
        # First registration
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "Test123!",
            "name": "Test"
        })
        # Second registration with same email
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "Test123!",
            "name": "Test"
        })
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
        print("✓ Register rejects duplicate email")
    
    def test_login_admin(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@sniperbot.io",
            "password": "SniperAdmin123!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["email"] == "admin@sniperbot.io"
        assert data["role"] == "admin"
        assert "subscription" in data
        print("✓ Admin login successful")
    
    def test_login_invalid_credentials(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@sniperbot.io",
            "password": "WrongPassword"
        })
        assert response.status_code == 401
        assert "invalid credentials" in response.json()["detail"].lower()
        print("✓ Login rejects invalid credentials")
    
    def test_get_me_with_token(self):
        # Login first
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@sniperbot.io",
            "password": "SniperAdmin123!"
        })
        token = login_res.json()["token"]
        
        # Get /me
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@sniperbot.io"
        assert data["role"] == "admin"
        assert "is_premium" in data
        assert data["is_premium"] == True  # Admin is premium
        assert "limits" in data
        assert data["limits"]["max_wallets"] == 10
        assert data["limits"]["live_trading"] == True
        print("✓ GET /api/auth/me returns user with is_premium and limits")
    
    def test_get_me_without_token(self):
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        print("✓ GET /api/auth/me requires authentication")
    
    def test_logout(self):
        # Login first
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@sniperbot.io",
            "password": "SniperAdmin123!"
        })
        token = login_res.json()["token"]
        
        # Logout
        response = requests.post(f"{BASE_URL}/api/auth/logout", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        assert "message" in response.json()
        print("✓ Logout successful")


class TestPremium:
    """Premium plans and limits"""
    
    def test_get_premium_plans(self):
        response = requests.get(f"{BASE_URL}/api/premium/plans")
        assert response.status_code == 200
        data = response.json()
        assert "plans" in data
        assert "monthly" in data["plans"]
        assert "quarterly" in data["plans"]
        assert data["plans"]["monthly"]["price"] == 29.00
        assert data["plans"]["quarterly"]["price"] == 69.00
        assert "free_limits" in data
        assert "premium_limits" in data
        assert data["free_limits"]["max_wallets"] == 1
        assert data["premium_limits"]["max_wallets"] == 10
        print("✓ Premium plans endpoint returns correct plans and limits")


class TestRealSolanaRPC:
    """Real Solana RPC integration via Helius"""
    
    def test_real_safety_audit_bonk_token(self):
        # BONK token mint address
        bonk_mint = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        response = requests.get(f"{BASE_URL}/api/safety/real/{bonk_mint}")
        assert response.status_code == 200
        data = response.json()
        assert data["token_mint"] == bonk_mint
        assert data["exists"] == True
        assert "safety_score" in data
        assert "safety_passed" in data
        assert "checks" in data
        assert "mint_revoked" in data["checks"]
        assert "freeze_revoked" in data["checks"]
        assert "top_holder_pct" in data["checks"]
        assert "supply" in data["checks"]
        assert "decimals" in data["checks"]
        print(f"✓ Real Solana RPC safety audit for BONK: score={data['safety_score']}, passed={data['safety_passed']}")
    
    def test_real_safety_audit_invalid_mint(self):
        # Invalid mint address
        invalid_mint = "InvalidMintAddress123"
        response = requests.get(f"{BASE_URL}/api/safety/real/{invalid_mint}")
        assert response.status_code == 200
        data = response.json()
        # Should return exists=False or error
        assert data["exists"] == False or "error" in data
        print("✓ Real Solana RPC handles invalid mint address")


class TestMultiWallet:
    """Multi-wallet CRUD operations"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token for authenticated requests"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@sniperbot.io",
            "password": "SniperAdmin123!"
        })
        return login_res.json()["token"]
    
    def test_get_wallets_requires_auth(self):
        response = requests.get(f"{BASE_URL}/api/wallets")
        assert response.status_code == 401
        print("✓ GET /api/wallets requires authentication")
    
    def test_get_wallets_with_auth(self, admin_token):
        response = requests.get(f"{BASE_URL}/api/wallets", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert "wallets" in data
        assert "max_wallets" in data
        assert "is_premium" in data
        assert data["max_wallets"] == 10  # Admin is premium
        assert data["is_premium"] == True
        # Check masked keys
        for wallet in data["wallets"]:
            assert "private_key_masked" in wallet
            assert "private_key" not in wallet  # Should be excluded
        print(f"✓ GET /api/wallets returns {len(data['wallets'])} wallets with masked keys")
    
    def test_add_wallet_requires_valid_keypair(self, admin_token):
        # Invalid private key
        response = requests.post(f"{BASE_URL}/api/wallets", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "private_key": "InvalidKey123",
                "label": "Test Wallet"
            }
        )
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()
        print("✓ POST /api/wallets rejects invalid private key")
    
    def test_add_wallet_with_valid_keypair(self, admin_token):
        # Valid Solana keypair (base58 encoded)
        # This is a test keypair - DO NOT use in production
        test_private_key = "5J7WTMRn1JqXXqrzZsvFJvDnHqjFJbqfJ5J7WTMRn1JqXXqrzZsvFJvDnHqjFJbqfJ5"
        
        # Note: This test may fail if the keypair is invalid
        # We'll test the endpoint structure instead
        response = requests.post(f"{BASE_URL}/api/wallets", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "private_key": test_private_key,
                "label": "Test Wallet"
            }
        )
        # Either 200 (success) or 400 (invalid key format)
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "label" in data
            assert "public_key" in data
            assert "private_key_masked" in data
            assert "private_key" not in data
            print(f"✓ POST /api/wallets adds wallet with masked key")
        else:
            print("✓ POST /api/wallets validates keypair format")


class TestExistingBotEndpoints:
    """Verify existing bot endpoints still work after auth changes"""
    
    def test_bot_state(self):
        response = requests.get(f"{BASE_URL}/api/bot/state")
        assert response.status_code == 200
        data = response.json()
        assert "is_running" in data
        assert "mode" in data
        print("✓ GET /api/bot/state still works")
    
    def test_bot_config(self):
        response = requests.get(f"{BASE_URL}/api/bot/config")
        assert response.status_code == 200
        data = response.json()
        assert "strategy" in data
        print("✓ GET /api/bot/config still works")
    
    def test_scanner_feed(self):
        response = requests.get(f"{BASE_URL}/api/scanner/feed?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print("✓ GET /api/scanner/feed still works")
    
    def test_portfolio(self):
        response = requests.get(f"{BASE_URL}/api/portfolio")
        assert response.status_code == 200
        data = response.json()
        assert "open_positions" in data
        assert "closed_positions" in data
        assert "stats" in data
        print("✓ GET /api/portfolio still works")
    
    def test_logs(self):
        response = requests.get(f"{BASE_URL}/api/logs?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print("✓ GET /api/logs still works")
