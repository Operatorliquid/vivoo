import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from storage.media_repository import MediaRepository


def test_s3_repository_downloads_and_publishes_private_media(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple] = []

    class FakeS3:
        def download_file(self, bucket, key, destination):
            calls.append(("download", bucket, key))
            Path(destination).parent.mkdir(parents=True, exist_ok=True)
            Path(destination).write_bytes(b"source")

        def upload_file(self, source, bucket, key, ExtraArgs):
            calls.append(("upload", bucket, key, ExtraArgs, Path(source).read_bytes()))

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda service, region_name: FakeS3()))
    repository = MediaRepository(tmp_path, "private-media", "sa-east-1")

    source = repository.materialize("sessions/one/highlight_source/source.mp4")
    output = repository.working_path("highlights/one.mp4")
    output.write_bytes(b"highlight")
    repository.publish("highlights/one.mp4", output)
    repository.release(source, output)

    assert calls[0] == ("download", "private-media", "sessions/one/highlight_source/source.mp4")
    assert calls[1][0:3] == ("upload", "private-media", "highlights/one.mp4")
    assert calls[1][3] == {"ContentType": "video/mp4"}
    assert not source.exists()
    assert not output.exists()


def test_repository_rejects_path_traversal(tmp_path: Path) -> None:
    repository = MediaRepository(tmp_path)
    with pytest.raises(ValueError):
        repository.materialize("../secret")
