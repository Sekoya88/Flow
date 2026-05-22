import { getToken, getApiUrl } from "./auth";

export class FlowApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
  }
}

export async function flowFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const [token, baseUrl] = await Promise.all([getToken(), getApiUrl()]);
  const res = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    throw new FlowApiError(res.status, await res.text());
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export type Agent = { id: string; name: string };
export type Paper = {
  id: string;
  title: string;
  tldr: string | null;
  relevance_score: number;
  source_url: string | null;
  status: string;
};

export async function listAgents(workspaceId: string): Promise<Agent[]> {
  return flowFetch(`/api/v1/agents?workspace_id=${workspaceId}`);
}

export async function listPapers(workspaceId: string): Promise<Paper[]> {
  return flowFetch(
    `/api/v1/digest/papers?workspace_id=${workspaceId}&status=unread&limit=10`
  );
}

export async function runAgent(
  workspaceId: string,
  agentId: string,
  message: string
): Promise<{ execution_id: string }> {
  return flowFetch("/api/v1/executions", {
    method: "POST",
    body: JSON.stringify({
      workspace_id: workspaceId,
      agent_id: agentId,
      user_message: message,
    }),
  });
}

export async function ingestKnowledge(
  workspaceId: string,
  title: string,
  content: string,
  sourceUrl?: string
): Promise<{ id: string }> {
  return flowFetch("/api/v1/knowledge/ingest", {
    method: "POST",
    body: JSON.stringify({
      workspace_id: workspaceId,
      title,
      content,
      source_url: sourceUrl,
    }),
  });
}

export async function getMe(): Promise<{
  user: { id: string; email: string };
  workspaces: { id: string; name: string }[];
}> {
  return flowFetch("/api/v1/auth/me");
}
