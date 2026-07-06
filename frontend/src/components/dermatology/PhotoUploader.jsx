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
      notify.error('Для загрузки фото выберите пациента или визит');
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
            notify.error('Не удалось загрузить фото. Проверьте соединение и попробуйте снова.');
            setUploadProgress(0);
          }
        };

        reader.onerror = () => {
          logger.error('FileReader error');
          notify.error('Не удалось прочитать файл.');
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
      notify.success('Фото удалено');
    } catch (error) {
      logger.error('Ошибка удаления фото:', error);
      notify.error('Не удалось удалить фото. Проверьте соединение и попробуйте снова.');
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
            Параметры съемки
          </Typography>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
            <div>
              <Input
                label="Зона"
                value={metadata.zone}
                onChange={(e) => setMetadata({ ...metadata, zone: e.target.value })}
                placeholder="Лицо, спина, руки..." />
              
            </div>
            
            <div>
              <Select
                label="Ракурс"
                value={metadata.angle}
                onChange={(e) => setMetadata({ ...metadata, angle: e.target.value })}>
                
                <Option value="front">Спереди</Option>
                <Option value="side">Сбоку</Option>
                <Option value="back">Сзади</Option>
                <Option value="close">Крупный план</Option>
              </Select>
            </div>
            
            <div>
              <Select
                label="Освещение"
                value={metadata.lighting}
                onChange={(e) => setMetadata({ ...metadata, lighting: e.target.value })}>
                
                <Option value="natural">Естественное</Option>
                <Option value="artificial">Искусственное</Option>
                <Option value="mixed">Смешанное</Option>
              </Select>
            </div>
            
            <div>
              <Select
                label="Вспышка"
                value={metadata.flash ? 'yes' : 'no'}
                onChange={(e) => setMetadata({ ...metadata, flash: e.target.value === 'yes' })}>
                
                <Option value="no">Без вспышки</Option>
                <Option value="yes">Со вспышкой</Option>
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
              Фото ДО процедуры
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
                'Отпустите файлы здесь...' :
                'Перетащите фото или нажмите для выбора'}
              </Typography>
              <Typography variant="caption" color="textSecondary">
                JPG, PNG, HEIC до 10MB
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
              Сделать фото
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
                  aria-label="Открыть фото до процедуры"
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
                    aria-label="Удалить фото до процедуры"
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
                      {photo.metadata.zone || 'Без зоны'}
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
              Фото ПОСЛЕ процедуры
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
                'Отпустите файлы здесь...' :
                'Перетащите фото или нажмите для выбора'}
              </Typography>
              <Typography variant="caption" color="textSecondary">
                JPG, PNG, HEIC до 10MB
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
              Сделать фото
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
                  aria-label="Открыть фото после процедуры"
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
                    aria-label="Удалить фото после процедуры"
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
                      {photo.metadata.zone || 'Без зоны'}
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
            Сравнить ДО и ПОСЛЕ
          </Button>
        </div>
      }

      {/* Прогресс загрузки */}
      {uploadProgress > 0 && uploadProgress < 100 &&
      <div style={{ marginTop: 16 }}>
          <Progress variant="determinate" value={uploadProgress} />
          <Typography variant="caption" color="textSecondary" style={{ textAlign: 'center', display: 'block', marginTop: 8 }}>
            Загрузка: {uploadProgress}%
          </Typography>
        </div>
      }

      {/* Конвертация HEIC */}
      {converting &&
      <Alert severity="info" style={{ marginTop: 16 }}>
          Конвертация HEIC в JPEG...
        </Alert>
      }

      {/* Диалог просмотра/сравнения */}
      <Dialog
        open={viewerOpen}
        onClose={() => setViewerOpen(false)}
        maxWidth="lg"
        fullWidth>
        
        <DialogTitle>
          {compareMode ? 'Сравнение ДО и ПОСЛЕ' : selectedPhoto?.type === 'before' ? 'Фото ДО' : 'Фото ПОСЛЕ'}
        </DialogTitle>
        
        <DialogContent>
          {compareMode ?
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
              <div>
                <Typography variant="h6" style={{ textAlign: 'center', marginBottom: 16 }}>
                  ДО
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
                  ПОСЛЕ
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
                    Параметры съемки:
                  </Typography>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8 }}>
                    <div style={{ padding: 8, backgroundColor: 'var(--mac-bg-secondary)', borderRadius: 4 }}>
                      Зона: {selectedPhoto.metadata.zone || 'Не указана'}
                    </div>
                    <div style={{ padding: 8, backgroundColor: 'var(--mac-bg-secondary)', borderRadius: 4 }}>
                      Ракурс: {selectedPhoto.metadata.angle}
                    </div>
                    <div style={{ padding: 8, backgroundColor: 'var(--mac-bg-secondary)', borderRadius: 4 }}>
                      Освещение: {selectedPhoto.metadata.lighting}
                    </div>
                    <div style={{ padding: 8, backgroundColor: 'var(--mac-bg-secondary)', borderRadius: 4 }}>
                      {selectedPhoto.metadata.flash ? 'Со вспышкой' : 'Без вспышки'}
                    </div>
                  </div>
                </div>
            }
            </div>
          }
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setViewerOpen(false)}>
            Закрыть
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
          Сделать фото {cameraType === 'before' ? 'ДО' : 'ПОСЛЕ'}
        </DialogTitle>
        
        <DialogContent>
          <div style={{ position: 'relative', width: '100%', height: '400px', backgroundColor: 'black', borderRadius: 8 }}>
            {/* Здесь должен быть компонент Webcam */}
            <Typography color="white" style={{ textAlign: 'center', paddingTop: 160 }}>
              Камера (требуется react-webcam)
            </Typography>
          </div>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setCameraOpen(false)}>
            Отмена
          </Button>
          <Button variant="primary" onClick={capturePhoto}>
            Сделать снимок
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
