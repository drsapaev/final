"""
Test cart creation function directly to see Python error
"""
import sys
sys.path.insert(0, '.')

from decimal import Decimal
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Create DB session
engine = create_engine("sqlite:///./clinic.db", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    # Import the endpoint function
    print("[*] Importing endpoint...")
    from app.api.v1.endpoints.registrar_wizard import create_cart_appointments, CartRequest, VisitRequest, ServiceItemRequest
    print("[OK] Endpoint imported successfully")

    # Get a patient
    from app.models.patient import Patient
    patient = db.query(Patient).first()
    if not patient:
        print("[ERROR] No patients found")
        sys.exit(1)
    print(f"[OK] Using patient ID: {patient.id}")

    # Get a service
    from app.models.service import Service
    service = db.query(Service).first()
    if not service:
        print("[ERROR] No services found")
        sys.exit(1)
    print(f"[OK] Using service ID: {service.id} ({service.name})")

    # Get current user (registrar)
    from app.models.user import User
    user = db.query(User).filter(User.username == "registrar").first()
    if not user:
        print("[ERROR] Registrar user not found")
        sys.exit(1)
    print(f"[OK] Using user: {user.username}")

    # Create cart request
    print("\n[*] Creating cart request...")
    cart_data = CartRequest(
        patient_id=patient.id,
        discount_mode="none",
        payment_method="cash",
        notes="Test cart",
        visits=[
            VisitRequest(
                department="general",
                visit_date=date.today(),
                visit_time="10:00",
                doctor_id=None,
                services=[
                    ServiceItemRequest(
                        service_id=service.id,
                        quantity=1,
                        custom_price=None
                    )
                ]
            )
        ]
    )
    print("[OK] Cart request created")

    # Call the endpoint function directly
    print("\n[*] Calling create_cart_appointments...")
    try:
        result = create_cart_appointments(
            cart_data=cart_data,
            db=db,
            current_user=user
        )
        print(f"\n[OK] Success!")
        print(f"     Invoice ID: {result.invoice_id}")
        print(f"     Visit IDs: {result.visit_ids}")
        print(f"     Total amount: {result.total_amount}")
        print(f"     Message: {result.message}")
    except Exception as e:
        print(f"\n[ERROR] Function call failed:")
        print(f"        Type: {type(e).__name__}")
        print(f"        Message: {str(e)}")
        import traceback
        print("\n[TRACEBACK]")
        traceback.print_exc()

except Exception as e:
    print(f"\n[ERROR] Import or setup failed:")
    print(f"        Type: {type(e).__name__}")
    print(f"        Message: {str(e)}")
    import traceback
    print("\n[TRACEBACK]")
    traceback.print_exc()
finally:
    db.close()
