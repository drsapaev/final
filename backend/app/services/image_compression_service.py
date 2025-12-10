"""
Image Compression Service
Сервис для оптимизации и сжатия изображений
"""
import io
import os
import logging
from typing import Optional, Tuple
from PIL import Image

logger = logging.getLogger(__name__)


class ImageCompressor:
    """
    Сервис для сжатия и оптимизации изображений
    
    Поддерживает:
    - JPEG с настраиваемым качеством
    - PNG с оптимизацией
    - WebP с высоким сжатием
    - Автоматическое изменение размера
    - Оптимизация для веб (progressive JPEG)
    """
    
    # Максимальные размеры для разных целей
    SIZE_PRESETS = {
        "thumbnail": (150, 150),
        "preview": (400, 400),
        "medium": (800, 800),
        "large": (1600, 1600),
        "full": (2400, 2400),
    }
    
    # Качество по умолчанию для JPEG
    DEFAULT_QUALITY = 85
    
    # Минимальное качество
    MIN_QUALITY = 40
    
    def __init__(
        self,
        max_size: Tuple[int, int] = (1920, 1920),
        quality: int = 85,
        output_format: str = "JPEG",
    ):
        """
        Инициализация компрессора
        
        Args:
            max_size: Максимальный размер (width, height)
            quality: Качество сжатия (1-100)
            output_format: Выходной формат (JPEG, PNG, WEBP)
        """
        self.max_size = max_size
        self.quality = min(100, max(self.MIN_QUALITY, quality))
        self.output_format = output_format.upper()
    
    def compress(
        self,
        image_data: bytes,
        max_size: Optional[Tuple[int, int]] = None,
        quality: Optional[int] = None,
        output_format: Optional[str] = None,
        preserve_exif: bool = False,
    ) -> Tuple[bytes, dict]:
        """
        Сжимает изображение
        
        Args:
            image_data: Исходные байты изображения
            max_size: Максимальный размер (переопределяет default)
            quality: Качество (переопределяет default)
            output_format: Формат (переопределяет default)
            preserve_exif: Сохранять EXIF данные
            
        Returns:
            Tuple[bytes, dict]: Сжатые данные и метаданные
        """
        try:
            # Открываем изображение
            img = Image.open(io.BytesIO(image_data))
            
            # Сохраняем оригинальные данные
            original_size = len(image_data)
            original_dimensions = img.size
            original_format = img.format
            
            # EXIF данные
            exif_data = None
            if preserve_exif and hasattr(img, '_getexif'):
                try:
                    exif_data = img.info.get('exif')
                except Exception:
                    pass
            
            # Конвертируем RGBA в RGB для JPEG
            target_format = output_format or self.output_format
            if target_format == "JPEG" and img.mode in ('RGBA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode not in ('RGB', 'RGBA', 'L'):
                img = img.convert('RGB')
            
            # Изменяем размер если нужно
            target_size = max_size or self.max_size
            if img.size[0] > target_size[0] or img.size[1] > target_size[1]:
                img.thumbnail(target_size, Image.Resampling.LANCZOS)
            
            # Компрессия
            output = io.BytesIO()
            target_quality = quality or self.quality
            
            save_kwargs = {}
            
            if target_format == "JPEG":
                save_kwargs = {
                    "format": "JPEG",
                    "quality": target_quality,
                    "optimize": True,
                    "progressive": True,
                }
                if exif_data:
                    save_kwargs["exif"] = exif_data
                    
            elif target_format == "PNG":
                save_kwargs = {
                    "format": "PNG",
                    "optimize": True,
                }
                
            elif target_format == "WEBP":
                save_kwargs = {
                    "format": "WEBP",
                    "quality": target_quality,
                    "method": 6,  # Максимальное сжатие
                }
                if exif_data:
                    save_kwargs["exif"] = exif_data
            else:
                save_kwargs = {
                    "format": target_format,
                }
            
            img.save(output, **save_kwargs)
            compressed_data = output.getvalue()
            
            # Статистика
            compressed_size = len(compressed_data)
            compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
            
            metadata = {
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": round(compression_ratio, 2),
                "original_dimensions": original_dimensions,
                "new_dimensions": img.size,
                "original_format": original_format,
                "output_format": target_format,
                "quality": target_quality,
            }
            
            logger.info(
                f"Image compressed: {original_size} -> {compressed_size} bytes "
                f"({compression_ratio:.1f}% reduction)"
            )
            
            return compressed_data, metadata
            
        except Exception as e:
            logger.error(f"Image compression error: {e}")
            raise
    
    def compress_for_web(
        self,
        image_data: bytes,
        target_size_kb: int = 200,
        min_quality: int = 40,
    ) -> Tuple[bytes, dict]:
        """
        Сжимает изображение до целевого размера в KB
        Автоматически подбирает качество
        
        Args:
            image_data: Исходные байты
            target_size_kb: Целевой размер в KB
            min_quality: Минимальное качество
            
        Returns:
            Tuple[bytes, dict]: Сжатые данные и метаданные
        """
        target_size_bytes = target_size_kb * 1024
        
        # Если уже достаточно маленькое
        if len(image_data) <= target_size_bytes:
            return self.compress(image_data)
        
        # Бинарный поиск оптимального качества
        low, high = min_quality, 95
        best_data = None
        best_metadata = None
        
        while low <= high:
            mid = (low + high) // 2
            compressed, metadata = self.compress(image_data, quality=mid)
            
            if len(compressed) <= target_size_bytes:
                best_data = compressed
                best_metadata = metadata
                low = mid + 1  # Пробуем более высокое качество
            else:
                high = mid - 1  # Нужно больше сжатия
        
        if best_data is None:
            # Если не удалось достичь целевого размера, возвращаем минимальное качество
            best_data, best_metadata = self.compress(image_data, quality=min_quality)
        
        return best_data, best_metadata
    
    def create_thumbnail(
        self,
        image_data: bytes,
        size: Tuple[int, int] = (150, 150),
        quality: int = 80,
    ) -> Tuple[bytes, dict]:
        """
        Создаёт миниатюру изображения
        
        Args:
            image_data: Исходные байты
            size: Размер миниатюры
            quality: Качество
            
        Returns:
            Tuple[bytes, dict]: Миниатюра и метаданные
        """
        return self.compress(image_data, max_size=size, quality=quality)
    
    def optimize_for_storage(
        self,
        image_data: bytes,
        preset: str = "medium",
    ) -> Tuple[bytes, dict]:
        """
        Оптимизирует изображение для хранения
        
        Args:
            image_data: Исходные байты
            preset: Пресет размера (thumbnail, preview, medium, large, full)
            
        Returns:
            Tuple[bytes, dict]: Оптимизированные данные и метаданные
        """
        size = self.SIZE_PRESETS.get(preset, self.SIZE_PRESETS["medium"])
        return self.compress(image_data, max_size=size, quality=85)


# Глобальный экземпляр
_compressor_instance = None


def get_image_compressor() -> ImageCompressor:
    """Получить глобальный экземпляр компрессора"""
    global _compressor_instance
    if _compressor_instance is None:
        _compressor_instance = ImageCompressor()
    return _compressor_instance


def compress_image(
    image_data: bytes,
    max_size: Tuple[int, int] = (1920, 1920),
    quality: int = 85,
) -> Tuple[bytes, dict]:
    """Быстрое сжатие изображения"""
    return get_image_compressor().compress(image_data, max_size=max_size, quality=quality)


def create_thumbnail(image_data: bytes, size: Tuple[int, int] = (150, 150)) -> Tuple[bytes, dict]:
    """Быстрое создание миниатюры"""
    return get_image_compressor().create_thumbnail(image_data, size=size)
