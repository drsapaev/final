/**
 * useMcpClient — hook wrapper for the MCP (Model Context Protocol) API.
 *
 * Per ADR-0015, components must NOT import from `api/mcpClient` directly.
 * This hook is the sanctioned entry point.
 *
 * The MCP API client (`api/mcpClient.ts: mcpAPI`) is a large object with
 * ~30 methods. Wrapping each in a separate hook method would be pure
 * boilerplate. Instead, this hook returns the `mcpAPI` object via the
 * hook layer — the import boundary is enforced, but the call surface is
 * unchanged.
 *
 * Components should call:
 *   const mcpAPI = useMcpClient();
 *   const status = await mcpAPI.getStatus();
 *
 * Tests that mock `api/mcpClient` continue to work because the hook
 * returns the same object reference.
 */

import { mcpAPI } from '../api/mcpClient';

// Re-export the type for callers that need it.
export type McpAPI = typeof mcpAPI;

export function useMcpClient(): McpAPI {
  // mcpAPI is a stable singleton (module-level const). Returning it directly
  // is safe — the reference never changes.
  return mcpAPI;
}

export default useMcpClient;
