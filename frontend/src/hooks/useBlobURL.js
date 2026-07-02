import { useEffect, useState } from 'react';

/**
 * Hook для безопасного управления Blob URLs
 * Автоматически очищает URL при размонтировании компонента
 *
 * @param {File|Blob} file - Файл или Blob объект
 * @returns {string|null} URL для использования в src атрибуте
 *
 * @example
 * function ImagePreview({ file }) {
 *   const blobURL = useBlobURL(file);
 *   return <img src={blobURL} alt="Preview" />;
 * }
 */
export function useBlobURL(file) {
  const [blobURL, setBlobURL] = useState(null);

  useEffect(() => {
    if (!file) {
      setBlobURL(null);
      return;
    }

    // Создаём blob URL
    const url = URL.createObjectURL(file);
    setBlobURL(url);

    // Cleanup функция - освобождаем память при размонтировании
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file]);

  return blobURL;
}

/**
 * Hook для управления массивом Blob URLs
 * Полезно для галерей изображений
 *
 * @param {Array<File|Blob>} files - Массив файлов
 * @returns {Array<string>} Массив URLs
 *
 * @example
 * function Gallery({ files }) {
 *   const urls = useBlobURLs(files);
 *   return urls.map((url, i) => <img key={i} src={url} />);
 * }
 */
export function useBlobURLs(files) {
  const [blobURLs, setBlobURLs] = useState([]);

  useEffect(() => {
    if (!files || files.length === 0) {
      setBlobURLs([]);
      return;
    }

    // Создаём URLs для всех файлов
    const urls = files.map(file => URL.createObjectURL(file));
    setBlobURLs(urls);

    // Cleanup - освобождаем все URLs
    return () => {
      urls.forEach(url => URL.revokeObjectURL(url));
    };
  }, [files]);

  return blobURLs;
}

/**
 * Hook с контролем над lifecycle blob URL
 * Возвращает URL и функцию для ручной очистки
 *
 * @param {File|Blob} file - Файл или Blob объект
 * @returns {Object} { url, revoke } - URL и функция очистки
 *
 * @example
 * function Download({ file }) {
 *   const { url, revoke } = useControlledBlobURL(file);
 *
 *   const handleDownload = () => {
 *     const a = document.createElement('a');
 *     a.href = url;
 *     a.download = 'file.pdf';
 *     a.click();
 *     revoke(); // Очистка после скачивания
 *   };
 *
 *   return <button onClick={handleDownload}>Download</button>;
 * }
 */
export function useControlledBlobURL(file) {
  const [url, setUrl] = useState(null);

  useEffect(() => {
    if (!file) {
      setUrl(null);
      return;
    }

    const blobUrl = URL.createObjectURL(file);
    setUrl(blobUrl);

    // Auto cleanup при размонтировании
    return () => {
      URL.revokeObjectURL(blobUrl);
    };
  }, [file]);

  const revoke = () => {
    if (url) {
      URL.revokeObjectURL(url);
      setUrl(null);
    }
  };

  return { url, revoke };
}

export default useBlobURL;
