/**
 * DermaVisitGallery — галерея фото текущего визита (план аудита дерматологии, пункт 8).
 *
 * Единственный источник фото — файловый API `/files`:
 * - при открытии загружает список сохранённых файлов визита (GET /files/?patient_id&visit_id);
 * - приватное превью получает авторизованным запросом (GET /files/{id}/preview, blob);
 * - временные objectURL освобождаются при размонтировании и смене пациента/визита;
 * - категории «осмотр»/«до»/«после» хранятся в существующих тегах файла
 *   (dermatology,photo,examination|before|after);
 * - псевдозагрузки File/blob: в JSON ЭМК нет — галерея не пишет в specialty_data.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle, Image as ImageIcon, RefreshCw, Sparkles, Trash2, Upload, X } from 'lucide-react';
import { api } from '../../api/client';
import notify from '../../services/notify';
import { convertHEICToJPEG, isHEICFile } from '../../utils/heicConverter';
import { useTranslation } from '../../i18n/useTranslation';
import logger from '../../utils/logger';
import './DermaVisitGallery.css';

export type DermaPhotoCategory = 'examination' | 'before' | 'after';

export const DERMA_PHOTO_CATEGORIES: DermaPhotoCategory[] = ['examination', 'before', 'after'];

/** Тег категории внутри общего префикса dermatology,photo,<category>. */
export function dermaPhotoCategoryOf(tags: unknown, mimeType?: unknown): DermaPhotoCategory {
  const list = Array.isArray(tags) ? tags.map((tag) => String(tag)) : [];
  if (list.includes('before')) return 'before';
  if (list.includes('after')) return 'after';
  if (list.includes('examination')) return 'examination';
  // Файлы без тега категории (например, загруженные до аудита) считаются
  // фото осмотра — это фото визита, а не снимки процедур «до/после».
  void mimeType;
  return 'examination';
}

interface StoredFile {
  id: number;
  title?: string | null;
  filename?: string | null;
  mime_type?: string;
  tags?: string[] | null;
  created_at?: string;
}

export interface VisitPhoto {
  id: number;
  category: DermaPhotoCategory;
  previewUrl: string | null;
  title: string;
}

interface DermaVisitGalleryProps {
  patientId: number | string;
  visitId: number | string;
  disabled?: boolean;
}

interface SkinFileAnalysisState {
  fileId: number;
  status: 'loading' | 'done' | 'error';
  suggestion?: string;
  aiNotice?: string;
}

const LIST_PAGE_SIZE = 100;

