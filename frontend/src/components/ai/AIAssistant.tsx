import { useTranslation } from '../../i18n/useTranslation';
import { useState } from 'react';
import type { CSSProperties } from 'react';
import PropTypes from 'prop-types';
import {
  Card as RawCard, CardContent, Typography as RawTypography, Alert as RawAlert, Badge as RawBadge, CircularProgress as RawCircularProgress, Button as RawButton,
} from '../ui/macos';
const Card = RawCard as unknown as React.ComponentType<Record<string, unknown>>;
const Typography = RawTypography as unknown as React.ComponentType<Record<string, unknown>>;
const Alert = RawAlert as unknown as React.ComponentType<Record<string, unknown>>;
const Badge = RawBadge as unknown as React.ComponentType<Record<string, unknown>>;
const CircularProgress = RawCircularProgress as unknown as React.ComponentType<Record<string, unknown>>;
const Button = RawButton as unknown as React.ComponentType<Record<string, unknown>>;
import { ChevronDown, ChevronUp, Brain, CheckCircle, Copy, RefreshCw } from 'lucide-react';
import { notify } from '../../services/notify';
import { apiClient } from '../../api/client';
import { mcpAPI } from '../../api/mcpClient';
import { sanitizeAIContent } from '../../utils/sanitizer';
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
    return obj.map((item) => sanitizeAIResponse(item));
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

const AI_DRAFT_NOTICE = 'misc.aia_draft_notice';
const AI_PROVIDER_UNAVAILABLE_NOTICE = 'misc.aia_provider_unavailable_notice';

function getAIResponseError(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return null;
  }

  if (typeof payload.error === 'string' && payload.error.trim()) {
    return payload.error;
  }

  if (typeof payload.detail === 'string' && payload.detail.trim()) {
    return payload.detail;
  }

  return null;
}

function normalizeAIErrorMessage(message) {
  const rawMessage = String(message || '').trim();
  if (!rawMessage) {
    return null;
  }

  const lower = rawMessage.toLowerCase();
  if (
    lower.includes('no ai provider') ||
    lower.includes('provider available') ||
    lower.includes('api key') ||
    lower.includes('not configured')
  ) {
    return null;
  }

  return rawMessage;
}

function getResultProvider(value) {
  if (Array.isArray(value)) {
    for (const item of value) {
      const provider = getResultProvider(item);
      if (provider) return provider;
    }
    return null;
  }

  if (!value || typeof value !== 'object') {
    return null;
  }

  return value.provider || value.provider_used || value.model || value.source || null;
}

function isFallbackProvider(providerName) {
  const normalized = String(providerName || '').toLowerCase();
  return normalized === 'mock' || normalized === 'none' || normalized.includes('mock');
}

