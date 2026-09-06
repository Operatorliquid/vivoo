import asyncio
import hashlib
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest
import services.media_storage as media_storage_module
from domain.schemas import PresignUploadRequest
from services.media_storage import MediaStorage


async def chunks(value: bytes):
    yield value


def test_delete_removes_local_media(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        media_storage_module,
        "settings",
        SimpleNamespace(local_media_root=str(tmp_path), s3_media_bucket="", aws_region="us-east-1"),
    )
    target = tmp_path / "highlights" / "clip.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"video")

    MediaStorage().delete("highlights/clip.mp4")

    assert not target.exists()


def test_delete_uses_the_configured_s3_bucket(monkeypatch) -> None:
    calls: list[dict[str, str]] = []

    class FakeS3Client:
        def head_object(self, **payload):
            assert payload == {"Bucket": "courtvision-media", "Key": "highlights/clip.mp4"}
            return {"VersionId": "version-01"}

        def delete_object(self, **payload) -> None:
            calls.append(payload)

    fake_boto3 = SimpleNamespace(client=lambda service, region_name: FakeS3Client())
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setattr(
        media_storage_module,
        "settings",
        SimpleNamespace(local_media_root="/unused", s3_media_bucket="courtvision-media", aws_region="sa-east-1"),
    )

    MediaStorage().delete("highlights/clip.mp4")

    assert calls == [{"Bucket": "courtvision-media", "Key": "highlights/clip.mp4", "VersionId": "version-01"}]


def test_delete_rejects_unsafe_storage_keys() -> None:
    with pytest.raises(ValueError):
        MediaStorage().delete("../outside.mp4")


def test_exists_reads_local_storage(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        media_storage_module,
        "settings",
        SimpleNamespace(local_media_root=str(tmp_path), s3_media_bucket="", aws_region="us-east-1"),
    )
    target = tmp_path / "sessions" / "match.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"video")

    assert MediaStorage().exists("sessions/match.mp4") is True
    assert MediaStorage().exists("sessions/missing.mp4") is False


def test_completed_upload_requires_matching_checksum(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        media_storage_module,
        "settings",
        SimpleNamespace(local_media_root=str(tmp_path), s3_media_bucket="", aws_region="us-east-1"),
    )
    content = b"verified-video"
    checksum = hashlib.sha256(content).hexdigest()
    target = tmp_path / "sessions" / checksum
    target.parent.mkdir(parents=True)
    target.write_bytes(content)

    assert MediaStorage().completed_upload_exists(f"sessions/{checksum}") is True
    target.write_bytes(b"corrupted")
    assert MediaStorage().completed_upload_exists(f"sessions/{checksum}") is False


def test_s3_playback_uses_a_short_lived_private_redirect(monkeypatch) -> None:
    calls: list[tuple[str, dict, int]] = []

    class FakeS3Client:
        def generate_presigned_url(self, operation, Params, ExpiresIn):
            calls.append((operation, Params, ExpiresIn))
            return "https://signed.example/private-video"

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda service, region_name: FakeS3Client()))
    monkeypatch.setattr(
        media_storage_module,
        "settings",
        SimpleNamespace(
            local_media_root="/unused",
            s3_media_bucket="courtvision-private",
            aws_region="sa-east-1",
            presign_ttl_seconds=300,
        ),
    )

    response = MediaStorage().playback_response("sessions/one/recording/video.mp4", "partido.mp4")

    assert response.status_code == 307
    assert response.headers["location"] == "https://signed.example/private-video"
    assert response.headers["cache-control"] == "private, no-store"
    assert calls[0][0] == "get_object"
    assert calls[0][1]["Bucket"] == "courtvision-private"
    assert calls[0][2] == 300


def test_resumable_upload_recovers_parts_and_completion_is_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        media_storage_module,
        "settings",
        SimpleNamespace(local_media_root=str(tmp_path), s3_media_bucket="", aws_region="us-east-1"),
    )
    storage = MediaStorage()
    storage.part_size = 4
    content = b"professional-video"
    checksum = hashlib.sha256(content).hexdigest()
    request = PresignUploadRequest(
        session_id=UUID("00000000-0000-0000-0000-000000000001"),
        media_type="recording",
        content_type="video/mp4",
        size_bytes=len(content),
        checksum=checksum,
    )

    reservation = storage.start_resumable(request, "camera-01")
    asyncio.run(storage.save_resumable_part(reservation["upload_id"], 1, chunks(content[:4])))
    resumed = storage.start_resumable(request, "camera-01")
    assert resumed["received_parts"] == [1]

    for number, offset in enumerate(range(4, len(content), 4), start=2):
        asyncio.run(storage.save_resumable_part(reservation["upload_id"], number, chunks(content[offset:offset + 4])))
    storage.complete_resumable(reservation["upload_id"], reservation["storage_key"], len(content), checksum)
    storage.complete_resumable(reservation["upload_id"], reservation["storage_key"], len(content), checksum)

    target = tmp_path / reservation["storage_key"]
    assert target.read_bytes() == content
    assert storage.start_resumable(request, "camera-01")["received_parts"] == [1, 2, 3, 4, 5]
