import { useEffect, useState } from 'react';

/**
 * Hook для безопасного управления Blob URLs.
 * Автоматически очищает URL при размонтировании компонента.
 *
 * @example
 * function ImagePreview({ file }: { file: File | Blob | null }) {
 *   const blobURL = useBlobURL(file);
 *   return <img src={blobURL ?? undefined} alt="Preview" />;
 * }
 */
export function useBlobURL(file: File | Blob | null | undefined): string | null {
  const [blobURL, setBlobURL] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setBlobURL(null);
      return;
    }

    // Создаём blob URL
    const url = URL.createObjectURL(file);
    setBlobURL(url);

    // Cleanup функция — освобождаем память при размонтировании
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file]);

  return blobURL;
}

/**
 * Hook для управления массивом Blob URLs.
 * Полезно для галерей изображений.
 *
 * @example
 * function Gallery({ files }: { files: File[] }) {
 *   const urls = useBlobURLs(files);
 *   return urls.map((url, i) => <img key={i} src={url} />);
 * }
 */
export function useBlobURLs(
  files: ReadonlyArray<File | Blob> | null | undefined,
): string[] {
  const [blobURLs, setBlobURLs] = useState<string[]>([]);

  useEffect(() => {
    if (!files || files.length === 0) {
      setBlobURLs([]);
      return;
    }

    // Создаём URLs для всех файлов
    const urls = files.map((file) => URL.createObjectURL(file));
    setBlobURLs(urls);

    // Cleanup — освобождаем все URLs
    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [files]);

  return blobURLs;
}

export interface ControlledBlobURL {
  url: string | null;
  revoke: () => void;
}

/**
 * Hook с контролем над lifecycle blob URL.
 * Возвращает URL и функцию для ручной очистки.
 *
 * @example
 * function Download({ file }: { file: File | null }) {
 *   const { url, revoke } = useControlledBlobURL(file);
 *
 *   const handleDownload = () => {
 *     if (!url) return;
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
export function useControlledBlobURL(
  file: File | Blob | null | undefined,
): ControlledBlobURL {
  const [url, setUrl] = useState<string | null>(null);

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

  const revoke = (): void => {
    if (url) {
      URL.revokeObjectURL(url);
      setUrl(null);
    }
  };

  return { url, revoke };
}

export default useBlobURL;
