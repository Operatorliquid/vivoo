from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from camera.preview import stream_mjpeg
from runtime.supervisor import MultiCameraSupervisor


def serve_local_agent(runtime: MultiCameraSupervisor, host: str = "127.0.0.1", port: int = 8781) -> ThreadingHTTPServer:
    def selected(camera_id: str | None):
        return runtime.runtime(camera_id) if hasattr(runtime, "runtime") else runtime

    class Handler(BaseHTTPRequestHandler):
        def _headers(self, status: int = 200, content_type: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")

        def _json(self, value: Any, status: int = 200) -> None:
            body = json.dumps(value, default=str).encode("utf-8")
            self._headers(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0"))
            value = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(value, dict):
                raise ValueError("El payload debe ser un objeto")
            return value

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._headers(204)
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            path = urlsplit(self.path).path
            camera_id = parse_qs(urlsplit(self.path).query).get("camera_id", [None])[0]
            if path == "/":
                body = Path(__file__).with_name("index.html").read_bytes()
                self._headers(200, "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/v1/status":
                try:
                    self._json(runtime.safe_status(camera_id) if hasattr(runtime, "runtime") else runtime.safe_status())
                except ValueError as error:
                    self._json({"error": str(error)}, 404)
                return
            if path == "/v1/config":
                try:
                    selected_runtime = selected(camera_id)
                except ValueError as error:
                    self._json({"error": str(error)}, 404)
                    return
                self._json({
                    "cloud_api_url": selected_runtime.config.cloud_api_url,
                    "camera": selected_runtime.safe_status()["camera"],
                    "detector": {
                        "model": selected_runtime.config.pose_model,
                        "device": selected_runtime.config.pose_device,
                        "image_size": selected_runtime.config.pose_image_size,
                        "person_confidence": selected_runtime.config.pose_person_confidence,
                        "keypoint_confidence": selected_runtime.config.pose_keypoint_confidence,
                        "roi": selected_runtime.config.pose_roi,
                        "min_person_height_ratio": selected_runtime.config.pose_min_person_height_ratio,
                        "min_wrist_spread_ratio": selected_runtime.config.pose_min_wrist_spread_ratio,
                        "hold_seconds": selected_runtime.config.gesture_hold_seconds,
                        "cooldown_seconds": selected_runtime.config.gesture_cooldown_seconds,
                        "release_seconds": selected_runtime.config.gesture_release_seconds,
                        "minimum_wrist_lift_ratio": selected_runtime.config.gesture_min_wrist_lift_ratio,
                        "minimum_local_motion": selected_runtime.config.gesture_min_local_motion,
                        "max_gap_seconds": selected_runtime.config.gesture_max_gap_seconds,
                    },
                })
                return
            if path == "/v1/preview.mjpeg":
                mode = parse_qs(urlsplit(self.path).query).get("mode", ["preview"])[0]
                fps = 15 if mode == "live" else 1
                try:
                    selected_runtime = selected(camera_id)
                    stream = stream_mjpeg(
                        selected_runtime.config.media_rtsp_url,
                        fps,
                        selected_runtime.config.pose_rotation_degrees,
                    )
                    self._headers(200, "multipart/x-mixed-replace; boundary=ffmpeg")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Accel-Buffering", "no")
                    self.end_headers()
                    for chunk in stream:
                        self.wfile.write(chunk)
                except ValueError as error:
                    self._json({"error": str(error)}, 404)
                    return
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return
                return
            self._json({"error": "Not found"}, 404)

        def do_POST(self) -> None:  # noqa: N802
            try:
                path = urlsplit(self.path).path
                camera_id = parse_qs(urlsplit(self.path).query).get("camera_id", [None])[0]
                if path == "/v1/check":
                    selected_runtime = selected(camera_id)
                    self._json(selected_runtime.check_camera())
                    return
                if path == "/v1/recording/start":
                    selected_runtime = selected(camera_id)
                    selected_runtime.start_recording()
                    self._json(selected_runtime.safe_status())
                    return
                if path == "/v1/recording/stop":
                    selected_runtime = selected(camera_id)
                    selected_runtime.stop_recording()
                    self._json(selected_runtime.safe_status())
                    return
                if path == "/v1/trigger":
                    selected_runtime = selected(camera_id)
                    self._json(selected_runtime.trigger(), 202)
                    return
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self._json({"error": str(error)}, 400)
                return
            self._json({"error": "Not found"}, 404)

        def do_PATCH(self) -> None:  # noqa: N802
            if urlsplit(self.path).path != "/v1/config":
                self._json({"error": "Not found"}, 404)
                return
            try:
                camera_id = parse_qs(urlsplit(self.path).query).get("camera_id", [None])[0]
                changes = self._body()
                if hasattr(runtime, "runtime"):
                    self._json(runtime.runtime(camera_id).update_config(changes) if camera_id else runtime.configure(changes))
                else:
                    self._json(runtime.update_config(changes))
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self._json({"error": str(error)}, 400)

        def do_DELETE(self) -> None:  # noqa: N802
            if urlsplit(self.path).path != "/v1/cameras":
                self._json({"error": "Not found"}, 404)
                return
            camera_id = parse_qs(urlsplit(self.path).query).get("camera_id", [None])[0]
            if not camera_id:
                self._json({"error": "Falta identificar la cámara"}, 422)
                return
            runtime.remove(camera_id)
            self._headers(204)
            self.end_headers()

        def log_message(self, *_args: object) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)
