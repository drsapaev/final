import { useTranslation } from '../../i18n/useTranslation';
/**
 * ECG Viewer Component
 * Просмотр и анализ ЭКГ файлов
 * Согласно MASTER_TODO_LIST строка 247
 */
import { useEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Progress,
  Input } from '../ui/macos';
import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle,
  ClipboardCheck,
  Clock,
  CloudUpload,
  Download,
  Eye,
  HeartPulse,
  Trash2,
  X,
} from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import { api } from '../../api/client';
// R-11 / P-003 (UX audit): persist parsed ECG parameters to backend so the
// cardiologist panel's "history" tab can list prior ECGs without re-parsing
// the source file.
import notify from '../../services/notify';
import logger from '../../utils/logger';
import { getErrorMessage } from '../../utils/errorHandler';
import { parseECGFile, analyzeECGParameters, toFiniteNumber } from './ECGParser';


const iconSize = 16;

interface EcgParameters {
  heartRate?: number;
  prInterval?: number;
  qrsInterval?: number;
  qtInterval?: number;
  // ECGPARSER-FE-003 (audit 3886 round 25): the XML parser emits
  // `qtcInterval` (device-measured corrected QT) — declared here so the
  // structured persistence mapping can read it type-safely.
  qtcInterval?: number;
  qtCorrected?: number;
  rhythm?: string;
  stSegment?: string;
  tWave?: string;
  axis?: string | number;
  interpretation?: string;
  [key: string]: unknown;
}

interface EcgFile {
  id: string | number;
  name: string;
  type: string;
  size: number;
  uploadedAt: string;
  parameters: EcgParameters | null;
  [key: string]: unknown;
}

interface AnalysisResult {
  findings?: string[];
  interpretation?: string;
  recommendations?: string;
  error?: string;
  [key: string]: unknown;
}

