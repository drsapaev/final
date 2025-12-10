/**
 * Валидатор файлов с проверкой magic numbers и MIME types
 * Защита от загрузки вредоносных файлов
 */
import logger from './logger';

/**
 * Разрешённые MIME types для медицинских файлов
 */
export const ALLOWED_MIME_TYPES = {
  images: [
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/gif',
    'image/heic',
    'image/heif',
    'image/webp',
    'image/bmp',
    'image/tiff'
  ],
  documents: [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // .docx
    'application/vnd.ms-word.document.macroEnabled.12', // .docm
    'text/plain'
  ],
  spreadsheets: [
    'text/csv',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', // .xlsx
    'application/vnd.ms-excel.sheet.macroEnabled.12' // .xlsm
  ],
  medical: [
    'text/xml',           // ECG
    'application/xml',
    'application/dicom',  // Medical imaging (DICOM)
    'application/zip'     // Архивы медицинских данных
  ]
};

/**
 * Magic numbers (сигнатуры файлов) для проверки
 * Первые байты файла определяют его реальный тип
 */
export const FILE_SIGNATURES = {
  // Images
  'image/jpeg': [
    'FFD8FFE0', // JPEG JFIF
    'FFD8FFE1', // JPEG EXIF
    'FFD8FFE2', // JPEG EXIF
    'FFD8FFE8'  // JPEG SPIFF
  ],
  'image/png': ['89504E47'],
  'image/gif': ['47494638'], // GIF87a or GIF89a
  'image/bmp': ['424D'],
  'image/webp': ['52494646'], // RIFF (needs WEBP at offset 8)
  'image/tiff': ['49492A00', '4D4D002A'],

  // Documents
  'application/pdf': ['25504446'], // %PDF
  'application/msword': ['D0CF11E0'], // DOC (OLE2)
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['504B0304'], // DOCX (ZIP)

  // Spreadsheets
  'text/csv': [], // CSV не имеет magic number
  'application/vnd.ms-excel': ['D0CF11E0'], // XLS (OLE2)
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['504B0304'], // XLSX (ZIP)

  // Medical
  'text/xml': ['3C3F786D6C'], // <?xml
  'application/xml': ['3C3F786D6C'],
  'application/dicom': ['4449434D'], // DICM at offset 128
  'application/zip': ['504B0304', '504B0506'] // ZIP
};

/**
 * Соответствие расширений и MIME types
 */
export const EXTENSION_TO_MIME = {
  // Images
  'jpg': 'image/jpeg',
  'jpeg': 'image/jpeg',
  'png': 'image/png',
  'gif': 'image/gif',
  'heic': 'image/heic',
  'heif': 'image/heif',
  'webp': 'image/webp',
  'bmp': 'image/bmp',
  'tiff': 'image/tiff',
  'tif': 'image/tiff',

  // Documents
  'pdf': 'application/pdf',
  'doc': 'application/msword',
  'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'txt': 'text/plain',

  // Spreadsheets
  'csv': 'text/csv',
  'xls': 'application/vnd.ms-excel',
  'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',

  // Medical
  'xml': 'text/xml',
  'dcm': 'application/dicom',
  'zip': 'application/zip'
};

/**
 * Чтение первых байтов файла для проверки сигнатуры
 * @param {File} file - Файл для чтения
 * @param {number} bytesToRead - Количество байтов для чтения
 * @returns {Promise<string>} Hex строка с сигнатурой
 */
async function readFileSignature(file, bytesToRead = 12) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = (e) => {
      const arr = new Uint8Array(e.target.result);
      const hex = Array.from(arr)
        .map(b => b.toString(16).padStart(2, '0').toUpperCase())
        .join('');
      resolve(hex);
    };

    reader.onerror = () => reject(new Error('Не удалось прочитать файл'));

    // Читаем первые байты
    const blob = file.slice(0, bytesToRead);
    reader.readAsArrayBuffer(blob);
  });
}

/**
 * Проверка соответствия расширения файла его MIME type
 * @param {string} filename - Имя файла
 * @param {string} mimeType - MIME type
 * @returns {boolean} true если соответствует
 */
function validateExtensionMatch(filename, mimeType) {
  const ext = filename.split('.').pop()?.toLowerCase();
  if (!ext) return false;

  const expectedMime = EXTENSION_TO_MIME[ext];
  if (!expectedMime) return false;

  return expectedMime === mimeType;
}

/**
 * Проверка magic number файла
 * @param {File} file - Файл для проверки
 * @returns {Promise<{valid: boolean, detectedType: string|null}>}
 */
async function validateMagicNumber(file) {
  try {
    const signature = await readFileSignature(file);

    // Проверяем все известные сигнатуры
    for (const [mimeType, signatures] of Object.entries(FILE_SIGNATURES)) {
      if (signatures.length === 0) continue; // Пропускаем типы без сигнатуры (CSV)

      for (const sig of signatures) {
        if (signature.startsWith(sig)) {
          return {
            valid: true,
            detectedType: mimeType
          };
        }
      }
    }

    // Специальная проверка для WEBP (сигнатура RIFF + WEBP на offset 8)
    if (signature.startsWith('52494646')) {
      const webpSignature = await readFileSignature(file, 16);
      if (webpSignature.substring(16, 24) === '57454250') { // WEBP
        return {
          valid: true,
          detectedType: 'image/webp'
        };
      }
    }

    // Специальная проверка для DICOM (DICM на offset 128)
    if (file.size >= 132) {
      const reader = new FileReader();
      const dicomCheck = await new Promise((resolve) => {
        reader.onload = (e) => {
          const arr = new Uint8Array(e.target.result);
          const dicomSig = Array.from(arr.slice(128, 132))
            .map(b => b.toString(16).padStart(2, '0').toUpperCase())
            .join('');
          resolve(dicomSig === '4449434D');
        };
        reader.readAsArrayBuffer(file.slice(0, 132));
      });

      if (dicomCheck) {
        return {
          valid: true,
          detectedType: 'application/dicom'
        };
      }
    }

    return {
      valid: false,
      detectedType: null
    };
  } catch (error) {
    logger.error('Error validating magic number:', error);
    return {
      valid: false,
      detectedType: null
    };
  }
}

