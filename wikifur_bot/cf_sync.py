"""Local HTTP endpoint for the CF-clearance browser extension.

Cloudflare's cf_clearance cookie expires periodically and has to be copied
from a real browser session into .env (CF_CLEARANCE + USER_AGENT_SPOOF),
bound together. `bot serve-cf` runs a tiny loopback-only server that the
companion browser extension (browser-extension/) POSTs the current cookie
and User-Agent to, so refreshing .env doesn't require manual copy/paste.
"""

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dotenv import find_dotenv, set_key


class _Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        self._send_json(200, {"status": "ok", "env_file": find_dotenv() or None})

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/cf-clearance":
            self._send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
            return

        cf_clearance = (data.get("cf_clearance") or "").strip()
        user_agent = (data.get("user_agent") or "").strip()
        if not cf_clearance or not user_agent:
            self._send_json(400, {"error": "cf_clearance and user_agent are both required"})
            return

        path = find_dotenv()
        if not path:
            self._send_json(500, {"error": ".env not found"})
            return

        set_key(path, "CF_CLEARANCE", cf_clearance)
        set_key(path, "USER_AGENT_SPOOF", user_agent)

        expiry_note = ""
        expires_at = data.get("expires_at")
        if expires_at:
            try:
                expires = datetime.fromtimestamp(float(expires_at), tz=timezone.utc)
            except (TypeError, ValueError, OverflowError, OSError):
                pass
            else:
                set_key(path, "CF_CLEARANCE_EXPIRES", expires.isoformat())
                expiry_note = f", expires {expires.isoformat()}"

        print(
            f"[cf-sync] updated CF_CLEARANCE ({len(cf_clearance)} chars) + USER_AGENT_SPOOF "
            f"from {self.client_address[0]}{expiry_note}"
        )
        self._send_json(200, {"status": "updated"})

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib override
        print(f"[cf-sync] {self.address_string()} - {format % args}")


def cmd_serve_cf(args: argparse.Namespace) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", args.port), _Handler)
    print(f"Listening on http://127.0.0.1:{args.port} (Ctrl+C to stop)")
    print("Point the browser extension at this port; it POSTs cf_clearance + User-Agent")
    print("here whenever the cookie changes, and this writes them straight into .env.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
