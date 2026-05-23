import { flowFetch } from "./flow-api";

export type MCPServer = {
  id: string;
  workspace_id: string;
  name: string;
  url: string;
  transport: string;
  active: boolean;
};

export type MCPTool = {
  id: string;
  mcp_server_id: string;
  tool_name: string;
  enabled: boolean;
};

export async function listMCPServers(workspaceId: string): Promise<MCPServer[]> {
  return flowFetch(`/api/v1/mcp/servers?workspace_id=${workspaceId}`);
}

export async function pingMCPServer(serverId: string): Promise<{ ok: boolean; status_code?: number; error?: string }> {
  return flowFetch(`/api/v1/mcp/servers/${serverId}/ping`);
}

export async function listMCPTools(serverId: string): Promise<MCPTool[]> {
  return flowFetch(`/api/v1/mcp/servers/${serverId}/tools`);
}
