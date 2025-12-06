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
  Alert,
  Progress,
  Badge,
  CircularProgress,
} from '../ui/macos';
import {
  BarChart3,
  Smile,
  AlertCircle,
  CheckCircle,
  TrendingUp,
  TrendingDown,
  Lightbulb,
  Flame,
  Droplets,
  Sun,
  Layers,
  Palette,
  Sparkles,
} from 'lucide-react';
import { api } from '../../api/client';

import logger from '../../utils/logger';
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
      logger.error('Ошибка AI анализа:', error);
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
      logger.error('Ошибка сравнительного анализа:', error);
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
      case 'acne': return <Flame style={{ color: 'var(--mac-accent-red)' }} />;
      case 'wrinkles': return <Layers style={{ color: 'var(--mac-accent-orange)' }} />;
      case 'pigmentation': return <Palette style={{ color: 'var(--mac-accent-blue)' }} />;
      case 'dryness': return <Droplets style={{ color: 'var(--mac-accent-blue)' }} />;
      case 'oiliness': return <Sun style={{ color: 'var(--mac-accent-orange)' }} />;
      default: return <Smile />;
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
    <div style={{ padding: 16, textAlign: 'center', border: '1px solid var(--mac-border)', borderRadius: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8 }}>
        {icon}
      </div>
      <Typography variant="h4" gutterBottom>
        {value}
      </Typography>
      <Typography variant="caption" color="textSecondary">
        {label}
      </Typography>
      {trend !== null && (
        <div style={{ marginTop: 8 }}>
          {trend > 0 ? (
            <Badge
              variant="success"
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}
            >
              <TrendingUp style={{ width: 12, height: 12 }} />
              +{trend}%
            </Badge>
          ) : (
            <Badge
              variant="danger"
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}
            >
              <TrendingDown style={{ width: 12, height: 12 }} />
              {trend}%
            </Badge>
          )}
        </div>
      )}
    </div>
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
            <BarChart3 style={{ marginRight: 8, verticalAlign: 'middle' }} />
            AI Анализ кожи
          </Typography>

          {/* Кнопки анализа */}
          <div style={{ marginTop: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {photos.before && photos.before.length > 0 && (
              <Button
                variant="primary"
                onClick={() => startAnalysis('before')}
                disabled={analyzing}
              >
                <Sparkles style={{ width: 16, height: 16, marginRight: 8 }} />
                Анализировать ДО
              </Button>
            )}
            
            {photos.after && photos.after.length > 0 && (
              <Button
                variant="primary"
                onClick={() => startAnalysis('after')}
                disabled={analyzing}
              >
                <Sparkles style={{ width: 16, height: 16, marginRight: 8 }} />
                Анализировать ПОСЛЕ
              </Button>
            )}
            
            {photos.before?.length > 0 && photos.after?.length > 0 && (
              <Button
                variant="secondary"
                onClick={startComparativeAnalysis}
                disabled={analyzing}
              >
                <BarChart3 style={{ width: 16, height: 16, marginRight: 8 }} />
                Сравнительный анализ
              </Button>
            )}
          </div>

          {/* Прогресс анализа */}
          {analyzing && (
            <div style={{ marginTop: 24 }}>
              <Progress />
              <Typography variant="body2" color="textSecondary" style={{ textAlign: 'center', marginTop: 8 }}>
                Анализ изображения с помощью AI...
              </Typography>
            </div>
          )}

          {/* Результаты анализа */}
          {analysisResult && !analysisResult.error && (
            <div style={{ marginTop: 24 }}>
              {/* Общая оценка */}
              {analysisResult.overall_score !== undefined && (
                <div style={{ padding: 24, marginBottom: 24, textAlign: 'center', border: '1px solid var(--mac-border)', borderRadius: 8 }}>
                  <Typography variant="h6" gutterBottom>
                    Общее состояние кожи
                  </Typography>
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 16 }}>
                    <CircularProgress
                      variant="determinate"
                      value={analysisResult.overall_score}
                      size={80}
                      thickness={4}
                      color={getScoreColor(analysisResult.overall_score)}
                    />
                    <div>
                      <Typography variant="h3">
                        {analysisResult.overall_score}
                      </Typography>
                      <Typography variant="caption" color="textSecondary">
                        из 100
                      </Typography>
                    </div>
                  </div>
                  <Badge
                    variant="primary"
                    style={{ marginTop: 16 }}
                  >
                    {analysisResult.skin_type || 'Нормальная кожа'}
                  </Badge>
                </div>
              )}

              {/* Метрики */}
              {analysisResult.metrics && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 24 }}>
                  {renderMetric(
                    'Увлажненность',
                    `${analysisResult.metrics.hydration || 0}%`,
                    <Droplets style={{ color: 'var(--mac-accent-blue)' }} />,
                    analysisResult.metrics.hydration_trend
                  )}
                  {renderMetric(
                    'Жирность',
                    `${analysisResult.metrics.oiliness || 0}%`,
                    <Sun style={{ color: 'var(--mac-accent-orange)' }} />,
                    analysisResult.metrics.oiliness_trend
                  )}
                  {renderMetric(
                    'Текстура',
                    `${analysisResult.metrics.texture || 0}%`,
                    <Layers style={{ color: 'var(--mac-accent-blue)' }} />,
                    analysisResult.metrics.texture_trend
                  )}
                  {renderMetric(
                    'Тон',
                    `${analysisResult.metrics.tone || 0}%`,
                    <Palette style={{ color: 'var(--mac-accent-purple)' }} />,
                    analysisResult.metrics.tone_trend
                  )}
                </div>
              )}

              {/* Обнаруженные проблемы */}
              {analysisResult.problems && analysisResult.problems.length > 0 && (
                <div style={{ padding: 16, marginBottom: 24, border: '1px solid var(--mac-border)', borderRadius: 8 }}>
                  <Typography variant="h6" gutterBottom>
                    Обнаруженные проблемы
                  </Typography>
                  <div>
                    {analysisResult.problems.map((problem, index) => (
                      <div key={index} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 16 }}>
                        <div style={{ marginTop: 4 }}>
                          {getProblemIcon(problem.type)}
                        </div>
                        <div style={{ flex: 1 }}>
                          <Typography variant="body1" style={{ fontWeight: 500 }}>
                            {problem.name}
                          </Typography>
                          <Typography variant="caption" color="textSecondary" style={{ display: 'block', marginTop: 4 }}>
                            {problem.description}
                          </Typography>
                          <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                            <Badge
                              variant={problem.severity === 'high' ? 'danger' : 'warning'}
                            >
                              Степень: {problem.severity}
                            </Badge>
                            {problem.area && (
                              <Badge variant="info">
                                Зона: {problem.area}
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Улучшения (для сравнительного анализа) */}
              {analysisResult.improvements && analysisResult.improvements.length > 0 && (
                <Alert severity="success" style={{ marginBottom: 24 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Положительные изменения:
                  </Typography>
                  <div>
                    {analysisResult.improvements.map((improvement, index) => (
                      <div key={index} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <CheckCircle style={{ width: 16, height: 16, color: 'var(--mac-accent-green)' }} />
                        <Typography variant="body2">{improvement}</Typography>
                      </div>
                    ))}
                  </div>
                </Alert>
              )}

              {/* Рекомендации */}
              {analysisResult.recommendations && analysisResult.recommendations.length > 0 && (
                <div style={{ padding: 16, marginBottom: 24, border: '1px solid var(--mac-border)', borderRadius: 8 }}>
                  <Typography variant="h6" gutterBottom>
                    <Lightbulb style={{ marginRight: 8, verticalAlign: 'middle', color: 'var(--mac-accent-orange)' }} />
                    Рекомендации
                  </Typography>
                  <div>
                    {analysisResult.recommendations.map((rec, index) => (
                      <div key={index} style={{ marginBottom: 16 }}>
                        <Typography variant="body1" style={{ fontWeight: 500, marginBottom: 8 }}>
                          {rec.title}
                        </Typography>
                        <Typography variant="body2" style={{ marginBottom: 8 }}>
                          {rec.description}
                        </Typography>
                        {rec.procedures && rec.procedures.length > 0 && (
                          <div style={{ marginTop: 8 }}>
                            <Typography variant="caption" color="textSecondary" style={{ display: 'block', marginBottom: 4 }}>
                              Рекомендуемые процедуры:
                            </Typography>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                              {rec.procedures.map((proc, i) => (
                                <Badge
                                  key={i}
                                  variant="info"
                                >
                                  {proc}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}
                        {index < analysisResult.recommendations.length - 1 && (
                          <div style={{ height: 1, backgroundColor: 'var(--mac-border)', margin: '16px 0' }} />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Рекомендуемый уход */}
              {analysisResult.care_routine && (
                <div style={{ padding: 16, border: '1px solid var(--mac-border)', borderRadius: 8 }}>
                  <Typography variant="h6" gutterBottom>
                    Домашний уход
                  </Typography>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
                    {['morning', 'evening'].map((time) => (
                      analysisResult.care_routine[time] && (
                        <div key={time}>
                          <Typography variant="subtitle2" gutterBottom>
                            {time === 'morning' ? 'Утренний уход' : 'Вечерний уход'}
                          </Typography>
                          <div>
                            {analysisResult.care_routine[time].map((step, index) => (
                              <div key={index} style={{ marginBottom: 8 }}>
                                <Typography variant="body2">
                                  {index + 1}. {step}
                                </Typography>
                              </div>
                            ))}
                          </div>
                        </div>
                      )
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Ошибка анализа */}
          {analysisResult?.error && (
            <Alert severity="error" style={{ marginTop: 16 }}>
              {analysisResult.error}
            </Alert>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default SkinAnalysis;