const AIAssistant = ({
  analysisType,
  data,
  onResult,
  title = 'misc.aia_title',
  expanded = true,
  useMCP = true,
  providerOptions = ['deepseek', 'gemini', 'openai', 'default'],
  // X-1 (UX audit): specialty + onSuggestionSelect — previously ignored by AIAssistant,
  // causing all 3 panels' AI tabs to be non-functional.
  specialty,
  onSuggestionSelect,
}) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [provider, setProvider] = useState('deepseek');
  const [retryCount, setRetryCount] = useState(0);
  const [isOpen, setIsOpen] = useState(expanded);

  // X-1 (UX audit): If specialty is provided, auto-configure analysisType and data
  // so the AI tab works without the parent having to pass analysisType explicitly.
  const effectiveAnalysisType = analysisType || (specialty ? 'icd10' : undefined);
  const effectiveData = data || (specialty ? {
    complaint: '',
    specialty: specialty,
    patient_age: null,
    patient_gender: null,
  } : undefined);

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

      switch (effectiveAnalysisType) {
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
          throw new Error(t('misc.aia_unknown_type'));
      }

      // Санитизируем AI-generated контент перед отображением (XSS защита)
      const responseError = getAIResponseError(response?.data);
      if (responseError) {
        throw new Error(responseError);
      }

      const sanitizedData = sanitizeAIResponse(response.data);
      setResult(sanitizedData);
      if (onResult) onResult(sanitizedData);
      notify.success(t('misc.aia_analysis_done'));
      logger.log('AI response sanitized and validated');
      setRetryCount(0);
    } catch (err) {
      const errorMsg = normalizeAIErrorMessage(
        err.response?.data?.detail || err.response?.data?.error || err.message
      );
      setError(errorMsg);
      notify.error(t('misc.aia_analysis_error', { message: errorMsg }));
      setRetryCount((prev) => prev + 1);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    notify.info(t('final.copied_to_clipboard'));
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
        padding: 'var(--mac-spacing-1) var(--mac-spacing-2)', borderRadius: 9999, fontSize: 12
      }}>{children}</span>);

  };
  Pill.propTypes = {
    children: PropTypes.node,
    color: PropTypes.string
  };

  const renderComplaintResult = () => {
    if (!result) return null;
    return (
      <div>
        {result.preliminary_diagnosis &&
        <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_preliminary_dx')}</Typography>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {result.preliminary_diagnosis.map((diagnosis, idx) =>
            <Pill key={idx} color="primary">{diagnosis}</Pill>
            )}
            </div>
          </div>
        }
        {result.examinations && result.examinations.length > 0 &&
        <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_exam_plan')}</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {result.examinations.map((exam, idx) =>
            <li key={idx}>
                  <span><CheckCircle style={{ width: 14, height: 14, marginRight: 6 }} />{`${exam.type}: ${exam.name}`}</span>
                  {exam.reason &&
              <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>{exam.reason}</div>
              }
                </li>
            )}
            </ul>
          </div>
        }
        {result.lab_tests && result.lab_tests.length > 0 &&
        <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_lab_tests')}</Typography>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {result.lab_tests.map((test, idx) =>
            <Pill key={idx}>{test}</Pill>
            )}
            </div>
          </div>
        }
        {result.red_flags && result.red_flags.length > 0 &&
        <Alert severity="warning" style={{ marginTop: 8 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_red_flags')}</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {result.red_flags.map((flag, idx) => <li key={idx}>{flag}</li>)}
            </ul>
          </Alert>
        }
        {result.urgency &&
        <div style={{ marginTop: 8 }}>
            <Pill color={
          result.urgency === t('misc.aia_urgency_emergency') ? 'error' :
          result.urgency === t('misc.aia_urgency_urgent') ? 'warning' : 'info'
          }>
              {t('misc.aia_urgency_label')} {result.urgency}
            </Pill>
          </div>
        }
      </div>);

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
          {result.suggestions && result.suggestions.length > 0 &&
          <div>
              <Typography variant="subtitle2" gutterBottom>{t('misc.aia_icd10_codes')}</Typography>
              <div>
                {result.suggestions.map((item, idx) =>
              <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 'var(--mac-spacing-2) 0', borderBottom: '1px solid var(--mac-border)' }}>
                    <div>
                      {`${item.code} - ${item.name || item.description}`}
                      {item.relevance &&
                  <span style={{ marginLeft: 8 }}>
                          <Pill color={item.relevance === t('misc.aia_relevance_high') ? 'success' : item.relevance === t('misc.aia_relevance_medium') ? 'warning' : 'default'}>
                            {item.relevance}
                          </Pill>
                        </span>
                  }
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--mac-spacing-1)' }}>
                    <Button variant="outline" onClick={() => copyToClipboard(`${item.code} - ${item.name || item.description}`)}>
                      <Copy style={{ width: 14, height: 14, marginRight: 6 }} />{t('misc.aia_copy')}
                    </Button>
                    {onSuggestionSelect && (
                    <Button variant="primary" onClick={() => {
                      onSuggestionSelect('icd10', item.code);
                      notify.success(t('final.icd_added_to_form'));
                    }}>
                      <CheckCircle style={{ width: 14, height: 14, marginRight: 6 }} />{t('misc.aia_use')}
                    </Button>
                    )}
                    </div>
                  </div>
              )}
              </div>
            </div>
          }
        </div>);

    }
    if (!result || !Array.isArray(result)) return null;
    return (
      <div>
        {result.map((item, idx) =>
        <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 'var(--mac-spacing-2) 0', borderBottom: '1px solid var(--mac-border)' }}>
            <div>
              {`${item.code} - ${item.name || item.description}`}
              {item.relevance &&
            <span style={{ marginLeft: 8 }}>
                  <Pill color={item.relevance === t('misc.aia_relevance_high') ? 'success' : item.relevance === t('misc.aia_relevance_medium') ? 'warning' : 'default'}>
                    {item.relevance}
                  </Pill>
                </span>
            }
            </div>
            <div style={{ display: 'flex', gap: 'var(--mac-spacing-1)' }}>
            <Button variant="outline" onClick={() => copyToClipboard(`${item.code} - ${item.name || item.description}`)}>
              <Copy style={{ width: 14, height: 14, marginRight: 6 }} />{t('misc.aia_copy')}
            </Button>
            {onSuggestionSelect && (
            <Button variant="primary" onClick={() => {
              onSuggestionSelect('icd10', item.code);
              notify.success(t('final.icd_added_to_form'));
            }}>
              <CheckCircle style={{ width: 14, height: 14, marginRight: 6 }} />{t('misc.aia_use')}
            </Button>
            )}
            </div>
          </div>
        )}
      </div>);

  };

  const renderLabResult = () => {
    if (!result) return null;
    return (
      <div>
        {result.summary &&
        <Alert severity="info" style={{ marginBottom: 12 }}>
            <Typography variant="body2">{result.summary}</Typography>
          </Alert>
        }
        {result.abnormal_values && result.abnormal_values.length > 0 &&
        <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_abnormal_values')}</Typography>
            {result.abnormal_values.map((item, idx) =>
          <details key={idx} open={idx === 0} style={{
            border: '1px solid var(--mac-border)', borderRadius: 8, padding: 12, marginBottom: 8
          }}>
                <summary style={{ cursor: 'pointer', listStyle: 'none' }}>
                  {item.parameter}: {item.value}
                </summary>
                <div style={{ marginTop: 8 }}>
                  <Typography variant="body2" gutterBottom><strong>{t('misc.aia_interpretation')}</strong> {item.interpretation}</Typography>
                  <Typography variant="body2"><strong>{t('misc.aia_clinical_significance')}</strong> {item.clinical_significance}</Typography>
                </div>
              </details>
          )}
          </div>
        }
        {result.possible_conditions && result.possible_conditions.length > 0 &&
        <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_possible_conditions')}</Typography>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {result.possible_conditions.map((condition, idx) =>
            <Pill key={idx} color="warning">{condition}</Pill>
            )}
            </div>
          </div>
        }
        {result.recommendations && result.recommendations.length > 0 &&
        <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_recommendations')}</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {result.recommendations.map((rec, idx) => <li key={idx}>{rec}</li>)}
            </ul>
          </div>
        }
        {result.urgency &&
        <Alert severity={result.urgency === t('misc.aia_yes') ? 'warning' : 'info'} style={{ marginTop: 8 }}>
            {t('misc.aia_urgent_consultation')}: {result.urgency}
          </Alert>
        }
      </div>);

  };

  const renderECGResult = () => {
    if (!result) return null;
    return (
      <div>
        <div style={{ border: '1px solid var(--mac-border)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <Typography variant="subtitle2" gutterBottom>{t('misc.aia_main_params')}</Typography>
          <div style={{ display: 'grid', gap: 6 }}>
            {result.rhythm && <Typography variant="body2"><strong>{t('misc.aia_rhythm')}</strong> {result.rhythm}</Typography>}
            {result.rate && <Typography variant="body2"><strong>{t('misc.aia_hr')}</strong> {result.rate}</Typography>}
            {result.conduction && <Typography variant="body2"><strong>{t('misc.aia_conduction')}</strong> {result.conduction}</Typography>}
            {result.axis && <Typography variant="body2"><strong>{t('misc.aia_axis')}</strong> {result.axis}</Typography>}
          </div>
        </div>
        {result.abnormalities && result.abnormalities.length > 0 &&
        <Alert severity="warning">
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_abnormalities')}</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {result.abnormalities.map((item, idx) => <li key={idx}>{item}</li>)}
            </ul>
          </Alert>
        }
        {result.interpretation &&
        <div style={{ border: '1px solid var(--mac-border)', borderRadius: 8, padding: 12, marginTop: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_conclusion')}</Typography>
            <Typography variant="body2">{result.interpretation}</Typography>
          </div>
        }
        {result.recommendations && result.recommendations.length > 0 &&
        <div style={{ marginTop: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_recommendations')}</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {result.recommendations.map((rec, idx) => <li key={idx}>{rec}</li>)}
            </ul>
          </div>
        }
        {result.urgency &&
        <Pill color={result.urgency === t('misc.aia_urgency_emergency') ? 'error' : result.urgency === t('misc.aia_urgency_planned') ? 'info' : 'default'}>
            {t('misc.aia_cardio_consultation')}: {result.urgency}
          </Pill>
        }
      </div>);

  };

  const renderResult = () => {
    if (error) return <Alert severity="error">{error}</Alert>;
    if (!result) return null;
    switch (effectiveAnalysisType) {
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
          </div>);

    }
  };

  const resultProvider = getResultProvider(result);
  const usesFallbackProvider = isFallbackProvider(resultProvider);
  const usesServerDefaultProvider = provider === 'default';

  return (
    <Card>
      <CardContent>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Brain style={{ color: 'var(--mac-accent-blue)' }} />
            <Typography variant="h6">{typeof title === 'string' && title.startsWith('misc.') ? t(title) : title}</Typography>
            {useMCP && <Badge variant="success">MCP</Badge>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {providerOptions.map((prov) =>
              <Button key={prov} size="small" variant={provider === prov ? 'primary' : 'outline'} onClick={() => setProvider(prov)} disabled={loading}>
                  {prov.toUpperCase()}
                </Button>
              )}
            </div>
            <Button size="small" variant="outline" onClick={() => analyzeData(true)} disabled={loading || !data}>
              <RefreshCw style={{ width: 14, height: 14, marginRight: 6 }} />
              {t('misc.aia_refresh')}
            </Button>
            <Button
              type="button"
              size="small"
              variant="outline"
              title={isOpen ? 'Collapse AI assistant details' : 'Expand AI assistant details'}
              aria-label={isOpen ? 'Collapse AI assistant details' : 'Expand AI assistant details'}
              onClick={() => setIsOpen((v) => !v)}
            >
              {isOpen ? <ChevronUp style={{ width: 14, height: 14 }} /> : <ChevronDown style={{ width: 14, height: 14 }} />}
            </Button>
          </div>
        </div>

        {isOpen &&
        <div style={{ display: 'grid', gap: 8, marginBottom: 12 }}>
            <Alert severity="warning">
              <Typography variant="body2">{t(AI_DRAFT_NOTICE)}</Typography>
            </Alert>
            {usesServerDefaultProvider && !usesFallbackProvider &&
            <Alert severity="info">
                <Typography variant="body2">
                  {t('misc.aia_default_provider_notice')}
                </Typography>
              </Alert>
            }
            {usesFallbackProvider &&
            <Alert severity="info">
                <Typography variant="body2">
                  {t('misc.aia_fallback_provider_notice', { provider: String(resultProvider).toUpperCase() })}
                </Typography>
              </Alert>
            }
          </div>
        }

        {loading ?
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 32 }}>
            <CircularProgress />
            <Typography variant="body2" color="textSecondary" style={{ marginTop: 8 }}>
              {t('misc.aia_analyzing_via', { provider: provider.toUpperCase() })}
            </Typography>
          </div> :

        isOpen && renderResult()
        }

        {!result && !loading && !error &&
        <Alert severity="info">{t('misc.aia_click_refresh')}</Alert>
        }

        {error && retryCount > 0 &&
        <Alert severity="warning" style={{ marginTop: 8 }}>
            <Typography variant="body2">{t('misc.aia_retry_attempt', { count: retryCount })}</Typography>
          </Alert>
        }
      </CardContent>
    </Card>);

};

AIAssistant.propTypes = {
  analysisType: PropTypes.string,
  data: PropTypes.object,
  onResult: PropTypes.func,
  title: PropTypes.string,
  expanded: PropTypes.bool,
  useMCP: PropTypes.bool,
  providerOptions: PropTypes.array,
  // X-1 (UX audit): new props for specialty-scoped AI integration
  specialty: PropTypes.string,
  onSuggestionSelect: PropTypes.func,
};

export default AIAssistant;
