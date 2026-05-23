let tooltip: HTMLElement | null = null;

function removeTooltip() {
  tooltip?.remove();
  tooltip = null;
}

document.addEventListener("mouseup", () => {
  const selection = window.getSelection();
  const text = selection?.toString().trim() ?? "";

  removeTooltip();
  if (text.length < 10) return;

  const range = selection!.getRangeAt(0);
  const rect = range.getBoundingClientRect();

  tooltip = document.createElement("div");
  tooltip.textContent = "📥 Save to Flow";
  Object.assign(tooltip.style, {
    position: "fixed",
    top: `${rect.top + window.scrollY - 36}px`,
    left: `${rect.left + rect.width / 2}px`,
    transform: "translateX(-50%)",
    background: "#1a1a2e",
    color: "#e2e2ff",
    border: "1px solid #3d3d7f",
    borderRadius: "6px",
    padding: "4px 10px",
    fontSize: "11px",
    fontFamily: "monospace",
    cursor: "pointer",
    zIndex: "2147483647",
    boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
    userSelect: "none",
    whiteSpace: "nowrap",
  });

  tooltip.addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "SAVE_SELECTION", text });
    removeTooltip();
  });

  document.body.appendChild(tooltip);
});

document.addEventListener("mousedown", (e) => {
  if (e.target !== tooltip) removeTooltip();
});
