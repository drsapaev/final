"""
MCP клиент для медицинских сервисов
"""
from typing import Dict, Any, Optional, List, Union
import asyncio
import logging
import json
from datetime import datetime
from .base_server import MCPRequest, MCPResponse
from .complaint_server import MedicalComplaintMCPServer
from .icd10_server import MedicalICD10MCPServer
from .lab_server import MedicalLabMCPServer
from .imaging_server import MedicalImagingMCPServer

logger = logging.getLogger(__name__)


class MedicalMCPClient:
    """Унифицированный MCP клиент для всех медицинских сервисов"""
    
    def __init__(self):
        self.servers: Dict[str, Any] = {}
        self.initialized = False
        self._request_counter = 0
        self._initialize_servers()
    
    def _initialize_servers(self):
        """Инициализация MCP серверов"""
        try:
            self.servers = {
                "complaint": MedicalComplaintMCPServer(),
                "icd10": MedicalICD10MCPServer(),
                "lab": MedicalLabMCPServer(),
                "imaging": MedicalImagingMCPServer()
            }
            logger.info("MCP servers initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MCP servers: {str(e)}")
            self.servers = {}
    
    async def initialize(self):
        """Асинхронная инициализация всех серверов"""
        if self.initialized:
            return
        
        try:
            init_tasks = []
            for name, server in self.servers.items():
                logger.info(f"Initializing {name} server...")
                init_tasks.append(server.initialize())
            
            await asyncio.gather(*init_tasks)
            self.initialized = True
            logger.info("All MCP servers initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MCP servers: {str(e)}")
            raise
    
    async def shutdown(self):
        """Завершение работы всех серверов"""
        try:
            shutdown_tasks = []
            for name, server in self.servers.items():
                logger.info(f"Shutting down {name} server...")
                shutdown_tasks.append(server.shutdown())
            
            await asyncio.gather(*shutdown_tasks)
            self.initialized = False
            logger.info("All MCP servers shut down successfully")
        except Exception as e:
            logger.error(f"Error shutting down MCP servers: {str(e)}")
    
    def _generate_request_id(self) -> str:
        """Генерация уникального ID запроса"""
        self._request_counter += 1
        return f"req_{self._request_counter}_{datetime.utcnow().timestamp()}"
    
    async def _call_server(
        self,
        server_name: str,
        method: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Вызов метода на MCP сервере"""
        if server_name not in self.servers:
            return {
                "status": "error",
                "error": f"Server '{server_name}' not found"
            }
        
        server = self.servers[server_name]
        request = MCPRequest(
            method=method,
            params=params,
            id=self._generate_request_id()
        )
        
        try:
            response = await server.handle_request(request)
            
            if response.error:
                return {
                    "status": "error",
                    "error": response.error.get("message", "Unknown error"),
                    "request_id": request.id
                }
            
            return {
                "status": "success",
                "data": response.result,
                "metadata": response.metadata,
                "request_id": request.id
            }
        except Exception as e:
            logger.error(f"Error calling {server_name}.{method}: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "request_id": request.id
            }
    
    # === COMPLAINT ANALYSIS ===
    
    async def analyze_complaint(
        self,
        complaint: str,
        patient_info: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        urgency_assessment: bool = True
    ) -> Dict[str, Any]:
        """Анализ жалоб пациента через MCP"""
        return await self._call_server(
            "complaint",
            "tool/analyze_complaint",
            {
                "complaint": complaint,
                "patient_info": patient_info,
                "provider": provider,
                "urgency_assessment": urgency_assessment
            }
        )
    
    async def validate_complaint(self, complaint: str) -> Dict[str, Any]:
        """Валидация жалоб через MCP"""
        return await self._call_server(
            "complaint",
            "tool/validate_complaint",
            {"complaint": complaint}
        )
    
    async def suggest_complaint_questions(
        self,
        complaint: str,
        specialty: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получение уточняющих вопросов по жалобам"""
        return await self._call_server(
            "complaint",
            "tool/suggest_questions",
            {
                "complaint": complaint,
                "specialty": specialty
            }
        )
    
    async def get_complaint_templates(
        self,
        specialty: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получение шаблонов жалоб"""
        return await self._call_server(
            "complaint",
            "resource/complaint_templates",
            {"specialty": specialty}
        )
    
    # === ICD-10 FUNCTIONS ===
    
    async def suggest_icd10(
        self,
        symptoms: List[str],
        diagnosis: Optional[str] = None,
        specialty: Optional[str] = None,
        provider: Optional[str] = None,
        max_suggestions: int = 5
    ) -> Dict[str, Any]:
        """Подсказки кодов МКБ-10"""
        return await self._call_server(
            "icd10",
            "tool/suggest_icd10",
            {
                "symptoms": symptoms,
                "diagnosis": diagnosis,
                "specialty": specialty,
                "provider": provider,
                "max_suggestions": max_suggestions
            }
        )
    
    async def validate_icd10(
        self,
        code: str,
        symptoms: Optional[List[str]] = None,
        diagnosis: Optional[str] = None
    ) -> Dict[str, Any]:
        """Валидация кода МКБ-10"""
        return await self._call_server(
            "icd10",
            "tool/validate_icd10",
            {
                "code": code,
                "symptoms": symptoms,
                "diagnosis": diagnosis
            }
        )
    
    async def search_icd10(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Поиск кодов МКБ-10"""
        return await self._call_server(
            "icd10",
            "tool/search_icd10",
            {
                "query": query,
                "category": category,
                "limit": limit
            }
        )
    
    async def get_common_icd10_codes(
        self,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получение часто используемых кодов МКБ-10"""
        return await self._call_server(
            "icd10",
            "resource/common_icd10_codes",
            {"category": category}
        )
    
    # === LAB ANALYSIS ===
    
    async def interpret_lab_results(
        self,
        results: List[Dict[str, Any]],
        patient_info: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        include_recommendations: bool = True
    ) -> Dict[str, Any]:
        """Интерпретация лабораторных результатов"""
        return await self._call_server(
            "lab",
            "tool/interpret_lab_results",
            {
                "results": results,
                "patient_info": patient_info,
                "provider": provider,
                "include_recommendations": include_recommendations
            }
        )
    
    async def check_critical_lab_values(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Проверка критических значений в анализах"""
        return await self._call_server(
            "lab",
            "tool/check_critical_values",
            {"results": results}
        )
    
    async def suggest_follow_up_tests(
        self,
        current_results: List[Dict[str, Any]],
        abnormal_findings: List[str],
        clinical_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Рекомендации дополнительных анализов"""
        return await self._call_server(
            "lab",
            "tool/suggest_follow_up_tests",
            {
                "current_results": current_results,
                "abnormal_findings": abnormal_findings,
                "clinical_context": clinical_context
            }
        )
    
    async def get_normal_ranges(
        self,
        test_name: Optional[str] = None,
        patient_gender: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получение нормальных диапазонов для анализов"""
        return await self._call_server(
            "lab",
            "resource/normal_ranges",
            {
                "test_name": test_name,
                "patient_gender": patient_gender
            }
        )
    
    async def get_test_panels(
        self,
        panel_name: Optional[str] = None,
        indication: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получение панелей анализов"""
        return await self._call_server(
            "lab",
            "resource/test_panels",
            {
                "panel_name": panel_name,
                "indication": indication
            }
        )
    
    # === IMAGING ANALYSIS ===
    
    async def analyze_medical_image(
        self,
        image_data: str,
        image_type: str,
        modality: Optional[str] = None,
        clinical_context: Optional[str] = None,
        patient_info: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Анализ медицинского изображения"""
        return await self._call_server(
            "imaging",
            "tool/analyze_medical_image",
            {
                "image_data": image_data,
                "image_type": image_type,
                "modality": modality,
                "clinical_context": clinical_context,
                "patient_info": patient_info,
                "provider": provider
            }
        )
    
    async def analyze_skin_lesion(
        self,
        image_data: str,
        lesion_info: Optional[Dict[str, Any]] = None,
        patient_history: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Анализ кожных образований"""
        return await self._call_server(
            "imaging",
            "tool/analyze_skin_lesion",
            {
                "image_data": image_data,
                "lesion_info": lesion_info,
                "patient_history": patient_history,
                "provider": provider
            }
        )
    
    async def compare_medical_images(
        self,
        image1_data: str,
        image2_data: str,
        comparison_type: str,
        time_interval: Optional[str] = None
    ) -> Dict[str, Any]:
        """Сравнение медицинских изображений"""
        return await self._call_server(
            "imaging",
            "tool/compare_images",
            {
                "image1_data": image1_data,
                "image2_data": image2_data,
                "comparison_type": comparison_type,
                "time_interval": time_interval
            }
        )
    
    async def get_imaging_types(
        self,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получение информации о типах изображений"""
        return await self._call_server(
            "imaging",
            "resource/imaging_types",
            {"category": category}
        )
    
    # === UTILITY FUNCTIONS ===
    
    async def get_server_capabilities(
        self,
        server_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получение возможностей серверов"""
        if server_name:
            if server_name in self.servers:
                return {
                    "status": "success",
                    "server": server_name,
                    "capabilities": self.servers[server_name].get_capabilities()
                }
            else:
                return {
                    "status": "error",
                    "error": f"Server '{server_name}' not found"
                }
        
        # Возвращаем возможности всех серверов
        all_capabilities = {}
        for name, server in self.servers.items():
            all_capabilities[name] = server.get_capabilities()
        
        return {
            "status": "success",
            "servers": all_capabilities
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка состояния всех серверов"""
        health_status = {
            "overall": "healthy",
            "servers": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for name, server in self.servers.items():
            try:
                # Простой тест - получаем возможности
                capabilities = server.get_capabilities()
                health_status["servers"][name] = {
                    "status": "healthy",
                    "tools_count": len(capabilities.get("tools", [])),
                    "resources_count": len(capabilities.get("resources", []))
                }
            except Exception as e:
                health_status["servers"][name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health_status["overall"] = "degraded"
        
        return health_status
    
    async def batch_process(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Пакетная обработка запросов"""
        tasks = []
        
        for req in requests:
            server_name = req.get("server")
            method = req.get("method")
            params = req.get("params", {})
            
            if not server_name or not method:
                tasks.append(asyncio.create_task(
                    asyncio.coroutine(lambda: {
                        "status": "error",
                        "error": "Missing server or method"
                    })()
                ))
            else:
                tasks.append(self._call_server(server_name, method, params))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обработка исключений
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "status": "error",
                    "error": str(result),
                    "request_index": i
                })
            else:
                result["request_index"] = i
                processed_results.append(result)
        
        return processed_results


# Глобальный экземпляр клиента
_mcp_client: Optional[MedicalMCPClient] = None


async def get_mcp_client() -> MedicalMCPClient:
    """Получить или создать глобальный экземпляр MCP клиента"""
    global _mcp_client
    
    if _mcp_client is None:
        _mcp_client = MedicalMCPClient()
        await _mcp_client.initialize()
    
    return _mcp_client


async def shutdown_mcp_client():
    """Завершить работу MCP клиента"""
    global _mcp_client
    
    if _mcp_client is not None:
        await _mcp_client.shutdown()
        _mcp_client = None
