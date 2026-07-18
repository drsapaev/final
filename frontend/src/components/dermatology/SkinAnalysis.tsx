
/**
 * Skin Analysis Component
 * AI анализ состояния кожи
 * Согласно MASTER_TODO_LIST строка 268
 */
import { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Card,
  CardContent,
  Typography as TypographyRaw,
  Button as ButtonRaw,
  Alert as AlertRaw,
  Progress as ProgressRaw,
  Badge,
  CircularProgress as CircularProgressRaw,
} from '../ui/macos';
import {
  BarChart3,
  Smile,

  CheckCircle,
  TrendingUp,
  TrendingDown,
  Lightbulb,
  Flame,
  Droplets,
  Sun,
  Layers,
  Palette,
  Sparkles } from
'lucide-react';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";
const CircularProgressAny = CircularProgressRaw as unknown as React.ComponentType<Record<string, unknown>>;
const ProgressAny = ProgressRaw as unknown as React.ComponentType<Record<string, unknown>>;
const Button = ButtonRaw as unknown as React.ComponentType<Record<string, unknown>>;
const Typography = TypographyRaw as unknown as React.ComponentType<Record<string, unknown>>;
const Alert = AlertRaw as unknown as React.ComponentType<Record<string, unknown>>;
const SkinAnalysis = ({ photos, visitId, patientId, onAnalysisComplete }) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  useState(null);
  const [compareMode, setCompareMode] = useState(false);

  // Запуск AI анализа
  const startAnalysis = async (photoType = 'current') => {
    if (!photos || photos.length === 0) return;

    setAnalyzing(true);
    setAnalysisResult(null);

    try {
      const photoToAnalyze = photoType === 'before' ?
      photos.before?.[0] :
      photos.after?.[0] || photos.before?.[0];

      if (!photoToAnalyze) {
        throw new Error('Нет фото для анализа');
      }

      const response = await api.post('/ai/skin-analyze', {
        file_id: photoToAnalyze.id,
        visit_id: visitId,
        patient_id: patientId,
        analysis_type: photoType === 'before' ? 'initial' : 'follow-up',
        compare_with: compareMode && photos.before?.[0] ? photos.before[0].id : null
      });

      setAnalysisResult(response.data);
      onAnalysisComplete && onAnalysisComplete(response.data);

    } catch (error) {
      logger.error('Ошибка AI анализа:', error);
      setAnalysisResult({
        error: t('derma.derma_skin_error_analyze')
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
        analysis_type: 'comparative'
      });

      setAnalysisResult(response.data);
      onAnalysisComplete && onAnalysisComplete(response.data);

    } catch (error) {
      logger.error('Ошибка сравнительного анализа:', error);
      setAnalysisResult({
        error: t('derma.derma_skin_error_compare')
      });
    } finally {
      setAnalyzing(false);
    }
  };

  // Получение иконки для типа проблемы
  const getProblemIcon = (type) => {
    switch (type) {
      case 'acne':return <Flame style={{ color: 'var(--mac-accent-red)' }} />;
      case 'wrinkles':return <Layers style={{ color: 'var(--mac-accent-orange)' }} />;
      case 'pigmentation':return <Palette style={{ color: 'var(--mac-accent-blue)' }} />;
      case 'dryness':return <Droplets style={{ color: 'var(--mac-accent-blue)' }} />;
      case 'oiliness':return <Sun style={{ color: 'var(--mac-accent-orange)' }} />;
      default:return <Smile />;
    }
  };

  // Определение цвета для оценки
  const getScoreColor = (score) => {
    if (score >= 80) return 'success';
    if (score >= 60) return 'warning';
    return 'error';
  };

  // Рендер метрики
  const renderMetric = (label, value, icon, trend = null) =>
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
      {trend !== null &&
    <div style={{ marginTop: 8 }}>
          {trend > 0 ?
      <Badge
        variant="success"
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
        
              <TrendingUp style={{ width: 12, height: 12 }} />
              +{trend}%
            </Badge> :

      <Badge
        variant="danger"
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
        
              <TrendingDown style={{ width: 12, height: 12 }} />
              {trend}%
            </Badge>
      }
        </div>
    }
    </div>;


  if (!photos || (!photos.before || photos.before.length === 0) && (!photos.after || photos.after.length === 0)) {
    return (
      <Card>
        <CardContent>
          <Typography variant="body1" color="text.secondary" align="center">
            {t('derma.derma_skin_upload_hint')}
          </Typography>
        </CardContent>
      </Card>);

  }

  return (
    <Box>
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            <BarChart3 style={{ marginRight: 8, verticalAlign: 'middle' }} />
            {t('derma.derma_skin_title')}
          </Typography>

          {/* Кнопки анализа */}
          <div style={{ marginTop: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {photos.before && photos.before.length > 0 &&
            <Button
              variant="primary"
              onClick={() => startAnalysis('before')}
              disabled={analyzing}>
              
                <Sparkles style={{ width: 16, height: 16, marginRight: 8 }} />
                {t('derma.derma_skin_analyze_before')}
              </Button>
            }
            
            {photos.after && photos.after.length > 0 &&
            <Button
              variant="primary"
              onClick={() => startAnalysis('after')}
              disabled={analyzing}>
              
                <Sparkles style={{ width: 16, height: 16, marginRight: 8 }} />
                {t('derma.derma_skin_analyze_after')}
              </Button>
            }
            
            {photos.before?.length > 0 && photos.after?.length > 0 &&
            <Button
              variant="secondary"
              onClick={startComparativeAnalysis}
              disabled={analyzing}>
              
                <BarChart3 style={{ width: 16, height: 16, marginRight: 8 }} />
                {t('derma.derma_skin_compare')}
              </Button>
            }
          </div>

          {/* Прогресс анализа */}
          {analyzing &&
          <div style={{ marginTop: 24 }}>
              <ProgressAny />
              <Typography variant="body2" color="textSecondary" style={{ textAlign: 'center', marginTop: 8 }}>
                {t('derma.derma_skin_analyzing')}
              </Typography>
            </div>
          }

          {/* Результаты анализа */}
          {analysisResult && !analysisResult.error &&
          <div style={{ marginTop: 24 }}>
              {/* Общая оценка */}
              {analysisResult.overall_score !== undefined &&
            <div style={{ padding: 24, marginBottom: 24, textAlign: 'center', border: '1px solid var(--mac-border)', borderRadius: 8 }}>
                  <Typography variant="h6" gutterBottom>
                    {t('derma.derma_skin_overall_state')}
                  </Typography>
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 16 }}>
                    <CircularProgressAny
                  variant="determinate"
                  value={analysisResult.overall_score}
                  size={80 as unknown as "small" | "default" | "large" | "xlarge"}
                  thickness={"thick" as unknown as "thin" | "medium" | "thick"}
                  color={getScoreColor(analysisResult.overall_score)} />
                
                    <div>
                      <Typography variant="h3">
                        {analysisResult.overall_score}
                      </Typography>
                      <Typography variant="caption" color="textSecondary">
                        {t('derma.derma_skin_out_of')}
                      </Typography>
                    </div>
                  </div>
                  <Badge
                variant="primary"
                style={{ marginTop: 16 }}>
                
                    {analysisResult.skin_type || t('derma.derma_skin_default_type')}
                  </Badge>
                </div>
            }

              {/* Метрики */}
              {analysisResult.metrics &&
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 24 }}>
                  {renderMetric(
                t('derma.derma_skin_metric_hydration'),
                `${analysisResult.metrics.hydration || 0}%`,
                <Droplets style={{ color: 'var(--mac-accent-blue)' }} />,
                analysisResult.metrics.hydration_trend
              )}
                  {renderMetric(
                t('derma.derma_skin_metric_oiliness'),
                `${analysisResult.metrics.oiliness || 0}%`,
                <Sun style={{ color: 'var(--mac-accent-orange)' }} />,
                analysisResult.metrics.oiliness_trend
              )}
                  {renderMetric(
                t('derma.derma_skin_metric_texture'),
                `${analysisResult.metrics.texture || 0}%`,
                <Layers style={{ color: 'var(--mac-accent-blue)' }} />,
                analysisResult.metrics.texture_trend
              )}
                  {renderMetric(
                t('derma.derma_skin_metric_tone'),
                `${analysisResult.metrics.tone || 0}%`,
                <Palette style={{ color: 'var(--mac-accent-purple)' }} />,
                analysisResult.metrics.tone_trend
              )}
                </div>
            }

              {/* Обнаруженные проблемы */}
              {analysisResult.problems && analysisResult.problems.length > 0 &&
            <div style={{ padding: 16, marginBottom: 24, border: '1px solid var(--mac-border)', borderRadius: 8 }}>
                  <Typography variant="h6" gutterBottom>
                    {t('derma.derma_skin_problems_title')}
                  </Typography>
                  <div>
                    {analysisResult.problems.map((problem, index) =>
                <div key={index} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 16 }}>
                        <div style={{ marginTop: 4 }}>
                          {getProblemIcon(problem.type)}
                        </div>
                        <div style={{ flex: 1 }}>
                          <Typography variant="body1" style={{ fontWeight: 'var(--mac-font-weight-medium)' }}>
                            {problem.name}
                          </Typography>
                          <Typography variant="caption" color="textSecondary" style={{ display: 'block', marginTop: 4 }}>
                            {problem.description}
                          </Typography>
                          <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                            <Badge
                        variant={problem.severity === 'high' ? 'danger' : 'warning'}>
                        
                              {t('derma.derma_skin_severity_inline', { severity: problem.severity })}
                            </Badge>
                            {problem.area &&
                      <Badge variant="info">
                                {t('derma.derma_skin_zone_inline', { zone: problem.area })}
                              </Badge>
                      }
                          </div>
                        </div>
                      </div>
                )}
                  </div>
                </div>
            }

              {/* Улучшения (для сравнительного анализа) */}
              {analysisResult.improvements && analysisResult.improvements.length > 0 &&
            <Alert severity="success" style={{ marginBottom: 24 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    {t('derma.derma_skin_improvements_title')}
                  </Typography>
                  <div>
                    {analysisResult.improvements.map((improvement, index) =>
                <div key={index} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <CheckCircle style={{ width: 16, height: 16, color: 'var(--mac-accent-green)' }} />
                        <Typography variant="body2">{improvement}</Typography>
                      </div>
                )}
                  </div>
                </Alert>
            }

              {/* Рекомендации */}
              {analysisResult.recommendations && analysisResult.recommendations.length > 0 &&
            <div style={{ padding: 16, marginBottom: 24, border: '1px solid var(--mac-border)', borderRadius: 8 }}>
                  <Typography variant="h6" gutterBottom>
                    <Lightbulb style={{ marginRight: 8, verticalAlign: 'middle', color: 'var(--mac-accent-orange)' }} />
                    {t('derma.derma_skin_recommendations_title')}
                  </Typography>
                  <div>
                    {analysisResult.recommendations.map((rec, index) =>
                <div key={index} style={{ marginBottom: 16 }}>
                        <Typography variant="body1" style={{ fontWeight: 'var(--mac-font-weight-medium)', marginBottom: 8 }}>
                          {rec.title}
                        </Typography>
                        <Typography variant="body2" style={{ marginBottom: 8 }}>
                          {rec.description}
                        </Typography>
                        {rec.procedures && rec.procedures.length > 0 &&
                  <div style={{ marginTop: 8 }}>
                            <Typography variant="caption" color="textSecondary" style={{ display: 'block', marginBottom: 4 }}>
                              {t('derma.derma_skin_recommended_procedures')}
                            </Typography>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                              {rec.procedures.map((proc, i) =>
                      <Badge
                        key={i}
                        variant="info">
                        
                                  {proc}
                                </Badge>
                      )}
                            </div>
                          </div>
                  }
                        {index < analysisResult.recommendations.length - 1 &&
                  <div style={{ height: 1, backgroundColor: 'var(--mac-border)', margin: '16px 0' }} />
                  }
                      </div>
                )}
                  </div>
                </div>
            }

              {/* Рекомендуемый уход */}
              {analysisResult.care_routine &&
            <div style={{ padding: 16, border: '1px solid var(--mac-border)', borderRadius: 8 }}>
                  <Typography variant="h6" gutterBottom>
                    {t('derma.derma_skin_care_title')}
                  </Typography>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
                    {['morning', 'evening'].map((time) =>
                analysisResult.care_routine[time] &&
                <div key={time}>
                          <Typography variant="subtitle2" gutterBottom>
                            {time === 'morning' ? t('derma.derma_skin_morning_care') : t('derma.derma_skin_evening_care')}
                          </Typography>
                          <div>
                            {analysisResult.care_routine[time].map((step, index) =>
                    <div key={index} style={{ marginBottom: 8 }}>
                                <Typography variant="body2">
                                  {index + 1}. {step}
                                </Typography>
                              </div>
                    )}
                          </div>
                        </div>

                )}
                  </div>
                </div>
            }
            </div>
          }

          {/* Ошибка анализа */}
          {analysisResult?.error &&
          <Alert severity="error" style={{ marginTop: 16 }}>
              {analysisResult.error}
            </Alert>
          }
        </CardContent>
      </Card>
    </Box>);

};

SkinAnalysis.propTypes = {
  photos: PropTypes.object,
  visitId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  patientId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onAnalysisComplete: PropTypes.func
};

export default SkinAnalysis;
