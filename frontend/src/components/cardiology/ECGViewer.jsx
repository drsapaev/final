/**
 * ECG Viewer Component
 * Просмотр и анализ ЭКГ файлов
 * Согласно MASTER_TODO_LIST строка 247
 */
import React, { useState, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  Badge,
  Progress,
} from '../ui/macos';
import {
  CloudUpload,
  Eye,
  Download,
  Trash2,
  BarChart3,
  Heart,
  Clock,
  Activity,
  ZoomIn,
  ZoomOut,
  Maximize,
  X,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import { api } from '../../api/client';
import { parseECGFile, analyzeECGParameters } from './ECGParser';

import logger from '../../utils/logger';
const ECGViewer = ({ visitId, patientId, onDataUpdate }) => {
  const [ecgFiles, setEcgFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [ecgParameters, setEcgParameters] = useState(null);

  // Поддерживаемые форматы
  const acceptedFormats = {
    'application/pdf': ['.pdf'],
    'text/xml': ['.xml'],
    'application/scp': ['.scp'],
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
  };

  // Загрузка файлов
  const onDrop = useCallback(async (acceptedFiles) => {
    for (const file of acceptedFiles) {
      setUploadProgress(0);
      
      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('kind', 'ecg');
        formData.append('visit_id', visitId);
        
        const response = await api.post(`/visits/${visitId}/files`, formData, {
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
          name: file.name,
          type: file.type,
          size: file.size,
          url: response.data.url,
          uploadedAt: new Date().toISOString(),
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
        setUploadProgress(0);
      }
    }
  }, [visitId, onDataUpdate]);

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
        
        // Отправляем на сервер если нужно
        try {
          await api.post(`/visits/${visitId}/ecg/parse`, {
            file_id: uploadedFile.id,
            parameters: enrichedParams,
          });
        } catch (error) {
          logger.error('Ошибка сохранения параметров на сервере:', error);
        }
      }
    } catch (error) {
      logger.error('Ошибка парсинга ЭКГ:', error);
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
        error: 'Не удалось проанализировать ЭКГ',
      });
    } finally {
      setAnalyzing(false);
    }
  };

  // Открыть просмотрщик
  const openViewer = (file) => {
    setSelectedFile(file);
    setViewerOpen(true);
    
    if (file.parameters) {
      setEcgParameters(file.parameters);
    }
  };

  // Удалить файл
  const deleteFile = async (fileId) => {
    try {
      await api.delete(`/files/${fileId}`);
      setEcgFiles(prev => prev.filter(f => f.id !== fileId));
      onDataUpdate && onDataUpdate();
    } catch (error) {
      logger.error('Ошибка удаления файла:', error);
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
      critical.push({ name: 'Тахикардия', value: `${params.heartRate} уд/мин` });
    }
    if (params?.heartRate < 60) {
      critical.push({ name: 'Брадикардия', value: `${params.heartRate} уд/мин` });
    }
    if (params?.qtInterval > 450) {
      critical.push({ name: 'Удлинение QT', value: `${params.qtInterval} мс` });
    }
    if (params?.prInterval > 200) {
      critical.push({ name: 'AV блокада I ст.', value: `${params.prInterval} мс` });
    }
    
    return critical;
  };

  return (
    <Box>
      {/* Зона загрузки */}
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" style={{ marginBottom: 16 }}>
            <Clock style={{ marginRight: 8, verticalAlign: 'middle' }} />
            ЭКГ исследования
          </Typography>
          
          <Box
            {...getRootProps()}
            sx={{
              mt: 2,
              p: 3,
              border: '2px dashed',
              borderColor: isDragActive ? 'primary.main' : 'divider',
              borderRadius: 2,
              bgcolor: isDragActive ? 'action.hover' : 'background.paper',
              cursor: 'pointer',
              transition: 'all 0.3s',
              textAlign: 'center',
            }}
          >
            <input {...getInputProps()} />
            <CloudUpload sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
            <Typography variant="body1" color="text.secondary">
              {isDragActive
                ? 'Отпустите файлы здесь...'
                : 'Перетащите ЭКГ файлы или нажмите для выбора'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Поддерживаются: PDF, SCP, XML, JPG, PNG
            </Typography>
          </Box>
          
          {uploadProgress > 0 && uploadProgress < 100 && (
            <Box sx={{ mt: 2 }}>
              {/* <LinearProgress variant="determinate" value={uploadProgress} /> */}
              <Progress variant="determinate" value={uploadProgress} />
              <Typography variant="caption" color="text.secondary">
                Загрузка: {uploadProgress}%
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Список загруженных ЭКГ */}
      {ecgFiles.length > 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Загруженные ЭКГ ({ecgFiles.length})
            </Typography>
            
            <List>
              {ecgFiles.map((file, index) => {
                const criticalParams = file.parameters 
                  ? getCriticalParameters(file.parameters)
                  : [];
                
                return (
                  <React.Fragment key={file.id}>
                    {index > 0 && <Divider />}
                    
                    <ListItem>
                      <ListItemIcon>
                        <FavoriteBorder color="error" />
                      </ListItemIcon>
                      
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="body1">
                              {file.name}
                            </Typography>
                            {criticalParams.length > 0 && (
                              // <Chip
                              //   size="small"
                              //   label="Внимание"
                              //   color="warning"
                              //   icon={<Warning />}
                              // />
                              <Badge variant="warning" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                                <AlertTriangle style={{ width: 14, height: 14 }} />
                                Внимание
                              </Badge>
                            )}
                          </Box>
                        }
                        secondary={
                          <Box>
                            <Typography variant="caption" color="text.secondary">
                              {formatFileSize(file.size)} • {new Date(file.uploadedAt).toLocaleString()}
                            </Typography>
                            
                            {file.parameters && (
                              <Box sx={{ mt: 1 }}>
                                <Grid container spacing={2}>
                                  <Grid item>
                                    {/* <Chip size="small" label={`ЧСС: ${file.parameters.heartRate} уд/мин`} /> */}
                                    <Badge variant={file.parameters.heartRate > 100 || file.parameters.heartRate < 60 ? 'warning' : 'info'}>
                                      ЧСС: {file.parameters.heartRate} уд/мин
                                    </Badge>
                                  </Grid>
                                  <Grid item>
                                    {/* <Chip size="small" label={`QT: ${file.parameters.qtInterval} мс`} /> */}
                                    <Badge variant={file.parameters.qtInterval > 450 ? 'warning' : 'info'}>
                                      QT: {file.parameters.qtInterval} мс
                                    </Badge>
                                  </Grid>
                                  <Grid item>
                                    {/* <Chip size="small" label={`PR: ${file.parameters.prInterval} мс`} /> */}
                                    <Badge variant={file.parameters.prInterval > 200 ? 'warning' : 'info'}>
                                      PR: {file.parameters.prInterval} мс
                                    </Badge>
                                  </Grid>
                                </Grid>
                                
                                {criticalParams.length > 0 && (
                                  <Alert severity="warning" sx={{ mt: 1 }}>
                                    <Typography variant="caption">
                                      Обнаружены отклонения:
                                    </Typography>
                                    {criticalParams.map((param, i) => (
                                      <Typography key={i} variant="caption" display="block">
                                        • {param.name}: {param.value}
                                      </Typography>
                                    ))}
                                  </Alert>
                                )}
                              </Box>
                            )}
                          </Box>
                        }
                      />
                      
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <IconButton
                          size="small"
                          onClick={() => openViewer(file)}
                          title="Просмотр"
                        >
                          <Visibility />
                        </IconButton>
                        
                        <IconButton
                          size="small"
                          onClick={() => analyzeECG(file)}
                          disabled={analyzing}
                          title="AI анализ"
                        >
                          <Analytics />
                        </IconButton>
                        
                        <IconButton
                          size="small"
                          component="a"
                          href={file.url}
                          download
                          title="Скачать"
                        >
                          <Download />
                        </IconButton>
                        
                        <IconButton
                          size="small"
                          onClick={() => deleteFile(file.id)}
                          title="Удалить"
                        >
                          <Delete />
                        </IconButton>
                      </Box>
                    </ListItem>
                  </React.Fragment>
                );
              })}
            </List>
          </CardContent>
        </Card>
      )}

      {/* AI анализ результат */}
      {analyzing && (
        <Card sx={{ mt: 2 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              {/* <LinearProgress sx={{ flex: 1 }} /> */}
              <Progress />
              <Typography variant="body2">
                Анализ ЭКГ с помощью AI...
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}
      
      {analysisResult && !analysisResult.error && (
        <Card sx={{ mt: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              <Assessment sx={{ mr: 1, verticalAlign: 'middle' }} />
              AI Интерпретация ЭКГ
            </Typography>
            
            <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
              {analysisResult.findings && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Основные находки:
                  </Typography>
                  {analysisResult.findings.map((finding, i) => (
                    // <Chip key={i} label={finding} />
                    <Badge
                      key={i}
                      variant={finding.includes('норма') ? 'success' : 'warning'}
                      style={{ marginRight: 8, marginBottom: 8, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                    >
                      {finding.includes('норма') ? (
                        <CheckCircleIcon style={{ width: 14, height: 14 }} />
                      ) : (
                        <AlertTriangle style={{ width: 14, height: 14 }} />
                      )}
                      {finding}
                    </Badge>
                  ))}
                </Box>
              )}
              
              {analysisResult.interpretation && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Интерпретация:
                  </Typography>
                  <Typography variant="body2">
                    {analysisResult.interpretation}
                  </Typography>
                </Box>
              )}
              
              {analysisResult.recommendations && (
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    Рекомендации:
                  </Typography>
                  <Typography variant="body2">
                    {analysisResult.recommendations}
                  </Typography>
                </Box>
              )}
              
              <Alert severity="info" sx={{ mt: 2 }}>
                <Typography variant="caption">
                  AI-анализ носит рекомендательный характер. 
                  Окончательное заключение делает врач.
                </Typography>
              </Alert>
            </Paper>
          </CardContent>
        </Card>
      )}

      {/* Диалог просмотра */}
      <Dialog
        open={viewerOpen}
        onClose={() => setViewerOpen(false)}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography variant="h6">
              {selectedFile?.name}
            </Typography>
            <Button 
              variant="outline" 
              onClick={() => setViewerOpen(false)}
              style={{ padding: '8px' }}
            >
              <X style={{ width: 16, height: 16 }} />
            </Button>
          </Box>
        </DialogTitle>
        
        <DialogContent>
          {selectedFile && (
            <Box>
              {/* Для PDF и изображений показываем превью */}
              {(selectedFile.type === 'application/pdf' || 
                selectedFile.type.startsWith('image/')) && (
                <Box sx={{ textAlign: 'center' }}>
                  {selectedFile.type === 'application/pdf' ? (
                    <iframe
                      src={selectedFile.url}
                      width="100%"
                      height="600px"
                      title="ECG PDF"
                    />
                  ) : (
                    <img
                      src={selectedFile.url}
                      alt="ECG"
                      style={{ maxWidth: '100%', height: 'auto' }}
                    />
                  )}
                </Box>
              )}
              
              {/* Параметры ЭКГ */}
              {ecgParameters && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="h6" gutterBottom>
                    Параметры ЭКГ
                  </Typography>
                  
                  <Grid container spacing={2}>
                    <Grid item xs={6} md={3}>
                      <Paper sx={{ p: 2 }}>
                        <Typography variant="caption" color="text.secondary">
                          Частота сердечных сокращений
                        </Typography>
                        <Typography variant="h6">
                          {ecgParameters.heartRate} уд/мин
                        </Typography>
                      </Paper>
                    </Grid>
                    
                    <Grid item xs={6} md={3}>
                      <Paper sx={{ p: 2 }}>
                        <Typography variant="caption" color="text.secondary">
                          Интервал PR
                        </Typography>
                        <Typography variant="h6">
                          {ecgParameters.prInterval} мс
                        </Typography>
                      </Paper>
                    </Grid>
                    
                    <Grid item xs={6} md={3}>
                      <Paper sx={{ p: 2 }}>
                        <Typography variant="caption" color="text.secondary">
                          Интервал QRS
                        </Typography>
                        <Typography variant="h6">
                          {ecgParameters.qrsInterval} мс
                        </Typography>
                      </Paper>
                    </Grid>
                    
                    <Grid item xs={6} md={3}>
                      <Paper sx={{ p: 2 }}>
                        <Typography variant="caption" color="text.secondary">
                          Интервал QT
                        </Typography>
                        <Typography variant="h6">
                          {ecgParameters.qtInterval} мс
                        </Typography>
                      </Paper>
                    </Grid>
                    
                    {ecgParameters.axis && (
                      <Grid item xs={12}>
                        <Paper sx={{ p: 2 }}>
                          <Typography variant="caption" color="text.secondary">
                            Электрическая ось сердца
                          </Typography>
                          <Typography variant="h6">
                            {ecgParameters.axis}°
                          </Typography>
                        </Paper>
                      </Grid>
                    )}
                  </Grid>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => analyzeECG(selectedFile)} disabled={analyzing}>
            AI Анализ
          </Button>
          <Button
            component="a"
            href={selectedFile?.url}
            download
            variant="contained"
          >
            Скачать
          </Button>
          <Button onClick={() => setViewerOpen(false)}>
            Закрыть
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ECGViewer;

