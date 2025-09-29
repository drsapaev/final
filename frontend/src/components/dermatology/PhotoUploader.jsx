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
  Grid,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  Chip,
  LinearProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Paper,
} from '@mui/material';
import {
  PhotoCamera,
  CloudUpload,
  Delete,
  Visibility,
  CompareArrows,
  Warning,
  CheckCircle,
  CameraAlt,
  FlipCameraAndroid,
  Brightness5,
  ZoomIn,
} from '@mui/icons-material';
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
    for (let file of acceptedFiles) {
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
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Параметры съемки
          </Typography>
          
          <Grid container spacing={2}>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label="Зона"
                value={metadata.zone}
                onChange={(e) => setMetadata({ ...metadata, zone: e.target.value })}
                placeholder="Лицо, спина, руки..."
              />
            </Grid>
            
            <Grid item xs={12} md={3}>
              <FormControl fullWidth>
                <InputLabel>Ракурс</InputLabel>
                <Select
                  value={metadata.angle}
                  onChange={(e) => setMetadata({ ...metadata, angle: e.target.value })}
                  label="Ракурс"
                >
                  <MenuItem value="front">Спереди</MenuItem>
                  <MenuItem value="side">Сбоку</MenuItem>
                  <MenuItem value="back">Сзади</MenuItem>
                  <MenuItem value="close">Крупный план</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} md={3}>
              <FormControl fullWidth>
                <InputLabel>Освещение</InputLabel>
                <Select
                  value={metadata.lighting}
                  onChange={(e) => setMetadata({ ...metadata, lighting: e.target.value })}
                  label="Освещение"
                >
                  <MenuItem value="natural">Естественное</MenuItem>
                  <MenuItem value="artificial">Искусственное</MenuItem>
                  <MenuItem value="mixed">Смешанное</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} md={3}>
              <FormControl fullWidth>
                <InputLabel>Вспышка</InputLabel>
                <Select
                  value={metadata.flash ? 'yes' : 'no'}
                  onChange={(e) => setMetadata({ ...metadata, flash: e.target.value === 'yes' })}
                  label="Вспышка"
                >
                  <MenuItem value="no">Без вспышки</MenuItem>
                  <MenuItem value="yes">Со вспышкой</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      <Grid container spacing={2}>
        {/* Фото ДО */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <PhotoCamera sx={{ mr: 1, verticalAlign: 'middle' }} />
                Фото ДО процедуры
              </Typography>
              
              <Box
                {...getBeforeRootProps()}
                sx={{
                  mt: 2,
                  p: 3,
                  border: '2px dashed',
                  borderColor: isBeforeDragActive ? 'primary.main' : 'divider',
                  borderRadius: 2,
                  bgcolor: isBeforeDragActive ? 'action.hover' : 'background.paper',
                  cursor: 'pointer',
                  textAlign: 'center',
                }}
              >
                <input {...getBeforeInputProps()} />
                <CloudUpload sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
                <Typography variant="body1" color="text.secondary">
                  {isBeforeDragActive
                    ? 'Отпустите файлы здесь...'
                    : 'Перетащите фото или нажмите для выбора'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  JPG, PNG, HEIC до 10MB
                </Typography>
              </Box>
              
              <Button
                fullWidth
                variant="outlined"
                startIcon={<CameraAlt />}
                sx={{ mt: 2 }}
                onClick={() => {
                  setCameraType('before');
                  setCameraOpen(true);
                }}
              >
                Сделать фото
              </Button>
              
              {/* Превью фото ДО */}
              {photos.before.length > 0 && (
                <Grid container spacing={1} sx={{ mt: 2 }}>
                  {photos.before.map((photo) => (
                    <Grid item xs={6} key={photo.id}>
                      <Paper sx={{ position: 'relative' }}>
                        <img
                          src={photo.preview}
                          alt="Before"
                          style={{
                            width: '100%',
                            height: '150px',
                            objectFit: 'cover',
                            cursor: 'pointer',
                          }}
                          onClick={() => openViewer(photo, 'before')}
                        />
                        <Box sx={{
                          position: 'absolute',
                          top: 0,
                          right: 0,
                          p: 0.5,
                          bgcolor: 'rgba(0,0,0,0.5)',
                        }}>
                          <IconButton
                            size="small"
                            onClick={() => deletePhoto(photo.id, 'before')}
                            sx={{ color: 'white' }}
                          >
                            <Delete fontSize="small" />
                          </IconButton>
                        </Box>
                        <Typography
                          variant="caption"
                          sx={{
                            position: 'absolute',
                            bottom: 0,
                            left: 0,
                            right: 0,
                            p: 0.5,
                            bgcolor: 'rgba(0,0,0,0.7)',
                            color: 'white',
                          }}
                        >
                          {photo.metadata.zone || 'Без зоны'}
                        </Typography>
                      </Paper>
                    </Grid>
                  ))}
                </Grid>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Фото ПОСЛЕ */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <PhotoCamera sx={{ mr: 1, verticalAlign: 'middle' }} />
                Фото ПОСЛЕ процедуры
              </Typography>
              
              <Box
                {...getAfterRootProps()}
                sx={{
                  mt: 2,
                  p: 3,
                  border: '2px dashed',
                  borderColor: isAfterDragActive ? 'primary.main' : 'divider',
                  borderRadius: 2,
                  bgcolor: isAfterDragActive ? 'action.hover' : 'background.paper',
                  cursor: 'pointer',
                  textAlign: 'center',
                }}
              >
                <input {...getAfterInputProps()} />
                <CloudUpload sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
                <Typography variant="body1" color="text.secondary">
                  {isAfterDragActive
                    ? 'Отпустите файлы здесь...'
                    : 'Перетащите фото или нажмите для выбора'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  JPG, PNG, HEIC до 10MB
                </Typography>
              </Box>
              
              <Button
                fullWidth
                variant="outlined"
                startIcon={<CameraAlt />}
                sx={{ mt: 2 }}
                onClick={() => {
                  setCameraType('after');
                  setCameraOpen(true);
                }}
              >
                Сделать фото
              </Button>
              
              {/* Превью фото ПОСЛЕ */}
              {photos.after.length > 0 && (
                <Grid container spacing={1} sx={{ mt: 2 }}>
                  {photos.after.map((photo) => (
                    <Grid item xs={6} key={photo.id}>
                      <Paper sx={{ position: 'relative' }}>
                        <img
                          src={photo.preview}
                          alt="After"
                          style={{
                            width: '100%',
                            height: '150px',
                            objectFit: 'cover',
                            cursor: 'pointer',
                          }}
                          onClick={() => openViewer(photo, 'after')}
                        />
                        <Box sx={{
                          position: 'absolute',
                          top: 0,
                          right: 0,
                          p: 0.5,
                          bgcolor: 'rgba(0,0,0,0.5)',
                        }}>
                          <IconButton
                            size="small"
                            onClick={() => deletePhoto(photo.id, 'after')}
                            sx={{ color: 'white' }}
                          >
                            <Delete fontSize="small" />
                          </IconButton>
                        </Box>
                        <Typography
                          variant="caption"
                          sx={{
                            position: 'absolute',
                            bottom: 0,
                            left: 0,
                            right: 0,
                            p: 0.5,
                            bgcolor: 'rgba(0,0,0,0.7)',
                            color: 'white',
                          }}
                        >
                          {photo.metadata.zone || 'Без зоны'}
                        </Typography>
                      </Paper>
                    </Grid>
                  ))}
                </Grid>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Кнопка сравнения */}
      {photos.before.length > 0 && photos.after.length > 0 && (
        <Box sx={{ mt: 2, textAlign: 'center' }}>
          <Button
            variant="contained"
            size="large"
            startIcon={<CompareArrows />}
            onClick={openCompareMode}
          >
            Сравнить ДО и ПОСЛЕ
          </Button>
        </Box>
      )}

      {/* Прогресс загрузки */}
      {uploadProgress > 0 && uploadProgress < 100 && (
        <Box sx={{ mt: 2 }}>
          <LinearProgress variant="determinate" value={uploadProgress} />
          <Typography variant="caption" color="text.secondary" align="center">
            Загрузка: {uploadProgress}%
          </Typography>
        </Box>
      )}

      {/* Конвертация HEIC */}
      {converting && (
        <Alert severity="info" sx={{ mt: 2 }}>
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
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Typography variant="h6" align="center" gutterBottom>
                  ДО
                </Typography>
                {photos.before[0] && (
                  <img
                    src={photos.before[0].preview}
                    alt="Before"
                    style={{ width: '100%', height: 'auto' }}
                  />
                )}
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="h6" align="center" gutterBottom>
                  ПОСЛЕ
                </Typography>
                {photos.after[0] && (
                  <img
                    src={photos.after[0].preview}
                    alt="After"
                    style={{ width: '100%', height: 'auto' }}
                  />
                )}
              </Grid>
            </Grid>
          ) : selectedPhoto && (
            <Box>
              <img
                src={selectedPhoto.preview}
                alt={selectedPhoto.type}
                style={{ width: '100%', height: 'auto' }}
              />
              
              {selectedPhoto.metadata && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Параметры съемки:
                  </Typography>
                  <Grid container spacing={1}>
                    <Grid item xs={6}>
                      <Chip label={`Зона: ${selectedPhoto.metadata.zone || 'Не указана'}`} size="small" />
                    </Grid>
                    <Grid item xs={6}>
                      <Chip label={`Ракурс: ${selectedPhoto.metadata.angle}`} size="small" />
                    </Grid>
                    <Grid item xs={6}>
                      <Chip label={`Освещение: ${selectedPhoto.metadata.lighting}`} size="small" />
                    </Grid>
                    <Grid item xs={6}>
                      <Chip label={selectedPhoto.metadata.flash ? 'Со вспышкой' : 'Без вспышки'} size="small" />
                    </Grid>
                  </Grid>
                </Box>
              )}
            </Box>
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
          <Box sx={{ position: 'relative', width: '100%', height: '400px', bgcolor: 'black' }}>
            {/* Здесь должен быть компонент Webcam */}
            <Typography color="white" align="center" sx={{ pt: 20 }}>
              Камера (требуется react-webcam)
            </Typography>
          </Box>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setCameraOpen(false)}>
            Отмена
          </Button>
          <Button variant="contained" onClick={capturePhoto}>
            Сделать снимок
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default PhotoUploader;

