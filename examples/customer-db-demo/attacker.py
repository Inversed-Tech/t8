#!/usr/bin/env python3
"""Exfiltration canary for the T8 demo.

Stands in for an attacker-controlled server the agent might be tricked into
sending data to. It logs LOUDLY whenever anything arrives. During the demo this
pane stays SILENT when traffic goes through T8 (egress blocked) — absence of
output is the proof, not our narration. In the --no-t8 counterfactual it lights
up, showing the leak that T8 prevents.

Stdlib only.
"""
import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", "8091"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _capture(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else b""
        preview = body[:300].decode("utf-8", "replace")
        print("\n" + "!" * 70, flush=True)
        print(f"!!! EXFILTRATION RECEIVED  {self.command} {self.path}", flush=True)
        print(f"!!! {length} bytes of customer data landed on the attacker server", flush=True)
        print(f"!!! preview: {preview}", flush=True)
        print("!" * 70 + "\n", flush=True)
        out = json.dumps({"received": True, "bytes": length}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    do_GET = _capture
    do_POST = _capture


if __name__ == "__main__":
    print(f"[attacker] listening on :{PORT} — waiting for stolen data (should stay silent via T8)",
          flush=True)
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
