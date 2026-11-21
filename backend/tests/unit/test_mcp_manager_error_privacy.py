"""MCP transport errors must not expose clinical content."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.mcp.mcp_manager import MCPManager


@pytest.mark.asyncio
async def test_mcp_provider_exception_is_generic_and_preserves_failure_tracking(caplog):
    marker = "SYNTHETIC-CLINICAL-CANARY"
    manager = MCPManager()
    manager.config["enabled"] = True
    manager.client = SimpleNamespace(_call_server=AsyncMock(side_effect=RuntimeError(marker)))

    with caplog.at_level("ERROR", logger="app.services.mcp.mcp_manager"):
        response = await manager.execute_request("lab", "tool/interpret_lab_results", {})

    assert response["status"] == "error"
    assert response["layer"] == "mcp_manager"
    assert response["server"] == "lab"
    assert response["method"] == "tool/interpret_lab_results"
    assert manager.metrics["requests_failed"] == 1
    assert manager._server_failures["lab"] == 1
    assert marker not in repr(response)
    assert marker not in caplog.text
    records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert records and all(record.exc_info is None for record in records)


@pytest.mark.asyncio
async def test_complaint_provider_errors_are_not_logged_before_mcp_boundary(caplog):
    from app.services.mcp.complaint_server import MedicalComplaintMCPServer

    marker = "SYNTHETIC-CLINICAL-CANARY"
    server = MedicalComplaintMCPServer()
    server.validate_complaint = AsyncMock(return_value={"valid": True})
    server.ai_manager = SimpleNamespace(analyze_complaint=AsyncMock(
        side_effect=[{"error": marker}, RuntimeError(marker), RuntimeError(marker), RuntimeError(marker)]
    ))

    with caplog.at_level("INFO", logger="app.services.mcp.complaint_server"):
        await server.analyze_complaint("SYNTHETIC", urgency_assessment=False)

    assert marker not in caplog.text


@pytest.mark.asyncio
async def test_nested_error_fields_are_sanitized_without_changing_success_or_fallback():
    marker = "SYNTHETIC-CLINICAL-CANARY"
    source = {
        "status": "success",
        "data": {
            "status": "error", "error": marker, "message": marker, "detail": marker,
            "fallback": True, "results": [{"success": False, "reason": marker}],
        },
        "metadata": {"source": "SYNTHETIC"},
    }
    manager = MCPManager()
    manager.config["enabled"] = True
    manager.client = SimpleNamespace(_call_server=AsyncMock(return_value=source))

    result = await manager.execute_request("lab", "tool/interpret_lab_results", {})

    assert result["status"] == "success"
    assert result["data"]["status"] == "error"
    assert result["data"]["fallback"] is True
    assert result["metadata"] == {"source": "SYNTHETIC"}
    assert result["data"]["results"][0]["success"] is False
    assert marker not in repr(result)
    assert source["data"]["error"] == marker


@pytest.mark.asyncio
async def test_mcp_success_content_and_empty_error_remain_unchanged():
    source = {"status": "success", "data": {"message": "SYNTHETIC", "error": ""}}
    manager = MCPManager()
    manager.config["enabled"] = True
    manager.client = SimpleNamespace(_call_server=AsyncMock(return_value=source))

    result = await manager.execute_request("lab", "tool/interpret_lab_results", {})

    assert result["status"] == "success"
    assert result["data"] == source["data"]
