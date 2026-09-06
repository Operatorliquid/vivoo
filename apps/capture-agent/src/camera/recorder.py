from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import time
from typing import Callable


class LocalRecorder:
    """Session recorder backed by crash-tolerant five-second MPEG-TS segments."""

    SEGMENT_SECONDS = 5
    RING_SEGMENTS = 12

    def __init__(
        self,
        storage_dir: Path,
        popen: Callable = subprocess.Popen,
        runner: Callable = subprocess.run,
    ) -> None:
        self.storage_dir = storage_dir
        self.popen = popen
        self.runner = runner
        self.process: subprocess.Popen | None = None
        self.session_id: str | None = None
        self.session_dir: Path | None = None
        self.preserve_full_recording = False
        self.rotation_degrees = 0
        self.command: list[str] = []
        self.started_at = 0.0

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def healthy(self) -> bool:
        """A live process must also keep producing segments after warm-up."""
        if not self.running:
            return False
        if time.monotonic() - self.started_at <= self.SEGMENT_SECONDS * 3:
            return True
        segments = self.segment_files()
        return bool(segments and time.time() - segments[-1].stat().st_mtime <= self.SEGMENT_SECONDS * 3)

    def start(self, rtsp_url: str, session_id: str, preserve_full_recording: bool, rotation_degrees: int = 0) -> None:
        if self.running:
            return
        if not session_id.strip():
            raise ValueError("session_id is required to record")
        self.session_id = session_id
        self.preserve_full_recording = preserve_full_recording
        if rotation_degrees not in {0, 90, 180, 270}:
            raise ValueError("rotation_degrees must be 0, 90, 180 or 270")
        self.rotation_degrees = rotation_degrees
        self.session_dir = self.storage_dir / "recordings" / f"session-{session_id}" / "segments"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        existing = self.segment_files()
        start_number = max((int(path.stem.split("-")[-1]) for path in existing), default=-1) + 1
        output = self.session_dir / "segment-%06d.ts"
        segment_args = [
            "-f", "segment",
            "-segment_time", str(self.SEGMENT_SECONDS),
            "-segment_start_number", str(start_number),
            "-reset_timestamps", "1",
            "-segment_format", "mpegts",
        ]
        if not preserve_full_recording:
            segment_args.extend(["-segment_wrap", str(self.RING_SEGMENTS)])
        self.command = [
            "ffmpeg", "-hide_banner", "-loglevel", "warning", "-y",
            "-rtsp_transport", "tcp", "-i", rtsp_url,
            "-map", "0:v:0", "-map", "0:a?", "-c:v", "copy", "-c:a", "aac",
            *segment_args,
            str(output),
        ]
        self.process = self.popen(
            self.command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.started_at = time.monotonic()

    def _terminate_process(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None

    def restart(self, rtsp_url: str) -> None:
        """Reconnect FFmpeg without closing or assembling the active match."""
        session_id = self.session_id
        preserve = self.preserve_full_recording
        rotation = self.rotation_degrees
        if not session_id:
            raise ValueError("No hay una grabación activa para reconectar")
        self._terminate_process()
        self.start(rtsp_url, session_id, preserve, rotation)

    def segment_files(self) -> list[Path]:
        if self.session_dir is None or not self.session_dir.exists():
            return []
        return sorted(
            (path for path in self.session_dir.glob("segment-*.ts") if path.is_file() and path.stat().st_size > 0),
            key=lambda path: (path.stat().st_mtime_ns, path.name),
        )

    @staticmethod
    def _concat_entry(path: Path) -> str:
        return "file '" + str(path.resolve()).replace("'", "'\\''") + "'\n"

    def _assemble(self, segments: list[Path], output_path: Path) -> Path:
        if not segments:
            raise ValueError("No hay segmentos para finalizar")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        concat_path = output_path.with_suffix(".concat.txt")
        concat_path.write_text("".join(self._concat_entry(path) for path in segments), encoding="utf-8")
        try:
            self.runner(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "concat", "-safe", "0",
                    *(["-display_rotation:v:0", str(self.rotation_degrees)] if self.rotation_degrees else []),
                    "-i", str(concat_path),
                    "-map", "0:v:0", "-map", "0:a?", "-c", "copy",
                    "-movflags", "+faststart", str(output_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        finally:
            concat_path.unlink(missing_ok=True)
        return output_path

    def export_recent_clip(self, output_path: Path, seconds: int = 30) -> Path:
        """Freeze the most recent bounded window without interrupting capture."""
        if seconds <= 0:
            raise ValueError("seconds must be positive")
        # The segment that contains the gesture is still open when the event
        # arrives. Let FFmpeg roll once, then exclude only the new active file.
        # This keeps the gesture itself inside the saved clip.
        if self.running:
            time.sleep(self.SEGMENT_SECONDS + 0.75)
        segments = self.segment_files()
        if self.running and len(segments) > 1:
            segments = segments[:-1]
        segments = segments[-max(2, (seconds // self.SEGMENT_SECONDS) + 3):]
        if not segments:
            raise ValueError("Todavía no hay video suficiente para guardar el momento")
        staging = output_path.with_suffix(".source.mp4")
        staging.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._assemble(segments, staging)
            probe = self.runner(
                [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(staging),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            duration = float(probe.stdout.strip())
            start = max(0.0, duration - seconds)
            self.runner(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{start:.3f}",
                    *(["-display_rotation:v:0", str(self.rotation_degrees)] if self.rotation_degrees else []),
                    "-i", str(staging), "-t", str(seconds),
                    "-map", "0:v:0", "-map", "0:a?", "-c", "copy",
                    "-movflags", "+faststart", str(output_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        finally:
            staging.unlink(missing_ok=True)
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("FFmpeg no generó el clip del momento")
        return output_path

    def stop(self) -> Path | None:
        if self.process is None:
            return None
        self._terminate_process()
        output_path: Path | None = None
        session_root = self.session_dir.parent if self.session_dir else None
        if self.preserve_full_recording and self.session_id:
            segments = self.segment_files()
            if segments:
                output_path = self.storage_dir / "recordings" / f"session-{self.session_id}.mp4"
                self._assemble(segments, output_path)
        if session_root and (not self.preserve_full_recording or (output_path and output_path.exists())):
            shutil.rmtree(session_root, ignore_errors=True)
        self.session_id = None
        self.session_dir = None
        self.preserve_full_recording = False
        self.rotation_degrees = 0
        self.started_at = 0.0
        return output_path