// Styles object contains a mix of CSSProperties and one function (dropzone).
// `any` is used here intentionally to keep the mixed-type access ergonomic;
// explicit `any` is permitted under noImplicitAny (which only flags inferred
// any). See ADR-0014 for the rationale on legacy style objects.
const styles: Record<string, any> = {
  root: {
    display: 'grid',
    gap: 'var(--mac-spacing-4)',
  },
  sectionTitle: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--mac-spacing-2)',
    margin: '0 0 16px',
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-xl)',
    fontWeight: 'var(--mac-font-weight-semibold)',
  },
  dropzone: (active: boolean) => ({
    marginTop: 'var(--mac-spacing-4)',
    padding: 'var(--mac-spacing-6)',
    border: '2px dashed',
    borderColor: active ? 'var(--mac-accent-blue)' : 'var(--mac-border)',
    borderRadius: 'var(--mac-radius-lg)',
    background: active ? 'var(--mac-accent-bg)' : 'var(--mac-card-bg)',
    cursor: 'pointer',
    transition: 'border-color 160ms ease, background 160ms ease',
    textAlign: 'center',
  }),
  mutedText: {
    margin: 0,
    color: 'var(--mac-text-secondary)',
    fontSize: 'var(--mac-font-size-sm)',
  },
  caption: {
    margin: 0,
    color: 'var(--mac-text-secondary)',
    fontSize: 'var(--mac-font-size-xs)',
  },
  uploadProgress: {
    display: 'grid',
    gap: 'var(--mac-spacing-2)',
    marginTop: 'var(--mac-spacing-4)',
  },
  fileList: {
    display: 'grid',
    gap: 0,
    margin: 0,
    padding: 0,
    listStyle: 'none',
  },
  fileItem: {
    display: 'grid',
    gridTemplateColumns: '32px minmax(0, 1fr) auto',
    gap: 'var(--mac-spacing-3)',
    alignItems: 'start',
    padding: '14px 0',
    borderTop: '1px solid var(--mac-border)',
  },
  fileIcon: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '32px',
    height: '32px',
    borderRadius: '50%',
    color: 'var(--mac-danger, #ff3b30)',
    background: 'rgba(255, 59, 48, 0.08)',
  },
  fileHeader: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 'var(--mac-spacing-2)',
  },
  fileName: {
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-base)',
    fontWeight: 'var(--mac-font-weight-semibold)',
  },
  badgeRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 'var(--mac-spacing-2)',
    marginTop: 'var(--mac-spacing-2)',
  },
  criticalAlert: {
    marginTop: '10px',
  },
  criticalList: {
    display: 'grid',
    gap: '3px',
    marginTop: 'var(--mac-spacing-2)',
  },
  actionRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 'var(--mac-spacing-2)',
    justifyContent: 'flex-end',
  },
  iconButton: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '32px',
    height: '32px',
    borderRadius: 'var(--mac-radius-md)',
    border: '1px solid var(--mac-border)',
    background: 'var(--mac-card-bg)',
    color: 'var(--mac-text-primary)',
    cursor: 'pointer',
  },
  iconButtonDisabled: {
    opacity: 0.5,
    cursor: 'not-allowed',
  },
  analysisStatus: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--mac-spacing-3)',
  },
  analysisPanel: {
    display: 'grid',
    gap: 'var(--mac-spacing-4)',
    padding: 'var(--mac-spacing-4)',
    borderRadius: 'var(--mac-radius-lg)',
    border: '1px solid var(--mac-border)',
    background: 'var(--mac-bg-secondary)',
  },
  subsectionTitle: {
    margin: '0 0 8px',
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-sm)',
    fontWeight: 'var(--mac-font-weight-semibold)',
  },
  bodyText: {
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-sm)',
    lineHeight: 1.5,
  },
  dialogHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 'var(--mac-spacing-3)',
  },
  dialogTitle: {
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-xl)',
    fontWeight: 'var(--mac-font-weight-semibold)',
  },
  dialogContent: {
    maxHeight: '78vh',
    overflow: 'auto',
  },
  previewArea: {
    textAlign: 'center',
  },
  previewFrame: {
    width: '100%',
    height: '600px',
    border: '1px solid var(--mac-border)',
    borderRadius: 'var(--mac-radius-md)',
  },
  previewImage: {
    maxWidth: '100%',
    height: 'auto',
    borderRadius: 'var(--mac-radius-md)',
  },
  metricGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
    gap: 'var(--mac-spacing-3)',
  },
  metricCard: {
    padding: '14px',
    borderRadius: 'var(--mac-radius-lg)',
    border: '1px solid var(--mac-border)',
    background: 'var(--mac-card-bg)',
  },
  metricValue: {
    margin: '4px 0 0',
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-xl)',
    fontWeight: 'var(--mac-font-weight-semibold)',
  },
};

