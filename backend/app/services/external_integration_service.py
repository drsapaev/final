"""
External Integration Service
Сервис для интеграции с внешними системами (DMED, eGOV, Страхование)
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class IntegrationType(str, Enum):
    """Типы внешних интеграций"""
    DMED = "dmed"
    EGOV = "egov"
    INSURANCE = "insurance"
    ESKIZ = "eskiz"  # SMS провайдер


class BaseIntegration(ABC):
    """Базовый класс для внешних интеграций"""
    
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    @abstractmethod
    async def verify_patient(self, patient_id: str) -> Dict[str, Any]:
        """Верификация пациента"""
        pass
    
    @abstractmethod
    async def submit_visit(self, visit_data: Dict) -> Dict[str, Any]:
        """Отправка данных о визите"""
        pass
    
    async def close(self):
        """Закрыть HTTP клиент"""
        await self.client.aclose()


class DMEDIntegration(BaseIntegration):
    """
    Интеграция с DMED (Единая медицинская информационная система)
    
    Функции:
    - Верификация пациента по ПИНФЛ
    - Отправка данных о визитах
    - Получение истории болезни
    - Регистрация направлений
    """
    
    def __init__(self):
        api_key = os.getenv("DMED_API_KEY", "")
        base_url = os.getenv("DMED_BASE_URL", "https://api.dmed.uz/v1")
        super().__init__(api_key, base_url)
        self.clinic_id = os.getenv("DMED_CLINIC_ID", "")
    
    async def verify_patient(self, pinfl: str) -> Dict[str, Any]:
        """
        Верификация пациента по ПИНФЛ в DMED
        
        Args:
            pinfl: Персональный идентификационный номер физического лица
            
        Returns:
            Данные пациента из DMED
        """
        try:
            if not self.api_key:
                return {"verified": False, "error": "DMED API key not configured"}
            
            response = await self.client.get(
                f"{self.base_url}/patients/verify",
                params={"pinfl": pinfl},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Clinic-ID": self.clinic_id,
                },
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "verified": True,
                    "patient_data": data,
                    "full_name": data.get("full_name"),
                    "birth_date": data.get("birth_date"),
                    "gender": data.get("gender"),
                    "address": data.get("address"),
                }
            else:
                return {"verified": False, "error": f"DMED error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"DMED verification error: {e}")
            return {"verified": False, "error": str(e)}
    
    async def submit_visit(self, visit_data: Dict) -> Dict[str, Any]:
        """
        Отправка данных о визите в DMED
        
        Args:
            visit_data: Данные визита (diagnosis, services, doctor, etc.)
            
        Returns:
            Результат отправки
        """
        try:
            if not self.api_key:
                return {"success": False, "error": "DMED API key not configured"}
            
            payload = {
                "clinic_id": self.clinic_id,
                "patient_pinfl": visit_data.get("patient_pinfl"),
                "visit_date": visit_data.get("visit_date"),
                "doctor_id": visit_data.get("doctor_id"),
                "diagnosis_code": visit_data.get("icd10_code"),
                "diagnosis_text": visit_data.get("diagnosis"),
                "services": visit_data.get("services", []),
                "prescriptions": visit_data.get("prescriptions", []),
            }
            
            response = await self.client.post(
                f"{self.base_url}/visits",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Clinic-ID": self.clinic_id,
                    "Content-Type": "application/json",
                },
            )
            
            if response.status_code in (200, 201):
                return {"success": True, "dmed_id": response.json().get("id")}
            else:
                return {"success": False, "error": f"DMED error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"DMED submit error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_patient_history(self, pinfl: str) -> Dict[str, Any]:
        """
        Получение истории болезни пациента из DMED
        
        Args:
            pinfl: ПИНФЛ пациента
            
        Returns:
            История визитов и диагнозов
        """
        try:
            if not self.api_key:
                return {"success": False, "error": "DMED API key not configured"}
            
            response = await self.client.get(
                f"{self.base_url}/patients/{pinfl}/history",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Clinic-ID": self.clinic_id,
                },
            )
            
            if response.status_code == 200:
                return {"success": True, "history": response.json()}
            else:
                return {"success": False, "error": f"DMED error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"DMED history error: {e}")
            return {"success": False, "error": str(e)}


class EGOVIntegration(BaseIntegration):
    """
    Интеграция с eGOV (Электронное правительство)
    
    Функции:
    - Верификация документов
    - Получение данных из реестров
    - Проверка льгот
    """
    
    def __init__(self):
        api_key = os.getenv("EGOV_API_KEY", "")
        base_url = os.getenv("EGOV_BASE_URL", "https://api.egov.uz/v1")
        super().__init__(api_key, base_url)
    
    async def verify_patient(self, pinfl: str) -> Dict[str, Any]:
        """Верификация гражданина по ПИНФЛ"""
        try:
            if not self.api_key:
                return {"verified": False, "error": "eGOV API key not configured"}
            
            response = await self.client.get(
                f"{self.base_url}/citizens/verify",
                params={"pinfl": pinfl},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "verified": True,
                    "citizen_data": data,
                    "full_name": data.get("full_name"),
                    "document_valid": data.get("document_valid", True),
                }
            else:
                return {"verified": False, "error": f"eGOV error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"eGOV verification error: {e}")
            return {"verified": False, "error": str(e)}
    
    async def submit_visit(self, visit_data: Dict) -> Dict[str, Any]:
        """eGOV не требует отправки визитов напрямую"""
        return {"success": True, "message": "Not applicable for eGOV"}
    
    async def check_benefits(self, pinfl: str) -> Dict[str, Any]:
        """
        Проверка льгот гражданина
        
        Args:
            pinfl: ПИНФЛ гражданина
            
        Returns:
            Список активных льгот
        """
        try:
            if not self.api_key:
                return {"success": False, "error": "eGOV API key not configured"}
            
            response = await self.client.get(
                f"{self.base_url}/citizens/{pinfl}/benefits",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            
            if response.status_code == 200:
                return {"success": True, "benefits": response.json()}
            else:
                return {"success": False, "error": f"eGOV error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"eGOV benefits error: {e}")
            return {"success": False, "error": str(e)}


class InsuranceIntegration(BaseIntegration):
    """
    Интеграция со страховыми компаниями
    
    Функции:
    - Проверка полиса
    - Авторизация услуг
    - Отправка страхового случая
    - Получение статуса возмещения
    """
    
    def __init__(self, provider: str = "default"):
        self.provider = provider
        api_key = os.getenv(f"INSURANCE_{provider.upper()}_API_KEY", "")
        base_url = os.getenv(
            f"INSURANCE_{provider.upper()}_BASE_URL",
            "https://api.insurance-provider.uz/v1"
        )
        super().__init__(api_key, base_url)
    
    async def verify_patient(self, policy_number: str) -> Dict[str, Any]:
        """
        Проверка страхового полиса
        
        Args:
            policy_number: Номер страхового полиса
            
        Returns:
            Данные полиса
        """
        try:
            if not self.api_key:
                return {"verified": False, "error": "Insurance API key not configured"}
            
            response = await self.client.get(
                f"{self.base_url}/policies/{policy_number}",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "verified": True,
                    "policy_data": data,
                    "holder_name": data.get("holder_name"),
                    "valid_from": data.get("valid_from"),
                    "valid_to": data.get("valid_to"),
                    "is_active": data.get("is_active", False),
                    "coverage_type": data.get("coverage_type"),
                    "coverage_limit": data.get("coverage_limit"),
                }
            else:
                return {"verified": False, "error": f"Insurance error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Insurance verification error: {e}")
            return {"verified": False, "error": str(e)}
    
    async def submit_visit(self, visit_data: Dict) -> Dict[str, Any]:
        """Отправка страхового случая"""
        return await self.submit_claim(visit_data)
    
    async def authorize_service(
        self,
        policy_number: str,
        service_code: str,
        estimated_cost: float,
    ) -> Dict[str, Any]:
        """
        Авторизация услуги страховой компанией
        
        Args:
            policy_number: Номер полиса
            service_code: Код услуги
            estimated_cost: Ориентировочная стоимость
            
        Returns:
            Результат авторизации
        """
        try:
            if not self.api_key:
                return {"authorized": False, "error": "Insurance API key not configured"}
            
            response = await self.client.post(
                f"{self.base_url}/authorizations",
                json={
                    "policy_number": policy_number,
                    "service_code": service_code,
                    "estimated_cost": estimated_cost,
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            
            if response.status_code in (200, 201):
                data = response.json()
                return {
                    "authorized": data.get("authorized", False),
                    "authorization_code": data.get("authorization_code"),
                    "approved_amount": data.get("approved_amount"),
                    "patient_copay": data.get("patient_copay", 0),
                }
            else:
                return {"authorized": False, "error": f"Insurance error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Insurance authorization error: {e}")
            return {"authorized": False, "error": str(e)}
    
    async def submit_claim(self, claim_data: Dict) -> Dict[str, Any]:
        """
        Отправка страхового случая (claim)
        
        Args:
            claim_data: Данные страхового случая
            
        Returns:
            Результат отправки
        """
        try:
            if not self.api_key:
                return {"success": False, "error": "Insurance API key not configured"}
            
            response = await self.client.post(
                f"{self.base_url}/claims",
                json=claim_data,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            
            if response.status_code in (200, 201):
                data = response.json()
                return {
                    "success": True,
                    "claim_id": data.get("claim_id"),
                    "status": data.get("status"),
                }
            else:
                return {"success": False, "error": f"Insurance error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Insurance claim error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_claim_status(self, claim_id: str) -> Dict[str, Any]:
        """
        Получение статуса страхового случая
        
        Args:
            claim_id: ID страхового случая
            
        Returns:
            Статус и детали
        """
        try:
            if not self.api_key:
                return {"success": False, "error": "Insurance API key not configured"}
            
            response = await self.client.get(
                f"{self.base_url}/claims/{claim_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "claim_id": claim_id,
                    "status": data.get("status"),
                    "approved_amount": data.get("approved_amount"),
                    "paid_amount": data.get("paid_amount"),
                    "rejection_reason": data.get("rejection_reason"),
                }
            else:
                return {"success": False, "error": f"Insurance error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Insurance status error: {e}")
            return {"success": False, "error": str(e)}


class IntegrationManager:
    """
    Менеджер для работы с внешними интеграциями
    """
    
    def __init__(self):
        self._integrations: Dict[IntegrationType, BaseIntegration] = {}
        self._initialize_integrations()
    
    def _initialize_integrations(self):
        """Инициализация доступных интеграций"""
        
        # DMED
        if os.getenv("DMED_API_KEY"):
            self._integrations[IntegrationType.DMED] = DMEDIntegration()
            logger.info("✅ DMED integration initialized")
        
        # eGOV
        if os.getenv("EGOV_API_KEY"):
            self._integrations[IntegrationType.EGOV] = EGOVIntegration()
            logger.info("✅ eGOV integration initialized")
        
        # Insurance
        if os.getenv("INSURANCE_DEFAULT_API_KEY"):
            self._integrations[IntegrationType.INSURANCE] = InsuranceIntegration()
            logger.info("✅ Insurance integration initialized")
    
    def get_integration(self, integration_type: IntegrationType) -> Optional[BaseIntegration]:
        """Получить интеграцию по типу"""
        return self._integrations.get(integration_type)
    
    def get_available_integrations(self) -> List[str]:
        """Получить список доступных интеграций"""
        return [i.value for i in self._integrations.keys()]
    
    async def verify_patient_all(self, identifier: str) -> Dict[str, Any]:
        """
        Верификация пациента через все доступные источники
        
        Args:
            identifier: ПИНФЛ или номер полиса
            
        Returns:
            Результаты верификации из всех источников
        """
        results = {}
        
        for integration_type, integration in self._integrations.items():
            try:
                result = await integration.verify_patient(identifier)
                results[integration_type.value] = result
            except Exception as e:
                results[integration_type.value] = {"error": str(e)}
        
        return results


# Глобальный экземпляр
_integration_manager: Optional[IntegrationManager] = None


def get_integration_manager() -> IntegrationManager:
    """Получить глобальный экземпляр менеджера интеграций"""
    global _integration_manager
    if _integration_manager is None:
        _integration_manager = IntegrationManager()
    return _integration_manager
