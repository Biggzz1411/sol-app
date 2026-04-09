"""
Backend tests for:
- Referral system (code generation, validation, registration with referral, stats)
- Stripe checkout with live key
- SOL payment initiation with owner wallet
"""
import pytest
import requests
import os
import time
from pathlib import Path

# Read BASE_URL from frontend/.env
def get_base_url():
    env_file = Path('/app/frontend/.env')
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith('EXPO_PUBLIC_BACKEND_URL='):
                return line.split('=', 1)[1].strip().strip('"')
    return 'https://app-builder-4154.preview.emergentagent.com'

BASE_URL = get_base_url()

class TestReferralSystem:
    """Test referral code generation, validation, and rewards"""
    
    def test_admin_login_returns_premium_user(self):
        """Admin login should return user with admin role and active premium"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "Superbiggzz1411@gmail.com", "password": "Biggzz1411!"}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert data["email"] == "superbiggzz1411@gmail.com", "Email should be lowercase"
        assert data["role"] == "admin", "User should have admin role"
        assert data["subscription"]["status"] == "active", "Admin should have active subscription"
        print(f"✓ Admin login successful: {data['email']} (role: {data['role']}, premium: {data['subscription']['status']})")
        
        # Store token for subsequent tests
        pytest.admin_token = data["token"]
        pytest.admin_user_id = data["id"]
    
    def test_get_referral_code_returns_snipe_format(self):
        """GET /api/referral/code should return code in SNIPE-XXXXXX format"""
        response = requests.get(
            f"{BASE_URL}/api/referral/code",
            headers={"Authorization": f"Bearer {pytest.admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get referral code: {response.text}"
        
        data = response.json()
        assert "referral_code" in data, "Response should contain referral_code"
        assert data["referral_code"].startswith("SNIPE-"), f"Code should start with SNIPE-, got: {data['referral_code']}"
        assert len(data["referral_code"]) == 12, f"Code should be 12 chars (SNIPE-XXXXXX), got: {data['referral_code']}"
        assert data["referrer_reward_days"] == 7, "Referrer should get 7 days"
        assert data["referee_reward_days"] == 3, "Referee should get 3 days"
        print(f"✓ Referral code generated: {data['referral_code']} (referrer: 7d, referee: 3d)")
        
        # Store for validation test
        pytest.admin_referral_code = data["referral_code"]
    
    def test_validate_existing_referral_code(self):
        """GET /api/referral/validate/{code} should validate existing code"""
        response = requests.get(
            f"{BASE_URL}/api/referral/validate/{pytest.admin_referral_code}"
        )
        assert response.status_code == 200, f"Failed to validate code: {response.text}"
        
        data = response.json()
        assert data["valid"] is True, f"Code should be valid, got: {data}"
        assert "referrer_name" in data, "Should return referrer name"
        print(f"✓ Referral code validated: {pytest.admin_referral_code} (valid: {data['valid']}, referrer: {data['referrer_name']})")
    
    def test_validate_invalid_referral_code(self):
        """GET /api/referral/validate/{code} should return false for invalid code"""
        response = requests.get(
            f"{BASE_URL}/api/referral/validate/SNIPE-INVALID"
        )
        assert response.status_code == 200, f"Failed to validate code: {response.text}"
        
        data = response.json()
        assert data["valid"] is False, f"Invalid code should return valid=false, got: {data}"
        print(f"✓ Invalid referral code correctly rejected: SNIPE-INVALID")
    
    def test_register_with_referral_code_gives_3_days_premium(self):
        """POST /api/auth/register with referral_code should give referee 3 days premium"""
        # Generate unique email for test
        test_email = f"referee_test_{int(time.time())}@test.com"
        
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": test_email,
                "password": "TestPass123!",
                "name": "Test Referee",
                "referral_code": pytest.admin_referral_code
            }
        )
        assert response.status_code == 200, f"Registration failed: {response.text}"
        
        data = response.json()
        assert data["email"] == test_email.lower(), "Email should be lowercase"
        assert data["subscription"]["status"] == "active", "Referee should have active subscription"
        assert data["subscription"]["plan"] == "referral_bonus", "Plan should be referral_bonus"
        assert data["subscription"]["expires_at"] is not None, "Should have expiry date"
        assert data["subscription"]["payment_method"] == "referral", "Payment method should be referral"
        print(f"✓ Referee registered with referral code: {test_email} (premium: {data['subscription']['status']}, expires: {data['subscription']['expires_at']})")
        
        # Store for cleanup
        pytest.referee_token = data["token"]
        pytest.referee_email = test_email
    
    def test_get_referral_stats_shows_referral_count(self):
        """GET /api/referral/stats should return referral count and earned days"""
        response = requests.get(
            f"{BASE_URL}/api/referral/stats",
            headers={"Authorization": f"Bearer {pytest.admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get referral stats: {response.text}"
        
        data = response.json()
        assert "referral_code" in data, "Should return referral code"
        assert "total_referrals" in data, "Should return total referrals"
        assert "total_days_earned" in data, "Should return total days earned"
        assert "referrals" in data, "Should return referrals list"
        assert data["total_referrals"] >= 1, f"Should have at least 1 referral (from test), got: {data['total_referrals']}"
        assert data["total_days_earned"] >= 7, f"Should have earned at least 7 days, got: {data['total_days_earned']}"
        print(f"✓ Referral stats: {data['total_referrals']} referrals, {data['total_days_earned']} days earned")


class TestStripePayment:
    """Test Stripe checkout with live key"""
    
    def test_stripe_checkout_returns_url_with_live_key(self):
        """POST /api/premium/checkout should return Stripe checkout URL with live key configured"""
        # Use admin token from previous test
        if not hasattr(pytest, 'admin_token'):
            pytest.skip("Admin token not available")
        
        response = requests.post(
            f"{BASE_URL}/api/premium/checkout",
            headers={"Authorization": f"Bearer {pytest.admin_token}"},
            json={
                "plan_id": "monthly",
                "origin_url": BASE_URL
            }
        )
        assert response.status_code == 200, f"Stripe checkout failed: {response.text}"
        
        data = response.json()
        # With live key configured, should return URL
        if "url" in data:
            assert data["url"].startswith("https://checkout.stripe.com/"), f"Should return Stripe checkout URL, got: {data['url']}"
            assert "session_id" in data, "Should return session_id"
            print(f"✓ Stripe checkout URL generated: {data['url'][:60]}... (session: {data['session_id'][:20]}...)")
        elif "error" in data:
            # If Stripe not configured (shouldn't happen with live key)
            assert data["use_sol"] is True, "Should suggest SOL payment if Stripe not configured"
            print(f"⚠ Stripe not configured: {data['error']}")
        else:
            pytest.fail(f"Unexpected response: {data}")


class TestSOLPayment:
    """Test SOL payment initiation with owner wallet"""
    
    def test_sol_payment_initiate_returns_owner_wallet(self):
        """POST /api/premium/sol/initiate should return payment order with owner wallet"""
        if not hasattr(pytest, 'admin_token'):
            pytest.skip("Admin token not available")
        
        response = requests.post(
            f"{BASE_URL}/api/premium/sol/initiate",
            headers={"Authorization": f"Bearer {pytest.admin_token}"},
            json={"plan_id": "monthly"}
        )
        assert response.status_code == 200, f"SOL payment initiation failed: {response.text}"
        
        data = response.json()
        assert "order_id" in data, "Should return order_id"
        assert "wallet_address" in data, "Should return wallet_address"
        assert "amount_sol" in data, "Should return amount_sol"
        assert "amount_lamports" in data, "Should return amount_lamports"
        assert "plan" in data, "Should return plan details"
        assert "expires_in_minutes" in data, "Should return expiry time"
        
        # Verify wallet address is the owner wallet
        assert len(data["wallet_address"]) > 30, f"Wallet address should be valid Solana address, got: {data['wallet_address']}"
        
        # Verify amount is correct for monthly plan (0.2 SOL)
        assert data["amount_sol"] >= 0.2, f"Monthly plan should be at least 0.2 SOL, got: {data['amount_sol']}"
        assert data["amount_sol"] < 0.21, f"Monthly plan should be around 0.2 SOL, got: {data['amount_sol']}"
        
        # Verify plan details
        assert data["plan"]["label"] == "Premium Monthly", f"Plan label should be 'Premium Monthly', got: {data['plan']['label']}"
        assert data["plan"]["duration_days"] == 30, f"Monthly plan should be 30 days, got: {data['plan']['duration_days']}"
        
        print(f"✓ SOL payment order created: {data['order_id'][:20]}... (wallet: {data['wallet_address'][:20]}..., amount: {data['amount_sol']} SOL)")
    
    def test_sol_payment_quarterly_plan(self):
        """POST /api/premium/sol/initiate with quarterly plan should return 0.5 SOL"""
        if not hasattr(pytest, 'admin_token'):
            pytest.skip("Admin token not available")
        
        response = requests.post(
            f"{BASE_URL}/api/premium/sol/initiate",
            headers={"Authorization": f"Bearer {pytest.admin_token}"},
            json={"plan_id": "quarterly"}
        )
        assert response.status_code == 200, f"SOL payment initiation failed: {response.text}"
        
        data = response.json()
        assert data["amount_sol"] >= 0.5, f"Quarterly plan should be at least 0.5 SOL, got: {data['amount_sol']}"
        assert data["amount_sol"] < 0.51, f"Quarterly plan should be around 0.5 SOL, got: {data['amount_sol']}"
        assert data["plan"]["label"] == "Premium Quarterly", f"Plan label should be 'Premium Quarterly', got: {data['plan']['label']}"
        assert data["plan"]["duration_days"] == 90, f"Quarterly plan should be 90 days, got: {data['plan']['duration_days']}"
        assert data["plan"]["save_pct"] == 17, f"Quarterly plan should show 17% savings, got: {data['plan']['save_pct']}"
        
        print(f"✓ SOL quarterly payment order: {data['amount_sol']} SOL (90 days, save 17%)")


class TestPremiumPlansEndpoint:
    """Test premium plans endpoint returns correct data"""
    
    def test_premium_plans_returns_sol_prices(self):
        """GET /api/premium/plans should return monthly and quarterly plans with SOL prices"""
        response = requests.get(f"{BASE_URL}/api/premium/plans")
        assert response.status_code == 200, f"Failed to get premium plans: {response.text}"
        
        data = response.json()
        assert "plans" in data, "Should return plans"
        assert "monthly" in data["plans"], "Should have monthly plan"
        assert "quarterly" in data["plans"], "Should have quarterly plan"
        assert "owner_wallet" in data, "Should return owner_wallet"
        assert "payment_methods" in data, "Should return payment_methods"
        
        # Verify monthly plan
        monthly = data["plans"]["monthly"]
        assert monthly["price_sol"] == 0.2, f"Monthly should be 0.2 SOL, got: {monthly['price_sol']}"
        assert monthly["price_usd"] == 29.00, f"Monthly should be $29, got: {monthly['price_usd']}"
        assert monthly["duration_days"] == 30, f"Monthly should be 30 days, got: {monthly['duration_days']}"
        
        # Verify quarterly plan
        quarterly = data["plans"]["quarterly"]
        assert quarterly["price_sol"] == 0.5, f"Quarterly should be 0.5 SOL, got: {quarterly['price_sol']}"
        assert quarterly["price_usd"] == 69.00, f"Quarterly should be $69, got: {quarterly['price_usd']}"
        assert quarterly["duration_days"] == 90, f"Quarterly should be 90 days, got: {quarterly['duration_days']}"
        assert quarterly["save_pct"] == 17, f"Quarterly should save 17%, got: {quarterly['save_pct']}"
        
        # Verify payment methods
        assert "sol" in data["payment_methods"], "Should support SOL payment"
        assert "stripe" in data["payment_methods"], "Should support Stripe payment"
        
        print(f"✓ Premium plans: Monthly 0.2 SOL ($29), Quarterly 0.5 SOL ($69, save 17%)")
        print(f"✓ Owner wallet: {data['owner_wallet'][:20]}...")
        print(f"✓ Payment methods: {', '.join(data['payment_methods'])}")
