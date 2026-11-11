import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def response_for_path(path: str) -> tuple[int, dict[str, str]]:
    if path == "/healthz" or path == "/readyz":
        return 200, {"status": "ok"}
    if path == "/":
        return 200, {
            "app": "gitops-sample-app",
            "environment": os.environ.get("APP_ENV", "local"),
            "version": os.environ.get("APP_VERSION", "local"),
        }
    return 404, {"error": "not found"}


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        status, body = response_for_path(self.path)
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        print("%s - %s" % (self.address_string(), format % args))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), RequestHandler)
    server.serve_forever()
