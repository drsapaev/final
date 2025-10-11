"""
MCP (Model Context Protocol) интеграция для медицинской клиники
"""

from .base_server import BaseMCPServer
from .mcp_client import MedicalMCPClient, get_mcp_client
from .complaint_server import MedicalComplaintMCPServer
from .icd10_server import MedicalICD10MCPServer
from .lab_server import MedicalLabMCPServer
from .imaging_server import MedicalImagingMCPServer
from .mcp_manager import MCPManager, get_mcp_manager

__all__ = [
    'BaseMCPServer',
    'MedicalMCPClient',
    'get_mcp_client',
    'MedicalComplaintMCPServer',
    'MedicalICD10MCPServer',
    'MedicalLabMCPServer',
    'MedicalImagingMCPServer',
    'MCPManager',
    'get_mcp_manager'
]
