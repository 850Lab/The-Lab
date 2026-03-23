"""
server.py | 850 Lab
Standalone Stripe webhook server on port 5001.
Runs as a separate process alongside Streamlit.
"""

import sys
import json
from http.server import HTTPServer, BaseHTTPRequestHandler


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/webhook/stripe":
            content_length = int(self.headers.get("Content-Length", 0))
            payload = self.rfile.read(content_length)
            sig_header = self.headers.get("Stripe-Signature", "")

            from webhook_handler import handle_stripe_webhook
            result = handle_stripe_webhook(payload, sig_header)

            self.send_response(result.get("status", 200))
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(result.get("body", "OK").encode())
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_GET(self):
        if self.path == "/webhook/stripe":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "active",
                "endpoint": "/webhook/stripe",
                "method": "POST",
            }).encode())
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        print(f"[webhook] {args[0]}", file=sys.stderr, flush=True)


def main():
    port = 5001
    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    print(f"[webhook] Stripe webhook server listening on port {port}", file=sys.stderr, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