export function DermaVisitGallery({ patientId, visitId, disabled = false }: DermaVisitGalleryProps) {
  const { t: rawT } = useTranslation();
  const t = rawT as (key: string, options?: Record<string, unknown>) => string;
  const [photos, setPhotos] = useState<VisitPhoto[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [activeCategory, setActiveCategory] = useState<DermaPhotoCategory>('examination');
  const [analysis, setAnalysis] = useState<SkinFileAnalysisState | null>(null);
  const objectUrlsRef = useRef<Set<string>>(new Set());
  const loadSeqRef = useRef(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const releaseObjectUrls = useCallback(() => {
    for (const url of objectUrlsRef.current) {
      URL.revokeObjectURL(url);
    }
    objectUrlsRef.current = new Set();
  }, []);

  const loadGallery = useCallback(async () => {
    const seq = ++loadSeqRef.current;
    setLoading(true);
    setLoadFailed(false);
    try {
      const listResponse = await api.get<{ files?: StoredFile[]; total?: number } | StoredFile[]>('/files/', {
        params: { patient_id: patientId, visit_id: visitId, size: LIST_PAGE_SIZE },
      });
      if (seq !== loadSeqRef.current) return;
      const raw = listResponse.data;
      const files = Array.isArray(raw) ? raw : (raw?.files ?? []);
      const imageFiles = files.filter((file) => String(file?.mime_type ?? '').startsWith('image/'));
      releaseObjectUrls();
      setPhotos(imageFiles.map((file) => ({
        id: file.id,
        category: dermaPhotoCategoryOf(file.tags, file.mime_type),
        previewUrl: null,
        title: file.title || file.filename || `#${file.id}`,
      })));
      // Превью — отдельные авторизованные запросы: приватные файлы недоступны
      // по прямому URL без заголовков авторизации.
      for (const file of imageFiles) {
        try {
          const previewResponse = await api.get<Blob>(`/files/${file.id}/preview`, { responseType: 'blob' });
          if (seq !== loadSeqRef.current) return;
          const url = URL.createObjectURL(previewResponse.data);
          objectUrlsRef.current.add(url);
          setPhotos((prev) => prev.map((photo) => (photo.id === file.id ? { ...photo, previewUrl: url } : photo)));
        } catch (error) {
          // Превью недоступно — карточка файла остаётся с заглушкой.
          logger.warn('[DermaVisitGallery] preview failed', { fileId: file.id, errorType: (error as { name?: string })?.name });
        }
      }
    } catch (error) {
      if (seq === loadSeqRef.current) {
        setLoadFailed(true);
        logger.error('[DermaVisitGallery] list failed:', error);
      }
    } finally {
      if (seq === loadSeqRef.current) setLoading(false);
    }
  }, [patientId, visitId, releaseObjectUrls]);

  // Загрузка при открытии и при смене пациента/визита; очистка при уходе.
  useEffect(() => {
    loadGallery();
    return () => {
      loadSeqRef.current += 1;
      releaseObjectUrls();
    };
  }, [loadGallery, releaseObjectUrls]);

  const handleUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      for (const rawFile of Array.from(files)) {
        let uploadFile: File | Blob = rawFile;
        if (isHEICFile(rawFile)) {
          uploadFile = await convertHEICToJPEG(rawFile, 0.9);
        }
        const formData = new FormData();
        formData.append('file', uploadFile);
        formData.append('file_type', 'image');
        formData.append('permission', 'private');
        formData.append('tags', `dermatology,photo,${activeCategory}`);
        formData.append('patient_id', String(patientId));
        formData.append('visit_id', String(visitId));
        await api.post('/files/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      }
      await loadGallery();
      notify.success(t('derma.derma_gallery_uploaded'));
    } catch (error) {
      logger.error('[DermaVisitGallery] upload failed:', error);
      notify.error(t('derma.derma_gallery_upload_failed'));
    } finally {
      setUploading(false);
    }
  }, [activeCategory, patientId, visitId, loadGallery, t]);

  // AI-анализ сохранённого фото — ТОЛЬКО по нажатию (пункт 9 плана аудита).
  // Ответ — подсказка: показывается в панели и никогда не записывается в ЭМК
  // (компонент не имеет onChange в specialty_data). Ошибка/503 не ломают галерею.
  const handleAnalyze = useCallback(async (photoId: number) => {
    setAnalysis({ fileId: photoId, status: 'loading' });
    try {
      const response = await api.post<{
        status?: string;
        data?: { content?: unknown };
        ai_notice?: string;
        requires_doctor_confirmation?: boolean;
        decision_boundary?: string;
      }>('/ai/v2/analyze-skin-file', {
        visit_id: visitId,
        file_id: photoId,
      });
      const payload = response.data ?? {};
      const content = payload.data?.content;
      setAnalysis({
        fileId: photoId,
        status: 'done',
        suggestion: typeof content === 'string' && content.trim() ? content : '',
        aiNotice: typeof payload.ai_notice === 'string' ? payload.ai_notice : '',
      });
    } catch (error) {
      logger.error('[DermaVisitGallery] AI analysis failed:', error);
      setAnalysis({ fileId: photoId, status: 'error' });
    }
  }, [visitId]);

  const handleDelete = useCallback(async (photoId: number) => {
    try {
      await api.delete(`/files/${photoId}`);
      await loadGallery();
      notify.success(t('derma.derma_gallery_deleted'));
    } catch (error) {
      logger.error('[DermaVisitGallery] delete failed:', error);
      notify.error(t('derma.derma_gallery_delete_failed'));
    }
  }, [loadGallery, t]);

  const visiblePhotos = photos.filter((photo) => photo.category === activeCategory);

  return (
    <section className="derma-gallery" aria-label={t('derma.derma_gallery_title')}>
      <div className="derma-gallery-header">
        <h4 className="derma-gallery-title">{t('derma.derma_gallery_title')}</h4>
        <div className="derma-gallery-actions">
          <div className="derma-gallery-categories" role="group" aria-label={t('derma.derma_gallery_categories_aria')}>
            {DERMA_PHOTO_CATEGORIES.map((category) => (
              <button
                key={category}
                type="button"
                className={`derma-gallery-chip${activeCategory === category ? ' derma-gallery-chip-active' : ''}`}
                aria-pressed={activeCategory === category}
                onClick={() => setActiveCategory(category)}
                disabled={disabled}>
                {t(`derma.derma_gallery_category_${category}`)}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="derma-gallery-upload-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || uploading}>
            <Upload size={16} aria-hidden="true" />
            {uploading ? t('derma.derma_gallery_uploading') : t('derma.derma_gallery_upload')}
          </button>
        </div>
      </div>
      <input
        ref={fileInputRef}
        type="file"
        className="derma-gallery-file-input"
        accept="image/jpeg,image/png,image/heic,image/heif,image/webp"
        multiple
        aria-label={t('derma.derma_gallery_upload_aria')}
        onChange={(event) => {
          void handleUpload(event.target.files);
          event.target.value = '';
        }}
        disabled={disabled || uploading} />

      {loadFailed ?
        <div className="derma-gallery-state" role="alert">
          <AlertCircle size={32} aria-hidden="true" />
          <p>{t('derma.derma_gallery_load_error')}</p>
          <button type="button" className="derma-gallery-upload-btn" onClick={() => void loadGallery()}>
            <RefreshCw size={14} aria-hidden="true" />
            {t('derma.derma_gallery_retry')}
          </button>
        </div>
        : loading && photos.length === 0 ?
        <div className="derma-gallery-state" aria-busy="true">
          <p>{t('derma.derma_gallery_loading')}</p>
        </div>
        : visiblePhotos.length === 0 ?
        <div className="derma-gallery-state">
          <ImageIcon size={32} aria-hidden="true" />
          <p>{t('derma.derma_gallery_empty')}</p>
        </div>
        :
        <div className="derma-gallery-grid">
          {visiblePhotos.map((photo) => (
            <div key={photo.id} className="derma-gallery-item">
              {photo.previewUrl ?
                <img
                  src={photo.previewUrl}
                  alt={t('derma.derma_gallery_photo_alt', { category: t(`derma.derma_gallery_category_${photo.category}`) })}
                  loading="lazy" /> :
                <div className="derma-gallery-item-placeholder" aria-label={t('derma.derma_gallery_photo_alt', { category: t(`derma.derma_gallery_category_${photo.category}`) })}>
                  <ImageIcon size={24} aria-hidden="true" />
                </div>}
              <div className="derma-gallery-item-actions">
                <button
                  type="button"
                  className="derma-gallery-analyze"
                  aria-label={t('derma.derma_gallery_ai_button_aria', { category: t(`derma.derma_gallery_category_${photo.category}`) })}
                  title={t('derma.derma_gallery_ai_button')}
                  disabled={disabled || (analysis?.status === 'loading')}
                  onClick={() => void handleAnalyze(photo.id)}>
                  <Sparkles size={14} aria-hidden="true" />
                </button>
                {!disabled &&
                  <button
                    type="button"
                    className="derma-gallery-delete"
                    aria-label={t('derma.derma_gallery_delete_aria', { category: t(`derma.derma_gallery_category_${photo.category}`) })}
                    onClick={() => void handleDelete(photo.id)}>
                    <Trash2 size={14} aria-hidden="true" />
                  </button>}
              </div>
            </div>
          ))}
        </div>}

      {/* Подсказка AI — только по нажатию, никогда не записывается в ЭМК (пункт 9) */}
      {analysis &&
        <div className="derma-gallery-analysis" role="status" aria-live="polite">
          <div className="derma-gallery-analysis-header">
            <span className="derma-gallery-analysis-title">{t('derma.derma_gallery_ai_result_title')}</span>
            <button
              type="button"
              className="derma-gallery-analysis-close"
              aria-label={t('derma.derma_gallery_ai_close')}
              onClick={() => setAnalysis(null)}>
              <X size={14} aria-hidden="true" />
            </button>
          </div>
          {analysis.status === 'loading' &&
            <p className="derma-gallery-analysis-hint">{t('derma.derma_gallery_ai_analyzing')}</p>}
          {analysis.status === 'error' &&
            <p className="derma-gallery-analysis-error" role="alert">{t('derma.derma_gallery_ai_error')}</p>}
          {analysis.status === 'done' &&
            <>
              <p className="derma-gallery-analysis-confirmation">{t('derma.derma_gallery_ai_confirmation')}</p>
              <pre className="derma-gallery-analysis-content">{analysis.suggestion || t('derma.derma_gallery_ai_empty')}</pre>
              {analysis.aiNotice &&
                <p className="derma-gallery-analysis-notice">{analysis.aiNotice}</p>}
            </>}
        </div>}
    </section>
  );
}

export default DermaVisitGallery;
