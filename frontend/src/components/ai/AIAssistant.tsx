import { useTranslation } from '../../i18n/useTranslation';
import { useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import {
  Card, CardContent, Typography, Alert, Badge, CircularProgress, Button,
} from '../ui/macos';
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
function sanitizeAIResponse(obj: unknown): unknown {
  if (typeof obj === 'string') {
    return sanitizeAIContent(obj);
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => sanitizeAIResponse(item));
  }

  if (obj && typeof obj === 'object') {
    const sanitized: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj)) {
      sanitized[key] = sanitizeAIResponse(value);
    }
    return sanitized;
  }

  return obj;
}

const AI_DRAFT_NOTICE = 'misc.aia_draft_notice';
const AI_PROVIDER_UNAVAILABLE_NOTICE = 'misc.aia_provider_unavailable_notice';

/**
 * Minimal shape of an MCP client response envelope. The MCP client returns
 * `Promise<unknown>`, but every method resolves to an object with optional
 * status/error/data fields — captured here so the assistant can read them
 * without resorting to `any`.
 */
interface McpResultDto {
  status?: string;
  error?: string;
  data?: Record<string, unknown>;
}

/**
 * AI analysis result returned by the backend / MCP layer. The shape is
 * dynamic (complaint / icd10 / lab / ecg variants) so we keep it as an
 * index-signature object; the icd10 path also accepts a plain array of
 * suggestions, hence the union with `unknown[]`.
 */
type AIResult = Record<string, unknown> | unknown[];

/** Type guard: narrows `AIResult | null` to the object variant. */
function isResultObject(value: AIResult | null | undefined): value is Record<string, unknown> {
  return !!value && !Array.isArray(value);
}

function getAIResponseError(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return null;
  }

  const p = payload as Record<string, unknown>;
  if (typeof p.error === 'string' && p.error.trim()) {
    return p.error;
  }

  if (typeof p.detail === 'string' && p.detail.trim()) {
    return p.detail;
  }

  return null;
}

