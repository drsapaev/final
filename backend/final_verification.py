"""
Final verification - all systems check
"""
import requests
import json

BASE_URL = "http://localhost:8000"

print("="*60)
print("FINAL VERIFICATION - ALL SYSTEMS CHECK")
print("="*60)

# Login as registrar
print("\n1️⃣ Testing registrar login...")
response = requests.post(
    f"{BASE_URL}/api/v1/auth/login",
    data={"username": "registrar@example.com", "password": "registrar123"}
)
if response.status_code == 200:
    token = response.json()["access_token"]
    print("✅ Login successful")
else:
    print(f"❌ Login failed: {response.status_code}")
    exit(1)

headers = {"Authorization": f"Bearer {token}"}

# Test registrar departments endpoint
print("\n2️⃣ Testing /registrar/departments endpoint...")
response = requests.get(f"{BASE_URL}/api/v1/registrar/departments?active_only=true", headers=headers)
if response.status_code == 200:
    departments = response.json()
    if isinstance(departments, list):
        dept_list = departments
    elif isinstance(departments, dict) and 'data' in departments:
        dept_list = departments['data']
    else:
        dept_list = []
    
    print(f"✅ Departments loaded: {len(dept_list)} departments")
    for dept in dept_list[:3]:
        print(f"   - {dept.get('name_ru')} (key: {dept.get('key')})")
else:
    print(f"❌ Failed: {response.status_code}")
    exit(1)

# Test cart creation
print("\n3️⃣ Testing cart creation...")
cart_data = {
    "patient_id": 1,
    "visits": [{
        "visit_date": "2025-11-28",
        "visit_time": "10:00",
        "department": "general",
        "doctor_id": None,
        "notes": "Final test",
        "services": [{"service_id": 3, "quantity": 1, "custom_price": None}]
    }],
    "discount_mode": "none",
    "payment_method": "cash",
    "notes": "Final verification test"
}

response = requests.post(
    f"{BASE_URL}/api/v1/registrar/cart",
    json=cart_data,
    headers={**headers, "Content-Type": "application/json"}
)

if response.status_code == 200:
    result = response.json()
    print(f"✅ Cart created successfully!")
    print(f"   Invoice ID: {result.get('invoice_id')}")
    print(f"   Visit IDs: {result.get('visit_ids')}")
    print(f"   Total: {result.get('total_amount')} UZS")
else:
    print(f"❌ Failed: {response.status_code}")
    print(f"   Error: {response.text}")
    exit(1)

print("\n" + "="*60)
print("🎉 ALL SYSTEMS OPERATIONAL!")
print("="*60)
print("\n✅ Summary:")
print("  1. Registrar authentication: WORKING")
print("  2. Department API (/registrar/departments): WORKING")
print("  3. Cart creation API: WORKING")
print("  4. Department field bug (500 error): FIXED")
print("\n🚀 You can now:")
print("  - Refresh the Registrar Panel (F5)")
print("  - Create appointments without errors")
print("  - Load dynamic departments")
