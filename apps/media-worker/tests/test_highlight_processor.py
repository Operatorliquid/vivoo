from pathlib import Path

import pytest

from clipping.highlight_processor import ClipRequest, build_ffmpeg_command


def test_builds_ffmpeg_command_for_a_30_second_highlight() -> None:
    command = build_ffmpeg_command(ClipRequest(Path("source.mp4"), Path("out.mp4"), 90, 30))
    assert command[:9] == ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "90", "-i", "source.mp4"]
    assert "-t" in command
    assert command[command.index("-t") + 1] == "30"
    assert command[command.index("-c") + 1] == "copy"
    assert command[-1] == "out.mp4"


def test_rejects_invalid_clip_boundaries() -> None:
    with pytest.raises(ValueError):
        build_ffmpeg_command(ClipRequest(Path("source.mp4"), Path("out.mp4"), -1, 30))
    with pytest.raises(ValueError):
        build_ffmpeg_command(ClipRequest(Path("source.mp4"), Path("out.mp4"), 0, 0))


def test_watermarked_highlight_is_baked_with_h264_instead_of_stream_copy(tmp_path: Path) -> None:
    watermark = tmp_path / "vivoo.png"
    watermark.write_bytes(b"png")

    command = build_ffmpeg_command(ClipRequest(
        Path("source.mp4"), Path("out.mp4"), 0, 30, watermark,
    ))

    assert "-filter_complex" in command
    assert "overlay=" in command[command.index("-filter_complex") + 1]
    assert "shortest=1" in command[command.index("-filter_complex") + 1]
    assert command[command.index("-c:v") + 1] == "libx264"
    assert "copy" not in command
