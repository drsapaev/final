"""Private file storage and publication rules for public-site images."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import tempfile
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import log_audit_event
from app.core.config import settings
from app.models.clinic import Doctor
from app.models.public_site_media import PublicSiteMedia
from app.repositories.public_site_read_repository import PublicSiteReadRepository
from app.services.public_site_read_service import PublicSiteReadService

logger = logging.getLogger(__name__)

_STORAGE_KEY_RE = re.compile(r"^[0-9a-f]{64}$")
_BACKUP_NAME_RE = re.compile(
    r"^[0-9]{8}T[0-9]{12}Z-[0-9a-f]{64}-[0-9a-f]{8}\.(?:jpg|png|webp)$"
)
_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


class PublicSiteMediaError(Exception):
    """Expected public media failure that can be returned without path details."""

    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True)
class PublicSiteMediaPayload:
    body: bytes
    mime_type: str


class PublicSiteMediaService:
    """Manage normalized image files and their database publication rows."""

    def __init__(
        self,
        db: Session,
        *,
        media_root: Path | str | None = None,
        backup_root: Path | str | None = None,
        retention_days: int | None = None,
        max_upload_bytes: int | None = None,
        max_pixels: int | None = None,
    ) -> None:
        self.db = db
        self.media_root = (
            Path(media_root)
            if media_root is not None
            else settings.PUBLIC_SITE_MEDIA_ROOT
        )
        self.backup_root = (
            Path(backup_root)
            if backup_root is not None
            else settings.PUBLIC_SITE_MEDIA_BACKUP_ROOT
        )
        self.retention_days = (
            retention_days
            if retention_days is not None
            else settings.PUBLIC_SITE_MEDIA_BACKUP_RETENTION_DAYS
        )
        self.max_upload_bytes = (
            max_upload_bytes
            if max_upload_bytes is not None
            else settings.PUBLIC_SITE_MEDIA_MAX_UPLOAD_BYTES
        )
        self.max_pixels = (
            max_pixels
            if max_pixels is not None
            else settings.PUBLIC_SITE_MEDIA_MAX_PIXELS
        )
        self._validate_roots()

    def _validate_roots(self) -> None:
        if (self.media_root is None) != (self.backup_root is None):
            raise PublicSiteMediaError(503, "public_media_storage_unavailable")
        if self.media_root is None or self.backup_root is None:
            return

        media = os.path.normcase(os.path.abspath(os.fspath(self.media_root)))
        backup = os.path.normcase(os.path.abspath(os.fspath(self.backup_root)))
        try:
            common = os.path.commonpath((media, backup))
        except ValueError as exc:
            raise PublicSiteMediaError(503, "public_media_storage_unavailable") from exc
        if common in (media, backup):
            raise PublicSiteMediaError(503, "public_media_storage_unavailable")

    def _configured_roots(self, *, create: bool = False) -> tuple[Path, Path]:
        if self.media_root is None or self.backup_root is None:
            raise PublicSiteMediaError(503, "public_media_storage_unavailable")
        media_root = self.media_root.expanduser()
        backup_root = self.backup_root.expanduser()

        if create:
            try:
                media_root.mkdir(parents=True, exist_ok=True)
                backup_root.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise PublicSiteMediaError(
                    503, "public_media_storage_unavailable"
                ) from exc

        for root in (media_root, backup_root):
            if root.is_symlink() or (root.exists() and not root.is_dir()):
                raise PublicSiteMediaError(503, "public_media_storage_unavailable")
        if create and (not media_root.is_dir() or not backup_root.is_dir()):
            raise PublicSiteMediaError(503, "public_media_storage_unavailable")
        return media_root, backup_root

    @staticmethod
    def _probe_storage_root(root: Path) -> None:
        probe_path: Path | None = None
        descriptor: int | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".public-site-media-probe-", dir=root
            )
            probe_path = Path(temporary_name)
            payload = secrets.token_bytes(32)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if probe_path.read_bytes() != payload:
                raise OSError("storage probe did not round-trip")
        except OSError as exc:
            raise PublicSiteMediaError(503, "public_media_storage_unavailable") from exc
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if probe_path is not None:
                try:
                    probe_path.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("public_site_media.storage_probe_cleanup_failed")
                    raise PublicSiteMediaError(
                        503, "public_media_storage_unavailable"
                    ) from exc

    def verify_storage_ready(self) -> None:
        """Round-trip and remove a temporary file in both configured roots."""
        media_root, backup_root = self._configured_roots()
        for root in (media_root, backup_root):
            if not root.is_dir():
                raise PublicSiteMediaError(503, "public_media_storage_unavailable")
            self._probe_storage_root(root)

    @staticmethod
    def _normalize_image(
        raw: bytes, *, max_upload_bytes: int, max_pixels: int
    ) -> tuple[bytes, str]:
        if not raw:
            raise PublicSiteMediaError(400, "public_media_empty_file")
        if len(raw) > max_upload_bytes:
            raise PublicSiteMediaError(413, "public_media_file_too_large")

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(raw)) as source:
                    image_format = source.format
                    if image_format not in _FORMATS:
                        raise PublicSiteMediaError(
                            400, "public_media_unsupported_image"
                        )
                    if (
                        getattr(source, "is_animated", False)
                        or getattr(source, "n_frames", 1) != 1
                    ):
                        raise PublicSiteMediaError(
                            400, "public_media_unsupported_image"
                        )
                    if source.width * source.height > max_pixels:
                        raise PublicSiteMediaError(
                            413, "public_media_image_dimensions_too_large"
                        )
                    source.verify()

                with Image.open(BytesIO(raw)) as source:
                    image = ImageOps.exif_transpose(source)
                    image.load()
                    has_alpha = (
                        "A" in image.getbands()
                        or image.info.get("transparency") is not None
                    )
                    if image_format == "JPEG":
                        rgba = image.convert("RGBA")
                        flattened = Image.new("RGB", rgba.size, (255, 255, 255))
                        flattened.paste(rgba, mask=rgba.getchannel("A"))
                        output_image = flattened
                    elif image_format == "PNG":
                        output_image = image.convert("RGBA" if has_alpha else "RGB")
                    else:
                        output_image = image.convert("RGBA" if has_alpha else "RGB")

                    output = BytesIO()
                    save_options: dict[str, object]
                    if image_format == "JPEG":
                        save_options = {
                            "quality": 90,
                            "optimize": True,
                            "progressive": True,
                        }
                    elif image_format == "PNG":
                        save_options = {"optimize": True}
                    else:
                        save_options = {"quality": 90, "method": 6}
                    output_image.save(output, format=image_format, **save_options)
                    normalized = output.getvalue()
        except PublicSiteMediaError:
            raise
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            UnidentifiedImageError,
            OSError,
            ValueError,
        ) as exc:
            raise PublicSiteMediaError(400, "public_media_unsupported_image") from exc

        mime_type = _FORMATS[image_format][0]
        if len(normalized) > max_upload_bytes:
            raise PublicSiteMediaError(413, "public_media_file_too_large")
        return normalized, mime_type

    @staticmethod
    def _atomic_write(path: Path, body: bytes) -> None:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=".public-media-", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(file_descriptor, "wb") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise

    def _media_path(self, storage_key: str) -> Path:
        if not _STORAGE_KEY_RE.fullmatch(storage_key):
            raise PublicSiteMediaError(404, "public_content_not_found")
        media_root, _ = self._configured_roots()
        return media_root / storage_key

    def _verified_file(self, media: PublicSiteMedia) -> bytes:
        try:
            path = self._media_path(media.storage_key)
            if path.is_symlink() or not path.is_file():
                raise OSError("media file unavailable")
            body = path.read_bytes()
        except PublicSiteMediaError:
            raise
        except OSError as exc:
            raise PublicSiteMediaError(503, "public_media_storage_unavailable") from exc
        if (
            len(body) != media.byte_size
            or hashlib.sha256(body).hexdigest() != media.sha256
        ):
            raise PublicSiteMediaError(503, "public_media_storage_unavailable")
        return body

    def _write_backup(self, media: PublicSiteMedia) -> None:
        _, backup_root = self._configured_roots(create=True)
        body = self._verified_file(media)
        extension = {
            mime_type: file_extension
            for _image_format, (mime_type, file_extension) in _FORMATS.items()
        }.get(media.mime_type)
        if extension is None:
            raise PublicSiteMediaError(503, "public_media_storage_unavailable")
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        backup_path = backup_root / (
            f"{timestamp}-{media.storage_key}-{secrets.token_hex(4)}{extension}"
        )
        try:
            self._atomic_write(backup_path, body)
        except OSError as exc:
            raise PublicSiteMediaError(503, "public_media_storage_unavailable") from exc

    def list_admin_media(self) -> list[dict[str, object]]:
        rows = list(
            self.db.scalars(
                select(PublicSiteMedia).order_by(PublicSiteMedia.created_at.desc())
            ).all()
        )
        return [self.list_admin_media_item(row) for row in rows]

    def list_admin_media_item(self, row: PublicSiteMedia) -> dict[str, object]:
        return {
            "id": row.id,
            "asset_kind": row.asset_kind,
            "doctor_id": row.doctor_id,
            "mime_type": row.mime_type,
            "byte_size": row.byte_size,
            "is_published": row.is_published,
            "published_at": row.published_at,
            "created_at": row.created_at,
            "media_url": self._public_media_url(row.storage_key),
        }

    def get_admin_preview(self, media_id: int) -> PublicSiteMediaPayload:
        """Read and verify a published or draft image for an authenticated Admin."""
        media = self.db.get(PublicSiteMedia, media_id)
        if media is None:
            raise PublicSiteMediaError(404, "public_media_not_found")
        return PublicSiteMediaPayload(
            body=self._verified_file(media),
            mime_type=media.mime_type,
        )

    @staticmethod
    def _public_media_url(storage_key: str) -> str:
        return f"/api/v1/public-site/media/{storage_key}"

    def upload(
        self,
        *,
        raw: bytes,
        asset_kind: str,
        doctor_id: int | None,
        actor_user_id: int,
    ) -> PublicSiteMedia:
        if asset_kind not in ("clinic_logo", "doctor_portrait"):
            raise PublicSiteMediaError(400, "public_media_invalid_asset_kind")
        if (asset_kind == "clinic_logo" and doctor_id is not None) or (
            asset_kind == "doctor_portrait" and doctor_id is None
        ):
            raise PublicSiteMediaError(400, "public_media_invalid_owner")
        if doctor_id is not None and self.db.get(Doctor, doctor_id) is None:
            raise PublicSiteMediaError(404, "public_media_doctor_not_found")

        normalized, mime_type = self._normalize_image(
            raw,
            max_upload_bytes=self.max_upload_bytes,
            max_pixels=self.max_pixels,
        )
        media_root, _ = self._configured_roots(create=True)
        storage_key = secrets.token_hex(32)
        media_path = media_root / storage_key
        commit_attempted = False
        try:
            self._atomic_write(media_path, normalized)
            media = PublicSiteMedia(
                asset_kind=asset_kind,
                doctor_id=doctor_id,
                storage_key=storage_key,
                mime_type=mime_type,
                byte_size=len(normalized),
                sha256=hashlib.sha256(normalized).hexdigest(),
                is_published=False,
                published_at=None,
                uploaded_by_user_id=actor_user_id,
            )
            self._write_backup(media)
            self.db.add(media)
            self.db.flush()
            log_audit_event(
                self.db,
                user_id=actor_user_id,
                action="create",
                table_name="public_site_media",
                row_id=media.id,
                new_values={
                    "asset_kind": asset_kind,
                    "doctor_id": doctor_id,
                    "mime_type": mime_type,
                    "byte_size": len(normalized),
                    "is_published": False,
                },
                description="Public-site media uploaded",
            )
            commit_attempted = True
            self.db.commit()
            self.db.refresh(media)
            return media
        except PublicSiteMediaError:
            self.db.rollback()
            if not commit_attempted:
                try:
                    media_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("public_site_media.upload_orphan_cleanup_failed")
            raise
        except Exception as exc:
            self.db.rollback()
            if not commit_attempted:
                try:
                    media_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("public_site_media.upload_orphan_cleanup_failed")
            logger.warning(
                "public_site_media.upload_failed error_type=%s", type(exc).__name__
            )
            raise PublicSiteMediaError(500, "public_media_operation_failed") from exc

    def publish(self, *, media_id: int, actor_user_id: int) -> PublicSiteMedia:
        media = self.db.get(PublicSiteMedia, media_id)
        if media is None:
            raise PublicSiteMediaError(404, "public_media_not_found")
        if media.is_published:
            return media

        self._verified_file(media)
        current_stmt = select(PublicSiteMedia).where(
            PublicSiteMedia.asset_kind == media.asset_kind,
            PublicSiteMedia.is_published.is_(True),
            PublicSiteMedia.id != media.id,
        )
        if media.doctor_id is None:
            current_stmt = current_stmt.where(PublicSiteMedia.doctor_id.is_(None))
        else:
            current_stmt = current_stmt.where(
                PublicSiteMedia.doctor_id == media.doctor_id
            )
        current_rows = list(self.db.scalars(current_stmt.with_for_update()).all())

        try:
            for current in current_rows:
                self._write_backup(current)
                current.is_published = False
                current.published_at = None
                current.updated_at = datetime.now(UTC)
            if current_rows:
                self.db.flush()

            self._write_backup(media)
            old_value = {
                "is_published": False,
                "published_at": None,
            }
            media.is_published = True
            media.published_at = datetime.now(UTC)
            media.updated_at = media.published_at
            self.db.flush()
            log_audit_event(
                self.db,
                user_id=actor_user_id,
                action="update",
                table_name="public_site_media",
                row_id=media.id,
                old_values=old_value,
                new_values={
                    "asset_kind": media.asset_kind,
                    "doctor_id": media.doctor_id,
                    "is_published": True,
                },
                description="Public-site media published",
            )
            for current in current_rows:
                log_audit_event(
                    self.db,
                    user_id=actor_user_id,
                    action="update",
                    table_name="public_site_media",
                    row_id=current.id,
                    old_values={"is_published": True},
                    new_values={"is_published": False},
                    description="Public-site media replaced",
                )
            self.db.commit()
            self.db.refresh(media)
            return media
        except PublicSiteMediaError:
            self.db.rollback()
            raise
        except IntegrityError as exc:
            self.db.rollback()
            raise PublicSiteMediaError(
                409, "public_media_publication_conflict"
            ) from exc
        except Exception as exc:
            self.db.rollback()
            logger.warning(
                "public_site_media.publish_failed error_type=%s", type(exc).__name__
            )
            raise PublicSiteMediaError(500, "public_media_operation_failed") from exc

    def unpublish(self, *, media_id: int, actor_user_id: int) -> PublicSiteMedia:
        media = self.db.get(PublicSiteMedia, media_id)
        if media is None:
            raise PublicSiteMediaError(404, "public_media_not_found")
        if not media.is_published:
            raise PublicSiteMediaError(409, "public_media_not_published")

        try:
            self._write_backup(media)
            old_values = {"is_published": True, "published_at": media.published_at}
            media.is_published = False
            media.published_at = None
            media.updated_at = datetime.now(UTC)
            log_audit_event(
                self.db,
                user_id=actor_user_id,
                action="update",
                table_name="public_site_media",
                row_id=media.id,
                old_values=old_values,
                new_values={"is_published": False, "published_at": None},
                description="Public-site media unpublished",
            )
            self.db.commit()
            self.db.refresh(media)
            return media
        except PublicSiteMediaError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            logger.warning(
                "public_site_media.unpublish_failed error_type=%s", type(exc).__name__
            )
            raise PublicSiteMediaError(500, "public_media_operation_failed") from exc

    def get_public_asset(self, storage_key: str) -> PublicSiteMediaPayload | None:
        if not _STORAGE_KEY_RE.fullmatch(storage_key):
            return None
        media = self.db.scalars(
            select(PublicSiteMedia).where(
                PublicSiteMedia.storage_key == storage_key,
                PublicSiteMedia.is_published.is_(True),
            )
        ).first()
        if media is None:
            return None
        if media.doctor_id is not None:
            read_service = PublicSiteReadService(PublicSiteReadRepository(self.db))
            if not read_service.is_public_doctor_media_owner(media.doctor_id):
                return None
        return PublicSiteMediaPayload(
            body=self._verified_file(media),
            mime_type=media.mime_type,
        )

    @staticmethod
    def cleanup_expired_backups(
        *,
        backup_root: Path | str | None = None,
        retention_days: int | None = None,
        now: datetime | None = None,
    ) -> int:
        configured_root = (
            Path(backup_root)
            if backup_root is not None
            else settings.PUBLIC_SITE_MEDIA_BACKUP_ROOT
        )
        if configured_root is None:
            raise PublicSiteMediaError(503, "public_media_storage_unavailable")
        root = configured_root.expanduser()
        if root.is_symlink() or not root.is_dir():
            raise PublicSiteMediaError(503, "public_media_storage_unavailable")
        days = (
            retention_days
            if retention_days is not None
            else settings.PUBLIC_SITE_MEDIA_BACKUP_RETENTION_DAYS
        )
        cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
        removed = 0
        for entry in root.iterdir():
            if not _BACKUP_NAME_RE.fullmatch(entry.name) or entry.is_symlink():
                continue
            try:
                modified_at = datetime.fromtimestamp(entry.stat().st_mtime, UTC)
                if modified_at < cutoff and entry.is_file():
                    entry.unlink()
                    removed += 1
            except OSError:
                logger.warning("public_site_media.backup_cleanup_failed")
        return removed
