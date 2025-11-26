/**
 * Photo Uploader Component
 * Загрузка фото до/после с поддержкой HEIC
 * Согласно MASTER_TODO_LIST строка 265
 */
import React, { useState, useCallback, useRef } from 'react';
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
  Eye,
  ArrowLeftRight,
  AlertTriangle,
  CheckCircle,
  CameraIcon,
  RotateCcw,
  Sun,
  ZoomIn,
} from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import heic2any from 'heic2any';
import { api } from '../../api/client';

const PhotoUploader = ({ visitId, patientId, onDataUpdate }) => {
  const [photos, setPhotos] = useState({
    before: [],
    after: [],
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
    flash: false,
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
    'image/webp': ['.webp'],
  };

  // Конвертация HEIC в JPEG
  const convertHEICtoJPEG = async (file) => {
    setConverting(true);
    try {
      const blob = await heic2any({
        blob: file,
        toType: 'image/jpeg',
        quality: 0.9,
      });
      
      // Создаем новый File объект
      const convertedFile = new File(
        [blob],
        file.name.replace(/\.heic$/i, '.jpg'),
        { type: 'image/jpeg' }
      );
      
      setConverting(false);
      return convertedFile;
    } catch (error) {
      console.error('Ошибка конвертации HEIC:', error);
      setConverting(false);
      throw error;
    }
  };

  // Обработка загрузки файлов
  const handleFileDrop = useCallback(async (acceptedFiles, fileType) => {
    for (const file of acceptedFiles) {
      setUploadProgress(0);
      
      try {
        // Проверяем и конвертируем HEIC
        let processedFile = file;
        if (file.type === 'image/heic' || file.name.toLowerCase().endsWith('.heic')) {
          processedFile = await convertHEICtoJPEG(file);
        }
        
        // Создаем превью
        const reader = new FileReader();
        reader.onload = async (e) => {
          const preview = e.target.result;
          
          // Загружаем на сервер
          const formData = new FormData();
          formData.append('file', processedFile);
          formData.append('kind', fileType === 'before' ? 'photo_before' : 'photo_after');
          formData.append('visit_id', visitId);
          formData.append('metadata', JSON.stringify(metadata));
          
          const response = await api.post(`/visits/${visitId}/files`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            onUploadProgress: (progressEvent) => {
              const percentCompleted = Math.round(
                (progressEvent.loaded * 100) / progressEvent.total
              );
              setUploadProgress(percentCompleted);
            },
          });
          
          const newPhoto = {
            id: response.data.id,
            url: response.data.url,
            preview: preview,
            name: processedFile.name,
            size: processedFile.size,
            uploadedAt: new Date().toISOString(),
            metadata: metadata,
          };
          
          setPhotos(prev => ({
            ...prev,
            [fileType]: [...prev[fileType], newPhoto],
          }));
          
          setUploadProgress(0);
          onDataUpdate && onDataUpdate();
        };
        
        reader.readAsDataURL(processedFile);
        
      } catch (error) {
        console.error('Ошибка загрузки фото:', error);
        setUploadProgress(0);
      }
    }
  }, [visitId, metadata, onDataUpdate]);

  // Dropzone для фото "До"
  const {
    getRootProps: getBeforeRootProps,
    getInputProps: getBeforeInputProps,
    isDragActive: isBeforeDragActive,
  } = useDropzone({
    onDrop: (files) => handleFileDrop(files, 'before'),
    accept: acceptedFormats,
    multiple: true,
  });

  // Dropzone для фото "После"
  const {
    getRootProps: getAfterRootProps,
    getInputProps: getAfterInputProps,
    isDragActive: isAfterDragActive,
  } = useDropzone({
    onDrop: (files) => handleFileDrop(files, 'after'),
    accept: acceptedFormats,
    multiple: true,
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
      setPhotos(prev => ({
        ...prev,
        [type]: prev[type].filter(p => p.id !== photoId),
      }));
      onDataUpdate && onDataUpdate();
    } catch (error) {
      console.error('Ошибка удаления фото:', error);
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
  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

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
                placeholder="Лицо, спина, руки..."
              />
            </div>
            
            <div>
              <Select
                label="Ракурс"
                value={metadata.angle}
                onChange={(e) => setMetadata({ ...metadata, angle: e.target.value })}
              >
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
                onChange={(e) => setMetadata({ ...metadata, lighting: e.target.value })}
              >
                <Option value="natural">Естественное</Option>
                <Option value="artificial">Искусственное</Option>
                <Option value="mixed">Смешанное</Option>
              </Select>
            </div>
            
            <div>
              <Select
                label="Вспышка"
                value={metadata.flash ? 'yes' : 'no'}
                onChange={(e) => setMetadata({ ...metadata, flash: e.target.value === 'yes' })}
              >
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
                transition: 'all 0.3s',
              }}
            >
              <input {...getBeforeInputProps()} />
              <Upload style={{ width: 48, height: 48, color: 'var(--mac-text-secondary)', marginBottom: 8 }} />
              <Typography variant="body1" color="textSecondary">
                {isBeforeDragActive
                  ? 'Отпустите файлы здесь...'
                  : 'Перетащите фото или нажмите для выбора'}
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
              }}
            >
              <CameraIcon style={{ width: 16, height: 16, marginRight: 8 }} />
              Сделать фото
            </Button>
              
            {/* Превью фото ДО */}
            {photos.before.length > 0 && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8, marginTop: 16 }}>
                {photos.before.map((photo) => (
                  <div key={photo.id} style={{ position: 'relative' }}>
                    <img
                      src={photo.preview}
                      alt="Before"
                      style={{
                        width: '100%',
                        height: '150px',
                        objectFit: 'cover',
                        cursor: 'pointer',
                        borderRadius: 8,
                      }}
                      onClick={() => openViewer(photo, 'before')}
                    />
                    <div style={{
                      position: 'absolute',
                      top: 4,
                      right: 4,
                      padding: 4,
                      backgroundColor: 'rgba(0,0,0,0.5)',
                      borderRadius: 4,
                    }}>
                      <button
                        onClick={() => deletePhoto(photo.id, 'before')}
                        style={{ color: 'white', background: 'none', border: 'none', cursor: 'pointer' }}
                      >
                        <Trash2 style={{ width: 16, height: 16 }} />
                      </button>
                    </div>
                    <div style={{
                      position: 'absolute',
                      bottom: 0,
                      left: 0,
                      right: 0,
                      padding: 4,
                      backgroundColor: 'rgba(0,0,0,0.7)',
                      color: 'white',
                      fontSize: '12px',
                      borderRadius: '0 0 8px 8px',
                    }}>
                      {photo.metadata.zone || 'Без зоны'}
                    </div>
                  </div>
                ))}
              </div>
            )}
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
                transition: 'all 0.3s',
              }}
            >
              <input {...getAfterInputProps()} />
              <Upload style={{ width: 48, height: 48, color: 'var(--mac-text-secondary)', marginBottom: 8 }} />
              <Typography variant="body1" color="textSecondary">
                {isAfterDragActive
                  ? 'Отпустите файлы здесь...'
                  : 'Перетащите фото или нажмите для выбора'}
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
              }}
            >
              <CameraIcon style={{ width: 16, height: 16, marginRight: 8 }} />
              Сделать фото
            </Button>
            
            {/* Превью фото ПОСЛЕ */}
            {photos.after.length > 0 && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8, marginTop: 16 }}>
                {photos.after.map((photo) => (
                  <div key={photo.id} style={{ position: 'relative' }}>
                    <img
                      src={photo.preview}
                      alt="After"
                      style={{
                        width: '100%',
                        height: '150px',
                        objectFit: 'cover',
                        cursor: 'pointer',
                        borderRadius: 8,
                      }}
                      onClick={() => openViewer(photo, 'after')}
                    />
                    <div style={{
                      position: 'absolute',
                      top: 4,
                      right: 4,
                      padding: 4,
                      backgroundColor: 'rgba(0,0,0,0.5)',
                      borderRadius: 4,
                    }}>
                      <button
                        onClick={() => deletePhoto(photo.id, 'after')}
                        style={{ color: 'white', background: 'none', border: 'none', cursor: 'pointer' }}
                      >
                        <Trash2 style={{ width: 16, height: 16 }} />
                      </button>
                    </div>
                    <div style={{
                      position: 'absolute',
                      bottom: 0,
                      left: 0,
                      right: 0,
                      padding: 4,
                      backgroundColor: 'rgba(0,0,0,0.7)',
                      color: 'white',
                      fontSize: '12px',
                      borderRadius: '0 0 8px 8px',
                    }}>
                      {photo.metadata.zone || 'Без зоны'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Кнопка сравнения */}
      {photos.before.length > 0 && photos.after.length > 0 && (
        <div style={{ marginTop: 16, textAlign: 'center' }}>
          <Button
            variant="primary"
            size="large"
            onClick={openCompareMode}
          >
            <ArrowLeftRight style={{ width: 16, height: 16, marginRight: 8 }} />
            Сравнить ДО и ПОСЛЕ
          </Button>
        </div>
      )}

      {/* Прогресс загрузки */}
      {uploadProgress > 0 && uploadProgress < 100 && (
        <div style={{ marginTop: 16 }}>
          <Progress variant="determinate" value={uploadProgress} />
          <Typography variant="caption" color="textSecondary" style={{ textAlign: 'center', display: 'block', marginTop: 8 }}>
            Загрузка: {uploadProgress}%
          </Typography>
        </div>
      )}

      {/* Конвертация HEIC */}
      {converting && (
        <Alert severity="info" style={{ marginTop: 16 }}>
          Конвертация HEIC в JPEG...
        </Alert>
      )}

      {/* Диалог просмотра/сравнения */}
      <Dialog
        open={viewerOpen}
        onClose={() => setViewerOpen(false)}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          {compareMode ? 'Сравнение ДО и ПОСЛЕ' : selectedPhoto?.type === 'before' ? 'Фото ДО' : 'Фото ПОСЛЕ'}
        </DialogTitle>
        
        <DialogContent>
          {compareMode ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
              <div>
                <Typography variant="h6" style={{ textAlign: 'center', marginBottom: 16 }}>
                  ДО
                </Typography>
                {photos.before[0] && (
                  <img
                    src={photos.before[0].preview}
                    alt="Before"
                    style={{ width: '100%', height: 'auto', borderRadius: 8 }}
                  />
                )}
              </div>
              <div>
                <Typography variant="h6" style={{ textAlign: 'center', marginBottom: 16 }}>
                  ПОСЛЕ
                </Typography>
                {photos.after[0] && (
                  <img
                    src={photos.after[0].preview}
                    alt="After"
                    style={{ width: '100%', height: 'auto', borderRadius: 8 }}
                  />
                )}
              </div>
            </div>
          ) : selectedPhoto && (
            <div>
              <img
                src={selectedPhoto.preview}
                alt={selectedPhoto.type}
                style={{ width: '100%', height: 'auto', borderRadius: 8 }}
              />
              
              {selectedPhoto.metadata && (
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
              )}
            </div>
          )}
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
        fullWidth
      >
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
    </Box>
  );
};

export default PhotoUploader;

