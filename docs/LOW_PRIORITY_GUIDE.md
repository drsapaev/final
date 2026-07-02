# Low Priority Tasks - Implementation Guide

> **Date**: December 2024  
> **Status**: Recommendations for future development

---

## Overview

This document provides guidance for the remaining LOW priority tasks. These are quality improvements that can be implemented incrementally over time.

---

## 1. Type Hints Completion

### Current State
- Most newer code has type hints
- Some older endpoints and utility functions lack hints

### Recommended Actions

1. **Install mypy for type checking:**
```bash
pip install mypy
mypy app/ --ignore-missing-imports
```

2. **Priority files for type hints:**
```
app/api/v1/endpoints/*.py    # API endpoints
app/services/*.py            # Business logic
app/crud/*.py                # Database operations
```

3. **Example type hint patterns:**
```python
# Before
def get_patient(db, patient_id):
    return db.query(Patient).filter(Patient.id == patient_id).first()

# After
from typing import Optional
from sqlalchemy.orm import Session
from app.models.patient import Patient

def get_patient(db: Session, patient_id: int) -> Optional[Patient]:
    return db.query(Patient).filter(Patient.id == patient_id).first()
```

4. **Common imports needed:**
```python
from typing import List, Dict, Optional, Any, Union, Tuple
from datetime import datetime, date
from sqlalchemy.orm import Session
```

---

## 2. Test Coverage Improvement

### Current State
- Basic tests exist
- Critical paths need more coverage

### Priority Areas for Testing

1. **Payment Processing** (`app/services/payment_service.py`)
   - Webhook validation
   - Transaction processing
   - Refund handling

2. **Patient Validation** (`app/services/patient_validation.py`)
   - Phone number formats
   - Required fields
   - Duplicate detection

3. **Queue Operations** (`app/services/queue_service.py`)
   - Queue number assignment
   - Status transitions
   - Concurrent access

### Test Template

```python
# tests/test_payment_service.py
import pytest
from unittest.mock import Mock, patch
from app.services.payment_service import PaymentService

class TestPaymentService:
    
    def test_process_payment_success(self, db_session):
        """Test successful payment processing"""
        service = PaymentService(db_session)
        result = service.process_payment(
            visit_id=1,
            amount=100000,
            method="cash"
        )
        assert result.success is True
        assert result.transaction_id is not None
    
    def test_process_payment_insufficient_amount(self, db_session):
        """Test payment with insufficient amount"""
        service = PaymentService(db_session)
        with pytest.raises(ValueError):
            service.process_payment(visit_id=1, amount=0, method="cash")
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_payment_service.py -v
```

---

## 3. Code Duplication Reduction

### Common Patterns to Extract

1. **Error Response Creation**
```python
# Create: app/api/utils/responses.py
from fastapi import HTTPException, status

def not_found(message: str = "Resource not found"):
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)

def forbidden(message: str = "Access denied"):
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)

def bad_request(message: str):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
```

2. **Database Query Helpers**
```python
# Create: app/crud/base.py
from typing import TypeVar, Generic, Type, Optional, List
from sqlalchemy.orm import Session
from app.db.base_class import Base

ModelType = TypeVar("ModelType", bound=Base)

class CRUDBase(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    def get(self, db: Session, id: int) -> Optional[ModelType]:
        return db.query(self.model).filter(self.model.id == id).first()
    
    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        return db.query(self.model).offset(skip).limit(limit).all()
```

3. **Validation Patterns**
```python
# Create: app/utils/validators.py
import re

def validate_phone_uz(phone: str) -> bool:
    """Validate Uzbekistan phone number"""
    patterns = [
        r"^\+998\d{9}$",
        r"^998\d{9}$",
        r"^\d{9}$",
    ]
    return any(re.match(p, phone) for p in patterns)

def normalize_phone(phone: str) -> str:
    """Normalize phone to +998XXXXXXXXX format"""
    digits = re.sub(r'\D', '', phone)
    if digits.startswith('998'):
        return f'+{digits}'
    elif len(digits) == 9:
        return f'+998{digits}'
    return phone
```

---

## 4. Documentation Comments

### Docstring Style Guide (Google Style)

```python
def create_appointment(
    db: Session,
    patient_id: int,
    doctor_id: int,
    scheduled_at: datetime,
    services: List[int]
) -> Appointment:
    """
    Create a new appointment for a patient.
    
    Args:
        db: Database session
        patient_id: ID of the patient
        doctor_id: ID of the doctor
        scheduled_at: Appointment date and time
        services: List of service IDs
    
    Returns:
        Created Appointment object
    
    Raises:
        ValueError: If patient or doctor not found
        ConflictError: If time slot is not available
    
    Example:
        >>> appointment = create_appointment(
        ...     db=session,
        ...     patient_id=1,
        ...     doctor_id=5,
        ...     scheduled_at=datetime(2024, 12, 15, 10, 0),
        ...     services=[1, 2]
        ... )
    """
    # Implementation...
```

### Priority Files for Documentation

1. `app/services/*.py` - Business logic
2. `app/api/v1/endpoints/*.py` - API endpoints
3. `app/models/*.py` - Data models
4. `app/utils/*.py` - Utility functions

### Auto-Documentation Tools

```bash
# Generate API docs from docstrings
pip install pdoc3
pdoc --html app/ -o docs/api/

# Or use Sphinx
pip install sphinx sphinx-autodoc-typehints
sphinx-quickstart docs/
```

---

## Implementation Priority

| Task | Effort | Impact | Priority |
|------|--------|--------|----------|
| Type Hints | Medium | High | 1 |
| Test Coverage | High | High | 2 |
| Code Duplication | Medium | Medium | 3 |
| Documentation | Low | Medium | 4 |

---

## Quick Wins

These can be done quickly with high impact:

1. Add type hints to `app/api/deps.py`
2. Add tests for `app/services/patient_validation.py`
3. Create `app/api/utils/responses.py` helper
4. Add docstrings to main entry points

---

*This guide is part of the LOW priority tasks documentation*
