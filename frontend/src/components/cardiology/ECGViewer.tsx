// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useTranslation } from '../../i18n/useTranslation';
/**
 * ECG Viewer Component
 * Просмотр и анализ ЭКГ файлов
 * Согласно MASTER_TODO_LIST строка 247
 */
import { useEffect, useState } from 'react';
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
import PropTypes from 'prop-types';
import { api } from '../../api/client';
// R-11 / P-003 (UX audit): persist parsed ECG parameters to backend so the
// cardiologist panel's "history" tab can list prior ECGs without re-parsing
// the source file.
import notify from '../../services/notify';
import logger from '../../utils/logger';
import { getErrorMessage } from '../../utils/errorHandler';
import { parseECGFile, analyzeECGParameters } from './ECGParser';


const iconSize = 16;

const styles = {
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
  dropzone: (active) => ({
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

const ECGViewer = ({ visitId, patientId, onDataUpdate }) => {
  const { t: tI18n } = useTranslation();
  const [ecgFiles, setEcgFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerBlobUrl, setViewerBlobUrl] = useState(null);
  const [viewerLoading, setViewerLoading] = useState(false);
  const [viewerError, setViewerError] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [ecgParameters, setEcgParameters] = useState(null);

  useEffect(() => () => {
    if (viewerBlobUrl) {
      window.URL.revokeObjectURL(viewerBlobUrl);
    }
  }, [viewerBlobUrl]);

  // Поддерживаемые форматы
  const acceptedFormats = {
    'application/pdf': ['.pdf'],
    'text/xml': ['.xml'],
    'application/scp': ['.scp'],
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
  };

  // Загрузка файлов
  const onDrop = async (acceptedFiles) => {
    for (const file of acceptedFiles) {
      setUploadProgress(0);
      
      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('file_type', 'medical_record');
        formData.append('title', file.name);
        formData.append('tags', 'ecg,cardiology');
        if (patientId) {
          formData.append('patient_id', patientId);
        }
        if (visitId) {
          formData.append('visit_id', visitId);
        }
        
        const response = await api.post('/files/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (progressEvent) => {
            const percentCompleted = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            setUploadProgress(percentCompleted);
          },
        });
        
        const newFile = {
          id: response.data.id,
          name: response.data.original_filename || file.name,
          type: response.data.mime_type || file.type,
          size: response.data.file_size || file.size,
          uploadedAt: response.data.created_at || new Date().toISOString(),
          parameters: null,
        };
        
        setEcgFiles(prev => [...prev, newFile]);
        
        // Если это SCP/XML, пытаемся парсить
        if (file.type === 'text/xml' || file.name.endsWith('.scp')) {
          await parseECGFileData(file, newFile);
        }

        setUploadProgress(0);
        onDataUpdate && onDataUpdate();
        
      } catch (error) {
        logger.error('Ошибка загрузки ЭКГ:', error);
        notify.error(getErrorMessage(error, tI18n('cardio.cardio_ecg_upload_failed')));
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
  const parseECGFileData = async (originalFile, uploadedFile) => {
    try {
      // Сначала пробуем локальный парсинг
      const parseResult = await parseECGFile(originalFile);
      
      if (parseResult.success && parseResult.parameters) {
        const analysis = analyzeECGParameters(parseResult.parameters);
        const enrichedParams = {
          ...parseResult.parameters,
          ...analysis,
        };
        
        setEcgParameters(enrichedParams);
        
        // Обновляем файл с параметрами
        setEcgFiles(prev => prev.map(f => 
          f.id === uploadedFile.id 
            ? { ...f, parameters: enrichedParams }
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
            await api.post('/cardio/ecg', {
              patient_id: Number(patientId),
              visit_id: visitId ? Number(visitId) : null,
              file_id: uploadedFile.id,
              ecg_date: new Date().toISOString().slice(0, 10),
              heart_rate: enrichedParams.heart_rate ?? enrichedParams.heartRate ?? null,
              pr_interval: enrichedParams.pr_interval ?? enrichedParams.prInterval ?? null,
              qrs_duration: enrichedParams.qrs_duration ?? enrichedParams.qrsDuration ?? null,
              qt_interval: enrichedParams.qt_interval ?? enrichedParams.qtInterval ?? null,
              qt_corrected: enrichedParams.qt_corrected ?? enrichedParams.qtCorrected ?? null,
              rhythm: enrichedParams.rhythm ?? null,
              st_segment: enrichedParams.st_segment ?? enrichedParams.stSegment ?? null,
              t_wave: enrichedParams.t_wave ?? enrichedParams.tWave ?? null,
              axis: enrichedParams.axis ?? null,
              interpretation: enrichedParams.interpretation ?? null,
              source: 'device',
              parameters: enrichedParams,
            });
            notify.success(tI18n('final.ecg_saved'));
          } catch (persistError) {
            logger.error('Не удалось сохранить ЭКГ в истории пациента:', persistError);
            notify.error(tI18n('final.ecg_not_saved'));
          }
        }
      }
    } catch (error) {
      logger.error('Ошибка парсинга ЭКГ:', error);
      notify.warning(tI18n('final.ecg_parse_warning'));
    }
  };

  const openFileBlobUrl = async (fileId, mode = 'preview') => {
    const response = await api.get(`/files/${fileId}/${mode}`, {
      responseType: 'blob',
    });

    return window.URL.createObjectURL(response.data);
  };

  const downloadFile = async (file) => {
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
      notify.error(tI18n('final.ecg_download_failed'));
    }
  };

  // AI анализ ЭКГ
  const analyzeECG = async (file) => {
    setAnalyzing(true);
    setAnalysisResult(null);
    
    try {
      const response = await api.post('/ai/ecg-interpret', {
        file_id: file.id,
        visit_id: visitId,
        patient_id: patientId,
      });
      
      setAnalysisResult(response.data);
      onDataUpdate && onDataUpdate();
      
    } catch (error) {
      logger.error('Ошибка AI анализа:', error);
      setAnalysisResult({
        error: tI18n('cardio.cardio_ecg_ai_failed'),
      });
    } finally {
      setAnalyzing(false);
    }
  };

  // Открыть просмотрщик
  const openViewer = async (file) => {
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
      setViewerBlobUrl(blobUrl);
    } catch (error) {
      logger.info('Предпросмотр файла недоступен, используем только скачивание:', error);
      setViewerBlobUrl(null);
      setViewerError(tI18n('cardio.cardio_ecg_preview_unavailable'));
    } finally {
      setViewerLoading(false);
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
  const deleteFile = async (fileId) => {
    try {
      await api.delete(`/files/${fileId}`);
      setEcgFiles(prev => prev.filter(f => f.id !== fileId));
      onDataUpdate && onDataUpdate();
    } catch (error) {
      logger.error('Ошибка удаления файла:', error);
      notify.error(tI18n('final.ecg_delete_failed'));
    }
  };

  // Форматирование размера файла
  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  // Определение критичных параметров
  const getCriticalParameters = (params) => {
    const critical = [];
    
    if (params?.heartRate > 100) {
      critical.push({ name: tI18n('cardio.cardio_ecg_critical_tachycardia'), value: tI18n('cardio.cardio_ecg_bpm_value', { count: params.heartRate }) });
    }
    if (params?.heartRate < 60) {
      critical.push({ name: tI18n('cardio.cardio_ecg_critical_bradycardia'), value: tI18n('cardio.cardio_ecg_bpm_value', { count: params.heartRate }) });
    }
    if (params?.qtInterval > 450) {
      critical.push({ name: tI18n('cardio.cardio_ecg_critical_qt_prolonged'), value: tI18n('cardio.cardio_ecg_ms_value', { count: params.qtInterval }) });
    }
    if (params?.prInterval > 200) {
      critical.push({ name: tI18n('cardio.cardio_ecg_critical_av_block'), value: tI18n('cardio.cardio_ecg_ms_value', { count: params.prInterval }) });
    }
    
    return critical;
  };

  return (
    <div style={styles.root}>
      <Card>
        <CardContent>
          <h3 style={styles.sectionTitle}>
            <Clock size={iconSize} aria-hidden="true" />
            {tI18n('cardio.cardio_ecg_section_title')}
          </h3>

          <div {...getRootProps()} style={styles.dropzone(isDragActive)}>
            <Input {...getInputProps()} />
            <CloudUpload size={48} color="var(--mac-text-secondary)" aria-hidden="true" />
            <p style={{ ...styles.mutedText, marginTop: 'var(--mac-spacing-2)' }}>
              {isDragActive
                ? tI18n('cardio.cardio_ecg_drop_active')
                : tI18n('cardio.cardio_ecg_drop_idle')}
            </p>
            <p style={{ ...styles.caption, marginTop: 'var(--mac-spacing-2)' }}>
              {tI18n('cardio.cardio_ecg_formats_supported')}
            </p>
          </div>

          {uploadProgress > 0 && uploadProgress < 100 && (
            <div style={styles.uploadProgress}>
              <Progress variant="primary" value={uploadProgress} />
              <p style={styles.caption}>{tI18n('cardio.cardio_ecg_uploading', { percent: uploadProgress })}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {ecgFiles.length > 0 && (
        <Card>
          <CardContent>
            <h3 style={styles.sectionTitle}>{tI18n('cardio.cardio_ecg_uploaded_count', { count: ecgFiles.length })}</h3>

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
                            {tI18n('cardio.cardio_ecg_attention')}
                          </Badge>
                        )}
                      </div>

                      <p style={{ ...styles.caption, marginTop: 'var(--mac-spacing-1)' }}>
                        {formatFileSize(file.size)} • {new Date(file.uploadedAt).toLocaleString()}
                      </p>

                      {file.parameters && (
                        <div style={styles.badgeRow}>
                          <Badge variant={file.parameters.heartRate > 100 || file.parameters.heartRate < 60 ? 'warning' : 'info'}>
                            {tI18n('cardio.cardio_ecg_hr_label', { value: file.parameters.heartRate })}
                          </Badge>
                          <Badge variant={file.parameters.qtInterval > 450 ? 'warning' : 'info'}>
                            {tI18n('cardio.cardio_ecg_qt_label', { value: file.parameters.qtInterval })}
                          </Badge>
                          <Badge variant={file.parameters.prInterval > 200 ? 'warning' : 'info'}>
                            {tI18n('cardio.cardio_ecg_pr_label', { value: file.parameters.prInterval })}
                          </Badge>
                        </div>
                      )}

                      {criticalParams.length > 0 && (
                        <Alert severity="warning" style={styles.criticalAlert}>
                          <span style={styles.caption}>{tI18n('cardio.cardio_ecg_deviations_found')}</span>
                          <span style={styles.criticalList}>
                            {criticalParams.map((param, i) => (
                              <span key={i} style={styles.caption}>
                                {tI18n('cardio.cardio_ecg_param_value', { name: param.name, value: param.value })}
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
                        title={tI18n('cardio.cardio_ecg_view')}
                        aria-label={tI18n('cardio.cardio_ecg_view')}
                      >
                        <Eye size={iconSize} aria-hidden="true" />
                      </button>

                      <button
                        type="button"
                        style={{ ...styles.iconButton, ...(analyzing ? styles.iconButtonDisabled : {}) }}
                        onClick={() => analyzeECG(file)}
                        disabled={analyzing}
                        title={tI18n('cardio.cardio_ecg_ai_analysis')}
                        aria-label={tI18n('cardio.cardio_ecg_ai_analysis')}
                      >
                        <BrainCircuit size={iconSize} aria-hidden="true" />
                      </button>

                      <button
                        type="button"
                        style={styles.iconButton}
                        onClick={() => downloadFile(file)}
                        title={tI18n('cardio.cardio_ecg_download')}
                        aria-label={tI18n('cardio.cardio_ecg_download')}
                      >
                        <Download size={iconSize} aria-hidden="true" />
                      </button>

                      <button
                        type="button"
                        style={styles.iconButton}
                        onClick={() => deleteFile(file.id)}
                        title={tI18n('cardio.cardio_ecg_delete')}
                        aria-label={tI18n('cardio.cardio_ecg_delete')}
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
              <p style={styles.bodyText}>{tI18n('cardio.cardio_ecg_analyzing')}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {analysisResult && !analysisResult.error && (
        <Card>
          <CardContent>
            <h3 style={styles.sectionTitle}>
              <ClipboardCheck size={iconSize} aria-hidden="true" />
              {tI18n('cardio.cardio_ecg_ai_interpretation_title')}
            </h3>

            <div style={styles.analysisPanel}>
              {analysisResult.findings && (
                <section>
                  <h4 style={styles.subsectionTitle}>{tI18n('cardio.cardio_ecg_findings_title')}</h4>
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
                  <h4 style={styles.subsectionTitle}>{tI18n('cardio.cardio_ecg_interpretation_title')}</h4>
                  <p style={styles.bodyText}>{analysisResult.interpretation}</p>
                </section>
              )}

              {analysisResult.recommendations && (
                <section>
                  <h4 style={styles.subsectionTitle}>{tI18n('cardio.cardio_ecg_recommendations_title')}</h4>
                  <p style={styles.bodyText}>{analysisResult.recommendations}</p>
                </section>
              )}

              <Alert severity="info">
                <span style={styles.caption}>
                  {tI18n('cardio.cardio_ecg_ai_disclaimer')}
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
              aria-label={tI18n('cardio.cardio_ecg_close_viewer_aria')}
            >
              <X style={{ width: 16, height: 16 }} />
            </Button>
          </div>
        </DialogTitle>

        <DialogContent style={styles.dialogContent}>
          {selectedFile && (
            <div>
              {viewerLoading ? (
                <Alert severity="info">{tI18n('cardio.cardio_ecg_loading_preview')}</Alert>
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
                      {tI18n('cardio.cardio_ecg_preview_limited')}
                    </Alert>
                  )}
                </div>
              ) : viewerError ? (
                <Alert severity="warning">{viewerError}</Alert>
              ) : (
                <Alert severity="info">{tI18n('cardio.cardio_ecg_file_ready')}</Alert>
              )}

              {ecgParameters && (
                <section style={{ marginTop: 'var(--mac-spacing-4)' }}>
                  <h3 style={styles.sectionTitle}>{tI18n('cardio.cardio_ecg_params_title')}</h3>

                  <div style={styles.metricGrid}>
                    <div style={styles.metricCard}>
                      <p style={styles.caption}>{tI18n('cardio.cardio_ecg_hr_full')}</p>
                      <p style={styles.metricValue}>{tI18n('cardio.cardio_ecg_bpm_value', { count: ecgParameters.heartRate })}</p>
                    </div>

                    <div style={styles.metricCard}>
                      <p style={styles.caption}>{tI18n('cardio.cardio_ecg_pr_interval')}</p>
                      <p style={styles.metricValue}>{tI18n('cardio.cardio_ecg_ms_value', { count: ecgParameters.prInterval })}</p>
                    </div>

                    <div style={styles.metricCard}>
                      <p style={styles.caption}>{tI18n('cardio.cardio_ecg_qrs_interval')}</p>
                      <p style={styles.metricValue}>{tI18n('cardio.cardio_ecg_ms_value', { count: ecgParameters.qrsInterval })}</p>
                    </div>

                    <div style={styles.metricCard}>
                      <p style={styles.caption}>{tI18n('cardio.cardio_ecg_qt_interval')}</p>
                      <p style={styles.metricValue}>{tI18n('cardio.cardio_ecg_ms_value', { count: ecgParameters.qtInterval })}</p>
                    </div>

                    {ecgParameters.axis && (
                      <div style={styles.metricCard}>
                        <p style={styles.caption}>{tI18n('cardio.cardio_ecg_heart_axis')}</p>
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
          <Button onClick={() => analyzeECG(selectedFile)} disabled={analyzing}>
            {tI18n('cardio.cardio_ecg_ai_analysis_action')}
          </Button>
          <Button onClick={() => downloadFile(selectedFile)} variant="primary">
            {tI18n('cardio.cardio_ecg_download')}
          </Button>
          <Button onClick={closeViewer}>{tI18n('cardio.cardio_ecg_close')}</Button>
        </DialogActions>
      </Dialog>
    </div>
  );
};

ECGViewer.propTypes = {
  visitId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  patientId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onDataUpdate: PropTypes.func,
};

export default ECGViewer;

