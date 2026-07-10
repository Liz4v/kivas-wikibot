// Watches the wikifur.com cf_clearance cookie and forwards it, together with
// this browser's exact User-Agent, to the local `bot serve-cf` endpoint —
// which writes them straight into .env. cf_clearance is set as a
// Partitioned (CHIPS) cookie keyed to the wikifur.com top-level site, so it
// has to be looked up with that exact partitionKey or `cookies.getAll`
// silently omits it.

const DEFAULT_PORT = 8765;
const TOP_LEVEL_SITE = "https://wikifur.com";

async function getPort() {
  const { port } = await chrome.storage.local.get("port");
  return port || DEFAULT_PORT;
}

async function findCfClearance() {
  const cookies = await chrome.cookies.getAll({
    domain: "wikifur.com",
    partitionKey: { topLevelSite: TOP_LEVEL_SITE },
  });
  return cookies.find((c) => c.name === "cf_clearance") || null;
}

async function setStatus(text) {
  await chrome.storage.local.set({ lastStatus: text, lastStatusAt: Date.now() });
}

async function postToServer(cfClearance, userAgent, expiresAt) {
  const port = await getPort();
  const body = { cf_clearance: cfClearance, user_agent: userAgent };
  if (expiresAt) body.expires_at = expiresAt;

  try {
    const res = await fetch(`http://127.0.0.1:${port}/cf-clearance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      await setStatus(`sync failed: ${err.error || res.status}`);
      return false;
    }
    const expiryNote = expiresAt ? ` (cookie expires ${new Date(expiresAt * 1000).toLocaleString()})` : "";
    await setStatus(`synced at ${new Date().toLocaleTimeString()}${expiryNote}`);
    return true;
  } catch {
    await setStatus(`can't reach 127.0.0.1:${port} — is 'uv run bot serve-cf' running?`);
    return false;
  }
}

async function syncNow() {
  const cookie = await findCfClearance();
  if (!cookie) {
    await setStatus("no cf_clearance cookie found automatically — visit pt/en.wikifur.com, or paste it manually below");
    return false;
  }
  // Session cookies have no expirationDate; expiresAt stays undefined then.
  return postToServer(cookie.value, navigator.userAgent, cookie.expirationDate);
}

chrome.cookies.onChanged.addListener((changeInfo) => {
  if (changeInfo.cookie.name !== "cf_clearance") return;
  if (!changeInfo.cookie.domain.includes("wikifur.com")) return;
  syncNow();
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "sync-now") {
    syncNow().then((ok) => sendResponse({ ok }));
    return true; // keep the message channel open for the async response
  }
  if (msg?.type === "sync-pasted") {
    postToServer(msg.cfClearance, navigator.userAgent).then((ok) => sendResponse({ ok }));
    return true;
  }
});

// Fallback in case onChanged is missed for some reason.
chrome.alarms.create("periodic-sync", { periodInMinutes: 30 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "periodic-sync") syncNow();
});
