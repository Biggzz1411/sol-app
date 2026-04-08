"""
Backend tests for SOL Payment Flow.
Tests: SOL payment initiate, verify (pending), Stripe checkout placeholder, premium plans with SOL pricing.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')

class TestPremiumPlansWithSOL:
    """Premium plans endpoint with SOL pricing"""
    
    def test_premium_plans_structure(self):
        """Verify plans endpoint returns all required fields for SOL payments"""
        response = requests.get(f"{BASE_URL}/api/premium/plans")
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level structure
        assert "plans" in data
        assert "free_limits" in data
        assert "premium_limits" in data
        assert "owner_wallet" in data
        assert "payment_methods" in data
        
        # Verify owner wallet
        assert data["owner_wallet"] == "8YjBBpAg8W3d8Juzrp7Xicga8wLe6sFwPphtswwJxgx9"
        
        # Verify payment methods
        assert "sol" in data["payment_methods"]
        assert "stripe" in data["payment_methods"]
        
        print(f"✓ Premium plans endpoint returns owner_wallet: {data['owner_wallet']}")
        print(f"✓ Payment methods: {data['payment_methods']}")
    
    def test_monthly_plan_sol_pricing(self):
        """Verify monthly plan has correct SOL pricing"""
        response = requests.get(f"{BASE_URL}/api/premium/plans")
        data = response.json()
        
        monthly = data["plans"]["monthly"]
        assert "price_sol" in monthly
        assert "price_usd" in monthly
        assert monthly["price_sol"] == 0.2
        assert monthly["price_usd"] == 29.00
        assert monthly["duration_days"] == 30
        
        print(f"✓ Monthly plan: {monthly['price_sol']} SOL (~${monthly['price_usd']} USD)")
    
    def test_quarterly_plan_sol_pricing(self):
        """Verify quarterly plan has correct SOL pricing"""
        response = requests.get(f"{BASE_URL}/api/premium/plans")
        data = response.json()
        
        quarterly = data["plans"]["quarterly"]
        assert "price_sol" in quarterly
        assert "price_usd" in quarterly
        assert quarterly["price_sol"] == 0.5
        assert quarterly["price_usd"] == 69.00
        assert quarterly["duration_days"] == 90
        assert "save_pct" in quarterly
        assert quarterly["save_pct"] == 17
        
        print(f"✓ Quarterly plan: {quarterly['price_sol']} SOL (~${quarterly['price_usd']} USD) - Save {quarterly['save_pct']}%")


class TestSOLPaymentInitiate:
    """SOL payment initiation flow"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token for authenticated requests"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@sniperbot.io",
            "password": "SniperAdmin123!"
        })
        return login_res.json()["token"]
    
    def test_initiate_sol_payment_requires_auth(self):
        """Verify SOL payment initiation requires authentication"""
        response = requests.post(f"{BASE_URL}/api/premium/sol/initiate", json={
            "plan_id": "monthly"
        })
        assert response.status_code == 401
        print("✓ POST /api/premium/sol/initiate requires authentication")
    
    def test_initiate_sol_payment_invalid_plan(self, admin_token):
        """Verify invalid plan_id is rejected"""
        response = requests.post(f"{BASE_URL}/api/premium/sol/initiate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"plan_id": "invalid_plan"}
        )
        assert response.status_code == 400
        assert "invalid plan" in response.json()["detail"].lower()
        print("✓ SOL payment initiate rejects invalid plan_id")
    
    def test_initiate_sol_payment_monthly(self, admin_token):
        """Verify SOL payment initiation for monthly plan"""
        response = requests.post(f"{BASE_URL}/api/premium/sol/initiate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"plan_id": "monthly"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "order_id" in data
        assert "wallet_address" in data
        assert "amount_sol" in data
        assert "amount_lamports" in data
        assert "plan" in data
        assert "expires_in_minutes" in data
        
        # Verify wallet address
        assert data["wallet_address"] == "8YjBBpAg8W3d8Juzrp7Xicga8wLe6sFwPphtswwJxgx9"
        
        # Verify amount is close to 0.2 SOL (with unique suffix)
        assert 0.2 <= data["amount_sol"] <= 0.201  # Base 0.2 + small suffix
        
        # Verify lamports match SOL amount
        expected_lamports = int(data["amount_sol"] * 1_000_000_000)
        assert data["amount_lamports"] == expected_lamports
        
        # Verify plan details
        assert data["plan"]["label"] == "Premium Monthly"
        assert data["plan"]["price_sol"] == 0.2
        assert data["plan"]["duration_days"] == 30
        
        # Verify expiry
        assert data["expires_in_minutes"] == 30
        
        print(f"✓ SOL payment initiated for monthly plan")
        print(f"  Order ID: {data['order_id'][:16]}...")
        print(f"  Amount: {data['amount_sol']} SOL ({data['amount_lamports']} lamports)")
        print(f"  Wallet: {data['wallet_address']}")
        
        return data["order_id"]  # Return for verify test
    
    def test_initiate_sol_payment_quarterly(self, admin_token):
        """Verify SOL payment initiation for quarterly plan"""
        response = requests.post(f"{BASE_URL}/api/premium/sol/initiate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"plan_id": "quarterly"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify amount is close to 0.5 SOL (with unique suffix)
        assert 0.5 <= data["amount_sol"] <= 0.501
        
        # Verify plan details
        assert data["plan"]["label"] == "Premium Quarterly"
        assert data["plan"]["price_sol"] == 0.5
        assert data["plan"]["duration_days"] == 90
        
        print(f"✓ SOL payment initiated for quarterly plan: {data['amount_sol']} SOL")


class TestSOLPaymentVerify:
    """SOL payment verification flow"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token for authenticated requests"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@sniperbot.io",
            "password": "SniperAdmin123!"
        })
        return login_res.json()["token"]
    
    @pytest.fixture
    def payment_order(self, admin_token):
        """Create a payment order for testing"""
        response = requests.post(f"{BASE_URL}/api/premium/sol/initiate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"plan_id": "monthly"}
        )
        return response.json()
    
    def test_verify_sol_payment_requires_auth(self, payment_order):
        """Verify SOL payment verification requires authentication"""
        response = requests.post(f"{BASE_URL}/api/premium/sol/verify/{payment_order['order_id']}")
        assert response.status_code == 401
        print("✓ POST /api/premium/sol/verify requires authentication")
    
    def test_verify_sol_payment_not_found(self, admin_token):
        """Verify non-existent order returns 404"""
        fake_order_id = "00000000-0000-0000-0000-000000000000"
        response = requests.post(f"{BASE_URL}/api/premium/sol/verify/{fake_order_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
        print("✓ SOL payment verify returns 404 for non-existent order")
    
    def test_verify_sol_payment_pending(self, admin_token, payment_order):
        """Verify SOL payment returns pending when no payment sent"""
        # Since we're not actually sending SOL, verification should return pending
        response = requests.post(f"{BASE_URL}/api/premium/sol/verify/{payment_order['order_id']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return pending status since no real payment was made
        assert data["status"] == "pending"
        assert "message" in data
        assert "not yet detected" in data["message"].lower() or "not detected" in data["message"].lower()
        
        # Should include payment details for retry
        assert "wallet_address" in data
        assert "expected_sol" in data
        assert data["wallet_address"] == "8YjBBpAg8W3d8Juzrp7Xicga8wLe6sFwPphtswwJxgx9"
        
        print(f"✓ SOL payment verify returns pending (no real payment sent)")
        print(f"  Status: {data['status']}")
        print(f"  Message: {data['message']}")


class TestSOLPaymentOrders:
    """SOL payment orders listing"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token for authenticated requests"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@sniperbot.io",
            "password": "SniperAdmin123!"
        })
        return login_res.json()["token"]
    
    def test_get_sol_orders_requires_auth(self):
        """Verify SOL orders endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/premium/sol/orders")
        assert response.status_code == 401
        print("✓ GET /api/premium/sol/orders requires authentication")
    
    def test_get_sol_orders(self, admin_token):
        """Verify SOL orders endpoint returns user's orders"""
        # Create an order first
        requests.post(f"{BASE_URL}/api/premium/sol/initiate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"plan_id": "monthly"}
        )
        
        # Get orders
        response = requests.get(f"{BASE_URL}/api/premium/sol/orders",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "orders" in data
        assert isinstance(data["orders"], list)
        
        if len(data["orders"]) > 0:
            order = data["orders"][0]
            assert "order_id" in order
            assert "plan_id" in order
            assert "expected_sol" in order
            assert "owner_wallet" in order
            assert "status" in order
            assert "created_at" in order
            print(f"✓ GET /api/premium/sol/orders returns {len(data['orders'])} order(s)")
        else:
            print("✓ GET /api/premium/sol/orders returns empty list (no orders yet)")


class TestStripeCheckoutPlaceholder:
    """Stripe checkout placeholder (not fully configured)"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token for authenticated requests"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@sniperbot.io",
            "password": "SniperAdmin123!"
        })
        return login_res.json()["token"]
    
    def test_stripe_checkout_returns_use_sol_message(self, admin_token):
        """Verify Stripe checkout returns 'use SOL' message when not configured"""
        response = requests.post(f"{BASE_URL}/api/premium/checkout",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "plan_id": "monthly",
                "origin_url": "https://app-builder-4154.preview.emergentagent.com"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return error message telling user to use SOL
        assert "error" in data or "use_sol" in data
        
        if "error" in data:
            assert "sol" in data["error"].lower()
            assert "coming soon" in data["error"].lower() or "use sol" in data["error"].lower()
        
        if "use_sol" in data:
            assert data["use_sol"] == True
        
        print(f"✓ Stripe checkout returns 'use SOL' message (Stripe not configured)")
        print(f"  Response: {data}")


class TestAdminPremiumStatus:
    """Verify admin has premium active"""
    
    def test_admin_has_premium_active(self):
        """Verify admin user has premium subscription active"""
        # Login as admin
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@sniperbot.io",
            "password": "SniperAdmin123!"
        })
        assert login_res.status_code == 200
        
        token = login_res.json()["token"]
        
        # Get user info
        me_res = requests.get(f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_res.status_code == 200
        data = me_res.json()
        
        # Verify admin has premium
        assert data["role"] == "admin"
        assert data["is_premium"] == True
        assert data["subscription"]["status"] == "active"
        assert data["subscription"]["plan"] == "admin"
        
        # Verify premium limits
        assert data["limits"]["max_wallets"] == 10
        assert data["limits"]["scan_interval_ms"] == 5000
        assert data["limits"]["live_trading"] == True
        assert data["limits"]["push_alerts"] == True
        assert data["limits"]["max_open_positions"] == 20
        
        print(f"✓ Admin user has premium active")
        print(f"  Role: {data['role']}")
        print(f"  Premium: {data['is_premium']}")
        print(f"  Plan: {data['subscription']['plan']}")
        print(f"  Max wallets: {data['limits']['max_wallets']}")
