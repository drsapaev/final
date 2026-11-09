
/**
 * Echo Form Component
 * Форма для ввода результатов ЭхоКГ
 * Phase 3: stale MASTER_TODO_LIST reference removed.
 */
import { useState, useEffect, useRef } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Button,
  Alert,
  Input,
  Textarea,
} from '../ui/macos';
import {
  Heart,
  Save,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";
import type { HttpApiError } from '../../types/errors';

// === Domain types ===
// EchoForm tracks echocardiography measurements grouped by anatomical
// section. All measurement fields are strings (user input) until saved.

export interface EchoData {
  leftVentricle: {
    edd: string;
    esd: string;
    ef: string;
    fs: string;
    ivs: string;
    pw: string;
  };
  rightVentricle: {
    rvdd: string;
    rvot: string;
  };
  atria: {
    la: string;
    ra: string;
  };
  valves: {
    mitral: { e: string; a: string; e_a: string; decel_time: string };
    tricuspid: { e: string; a: string; e_a: string };
    aortic: { peak_velocity: string; mean_gradient: string; ava: string };
    pulmonary: { peak_velocity: string; mean_gradient: string };
  };
  additional: {
    pericardium: string;
    aorta: string;
    comments: string;
  };
  conclusion: string;
  [key: string]: unknown;
}

export interface EchoFormProps {
  /** Visit ID for saving/loading Echo data via API. */
  visitId?: string | number | null;
  /** Patient ID (passed through for API calls). */
  patientId?: string | number | null;
  /** Called when user saves the form without a visitId (draft mode). */
  onSave?: (data: EchoData) => void;
  /** Reload patient data after Echo changes (called after successful save). */
  onDataUpdate?: () => void;
  /** Pre-populate the form with existing Echo data. */
  initialData?: Partial<EchoData> | null;
  [key: string]: unknown;
}

/** UI_AUDIT_PLAN Phase 0 ratchet: shared style constant instead of
 * another inline `style={{…}}` literal. */
const ALERT_MARGIN_STYLE: React.CSSProperties = { marginBottom: 16 };

/** RETRO-3941-02: same ratchet rule for the hydration-failure alert's icon
 * and retry button. */
const HYDRATION_ALERT_ICON_STYLE: React.CSSProperties = { width: 16, height: 16, marginRight: 8 };
const RETRY_BUTTON_STYLE: React.CSSProperties = { marginLeft: 12 };

const DEFAULT_ECHO_DATA = {
  // Левый желудочек
  leftVentricle: {
    edd: '', // КДР
    esd: '', // КСР
    ef: '', // ФВ
    fs: '', // ФС
    ivs: '', // МЖП
    pw: '' // ЗС
  },
  // Правый желудочек
  rightVentricle: {
    rvdd: '', // КДР ПЖ
    rvot: '' // ВТ ПЖ
  },
  // Предсердия
  atria: {
    la: '', // ЛП
    ra: '' // ПП
  },
  // Клапаны
  valves: {
    mitral: {
      e: '',
      a: '',
      e_a: '',
      decel_time: ''
    },
    tricuspid: {
      e: '',
      a: '',
      e_a: ''
    },
    aortic: {
      peak_velocity: '',
      mean_gradient: '',
      ava: ''
    },
    pulmonary: {
      peak_velocity: '',
      mean_gradient: ''
    }
  },
  // Дополнительные параметры
  additional: {
    pericardium: '',
    aorta: '',
    comments: ''
  },
  // Заключение
  conclusion: ''
};

function deepMerge(base: Record<string, unknown>, incoming: Record<string, unknown> | null | undefined): Record<string, unknown> {
  if (!incoming || typeof incoming !== 'object' || Array.isArray(incoming)) {
    return base;
  }

  const result: Record<string, unknown> = { ...base };
  for (const [key, value] of Object.entries(incoming)) {
    if (value && typeof value === 'object' && !Array.isArray(value) && base?.[key] && typeof base[key] === 'object') {
      result[key] = deepMerge(base[key] as Record<string, unknown>, value as Record<string, unknown>);
    } else {
      result[key] = value;
    }
  }
  return result;
}

function getNestedValue(source: unknown, path: string): string {
  if (!source || !path) return '';
  const result = String(path).split('.').reduce<unknown>((acc, key) => {
    if (acc && typeof acc === 'object') {
      return (acc as Record<string, unknown>)[key];
    }
    return undefined;
  }, source);
  return result == null ? '' : String(result);
}

function setNestedValue(source: Record<string, unknown>, path: string, value: unknown): Record<string, unknown> {
  const keys = String(path).split('.');
  const result = { ...source };
  let current: Record<string, unknown> = result;
  for (let i = 0; i < keys.length - 1; i += 1) {
    const key = keys[i];
    current[key] = current[key] && typeof current[key] === 'object' ? { ...(current[key] as Record<string, unknown>) } : {};
    current = current[key] as Record<string, unknown>;
  }
  current[keys[keys.length - 1]] = value;
  return result;
}

async function loadExistingEmrDraft(visitId: string | number | null | undefined) {
  try {
    const response = await api.get(`/v2/emr/${visitId}`);
    return response.data || null;
  } catch (err) {
    if ((err as HttpApiError)?.response?.status === 404) {
      return null;
    }
    throw err;
  }
}

function buildEchoEmrPayload(existingEmr: Record<string, unknown> | null, echoData: EchoData) {
  const currentData = (existingEmr?.data as Record<string, unknown>) || {};
  return {
    data: {
      ...currentData,
      specialty: currentData.specialty || 'cardiology',
      specialty_data: {
        ...((currentData.specialty_data as Record<string, unknown>) || {}),
        echo: echoData
      }
    },
    row_version: existingEmr?.row_version ?? 0,
    is_draft: true
  };
}

const EchoForm = ({ visitId, onSave, onDataUpdate, initialData = null }: EchoFormProps) => {
  const { t: rawT } = useTranslation(); const t = rawT;
  const [echoData, setEchoData] = useState<EchoData>(DEFAULT_ECHO_DATA as EchoData);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  // ECHO-FE-001 (audit 3886 round 20): hydration and dirty tracking.
  // The form previously initialized blank and hydrated ONLY from an
  // `initialData` prop that no caller passed, while Save unconditionally
  // replaced `specialty_data.echo` with the local state — an untouched
  // Save could wipe stored EF/EDD/conclusion with a blank revision.
  const [hydrating, setHydrating] = useState(false);
  const [info, setInfo] = useState('');
  const dirtyRef = useRef(false);
  const formEpochRef = useRef(0);
  // RETRO-3941-02 (post-merge review of PR 3941): a hydration failure of the
  // canonical EMR must fail CLOSED — the stored echo subtree is unknown, so
  // a blank/partial local form may never overwrite it. Save stays blocked
  // until a canonical load succeeds (Retry re-runs it via hydrationAttempt).
  const [hydrationFailed, setHydrationFailed] = useState(false);
  const [hydrationAttempt, setHydrationAttempt] = useState(0);
  // RETRO-3941-03: edits are counted per form epoch so a save that lands
  // AFTER newer edits never clears the dirty flag for them.
  const editEpochRef = useRef(0);
  const [expandedSections, setExpandedSections] = useState({
    leftVentricle: true,
    rightVentricle: false,
    atria: false,
    valves: false,
    additional: false
  });

  useEffect(() => {
    // Explicit initialData still wins: callers that own the data pass it.
    if (initialData) {
      setEchoData(deepMerge(DEFAULT_ECHO_DATA as Record<string, unknown>, initialData as Record<string, unknown>) as EchoData);
      setHydrationFailed(false);
      return;
    }

    const epoch = ++formEpochRef.current;
    dirtyRef.current = false;

    if (!visitId) {
      setEchoData(DEFAULT_ECHO_DATA as EchoData);
      setInfo('');
      setHydrationFailed(false);
      return;
    }

    // ECHO-FE-001: hydrate from the canonical EMR draft for this visit so
    // the doctor sees the stored echo measurements before any save.
    setHydrating(true);
    setInfo('');
    setSuccess('');
    setError('');
    setHydrationFailed(false);
    loadExistingEmrDraft(visitId)
      .then((existing) => {
        if (epoch !== formEpochRef.current) return; // visit switched mid-flight
        const storedData = (existing as Record<string, unknown> | null)?.data as Record<string, unknown> | undefined;
        const specialtyData = storedData?.specialty_data as Record<string, unknown> | undefined;
        const storedEcho = specialtyData?.echo;
        if (storedEcho && typeof storedEcho === 'object') {
          setEchoData(deepMerge(DEFAULT_ECHO_DATA as Record<string, unknown>, storedEcho as Record<string, unknown>) as EchoData);
        } else {
          setEchoData(DEFAULT_ECHO_DATA as EchoData);
        }
        dirtyRef.current = false;
      })
      .catch(() => {
        if (epoch !== formEpochRef.current) return;
        // RETRO-3941-02: fail CLOSED. The canonical echo subtree could not
        // be read (transient 5xx / network error): we do not know what is
        // stored, so the blank local form must not be savable — a save
        // would overwrite every stored field it did not hydrate. Surface
        // the failure, block Save and offer an explicit retry.
        setEchoData(DEFAULT_ECHO_DATA as EchoData);
        dirtyRef.current = false;
        setHydrationFailed(true);
      })
      .finally(() => {
        if (epoch === formEpochRef.current) {
          setHydrating(false);
        }
      });
  }, [visitId, initialData, hydrationAttempt]);

  const handleChange = (section: string, field: string, value: unknown) => {
    dirtyRef.current = true;
    editEpochRef.current += 1; // RETRO-3941-03: count every edit
    setInfo('');
    setEchoData((prev) => ({
      ...prev,
      [section]: field.includes('.')
        ? setNestedValue((prev[section] || {}) as Record<string, unknown>, field, value)
        : {
          ...((prev[section] as Record<string, unknown>) || {}),
          [field]: value
        }
    }));
  };

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const handleSave = async () => {
    const epoch = formEpochRef.current;
    // RETRO-3941-03: snapshot the edit counter at submission start. If the
    // doctor edits while the GET/POST is in flight, the request persists
    // this submitted snapshot — the newer values must stay marked unsaved.
    const editEpochAtSubmit = editEpochRef.current;
    try {
      setLoading(true);
      setError('');
      setInfo('');

      if (!visitId) {
        if (onSave) {
          onSave(echoData);
          setSuccess(t('cardio.cardio_echo_saved_draft'));
          return;
        }
        throw new Error('visit_id is required to save Echo results');
      }

      // ECHO-FE-001: a blank/unhydrated form must never be able to
      // overwrite the stored echo subtree — block Save until the canonical
      // EMR state for this visit has been loaded.
      // RETRO-3941-02: a FAILED hydration is just as unknown as a pending
      // one — Save stays blocked until Retry loads the canonical state.
      if (hydrating || hydrationFailed) {
        setInfo(t('cardio.cardio_echo_loading_existing'));
        return;
      }

      const existingEmr = await loadExistingEmrDraft(visitId);

      // ECHO-FE-001: pristine form + existing echo subtree → nothing to
      // change; skip the POST instead of writing an identical (or blank)
      // new revision of the EMR.
      const storedData = (existingEmr as Record<string, unknown> | null)?.data as Record<string, unknown> | undefined;
      const existingEcho = (storedData?.specialty_data as Record<string, unknown> | undefined)?.echo;
      const hasExistingEcho = Boolean(existingEcho && typeof existingEcho === 'object');
      if (!dirtyRef.current && hasExistingEcho) {
        setInfo(t('cardio.cardio_echo_no_changes'));
        return;
      }

      const response = await api.post(`/v2/emr/${visitId}`, buildEchoEmrPayload(existingEmr, echoData));

      if (epoch !== formEpochRef.current) return; // visit switched mid-save

      if (response.status === 200) {
        if (editEpochRef.current !== editEpochAtSubmit) {
          // RETRO-3941-03: edits happened after the submission started. The
          // POST persisted the submitted snapshot, NOT the values now on
          // screen: keep the form dirty, say so honestly, and require a
          // follow-up save. Never clear dirty tracking for edits the
          // request could not have carried.
          dirtyRef.current = true;
          setInfo(t('cardio.cardio_echo_saved_stale_edit'));
          return;
        }
        // The server-side state now matches the form: reset dirty tracking.
        dirtyRef.current = false;
        setSuccess(t('cardio.cardio_echo_saved_success'));
        if (onSave) {
          onSave(response.data?.data?.specialty_data?.echo || echoData);
        }
        onDataUpdate?.();
      }
    } catch (err) {
      if (epoch === formEpochRef.current) {
        setError(t('cardio.cardio_echo_save_error'));
      }
      logger.error('Echo form save error:', err);
    } finally {
      if (epoch === formEpochRef.current) {
        setLoading(false);
      }
    }
  };

  const renderSection = (
    title: string,
    section: keyof typeof expandedSections,
    fields: Array<{ key: string; label: string; placeholder: string }>,
    expanded: boolean
  ) =>
  <div style={{ marginBottom: 24 }}>
      <div
      role="button"
      tabIndex={0}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
        backgroundColor: 'var(--mac-bg-secondary)',
        border: '1px solid var(--mac-border)',
        borderRadius: 'var(--mac-radius-md)',
        cursor: 'pointer'
      }}
      onClick={() => toggleSection(section)}
      onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          toggleSection(section);
        }
      }}>
      
        <Typography variant="subtitle1" style={{ fontWeight: 'var(--mac-font-weight-medium)' }}>
          {title}
        </Typography>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {expanded ? <ChevronDown style={{ width: 16, height: 16 }} /> : <ChevronRight style={{ width: 16, height: 16 }} />}
        </div>
      </div>
      
      {expanded &&
    <div style={{ padding: 16, marginTop: 8, border: '1px solid var(--mac-border)', borderRadius: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
            {fields.map((field) =>
        <div key={field.key}>
                <Input
            label={field.label}
            value={getNestedValue(echoData[section], field.key)}
            onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleChange(section, field.key, e.target.value)}
            placeholder={field.placeholder} />
          
              </div>
        )}
          </div>
        </div>
    }
    </div>;


  return (
    <Card>
      <CardContent>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <Typography variant="h6">
            <Heart style={{ marginRight: 8, verticalAlign: 'middle' }} />
            {t('cardio.cardio_echo_results_title')}
          </Typography>
          
          <div style={{ display: 'flex', gap: 8 }}>
            {/* P-030 (UX audit): removed dead AI button. The onClick handler
                was empty, so the button did nothing. Backend has no
                /ai/echo-interpret endpoint yet. When AI echo analysis is
                implemented, re-add the button with a real handler. */}
            <Button
              variant="primary"
              onClick={handleSave}
              disabled={loading || hydrating || hydrationFailed}>
              
              <Save style={{ width: 16, height: 16, marginRight: 8 }} />
              {hydrating ? t('cardio.cardio_echo_loading_existing') : t('cardio.cardio_echo_save_button')}
            </Button>
          </div>
        </div>

        {error &&
        <Alert severity="error" style={{ marginBottom: 16 }}>
            <AlertTriangle style={{ width: 16, height: 16, marginRight: 8 }} />
            {error}
          </Alert>
        }

        {success &&
        <Alert severity="success" style={{ marginBottom: 16 }}>
            <CheckCircle style={{ width: 16, height: 16, marginRight: 8 }} />
            {success}
          </Alert>
        }

        {/* ECHO-FE-001: hydration/no-change status is informational. */}
        {info && !success && !error &&
        <Alert severity="info" style={ALERT_MARGIN_STYLE}>
            {info}
          </Alert>
        }

        {/* RETRO-3941-02: a failed canonical load fails closed — visible
            failure + explicit retry, Save blocked in between. */}
        {hydrationFailed &&
        <Alert severity="error" style={ALERT_MARGIN_STYLE}>
            <AlertTriangle style={HYDRATION_ALERT_ICON_STYLE} />
            {t('cardio.cardio_echo_hydration_error')}
            <Button
              variant="outline"
              size="small"
              style={RETRY_BUTTON_STYLE}
              onClick={() => setHydrationAttempt((attempt) => attempt + 1)}>
              {t('cardio.cardio_echo_retry')}
            </Button>
          </Alert>
        }

        {/* Левый желудочек */}
        {renderSection(
          t('cardio.cardio_echo_section_left_ventricle'),
          'leftVentricle',
          [
          { key: 'edd', label: t('cardio.cardio_echo_field_edd'), placeholder: t('cardio.cardio_echo_ph_edd') },
          { key: 'esd', label: t('cardio.cardio_echo_field_esd'), placeholder: t('cardio.cardio_echo_ph_esd') },
          { key: 'ef', label: t('cardio.cardio_echo_field_ef'), placeholder: t('cardio.cardio_echo_ph_ef') },
          { key: 'fs', label: t('cardio.cardio_echo_field_fs'), placeholder: t('cardio.cardio_echo_ph_fs') },
          { key: 'ivs', label: t('cardio.cardio_echo_field_ivs'), placeholder: t('cardio.cardio_echo_ph_ivs') },
          { key: 'pw', label: t('cardio.cardio_echo_field_pw'), placeholder: t('cardio.cardio_echo_ph_pw') }],

          expandedSections.leftVentricle
        )}

        {/* Правый желудочек */}
        {renderSection(
          t('cardio.cardio_echo_section_right_ventricle'),
          'rightVentricle',
          [
          { key: 'rvdd', label: t('cardio.cardio_echo_field_rvdd'), placeholder: t('cardio.cardio_echo_ph_rvdd') },
          { key: 'rvot', label: t('cardio.cardio_echo_field_rvot'), placeholder: t('cardio.cardio_echo_ph_rvot') }],

          expandedSections.rightVentricle
        )}

        {/* Предсердия */}
        {renderSection(
          t('cardio.cardio_echo_section_atria'),
          'atria',
          [
          { key: 'la', label: t('cardio.cardio_echo_field_la'), placeholder: t('cardio.cardio_echo_ph_la') },
          { key: 'ra', label: t('cardio.cardio_echo_field_ra'), placeholder: t('cardio.cardio_echo_ph_ra') }],

          expandedSections.atria
        )}

        {/* Клапаны */}
        {renderSection(
          t('cardio.cardio_echo_section_valves'),
          'valves',
          [
          { key: 'mitral.e', label: t('cardio.cardio_echo_field_mitral_e'), placeholder: t('cardio.cardio_echo_ph_mitral_e') },
          { key: 'mitral.a', label: t('cardio.cardio_echo_field_mitral_a'), placeholder: t('cardio.cardio_echo_ph_mitral_a') },
          { key: 'aortic.peak_velocity', label: t('cardio.cardio_echo_field_aortic'), placeholder: t('cardio.cardio_echo_ph_aortic') },
          { key: 'tricuspid.e', label: t('cardio.cardio_echo_field_tricuspid_e'), placeholder: t('cardio.cardio_echo_ph_tricuspid_e') }],

          expandedSections.valves
        )}

        {/* Дополнительные параметры */}
        {renderSection(
          t('cardio.cardio_echo_section_additional'),
          'additional',
          [
          { key: 'pericardium', label: t('cardio.cardio_echo_field_pericardium'), placeholder: t('cardio.cardio_echo_ph_pericardium') },
          { key: 'aorta', label: t('cardio.cardio_echo_field_aorta'), placeholder: t('cardio.cardio_echo_ph_aorta') }],

          expandedSections.additional
        )}

        {/* Комментарии */}
        <div style={{ marginTop: 24 }}>
          <Typography variant="subtitle1" style={{ marginBottom: 8 }}>
            {t('cardio.cardio_echo_comments_title')}
          </Typography>
          <Textarea
            value={echoData.additional.comments}
            onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleChange('additional', 'comments', e.target.value)}
            placeholder={t('cardio.cardio_echo_ph_comments')}
            rows={4} />
          
        </div>

        {/* Заключение */}
        <div style={{ marginTop: 24 }}>
          <Typography variant="subtitle1" style={{ marginBottom: 8 }}>
            {t('cardio.cardio_echo_conclusion_title')}
          </Typography>
          <Textarea
            value={echoData.conclusion}
            onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
              dirtyRef.current = true;
              editEpochRef.current += 1; // RETRO-3941-03: count every edit
              setInfo('');
              setEchoData((prev) => ({ ...prev, conclusion: e.target.value }));
            }}
            placeholder={t('cardio.cardio_echo_ph_conclusion')}
            rows={6} />
          
        </div>
      </CardContent>
    </Card>);

};


// audit/strict: removed self-referencing propTypes spread

export default EchoForm;
