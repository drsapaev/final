import React, { useState } from 'react';
import { Box, Card, CardContent, Typography, Alert, Badge, CircularProgress, Button } from '../../components/ui/macos';
import { ChevronDown, ChevronUp, Brain, AlertTriangle, CheckCircle, Info, Copy, RefreshCw } from 'lucide-react';
import { useSnackbar } from 'notistack';
import { apiClient } from '../../api/client';
import { mcpAPI } from '../../api/mcpClient';
import { sanitizeAIContent, sanitizeText } from '../../utils/sanitizer';
import logger from '../../utils/logger';

/**
 * Рекурсивная санитизация AI-generated контента
 * Защита от AI prompt injection attacks
 */
function sanitizeAIResponse(obj) {
  if (typeof obj === 'string') {
    return sanitizeAIContent(obj);
  }

  if (Array.isArray(obj)) {
    return obj.map(item => sanitizeAIResponse(item));
  }

  if (obj && typeof obj === 'object') {
    const sanitized = {};
    for (const [key, value] of Object.entries(obj)) {
      sanitized[key] = sanitizeAIResponse(value);
    }
    return sanitized;
  }

  return obj;
}

const AIAssistant = ({ 
  analysisType, 
  data, 
  onResult,
  title = 'AI Ассистент',
  expanded = true,
  useMCP = true,
  providerOptions = ['deepseek', 'gemini', 'openai', 'default']
}) => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [provider, setProvider] = useState('deepseek');
  const [retryCount, setRetryCount] = useState(0);
  const [isOpen, setIsOpen] = useState(expanded);
  const { enqueueSnackbar } = useSnackbar();

  const analyzeData = async (manualRetry = false) => {
    setLoading(true);
    setError(null);
    if (!manualRetry) {
      setResult(null);
      setRetryCount(0);
    }

    try {
      let response;
      let mcpResult;

      switch (analysisType) {
        case 'complaint':
          if (useMCP) {
            mcpResult = await mcpAPI.analyzeComplaint({
              complaint: data.complaint,
              patientAge: data.patient_age,
              patientGender: data.patient_gender,
              provider: provider
            });
            if (mcpResult.status === 'success') {
              response = { data: mcpResult.data };
            } else {
              throw new Error(mcpResult.error || 'MCP analysis failed');
            }
          } else {
            response = await apiClient.post('/api/v1/ai/complaint-to-plan', {
              ...data,
              provider,
              use_mcp: false
            });
          }
          break;

        case 'icd10':
          if (useMCP) {
            mcpResult = await mcpAPI.suggestICD10({
              symptoms: data.symptoms || [],
              diagnosis: data.diagnosis,
              specialty: data.specialty,
              provider: provider,
              maxSuggestions: data.maxSuggestions || 5
            });
            if (mcpResult.status === 'success') {
              if (mcpResult.data.clinical_recommendations) {
                response = { data: mcpResult.data };
              } else if (mcpResult.data.suggestions) {
                response = { data: mcpResult.data.suggestions };
              } else {
                response = { data: [] };
              }
            } else {
              throw new Error(mcpResult.error || 'MCP ICD10 suggestion failed');
            }
          } else {
            response = await apiClient.post('/api/v1/ai/icd-suggest', { ...data, provider });
          }
          break;

        case 'lab':
          if (useMCP) {
            mcpResult = await mcpAPI.interpretLabResults({
              results: data.results || data.lab_results,
              patientAge: data.patient_age,
              patientGender: data.patient_gender,
              provider: provider,
              includeRecommendations: true
            });
            if (mcpResult.status === 'success') {
              response = { data: mcpResult.data };
            } else {
              throw new Error(mcpResult.error || 'MCP lab interpretation failed');
            }
          } else {
            response = await apiClient.post('/api/v1/ai/lab-interpret', { ...data, provider });
          }
          break;

        case 'ecg':
          response = await apiClient.post('/api/v1/ai/ecg-interpret', { ...data, provider });
          break;

        case 'skin':
          if (useMCP && data.image) {
            mcpResult = await mcpAPI.analyzeSkinLesion(
              data.image,
              data.lesionInfo,
              data.patientHistory,
              provider
            );
            if (mcpResult.status === 'success') {
              response = { data: mcpResult.data };
            } else {
              throw new Error(mcpResult.error || 'MCP skin analysis failed');
            }
          } else {
            const formData = new FormData();
            formData.append('image', data.image);
            if (data.metadata) formData.append('metadata', JSON.stringify(data.metadata));
            formData.append('provider', provider);
            response = await apiClient.post('/api/v1/ai/skin-analyze', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
          }
          break;

        case 'imaging':
          if (useMCP && data.image) {
            mcpResult = await mcpAPI.analyzeImage(
              data.image,
              data.imageType || 'general',
              { modality: data.modality, clinicalContext: data.clinicalContext, provider: provider }
            );
            if (mcpResult.status === 'success') {
              response = { data: mcpResult.data };
            } else {
              throw new Error(mcpResult.error || 'MCP imaging analysis failed');
            }
          } else {
            throw new Error('Imaging analysis requires MCP mode');
          }
          break;

        default:
          throw new Error('Неизвестный тип анализа');
      }

      // Санитизируем AI-generated контент перед отображением (XSS защита)
      const sanitizedData = sanitizeAIResponse(response.data);
      setResult(sanitizedData);
      if (onResult) onResult(sanitizedData);
      enqueueSnackbar('AI анализ завершен', { variant: 'success' });
      logger.log('AI response sanitized and validated');
      setRetryCount(0);
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message;
      setError(errorMsg);
      enqueueSnackbar(`Ошибка AI анализа: ${errorMsg}`, { variant: 'error' });
      setRetryCount(prev => prev + 1);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    enqueueSnackbar('Скопировано в буфер обмена', { variant: 'info' });
  };

  const Pill = ({ children, color = 'default' }) => {
    const colors = {
      default: { border: 'var(--mac-border)', bg: 'transparent' },
      primary: { border: 'var(--mac-accent-blue)', bg: 'rgba(0,122,255,0.08)' },
      success: { border: 'rgba(52,199,89,0.45)', bg: 'rgba(52,199,89,0.08)' },
      warning: { border: 'rgba(255,149,0,0.45)', bg: 'rgba(255,149,0,0.08)' },
      error: { border: 'rgba(255,59,48,0.45)', bg: 'rgba(255,59,48,0.08)' },
      info: { border: 'rgba(0,122,255,0.45)', bg: 'rgba(0,122,255,0.08)' }
    }[color] || {};
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        border: `1px solid ${colors.border}`,
        background: colors.bg,
        padding: '4px 8px', borderRadius: 9999, fontSize: 12
      }}>{children}</span>
    );
  };

  const renderComplaintResult = () => {
    if (!result) return null;
    return (
      <div>
        {result.preliminary_diagnosis && (
          <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>Предварительные диагнозы:</Typography>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {result.preliminary_diagnosis.map((diagnosis, idx) => (
                <Pill key={idx} color="primary">{diagnosis}</Pill>
              ))}
            </div>
          </div>
        )}
        {result.examinations && result.examinations.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>План обследований:</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {result.examinations.map((exam, idx) => (
                <li key={idx}>
                  <span><CheckCircle style={{ width: 14, height: 14, marginRight: 6 }} />{`${exam.type}: ${exam.name}`}</span>
                  {exam.reason && (
                    <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>{exam.reason}</div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {result.lab_tests && result.lab_tests.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>Лабораторные анализы:</Typography>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {result.lab_tests.map((test, idx) => (
                <Pill key={idx}>{test}</Pill>
              ))}
            </div>
          </div>
        )}
        {result.red_flags && result.red_flags.length > 0 && (
          <Alert severity="warning" style={{ marginTop: 8 }}>
            <Typography variant="subtitle2" gutterBottom>Тревожные симптомы:</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {result.red_flags.map((flag, idx) => (<li key={idx}>{flag}</li>))}
            </ul>
          </Alert>
        )}
        {result.urgency && (
          <div style={{ marginTop: 8 }}>
            <Pill color={
              result.urgency === 'экстренно' ? 'error' :
              result.urgency === 'неотложно' ? 'warning' : 'info'
            }>
              Срочность: {result.urgency}
            </Pill>
          </div>
        )}
      </div>
    );
  };

  const renderICD10Result = () => {
    if (result && result.clinical_recommendations) {
      return (
        <div>
          <Alert severity="info" style={{ marginBottom: 12 }}>
            <Typography variant="body2" style={{ whiteSpace: 'pre-wrap' }}>
              {result.clinical_recommendations}
            </Typography>
          </Alert>
          {result.suggestions && result.suggestions.length > 0 && (
            <div>
              <Typography variant="subtitle2" gutterBottom>Коды МКБ-10:</Typography>
              <div>
                {result.suggestions.map((item, idx) => (
                  <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--mac-border)' }}>
                    <div>
                      {`${item.code} - ${item.name || item.description}`}
                      {item.relevance && (
                        <span style={{ marginLeft: 8 }}>
                          <Pill color={item.relevance === 'высокая' ? 'success' : item.relevance === 'средняя' ? 'warning' : 'default'}>
                            {item.relevance}
                          </Pill>
                        </span>
                      )}
                    </div>
                    <Button variant="outline" onClick={() => copyToClipboard(`${item.code} - ${item.name || item.description}`)}>
                      <Copy style={{ width: 14, height: 14, marginRight: 6 }} />Копировать
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      );
    }
    if (!result || !Array.isArray(result)) return null;
    return (
      <div>
        {result.map((item, idx) => (
          <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--mac-border)' }}>
            <div>
              {`${item.code} - ${item.name || item.description}`}
              {item.relevance && (
                <span style={{ marginLeft: 8 }}>
                  <Pill color={item.relevance === 'высокая' ? 'success' : item.relevance === 'средняя' ? 'warning' : 'default'}>
                    {item.relevance}
                  </Pill>
                </span>
              )}
            </div>
            <Button variant="outline" onClick={() => copyToClipboard(`${item.code} - ${item.name || item.description}`)}>
              <Copy style={{ width: 14, height: 14, marginRight: 6 }} />Копировать
            </Button>
          </div>
        ))}
      </div>
    );
  };

  const renderLabResult = () => {
    if (!result) return null;
    return (
      <div>
        {result.summary && (
          <Alert severity="info" style={{ marginBottom: 12 }}>
            <Typography variant="body2">{result.summary}</Typography>
          </Alert>
        )}
        {result.abnormal_values && result.abnormal_values.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>Отклонения от нормы:</Typography>
            {result.abnormal_values.map((item, idx) => (
              <details key={idx} open={idx === 0} style={{
                border: '1px solid var(--mac-border)', borderRadius: 8, padding: 12, marginBottom: 8
              }}>
                <summary style={{ cursor: 'pointer', listStyle: 'none' }}>
                  {item.parameter}: {item.value}
                </summary>
                <div style={{ marginTop: 8 }}>
                  <Typography variant="body2" gutterBottom><strong>Интерпретация:</strong> {item.interpretation}</Typography>
                  <Typography variant="body2"><strong>Клиническое значение:</strong> {item.clinical_significance}</Typography>
                </div>
              </details>
            ))}
          </div>
        )}
        {result.possible_conditions && result.possible_conditions.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>Возможные состояния:</Typography>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {result.possible_conditions.map((condition, idx) => (
                <Pill key={idx} color="warning">{condition}</Pill>
              ))}
            </div>
          </div>
        )}
        {result.recommendations && result.recommendations.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>Рекомендации:</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {result.recommendations.map((rec, idx) => (<li key={idx}>{rec}</li>))}
            </ul>
          </div>
        )}
        {result.urgency && (
          <Alert severity={result.urgency === 'да' ? 'warning' : 'info'} style={{ marginTop: 8 }}>
            Срочная консультация: {result.urgency}
          </Alert>
        )}
      </div>
    );
  };

  const renderECGResult = () => {
    if (!result) return null;
    return (
      <div>
        <div style={{ border: '1px solid var(--mac-border)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <Typography variant="subtitle2" gutterBottom>Основные параметры:</Typography>
          <div style={{ display: 'grid', gap: 6 }}>
            {result.rhythm && (<Typography variant="body2"><strong>Ритм:</strong> {result.rhythm}</Typography>)}
            {result.rate && (<Typography variant="body2"><strong>ЧСС:</strong> {result.rate}</Typography>)}
            {result.conduction && (<Typography variant="body2"><strong>Проводимость:</strong> {result.conduction}</Typography>)}
            {result.axis && (<Typography variant="body2"><strong>Электрическая ось:</strong> {result.axis}</Typography>)}
          </div>
        </div>
        {result.abnormalities && result.abnormalities.length > 0 && (
          <Alert severity="warning">
            <Typography variant="subtitle2" gutterBottom>Выявленные отклонения:</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {result.abnormalities.map((item, idx) => (<li key={idx}>{item}</li>))}
            </ul>
          </Alert>
        )}
        {result.interpretation && (
          <div style={{ border: '1px solid var(--mac-border)', borderRadius: 8, padding: 12, marginTop: 12 }}>
            <Typography variant="subtitle2" gutterBottom>Заключение:</Typography>
            <Typography variant="body2">{result.interpretation}</Typography>
          </div>
        )}
        {result.recommendations && result.recommendations.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <Typography variant="subtitle2" gutterBottom>Рекомендации:</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {result.recommendations.map((rec, idx) => (<li key={idx}>{rec}</li>))}
            </ul>
          </div>
        )}
        {result.urgency && (
          <Pill color={result.urgency === 'экстренно' ? 'error' : result.urgency === 'планово' ? 'info' : 'default'}>
            Консультация кардиолога: {result.urgency}
          </Pill>
        )}
      </div>
    );
  };

  const renderResult = () => {
    if (error) return <Alert severity="error">{error}</Alert>;
    if (!result) return null;
    switch (analysisType) {
      case 'complaint':
        return renderComplaintResult();
      case 'icd10':
        return renderICD10Result();
      case 'lab':
        return renderLabResult();
      case 'ecg':
        return renderECGResult();
      default:
        return (
          <div style={{ border: '1px solid var(--mac-border)', borderRadius: 8, padding: 12 }}>
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(result, null, 2)}</pre>
          </div>
        );
    }
  };

  return (
    <Card>
      <CardContent>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Brain style={{ color: 'var(--mac-accent-blue)' }} />
            <Typography variant="h6">{title}</Typography>
            {useMCP && (<Badge variant="success">MCP</Badge>)}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {providerOptions.map((prov) => (
                <Button key={prov} size="small" variant={provider === prov ? 'primary' : 'outline'} onClick={() => setProvider(prov)} disabled={loading}>
                  {prov.toUpperCase()}
                </Button>
              ))}
            </div>
            <Button size="small" variant="outline" onClick={() => analyzeData(true)} disabled={loading || !data}>
              <RefreshCw style={{ width: 14, height: 14, marginRight: 6 }} />
              Обновить
            </Button>
            <Button size="small" variant="outline" onClick={() => setIsOpen(v => !v)}>
              {isOpen ? <ChevronUp style={{ width: 14, height: 14 }} /> : <ChevronDown style={{ width: 14, height: 14 }} />}
            </Button>
          </div>
        </div>

        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 32 }}>
            <CircularProgress />
            <Typography variant="body2" color="textSecondary" style={{ marginTop: 8 }}>
              Анализ через {provider.toUpperCase()} AI...
            </Typography>
          </div>
        ) : (
          isOpen && renderResult()
        )}

        {!result && !loading && !error && (
          <Alert severity="info">Нажмите Обновить для запуска AI анализа</Alert>
        )}

        {error && retryCount > 0 && (
          <Alert severity="warning" style={{ marginTop: 8 }}>
            <Typography variant="body2">Попытка {retryCount}. Попробуйте сменить AI провайдер или повторить запрос.</Typography>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
};

export default AIAssistant;

