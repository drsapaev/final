"""
Базовый MCP сервер для медицинских сервисов
"""
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import logging
import json
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MCPTool:
    """Декоратор для MCP инструментов"""
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
    
    def __call__(self, func: Callable) -> Callable:
        func._mcp_tool = True
        func._mcp_name = self.name
        func._mcp_description = self.description
        return func


class MCPResource:
    """Декоратор для MCP ресурсов"""
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
    
    def __call__(self, func: Callable) -> Callable:
        func._mcp_resource = True
        func._mcp_name = self.name
        func._mcp_description = self.description
        return func


class MCPRequest(BaseModel):
    """Базовая модель запроса MCP"""
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)
    id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MCPResponse(BaseModel):
    """Базовая модель ответа MCP"""
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseMCPServer(ABC):
    """Базовый класс для MCP серверов"""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.tools: Dict[str, Callable] = {}
        self.resources: Dict[str, Callable] = {}
        self._register_tools_and_resources()
        logger.info(f"MCP Server '{self.name}' v{self.version} initialized")
    
    def _register_tools_and_resources(self):
        """Автоматическая регистрация инструментов и ресурсов"""
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, '_mcp_tool'):
                self.tools[attr._mcp_name] = attr
                logger.debug(f"Registered tool: {attr._mcp_name}")
            elif hasattr(attr, '_mcp_resource'):
                self.resources[attr._mcp_name] = attr
                logger.debug(f"Registered resource: {attr._mcp_name}")
    
    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Обработка MCP запроса"""
        try:
            # Проверяем тип метода
            if request.method.startswith("tool/"):
                tool_name = request.method.replace("tool/", "")
                return await self._handle_tool(tool_name, request)
            elif request.method.startswith("resource/"):
                resource_name = request.method.replace("resource/", "")
                return await self._handle_resource(resource_name, request)
            else:
                return MCPResponse(
                    error={"code": -32601, "message": f"Method not found: {request.method}"},
                    id=request.id
                )
        except Exception as e:
            logger.error(f"Error handling MCP request: {str(e)}")
            return MCPResponse(
                error={"code": -32603, "message": str(e)},
                id=request.id
            )
    
    async def _handle_tool(self, tool_name: str, request: MCPRequest) -> MCPResponse:
        """Обработка вызова инструмента"""
        if tool_name not in self.tools:
            return MCPResponse(
                error={"code": -32601, "message": f"Tool not found: {tool_name}"},
                id=request.id
            )
        
        try:
            tool = self.tools[tool_name]
            result = await tool(**request.params)
            
            return MCPResponse(
                result=result,
                id=request.id,
                metadata={
                    "tool": tool_name,
                    "server": self.name,
                    "version": self.version
                }
            )
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            return MCPResponse(
                error={"code": -32603, "message": f"Tool execution failed: {str(e)}"},
                id=request.id
            )
    
    async def _handle_resource(self, resource_name: str, request: MCPRequest) -> MCPResponse:
        """Обработка запроса ресурса"""
        if resource_name not in self.resources:
            return MCPResponse(
                error={"code": -32601, "message": f"Resource not found: {resource_name}"},
                id=request.id
            )
        
        try:
            resource = self.resources[resource_name]
            result = await resource(**request.params)
            
            return MCPResponse(
                result=result,
                id=request.id,
                metadata={
                    "resource": resource_name,
                    "server": self.name,
                    "version": self.version
                }
            )
        except Exception as e:
            logger.error(f"Error accessing resource {resource_name}: {str(e)}")
            return MCPResponse(
                error={"code": -32603, "message": f"Resource access failed: {str(e)}"},
                id=request.id
            )
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Получить список возможностей сервера"""
        return {
            "server": {
                "name": self.name,
                "version": self.version
            },
            "tools": [
                {
                    "name": name,
                    "description": getattr(func, '_mcp_description', '')
                }
                for name, func in self.tools.items()
            ],
            "resources": [
                {
                    "name": name,
                    "description": getattr(func, '_mcp_description', '')
                }
                for name, func in self.resources.items()
            ]
        }
    
    @abstractmethod
    async def initialize(self):
        """Инициализация сервера"""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Завершение работы сервера"""
        pass
