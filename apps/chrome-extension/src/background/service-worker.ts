import { getToken, getApiUrl, TOKEN_KEY } from "../lib/auth";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "flow-save",
    title: "Save to Flow",
    contexts: ["selection"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "flow-save") return;
  const text = info.selectionText ?? "";
  if (!text) return;

  const token = await getToken();
  if (!token) {
    chrome.notifications.create({
      type: "basic",
      iconUrl: "../icons/icon48.png",
      title: "Flow",
      message: "Not logged in. Open the Flow extension to sign in.",
    });
    return;
  }

  const baseUrl = await getApiUrl();
  try {
    const meRes = await fetch(`${baseUrl}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!meRes.ok) throw new Error("auth");
    const me = await meRes.json();
    const wsId = me.workspaces?.[0]?.id;
    if (!wsId) return;

    await fetch(`${baseUrl}/api/v1/knowledge/ingest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        workspace_id: wsId,
        title: tab?.title ?? "Web capture",
        content: text,
        source_url: tab?.url,
      }),
    });

    chrome.notifications.create({
      type: "basic",
      iconUrl: "../icons/icon48.png",
      title: "Flow",
      message: "Saved to knowledge base.",
    });
  } catch {
    chrome.notifications.create({
      type: "basic",
      iconUrl: "../icons/icon48.png",
      title: "Flow",
      message: "Failed to save. Check your connection.",
    });
  }
});
