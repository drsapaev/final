"""
File Validation Utility (Backend)

Validates uploaded files using magic number (file signature) detection
to prevent file type spoofing and malware uploads.

Security Features:
- Magic number validation
- File size limits
- MIME type verification
- Extension whitelist
- Malware signature detection
"""

import logging
import mimetypes
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status

logger = logging.getLogger(__name__)


class FileCategory(str, Enum):
    """File categories"""
    IMAGE = "image"
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    MEDICAL = "medical"
    AUDIO = "audio"
    VIDEO = "video"
    ARCHIVE = "archive"
    OTHER = "other"


# Magic numbers (file signatures) for different file types
MAGIC_NUMBERS = {
    # Images
    b'\xFF\xD8\xFF': {'ext': ['.jpg', '.jpeg'], 'mime': 'image/jpeg', 'category': FileCategory.IMAGE},
    b'\x89PNG\r\n\x1a\n': {'ext': ['.png'], 'mime': 'image/png', 'category': FileCategory.IMAGE},
    b'GIF87a': {'ext': ['.gif'], 'mime': 'image/gif', 'category': FileCategory.IMAGE},
    b'GIF89a': {'ext': ['.gif'], 'mime': 'image/gif', 'category': FileCategory.IMAGE},
    b'BM': {'ext': ['.bmp'], 'mime': 'image/bmp', 'category': FileCategory.IMAGE},
    b'RIFF': {'ext': ['.webp'], 'mime': 'image/webp', 'category': FileCategory.IMAGE},  # Needs WEBP check
    b'II*\x00': {'ext': ['.tiff', '.tif'], 'mime': 'image/tiff', 'category': FileCategory.IMAGE},
    b'MM\x00*': {'ext': ['.tiff', '.tif'], 'mime': 'image/tiff', 'category': FileCategory.IMAGE},

    # HEIC (медицинские фото с iPhone)
    b'ftypheic': {'ext': ['.heic'], 'mime': 'image/heic', 'category': FileCategory.IMAGE},
    b'ftypheix': {'ext': ['.heic'], 'mime': 'image/heic', 'category': FileCategory.IMAGE},
    b'ftyphevc': {'ext': ['.heic'], 'mime': 'image/heic', 'category': FileCategory.IMAGE},

    # Documents
    b'%PDF': {'ext': ['.pdf'], 'mime': 'application/pdf', 'category': FileCategory.DOCUMENT},
    b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1': {  # DOC, XLS, PPT (OLE)
        'ext': ['.doc', '.xls', '.ppt'],
        'mime': 'application/msword',
        'category': FileCategory.DOCUMENT
    },
    b'PK\x03\x04': {  # DOCX, XLSX, PPTX, ZIP, ODT
        'ext': ['.docx', '.xlsx', '.pptx', '.zip', '.odt'],
        'mime': 'application/zip',
        'category': FileCategory.DOCUMENT
    },

    # Medical formats
    b'DICM': {'ext': ['.dcm', '.dicom'], 'mime': 'application/dicom', 'category': FileCategory.MEDICAL},
    b'<?xml': {'ext': ['.xml'], 'mime': 'application/xml', 'category': FileCategory.MEDICAL},

    # Archives
    b'PK\x05\x06': {'ext': ['.zip'], 'mime': 'application/zip', 'category': FileCategory.ARCHIVE},
    b'PK\x07\x08': {'ext': ['.zip'], 'mime': 'application/zip', 'category': FileCategory.ARCHIVE},
    b'Rar!\x1a\x07': {'ext': ['.rar'], 'mime': 'application/x-rar-compressed', 'category': FileCategory.ARCHIVE},
    b'7z\xBC\xAF\x27\x1C': {'ext': ['.7z'], 'mime': 'application/x-7z-compressed', 'category': FileCategory.ARCHIVE},

    # Audio
    b'ID3': {'ext': ['.mp3'], 'mime': 'audio/mpeg', 'category': FileCategory.AUDIO},
    b'\xFF\xFB': {'ext': ['.mp3'], 'mime': 'audio/mpeg', 'category': FileCategory.AUDIO},
    b'RIFF': {'ext': ['.wav'], 'mime': 'audio/wav', 'category': FileCategory.AUDIO},  # Needs WAVE check

    # Video
    b'\x00\x00\x00\x18ftypmp42': {'ext': ['.mp4'], 'mime': 'video/mp4', 'category': FileCategory.VIDEO},
    b'\x00\x00\x00\x1Cftypmp42': {'ext': ['.mp4'], 'mime': 'video/mp4', 'category': FileCategory.VIDEO},
}


