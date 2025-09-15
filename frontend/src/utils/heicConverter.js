/**
 * HEIC → JPEG конвертация на клиенте
 * Использует Service Worker для фоновой конвертации
 */

/**
 * Проверяет, является ли файл HEIC форматом
 * @param {File} file - Файл для проверки
 * @returns {boolean}
 */
export function isHEICFile(file) {
  if (!file) return false;
  
  // Проверяем по MIME типу
  if (file.type === 'image/heic' || file.type === 'image/heif') {
    return true;
  }
  
  // Проверяем по расширению
  const fileName = file.name.toLowerCase();
  return fileName.endsWith('.heic') || fileName.endsWith('.heif');
}

/**
 * Конвертирует HEIC файл в JPEG через Service Worker
 * @param {File} heicFile - HEIC файл
 * @param {number} quality - Качество JPEG (0.1 - 1.0)
 * @returns {Promise<File>} - Конвертированный JPEG файл
 */
export async function convertHEICToJPEG(heicFile, quality = 0.8) {
  try {
    // Проверяем поддержку Service Worker
    if (!('serviceWorker' in navigator)) {
      throw new Error('Service Worker не поддерживается');
    }
    
    const registration = await navigator.serviceWorker.ready;
    
    if (!registration.active) {
      throw new Error('Service Worker не активен');
    }
    
    // Создаем MessageChannel для двусторонней связи
    const messageChannel = new MessageChannel();
    
    return new Promise((resolve, reject) => {
      // Настраиваем обработчик ответа
      messageChannel.port1.onmessage = (event) => {
        const { success, convertedFile, error } = event.data;
        
        if (success) {
          // Создаем новый File объект из Blob
          const jpegFile = new File(
            [convertedFile], 
            heicFile.name.replace(/\.(heic|heif)$/i, '.jpg'),
            { 
              type: 'image/jpeg',
              lastModified: Date.now()
            }
          );
          
          resolve(jpegFile);
        } else {
          reject(new Error(error || 'Ошибка конвертации'));
        }
      };
      
      // Отправляем файл в Service Worker
      registration.active.postMessage({
        type: 'CONVERT_HEIC',
        file: heicFile,
        quality
      }, [messageChannel.port2]);
    });
    
  } catch (error) {
    console.error('HEIC conversion error:', error);
    
    // Fallback: используем heic2any библиотеку напрямую
    return await convertHEICFallback(heicFile, quality);
  }
}

/**
 * Fallback конвертация через heic2any библиотеку
 * @param {File} heicFile - HEIC файл
 * @param {number} quality - Качество JPEG
 * @returns {Promise<File>} - Конвертированный файл
 */
async function convertHEICFallback(heicFile, quality = 0.8) {
  try {
    // Динамически импортируем heic2any
    const heic2any = (await import('heic2any')).default;
    
    const jpegBlob = await heic2any({
      blob: heicFile,
      toType: 'image/jpeg',
      quality
    });
    
    // Создаем File из Blob
    const jpegFile = new File(
      [jpegBlob], 
      heicFile.name.replace(/\.(heic|heif)$/i, '.jpg'),
      { 
        type: 'image/jpeg',
        lastModified: Date.now()
      }
    );
    
    return jpegFile;
    
  } catch (error) {
    console.error('HEIC fallback conversion failed:', error);
    throw new Error('Не удалось конвертировать HEIC файл');
  }
}

/**
 * Конвертирует множественные файлы
 * @param {FileList|File[]} files - Список файлов
 * @param {number} quality - Качество JPEG
 * @returns {Promise<File[]>} - Массив конвертированных файлов
 */
