# WikiFur CF-clearance sync (temporary)

Unpacked browser extension that keeps `CF_CLEARANCE` and `USER_AGENT_SPOOF`
in `.env` synced with a real browser session, so you don't have to copy the
cookie out of devtools by hand every time it expires. Remove it once the
WikiFur Cloudflare admin adds a WAF exception for the bot — it's a
workaround, not a permanent fixture.

Cloudflare's `cf_clearance` cookie here is a `Partitioned` (CHIPS) cookie
keyed to the `https://wikifur.com` top-level site, so `chrome.cookies`
lookups have to pass that exact `partitionKey` or they silently miss it —
a plain `cookies.get`/`getAll` by URL returns nothing. Once queried with the
right `partitionKey`, it works fine.

## How it works

1. `uv run bot serve-cf` starts a loopback-only HTTP server (default port
   8765) that writes whatever it receives into `.env`.
2. The extension watches the `cf_clearance` cookie on `*.wikifur.com`
   (queried with `partitionKey: { topLevelSite: "https://wikifur.com" }`).
   When it changes (or on a 30-minute fallback timer, or when you click
   "Sync now" in the popup), it POSTs `{cf_clearance, user_agent}` — using
   `navigator.userAgent`, i.e. this exact browser's real UA — to that local
   server.
3. If auto-detection ever breaks again (e.g. Cloudflare changes how the
   cookie is scoped), the popup has a "Paste manually instead" fallback:
   paste the value from DevTools → Application → Cookies and click
   "Sync pasted value".

## Setup (Vivaldi, or any Chromium-based browser)

1. In a terminal, from the repo root: `uv run bot serve-cf` and leave it
   running.
2. Go to `vivaldi://extensions`, enable **Developer mode** (top right),
   click **Load unpacked**, and select this `browser-extension/` folder.
3. Visit `https://pt.wikifur.com` or `https://en.wikifur.com` normally so
   Cloudflare's challenge runs once and sets the cookie.
4. The extension should sync automatically — check the popup (click its
   toolbar icon) for the last sync status, or hit **Sync now**.
5. Confirm it worked: `.env` should now have `CF_CLEARANCE` and
   `USER_AGENT_SPOOF` filled in, matching this browser.

If the popup says it can't reach `127.0.0.1:8765`, make sure `bot serve-cf`
is still running in a terminal.

## Uninstall

`vivaldi://extensions` → remove. Also fine to stop `bot serve-cf` at any
time — nothing else depends on it running.
