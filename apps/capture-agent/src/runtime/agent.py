from __future__ import annotations

import subprocess
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from camera.recorder import LocalRecorder
from camera.rtsp import RtspProbe
from client.api_client import AgentApiClient, AgentApiError
from config import AgentConfig, normalize_roi, save_config
from inference.events import NormalizedCaptureEvent, gesture_event, manual_event
from inference.monitor import GestureMonitor
from inference.yolo_pose import YoloPoseDetector
from local.outbox import EventOutbox
from local.state import StateStore


class LocalAgentRuntime:
    def __init__(self, config_path: Path, config: AgentConfig) -> None:
        self.config_path = config_path
        self.config = config
        self.state = StateStore(config.resolved_storage_dir / "agent-state.json")
        self.outbox = EventOutbox(config.resolved_storage_dir / "agent-events.sqlite3")
        self.probe = RtspProbe()
        self.recorder = LocalRecorder(config.resolved_storage_dir)
        self.api = AgentApiClient(config.cloud_api_url, config.agent_token) if config.agent_token else None
        self.gesture_monitor = self._build_gesture_monitor()
        self._stop = threading.Event()
        self._consecutive_probe_failures = 0
        self._recording_lock = threading.RLock()
        self._event_lock = threading.Lock()
        self._outbox_flush_lock = threading.Lock()
        self._media_flush_lock = threading.Lock()

    def _build_gesture_monitor(self) -> GestureMonitor:
        roi = normalize_roi(self.config.pose_roi)
        return GestureMonitor(
            detector=YoloPoseDetector(
                model_name=self.config.pose_model,
                device=self.config.pose_device,
                image_size=self.config.pose_image_size,
                person_confidence=self.config.pose_person_confidence,
                keypoint_confidence=self.config.pose_keypoint_confidence,
                rotation_degrees=self.config.pose_rotation_degrees,
                roi=tuple(roi),
                min_person_height_ratio=self.config.pose_min_person_height_ratio,
            ),
            on_gesture=self._handle_gesture,
            on_status=self._gesture_status,
            on_observation=self._gesture_observation,
            hold_seconds=self.config.gesture_hold_seconds,
            cooldown_seconds=self.config.gesture_cooldown_seconds,
            release_seconds=self.config.gesture_release_seconds,
            minimum_wrist_lift_ratio=self.config.gesture_min_wrist_lift_ratio,
            minimum_local_motion=self.config.gesture_min_local_motion,
            max_positive_gap_seconds=self.config.gesture_max_gap_seconds,
        )

    def safe_status(self) -> dict[str, object]:
        return {
            "agent": {"camera_id": self.config.camera.camera_id, "version": "0.9.0", "relay_active": bool(self.config.relay_rtsp_url)},
            "camera": {
                "field_id": self.config.camera.field_id,
                "field_name": self.config.camera.field_name,
                "host": self.config.camera.host,
                "rtsp_port": self.config.camera.rtsp_port,
                "stream_path": self.config.camera.stream_path,
            },
            "state": self.state.snapshot(),
        }

    def sync_cloud_config(self) -> None:
        if not self.api or not self.config.camera.camera_id:
            return
        try:
            payload = self.api.get_camera_config(self.config.camera.camera_id)
        except AgentApiError as error:
            self.state.update(last_error=str(error))
            return
        previous_session_id = self.state.snapshot().get("active_session_id")
        next_session_id = str(payload["active_session_id"]) if payload.get("active_session_id") else None
        if previous_session_id and previous_session_id != next_session_id and self.recorder.running:
            self.stop_recording()
        camera = self.config.camera
        config_changed = False
        for key in ("camera_id", "field_id", "field_name", "host", "rtsp_port", "username", "password", "stream_path", "detection_mode", "recording_enabled"):
            if key in payload and getattr(camera, key) != payload[key]:
                setattr(camera, key, payload[key])
                config_changed = True
        self.state.update(active_session_id=next_session_id)
        if config_changed:
            save_config(self.config_path, self.config)
        self.sync_recording()

    def check_camera(self) -> dict[str, object]:
        if not self.config.camera.host:
            self.state.mark_probe("offline", "Configurá la cámara local para comenzar")
            return self.safe_status()
        snapshot = self.state.snapshot()
        last_frame_at = snapshot.get("gesture_last_frame_at")
        fresh_detector_frame = False
        if last_frame_at:
            try:
                fresh_detector_frame = datetime.now(timezone.utc) - datetime.fromisoformat(str(last_frame_at)) < timedelta(seconds=8)
            except ValueError:
                fresh_detector_frame = False
        fresh_recording_segment = any(
            datetime.now(timezone.utc).timestamp() - path.stat().st_mtime < 15
            for path in self.recorder.segment_files()[-2:]
        )
        # Tapo cameras commonly allow only two RTSP readers. Recording and pose
        # detection already prove that frames are flowing, so opening a third
        # ffmpeg probe would report a false disconnect.
        if fresh_detector_frame or fresh_recording_segment:
            result = None
            self._consecutive_probe_failures = 0
            effective_status = "online"
            detail = "Imagen recibida por vivoo"
        else:
            result = self.probe.check(self.config.media_rtsp_url)
        if result is None:
            pass
        elif result.status == "online":
            self._consecutive_probe_failures = 0
            effective_status = "online"
            detail = "Señal estable a través del relay local" if self.config.relay_rtsp_url else result.detail
        else:
            self._consecutive_probe_failures += 1
            previous_status = self.state.snapshot().get("camera_status")
            if previous_status in {"online", "degraded"} and self._consecutive_probe_failures < 3:
                effective_status = "degraded"
                detail = f"Reconectando señal local ({self._consecutive_probe_failures}/3)"
            else:
                effective_status = result.status
                detail = result.detail
        self.state.mark_probe(effective_status, detail)
        self._heartbeat(effective_status)
        self.sync_recording()
        return self.safe_status()

    def _heartbeat(self, status: str) -> None:
        if self.api is None:
            self.state.update(last_error="Falta vincular el agente con la plataforma cloud")
            return
        try:
            snapshot = self.state.snapshot()
            recording_session_id = snapshot.get("recording_session_id") if self.recorder.running else None
            self.api.heartbeat(
                self.config.camera.camera_id,
                status,
                datetime.now(timezone.utc),
                "0.9.0",
                UUID(str(recording_session_id)) if recording_session_id else None,
                str(snapshot.get("gesture_detector_status") or "idle"),
                float(snapshot.get("gesture_inference_fps") or 0.0),
                str(snapshot["gesture_last_frame_at"]) if snapshot.get("gesture_last_frame_at") else None,
            )
            self.state.update(last_heartbeat_at=datetime.now(timezone.utc).isoformat(), last_error=None)
        except AgentApiError as error:
            self.state.update(last_error=str(error))

    def sync_recording(self) -> None:
        with self._recording_lock:
            snapshot = self.state.snapshot()
            active_session_id = snapshot.get("active_session_id")
            current_session_id = snapshot.get("recording_session_id")
            if not self.recorder.running and current_session_id and not active_session_id:
                self.state.update(recording=False, recording_session_id=None)
                current_session_id = None
            if self.recorder.running and current_session_id != active_session_id:
                self.stop_recording()
            if active_session_id and self.recorder.running and not getattr(self.recorder, "healthy", True):
                try:
                    self.recorder.restart(self.config.media_rtsp_url)
                    self.state.update(recording=True, last_error=None)
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    self.state.update(recording=False, last_error=f"Reconectando grabación: {error}")
            elif active_session_id and not self.recorder.running and self.config.camera.host:
                self.start_recording()
            elif not active_session_id and self.recorder.running:
                self.stop_recording()

    def start_recording(self) -> None:
        with self._recording_lock:
            if self.recorder.running:
                self.state.update(recording=True)
                return
            try:
                session_id = self.state.snapshot().get("active_session_id")
                if not session_id:
                    raise ValueError("No hay un partido activo para grabar")
                self.recorder.start(
                    self.config.media_rtsp_url,
                    str(session_id),
                    preserve_full_recording=True,
                    rotation_degrees=self.config.pose_rotation_degrees,
                )
                self.state.update(recording_session_id=session_id)
                self.state.update(recording=True, last_error=None)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                self.state.update(recording=False, last_error=f"No se pudo iniciar la grabación: {error}")

    def stop_recording(self) -> None:
        upload_queued = False
        with self._recording_lock:
            recording_session_id = self.state.snapshot().get("recording_session_id")
            try:
                output_path = self.recorder.stop()
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                self.state.update(recording=False, recording_session_id=None, last_error=f"No se pudo finalizar la grabación: {error}")
                return
            self.state.update(recording=False, recording_session_id=None)
            if output_path and output_path.exists():
                self._queue_recording_upload(output_path, recording_session_id)
                upload_queued = True
        if upload_queued:
            threading.Thread(
                target=self.flush_media_outbox,
                name="recording-upload",
                daemon=True,
            ).start()

    def _queue_recording_upload(self, recording_path: Path, session_id: object) -> None:
        if not session_id:
            return
        self.outbox.enqueue_media(
            upload_id=f"recording:{session_id}",
            session_id=str(session_id),
            media_type="recording",
            content_type="video/mp4",
            local_source_path=recording_path,
        )
        self.state.update(queued_uploads=self.outbox.pending_media_count())

    def flush_media_outbox(self) -> bool:
        if not self._media_flush_lock.acquire(blocking=False):
            return False
        try:
            return self._flush_media_outbox()
        finally:
            self._media_flush_lock.release()

    def _flush_media_outbox(self) -> bool:
        if not self.api:
            self.state.update(queued_uploads=self.outbox.pending_media_count())
            return False
        uploaded_any = False
        for item in self.outbox.pending_media():
            upload_id = str(item["upload_id"])
            source_path = Path(str(item["local_source_path"]))
            try:
                if not source_path.is_file():
                    raise ValueError("El archivo local pendiente ya no existe")
                upload = self.api.upload_resumable(
                    UUID(str(item["session_id"])), str(item["media_type"]), str(item["content_type"]), source_path,
                )
                storage_key = str(upload["storage_key"])
                self.outbox.set_media_storage_key(upload_id, storage_key)
                self.outbox.mark_media_sent(upload_id)
                source_path.unlink(missing_ok=True)
                uploaded_any = True
                self.state.update(
                    last_uploaded_recording=storage_key,
                    queued_uploads=self.outbox.pending_media_count(),
                    last_error=None,
                )
            except (AgentApiError, OSError, ValueError) as error:
                self.outbox.mark_media_attempt(upload_id, str(error))
                self.state.update(
                    queued_uploads=self.outbox.pending_media_count(),
                    last_error=f"Subida pendiente: {error}",
                )
                return uploaded_any
        return uploaded_any

    def _queue_event_with_media(self, event: NormalizedCaptureEvent) -> None:
        with self._recording_lock:
            if not self.state.snapshot().get("active_session_id"):
                raise ValueError("No hay un partido activo")
            self.sync_recording()
            if not self.recorder.running:
                raise ValueError("La cámara todavía no está grabando")
            source_path = self.config.resolved_storage_dir / "highlight-sources" / f"{event.source_id}.mp4"
            self.recorder.export_recent_clip(source_path, seconds=30)
            session_id = str(self.state.snapshot()["active_session_id"])
            self.outbox.enqueue(event, session_id=session_id, local_source_path=source_path)
            self.state.update(queued_events=self.outbox.pending_count())

    def trigger(self) -> dict[str, object]:
        occurred_at = datetime.now(timezone.utc)
        event = manual_event(occurred_at)
        event = NormalizedCaptureEvent(
            source_id=event.source_id,
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            buffer_start_at=occurred_at - timedelta(seconds=30),
            buffer_end_at=occurred_at,
        )
        self._queue_event_with_media(event)
        result = self.flush_outbox()
        if result:
            return result
        self.state.update(queued_events=self.outbox.pending_count())
        return {"accepted": False, "queued": True, "source_id": event.source_id}

    def _gesture_status(self, status: str, detail: str) -> None:
        self.state.update(gesture_detector_status=status, gesture_detector_detail=detail)

    def _gesture_observation(
        self,
        raised: bool,
        confidence: float,
        people: int,
        tracked_people: int,
        fps: float,
        inference_ms: float,
        observed_at: datetime,
    ) -> None:
        self.state.update(
            gesture_last_frame_at=observed_at.isoformat(),
            gesture_people_count=people,
            gesture_tracked_people=tracked_people,
            gesture_arms_raised=raised,
            gesture_pose_confidence=confidence,
            gesture_inference_fps=round(fps, 2),
            gesture_inference_ms=round(inference_ms, 1),
        )

    def _handle_gesture(self, confidence: float, occurred_at: datetime) -> None:
        if self.config.camera.detection_mode != "arms_up":
            return
        if not self.state.snapshot().get("active_session_id"):
            return
        event = gesture_event(
            occurred_at,
            confidence,
            threshold=self.config.pose_keypoint_confidence,
        )
        if event is None:
            return
        event = NormalizedCaptureEvent(
            source_id=event.source_id,
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            confidence=event.confidence,
            buffer_start_at=occurred_at - timedelta(seconds=30),
            buffer_end_at=occurred_at,
        )
        self.state.update(
            last_gesture_at=occurred_at.isoformat(),
            last_gesture_confidence=confidence,
        )
        threading.Thread(
            target=self._process_gesture_event,
            args=(event,),
            name=f"highlight-{event.source_id[:8]}",
            daemon=True,
        ).start()

    def _process_gesture_event(
        self,
        event: NormalizedCaptureEvent,
    ) -> None:
        # Clip extraction is serialized because ffmpeg reads the same rolling
        # buffer, but valid gestures are queued as threads instead of being
        # silently discarded while the previous clip is still being assembled.
        with self._event_lock:
            try:
                self._queue_event_with_media(event)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                self.state.update(last_error=f"No se pudo guardar el gesto: {error}")
                return
        self.state.update(queued_events=self.outbox.pending_count())
        self.flush_outbox()

    def _sync_gesture_monitor(self) -> None:
        snapshot = self.state.snapshot()
        session_active = bool(snapshot.get("active_session_id"))
        should_run = (
            session_active
            and self.config.camera.detection_mode == "arms_up"
            and bool(self.config.camera.host)
        )
        if should_run:
            self.gesture_monitor.start(self.config.media_rtsp_url)
            return
        if self.gesture_monitor.running:
            self.gesture_monitor.stop()
        if self.config.camera.detection_mode != "arms_up":
            self._gesture_status("disabled", "Detección configurada como manual")
        elif not session_active:
            self._gesture_status("idle", "Iniciá la grabación para detectar gestos")
        elif not self.config.camera.host:
            self._gesture_status("offline", "Esperando señal de la cámara")

    def flush_outbox(self) -> dict[str, object] | None:
        if not self._outbox_flush_lock.acquire(blocking=False):
            return None
        try:
            return self._flush_outbox()
        finally:
            self._outbox_flush_lock.release()

    def _flush_outbox(self) -> dict[str, object] | None:
        if not self.api:
            return None
        for item in self.outbox.pending():
            try:
                event_payload = item["payload"]
                session_id = event_payload.get("session_id") or self.state.snapshot().get("active_session_id")
                if not session_id:
                    raise ValueError("El evento pendiente no tiene una sesión asociada")
                local_source_path = Path(str(event_payload["local_source_path"])) if event_payload.get("local_source_path") else None
                source_storage_key = str(event_payload["source_storage_key"]) if event_payload.get("source_storage_key") else None
                if not source_storage_key:
                    if local_source_path is None or not local_source_path.is_file():
                        raise ValueError("Falta el clip local del momento")
                    upload = self.api.upload_resumable(UUID(str(session_id)), "highlight_source", "video/mp4", local_source_path)
                    source_storage_key = str(upload["storage_key"])
                    self.outbox.set_source_storage_key(str(item["source_id"]), source_storage_key)
                event = NormalizedCaptureEvent(
                    source_id=str(event_payload["source_id"]),
                    event_type=str(event_payload["event_type"]),
                    occurred_at=datetime.fromisoformat(str(event_payload["occurred_at"])),
                    confidence=float(event_payload["confidence"]) if event_payload.get("confidence") is not None else None,
                    buffer_start_at=datetime.fromisoformat(str(event_payload["buffer_start_at"])) if event_payload.get("buffer_start_at") else None,
                    buffer_end_at=datetime.fromisoformat(str(event_payload["buffer_end_at"])) if event_payload.get("buffer_end_at") else None,
                    source_storage_key=source_storage_key,
                )
                response = self.api.submit_event(UUID(str(session_id)), event)
                self.outbox.mark_sent(str(item["source_id"]))
                if local_source_path:
                    local_source_path.unlink(missing_ok=True)
                self.state.update(queued_events=self.outbox.pending_count(), last_error=None)
                return {"accepted": True, "event": response}
            except (AgentApiError, ValueError) as error:
                self.state.update(queued_events=self.outbox.pending_count(), last_error=str(error))
                return None
        return None

    def update_config(self, changes: dict[str, object]) -> dict[str, object]:
        connection_changed = bool({"cloud_api_url", "agent_token"}.intersection(changes))
        camera_changes = changes.pop("camera", None)
        connection_changed = connection_changed or bool(
            isinstance(camera_changes, dict) and "camera_id" in camera_changes
        )
        detector_keys = {
            "pose_model", "pose_device", "pose_image_size", "pose_person_confidence",
            "pose_keypoint_confidence", "pose_rotation_degrees", "pose_roi",
            "pose_min_person_height_ratio", "gesture_hold_seconds",
            "gesture_cooldown_seconds", "gesture_release_seconds",
            "gesture_min_wrist_lift_ratio", "gesture_max_gap_seconds",
            "gesture_min_local_motion",
        }
        detector_changed = bool(detector_keys.intersection(changes))
        if "pose_roi" in changes:
            changes["pose_roi"] = normalize_roi(changes["pose_roi"])
        for key, value in changes.items():
            if hasattr(self.config, key) and value is not None:
                setattr(self.config, key, value)
        if isinstance(camera_changes, dict):
            for key, value in camera_changes.items():
                if hasattr(self.config.camera, key) and value is not None:
                    setattr(self.config.camera, key, value)
        save_config(self.config_path, self.config)
        self.api = AgentApiClient(self.config.cloud_api_url, self.config.agent_token) if self.config.agent_token else None
        if connection_changed and self.api and self.config.camera.camera_id:
            self.sync_cloud_config()
            self.check_camera()
        if detector_changed:
            self.gesture_monitor.stop()
            self.gesture_monitor = self._build_gesture_monitor()
            self._sync_gesture_monitor()
        return self.safe_status()

    def run_background(self) -> None:
        self.sync_cloud_config()
        self.check_camera()
        self.sync_recording()
        self._sync_gesture_monitor()
        while not self._stop.wait(max(10, self.config.heartbeat_seconds)):
            self.sync_cloud_config()
            self.check_camera()
            self.sync_recording()
            self._sync_gesture_monitor()
            self.flush_outbox()
            self.flush_media_outbox()

    def stop(self) -> None:
        self._stop.set()
        self.gesture_monitor.stop()
        self.stop_recording()
