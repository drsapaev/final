"""
MCP (Model Context Protocol) интеграция для медицинской клиники
"""

from .base_server import BaseMCPServer
from .complaint_server import MedicalComplaintMCPServer
from .icd10_server import MedicalICD10MCPServer
from .imaging_server import MedicalImagingMCPServer
from .lab_server import MedicalLabMCPServer
from .mcp_client import get_mcp_client, MedicalMCPClient
from .mcp_manager import get_mcp_manager, MCPManager

__all__ = [
    'BaseMCPServer',
    'MedicalMCPClient',
    'get_mcp_client',
    'MedicalComplaintMCPServer',
    'MedicalICD10MCPServer',
    'MedicalLabMCPServer',
    'MedicalImagingMCPServer',
    'MCPManager',
    'get_mcp_manager',
]
