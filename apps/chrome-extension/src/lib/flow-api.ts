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
  const res = await flowFetch<{ agents: Agent[] }>(`/api/v1/workspaces/${workspaceId}/agents`);
  return res.agents;
}

export async function listPapers(workspaceId: string, status?: string): Promise<Paper[]> {
  const params = new URLSearchParams({ workspace_id: workspaceId, limit: "50" });
  if (status) params.set("status", status);
  return flowFetch(`/api/v1/digest/papers?${params}`);
}

export async function deletePaper(paperId: string): Promise<void> {
  await flowFetch(`/api/v1/digest/papers/${paperId}`, { method: "DELETE" });
}

export async function patchPaper(paperId: string, status: string): Promise<void> {
  await flowFetch(`/api/v1/digest/papers/${paperId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function runDigest(workspaceId: string): Promise<{ job_id: string }> {
  return flowFetch("/api/v1/digest/run", {
    method: "POST",
    body: JSON.stringify({ workspace_id: workspaceId }),
  });
}

export async function runAgent(
  _workspaceId: string,
  agentId: string,
  message: string
): Promise<{ execution_id: string }> {
  return flowFetch(`/api/v1/agents/${agentId}/execute`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export async function ingestKnowledge(
  workspaceId: string,
  title: string,
  body: string
): Promise<{ id: string }> {
  return flowFetch("/api/v1/knowledge", {
    method: "POST",
    body: JSON.stringify({ workspace_id: workspaceId, title, body }),
  });
}

export async function flowUpload<T>(path: string, formData: FormData): Promise<T> {
  const [token, baseUrl] = await Promise.all([getToken(), getApiUrl()]);
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) throw new FlowApiError(res.status, await res.text());
  if (res.status === 204) return undefined as T;
  return res.json();
}

export async function ingestImageKnowledge(
  workspaceId: string,
  imageBlob: Blob,
  filename: string
): Promise<{ id: string }> {
  const formData = new FormData();
  formData.append("workspace_id", workspaceId);
  formData.append("image", imageBlob, filename);
  return flowUpload("/api/v1/knowledge/from-image", formData);
}

export async function getMe(): Promise<{
  user: { id: string; email: string };
  workspaces: { id: string; name: string }[];
}> {
  return flowFetch("/api/v1/auth/me");
}