const ECGViewer = ({ visitId, patientId, onDataUpdate }: { visitId?: string | number; patientId?: string | number; onDataUpdate?: (data: unknown) => void }) => {
  const { t: tI18n } = useTranslation();
  const t = tI18n as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [ecgFiles, setEcgFiles] = useState<EcgFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<EcgFile | null>(null);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerBlobUrl, setViewerBlobUrl] = useState<string | null>(null);
  const [viewerLoading, setViewerLoading] = useState(false);
  const [viewerError, setViewerError] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [ecgParameters, setEcgParameters] = useState<EcgParameters | null>(null);

  // ECGVIEW-FE-002 (audit 3886 round 20): the viewer's local stores (file
  // list, selected preview, parsed parameters, AI analysis) belong to one
  // patient/visit context. When that context changes, the previous
  // patient's local files and previews must disappear and any in-flight
  // async work started for the old context must not commit into the new
  // one. Async callbacks capture the epoch at request start and compare it
  // against the live ref before every commit.
  const ownerKey = `${String(patientId ?? 'none')}|${String(visitId ?? 'none')}`;
  const ownerEpochRef = useRef(0);
  const ownerKeyRef = useRef(ownerKey);
  if (ownerKeyRef.current !== ownerKey) {
    ownerKeyRef.current = ownerKey;
    ownerEpochRef.current += 1;
  }
  const isStaleContext = (epochAtStart: number) => epochAtStart !== ownerEpochRef.current;

  useEffect(() => {
    // ECGVIEW-FE-002: reset every patient-scoped local store when the
    // owner context changes (the tab may stay mounted across selections —
    // EcgTab additionally keys this component by patient/visit).
    setEcgFiles([]);
    setSelectedFile(null);
    setAnalysisResult(null);
    setEcgParameters(null);
    setAnalyzing(false);
    setUploadProgress(0);
    setViewerError('');
    setViewerLoading(false);
    setViewerOpen(false);
    // viewerBlobUrl cleanup is handled by its own revoke effect below.
    setViewerBlobUrl((prev) => {
      if (prev) {
        window.URL.revokeObjectURL(prev);
      }
      return null;
    });
  }, [ownerKey]);

  useEffect(() => () => {
    if (viewerBlobUrl) {
      window.URL.revokeObjectURL(viewerBlobUrl);
    }
  }, [viewerBlobUrl]);

  // Поддерживаемые форматы
  // ECGVIEW-FE-003 (audit 3886 round 20): `.xml` is accepted regardless of
  // the MIME the browser reports (`text/xml`, `application/xml` or empty) —
  // the parser dispatches by extension, so the upload gate must too.
  const acceptedFormats = {
    'application/pdf': ['.pdf'],
    'text/xml': ['.xml'],
    'application/xml': ['.xml'],
    'application/scp': ['.scp'],
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
  };

  // ECGVIEW-FE-003: extension-driven dispatch — a valid `.xml` file must
  // reach the parser even when the browser tags it `application/xml` or
  // leaves the MIME empty. MIME-only gating silently skipped parsing.
  const shouldParseEcgFile = (file: File) => {
    const name = file.name.toLowerCase();
    return name.endsWith('.xml') || name.endsWith('.scp');
  };

  // Загрузка файлов
  const onDrop = async (acceptedFiles: File[]) => {
    for (const file of acceptedFiles) {
      const epochAtStart = ownerEpochRef.current;
      setUploadProgress(0);
      
      try {
        const formData = new FormData();
        // ECGVIEW-FE-001 (audit 3886 round 20): append the real binary File
        // part (with its filename). `String(file)` serialized to the literal
        // text "[object File]" and could never satisfy the backend's
        // `UploadFile` multipart contract.
        formData.append('file', file, file.name);
        formData.append('file_type', 'medical_record');
        formData.append('title', file.name);
        formData.append('tags', 'ecg,cardiology');
        if (patientId) {
          formData.append('patient_id', String(patientId));
        }
        if (visitId) {
          formData.append('visit_id', String(visitId));
        }
        
        const response = await api.post('/files/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (progressEvent: { loaded: number; total?: number }) => {
            const percentCompleted = Math.round(
              (progressEvent.loaded * 100) / (progressEvent.total ?? 1)
            );
            setUploadProgress(percentCompleted);
          },
        });
        
        // ECGVIEW-FE-002: the owner context may have changed while the
        // upload was in flight — do not surface the old patient's file.
        if (isStaleContext(epochAtStart)) return;
        
        const responseData = response.data as Record<string, unknown>;
        const newFile: EcgFile = {
          id: responseData.id as string | number,
          name: String(responseData.original_filename ?? file.name),
          type: String(responseData.mime_type ?? file.type),
          size: Number(responseData.file_size ?? file.size),
          uploadedAt: String(responseData.created_at ?? new Date().toISOString()),
          parameters: null,
        };
        
        setEcgFiles(prev => [...prev, newFile]);
        
        // Если это SCP/XML, пытаемся парсить (ECGVIEW-FE-003: по расширению)
        if (shouldParseEcgFile(file)) {
          await parseECGFileData(file, newFile);
        }

        if (isStaleContext(epochAtStart)) return;
        setUploadProgress(0);
        onDataUpdate?.(undefined);
        
      } catch (error) {
        if (isStaleContext(epochAtStart)) return;
        logger.error('Ошибка загрузки ЭКГ:', error);
        notify.error(getErrorMessage(error, t('cardio.cardio_ecg_upload_failed')));
        setUploadProgress(0);
      }
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: acceptedFormats,
    multiple: true,
  });

  // Парсинг ЭКГ файла
  const parseECGFileData = async (originalFile: File, uploadedFile: EcgFile) => {
    const epochAtStart = ownerEpochRef.current;
    try {
      // Сначала пробуем локальный парсинг
      const parseResult = await parseECGFile(originalFile) as Record<string, unknown>;
      
      if (parseResult.success && parseResult.parameters) {
        const analysis = analyzeECGParameters(parseResult.parameters as Record<string, unknown>);
        const enrichedParams = {
          ...(parseResult.parameters as Record<string, unknown>),
          ...analysis,
        };
        
        // ECGVIEW-FE-002: a parse that started under patient A must not
        // populate parameters or persist records after the context moved.
        if (isStaleContext(epochAtStart)) return;
        setEcgParameters(enrichedParams as EcgParameters);
        
        // Обновляем файл с параметрами
        setEcgFiles(prev => prev.map(f => 
          f.id === uploadedFile.id 
            ? { ...f, parameters: enrichedParams as EcgParameters }
            : f
        ));

        // R-11 / P-003 (UX audit): persist the parsed ECG parameters to
        // /cardio/ecg so the cardiologist panel's "history" tab can list
        // this ECG without re-parsing the source file. The source file is
        // already linked via file_id (uploaded through /files/upload).
        // We intentionally do NOT block the UI on this call — failure to
        // persist metadata should not prevent the doctor from continuing
        // to review the ECG; we surface a non-blocking toast instead.
        if (patientId) {
          try {
            // ECGPARSER-FE-003 (audit 3886 round 25): canonical typed
            // mapping for device measurements. The old payload read only
            // `qrs_duration ?? qrsDuration` and `qt_corrected ??
            // qtCorrected` — keys the parser never emits — so every parsed
            // QRS/QTc silently disappeared from the structured
            // cardio_ecg_records columns (the values survived only inside
            // the raw `parameters` dict). The mapping now reads the
            // parser's actual keys (`qrsInterval`, `qtcInterval`), keeps QT
            // and QTc distinct sources, and normalizes each measurement to
            // a finite number — never a fabricated one.
            const p = enrichedParams as Record<string, unknown>;
            const firstFiniteNumber = (...values: unknown[]): number | null => {
              for (const value of values) {
                const numeric = toFiniteNumber(value);
                if (numeric !== null) return numeric;
              }
              return null;
            };
            const axisValue = toFiniteNumber(p.axis);
            await api.post('/cardio/ecg', {
              patient_id: Number(patientId),
              visit_id: visitId ? Number(visitId) : null,
              file_id: uploadedFile.id,
              ecg_date: new Date().toISOString().slice(0, 10),
              heart_rate: firstFiniteNumber(p.heart_rate, p.heartRate),
              pr_interval: firstFiniteNumber(p.pr_interval, p.prInterval),
              qrs_duration: firstFiniteNumber(p.qrs_duration, p.qrsDuration, p.qrsInterval),
              qt_interval: firstFiniteNumber(p.qt_interval, p.qtInterval),
              qt_corrected: firstFiniteNumber(p.qt_corrected, p.qtCorrected, p.qtcInterval),
              rhythm: (p.rhythm as string | null | undefined) ?? null,
              st_segment: ((p.st_segment ?? p.stSegment) as string | null | undefined) ?? null,
              t_wave: ((p.t_wave ?? p.tWave) as string | null | undefined) ?? null,
              axis: axisValue === null ? null : String(axisValue),
              interpretation: (p.interpretation as string | null | undefined) ?? null,
              source: 'device',
              parameters: enrichedParams,
            });
            if (isStaleContext(epochAtStart)) return;
            notify.success(t('final.ecg_saved'));
          } catch (persistError) {
            if (isStaleContext(epochAtStart)) return;
            logger.error('Не удалось сохранить ЭКГ в истории пациента:', persistError);
            notify.error(t('final.ecg_not_saved'));
          }
        }
      } else if (parseResult.success === false) {
        // ECGPARSER-FE-001 (audit 3886 round 25): a failed parse must be a
        // visible negative state for the doctor. Previously the failure was
        // completely silent: an unrecognizable XML (or an unsupported
        // binary) stayed in the file list as an ordinary attachment while
        // nothing told the doctor that it was never analyzed and never
        // persisted to the structured ECG history. This branch also
        // finally surfaces the C-1 "SCP parsing not implemented" contract
        // of parseSCPFile. View-only formats (PDF: success:true with
        // parameters:null) intentionally stay silent.
        if (isStaleContext(epochAtStart)) return;
        logger.warn('Файл не распознан как ЭКГ:', {
          fileName: originalFile?.name,
          error: parseResult.error,
        });
        notify.warning(String(parseResult.error || t('final.ecg_parse_warning')));
      }
    } catch (error) {
      if (isStaleContext(epochAtStart)) return;
      logger.error('Ошибка парсинга ЭКГ:', error);
      notify.warning(t('final.ecg_parse_warning'));
    }
  };

  const openFileBlobUrl = async (fileId: string | number, mode = 'preview') => {
    const response = (await api.get(`/files/${fileId}/${mode}`, {
      responseType: 'blob',
    })) as import('axios').AxiosResponse<Record<string, unknown>>;

    return window.URL.createObjectURL(response.data as unknown as Blob);
  };

  const downloadFile = async (file: EcgFile) => {
    if (!file?.id) {
      return;
    }

    try {
      const blobUrl = await openFileBlobUrl(file.id, 'download');
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = file.name || 'ecg-file';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
    } catch (error) {
      logger.error('Ошибка скачивания файла:', error);
      notify.error(t('final.ecg_download_failed'));
    }
  };

  // AI анализ ЭКГ
  const analyzeECG = async (file: EcgFile) => {
    const epochAtStart = ownerEpochRef.current;
    setAnalyzing(true);
    setAnalysisResult(null);
    
    try {
      const response = (await api.post('/ai/ecg-interpret', {
        file_id: file.id,
        visit_id: visitId,
        patient_id: patientId,
      })) as import('axios').AxiosResponse<Record<string, unknown>>;
      
      // ECGVIEW-FE-002: an analysis for the previous patient's file must
      // not render under the new context.
      if (isStaleContext(epochAtStart)) return;
      setAnalysisResult(response.data as unknown as AnalysisResult);
      onDataUpdate?.(undefined);
      
    } catch (error) {
      if (isStaleContext(epochAtStart)) return;
      logger.error('Ошибка AI анализа:', error);
      setAnalysisResult({
        error: t('cardio.cardio_ecg_ai_failed'),
      });
    } finally {
      if (!isStaleContext(epochAtStart)) {
        setAnalyzing(false);
      }
    }
  };

  // Открыть просмотрщик
  const openViewer = async (file: EcgFile) => {
    const epochAtStart = ownerEpochRef.current;
    setSelectedFile(file);
    setViewerOpen(true);
    setViewerLoading(true);
    setViewerError('');

    if (file.parameters) {
      setEcgParameters(file.parameters);
    }

    try {
      if (viewerBlobUrl) {
        window.URL.revokeObjectURL(viewerBlobUrl);
      }

      const blobUrl = await openFileBlobUrl(file.id, 'preview');
      // ECGVIEW-FE-002: a preview fetched for the previous patient must
      // not open under the new context.
      if (isStaleContext(epochAtStart)) {
        window.URL.revokeObjectURL(blobUrl);
        return;
      }
      setViewerBlobUrl(blobUrl);
    } catch (error) {
      if (isStaleContext(epochAtStart)) return;
      logger.info('Предпросмотр файла недоступен, используем только скачивание:', error);
      setViewerBlobUrl(null);
      setViewerError(t('cardio.cardio_ecg_preview_unavailable'));
    } finally {
      if (!isStaleContext(epochAtStart)) {
        setViewerLoading(false);
      }
    }
  };

  const closeViewer = () => {
    if (viewerBlobUrl) {
      window.URL.revokeObjectURL(viewerBlobUrl);
    }
    setViewerBlobUrl(null);
    setViewerLoading(false);
    setViewerError('');
    setViewerOpen(false);
  };

  // Удалить файл
  const deleteFile = async (fileId: string | number) => {
    const epochAtStart = ownerEpochRef.current;
    try {
      await api.delete(`/files/${fileId}`);
      if (isStaleContext(epochAtStart)) return;
      setEcgFiles(prev => prev.filter(f => f.id !== fileId));
      onDataUpdate?.(undefined);
    } catch (error) {
      if (isStaleContext(epochAtStart)) return;
      logger.error('Ошибка удаления файла:', error);
      notify.error(t('final.ecg_delete_failed'));
    }
  };

  // Форматирование размера файла
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  // Определение критичных параметров
  const getCriticalParameters = (params: EcgParameters | null | undefined) => {
    const critical: Array<{ name: string; value: string }> = [];
    
    if (Number(params?.heartRate ?? 0) > 100) {
      critical.push({ name: t('cardio.cardio_ecg_critical_tachycardia'), value: t('cardio.cardio_ecg_bpm_value', { count: params?.heartRate ?? 0 }) });
    }
    if (Number(params?.heartRate ?? 0) < 60) {
      critical.push({ name: t('cardio.cardio_ecg_critical_bradycardia'), value: t('cardio.cardio_ecg_bpm_value', { count: params?.heartRate ?? 0 }) });
    }
    if (Number(params?.qtInterval ?? 0) > 450) {
      critical.push({ name: t('cardio.cardio_ecg_critical_qt_prolonged'), value: t('cardio.cardio_ecg_ms_value', { count: params?.qtInterval ?? 0 }) });
    }
    if (Number(params?.prInterval ?? 0) > 200) {
      critical.push({ name: t('cardio.cardio_ecg_critical_av_block'), value: t('cardio.cardio_ecg_ms_value', { count: params?.prInterval ?? 0 }) });
    }
    
    return critical;
  };

  return (
    <div style={styles.root}>
      <Card>
        <CardContent>
          <h3 style={styles.sectionTitle}>
            <Clock size={iconSize} aria-hidden="true" />
            {t('cardio.cardio_ecg_section_title')}
          </h3>

          <div {...getRootProps()} style={styles.dropzone(isDragActive)}>
            <input {...getInputProps() as Record<string, unknown>} />
            <CloudUpload size={48} color="var(--mac-text-secondary)" aria-hidden="true" />
            <p style={{ ...styles.mutedText, marginTop: 'var(--mac-spacing-2)' }}>
              {isDragActive
                ? t('cardio.cardio_ecg_drop_active')
                : t('cardio.cardio_ecg_drop_idle')}
            </p>
            <p style={{ ...styles.caption, marginTop: 'var(--mac-spacing-2)' }}>
              {t('cardio.cardio_ecg_formats_supported')}
            </p>
          </div>

          {uploadProgress > 0 && uploadProgress < 100 && (
            <div style={styles.uploadProgress}>
              <Progress variant="primary" value={uploadProgress} />
              <p style={styles.caption}>{t('cardio.cardio_ecg_uploading', { percent: uploadProgress })}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {ecgFiles.length > 0 && (
        <Card>
          <CardContent>
            <h3 style={styles.sectionTitle}>{t('cardio.cardio_ecg_uploaded_count', { count: ecgFiles.length })}</h3>

            <ul style={styles.fileList}>
              {ecgFiles.map((file) => {
                const criticalParams = file.parameters
                  ? getCriticalParameters(file.parameters)
                  : [];

                return (
                  <li key={file.id} style={styles.fileItem}>
                    <span style={styles.fileIcon} aria-hidden="true">
                      <HeartPulse size={18} />
                    </span>

                    <div>
                      <div style={styles.fileHeader}>
                        <p style={styles.fileName}>{file.name}</p>
                        {criticalParams.length > 0 && (
                          <Badge variant="warning" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                            <AlertTriangle style={{ width: 14, height: 14 }} />
                            {t('cardio.cardio_ecg_attention')}
                          </Badge>
                        )}
                      </div>

                      <p style={{ ...styles.caption, marginTop: 'var(--mac-spacing-1)' }}>
                        {formatFileSize(file.size)} • {new Date(file.uploadedAt).toLocaleString()}
                      </p>

                      {file.parameters && (
                        <div style={styles.badgeRow}>
                          <Badge variant={Number(file.parameters.heartRate ?? 0) > 100 || Number(file.parameters.heartRate ?? 0) < 60 ? 'warning' : 'info'}>
                            {t('cardio.cardio_ecg_hr_label', { value: file.parameters.heartRate })}
                          </Badge>
                          <Badge variant={Number(file.parameters.qtInterval ?? 0) > 450 ? 'warning' : 'info'}>
                            {t('cardio.cardio_ecg_qt_label', { value: file.parameters.qtInterval })}
                          </Badge>
                          <Badge variant={Number(file.parameters.prInterval ?? 0) > 200 ? 'warning' : 'info'}>
                            {t('cardio.cardio_ecg_pr_label', { value: file.parameters.prInterval })}
                          </Badge>
                        </div>
                      )}

                      {criticalParams.length > 0 && (
                        <Alert severity="warning" style={styles.criticalAlert}>
                          <span style={styles.caption}>{t('cardio.cardio_ecg_deviations_found')}</span>
                          <span style={styles.criticalList}>
                            {criticalParams.map((param, i) => (
                              <span key={i} style={styles.caption}>
                                {t('cardio.cardio_ecg_param_value', { name: param.name, value: param.value })}
                              </span>
                            ))}
                          </span>
                        </Alert>
                      )}
                    </div>

                    <div style={styles.actionRow}>
                      <button
                        type="button"
                        style={styles.iconButton}
                        onClick={() => openViewer(file)}
                        title={t('cardio.cardio_ecg_view')}
                        aria-label={t('cardio.cardio_ecg_view')}
                      >
                        <Eye size={iconSize} aria-hidden="true" />
                      </button>

                      <button
                        type="button"
                        style={{ ...styles.iconButton, ...(analyzing ? styles.iconButtonDisabled : {}) }}
                        onClick={() => analyzeECG(file)}
                        disabled={analyzing}
                        title={t('cardio.cardio_ecg_ai_analysis')}
                        aria-label={t('cardio.cardio_ecg_ai_analysis')}
                      >
                        <BrainCircuit size={iconSize} aria-hidden="true" />
                      </button>

                      <button
                        type="button"
                        style={styles.iconButton}
                        onClick={() => downloadFile(file)}
                        title={t('cardio.cardio_ecg_download')}
                        aria-label={t('cardio.cardio_ecg_download')}
                      >
                        <Download size={iconSize} aria-hidden="true" />
                      </button>

                      <button
                        type="button"
                        style={styles.iconButton}
                        onClick={() => deleteFile(file.id)}
                        title={t('cardio.cardio_ecg_delete')}
                        aria-label={t('cardio.cardio_ecg_delete')}
                      >
                        <Trash2 size={iconSize} aria-hidden="true" />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      )}

      {analyzing && (
        <Card>
          <CardContent>
            <div style={styles.analysisStatus}>
              <Progress value={75} variant="primary" style={{ flex: 1 }} />
              <p style={styles.bodyText}>{t('cardio.cardio_ecg_analyzing')}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {analysisResult && !analysisResult.error && (
        <Card>
          <CardContent>
            <h3 style={styles.sectionTitle}>
              <ClipboardCheck size={iconSize} aria-hidden="true" />
              {t('cardio.cardio_ecg_ai_interpretation_title')}
            </h3>

            <div style={styles.analysisPanel}>
              {analysisResult.findings && (
                <section>
                  <h4 style={styles.subsectionTitle}>{t('cardio.cardio_ecg_findings_title')}</h4>
                  <div style={styles.badgeRow}>
                    {analysisResult.findings.map((finding, i) => (
                      <Badge
                        key={i}
                        variant={finding.includes('норма') ? 'success' : 'warning'}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
                      >
                        {finding.includes('норма') ? (
                          <CheckCircle style={{ width: 14, height: 14 }} />
                        ) : (
                          <AlertTriangle style={{ width: 14, height: 14 }} />
                        )}
                        {finding}
                      </Badge>
                    ))}
                  </div>
                </section>
              )}

              {analysisResult.interpretation && (
                <section>
                  <h4 style={styles.subsectionTitle}>{t('cardio.cardio_ecg_interpretation_title')}</h4>
                  <p style={styles.bodyText}>{analysisResult.interpretation}</p>
                </section>
              )}

              {analysisResult.recommendations && (
                <section>
                  <h4 style={styles.subsectionTitle}>{t('cardio.cardio_ecg_recommendations_title')}</h4>
                  <p style={styles.bodyText}>{analysisResult.recommendations}</p>
                </section>
              )}

              <Alert severity="info">
                <span style={styles.caption}>
                  {t('cardio.cardio_ecg_ai_disclaimer')}
                </span>
              </Alert>
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog
        open={viewerOpen}
        onClose={closeViewer}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          <div style={styles.dialogHeader}>
            <h3 style={styles.dialogTitle}>{selectedFile?.name}</h3>
            <Button
              variant="outline"
              onClick={closeViewer}
              style={{ padding: 'var(--mac-spacing-2)' }}
              aria-label={t('cardio.cardio_ecg_close_viewer_aria')}
            >
              <X style={{ width: 16, height: 16 }} />
            </Button>
          </div>
        </DialogTitle>

        <DialogContent style={styles.dialogContent}>
          {selectedFile && (
            <div>
              {viewerLoading ? (
                <Alert severity="info">{t('cardio.cardio_ecg_loading_preview')}</Alert>
              ) : viewerBlobUrl ? (
                <div style={styles.previewArea}>
                  {(selectedFile.type === 'application/pdf' ||
                    selectedFile.type?.startsWith('image/')) ? (
                    selectedFile.type === 'application/pdf' ? (
                      <iframe
                        src={viewerBlobUrl}
                        style={styles.previewFrame}
                        title="ECG PDF"
                      />
                    ) : (
                      <img
                        src={viewerBlobUrl}
                        alt="ECG"
                        style={styles.previewImage}
                      />
                    )
                  ) : (
                    <Alert severity="info">
                      {t('cardio.cardio_ecg_preview_limited')}
                    </Alert>
                  )}
                </div>
              ) : viewerError ? (
                <Alert severity="warning">{viewerError}</Alert>
              ) : (
                <Alert severity="info">{t('cardio.cardio_ecg_file_ready')}</Alert>
              )}

              {ecgParameters && (
                <section style={{ marginTop: 'var(--mac-spacing-4)' }}>
                  <h3 style={styles.sectionTitle}>{t('cardio.cardio_ecg_params_title')}</h3>

                  <div style={styles.metricGrid}>
                    <div style={styles.metricCard}>
                      <p style={styles.caption}>{t('cardio.cardio_ecg_hr_full')}</p>
                      <p style={styles.metricValue}>{t('cardio.cardio_ecg_bpm_value', { count: ecgParameters.heartRate })}</p>
                    </div>

                    <div style={styles.metricCard}>
                      <p style={styles.caption}>{t('cardio.cardio_ecg_pr_interval')}</p>
                      <p style={styles.metricValue}>{t('cardio.cardio_ecg_ms_value', { count: ecgParameters.prInterval })}</p>
                    </div>

                    <div style={styles.metricCard}>
                      <p style={styles.caption}>{t('cardio.cardio_ecg_qrs_interval')}</p>
                      <p style={styles.metricValue}>{t('cardio.cardio_ecg_ms_value', { count: ecgParameters.qrsInterval })}</p>
                    </div>

                    <div style={styles.metricCard}>
                      <p style={styles.caption}>{t('cardio.cardio_ecg_qt_interval')}</p>
                      <p style={styles.metricValue}>{t('cardio.cardio_ecg_ms_value', { count: ecgParameters.qtInterval })}</p>
                    </div>

                    {ecgParameters.axis && (
                      <div style={styles.metricCard}>
                        <p style={styles.caption}>{t('cardio.cardio_ecg_heart_axis')}</p>
                        <p style={styles.metricValue}>{ecgParameters.axis}°</p>
                      </div>
                    )}
                  </div>
                </section>
              )}
            </div>
          )}
        </DialogContent>

        <DialogActions>
          <Button onClick={() => { if (selectedFile) analyzeECG(selectedFile); }} disabled={analyzing}>
            {t('cardio.cardio_ecg_ai_analysis_action')}
          </Button>
          <Button onClick={() => { if (selectedFile) downloadFile(selectedFile); }} variant="primary">
            {t('cardio.cardio_ecg_download')}
          </Button>
          <Button onClick={closeViewer}>{t('cardio.cardio_ecg_close')}</Button>
        </DialogActions>
      </Dialog>
    </div>
  );
};


export default ECGViewer;