/**
 * Основная функция валидации файла
 * @param {File} file - Файл для валидации
 * @param {Object} options - Опции валидации
 * @param {Array<string>} options.allowedCategories - Разрешённые категории ('images', 'documents', etc.)
 * @param {number} options.maxSize - Максимальный размер в байтах (по умолчанию 50MB)
 * @param {boolean} options.strictMagicNumber - Строгая проверка magic number (по умолчанию true)
 * @returns {Promise<{valid: boolean, errors: Array<string>, warnings: Array<string>}>}
 */
export async function validateFile(file, options = {}) {
  const {
    allowedCategories = ['images', 'documents'],
    maxSize = 50 * 1024 * 1024, // 50MB по умолчанию
    strictMagicNumber = true
  } = options;

  const errors = [];
  const warnings = [];

  // 1. Проверка размера файла
  if (file.size > maxSize) {
    errors.push(`Файл слишком большой. Максимальный размер: ${(maxSize / 1024 / 1024).toFixed(0)}MB`);
  }

  if (file.size === 0) {
    errors.push('Файл пустой');
  }

  // 2. Получить разрешённые MIME types
  const allowedTypes = allowedCategories.flatMap(cat =>
    ALLOWED_MIME_TYPES[cat] || []
  );

  if (allowedTypes.length === 0) {
    errors.push('Не указаны разрешённые типы файлов');
    return { valid: false, errors, warnings };
  }

  // 3. Проверка MIME type
  if (!allowedTypes.includes(file.type)) {
    errors.push(`Недопустимый тип файла: ${file.type || 'неизвестный'}. Разрешены: ${allowedCategories.join(', ')}`);
  }

  // 4. Проверка расширения файла
  const ext = file.name.split('.').pop()?.toLowerCase();
  if (!ext) {
    errors.push('Файл должен иметь расширение');
  } else {
    const expectedMime = EXTENSION_TO_MIME[ext];
    if (!expectedMime) {
      warnings.push(`Неизвестное расширение файла: .${ext}`);
    } else if (expectedMime !== file.type) {
      warnings.push(`Расширение .${ext} не соответствует MIME type ${file.type}`);
    }
  }

  // 5. Проверка magic number (сигнатуры файла)
  if (strictMagicNumber && file.type !== 'text/csv' && file.type !== 'text/plain') {
    const magicCheck = await validateMagicNumber(file);

    if (!magicCheck.valid) {
      errors.push('Содержимое файла не соответствует заявленному типу (неверная сигнатура файла)');
    } else if (magicCheck.detectedType !== file.type) {
      // Специальные случаи для совместимых типов
      const compatibleTypes = [
        ['text/xml', 'application/xml'],
        ['image/jpeg', 'image/jpg']
      ];

      const isCompatible = compatibleTypes.some(pair =>
        (pair.includes(file.type) && pair.includes(magicCheck.detectedType))
      );

      if (!isCompatible) {
        errors.push(
          `Реальный тип файла (${magicCheck.detectedType}) не соответствует заявленному (${file.type})`
        );
      }
    }
  }

  // 6. Дополнительные проверки для медицинских файлов
  if (allowedCategories.includes('medical')) {
    // Проверка что XML действительно содержит медицинские данные
    if (file.type === 'text/xml' || file.type === 'application/xml') {
      // TODO: Добавить проверку содержимого XML
      warnings.push('XML файлы требуют дополнительной валидации на сервере');
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings
  };
}

/**
 * Валидация множественных файлов
 * @param {Array<File>} files - Массив файлов
 * @param {Object} options - Опции валидации
 * @returns {Promise<{valid: boolean, results: Array<{file: File, validation: Object}>}>}
 */
export async function validateFiles(files, options = {}) {
  const results = await Promise.all(
    files.map(async (file) => ({
      file,
      validation: await validateFile(file, options)
    }))
  );

  const allValid = results.every(r => r.validation.valid);

  return {
    valid: allValid,
    results
  };
}

/**
 * Получить человекочитаемое описание разрешённых типов
 * @param {Array<string>} categories - Категории
 * @returns {string} Описание
 */
export function getAllowedTypesDescription(categories) {
  const descriptions = {
    images: 'изображения (JPEG, PNG, GIF, HEIC, WebP)',
    documents: 'документы (PDF, DOC, DOCX, TXT)',
    spreadsheets: 'таблицы (CSV, XLS, XLSX)',
    medical: 'медицинские файлы (XML, DICOM, ZIP)'
  };

  return categories.map(cat => descriptions[cat] || cat).join(', ');
}

export default validateFile;
