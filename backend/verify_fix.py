"""
Comprehensive verification script
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def check_backend_restart():
    print("🔍 Checking if backend was restarted...")
    try:
        # Check if /registrar/departments exists
        response = requests.get(f"{BASE_URL}/api/v1/registrar/departments")
        if response.status_code == 404:
            print("❌ Backend NOT restarted! /registrar/departments still returns 404")
            return False
        else:
            print(f"✅ Backend seems restarted! /registrar/departments returns {response.status_code}")
            return True
    except Exception as e:
        print(f"❌ Backend not running: {e}")
        return False

def test_cart_creation():
    print("\n🛒 Testing cart creation...")
    try:
        # Login
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": "registrar@example.com", "password": "registrar123"}
        )
        if response.status_code != 200:
            print(f"❌ Login failed: {response.status_code}")
            return False
            
        token = response.json()["access_token"]
        
        # Create cart
        cart_data = {
            "patient_id": 1,
            "visits": [{
                "visit_date": "2025-11-28",
                "visit_time": "10:00",
                "department": "general",
                "doctor_id": None,
                "notes": "Test",
                "services": [{"service_id": 3, "quantity": 1, "custom_price": None}]
            }],
            "discount_mode": "none",
            "payment_method": "cash",
            "notes": "Test"
        }
        
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        response = requests.post(f"{BASE_URL}/api/v1/registrar/cart", json=cart_data, headers=headers)
        
        if response.status_code == 200:
            print("✅ Cart creation SUCCESS!")
            return True
        else:
            print(f"❌ Cart creation FAILED: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

if __name__ == "__main__":
    restarted = check_backend_restart()
    if not restarted:
        print("\n⚠️ PLEASE RESTART BACKEND SERVER!")
        sys.exit(1)
        
    success = test_cart_creation()
    if success:
        print("\n🎉 ALL SYSTEMS GO!")
    else:
        print("\n💥 Still having issues with cart creation")
