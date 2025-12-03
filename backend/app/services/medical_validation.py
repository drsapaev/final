"""
Medical Record Validation Service

✅ SECURITY: Validation for medical records including ICD-10 codes, date ranges, and medical values
"""
import logging
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MedicalValidationService:
    """Service for medical record validation"""

    # ICD-10 code pattern (format: A00.0 or A00)
    ICD10_PATTERN = re.compile(r'^[A-Z]\d{2}(\.\d)?$')

    # Valid ICD-10 code ranges (simplified - in production, use full ICD-10 database)
    ICD10_RANGES = {
        'A': (0, 99),  # Certain infectious and parasitic diseases
        'B': (0, 99),  # Certain infectious and parasitic diseases
        'C': (0, 97),  # Neoplasms
        'D': (0, 89),  # Diseases of the blood and immune system
        'E': (0, 90),  # Endocrine, nutritional and metabolic diseases
        'F': (0, 99),  # Mental and behavioural disorders
        'G': (0, 99),  # Diseases of the nervous system
        'H': (0, 95),  # Diseases of the eye and adnexa
        'I': (0, 99),  # Diseases of the circulatory system
        'J': (0, 99),  # Diseases of the respiratory system
        'K': (0, 95),  # Diseases of the digestive system
        'L': (0, 99),  # Diseases of the skin and subcutaneous tissue
        'M': (0, 99),  # Diseases of the musculoskeletal system
        'N': (0, 99),  # Diseases of the genitourinary system
        'O': (0, 99),  # Pregnancy, childbirth and the puerperium
        'P': (0, 96),  # Certain conditions originating in the perinatal period
        'Q': (0, 99),  # Congenital malformations
        'R': (0, 94),  # Symptoms, signs and abnormal clinical findings
        'S': (0, 99),  # Injury, poisoning
        'T': (0, 88),  # Injury, poisoning
        'U': (0, 85),  # Codes for special purposes
        'V': (0, 99),  # External causes of morbidity
        'W': (0, 99),  # External causes of morbidity
        'X': (0, 99),  # External causes of morbidity
        'Y': (0, 98),  # External causes of morbidity
        'Z': (0, 99),  # Factors influencing health status
    }

    # Medical value ranges
    BLOOD_PRESSURE_SYSTOLIC_MIN = 50
    BLOOD_PRESSURE_SYSTOLIC_MAX = 250
    BLOOD_PRESSURE_DIASTOLIC_MIN = 30
    BLOOD_PRESSURE_DIASTOLIC_MAX = 150

    HEART_RATE_MIN = 30
    HEART_RATE_MAX = 220

    TEMPERATURE_MIN = 30.0  # Celsius
    TEMPERATURE_MAX = 45.0

    WEIGHT_MIN = 0.5  # kg
    WEIGHT_MAX = 500.0

    HEIGHT_MIN = 30.0  # cm
    HEIGHT_MAX = 250.0

    def validate_icd10_code(self, code: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        Validate ICD-10 code
        
        Returns:
            (is_valid, error_message)
        """
        if not code:
            return True, None  # ICD-10 code is optional

        code = code.strip().upper()

        # Check format
        if not self.ICD10_PATTERN.match(code):
            return False, f"Invalid ICD-10 code format: {code}. Expected format: A00.0 or A00"

        # Check letter and number range
        letter = code[0]
        number_str = code[1:3]
        
        if letter not in self.ICD10_RANGES:
            return False, f"Invalid ICD-10 category: {letter}"

        try:
            number = int(number_str)
            min_num, max_num = self.ICD10_RANGES[letter]
            
            if number < min_num or number > max_num:
                return False, f"ICD-10 code {code} is out of valid range for category {letter}"

            # Check subcategory if present
            if '.' in code:
                subcategory = int(code.split('.')[1])
                if subcategory < 0 or subcategory > 9:
                    return False, f"Invalid ICD-10 subcategory: {subcategory}"

        except ValueError:
            return False, f"Invalid ICD-10 code number: {number_str}"

        return True, None

    def validate_date_range(
        self, 
        start_date: Optional[date], 
        end_date: Optional[date],
        field_name: str = "date range"
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate date range
        
        Returns:
            (is_valid, error_message)
        """
        if not start_date or not end_date:
            return True, None  # Both dates optional

        if end_date < start_date:
            return False, f"End date cannot be before start date in {field_name}"

        # Check if range is reasonable (not more than 100 years)
        if (end_date - start_date).days > 36525:  # ~100 years
            return False, f"Date range exceeds 100 years in {field_name}"

        return True, None

    def validate_visit_date(
        self, 
        visit_date: Optional[date],
        birth_date: Optional[date] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate visit date
        
        Args:
            visit_date: Date of visit
            birth_date: Patient's birth date (optional)
        
        Returns:
            (is_valid, error_message)
        """
        if not visit_date:
            return True, None  # Visit date is optional

        today = date.today()

        # Visit date cannot be in the future (with small tolerance for timezone)
        if visit_date > today + timedelta(days=1):
            return False, "Visit date cannot be more than 1 day in the future"

        # Visit date should not be too far in the past (reasonable limit: 50 years)
        min_date = date(today.year - 50, 1, 1)
        if visit_date < min_date:
            return False, "Visit date is too far in the past"

        # If birth date is provided, visit date should be after birth date
        if birth_date and visit_date < birth_date:
            return False, "Visit date cannot be before patient's birth date"

        return True, None

    def validate_blood_pressure(
        self, systolic: Optional[float], diastolic: Optional[float]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate blood pressure values
        
        Returns:
            (is_valid, error_message)
        """
        if systolic is None and diastolic is None:
            return True, None  # Both optional

        if systolic is not None:
            if systolic < self.BLOOD_PRESSURE_SYSTOLIC_MIN:
                return False, f"Systolic pressure too low: {systolic} (minimum: {self.BLOOD_PRESSURE_SYSTOLIC_MIN})"
            if systolic > self.BLOOD_PRESSURE_SYSTOLIC_MAX:
                return False, f"Systolic pressure too high: {systolic} (maximum: {self.BLOOD_PRESSURE_SYSTOLIC_MAX})"

        if diastolic is not None:
            if diastolic < self.BLOOD_PRESSURE_DIASTOLIC_MIN:
                return False, f"Diastolic pressure too low: {diastolic} (minimum: {self.BLOOD_PRESSURE_DIASTOLIC_MIN})"
            if diastolic > self.BLOOD_PRESSURE_DIASTOLIC_MAX:
                return False, f"Diastolic pressure too high: {diastolic} (maximum: {self.BLOOD_PRESSURE_DIASTOLIC_MAX})"

        # Systolic should be higher than diastolic
        if systolic is not None and diastolic is not None:
            if systolic <= diastolic:
                return False, "Systolic pressure must be higher than diastolic pressure"

        return True, None

    def validate_heart_rate(self, heart_rate: Optional[float]) -> Tuple[bool, Optional[str]]:
        """
        Validate heart rate
        
        Returns:
            (is_valid, error_message)
        """
        if heart_rate is None:
            return True, None

        if heart_rate < self.HEART_RATE_MIN:
            return False, f"Heart rate too low: {heart_rate} (minimum: {self.HEART_RATE_MIN})"

        if heart_rate > self.HEART_RATE_MAX:
            return False, f"Heart rate too high: {heart_rate} (maximum: {self.HEART_RATE_MAX})"

        return True, None

    def validate_temperature(self, temperature: Optional[float]) -> Tuple[bool, Optional[str]]:
        """
        Validate body temperature
        
        Returns:
            (is_valid, error_message)
        """
        if temperature is None:
            return True, None

        if temperature < self.TEMPERATURE_MIN:
            return False, f"Temperature too low: {temperature}°C (minimum: {self.TEMPERATURE_MIN}°C)"

        if temperature > self.TEMPERATURE_MAX:
            return False, f"Temperature too high: {temperature}°C (maximum: {self.TEMPERATURE_MAX}°C)"

        return True, None

    def validate_weight(self, weight: Optional[float]) -> Tuple[bool, Optional[str]]:
        """
        Validate weight
        
        Returns:
            (is_valid, error_message)
        """
        if weight is None:
            return True, None

        if weight < self.WEIGHT_MIN:
            return False, f"Weight too low: {weight} kg (minimum: {self.WEIGHT_MIN} kg)"

        if weight > self.WEIGHT_MAX:
            return False, f"Weight too high: {weight} kg (maximum: {self.WEIGHT_MAX} kg)"

        return True, None

    def validate_height(self, height: Optional[float]) -> Tuple[bool, Optional[str]]:
        """
        Validate height
        
        Returns:
            (is_valid, error_message)
        """
        if height is None:
            return True, None

        if height < self.HEIGHT_MIN:
            return False, f"Height too low: {height} cm (minimum: {self.HEIGHT_MIN} cm)"

        if height > self.HEIGHT_MAX:
            return False, f"Height too high: {height} cm (maximum: {self.HEIGHT_MAX} cm)"

        return True, None

    def validate_medical_record(self, record_data: Dict, patient_birth_date: Optional[date] = None) -> Tuple[bool, List[str]]:
        """
        Comprehensive validation of medical record data
        
        Args:
            record_data: Dictionary with medical record fields
            patient_birth_date: Patient's birth date for date validation
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Validate ICD-10 code
        if "icd10" in record_data or "diagnosis_code" in record_data:
            icd10 = record_data.get("icd10") or record_data.get("diagnosis_code")
            valid, error = self.validate_icd10_code(icd10)
            if not valid:
                errors.append(error)

        # Validate visit date
        if "visit_date" in record_data or "appointment_date" in record_data:
            visit_date = record_data.get("visit_date") or record_data.get("appointment_date")
            if isinstance(visit_date, str):
                try:
                    visit_date = datetime.strptime(visit_date, "%Y-%m-%d").date()
                except ValueError:
                    errors.append("Invalid visit date format. Expected: YYYY-MM-DD")
                    visit_date = None

            if visit_date:
                valid, error = self.validate_visit_date(visit_date, patient_birth_date)
                if not valid:
                    errors.append(error)

        # Validate vital signs if present
        vital_signs = record_data.get("vital_signs") or {}
        
        if "blood_pressure" in vital_signs:
            bp = vital_signs["blood_pressure"]
            if isinstance(bp, dict):
                systolic = bp.get("systolic")
                diastolic = bp.get("diastolic")
                valid, error = self.validate_blood_pressure(systolic, diastolic)
                if not valid:
                    errors.append(error)

        if "heart_rate" in vital_signs:
            valid, error = self.validate_heart_rate(vital_signs.get("heart_rate"))
            if not valid:
                errors.append(error)

        if "temperature" in vital_signs:
            valid, error = self.validate_temperature(vital_signs.get("temperature"))
            if not valid:
                errors.append(error)

        if "weight" in vital_signs:
            valid, error = self.validate_weight(vital_signs.get("weight"))
            if not valid:
                errors.append(error)

        if "height" in vital_signs:
            valid, error = self.validate_height(vital_signs.get("height"))
            if not valid:
                errors.append(error)

        # Validate date ranges in procedures
        if "procedures" in record_data and isinstance(record_data["procedures"], list):
            for i, procedure in enumerate(record_data["procedures"]):
                if isinstance(procedure, dict):
                    if "start_date" in procedure and "end_date" in procedure:
                        start = procedure.get("start_date")
                        end = procedure.get("end_date")
                        
                        if isinstance(start, str):
                            try:
                                start = datetime.strptime(start, "%Y-%m-%d").date()
                            except ValueError:
                                errors.append(f"Procedure {i+1}: Invalid start date format")
                                start = None
                        
                        if isinstance(end, str):
                            try:
                                end = datetime.strptime(end, "%Y-%m-%d").date()
                            except ValueError:
                                errors.append(f"Procedure {i+1}: Invalid end date format")
                                end = None
                        
                        if start and end:
                            valid, error = self.validate_date_range(start, end, f"procedure {i+1}")
                            if not valid:
                                errors.append(error)

        return len(errors) == 0, errors