# Malware/executable signatures (blacklist)
DANGEROUS_SIGNATURES = [
    b'MZ',  # DOS/Windows executable
    b'\x7FELF',  # Linux executable
    b'#!',  # Shell script
    b'\xCA\xFE\xBA\xBE',  # Java class file
    b'\xFE\xED\xFA',  # Mach-O binary (macOS)
]


# File size limits by category (bytes)
SIZE_LIMITS = {
    FileCategory.IMAGE: 10 * 1024 * 1024,  # 10MB
    FileCategory.DOCUMENT: 20 * 1024 * 1024,  # 20MB
    FileCategory.SPREADSHEET: 20 * 1024 * 1024,  # 20MB
    FileCategory.MEDICAL: 50 * 1024 * 1024,  # 50MB (DICOM images can be large)
    FileCategory.AUDIO: 15 * 1024 * 1024,  # 15MB
    FileCategory.VIDEO: 100 * 1024 * 1024,  # 100MB
    FileCategory.ARCHIVE: 50 * 1024 * 1024,  # 50MB
    FileCategory.OTHER: 10 * 1024 * 1024,  # 10MB
}


# Allowed extensions by category
ALLOWED_EXTENSIONS = {
    FileCategory.IMAGE: ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.heic'],
    FileCategory.DOCUMENT: ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'],
    FileCategory.SPREADSHEET: ['.xls', '.xlsx', '.csv'],
    FileCategory.MEDICAL: ['.dcm', '.dicom', '.xml', '.pdf'],
    FileCategory.AUDIO: ['.mp3', '.wav', '.ogg', '.flac', '.aac'],
    FileCategory.VIDEO: ['.mp4', '.avi', '.mov', '.webm'],
    FileCategory.ARCHIVE: ['.zip', '.rar', '.7z'],
    FileCategory.OTHER: [],
}


def detect_file_type_by_magic(content: bytes, max_bytes: int = 512) -> Optional[Dict]:
    """
    Detect file type by magic number (file signature)

    Args:
        content: File content bytes
        max_bytes: Maximum bytes to read for detection

    Returns:
        Dict with file info or None if not recognized
    """
    # Read first bytes
    header = content[:max_bytes]

    # Check each magic number
    for magic, info in MAGIC_NUMBERS.items():
        if header.startswith(magic):
            return info

        # Special case for ftyp-based formats (HEIC, MP4)
        if magic.startswith(b'ftyp') and b'ftyp' in header[:20]:
            if magic in header[:20]:
                return info

        # Special case for WEBP
        if magic == b'RIFF' and b'WEBP' in header[:20]:
            return {'ext': ['.webp'], 'mime': 'image/webp', 'category': FileCategory.IMAGE}

        # Special case for WAV
        if magic == b'RIFF' and b'WAVE' in header[:20]:
            return {'ext': ['.wav'], 'mime': 'audio/wav', 'category': FileCategory.AUDIO}

        # Special case for DICOM
        if b'DICM' in header[:132]:  # DICOM magic number can be at offset 128
            return MAGIC_NUMBERS[b'DICM']

    return None


def detect_malware_signature(content: bytes) -> bool:
    """
    Check if file contains dangerous/executable signatures

    Args:
        content: File content bytes

    Returns:
        True if malware signature detected
    """
    header = content[:512]

    for signature in DANGEROUS_SIGNATURES:
        if header.startswith(signature):
            logger.warning(f"[File Validator] Dangerous signature detected: {signature.hex()}")
            return True

    return False


