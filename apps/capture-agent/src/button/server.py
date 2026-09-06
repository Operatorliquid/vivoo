from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from inference.events import NormalizedCaptureEvent

from .protocol import ButtonEventError, ButtonEventNormalizer, parse_json_payload


class ButtonEventReceiver:
    def __init__(self, secret: str, on_event: Callable[[NormalizedCaptureEvent], None], normalizer: ButtonEventNormalizer | None = None) -> None:
        self.on_event = on_event
        self.normalizer = normalizer or ButtonEventNormalizer(secret)

    def receive(self, body: bytes) -> NormalizedCaptureEvent | None:
        event = self.normalizer.normalize(parse_json_payload(body))
        if event is not None:
            self.on_event(event)
        return event


def serve_button_receiver(receiver: ButtonEventReceiver, host: str = "0.0.0.0", port: int = 8790) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/button/press":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                event = receiver.receive(self.rfile.read(length))
            except (ValueError, ButtonEventError) as error:
                body = json.dumps({"accepted": False, "error": str(error)}).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            body = json.dumps({"accepted": event is not None, "source_id": event.source_id if event else None}).encode("utf-8")
            self.send_response(202)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)
