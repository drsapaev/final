#!/usr/bin/env python3
"""
Simple test for cart creation functionality
Tests the /api/v1/registrar/cart endpoint
"""
try:
    print("🛒 Starting Simple Cart Test...")
except:
    pass  # In case print fails

try:
    import sys
    import os
    # Add backend directory to path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(current_dir, 'backend')
    sys.path.insert(0, backend_dir)
    print(f"📁 Added to path: {backend_dir}")
except Exception as e:
    print(f"Path setup failed: {e}")
    sys.exit(1)

import requests
import json
from datetime import date, datetime

# Configuration
API_BASE = "http://localhost:18000"
AUTH_TOKEN = None
REGISTRAR_PASSWORD_ENV = "QA_REGISTRAR_PASSWORD"
REGISTRAR_PASSWORD = os.environ.get(REGISTRAR_PASSWORD_ENV, "").strip()
if not REGISTRAR_PASSWORD:
    raise SystemExit(f"Set {REGISTRAR_PASSWORD_ENV} before running this smoke script.")

def login_as_registrar():
    """Login as registrar user"""
    print("[LOGIN] Attempting to login as registrar...")
    response = requests.post(
        f"{API_BASE}/api/v1/auth/minimal-login",
        json={
            "username": "registrar",
            "password": REGISTRAR_PASSWORD
        }
    )

    if response.status_code == 200:
        data = response.json()
        if "access_token" in data:
            global AUTH_TOKEN
            AUTH_TOKEN = data["access_token"]
            print("✅ Login successful")
            return True
        else:
            print(f"❌ No access_token in response: {data}")
            return False
    else:
        print(f"❌ Login failed: {response.status_code}")
        print(f"Response: {response.text}")
        return False

def get_test_patient():
    """Get a test patient ID"""
    print("[PATIENT] Getting test patient...")
    response = requests.get(
        f"{API_BASE}/api/v1/patients/",
        headers={"Authorization": f"Bearer {AUTH_TOKEN}"},
        params={"limit": 1}
    )

    if response.status_code == 200:
        patients = response.json()
        if patients and len(patients) > 0:
            patient_id = patients[0]["id"]
            print(f"✅ Using patient ID: {patient_id}")
            return patient_id
        else:
            print("❌ No patients found")
            return None
    else:
        print(f"❌ Failed to get patients: {response.status_code}")
        print(f"Response: {response.text}")
        return None

def get_test_services():
    """Get test services"""
    print("[SERVICES] Getting test services...")
    response = requests.get(
        f"{API_BASE}/api/v1/services/",
        headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
    )

    if response.status_code == 200:
        services = response.json()
        if services and len(services) > 0:
            # Return first service
            service = services[0]
            print(f"✅ Using service: {service.get('name', 'Unknown')} (ID: {service.get('id')})")
            return service
        else:
            print("❌ No services found")
            return None
    else:
        print(f"❌ Failed to get services: {response.status_code}")
        return None

def get_test_doctor():
    """Get a test doctor ID"""
    print("[DOCTOR] Getting test doctor...")
    response = requests.get(
        f"{API_BASE}/api/v1/admin/doctors/",
        headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
    )

    if response.status_code == 200:
        doctors = response.json()
        if doctors and len(doctors) > 0:
            doctor_id = doctors[0]["id"]
            print(f"✅ Using doctor ID: {doctor_id}")
            return doctor_id
        else:
            print("❌ No doctors found")
            return None
    else:
        print(f"❌ Failed to get doctors: {response.status_code}")
        return None

def test_cart_creation():
    """Test cart creation with minimal data"""
    print("\n[CART] Testing cart creation...")

    # Get test data
    patient_id = get_test_patient()
    if not patient_id:
        return False

    service = get_test_services()
    if not service:
        return False

    doctor_id = get_test_doctor()
    if not doctor_id:
        return False

    # Prepare cart data
    tomorrow = date.today()  # Use today for testing

    cart_data = {
        "patient_id": patient_id,
        "visits": [
            {
                "doctor_id": doctor_id,
                "services": [
                    {
                        "service_id": service["id"],
                        "quantity": 1
                    }
                ],
                "visit_date": tomorrow.isoformat(),
                "visit_time": "10:00",
                "department": "general"
            }
        ],
        "discount_mode": "none",
        "payment_method": "cash"
    }

    print(f"[CART] Sending cart data: {json.dumps(cart_data, indent=2, default=str)}")

    # Create cart
    response = requests.post(
        f"{API_BASE}/api/v1/registrar/cart",
        json=cart_data,
        headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
    )

    print(f"[CART] Response status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Cart created successfully!")
        print(f"   Invoice ID: {result.get('invoice_id')}")
        print(f"   Visit IDs: {result.get('visit_ids')}")
        print(f"   Total amount: {result.get('total_amount')}")
        return True
    else:
        print(f"❌ Cart creation failed: {response.status_code}")
        print(f"Response: {response.text}")
        return False

def main():
    """Main test function"""
    print("🛒 Simple Cart Creation Test")
    print("=" * 50)
    print("Starting test execution...")

    # Debug: write to file
    with open('test_debug.log', 'w') as f:
        f.write('Test started\n')

    # Check if server is running
    print("🔍 Checking server status...")
    try:
        print(f"Connecting to {API_BASE}...")
        response = requests.get(f"{API_BASE}/", timeout=5)
        print(f"Server response: {response.status_code}")
        if response.status_code != 200:
            print("❌ Server is not responding correctly")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        print("Make sure the server is running on localhost:18000")
        return False

    print("✅ Server is running")

    # Test login
    print("\n🔐 Testing login...")
    success = login_as_registrar()
    if success:
        print("✅ Login test passed!")
    else:
        print("❌ Login test failed!")

    print("Test completed!")
    return success

    # Login
    if not login_as_registrar():
        return False

    # Test cart creation
    if test_cart_creation():
        print("\n🎉 All tests passed!")
        return True
    else:
        print("\n💥 Test failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
