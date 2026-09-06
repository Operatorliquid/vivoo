import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import settings
from domain.schemas import PresignUploadRequest, PresignUploadResponse
from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse, Response


class MediaStorage:
    part_size = 8 * 1024 * 1024

    @staticmethod
    def _safe_path(storage_path: str) -> Path:
        safe_path = Path(storage_path)
        if safe_path.is_absolute() or ".." in safe_path.parts:
            raise ValueError("Invalid local storage path")
        return safe_path

    def save_local_upload(self, storage_path: str, content: bytes) -> None:
        safe_path = self._safe_path(storage_path)
        target = Path(settings.local_media_root) / safe_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    async def save_local_upload_stream(self, storage_path: str, chunks) -> None:
        safe_path = self._safe_path(storage_path)
        target = Path(settings.local_media_root) / safe_path
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(f"{target.suffix}.uploading")
        try:
            with temporary.open("wb") as destination:
                async for chunk in chunks:
                    destination.write(chunk)
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def presign_upload(self, request: PresignUploadRequest) -> PresignUploadResponse:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.presign_ttl_seconds)
        storage_key = f"sessions/{request.session_id}/{request.media_type}/{request.checksum}"
        if settings.s3_media_bucket:
            import boto3

            client = boto3.client("s3", region_name=settings.aws_region)
            upload_url = client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": settings.s3_media_bucket,
                    "Key": storage_key,
                    "ContentType": request.content_type,
                    "Metadata": {"sha256": request.checksum},
                },
                ExpiresIn=settings.presign_ttl_seconds,
            )
        else:
            upload_url = f"{settings.public_media_base_url.rstrip('/')}/agent/dev/uploads/{storage_key}"
        return PresignUploadResponse(upload_url=upload_url, storage_key=storage_key, expires_at=expires_at)

    def _upload_directory(self, upload_id: str) -> Path:
        if not upload_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in upload_id):
            raise ValueError("Invalid upload id")
        return Path(settings.local_media_root) / ".uploads" / upload_id

    def _completion_path(self, upload_id: str) -> Path:
        return Path(settings.local_media_root) / ".uploads" / "completed" / f"{upload_id}.json"

    def start_resumable(self, request: PresignUploadRequest, camera_id: str) -> dict[str, object]:
        storage_key = f"sessions/{request.session_id}/{request.media_type}/{request.checksum}"
        upload_id = hashlib.sha256(f"{camera_id}:{storage_key}".encode("utf-8")).hexdigest()[:40]
        directory = self._upload_directory(upload_id)
        manifest_path = directory / "manifest.json"
        expected = {
            "upload_id": upload_id,
            "camera_id": camera_id,
            "session_id": str(request.session_id),
            "media_type": request.media_type,
            "content_type": request.content_type,
            "size_bytes": request.size_bytes,
            "checksum": request.checksum,
            "storage_key": storage_key,
            "part_size": self.part_size,
        }
        completion_path = self._completion_path(upload_id)
        if completion_path.is_file():
            try:
                completed = json.loads(completion_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise HTTPException(status_code=409, detail="La subida completada no se puede recuperar") from error
            if any(completed.get(key) != expected[key] for key in expected):
                raise HTTPException(status_code=409, detail="La subida completada no coincide")
            total_parts = (request.size_bytes + self.part_size - 1) // self.part_size
            return expected | {"received_parts": list(range(1, total_parts + 1))}
        directory.mkdir(parents=True, exist_ok=True)
        if manifest_path.exists():
            try:
                current = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise HTTPException(status_code=409, detail="La subida no se puede recuperar") from error
            if any(current.get(key) != expected[key] for key in expected):
                raise HTTPException(status_code=409, detail="La reserva de subida no coincide")
        else:
            temporary = manifest_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(expected), encoding="utf-8")
            temporary.replace(manifest_path)
        received = sorted(int(path.stem) for path in directory.glob("*.part") if path.stem.isdigit())
        return expected | {"received_parts": received}

    def resumable_manifest(self, upload_id: str) -> dict[str, object]:
        manifest_path = self._upload_directory(upload_id) / "manifest.json"
        if not manifest_path.is_file():
            completion_path = self._completion_path(upload_id)
            if completion_path.is_file():
                manifest_path = completion_path
        if not manifest_path.is_file():
            raise HTTPException(status_code=404, detail="Subida no encontrada")
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=409, detail="La subida no se puede recuperar") from error

    async def save_resumable_part(self, upload_id: str, part_number: int, chunks) -> None:
        if self._completion_path(upload_id).is_file():
            raise HTTPException(status_code=409, detail="La subida ya fue completada")
        manifest = self.resumable_manifest(upload_id)
        if part_number < 1:
            raise HTTPException(status_code=422, detail="Número de parte inválido")
        expected_parts = (int(manifest["size_bytes"]) + self.part_size - 1) // self.part_size
        if part_number > expected_parts:
            raise HTTPException(status_code=422, detail="La parte excede el tamaño reservado")
        directory = self._upload_directory(upload_id)
        target = directory / f"{part_number}.part"
        temporary = target.with_suffix(".uploading")
        written = 0
        try:
            with temporary.open("wb") as destination:
                async for chunk in chunks:
                    written += len(chunk)
                    if written > self.part_size:
                        raise HTTPException(status_code=413, detail="La parte es demasiado grande")
                    destination.write(chunk)
            final_expected = int(manifest["size_bytes"]) - self.part_size * (expected_parts - 1)
            expected_size = final_expected if part_number == expected_parts else self.part_size
            if written != expected_size:
                raise HTTPException(status_code=409, detail="El tamaño de la parte no coincide")
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def complete_resumable(self, upload_id: str, storage_key: str, size_bytes: int, checksum: str) -> None:
        completion_path = self._completion_path(upload_id)
        if completion_path.is_file():
            try:
                completed = json.loads(completion_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise HTTPException(status_code=409, detail="La subida completada no se puede recuperar") from error
            if (
                completed.get("storage_key") != storage_key
                or completed.get("size_bytes") != size_bytes
                or completed.get("checksum") != checksum
            ):
                raise HTTPException(status_code=409, detail="La subida completada no coincide")
            self.verify_upload(storage_key, size_bytes, checksum)
            return
        manifest = self.resumable_manifest(upload_id)
        if manifest["storage_key"] != storage_key or manifest["size_bytes"] != size_bytes or manifest["checksum"] != checksum:
            raise HTTPException(status_code=409, detail="La subida no coincide con la reserva")
        directory = self._upload_directory(upload_id)
        expected_parts = (size_bytes + self.part_size - 1) // self.part_size
        parts = [directory / f"{number}.part" for number in range(1, expected_parts + 1)]
        if not all(path.is_file() for path in parts):
            raise HTTPException(status_code=409, detail="Todavía faltan partes del video")
        target = Path(settings.local_media_root) / self._safe_path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(f"{target.suffix}.assembling")
        digest = hashlib.sha256()
        total = 0
        try:
            with temporary.open("wb") as destination:
                for part in parts:
                    with part.open("rb") as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            digest.update(chunk)
                            destination.write(chunk)
                            total += len(chunk)
            if total != size_bytes or digest.hexdigest() != checksum:
                raise HTTPException(status_code=409, detail="La verificación final del video falló")
            if settings.s3_media_bucket:
                import boto3
                boto3.client("s3", region_name=settings.aws_region).upload_file(
                    str(temporary), settings.s3_media_bucket, self._safe_path(storage_key).as_posix(),
                    ExtraArgs={"ContentType": str(manifest["content_type"]), "Metadata": {"sha256": checksum}},
                )
                temporary.unlink(missing_ok=True)
            else:
                temporary.replace(target)
            completion_path.parent.mkdir(parents=True, exist_ok=True)
            completion_temporary = completion_path.with_suffix(".tmp")
            completion_temporary.write_text(json.dumps(manifest), encoding="utf-8")
            completion_temporary.replace(completion_path)
            shutil.rmtree(directory)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def verify_upload(self, storage_path: str, expected_size: int, expected_checksum: str) -> None:
        safe_path = self._safe_path(storage_path)
        if settings.s3_media_bucket:
            import boto3

            metadata = boto3.client("s3", region_name=settings.aws_region).head_object(
                Bucket=settings.s3_media_bucket,
                Key=safe_path.as_posix(),
            )
            if int(metadata.get("ContentLength", -1)) != expected_size:
                raise HTTPException(status_code=409, detail="El tamaño del video subido no coincide")
            if metadata.get("Metadata", {}).get("sha256") != expected_checksum:
                raise HTTPException(status_code=409, detail="El checksum del video subido no coincide")
            return

        media_path = Path(settings.local_media_root) / safe_path
        if not media_path.is_file() or media_path.stat().st_size != expected_size:
            raise HTTPException(status_code=409, detail="El tamaño del video subido no coincide")
        digest = hashlib.sha256()
        with media_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected_checksum:
            raise HTTPException(status_code=409, detail="El checksum del video subido no coincide")

    def delete(self, storage_path: str) -> None:
        safe_path = self._safe_path(storage_path)
        if settings.s3_media_bucket:
            import boto3
            from botocore.exceptions import ClientError

            client = boto3.client("s3", region_name=settings.aws_region)
            key = safe_path.as_posix()
            try:
                metadata = client.head_object(Bucket=settings.s3_media_bucket, Key=key)
            except ClientError as error:
                if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                    return
                raise
            version_id = metadata.get("VersionId")
            try:
                client.delete_object(
                    Bucket=settings.s3_media_bucket,
                    Key=key,
                    **({"VersionId": version_id} if version_id else {}),
                )
            except ClientError as error:
                if not version_id or error.response.get("Error", {}).get("Code") != "AccessDenied":
                    raise
                # Compatibility for deployments whose role has not yet received
                # DeleteObjectVersion: remove public availability immediately.
                client.delete_object(Bucket=settings.s3_media_bucket, Key=key)
            return
        (Path(settings.local_media_root) / safe_path).unlink(missing_ok=True)

    def exists(self, storage_path: str) -> bool:
        """Return whether a completed object exists without exposing its URL."""
        safe_path = self._safe_path(storage_path)
        if settings.s3_media_bucket:
            import boto3
            from botocore.exceptions import ClientError

            try:
                boto3.client("s3", region_name=settings.aws_region).head_object(
                    Bucket=settings.s3_media_bucket,
                    Key=safe_path.as_posix(),
                )
                return True
            except ClientError:
                return False
        return (Path(settings.local_media_root) / safe_path).is_file()

    def completed_upload_exists(self, storage_path: str) -> bool:
        """Verify a completed upload using the checksum encoded in its key."""
        safe_path = self._safe_path(storage_path)
        checksum = safe_path.name
        if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum.lower()):
            return False
        if settings.s3_media_bucket:
            import boto3
            from botocore.exceptions import ClientError

            try:
                metadata = boto3.client("s3", region_name=settings.aws_region).head_object(
                    Bucket=settings.s3_media_bucket,
                    Key=safe_path.as_posix(),
                )
            except ClientError:
                return False
            return int(metadata.get("ContentLength", 0)) > 0 and metadata.get("Metadata", {}).get("sha256") == checksum
        media_path = Path(settings.local_media_root) / safe_path
        if not media_path.is_file():
            return False
        digest = hashlib.sha256()
        try:
            with media_path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            return False
        return digest.hexdigest() == checksum

    def playback_response(self, storage_path: str, filename: str, download: bool = False) -> Response:
        safe_path = self._safe_path(storage_path)
        disposition = "attachment" if download else "inline"
        if settings.s3_media_bucket:
            import boto3

            url = boto3.client("s3", region_name=settings.aws_region).generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.s3_media_bucket,
                    "Key": safe_path.as_posix(),
                    "ResponseContentType": "video/mp4",
                    "ResponseContentDisposition": f'{disposition}; filename="{filename}"',
                },
                ExpiresIn=settings.presign_ttl_seconds,
            )
            return RedirectResponse(url, status_code=307, headers={"Cache-Control": "private, no-store"})

        media_path = Path(settings.local_media_root) / safe_path
        if not media_path.is_file():
            raise HTTPException(status_code=404, detail="Video no disponible")
        return FileResponse(
            media_path,
            media_type="video/mp4",
            filename=filename,
            content_disposition_type=disposition,
            headers={"Cache-Control": "private, no-store"},
        )


media_storage = MediaStorage()
