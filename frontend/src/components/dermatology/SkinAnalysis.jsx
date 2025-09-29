/**
 * Skin Analysis Component
 * AI анализ состояния кожи
 * Согласно MASTER_TODO_LIST строка 268
 */
import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Grid,
  Alert,
  LinearProgress,
  Chip,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Paper,
  Divider,
  Rating,
  CircularProgress,
} from '@mui/material';
import {
  Analytics,
  Face,
  Warning,
  CheckCircle,
  TrendingUp,
  TrendingDown,
  Lightbulb,
  LocalFireDepartment,
  WaterDrop,
  Brightness5,
  Texture,
  ColorLens,
  AutoFixHigh,
} from '@mui/icons-material';
import { api } from '../../api/client';

const SkinAnalysis = ({ photos, visitId, patientId, onAnalysisComplete }) => {
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [compareMode, setCompareMode] = useState(false);

  // Запуск AI анализа
  const startAnalysis = async (photoType = 'current') => {
    if (!photos || photos.length === 0) return;
    
    setAnalyzing(true);
    setAnalysisResult(null);
    
    try {
      const photoToAnalyze = photoType === 'before' 
        ? photos.before?.[0] 
        : photos.after?.[0] || photos.before?.[0];
      
      if (!photoToAnalyze) {
        throw new Error('Нет фото для анализа');
      }
      
      const response = await api.post('/ai/skin-analyze', {
        file_id: photoToAnalyze.id,
        visit_id: visitId,
        patient_id: patientId,
        analysis_type: photoType === 'before' ? 'initial' : 'follow-up',
        compare_with: compareMode && photos.before?.[0] ? photos.before[0].id : null,
      });
      
      setAnalysisResult(response.data);
      onAnalysisComplete && onAnalysisComplete(response.data);
      
    } catch (error) {
      console.error('Ошибка AI анализа:', error);
      setAnalysisResult({
        error: 'Не удалось проанализировать изображение',
      });
    } finally {
      setAnalyzing(false);
    }
  };

  // Сравнительный анализ
  const startComparativeAnalysis = async () => {
    if (!photos.before?.[0] || !photos.after?.[0]) return;
    
    setAnalyzing(true);
    setCompareMode(true);
    setAnalysisResult(null);
    
    try {
      const response = await api.post('/ai/skin-analyze', {
        before_file_id: photos.before[0].id,
        after_file_id: photos.after[0].id,
        visit_id: visitId,
        patient_id: patientId,
        analysis_type: 'comparative',
      });
      
      setAnalysisResult(response.data);
      onAnalysisComplete && onAnalysisComplete(response.data);
      
    } catch (error) {
      console.error('Ошибка сравнительного анализа:', error);
      setAnalysisResult({
        error: 'Не удалось выполнить сравнительный анализ',
      });
    } finally {
      setAnalyzing(false);
    }
  };

  // Получение иконки для типа проблемы
  const getProblemIcon = (type) => {
    switch (type) {
      case 'acne': return <LocalFireDepartment color="error" />;
      case 'wrinkles': return <Texture color="warning" />;
      case 'pigmentation': return <ColorLens color="action" />;
      case 'dryness': return <WaterDrop color="info" />;
      case 'oiliness': return <Brightness5 color="warning" />;
      default: return <Face />;
    }
  };

  // Определение цвета для оценки
  const getScoreColor = (score) => {
    if (score >= 80) return 'success';
    if (score >= 60) return 'warning';
    return 'error';
  };

  // Рендер метрики
  const renderMetric = (label, value, icon, trend = null) => (
    <Paper sx={{ p: 2, textAlign: 'center' }}>
      <Box sx={{ display: 'flex', justifyContent: 'center', mb: 1 }}>
        {icon}
      </Box>
      <Typography variant="h4" gutterBottom>
        {value}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      {trend !== null && (
        <Box sx={{ mt: 1 }}>
          {trend > 0 ? (
            <Chip
              size="small"
              label={`+${trend}%`}
              color="success"
              icon={<TrendingUp />}
            />
          ) : (
            <Chip
              size="small"
              label={`${trend}%`}
              color="error"
              icon={<TrendingDown />}
            />
          )}
        </Box>
      )}
    </Paper>
  );

  if (!photos || ((!photos.before || photos.before.length === 0) && (!photos.after || photos.after.length === 0))) {
    return (
      <Card>
        <CardContent>
          <Typography variant="body1" color="text.secondary" align="center">
            Загрузите фото для AI анализа состояния кожи
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Box>
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            <Analytics sx={{ mr: 1, verticalAlign: 'middle' }} />
            AI Анализ кожи
          </Typography>

          {/* Кнопки анализа */}
          <Box sx={{ mt: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            {photos.before && photos.before.length > 0 && (
              <Button
                variant="contained"
                startIcon={<AutoFixHigh />}
                onClick={() => startAnalysis('before')}
                disabled={analyzing}
              >
                Анализировать ДО
              </Button>
            )}
            
            {photos.after && photos.after.length > 0 && (
              <Button
                variant="contained"
                startIcon={<AutoFixHigh />}
                onClick={() => startAnalysis('after')}
                disabled={analyzing}
              >
                Анализировать ПОСЛЕ
              </Button>
            )}
            
            {photos.before?.length > 0 && photos.after?.length > 0 && (
              <Button
                variant="contained"
                color="secondary"
                startIcon={<Analytics />}
                onClick={startComparativeAnalysis}
                disabled={analyzing}
              >
                Сравнительный анализ
              </Button>
            )}
          </Box>

          {/* Прогресс анализа */}
          {analyzing && (
            <Box sx={{ mt: 3 }}>
              <LinearProgress />
              <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 1 }}>
                Анализ изображения с помощью AI...
              </Typography>
            </Box>
          )}

          {/* Результаты анализа */}
          {analysisResult && !analysisResult.error && (
            <Box sx={{ mt: 3 }}>
              {/* Общая оценка */}
              {analysisResult.overall_score !== undefined && (
                <Paper sx={{ p: 3, mb: 3, textAlign: 'center' }}>
                  <Typography variant="h6" gutterBottom>
                    Общее состояние кожи
                  </Typography>
                  <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 2 }}>
                    <CircularProgress
                      variant="determinate"
                      value={analysisResult.overall_score}
                      size={80}
                      thickness={4}
                      color={getScoreColor(analysisResult.overall_score)}
                    />
                    <Box>
                      <Typography variant="h3">
                        {analysisResult.overall_score}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        из 100
                      </Typography>
                    </Box>
                  </Box>
                  <Chip
                    label={analysisResult.skin_type || 'Нормальная кожа'}
                    color="primary"
                    sx={{ mt: 2 }}
                  />
                </Paper>
              )}

              {/* Метрики */}
              {analysisResult.metrics && (
                <Grid container spacing={2} sx={{ mb: 3 }}>
                  <Grid item xs={6} md={3}>
                    {renderMetric(
                      'Увлажненность',
                      `${analysisResult.metrics.hydration || 0}%`,
                      <WaterDrop color="info" />,
                      analysisResult.metrics.hydration_trend
                    )}
                  </Grid>
                  <Grid item xs={6} md={3}>
                    {renderMetric(
                      'Жирность',
                      `${analysisResult.metrics.oiliness || 0}%`,
                      <Brightness5 color="warning" />,
                      analysisResult.metrics.oiliness_trend
                    )}
                  </Grid>
                  <Grid item xs={6} md={3}>
                    {renderMetric(
                      'Текстура',
                      `${analysisResult.metrics.texture || 0}%`,
                      <Texture color="action" />,
                      analysisResult.metrics.texture_trend
                    )}
                  </Grid>
                  <Grid item xs={6} md={3}>
                    {renderMetric(
                      'Тон',
                      `${analysisResult.metrics.tone || 0}%`,
                      <ColorLens color="secondary" />,
                      analysisResult.metrics.tone_trend
                    )}
                  </Grid>
                </Grid>
              )}

              {/* Обнаруженные проблемы */}
              {analysisResult.problems && analysisResult.problems.length > 0 && (
                <Paper sx={{ p: 2, mb: 3 }}>
                  <Typography variant="h6" gutterBottom>
                    Обнаруженные проблемы
                  </Typography>
                  <List>
                    {analysisResult.problems.map((problem, index) => (
                      <ListItem key={index}>
                        <ListItemIcon>
                          {getProblemIcon(problem.type)}
                        </ListItemIcon>
                        <ListItemText
                          primary={problem.name}
                          secondary={
                            <Box>
                              <Typography variant="caption">
                                {problem.description}
                              </Typography>
                              <Box sx={{ mt: 1 }}>
                                <Chip
                                  size="small"
                                  label={`Степень: ${problem.severity}`}
                                  color={problem.severity === 'high' ? 'error' : 'warning'}
                                />
                                {problem.area && (
                                  <Chip
                                    size="small"
                                    label={`Зона: ${problem.area}`}
                                    sx={{ ml: 1 }}
                                  />
                                )}
                              </Box>
                            </Box>
                          }
                        />
                      </ListItem>
                    ))}
                  </List>
                </Paper>
              )}

              {/* Улучшения (для сравнительного анализа) */}
              {analysisResult.improvements && analysisResult.improvements.length > 0 && (
                <Alert severity="success" sx={{ mb: 3 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Положительные изменения:
                  </Typography>
                  <List dense>
                    {analysisResult.improvements.map((improvement, index) => (
                      <ListItem key={index}>
                        <ListItemIcon>
                          <CheckCircle color="success" />
                        </ListItemIcon>
                        <ListItemText primary={improvement} />
                      </ListItem>
                    ))}
                  </List>
                </Alert>
              )}

              {/* Рекомендации */}
              {analysisResult.recommendations && analysisResult.recommendations.length > 0 && (
                <Paper sx={{ p: 2, mb: 3 }}>
                  <Typography variant="h6" gutterBottom>
                    <Lightbulb sx={{ mr: 1, verticalAlign: 'middle', color: 'warning.main' }} />
                    Рекомендации
                  </Typography>
                  <List>
                    {analysisResult.recommendations.map((rec, index) => (
                      <React.Fragment key={index}>
                        {index > 0 && <Divider />}
                        <ListItem>
                          <ListItemText
                            primary={rec.title}
                            secondary={
                              <Box>
                                <Typography variant="body2" paragraph>
                                  {rec.description}
                                </Typography>
                                {rec.procedures && rec.procedures.length > 0 && (
                                  <Box sx={{ mt: 1 }}>
                                    <Typography variant="caption" color="text.secondary">
                                      Рекомендуемые процедуры:
                                    </Typography>
                                    <Box sx={{ mt: 0.5 }}>
                                      {rec.procedures.map((proc, i) => (
                                        <Chip
                                          key={i}
                                          label={proc}
                                          size="small"
                                          sx={{ mr: 0.5, mb: 0.5 }}
                                        />
                                      ))}
                                    </Box>
                                  </Box>
                                )}
                              </Box>
                            }
                          />
                        </ListItem>
                      </React.Fragment>
                    ))}
                  </List>
                </Paper>
              )}

              {/* Рекомендуемый уход */}
              {analysisResult.care_routine && (
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>
                    Домашний уход
                  </Typography>
                  <Grid container spacing={2}>
                    {['morning', 'evening'].map((time) => (
                      analysisResult.care_routine[time] && (
                        <Grid item xs={12} md={6} key={time}>
                          <Typography variant="subtitle2" gutterBottom>
                            {time === 'morning' ? 'Утренний уход' : 'Вечерний уход'}
                          </Typography>
                          <List dense>
                            {analysisResult.care_routine[time].map((step, index) => (
                              <ListItem key={index}>
                                <ListItemText
                                  primary={`${index + 1}. ${step}`}
                                />
                              </ListItem>
                            ))}
                          </List>
                        </Grid>
                      )
                    ))}
                  </Grid>
                </Paper>
              )}
            </Box>
          )}

          {/* Ошибка анализа */}
          {analysisResult?.error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {analysisResult.error}
            </Alert>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default SkinAnalysis;

