// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useTranslation } from '../../i18n/useTranslation';
/**
 * Photo Uploader Component
 * Загрузка фото до/после с поддержкой HEIC
 * Согласно MASTER_TODO_LIST строка 265
 */
import { useState, useCallback, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Alert,
  Progress,
  Input,
  Select,
  Option,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '../ui/macos';
import {
  Camera,
  Upload,
  Trash2,

  ArrowLeftRight,


  CameraIcon } from



'lucide-react';
import { useDropzone } from 'react-dropzone';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import notify from '../../services/notify';
import { convertHEICToJPEG, isHEICFile } from '../../utils/heicConverter';
import PropTypes from 'prop-types';
const PhotoUploader = ({ patientId, visitId, onDataUpdate }) => {
  const { t } = useTranslation();
  const [photos, setPhotos] = useState({
    before: [],
    after: []
  });
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [compareMode, setCompareMode] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [converting, setConverting] = useState(false);
  const [metadata, setMetadata] = useState({
    zone: '',
    angle: 'front',
    lighting: 'natural',
    flash: false
  });

  const webcamRef = useRef(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraType, setCameraType] = useState('before');

  // Поддерживаемые форматы
  const acceptedFormats = {
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/heic': ['.heic'],
    'image/heif': ['.heif'],
    'image/webp': ['.webp']
  };

  // Конвертация HEIC в JPEG
  const convertHEICtoJPEG = async (file) => {
    setConverting(true);
    try {
      return await convertHEICToJPEG(file, 0.9);

    } catch (error) {
      logger.error('Ошибка конвертации HEIC:', error);
      throw error;
    } finally {
      setConverting(false);
    }
  };

  // Обработка загрузки файлов
  const handleFileDrop = useCallback(async (acceptedFiles, fileType) => {
    // D-001 fix: validate patientId/visitId BEFORE starting FileReader.
    // Previously this check was inside reader.onload (async callback),
    // causing an unhandled promise rejection that crashed silently.
    if (!patientId && !visitId) {
      notify.error(t('final.photo_select_patient'));
      return;
    }

    for (const file of acceptedFiles) {
      setUploadProgress(0);

      try {
        // Проверяем и конвертируем HEIC
        let processedFile = file;
        if (isHEICFile(file)) {
          processedFile = await convertHEICtoJPEG(file);
        }

        // Создаем превью
        const reader = new FileReader();
        reader.onload = async (e) => {
          const preview = e.target.result;

          // Загружаем на сервер
          const formData = new FormData();
          formData.append('file', processedFile);
          formData.append('file_type', 'image');
          formData.append('title', processedFile.name);
          formData.append('tags', `dermatology,photo,${fileType}`);
          if (patientId) {
            formData.append('patient_id', patientId);
          }
          if (visitId) {
            formData.append('visit_id', visitId);
          }

          try {
            const response = await api.post('/files/upload', formData, {
              headers: { 'Content-Type': 'multipart/form-data' },
              onUploadProgress: (progressEvent) => {
                const percentCompleted = Math.round(
                  progressEvent.loaded * 100 / progressEvent.total
                );
                setUploadProgress(percentCompleted);
              }
            });

            const newPhoto = {
              id: response.data.id,
              url: response.data.url || (response.data.id ? `/api/v1/files/${response.data.id}/download` : preview),
              preview: preview,
              name: processedFile.name,
              size: processedFile.size,
              uploadedAt: new Date().toISOString(),
              metadata: metadata
            };

            // D-001 fix: compute updatedPhotos BEFORE setPhotos, then pass
            // the computed value to onDataUpdate. Previously `photos` was
            // stale (setPhotos is async) so the parent received old data.
            setPhotos((prev) => {
              const updated = {
                ...prev,
                [fileType]: [...prev[fileType], newPhoto]
              };
              onDataUpdate && onDataUpdate(updated);
              return updated;
            });

            setUploadProgress(0);
          } catch (uploadError) {
            logger.error('Photo upload failed:', uploadError);
            notify.error(t('final.photo_upload_failed'));
            setUploadProgress(0);
          }
        };

        reader.onerror = () => {
          logger.error('FileReader error');
          notify.error(t('final.photo_read_failed'));
          setUploadProgress(0);
        };

        reader.readAsDataURL(processedFile);

      } catch (error) {
        logger.error('Ошибка загрузки фото:', error);
        setUploadProgress(0);
      }
    }
  }, [visitId, metadata, onDataUpdate]);

  // Dropzone для фото "До"
  const {
    getRootProps: getBeforeRootProps,
    getInputProps: getBeforeInputProps,
    isDragActive: isBeforeDragActive
  } = useDropzone({
    onDrop: (files) => handleFileDrop(files, 'before'),
    accept: acceptedFormats,
    multiple: true
  });

  // Dropzone для фото "После"
  const {
    getRootProps: getAfterRootProps,
    getInputProps: getAfterInputProps,
    isDragActive: isAfterDragActive
  } = useDropzone({
    onDrop: (files) => handleFileDrop(files, 'after'),
    accept: acceptedFormats,
    multiple: true
  });

  // Захват с камеры
  const capturePhoto = async () => {
    if (webcamRef.current) {
      const imageSrc = webcamRef.current.getScreenshot();

      // Конвертируем base64 в blob
      const response = await fetch(imageSrc);
      const blob = await response.blob();
      const file = new File([blob], `camera_${Date.now()}.jpg`, { type: 'image/jpeg' });

      handleFileDrop([file], cameraType);
      setCameraOpen(false);
    }
  };

  // Удаление фото
  const deletePhoto = async (photoId, type) => {
    try {
      await api.delete(`/files/${photoId}`);
      // D-001 fix: compute updated photos inside setPhotos callback
      // and pass to onDataUpdate. Previously onDataUpdate() was called
      // with no argument, so the parent received undefined.
      setPhotos((prev) => {
        const updated = {
          ...prev,
          [type]: prev[type].filter((p) => p.id !== photoId)
        };
        onDataUpdate && onDataUpdate(updated);
        return updated;
      });
      notify.success(t('final.photo_deleted'));
    } catch (error) {
      logger.error('Ошибка удаления фото:', error);
      notify.error(t('final.photo_delete_failed'));
    }
  };

  // Открыть просмотрщик
  const openViewer = (photo, type) => {
    setSelectedPhoto({ ...photo, type });
    setViewerOpen(true);
    setCompareMode(false);
  };

  // Режим сравнения
  const openCompareMode = () => {
    if (photos.before.length > 0 && photos.after.length > 0) {
      setCompareMode(true);
      setViewerOpen(true);
    }
  };

  // Форматирование размера






  return (
    <Box>
      {/* Метаданные фото */}
      <Card style={{ marginBottom: 16 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {t('derma.derma_photo_shoot_params')}
          </Typography>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
            <div>
              <Input
                label={t('derma.derma_photo_zone')}
                value={metadata.zone}
                onChange={(e) => setMetadata({ ...metadata, zone: e.target.value })}
                placeholder={t('derma.derma_photo_ph_zone')} />
              
            </div>
            
            <div>
              <Select
                label={t('derma.derma_photo_angle')}
                value={metadata.angle}
                onChange={(e) => setMetadata({ ...metadata, angle: e.target.value })}>
                
                <Option value="front">{t('derma.derma_photo_angle_front')}</Option>
                <Option value="side">{t('derma.derma_photo_angle_side')}</Option>
                <Option value="back">{t('derma.derma_photo_angle_back')}</Option>
                <Option value="close">{t('derma.derma_photo_angle_close')}</Option>
              </Select>
            </div>
            
            <div>
              <Select
                label={t('derma.derma_photo_lighting')}
                value={metadata.lighting}
                onChange={(e) => setMetadata({ ...metadata, lighting: e.target.value })}>
                
                <Option value="natural">{t('derma.derma_photo_lighting_natural')}</Option>
                <Option value="artificial">{t('derma.derma_photo_lighting_artificial')}</Option>
                <Option value="mixed">{t('derma.derma_photo_lighting_mixed')}</Option>
              </Select>
            </div>
            
            <div>
              <Select
                label={t('derma.derma_photo_flash')}
                value={metadata.flash ? 'yes' : 'no'}
                onChange={(e) => setMetadata({ ...metadata, flash: e.target.value === 'yes' })}>
                
                <Option value="no">{t('derma.derma_photo_flash_no')}</Option>
                <Option value="yes">{t('derma.derma_photo_flash_yes')}</Option>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 16 }}>
        {/* Фото ДО */}
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              <Camera style={{ marginRight: 8, verticalAlign: 'middle' }} />
              {t('derma.derma_photo_before_title')}
            </Typography>
            
            <div
              {...getBeforeRootProps()}
              style={{
                marginTop: 16,
                padding: 24,
                border: '2px dashed',
                borderColor: isBeforeDragActive ? 'var(--mac-accent-blue)' : 'var(--mac-border)',
                borderRadius: 8,
                backgroundColor: isBeforeDragActive ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)',
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.3s'
              }}>
              
              <Input {...getBeforeInputProps()} />
              <Upload style={{ width: 48, height: 48, color: 'var(--mac-text-secondary)', marginBottom: 8 }} />
              <Typography variant="body1" color="textSecondary">
                {isBeforeDragActive ?
                t('derma.derma_photo_drop_here') :
                t('derma.derma_photo_drag_or_click')}
              </Typography>
              <Typography variant="caption" color="textSecondary">
                {t('derma.derma_photo_formats_hint')}
              </Typography>
            </div>
            
            <Button
              fullWidth
              variant="outline"
              style={{ marginTop: 16 }}
              onClick={() => {
                setCameraType('before');
                setCameraOpen(true);
              }}>
              
              <CameraIcon style={{ width: 16, height: 16, marginRight: 8 }} />
              {t('derma.derma_photo_take_photo')}
            </Button>
              
            {/* Превью фото ДО */}
            {photos.before.length > 0 &&
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8, marginTop: 16 }}>
                {photos.before.map((photo) =>
              <div key={photo.id} style={{ position: 'relative' }}>
                    <img
                  src={photo.preview}
                  alt="Before"
                  role="button"
                  aria-label={t('derma.derma_photo_open_before_aria')}
                  tabIndex={0}
                  style={{
                    width: '100%',
                    height: '150px',
                    objectFit: 'cover',
                    cursor: 'pointer',
                    borderRadius: 8
                  }}
                  onClick={() => openViewer(photo, 'before')}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      openViewer(photo, 'before');
                    }
                  }} />
                
                    <div style={{
                  position: 'absolute',
                  top: 4,
                  right: 4,
                  padding: 4,
                  backgroundColor: 'color-mix(in srgb, black, transparent 50%)',
                  borderRadius: 4
                }}>
                      <button
                    onClick={() => deletePhoto(photo.id, 'before')}
                    aria-label={t('derma.derma_photo_delete_before_aria')}
                    style={{ color: 'white', background: 'none', border: 'none', cursor: 'pointer' }}>
                    
                        <Trash2 style={{ width: 16, height: 16 }} />
                      </button>
                    </div>
                    <div style={{
                  position: 'absolute',
                  bottom: 0,
                  left: 0,
                  right: 0,
                  padding: 4,
                  backgroundColor: 'color-mix(in srgb, black, transparent 30%)',
                  color: 'white',
                  fontSize: 'var(--mac-font-size-xs)',
                  borderRadius: '0 0 8px 8px'
                }}>
                      {photo.metadata.zone || t('derma.derma_photo_no_zone')}
                    </div>
                  </div>
              )}
              </div>
            }
          </CardContent>
        </Card>

        {/* Фото ПОСЛЕ */}
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              <Camera style={{ marginRight: 8, verticalAlign: 'middle' }} />
              {t('derma.derma_photo_after_title')}
            </Typography>
            
            <div
              {...getAfterRootProps()}
              style={{
                marginTop: 16,
                padding: 24,
                border: '2px dashed',
                borderColor: isAfterDragActive ? 'var(--mac-accent-blue)' : 'var(--mac-border)',
                borderRadius: 8,
                backgroundColor: isAfterDragActive ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)',
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.3s'
              }}>
              
              <Input {...getAfterInputProps()} />
              <Upload style={{ width: 48, height: 48, color: 'var(--mac-text-secondary)', marginBottom: 8 }} />
              <Typography variant="body1" color="textSecondary">
                {isAfterDragActive ?
                t('derma.derma_photo_drop_here') :
                t('derma.derma_photo_drag_or_click')}
              </Typography>
              <Typography variant="caption" color="textSecondary">
                {t('derma.derma_photo_formats_hint')}
              </Typography>
            </div>
            
            <Button
              fullWidth
              variant="outline"
              style={{ marginTop: 16 }}
              onClick={() => {
                setCameraType('after');
                setCameraOpen(true);
              }}>
              
              <CameraIcon style={{ width: 16, height: 16, marginRight: 8 }} />
              {t('derma.derma_photo_take_photo')}
            </Button>
            
            {/* Превью фото ПОСЛЕ */}
            {photos.after.length > 0 &&
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8, marginTop: 16 }}>
                {photos.after.map((photo) =>
              <div key={photo.id} style={{ position: 'relative' }}>
                    <img
                  src={photo.preview}
                  alt="After"
                  role="button"
                  aria-label={t('derma.derma_photo_open_after_aria')}
                  tabIndex={0}
                  style={{
                    width: '100%',
                    height: '150px',
                    objectFit: 'cover',
                    cursor: 'pointer',
                    borderRadius: 8
                  }}
                  onClick={() => openViewer(photo, 'after')}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      openViewer(photo, 'after');
                    }
                  }} />
                
                    <div style={{
                  position: 'absolute',
                  top: 4,
                  right: 4,
                  padding: 4,
                  backgroundColor: 'color-mix(in srgb, black, transparent 50%)',
                  borderRadius: 4
                }}>
                      <button
                    onClick={() => deletePhoto(photo.id, 'after')}
                    aria-label={t('derma.derma_photo_delete_after_aria')}
                    style={{ color: 'white', background: 'none', border: 'none', cursor: 'pointer' }}>
                    
                        <Trash2 style={{ width: 16, height: 16 }} />
                      </button>
                    </div>
                    <div style={{
                  position: 'absolute',
                  bottom: 0,
                  left: 0,
                  right: 0,
                  padding: 4,
                  backgroundColor: 'color-mix(in srgb, black, transparent 30%)',
                  color: 'white',
                  fontSize: 'var(--mac-font-size-xs)',
                  borderRadius: '0 0 8px 8px'
                }}>
                      {photo.metadata.zone || t('derma.derma_photo_no_zone')}
                    </div>
                  </div>
              )}
              </div>
            }
          </CardContent>
        </Card>
      </div>

      {/* Кнопка сравнения */}
      {photos.before.length > 0 && photos.after.length > 0 &&
      <div style={{ marginTop: 16, textAlign: 'center' }}>
          <Button
          variant="primary"
          size="large"
          onClick={openCompareMode}>
          
            <ArrowLeftRight style={{ width: 16, height: 16, marginRight: 8 }} />
            {t('derma.derma_photo_compare_button')}
          </Button>
        </div>
      }

      {/* Прогресс загрузки */}
      {uploadProgress > 0 && uploadProgress < 100 &&
      <div style={{ marginTop: 16 }}>
          <Progress variant="determinate" value={uploadProgress} />
          <Typography variant="caption" color="textSecondary" style={{ textAlign: 'center', display: 'block', marginTop: 8 }}>
            {t('derma.derma_photo_upload_progress', { progress: uploadProgress })}
          </Typography>
        </div>
      }

      {/* Конвертация HEIC */}
      {converting &&
      <Alert severity="info" style={{ marginTop: 16 }}>
          {t('derma.derma_photo_heic_converting')}
        </Alert>
      }

      {/* Диалог просмотра/сравнения */}
      <Dialog
        open={viewerOpen}
        onClose={() => setViewerOpen(false)}
        maxWidth="lg"
        fullWidth>
        
        <DialogTitle>
          {compareMode ? t('derma.derma_photo_compare_title') : selectedPhoto?.type === 'before' ? t('derma.derma_photo_before_short') : t('derma.derma_photo_after_short')}
        </DialogTitle>
        
        <DialogContent>
          {compareMode ?
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
              <div>
                <Typography variant="h6" style={{ textAlign: 'center', marginBottom: 16 }}>
                  {t('derma.derma_photo_before_label')}
                </Typography>
                {photos.before[0] &&
              <img
                src={photos.before[0].preview}
                alt="Before"
                style={{ width: '100%', height: 'auto', borderRadius: 8 }} />

              }
              </div>
              <div>
                <Typography variant="h6" style={{ textAlign: 'center', marginBottom: 16 }}>
                  {t('derma.derma_photo_after_label')}
                </Typography>
                {photos.after[0] &&
              <img
                src={photos.after[0].preview}
                alt="After"
                style={{ width: '100%', height: 'auto', borderRadius: 8 }} />

              }
              </div>
            </div> :
          selectedPhoto &&
          <div>
              <img
              src={selectedPhoto.preview}
              alt={selectedPhoto.type}
              style={{ width: '100%', height: 'auto', borderRadius: 8 }} />
            
              
              {selectedPhoto.metadata &&
            <div style={{ marginTop: 16 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    {t('derma.derma_photo_shoot_params_colon')}
                  </Typography>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8 }}>
                    <div style={{ padding: 8, backgroundColor: 'var(--mac-bg-secondary)', borderRadius: 4 }}>
                      {t('derma.derma_photo_zone_inline')} {selectedPhoto.metadata.zone || t('derma.derma_photo_zone_unspecified')}
                    </div>
                    <div style={{ padding: 8, backgroundColor: 'var(--mac-bg-secondary)', borderRadius: 4 }}>
                      {t('derma.derma_photo_angle_inline')} {selectedPhoto.metadata.angle}
                    </div>
                    <div style={{ padding: 8, backgroundColor: 'var(--mac-bg-secondary)', borderRadius: 4 }}>
                      {t('derma.derma_photo_lighting_inline')} {selectedPhoto.metadata.lighting}
                    </div>
                    <div style={{ padding: 8, backgroundColor: 'var(--mac-bg-secondary)', borderRadius: 4 }}>
                      {selectedPhoto.metadata.flash ? t('derma.derma_photo_flash_yes') : t('derma.derma_photo_flash_no')}
                    </div>
                  </div>
                </div>
            }
            </div>
          }
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setViewerOpen(false)}>
            {t('derma.derma_photo_close')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Диалог камеры */}
      <Dialog
        open={cameraOpen}
        onClose={() => setCameraOpen(false)}
        maxWidth="md"
        fullWidth>
        
        <DialogTitle>
          {t('derma.derma_photo_camera_title', { type: cameraType === 'before' ? t('derma.derma_photo_before_label') : t('derma.derma_photo_after_label') })}
        </DialogTitle>
        
        <DialogContent>
          <div style={{ position: 'relative', width: '100%', height: '400px', backgroundColor: 'black', borderRadius: 8 }}>
            {/* Здесь должен быть компонент Webcam */}
            <Typography color="white" style={{ textAlign: 'center', paddingTop: 160 }}>
              {t('derma.derma_photo_camera_placeholder')}
            </Typography>
          </div>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setCameraOpen(false)}>
            {t('derma.derma_photo_cancel')}
          </Button>
          <Button variant="primary" onClick={capturePhoto}>
            {t('derma.derma_photo_capture')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>);

};


PhotoUploader.propTypes = {
  ...(PhotoUploader.propTypes || {}),
  onDataUpdate: PropTypes.any,
  patientId: PropTypes.any,
  visitId: PropTypes.any,
};

export default PhotoUploader;
