/**
 * DermaVisitGallery — галерея фото текущего визита (план аудита дерматологии, пункт 8).
 *
 * Единственный источник фото — файловый API `/files`:
 * - при открытии загружает список фото дерматологического осмотра визита
 *   (GET /files/?patient_id&visit_id): доменный предикат — теги
 *   dermatology+photo и file_type=image — применяется СЕРВЕРОМ в derma-ветке
 *   списка; клиентский MIME-фильтр ниже — вторая линия, а не граница;
 * - пагинация по серверному контракту (page/total ответа FileList):
 *   первая страница загружается при открытии, следующие — кнопкой
 *   «Показать ещё» без дублей (follow-up P2-2: визит с числом фото
 *   больше размера страницы больше не теряет старые фото);
 * - приватное превью получает авторизованным запросом (GET /files/{id}/preview, blob)
 *   с ограниченной параллельностью и независимыми отказами (DERMAGALLERY-FE-007);
 * - временные objectURL освобождаются при размонтировании и смене пациента/визита;
 * - категории «осмотр»/«до»/«после» хранятся в существующих тегах файла
 *   (dermatology,photo,examination|before|after);
 * - псевдозагрузки File/blob: в JSON ЭМК нет — галерея не пишет в specialty_data.
 *
 * Инварианты контекста (аудит 3892: DERMAGALLERY-FE-001..007, DERMAAI-FE-001/002/004/005):
 * - смена пациента/визита СИНХРОННО очищает видимое состояние (фото, total,
 *   страницу, анализ AI, подтверждение удаления) — до разрешения нового GET
 *   старые карточки и действия недоступны (DERMAGALLERY-FE-001);
 * - асинхронные действия (upload/delete/AI) захватывают контекст и не
 *   перезагружают/не применяют результат после смены контекста (FE-002, DERMAAI-FE-001);
 * - пагинация доступна и в пустой локально категории (FE-004), состояние
 *   loadMore сбрасывается при смене контекста (FE-003), кнопка «Показать ещё»
 *   честно отключается во время любой загрузки (FE-007);
 * - RETRO-3942-01 (post-merge review #3944): действительность превью
 *   определяется контекстом и поколением списка, а НЕ идентификатором
 *   постраничного запроса — аппенд страницы 2 больше не отменяет ожидающие
 *   превью страницы 1: карточки прежних страниц получают свои blob-URL,
 *   когда ответы приходят;
 * - частично успешная загрузка перечитывает список и честно сообщает о
 *   частичном результате (FE-005);
 * - удаление — двухшаговое подтверждение без запроса к серверу на первом шаге (FE-006);
 * - подсказка AI привязана к файлу и контексту: канонический status='error'
 *   внутри HTTP 200 — ошибка, а не успех (DERMAAI-FE-002); анализ удалённого
 *   файла не показывается и не «воскрешает» поздний ответ (DERMAAI-FE-004);
 *   панель всегда называет фото-источник (DERMAAI-FE-005).
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
  // Серверный доменный предикат гарантирует теги dermatology+photo, но не
  // всегда тег категории: файлы без категории (например, помеченные через
  // API без examination/before/after) считаются фото осмотра — это фото
  // визита, а не снимки процедур «до/после».
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
/** Ограниченная параллельность приватных превью (DERMAGALLERY-FE-007). */
const PREVIEW_CONCURRENCY = 4;

