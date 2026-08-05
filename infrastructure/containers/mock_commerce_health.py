"""Infrastructure-only health shell for the Phase 1 Mock-Commerce container."""

from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def require_environment(name: str) -> None:
    if not os.environ.get(name, "").strip():
        raise RuntimeError(f"required environment variable is missing: {name}")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        body = b'{"status":"ready","service":"mock-commerce"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    require_environment("COMMERCE_DATABASE_URL")
    require_environment("INTERNAL_SERVICE_TOKEN")
    ThreadingHTTPServer(("0.0.0.0", 8080), HealthHandler).serve_forever()