export async function convertMultipleFiles(files, quality = 0.8) {
  const fileArray = Array.from(files);
  const convertedFiles = [];
  
  for (const file of fileArray) {
    try {
      if (isHEICFile(file)) {
        console.log(`Converting HEIC file: ${file.name}`);
        const convertedFile = await convertHEICToJPEG(file, quality);
        convertedFiles.push(convertedFile);
      } else {
        // Не HEIC файл, добавляем как есть
        convertedFiles.push(file);
      }
    } catch (error) {
      console.error(`Failed to convert ${file.name}:`, error);
      // В случае ошибки, добавляем оригинальный файл
      convertedFiles.push(file);
    }
  }
  
  return convertedFiles;
}

/**
 * Получает информацию о файле изображения
 * @param {File} file - Файл изображения
 * @returns {Promise<Object>} - Информация о файле
 */
export async function getImageInfo(file) {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith('image/')) {
      reject(new Error('Файл не является изображением'));
      return;
    }
    
    const img = new Image();
    const url = URL.createObjectURL(file);
    
    img.onload = () => {
      const info = {
        width: img.naturalWidth,
        height: img.naturalHeight,
        size: file.size,
        type: file.type,
        name: file.name,
        aspectRatio: img.naturalWidth / img.naturalHeight,
        megapixels: (img.naturalWidth * img.naturalHeight / 1000000).toFixed(1)
      };
      
      URL.revokeObjectURL(url);
      resolve(info);
    };
    
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Не удалось загрузить изображение'));
    };
    
    img.src = url;
  });
}

/**
 * Создает превью изображения
 * @param {File} file - Файл изображения
 * @param {number} maxWidth - Максимальная ширина превью
 * @param {number} maxHeight - Максимальная высота превью
 * @returns {Promise<string>} - Data URL превью
 */
export async function createImagePreview(file, maxWidth = 300, maxHeight = 300) {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith('image/')) {
      reject(new Error('Файл не является изображением'));
      return;
    }
    
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();
    const url = URL.createObjectURL(file);
    
    img.onload = () => {
      // Вычисляем размеры превью с сохранением пропорций
      let { width, height } = img;
      
      if (width > height) {
        if (width > maxWidth) {
          height = height * (maxWidth / width);
          width = maxWidth;
        }
      } else {
        if (height > maxHeight) {
          width = width * (maxHeight / height);
          height = maxHeight;
        }
      }
      
      canvas.width = width;
      canvas.height = height;
      
      // Рисуем изображение на canvas
      ctx.drawImage(img, 0, 0, width, height);
      
      // Получаем data URL
      const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
      
      URL.revokeObjectURL(url);
      resolve(dataUrl);
    };
    
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Не удалось создать превью'));
    };
    
    img.src = url;
  });
}

/**
 * Проверяет поддержку HEIC в браузере
 * @returns {Promise<boolean>}
 */
export async function checkHEICSupport() {
  try {
    // Создаем тестовый HEIC data URL (минимальный)
    const testHEIC = 'data:image/heic;base64,AAAAFGZ0eXBoZWljAAAAAG1pZjFoZWljbWlhZgAAABhtZXRhAAAAAAAAACFoZGxyAAAAAAAAAABtZGlyAAAAAAAAAAAAAAAAAAAAAAA=';
    
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(true);
      img.onerror = () => resolve(false);
      img.src = testHEIC;
      
      // Timeout через 1 секунду
      setTimeout(() => resolve(false), 1000);
    });
  } catch (error) {
    return false;
  }
}

/**
 * Обработчик для input[type="file"] с автоконвертацией HEIC
 * @param {Event} event - Event от input
 * @param {Function} callback - Callback с конвертированными файлами
 */
export async function handleFileInputWithHEICConversion(event, callback) {
  const files = event.target.files;
  if (!files || files.length === 0) return;
  
  try {
    console.log('Processing files with HEIC conversion...');
    const convertedFiles = await convertMultipleFiles(files);
    
    // Вызываем callback с конвертированными файлами
    callback(convertedFiles);
    
  } catch (error) {
    console.error('File processing error:', error);
    // В случае ошибки возвращаем оригинальные файлы
    callback(Array.from(files));
  }
}
