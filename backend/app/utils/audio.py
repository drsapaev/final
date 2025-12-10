"""
Утилиты для работы с аудио файлами
"""

import io
import logging
from typing import Tuple
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

# Максимальный размер файла (10 MB)
MAX_AUDIO_SIZE = 10 * 1024 * 1024

# Максимальная длительность (5 минут)
MAX_AUDIO_DURATION = 300


async def validate_audio_file(content: bytes, filename: str) -> Tuple[str, str]:
    """
    Валидация аудио файла
    
    Args:
        content: Содержимое файла
        filename: Имя файла
        
    Returns:
        Tuple[format, mime_type]
        
    Raises:
        HTTPException: Если файл не валиден
    """
    import os
    
    # Проверка размера
    if len(content) > MAX_AUDIO_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой (максимум {MAX_AUDIO_SIZE // 1024 // 1024} MB)"
        )
    
    # Проверка формата по расширению
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in ALLOWED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат аудио. Разрешены: {', '.join(ALLOWED_AUDIO_FORMATS.keys())}"
        )
    
    mime_type = ALLOWED_AUDIO_FORMATS[file_ext]
    format_name = file_ext.replace(".", "")
    
    return format_name, mime_type


async def get_audio_duration(content: bytes, format_name: str) -> int:
    """
    Получить длительность аудио в секундах
    
    Args:
        content: Содержимое файла
        format_name: Формат без точки (mp3, wav, ogg и т.д.)
        
    Returns:
        Длительность в секундах
        
    Raises:
        HTTPException: Если не удалось получить длительность
    """
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
        # Если pydub не установлен - возвращаем примерную длительность
        # Для webm/opus: ~64kbps = ~8KB/s
        estimated_duration = len(content) // 8000
        return min(estimated_duration, MAX_AUDIO_DURATION)
        
    except Exception as e:
        logger.error(f"Failed to get audio duration: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Не удалось обработать аудио файл: {str(e)}"
        )


async def compress_audio_if_needed(content: bytes, format_name: str) -> bytes:
    """
    Сжать аудио если оно слишком большое
    
    Args:
        content: Содержимое файла
        format_name: Формат без точки
        
    Returns:
        Сжатое содержимое (или оригинал если сжатие не нужно)
    """
    # Если файл меньше 1 MB - не сжимаем
    if len(content) < 1024 * 1024:
        return content
    
    try:
        from pydub import AudioSegment
        
        audio = AudioSegment.from_file(
            io.BytesIO(content),
            format=format_name
        )
        
        # Конвертируем в mono, 16kHz, 64kbps OGG
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(16000)
        
        output = io.BytesIO()
        audio.export(output, format="ogg", bitrate="64k")
        
        compressed = output.getvalue()
        
        logger.info(f"Compressed audio from {len(content)} to {len(compressed)} bytes")
        return compressed
        
    except ImportError:
        logger.warning("pydub not installed, cannot compress audio")
        return content
        
    except Exception as e:
        logger.warning(f"Failed to compress audio: {e}, using original")
        return content
