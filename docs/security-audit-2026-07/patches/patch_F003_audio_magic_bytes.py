"""
PATCH F-003: Magic bytes валидация аудио + Content-Disposition: attachment
=========================================================================

Файлы:
  1. backend/app/utils/audio.py — добавить проверку magic bytes
  2. backend/app/services/messages_api_service.py — stream с attachment + nosniff
  3. backend/requirements.txt — добавить python-magic

Зависимости:
  pip install python-magic
  Системная зависимость: libmagic1 (apt-get install libmagic1)
"""

# === 1. backend/app/utils/audio.py ===
AUDIO_PATCH = '''
"""
Утилиты для работы с аудио файлами — с проверкой magic bytes.
"""
import io
import logging

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Поддерживаемые форматы аудио
ALLOWED_AUDIO_FORMATS = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".webm": "audio/webm",
}

# НОВОЕ: magic bytes сигнатуры для каждого формата
# Источник: https://en.wikipedia.org/wiki/List_of_file_signatures
AUDIO_MAGIC_SIGNATURES = {
    ".mp3": [
        b"\\xff\\xfb",  # MP3 frame sync (MPEG-1 Layer III, no ID3)
        b"\\xff\\xf3",  # MP3 frame sync (MPEG-2 Layer III)
        b"\\xff\\xf2",  # MP3 frame sync (MPEG-2.5 Layer III)
        b"ID3",          # ID3v2 tag
    ],
    ".wav":  [b"RIFF"],          # RIFF container (WAV)
    ".ogg":  [b"OggS"],          # OGG container
    ".m4a":  [b"\\x00\\x00\\x00", b"ftyp"],  # MP4/M4A (offset 4: "ftyp")
    ".webm": [b"\\x1aE\\xdf\\xa3"],  # EBML (WebM/Matroska)
}

MAX_AUDIO_SIZE = 10 * 1024 * 1024
MAX_AUDIO_DURATION = 300


def _check_magic_bytes(content: bytes, file_ext: str) -> bool:
    """
    Проверка magic bytes: первые байты контента должны соответствовать
    сигнатуре заявленного формата.
    """
    expected_signatures = AUDIO_MAGIC_SIGNATURES.get(file_ext, [])
    if not expected_signatures:
        return False

    # Спец-проверка для m4a (сигнатура "ftyp" на смещении 4)
    if file_ext == ".m4a":
        return len(content) >= 12 and content[4:8] == b"ftyp"

    # Общий случай: проверяем первые N байт
    for sig in expected_signatures:
        if content.startswith(sig):
            return True
    return False


async def validate_audio_file(content: bytes, filename: str) -> tuple[str, str]:
    """
    Валидация аудио файла: размер + расширение + magic bytes.

    Args:
        content: Содержимое файла (байты)
        filename: Имя файла

    Returns:
        Tuple[format, mime_type]

    Raises:
        HTTPException: Если файл не валиден
    """
    import os

    # 1. Проверка размера (как раньше)
    if len(content) > MAX_AUDIO_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой (максимум {MAX_AUDIO_SIZE // 1024 // 1024} MB)"
        )

    # 2. Проверка расширения (как раньше)
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in ALLOWED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат аудио. Разрешены: {", ".join(ALLOWED_AUDIO_FORMATS.keys())}"
        )

    # 3. НОВОЕ: проверка magic bytes
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

    # 4. НОВОЕ: опционально — python-magic для доп. верификации
    try:
        import magic
        detected_mime = magic.from_buffer(content, mime=True)
        expected_mime = ALLOWED_AUDIO_FORMATS[file_ext]
        # Разрешаем некоторые варианты MIME (audio/wav vs audio/wave vs audio/x-wav)
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
        logger.warning("python-magic not installed, only magic bytes check performed")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Magic detection failed: %s", exc)

    mime_type = ALLOWED_AUDIO_FORMATS[file_ext]
    format_name = file_ext.replace(".", "")
    return format_name, mime_type


# Функция get_audio_duration — без изменений
# Функция compress_audio_if_needed — без изменений
'''

# === 2. backend/app/services/messages_api_service.py (stream_voice_message) ===
STREAM_PATCH = '''
# Изменения в stream_voice_message (строки 533-560)

def stream_voice_message(self, *, message_id: int, current_user: User) -> dict[str, Any]:
    message = self.repository.get_message(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    if message.sender_id != current_user.id and message.recipient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому сообщению")
    if message.message_type != "voice" or not message.file_id:
        raise HTTPException(status_code=400, detail="Это не голосовое сообщение")

    file_record = self.repository.get_file_by_id(message.file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="Аудио файл не найден")
    if not os.path.exists(file_record.file_path):
        raise HTTPException(status_code=404, detail="Файл не найден на диске")

    self._audit(
        action="access_voice_message",
        entity_type="message",
        entity_id=message_id,
        actor_user_id=current_user.id,
        payload={"file_id": file_record.id},
    )

    return {
        "path": file_record.file_path,
        "media_type": file_record.mime_type,
        # ИЗМЕНЕНО: всегда attachment, никогда inline
        "content_disposition": "attachment",
        "content_disposition_filename": "voice_message.mp3",  # нейтральное имя
    }


# Изменения в endpoint (строки 781-798):
@router.get("/voice/{message_id}/stream")
async def stream_voice_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = MessagesApiService(db).stream_voice_message(
        message_id=message_id,
        current_user=current_user,
    )
    return FileResponse(
        payload["path"],
        media_type=payload["media_type"],
        headers={
            # ИЗМЕНЕНО: attachment вместо inline
            "Content-Disposition": 'attachment; filename="voice_message.mp3"',
            # НОВОЕ: запретить MIME-sniffing
            "X-Content-Type-Options": "nosniff",
            # НОВОЕ: запретить встраивание в iframe
            "X-Frame-Options": "DENY",
            # НОВОЕ: CSP для этого ответа
            "Content-Security-Policy": "default-src 'none'",
        },
    )
'''

# === 3. backend/requirements.txt — добавить зависимость ===
REQUIREMENTS_PATCH = '''
# Добавить в backend/requirements.txt:
python-magic==0.4.27
# Системная зависимость (Ubuntu/Debian): sudo apt-get install libmagic1
'''

if __name__ == "__main__":
    print("F-003 PATCH — Audio magic bytes + attachment disposition")
    print("=" * 60)
    for name, content in [
        ("AUDIO_PATCH", AUDIO_PATCH),
        ("STREAM_PATCH", STREAM_PATCH),
        ("REQUIREMENTS_PATCH", REQUIREMENTS_PATCH),
    ]:
        print(f"\n--- {name} ---")
        print(content[:400] + "...")
