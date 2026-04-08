"""
Wallet Config API Tests
Tests: GET /api/wallet/config, PUT /api/wallet/config, DELETE /api/wallet/config/key
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://app-builder-4154.preview.emergentagent.com').rstrip('/')

class TestWalletConfig:
    """Wallet configuration endpoint tests"""
    
    def test_get_wallet_config_initial(self):
        """Test GET /api/wallet/config returns initial config"""
        response = requests.get(f"{BASE_URL}/api/wallet/config")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "rpc_url" in data
        assert "wss_url" in data
        assert "has_private_key" in data
        print(f"✓ Wallet config retrieved: has_key={data['has_private_key']}, rpc={data.get('rpc_url', 'N/A')[:50]}")
    
    def test_put_wallet_config_with_private_key(self):
        """Test PUT /api/wallet/config saves private key and returns masked version"""
        test_key = "5J3mBbAH58CpQ3YENNX6qsP4PmxNgNHLsZ3eLY7ZfMwk"
        test_rpc = "https://mainnet.helius-rpc.com/?api-key=test123"
        test_wss = "wss://mainnet.helius-rpc.com/?api-key=test123"
        
        response = requests.put(
            f"{BASE_URL}/api/wallet/config",
            json={
                "private_key": test_key,
                "rpc_url": test_rpc,
                "wss_url": test_wss
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify private key is masked
        assert "private_key_masked" in data
        assert data["private_key_masked"] == "5J3m...fMwk"
        assert "private_key" not in data  # Raw key should not be returned
        assert data["has_private_key"] == True
        assert data["rpc_url"] == test_rpc
        assert data["wss_url"] == test_wss
        print(f"✓ Wallet config saved: masked_key={data['private_key_masked']}")
        
        # Verify persistence with GET
        get_response = requests.get(f"{BASE_URL}/api/wallet/config")
        get_data = get_response.json()
        assert get_data["has_private_key"] == True
        assert get_data["private_key_masked"] == "5J3m...fMwk"
        assert get_data["rpc_url"] == test_rpc
        print("✓ Wallet config persisted correctly")
    
    def test_put_wallet_config_partial_update(self):
        """Test PUT /api/wallet/config with partial update (only RPC URL)"""
        new_rpc = "https://mainnet.helius-rpc.com/?api-key=updated456"
        
        response = requests.put(
            f"{BASE_URL}/api/wallet/config",
            json={"rpc_url": new_rpc}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Private key should still be present from previous test
        assert data["has_private_key"] == True
        assert data["rpc_url"] == new_rpc
        print(f"✓ Partial update successful: rpc updated, key preserved")
    
    def test_delete_wallet_config_key(self):
        """Test DELETE /api/wallet/config/key clears the private key"""
        response = requests.delete(f"{BASE_URL}/api/wallet/config/key")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "cleared" in data["message"].lower()
        print("✓ Private key cleared")
        
        # Verify key is actually cleared
        get_response = requests.get(f"{BASE_URL}/api/wallet/config")
        get_data = get_response.json()
        assert get_data["has_private_key"] == False
        assert get_data["private_key_masked"] == ""
        print("✓ Private key confirmed cleared via GET")
    
    def test_get_wallet_config_after_clear(self):
        """Test GET /api/wallet/config after key is cleared"""
        response = requests.get(f"{BASE_URL}/api/wallet/config")
        assert response.status_code == 200
        data = response.json()
        
        assert data["has_private_key"] == False
        assert data["private_key_masked"] == ""
        # RPC URLs should still be present
        assert "rpc_url" in data
        assert "wss_url" in data
        print("✓ Wallet config accessible after key clear, RPC URLs preserved")
