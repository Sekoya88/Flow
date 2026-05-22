export const TOKEN_KEY = "flow_jwt";
export const API_URL_KEY = "flow_api_url";
export const DEFAULT_API_URL = "http://localhost:18000";

export async function getToken(): Promise<string | null> {
  const result = await chrome.storage.local.get(TOKEN_KEY);
  return result[TOKEN_KEY] ?? null;
}

export async function setToken(token: string): Promise<void> {
  await chrome.storage.local.set({ [TOKEN_KEY]: token });
}

export async function clearToken(): Promise<void> {
  await chrome.storage.local.remove(TOKEN_KEY);
}

export async function getApiUrl(): Promise<string> {
  const result = await chrome.storage.local.get(API_URL_KEY);
  return result[API_URL_KEY] ?? DEFAULT_API_URL;
}