export function DermaVisitGallery({ patientId, visitId, disabled = false }: DermaVisitGalleryProps) {
  const { t: rawT } = useTranslation();
  const t = rawT as (key: string, options?: Record<string, unknown>) => string;
  const [photos, setPhotos] = useState<VisitPhoto[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  // Пагинация по серверному контракту FileList: total — счётчик доменного
  // запроса (те же предикаты, что и список), page — текущая загруженная
  // страница. Кнопка «Показать ещё» появляется, когда загружено меньше total.
  const [totalFiles, setTotalFiles] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [activeCategory, setActiveCategory] = useState<DermaPhotoCategory>('examination');
  const [analysis, setAnalysis] = useState<SkinFileAnalysisState | null>(null);
  // Двухшаговое удаление (DERMAGALLERY-FE-006): первый клик только «взводит»
  // подтверждение; DELETE уходит со второго, явного.
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const objectUrlsRef = useRef<Set<string>>(new Set());
  // RETRO-3942-01 (post-merge review #3944): три независимых счётчика вместо
  // одного общего seq.
  //  - contextEpoch — смена пациента/визита (или размонтирование): любая
  //    асинхронная работа прошлого контекста недействительна целиком;
  //  - listEpoch — поколение списка: полный перезапуск (loadGallery) строит
  //    список заново; аппенд «Показать ещё» поколение НЕ меняет и потому
  //    больше не отменяет ожидающие превью предыдущих страниц;
  //  - requestSeq — идентификатор последнего запроса, владеет только
  //    флагами загрузки (loading/loadingMore/loadFailed), чтобы поздний
  //    finally не сбросил флаг более нового запроса.
  const contextEpochRef = useRef(0);
  const listEpochRef = useRef(0);
  const requestSeqRef = useRef(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  // Текущий контекст (пациент:визит) для стражей асинхронных действий
  // (DERMAGALLERY-FE-002, DERMAAI-FE-001): ref обновляется на каждом рендере
  // и сравнивается с контекстом, захваченным действием на старте.
  const contextKeyRef = useRef(`${patientId}:${visitId}`);
  contextKeyRef.current = `${patientId}:${visitId}`;
  // Зеркало списка фото для стражей «файл ещё существует» (DERMAAI-FE-004).
  const photosRef = useRef<VisitPhoto[]>([]);
  photosRef.current = photos;

  const releaseObjectUrls = useCallback(() => {
    for (const url of objectUrlsRef.current) {
      URL.revokeObjectURL(url);
    }
    objectUrlsRef.current = new Set();
  }, []);

  // Превью — отдельные авторизованные запросы для переданных файлов
  // (приватные файлы недоступны по прямому URL без заголовков авторизации).
  // RETRO-3942-01: действительность превью определяется КОНТЕКСТОМ и
  // поколением списка (установкой карточки по id файла), а не идентификатором
  // постраничного запроса: загрузка страницы 2 (апенд того же списка) больше
  // не инвалидирует ожидающие превью страницы 1 — их карточки получают
  // свои blob-URL, когда ответы приходят.
  // Запросы идут ограниченными пачками (DERMAGALLERY-FE-007): один зависший
  // или упавший запрос не блокирует остальные превью своей пачки, а отказ
  // одного файла оставляет остальные карточки живыми.
  const attachPreviews = useCallback(async (files: StoredFile[], contextEpoch: number, listEpoch: number) => {
    for (let offset = 0; offset < files.length; offset += PREVIEW_CONCURRENCY) {
      if (contextEpoch !== contextEpochRef.current) return;
      if (listEpoch !== listEpochRef.current) return;
      const batch = files.slice(offset, offset + PREVIEW_CONCURRENCY);
      await Promise.allSettled(batch.map(async (file) => {
        try {
          const previewResponse = await api.get<Blob>(`/files/${file.id}/preview`, { responseType: 'blob' });
          if (contextEpoch !== contextEpochRef.current) return;
          if (listEpoch !== listEpochRef.current) return;
          const url = URL.createObjectURL(previewResponse.data);
          objectUrlsRef.current.add(url);
          setPhotos((prev) => prev.map((photo) => (photo.id === file.id ? { ...photo, previewUrl: url } : photo)));
        } catch (error) {
          // Превью недоступно — карточка файла остаётся с заглушкой.
          logger.warn('[DermaVisitGallery] preview failed', { fileId: file.id, errorType: (error as { name?: string })?.name });
        }
      }));
    }
  }, []);

  const loadGallery = useCallback(async () => {
    const requestSeq = ++requestSeqRef.current;
    // RETRO-3942-01: полный перезапуск — новое поколение списка: аппенды и
    // превью прошлых поколений недействительны (их файлы перезапрашиваются
    // заново), но загрузка следующей страницы поколения НЕ меняет.
    const listEpoch = ++listEpochRef.current;
    const contextEpoch = contextEpochRef.current;
    setLoading(true);
    setLoadFailed(false);
    // Смена контекста (или повторная загрузка) сбрасывает застрявший флаг
    // постраничной загрузки (DERMAGALLERY-FE-003): старый finally с устаревшим
    // seq не очистит его сам.
    setLoadingMore(false);
    try {
      const listResponse = await api.get<{ files?: StoredFile[]; total?: number } | StoredFile[]>('/files/', {
        params: { patient_id: patientId, visit_id: visitId, size: LIST_PAGE_SIZE, page: 1 },
      });
      if (contextEpoch !== contextEpochRef.current || listEpoch !== listEpochRef.current) return;
      const raw = listResponse.data;
      const files = Array.isArray(raw) ? raw : (raw?.files ?? []);
      const total = Array.isArray(raw) ? files.length : (raw?.total ?? files.length);
      // Вторая линия (не граница): сервер уже вернул только фото осмотра
      // (теги dermatology+photo, file_type=image); клиентский MIME-фильтр
      // страхует от нарушения контракта сервера.
      const imageFiles = files.filter((file) => String(file?.mime_type ?? '').startsWith('image/'));
      releaseObjectUrls();
      setPhotos(imageFiles.map((file) => ({
        id: file.id,
        category: dermaPhotoCategoryOf(file.tags, file.mime_type),
        previewUrl: null,
        title: file.title || file.filename || `#${file.id}`,
      })));
      setTotalFiles(total);
      setCurrentPage(1);
      // Превью не блокируют завершение загрузки списка (DERMAGALLERY-FE-007):
      // карточки и пагинация доступны сразу, превьи подтягиваются параллельно.
      void attachPreviews(imageFiles, contextEpoch, listEpoch);
    } catch (error) {
      if (contextEpoch === contextEpochRef.current && listEpoch === listEpochRef.current) {
        setLoadFailed(true);
        logger.error('[DermaVisitGallery] list failed:', error);
      }
    } finally {
      if (requestSeq === requestSeqRef.current) setLoading(false);
    }
  }, [patientId, visitId, releaseObjectUrls, attachPreviews]);

  // Следующая страница серверного контракта FileList (follow-up P2-2):
  // аппенд без дублей по id — прецедент dental PhotoArchive. Ошибка не
  // переводит галерею в error-состояние: уже показанные фото доступны,
  // кнопка остаётся для повторной попытки.
  const handleLoadMore = useCallback(async () => {
    if (loadingMore || loading) return;
    const nextPage = currentPage + 1;
    // RETRO-3942-01: аппенд того же списка — контекст и поколение списка
    // (listEpoch) НЕ меняются: ожидающие превью предыдущих страниц остаются
    // валидными и будут прикреплены, когда их ответы придут. requestSeq
    // забирает только владение флагом loadingMore.
    const requestSeq = ++requestSeqRef.current;
    const contextEpoch = contextEpochRef.current;
    const listEpoch = listEpochRef.current;
    setLoadingMore(true);
    try {
      const listResponse = await api.get<{ files?: StoredFile[]; total?: number } | StoredFile[]>('/files/', {
        params: { patient_id: patientId, visit_id: visitId, size: LIST_PAGE_SIZE, page: nextPage },
      });
      if (contextEpoch !== contextEpochRef.current || listEpoch !== listEpochRef.current) return;
      const raw = listResponse.data;
      const files = Array.isArray(raw) ? raw : (raw?.files ?? []);
      const total = Array.isArray(raw) ? files.length : (raw?.total ?? totalFiles);
      const imageFiles = files.filter((file) => String(file?.mime_type ?? '').startsWith('image/'));
      const loadedIds = new Set(photos.map((photo) => photo.id));
      const newFiles = imageFiles.filter((file) => !loadedIds.has(file.id));
      setPhotos((prev) => {
        const existingIds = new Set(prev.map((photo) => photo.id));
        return [...prev, ...newFiles
          .filter((file) => !existingIds.has(file.id))
          .map((file) => ({
            id: file.id,
            category: dermaPhotoCategoryOf(file.tags, file.mime_type),
            previewUrl: null,
            title: file.title || file.filename || `#${file.id}`,
          }))];
      });
      setTotalFiles(total);
      setCurrentPage(nextPage);
      void attachPreviews(newFiles, contextEpoch, listEpoch);
    } catch (error) {
      if (contextEpoch === contextEpochRef.current && listEpoch === listEpochRef.current) {
        logger.error('[DermaVisitGallery] load more failed:', error);
        notify.error(t('derma.derma_gallery_load_more_failed'));
      }
    } finally {
      if (requestSeq === requestSeqRef.current) setLoadingMore(false);
    }
  }, [currentPage, loading, loadingMore, totalFiles, photos, patientId, visitId, attachPreviews, t]);

  // Загрузка при открытии и при смене пациента/визита; очистка при уходе.
  // DERMAGALLERY-FE-001: смена контекста СИНХРОННО (до разрешения нового GET)
  // очищает видимое состояние — старые фото, метаданные, анализ AI и
  // «взведённое» удаление недоступны под новым визитом.
  useEffect(() => {
    setPhotos([]);
    setTotalFiles(0);
    setCurrentPage(1);
    setLoadingMore(false);
    setAnalysis(null);
    setConfirmDeleteId(null);
    setLoadFailed(false);
    loadGallery();
    return () => {
      // Смена контекста/размонтирование: прошлый контекст недействителен
      // целиком — включая его ожидающие превью (их blob-URL и так revoked).
      contextEpochRef.current += 1;
      requestSeqRef.current += 1;
      releaseObjectUrls();
    };
  }, [loadGallery, releaseObjectUrls]);

  // Загрузка файлов: пофайловые исходники, честный частичный результат
  // (DERMAGALLERY-FE-005) и страж контекста для отложенной перезагрузки
  // (DERMAGALLERY-FE-002): поздний ответ A не перечитывает список под B.
  const handleUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const actionContext = `${patientId}:${visitId}`;
    setUploading(true);
    let uploaded = 0;
    const failedNames: string[] = [];
    try {
      for (const rawFile of Array.from(files)) {
        try {
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
          uploaded += 1;
        } catch (error) {
          logger.error('[DermaVisitGallery] upload failed:', error, { file: rawFile.name });
          failedNames.push(rawFile.name);
        }
      }
    } finally {
      setUploading(false);
    }
    // DERMAGALLERY-FE-002: контекст сменился, пока шли POST'ы — не трогаем
    // список чужого визита (успешные файлы A уже сохранены на сервере; их
    // покажет перезагрузка при возврате к A).
    if (actionContext !== contextKeyRef.current) return;
    if (uploaded > 0) {
      await loadGallery();
      if (failedNames.length === 0) {
        notify.success(t('derma.derma_gallery_uploaded'));
      } else {
        notify.warning(t('derma.derma_gallery_upload_partial', { uploaded, failed: failedNames.length }));
      }
    } else {
      notify.error(t('derma.derma_gallery_upload_failed'));
    }
  }, [activeCategory, patientId, visitId, loadGallery, t]);

  // AI-анализ сохранённого фото — ТОЛЬКО по нажатию (пункт 9 плана аудита).
  // Ответ — подсказка: показывается в панели и никогда не записывается в ЭМК
  // (компонент не имеет onChange в specialty_data). Ошибка/503 не ломают галерею.
  // DERMAAI-FE-001: поздний ответ не применяется после смены контекста;
  // DERMAAI-FE-002: канонический status='error' внутри HTTP 200 — ошибка;
  // DERMAAI-FE-004: файл, удалённый пока запрос был в полёте, не получает
  // «воскрешённую» подсказку.
  const handleAnalyze = useCallback(async (photoId: number) => {
    const actionContext = `${patientId}:${visitId}`;
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
      if (actionContext !== contextKeyRef.current) return;
      const payload = response.data ?? {};
      const aiNotice = typeof payload.ai_notice === 'string' ? payload.ai_notice : '';
      if (payload.status === 'error') {
        setAnalysis({ fileId: photoId, status: 'error', aiNotice });
        return;
      }
      if (!photosRef.current.some((photo) => photo.id === photoId)) {
        // Файл удалён, пока ответ шёл: без подсказки и без панели-«призрака».
        setAnalysis(null);
        return;
      }
      const content = payload.data?.content;
      setAnalysis({
        fileId: photoId,
        status: 'done',
        suggestion: typeof content === 'string' && content.trim() ? content : '',
        aiNotice,
      });
    } catch (error) {
      logger.error('[DermaVisitGallery] AI analysis failed:', error);
      if (actionContext === contextKeyRef.current) {
        setAnalysis({ fileId: photoId, status: 'error' });
      }
    }
  }, [patientId, visitId]);

  // Удаление — только со второго, явного подтверждения (DERMAGALLERY-FE-006):
  // первый клик лишь взводит подтверждение и НЕ посылает DELETE.
  const handleDelete = useCallback(async (photoId: number) => {
    const actionContext = `${patientId}:${visitId}`;
    try {
      await api.delete(`/files/${photoId}`);
      // DERMAAI-FE-004: подсказка AI удалённого файла исчезает вместе с ним.
      setAnalysis((prev) => (prev && prev.fileId === photoId ? null : prev));
      // DERMAGALLERY-FE-002: контекст сменился, пока DELETE шёл — не
      // перечитываем список под чужим визитом.
      if (actionContext !== contextKeyRef.current) return;
      await loadGallery();
      notify.success(t('derma.derma_gallery_deleted'));
    } catch (error) {
      logger.error('[DermaVisitGallery] delete failed:', error);
      if (actionContext === contextKeyRef.current) {
        notify.error(t('derma.derma_gallery_delete_failed'));
      }
    }
  }, [patientId, visitId, loadGallery, t]);

  const visiblePhotos = photos.filter((photo) => photo.category === activeCategory);
  // DERMAAI-FE-005: панель подсказки всегда называет фото-источник и живёт
  // только пока файл существует в текущем списке.
  const analysisPhoto = analysis ? photos.find((photo) => photo.id === analysis.fileId) : undefined;

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
          <p>{photos.length === 0 ? t('derma.derma_gallery_empty') : t('derma.derma_gallery_empty_category')}</p>
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
                  (confirmDeleteId === photo.id ?
                    <span className="derma-gallery-delete-confirm" role="group" aria-label={t('derma.derma_gallery_delete_confirm')}>
                      <button
                        type="button"
                        className="derma-gallery-delete derma-gallery-delete-confirm-yes"
                        aria-label={t('derma.derma_gallery_delete_confirm_yes')}
                        title={t('derma.derma_gallery_delete_confirm')}
                        onClick={() => {
                          setConfirmDeleteId(null);
                          void handleDelete(photo.id);
                        }}>
                        <Trash2 size={14} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        className="derma-gallery-delete-cancel"
                        aria-label={t('derma.derma_gallery_delete_cancel')}
                        title={t('derma.derma_gallery_delete_cancel')}
                        onClick={() => setConfirmDeleteId(null)}>
                        <X size={14} aria-hidden="true" />
                      </button>
                    </span>
                    :
                    <button
                      type="button"
                      className="derma-gallery-delete"
                      aria-label={t('derma.derma_gallery_delete_aria', { category: t(`derma.derma_gallery_category_${photo.category}`) })}
                      title={t('derma.derma_gallery_delete_confirm')}
                      onClick={() => setConfirmDeleteId(photo.id)}>
                      <Trash2 size={14} aria-hidden="true" />
                    </button>)}
              </div>
            </div>
          ))}
        </div>}
      {/* Пагинация по серверному контракту FileList (follow-up P2-2):
          загружено меньше total — предложить следующую страницу.
          DERMAGALLERY-FE-004: кнопка доступна и когда в выбранной категории
          сейчас нет карточек (позже страницы лежат фото других категорий);
          DERMAGALLERY-FE-007: кнопка честно отключена на время любой загрузки. */}
      {!loadFailed && !loading && photos.length < totalFiles &&
        <button
          type="button"
          className="derma-gallery-load-more"
          onClick={() => void handleLoadMore()}
          disabled={disabled || loading || loadingMore}>
          {loadingMore ? t('derma.derma_gallery_loading') : t('derma.derma_gallery_load_more')}
        </button>}

      {/* Подсказка AI — только по нажатию, никогда не записывается в ЭМК (пункт 9).
          DERMAAI-FE-005: панель явно называет фото-источник подсказки. */}
      {analysis && analysisPhoto &&
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
          <p className="derma-gallery-analysis-source">
            {t('derma.derma_gallery_ai_source')}:{' '}
            <span className="derma-gallery-analysis-source-name">{analysisPhoto.title}</span>
          </p>
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
