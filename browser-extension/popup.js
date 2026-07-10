const portInput = document.getElementById("port");
const cookieInput = document.getElementById("cookie");
const statusEl = document.getElementById("status");
const syncBtn = document.getElementById("sync");
const syncPastedBtn = document.getElementById("syncPasted");

async function refreshStatus() {
  const { port, lastStatus } = await chrome.storage.local.get(["port", "lastStatus"]);
  portInput.value = port || 8765;
  statusEl.textContent = lastStatus || "not synced yet";
}

portInput.addEventListener("change", () => {
  chrome.storage.local.set({ port: Number(portInput.value) || 8765 });
});

syncBtn.addEventListener("click", async () => {
  statusEl.textContent = "syncing...";
  await chrome.runtime.sendMessage({ type: "sync-now" });
  refreshStatus();
});

syncPastedBtn.addEventListener("click", async () => {
  const cfClearance = cookieInput.value.trim();
  if (!cfClearance) {
    statusEl.textContent = "paste the cf_clearance value first";
    return;
  }
  statusEl.textContent = "syncing...";
  await chrome.runtime.sendMessage({ type: "sync-pasted", cfClearance });
  cookieInput.value = "";
  refreshStatus();
});

refreshStatus();