def validate_file_size(file_size: int, category: FileCategory) -> bool:
    """
    Validate file size against category limits

    Args:
        file_size: File size in bytes
        category: File category

    Returns:
        True if size is within limits
    """
    limit = SIZE_LIMITS.get(category, SIZE_LIMITS[FileCategory.OTHER])

    if file_size > limit:
        logger.warning(f"[File Validator] File size {file_size} exceeds limit {limit} for category {category}")
        return False

    return True


def validate_extension(filename: str, category: FileCategory) -> bool:
    """
    Validate file extension against category whitelist

    Args:
        filename: File name
        category: File category

    Returns:
        True if extension is allowed
    """
    ext = Path(filename).suffix.lower()
    allowed = ALLOWED_EXTENSIONS.get(category, [])

    if ext not in allowed:
        logger.warning(f"[File Validator] Extension {ext} not allowed for category {category}")
        return False

    return True


async def validate_upload_file(
    upload_file: UploadFile,
    expected_category: Optional[FileCategory] = None,
    max_size: Optional[int] = None
) -> Tuple[bool, str, Optional[Dict]]:
    """
    Comprehensive file validation

    Args:
        upload_file: FastAPI UploadFile object
        expected_category: Expected file category (optional)
        max_size: Custom max size in bytes (optional)

    Returns:
        Tuple of (is_valid, error_message, file_info)
    """
    try:
        # Read file content
        content = await upload_file.read()
        file_size = len(content)

        # Reset file pointer for later use
        await upload_file.seek(0)

        # 1. Check for malware signatures
        if detect_malware_signature(content):
            return False, "File contains suspicious executable signatures", None

        # 2. Detect file type by magic number
        file_info = detect_file_type_by_magic(content)

        if not file_info:
            logger.warning(f"[File Validator] Unknown file type for {upload_file.filename}")
            return False, "Unknown or unsupported file type", None

        category = file_info['category']
        detected_ext = file_info['ext'][0]

        # 3. Validate expected category
        if expected_category and category != expected_category:
            return False, f"File type mismatch: expected {expected_category}, got {category}", None

        # 4. Validate extension matches magic number
        actual_ext = Path(upload_file.filename or "").suffix.lower()

        if actual_ext not in file_info['ext']:
            logger.warning(f"[File Validator] Extension mismatch: {actual_ext} vs {file_info['ext']}")
            return False, f"File extension {actual_ext} does not match file content {detected_ext}", None

        # 5. Validate file size
        size_limit = max_size or SIZE_LIMITS.get(category, SIZE_LIMITS[FileCategory.OTHER])

        if file_size > size_limit:
            return False, f"File size {file_size} bytes exceeds limit {size_limit} bytes", None

        # 6. Additional validation for specific types
        if category == FileCategory.IMAGE:
            # Additional image validation can be added here
            pass

        elif category == FileCategory.MEDICAL:
            # Additional medical file validation
            pass

        # All validations passed
        logger.info(f"[File Validator] File validated: {upload_file.filename} ({category}, {file_size} bytes)")

        return True, "", file_info

    except Exception as e:
        logger.error(f"[File Validator] Validation error: {str(e)}")
        return False, f"Validation error: {str(e)}", None


async def validate_upload_file_strict(
    upload_file: UploadFile,
    expected_category: FileCategory,
    max_size: Optional[int] = None
) -> Dict:
    """
    Strict file validation with HTTPException on failure

    Args:
        upload_file: FastAPI UploadFile object
        expected_category: Expected file category (required)
        max_size: Custom max size in bytes (optional)

    Returns:
        File info dict

    Raises:
        HTTPException if validation fails
    """
    is_valid, error_msg, file_info = await validate_upload_file(
        upload_file,
        expected_category=expected_category,
        max_size=max_size
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File validation failed: {error_msg}"
        )

    return file_info


def get_allowed_extensions(category: FileCategory) -> List[str]:
    """Get list of allowed extensions for a category"""
    return ALLOWED_EXTENSIONS.get(category, [])


def get_size_limit(category: FileCategory) -> int:
    """Get size limit for a category"""
    return SIZE_LIMITS.get(category, SIZE_LIMITS[FileCategory.OTHER])
