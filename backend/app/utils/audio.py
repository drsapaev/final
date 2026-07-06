"""
Утилиты для работы с аудио файлами.

F-003: добавлена проверка magic bytes для предотвращения XSS через
переименованные файлы (evil.html → evil.mp3).
"""

import io
import logging

from fastapi import HTTPException

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_FORMATS = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".webm": "audio/webm",
}

# F-003: magic bytes сигнатуры для каждого формата
AUDIO_MAGIC_SIGNATURES = {
    ".mp3": [
        b"\\xff\\xfb",  # MP3 frame sync (MPEG-1 Layer III, no ID3)
        b"\\xff\\xf3",  # MP3 frame sync (MPEG-2 Layer III)
        b"\\xff\\xf2",  # MP3 frame sync (MPEG-2.5 Layer III)
        b"ID3",         # ID3v2 tag
    ],
    ".wav":  [b"RIFF"],                # RIFF container (WAV)
    ".ogg":  [b"OggS"],                # OGG container
    ".webm": [b"\\x1aE\\xdf\\xa3"],    # EBML (WebM/Matroska)
    # m4a требует спец-проверку (сигнатура "ftyp" на смещении 4)
}

MAX_AUDIO_SIZE = 10 * 1024 * 1024
MAX_AUDIO_DURATION = 300


def _check_magic_bytes(content: bytes, file_ext: str) -> bool:
    """Проверка magic bytes: первые байты контента должны соответствовать сигнатуре формата."""
    expected_signatures = AUDIO_MAGIC_SIGNATURES.get(file_ext, [])
    if not expected_signatures:
        return False

    # Спец-проверка для m4a (сигнатура "ftyp" на смещении 4)
    if file_ext == ".m4a":
        return len(content) >= 12 and content[4:8] == b"ftyp"

    for sig in expected_signatures:
        if content.startswith(sig):
            return True
    return False


async def validate_audio_file(content: bytes, filename: str) -> tuple[str, str]:
    """
    Валидация аудио файла: размер + расширение + magic bytes.

    F-003: добавлена проверка magic bytes для предотвращения XSS через
    переименованные файлы.
    """
    import os

    if len(content) > MAX_AUDIO_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой (максимум {MAX_AUDIO_SIZE // 1024 // 1024} MB)"
        )

    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in ALLOWED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат аудио. Разрешены: {', '.join(ALLOWED_AUDIO_FORMATS.keys())}"
        )

    # F-003: проверка magic bytes
    if not _check_magic_bytes(content, file_ext):
        logger.warning(
            "Audio magic bytes mismatch: filename=%s, ext=%s, first_bytes=%s",
            filename, file_ext, content[:16].hex(),
        )
        raise HTTPException(
            status_code=400,
            detail="Содержимое файла не соответствует заявленному формату. "
                   "Возможно, файл повреждён или переименован."
        )

    # F-003: опциональная проверка через python-magic (если установлен)
    try:
        import magic
        detected_mime = magic.from_buffer(content, mime=True)
        expected_mime = ALLOWED_AUDIO_FORMATS[file_ext]
        mime_aliases = {
            "audio/mpeg": ["audio/mpeg", "audio/mp3"],
            "audio/wav": ["audio/wav", "audio/wave", "audio/x-wav"],
            "audio/ogg": ["audio/ogg", "application/ogg"],
            "audio/mp4": ["audio/mp4", "audio/m4a", "video/mp4"],
            "audio/webm": ["audio/webm", "video/webm"],
        }
        allowed_mimes = mime_aliases.get(expected_mime, [expected_mime])
        if detected_mime not in allowed_mimes:
            logger.warning(
                "Audio MIME mismatch: filename=%s, detected=%s, expected_family=%s",
                filename, detected_mime, expected_mime,
            )
            raise HTTPException(
                status_code=400,
                detail=f"Обнаруженный тип файла ({detected_mime}) не соответствует ожидаемому"
            )
    except ImportError:
        logger.debug("python-magic not installed, only magic bytes check performed")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Magic detection failed: %s", exc)

    mime_type = ALLOWED_AUDIO_FORMATS[file_ext]
    format_name = file_ext.replace(".", "")
    return format_name, mime_type


async def get_audio_duration(content: bytes, format_name: str) -> int:
    """Получить длительность аудио в секундах."""
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(
            io.BytesIO(content),
            format=format_name
        )
        duration_seconds = int(audio.duration_seconds)
        if duration_seconds > MAX_AUDIO_DURATION:
            raise HTTPException(
                status_code=400,
                detail=f"Аудио слишком длинное (максимум {MAX_AUDIO_DURATION // 60} минут)"
            )
        return duration_seconds
    except ImportError:
        logger.warning("pydub not installed, cannot get audio duration")
        estimated_duration = len(content) // 18000
        return min(estimated_duration, MAX_AUDIO_DURATION)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to get audio duration error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=400, detail="Не удалось обработать аудио файл") from None


async def compress_audio_if_needed(content: bytes, format_name: str) -> bytes:
    """Сжать аудио если оно слишком большое."""
    if len(content) < 1024 * 1024:
        return content
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(io.BytesIO(content), format=format_name)
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(16000)
        output = io.BytesIO()
        audio.export(output, format="ogg", bitrate="64k")
        compressed = output.getvalue()
        logger.info("Compressed audio successfully")
        return compressed
    except ImportError:
        logger.warning("pydub not installed, cannot compress audio")
        return content
    except Exception as exc:
        logger.warning("Failed to compress audio error_type=%s; using original", type(exc).__name__)
        return content
