#!/usr/bin/env python3
"""Mock 'partner directory' enrichment API for the T8 demo.

A benign third-party service the agent may legitimately want to reach. It is NOT on
the default egress allowlist, so the agent's fetch is refused until an admin allowlists
it (./admin.sh allow-host partner) — the payoff for the egress admin knob.

Stdlib only.
"""
import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", "8092"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        out = json.dumps({
            "partner": "acme-directory",
            "enrichment": {"company": "Acme Corp", "segment": "SMB",
                           "industry": "Manufacturing", "verified": True},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


if __name__ == "__main__":
    print(f"[partner] listening on :{PORT} — enrichment directory (off the allowlist by default)",
          flush=True)
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
