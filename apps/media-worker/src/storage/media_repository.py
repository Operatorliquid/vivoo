from __future__ import annotations

from pathlib import Path


class MediaRepository:
    def __init__(self, local_root: Path, s3_bucket: str = "", aws_region: str = "sa-east-1") -> None:
        self.local_root = local_root
        self.s3_bucket = s3_bucket.strip()
        self.aws_region = aws_region

    @staticmethod
    def _safe_key(storage_key: str) -> Path:
        path = Path(storage_key)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Media storage key inválida")
        return path

    def materialize(self, storage_key: str) -> Path:
        relative = self._safe_key(storage_key)
        path = self.local_root / relative
        if not self.s3_bucket:
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        import boto3

        boto3.client("s3", region_name=self.aws_region).download_file(
            self.s3_bucket,
            relative.as_posix(),
            str(path),
        )
        return path

    def working_path(self, storage_key: str) -> Path:
        path = self.local_root / self._safe_key(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def publish(self, storage_key: str, local_path: Path) -> None:
        relative = self._safe_key(storage_key)
        if not self.s3_bucket:
            return
        import boto3

        boto3.client("s3", region_name=self.aws_region).upload_file(
            str(local_path),
            self.s3_bucket,
            relative.as_posix(),
            ExtraArgs={"ContentType": "video/mp4"},
        )

    def release(self, *paths: Path) -> None:
        if not self.s3_bucket:
            return
        for path in paths:
            path.unlink(missing_ok=True)
