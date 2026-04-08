"""
Backend tests for Admin Payment Wallet Management
Tests: Admin login with new credentials, payment wallet CRUD, dynamic owner_wallet in premium plans
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')

class TestAdminAuth:
    """Test admin login with new credentials"""
    
    def test_admin_login_new_credentials(self):
        """Test admin login with Superbiggzz1411@gmail.com / Biggzz1411!"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "Superbiggzz1411@gmail.com",
            "password": "Biggzz1411!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["email"] == "superbiggzz1411@gmail.com"  # Email normalized to lowercase
        assert data["role"] == "admin"
        assert "subscription" in data
        assert data["subscription"]["status"] == "active"
        print(f"✓ Admin login successful with new credentials: {data['email']}, role={data['role']}")
        return data["token"]
    
    def test_admin_has_premium_subscription(self):
        """Test admin has premium subscription"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "Superbiggzz1411@gmail.com",
            "password": "Biggzz1411!"
        })
        token = login_res.json()["token"]
        
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["is_premium"] == True
        assert data["role"] == "admin"
        assert data["subscription"]["status"] == "active"
        print("✓ Admin has premium subscription and is_premium=True")


class TestPaymentWalletCRUD:
    """Test payment wallet CRUD operations (admin only)"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token for authenticated requests"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "Superbiggzz1411@gmail.com",
            "password": "Biggzz1411!"
        })
        return login_res.json()["token"]
    
    @pytest.fixture
    def regular_user_token(self):
        """Create and login a regular user"""
        email = f"test_{uuid.uuid4().hex[:8]}@test.com"
        reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "Test123!",
            "name": "Test User"
        })
        return reg_res.json()["token"]
    
    def test_get_payment_wallets_requires_admin(self, regular_user_token):
        """Test GET /api/admin/payment-wallets requires admin role"""
        response = requests.get(f"{BASE_URL}/api/admin/payment-wallets", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        assert response.status_code == 403
        assert "admin only" in response.json()["detail"].lower()
        print("✓ GET /api/admin/payment-wallets requires admin role")
    
    def test_get_payment_wallets_as_admin(self, admin_token):
        """Test GET /api/admin/payment-wallets returns wallets list"""
        response = requests.get(f"{BASE_URL}/api/admin/payment-wallets", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert "wallets" in data
        assert isinstance(data["wallets"], list)
        
        # Should have at least the default wallet
        assert len(data["wallets"]) >= 1
        
        # Check wallet structure
        if len(data["wallets"]) > 0:
            wallet = data["wallets"][0]
            assert "id" in wallet
            assert "address" in wallet
            assert "label" in wallet
            assert "is_active" in wallet
            assert "created_at" in wallet
            assert "_id" not in wallet  # MongoDB _id should be excluded
            
            # Check for active wallet
            active_wallets = [w for w in data["wallets"] if w["is_active"]]
            assert len(active_wallets) == 1, "Should have exactly one active wallet"
            print(f"✓ GET /api/admin/payment-wallets returns {len(data['wallets'])} wallets, active: {active_wallets[0]['label']}")
    
    def test_add_payment_wallet_requires_admin(self, regular_user_token):
        """Test POST /api/admin/payment-wallets requires admin role"""
        response = requests.post(f"{BASE_URL}/api/admin/payment-wallets", 
            headers={"Authorization": f"Bearer {regular_user_token}"},
            json={
                "address": "TestWallet123456789012345678901234567890",
                "label": "Test Wallet"
            }
        )
        assert response.status_code == 403
        assert "admin only" in response.json()["detail"].lower()
        print("✓ POST /api/admin/payment-wallets requires admin role")
    
    def test_add_payment_wallet_as_admin(self, admin_token):
        """Test POST /api/admin/payment-wallets adds new wallet"""
        test_address = f"TEST_{uuid.uuid4().hex[:40]}"
        response = requests.post(f"{BASE_URL}/api/admin/payment-wallets", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "address": test_address,
                "label": "Test Business Wallet"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["address"] == test_address
        assert data["label"] == "Test Business Wallet"
        assert data["is_active"] == False  # New wallets are not active by default
        assert "id" in data
        assert "created_at" in data
        assert "_id" not in data
        print(f"✓ POST /api/admin/payment-wallets added wallet: {data['label']}, id={data['id']}")
        
        # Verify it appears in GET list
        get_response = requests.get(f"{BASE_URL}/api/admin/payment-wallets", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        wallets = get_response.json()["wallets"]
        added_wallet = next((w for w in wallets if w["address"] == test_address), None)
        assert added_wallet is not None
        assert added_wallet["label"] == "Test Business Wallet"
        print("✓ New wallet appears in GET /api/admin/payment-wallets")
        
        return data["id"]
    
    def test_add_duplicate_wallet_address(self, admin_token):
        """Test POST /api/admin/payment-wallets rejects duplicate address"""
        test_address = f"DUPLICATE_{uuid.uuid4().hex[:40]}"
        
        # Add first wallet
        requests.post(f"{BASE_URL}/api/admin/payment-wallets", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"address": test_address, "label": "First"}
        )
        
        # Try to add duplicate
        response = requests.post(f"{BASE_URL}/api/admin/payment-wallets", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"address": test_address, "label": "Duplicate"}
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()
        print("✓ POST /api/admin/payment-wallets rejects duplicate address")
    
    def test_activate_payment_wallet(self, admin_token):
        """Test PUT /api/admin/payment-wallets/{id}/activate"""
        # Add a new wallet
        test_address = f"ACTIVATE_{uuid.uuid4().hex[:40]}"
        add_response = requests.post(f"{BASE_URL}/api/admin/payment-wallets", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"address": test_address, "label": "To Activate"}
        )
        wallet_id = add_response.json()["id"]
        
        # Activate it
        response = requests.put(f"{BASE_URL}/api/admin/payment-wallets/{wallet_id}/activate", 
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "wallet" in data
        assert data["wallet"]["is_active"] == True
        assert data["wallet"]["id"] == wallet_id
        print(f"✓ PUT /api/admin/payment-wallets/{wallet_id}/activate activated wallet")
        
        # Verify only one wallet is active
        get_response = requests.get(f"{BASE_URL}/api/admin/payment-wallets", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        wallets = get_response.json()["wallets"]
        active_wallets = [w for w in wallets if w["is_active"]]
        assert len(active_wallets) == 1
        assert active_wallets[0]["id"] == wallet_id
        print("✓ Only one wallet is active after activation")
        
        return wallet_id
    
    def test_activate_nonexistent_wallet(self, admin_token):
        """Test PUT /api/admin/payment-wallets/{id}/activate with invalid ID"""
        fake_id = str(uuid.uuid4())
        response = requests.put(f"{BASE_URL}/api/admin/payment-wallets/{fake_id}/activate", 
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
        print("✓ PUT /api/admin/payment-wallets/{id}/activate returns 404 for invalid ID")
    
    def test_delete_non_active_wallet(self, admin_token):
        """Test DELETE /api/admin/payment-wallets/{id} removes non-active wallet"""
        # Add a new wallet (not active)
        test_address = f"DELETE_{uuid.uuid4().hex[:40]}"
        add_response = requests.post(f"{BASE_URL}/api/admin/payment-wallets", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"address": test_address, "label": "To Delete"}
        )
        wallet_id = add_response.json()["id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/admin/payment-wallets/{wallet_id}", 
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✓ DELETE /api/admin/payment-wallets/{wallet_id} removed wallet")
        
        # Verify it's gone
        get_response = requests.get(f"{BASE_URL}/api/admin/payment-wallets", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        wallets = get_response.json()["wallets"]
        deleted_wallet = next((w for w in wallets if w["id"] == wallet_id), None)
        assert deleted_wallet is None
        print("✓ Deleted wallet no longer appears in GET list")
    
    def test_delete_active_wallet_fails(self, admin_token):
        """Test DELETE /api/admin/payment-wallets/{id} fails for active wallet"""
        # Get current active wallet
        get_response = requests.get(f"{BASE_URL}/api/admin/payment-wallets", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        wallets = get_response.json()["wallets"]
        active_wallet = next((w for w in wallets if w["is_active"]), None)
        
        if active_wallet:
            response = requests.delete(f"{BASE_URL}/api/admin/payment-wallets/{active_wallet['id']}", 
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 400
            assert "cannot delete active wallet" in response.json()["detail"].lower()
            print("✓ DELETE /api/admin/payment-wallets/{id} prevents deleting active wallet")
        else:
            print("⚠ No active wallet found to test deletion prevention")
    
    def test_delete_nonexistent_wallet(self, admin_token):
        """Test DELETE /api/admin/payment-wallets/{id} with invalid ID"""
        fake_id = str(uuid.uuid4())
        response = requests.delete(f"{BASE_URL}/api/admin/payment-wallets/{fake_id}", 
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
        print("✓ DELETE /api/admin/payment-wallets/{id} returns 404 for invalid ID")


class TestDynamicOwnerWallet:
    """Test dynamic owner_wallet in premium plans endpoint"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "Superbiggzz1411@gmail.com",
            "password": "Biggzz1411!"
        })
        return login_res.json()["token"]
    
    def test_premium_plans_returns_active_wallet(self, admin_token):
        """Test GET /api/premium/plans returns owner_wallet from active payment wallet"""
        # Get current active wallet
        wallets_response = requests.get(f"{BASE_URL}/api/admin/payment-wallets", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        wallets = wallets_response.json()["wallets"]
        active_wallet = next((w for w in wallets if w["is_active"]), None)
        
        # Get premium plans
        response = requests.get(f"{BASE_URL}/api/premium/plans")
        assert response.status_code == 200
        data = response.json()
        assert "owner_wallet" in data
        
        if active_wallet:
            assert data["owner_wallet"] == active_wallet["address"]
            print(f"✓ GET /api/premium/plans returns active wallet: {data['owner_wallet'][:20]}...")
        else:
            print("⚠ No active wallet found, using default OWNER_WALLET")
    
    def test_sol_payment_uses_active_wallet(self, admin_token):
        """Test POST /api/premium/sol/initiate uses active payment wallet"""
        # Get current active wallet
        wallets_response = requests.get(f"{BASE_URL}/api/admin/payment-wallets", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        wallets = wallets_response.json()["wallets"]
        active_wallet = next((w for w in wallets if w["is_active"]), None)
        
        # Initiate SOL payment
        response = requests.post(f"{BASE_URL}/api/premium/sol/initiate", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"plan_id": "monthly"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "wallet_address" in data
        
        if active_wallet:
            assert data["wallet_address"] == active_wallet["address"]
            print(f"✓ POST /api/premium/sol/initiate uses active wallet: {data['wallet_address'][:20]}...")
        else:
            print("⚠ No active wallet found, using default OWNER_WALLET")
    
    def test_dynamic_wallet_change(self, admin_token):
        """Test that changing active wallet updates premium plans endpoint"""
        # Add a new wallet
        test_address = f"DYNAMIC_{uuid.uuid4().hex[:40]}"
        add_response = requests.post(f"{BASE_URL}/api/admin/payment-wallets", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"address": test_address, "label": "Dynamic Test"}
        )
        new_wallet_id = add_response.json()["id"]
        
        # Activate the new wallet
        requests.put(f"{BASE_URL}/api/admin/payment-wallets/{new_wallet_id}/activate", 
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Check premium plans now returns new wallet
        plans_response = requests.get(f"{BASE_URL}/api/premium/plans")
        plans_data = plans_response.json()
        assert plans_data["owner_wallet"] == test_address
        print(f"✓ Premium plans dynamically updated to new active wallet: {test_address[:20]}...")
        
        # Check SOL payment initiate also uses new wallet
        sol_response = requests.post(f"{BASE_URL}/api/premium/sol/initiate", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"plan_id": "monthly"}
        )
        sol_data = sol_response.json()
        assert sol_data["wallet_address"] == test_address
        print(f"✓ SOL payment initiate uses new active wallet: {test_address[:20]}...")


class TestPremiumPlansStructure:
    """Test premium plans endpoint structure"""
    
    def test_premium_plans_structure(self):
        """Test GET /api/premium/plans returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/premium/plans")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "plans" in data
        assert "free_limits" in data
        assert "premium_limits" in data
        assert "owner_wallet" in data
        assert "payment_methods" in data
        
        # Check plans
        assert "monthly" in data["plans"]
        assert "quarterly" in data["plans"]
        
        monthly = data["plans"]["monthly"]
        assert monthly["price_sol"] == 0.2
        assert monthly["duration_days"] == 30
        
        quarterly = data["plans"]["quarterly"]
        assert quarterly["price_sol"] == 0.5
        assert quarterly["duration_days"] == 90
        
        print("✓ GET /api/premium/plans returns correct structure with monthly (0.2 SOL) and quarterly (0.5 SOL) plans")