function normalizeAIErrorMessage(message: unknown): string | null {
  const rawMessage = String(message ?? '').trim();
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

function getResultProvider(value: unknown): string | null {
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

  const v = value as Record<string, unknown>;
  const provider = v.provider ?? v.provider_used ?? v.model ?? v.source;
  return typeof provider === 'string' ? provider : null;
}

function isFallbackProvider(providerName: unknown): boolean {
  const normalized = String(providerName ?? '').toLowerCase();
  return normalized === 'mock' || normalized === 'none' || normalized.includes('mock');
}

/**
 * Extracts `{ detail?, error? }` from an axios-like error response without
 * requiring the caller to assert on `unknown`. Used by the catch-block in
 * `analyzeData` to surface backend error messages.
 */
function getErrResponseData(err: unknown): { detail?: string; error?: string } | undefined {
  if (!err || typeof err !== 'object') return undefined;
  const maybeResponse = (err as { response?: unknown }).response;
  if (!maybeResponse || typeof maybeResponse !== 'object') return undefined;
  const data = (maybeResponse as { data?: unknown }).data;
  if (!data || typeof data !== 'object') return undefined;
  return data as { detail?: string; error?: string };
}

interface AIAssistantProps {
  analysisType?: string;
  data?: Record<string, unknown>;
  onResult?: (result: unknown) => void;
  title?: string;
  expanded?: boolean;
  useMCP?: boolean;
  providerOptions?: string[];
  specialty?: string;
  onSuggestionSelect?: (type: string, suggestion: unknown) => void;
}

const AIAssistant = ({
  analysisType,
  data,
  onResult,
  title = 'misc.aia_title',
  expanded = true,
  useMCP = true,
  providerOptions = ['deepseek', 'gemini', 'openai', 'default'],
  specialty,
  onSuggestionSelect,
}: AIAssistantProps) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AIResult | null>(null);
  const [error, setError] = useState<string | null>(null);
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
    if (!data) return;
    setLoading(true);
    setError(null);
    if (!manualRetry) {
      setResult(null);
      setRetryCount(0);
    }

    try {
      let response: { data?: unknown } | undefined;
      let mcpResult: McpResultDto | undefined;

      switch (effectiveAnalysisType) {
        case 'complaint':
          if (useMCP) {
            mcpResult = await mcpAPI.analyzeComplaint({
              complaint: data.complaint,
              patientAge: data.patient_age,
              patientGender: data.patient_gender,
              provider: provider
            }) as McpResultDto;
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
            }) as McpResultDto;
            if (mcpResult.status === 'success') {
              if (mcpResult.data?.clinical_recommendations) {
                response = { data: mcpResult.data };
              } else if (mcpResult.data?.suggestions) {
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
            }) as McpResultDto;
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
              data.image as File | Blob,
              data.lesionInfo as Record<string, unknown> | null,
              data.patientHistory as Record<string, unknown> | null,
              provider
            ) as McpResultDto;
            if (mcpResult.status === 'success') {
              response = { data: mcpResult.data };
            } else {
              throw new Error(mcpResult.error || 'MCP skin analysis failed');
            }
          } else {
            const formData = new FormData();
            formData.append('image', data.image as Blob);
            if (data.metadata) formData.append('metadata', JSON.stringify(data.metadata));
            formData.append('provider', provider);
            response = await apiClient.post('/api/v1/ai/skin-analyze', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
          }
          break;

        case 'imaging':
          if (useMCP && data.image) {
            mcpResult = await mcpAPI.analyzeImage(
              data.image as File,
              (data.imageType as string) || 'general',
              { modality: data.modality, clinicalContext: data.clinicalContext, provider: provider }
            ) as McpResultDto;
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

      const sanitizedData = sanitizeAIResponse(response?.data) as AIResult;
      setResult(sanitizedData);
      if (onResult) onResult(sanitizedData);
      notify.success(t('misc.aia_analysis_done'));
      logger.log('AI response sanitized and validated');
      setRetryCount(0);
    } catch (err: unknown) {
      const errData = getErrResponseData(err);
      const errorMsg = normalizeAIErrorMessage(
        errData?.detail || errData?.error || (err instanceof Error ? err.message : String(err))
      );
      setError(errorMsg);
      notify.error(t('misc.aia_analysis_error', { message: errorMsg }));
      setRetryCount((prev) => prev + 1);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    notify.info(t('final.copied_to_clipboard'));
  };

  interface PillProps {
    children?: ReactNode;
    color?: string;
  }
  const Pill = ({ children, color = 'default' }: PillProps) => {
    const colors: { border?: string; bg?: string } = {
      default: { border: 'var(--mac-border)', bg: 'transparent' },
      primary: { border: 'var(--mac-accent-blue)', bg: 'rgba(0,122,255,0.08)' },
      success: { border: 'rgba(52,199,89,0.45)', bg: 'rgba(52,199,89,0.08)' },
      warning: { border: 'rgba(255,149,0,0.45)', bg: 'rgba(255,149,0,0.08)' },
      error: { border: 'rgba(255,59,48,0.45)', bg: 'rgba(255,59,48,0.08)' },
      info: { border: 'rgba(0,122,255,0.45)', bg: 'rgba(0,122,255,0.08)' }
    }[color || 'default'] || {};
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        border: `1px solid ${colors.border}`,
        background: colors.bg,
        padding: 'var(--mac-spacing-1) var(--mac-spacing-2)', borderRadius: 9999, fontSize: 12
      }}>{children}</span>);

  };

  const renderComplaintResult = () => {
    if (!isResultObject(result)) return null;
    const resultObj = result;
    return (
      <div>
        {Array.isArray(resultObj.preliminary_diagnosis) && resultObj.preliminary_diagnosis.length > 0 &&
        <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_preliminary_dx')}</Typography>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {resultObj.preliminary_diagnosis.map((diagnosis: unknown, idx: number) =>
            <Pill key={idx} color="primary">{String(diagnosis ?? '')}</Pill>
            )}
            </div>
          </div>
        }
        {Array.isArray(resultObj.examinations) && resultObj.examinations.length > 0 &&
        <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_exam_plan')}</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {resultObj.examinations.map((exam: unknown, idx: number) => {
            const examObj = (exam ?? null) as Record<string, unknown> | null;
            return (
              <li key={idx}>
                  <span><CheckCircle style={{ width: 14, height: 14, marginRight: 6 }} />{`${String(examObj?.type ?? '')}: ${String(examObj?.name ?? '')}`}</span>
                  {Boolean(examObj?.reason) &&
              <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>{String(examObj?.reason ?? '')}</div>
              }
                </li>
            );
          })}
            </ul>
          </div>
        }
        {Array.isArray(resultObj.lab_tests) && resultObj.lab_tests.length > 0 &&
        <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_lab_tests')}</Typography>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {resultObj.lab_tests.map((test: unknown, idx: number) =>
            <Pill key={idx}>{String(test ?? '')}</Pill>
            )}
            </div>
          </div>
        }
        {Array.isArray(resultObj.red_flags) && resultObj.red_flags.length > 0 &&
        <Alert severity="warning" style={{ marginTop: 8 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_red_flags')}</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {resultObj.red_flags.map((flag: unknown, idx: number) => <li key={idx}>{String(flag ?? '')}</li>)}
            </ul>
          </Alert>
        }
        {Boolean(resultObj.urgency) &&
        <div style={{ marginTop: 8 }}>
            <Pill color={
          resultObj.urgency === t('misc.aia_urgency_emergency') ? 'error' :
          resultObj.urgency === t('misc.aia_urgency_urgent') ? 'warning' : 'info'
          }>
              {t('misc.aia_urgency_label')} {String(resultObj.urgency ?? '')}
            </Pill>
          </div>
        }
      </div>);

  };

  const renderICD10Result = () => {
    if (isResultObject(result) && result.clinical_recommendations) {
      const resultObj = result;
      return (
        <div>
          <Alert severity="info" style={{ marginBottom: 12 }}>
            <Typography variant="body2" style={{ whiteSpace: 'pre-wrap' }}>
              {String(resultObj.clinical_recommendations ?? '')}
            </Typography>
          </Alert>
          {Array.isArray(resultObj.suggestions) && resultObj.suggestions.length > 0 &&
          <div>
              <Typography variant="subtitle2" gutterBottom>{t('misc.aia_icd10_codes')}</Typography>
              <div>
                {resultObj.suggestions.map((item: unknown, idx: number) => {
                  const itemObj = (item ?? null) as Record<string, unknown> | null;
                  return (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 'var(--mac-spacing-2) 0', borderBottom: '1px solid var(--mac-border)' }}>
                    <div>
                      {`${String(itemObj?.code ?? '')} - ${String(itemObj?.name ?? itemObj?.description ?? '')}`}
                      {Boolean(itemObj?.relevance) &&
                  <span style={{ marginLeft: 8 }}>
                          <Pill color={itemObj?.relevance === t('misc.aia_relevance_high') ? 'success' : itemObj?.relevance === t('misc.aia_relevance_medium') ? 'warning' : 'default'}>
                            {String(itemObj?.relevance ?? '')}
                          </Pill>
                        </span>
                  }
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--mac-spacing-1)' }}>
                    <Button variant="outline" onClick={() => copyToClipboard(`${String(itemObj?.code ?? '')} - ${String(itemObj?.name ?? itemObj?.description ?? '')}`)}>
                      <Copy style={{ width: 14, height: 14, marginRight: 6 }} />{t('misc.aia_copy')}
                    </Button>
                    {onSuggestionSelect && (
                    <Button variant="primary" onClick={() => {
                      onSuggestionSelect('icd10', itemObj?.code);
                      notify.success(t('final.icd_added_to_form'));
                    }}>
                      <CheckCircle style={{ width: 14, height: 14, marginRight: 6 }} />{t('misc.aia_use')}
                    </Button>
                    )}
                    </div>
                  </div>
                  );
                })}
              </div>
            </div>
          }
        </div>);

    }
    if (!result || !Array.isArray(result)) return null;
    return (
      <div>
        {result.map((item: unknown, idx: number) => {
          const itemObj = (item ?? null) as Record<string, unknown> | null;
          return (
        <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 'var(--mac-spacing-2) 0', borderBottom: '1px solid var(--mac-border)' }}>
            <div>
              {`${String(itemObj?.code ?? '')} - ${String(itemObj?.name ?? itemObj?.description ?? '')}`}
              {Boolean(itemObj?.relevance) &&
            <span style={{ marginLeft: 8 }}>
                  <Pill color={itemObj?.relevance === t('misc.aia_relevance_high') ? 'success' : itemObj?.relevance === t('misc.aia_relevance_medium') ? 'warning' : 'default'}>
                    {String(itemObj?.relevance ?? '')}
                  </Pill>
                </span>
            }
            </div>
            <div style={{ display: 'flex', gap: 'var(--mac-spacing-1)' }}>
            <Button variant="outline" onClick={() => copyToClipboard(`${String(itemObj?.code ?? '')} - ${String(itemObj?.name ?? itemObj?.description ?? '')}`)}>
              <Copy style={{ width: 14, height: 14, marginRight: 6 }} />{t('misc.aia_copy')}
            </Button>
            {onSuggestionSelect && (
            <Button variant="primary" onClick={() => {
              onSuggestionSelect('icd10', itemObj?.code);
              notify.success(t('final.icd_added_to_form'));
            }}>
              <CheckCircle style={{ width: 14, height: 14, marginRight: 6 }} />{t('misc.aia_use')}
            </Button>
            )}
            </div>
          </div>
          );
        })}
      </div>);

  };

  const renderLabResult = () => {
    if (!isResultObject(result)) return null;
    const resultObj = result;
    return (
      <div>
        {Boolean(resultObj.summary) &&
        <Alert severity="info" style={{ marginBottom: 12 }}>
            <Typography variant="body2">{String(resultObj.summary ?? '')}</Typography>
          </Alert>
        }
        {Array.isArray(resultObj.abnormal_values) && resultObj.abnormal_values.length > 0 &&
        <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_abnormal_values')}</Typography>
            {resultObj.abnormal_values.map((item: unknown, idx: number) => {
          const itemObj = (item ?? null) as Record<string, unknown> | null;
          return (
          <details key={idx} open={idx === 0} style={{
            border: '1px solid var(--mac-border)', borderRadius: 8, padding: 12, marginBottom: 8
          }}>
                <summary style={{ cursor: 'pointer', listStyle: 'none' }}>
                  {String(itemObj?.parameter ?? '')}: {String(itemObj?.value ?? '')}
                </summary>
                <div style={{ marginTop: 8 }}>
                  <Typography variant="body2" gutterBottom><strong>{t('misc.aia_interpretation')}</strong> {String(itemObj?.interpretation ?? '')}</Typography>
                  <Typography variant="body2"><strong>{t('misc.aia_clinical_significance')}</strong> {String(itemObj?.clinical_significance ?? '')}</Typography>
                </div>
              </details>
          );
        })}
          </div>
        }
        {Array.isArray(resultObj.possible_conditions) && resultObj.possible_conditions.length > 0 &&
        <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_possible_conditions')}</Typography>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {resultObj.possible_conditions.map((condition: unknown, idx: number) =>
            <Pill key={idx} color="warning">{String(condition ?? '')}</Pill>
            )}
            </div>
          </div>
        }
        {Array.isArray(resultObj.recommendations) && resultObj.recommendations.length > 0 &&
        <div style={{ marginBottom: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_recommendations')}</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {resultObj.recommendations.map((rec: unknown, idx: number) => <li key={idx}>{String(rec ?? '')}</li>)}
            </ul>
          </div>
        }
        {Boolean(resultObj.urgency) &&
        <Alert severity={resultObj.urgency === t('misc.aia_yes') ? 'warning' : 'info'} style={{ marginTop: 8 }}>
            {t('misc.aia_urgent_consultation')}: {String(resultObj.urgency ?? '')}
          </Alert>
        }
      </div>);

  };

  const renderECGResult = () => {
    if (!isResultObject(result)) return null;
    const resultObj = result;
    return (
      <div>
        <div style={{ border: '1px solid var(--mac-border)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <Typography variant="subtitle2" gutterBottom>{t('misc.aia_main_params')}</Typography>
          <div style={{ display: 'grid', gap: 6 }}>
            {Boolean(resultObj.rhythm) && <Typography variant="body2"><strong>{t('misc.aia_rhythm')}</strong> {String(resultObj.rhythm ?? '')}</Typography>}
            {Boolean(resultObj.rate) && <Typography variant="body2"><strong>{t('misc.aia_hr')}</strong> {String(resultObj.rate ?? '')}</Typography>}
            {Boolean(resultObj.conduction) && <Typography variant="body2"><strong>{t('misc.aia_conduction')}</strong> {String(resultObj.conduction ?? '')}</Typography>}
            {Boolean(resultObj.axis) && <Typography variant="body2"><strong>{t('misc.aia_axis')}</strong> {String(resultObj.axis ?? '')}</Typography>}
          </div>
        </div>
        {Array.isArray(resultObj.abnormalities) && resultObj.abnormalities.length > 0 &&
        <Alert severity="warning">
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_abnormalities')}</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {resultObj.abnormalities.map((item: unknown, idx: number) => <li key={idx}>{String(item ?? '')}</li>)}
            </ul>
          </Alert>
        }
        {Boolean(resultObj.interpretation) &&
        <div style={{ border: '1px solid var(--mac-border)', borderRadius: 8, padding: 12, marginTop: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_conclusion')}</Typography>
            <Typography variant="body2">{String(resultObj.interpretation ?? '')}</Typography>
          </div>
        }
        {Array.isArray(resultObj.recommendations) && resultObj.recommendations.length > 0 &&
        <div style={{ marginTop: 12 }}>
            <Typography variant="subtitle2" gutterBottom>{t('misc.aia_recommendations')}</Typography>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {resultObj.recommendations.map((rec: unknown, idx: number) => <li key={idx}>{String(rec ?? '')}</li>)}
            </ul>
          </div>
        }
        {Boolean(resultObj.urgency) &&
        <Pill color={resultObj.urgency === t('misc.aia_urgency_emergency') ? 'error' : resultObj.urgency === t('misc.aia_urgency_planned') ? 'info' : 'default'}>
            {t('misc.aia_cardio_consultation')}: {String(resultObj.urgency ?? '')}
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


export default AIAssistant;
