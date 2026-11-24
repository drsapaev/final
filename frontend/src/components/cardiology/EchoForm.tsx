
/**
 * Echo Form Component
 * Форма для ввода результатов ЭхоКГ
 * Phase 3: stale MASTER_TODO_LIST reference removed.
 */
import { useState, useEffect, useId, useRef } from 'react';
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
import React from 'react';
import type { HttpApiError } from '../../types/errors';
import {
  ADULT_TTE_EF_METHODS,
  ADULT_TTE_MEASUREMENT_KEYS,
  ADULT_TTE_MEASUREMENTS,
  normalizeEchoForEditor,
  parseAdultTteMeasurement,
  type AdultTteMeasurementKey,
} from '../../utils/echoMeasurements';
import { invalidateEMRCache } from '../../hooks/useEMR';

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
  measurement_metadata?: {
    ef_method?: string;
    measured_at?: string;
    recorded_at?: string;
    source_visit_id?: string | number | null;
    definition_version?: number;
  };
  adult_tte?: {
    version?: number;
    measurements?: Partial<Record<AdultTteMeasurementKey, { value: string | number; unit: string }>>;
    ef_method?: string;
    measured_at?: string;
    recorded_at?: string;
    source_visit_id?: string | number;
  };
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

function getNestedValue(source: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((acc, key) => {
    if (acc && typeof acc === 'object') {
      return (acc as Record<string, unknown>)[key];
    }
    return undefined;
  }, source);
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

function getStoredEcho(emr: Record<string, unknown> | null): unknown {
  const data = emr?.data as Record<string, unknown> | undefined;
  return (data?.specialty_data as Record<string, unknown> | undefined)?.echo ?? null;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function isAdultTtePath(path: string) {
  return path.startsWith('adult_tte.');
}

function isLegacyMeasurementPath(path: string) {
  return /^(leftVentricle|rightVentricle|atria|valves|measurement_metadata)\./.test(path) ||
    path === 'additional.pericardium' || path === 'additional.aorta';
}

function containsEnteredValue(value: unknown): boolean {
  if (typeof value === 'string') return value.trim().length > 0;
  if (typeof value === 'number') return Number.isFinite(value);
  return Object.values(asRecord(value)).some(containsEnteredValue);
}

function echoSnapshot(value: unknown): string {
  return JSON.stringify(value, (_key, item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return item;
    return Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]]));
  });
}

function hydrateEcho(saved: unknown, draft: EchoData, touched: Iterable<string>): EchoData {
  let result = deepMerge(DEFAULT_ECHO_DATA, normalizeEchoForEditor(saved));
  for (const path of touched) {
    result = setNestedValue(result, path, getNestedValue(draft, path));
  }
  return result as EchoData;
}

function isReadOnlyEmr(emr: Record<string, unknown> | null) {
  return ['signed', 'amended', 'locked'].includes(String(emr?.status));
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

function buildEchoEmrPayload(
  existingEmr: Record<string, unknown> | null,
  echoData: EchoData,
  visitId: string | number,
  changes: ReadonlySet<string>,
) {
  const currentData = (existingEmr?.data as Record<string, unknown>) || {};
  const existingEcho = asRecord(getStoredEcho(existingEmr));
  let echo = { ...existingEcho };
  const recordedAt = new Date().toISOString();

  for (const path of changes) {
    if (!isAdultTtePath(path)) echo = setNestedValue(echo, path, getNestedValue(echoData, path));
  }
  // An adult TTE submission alone must leave the original measurements and metadata intact.
  if ([...changes].some(isLegacyMeasurementPath)) {
    const metadata = asRecord(echo.measurement_metadata);
    if (!Object.keys(existingEcho).some(key => key !== 'adult_tte')) metadata.definition_version ??= 1;
    echo.measurement_metadata = { ...metadata, recorded_at: recordedAt, source_visit_id: visitId };
  }

  if ([...changes].some(isAdultTtePath)) {
    const original = asRecord(existingEcho.adult_tte);
    const measurements = { ...asRecord(original.measurements) };
    for (const key of ADULT_TTE_MEASUREMENT_KEYS) {
      if (!changes.has(`adult_tte.measurements.${key}`)) continue;
      const value = parseAdultTteMeasurement(echoData.adult_tte?.measurements?.[key]?.value);
      if (value === null) delete measurements[key];
      else measurements[key] = { value, unit: ADULT_TTE_MEASUREMENTS[key].unit };
    }

    const adultTte: Record<string, unknown> = { ...original, version: 2, measurements };
    if (changes.has('adult_tte.ef_method')) {
      const method = ADULT_TTE_EF_METHODS.find(code => code === echoData.adult_tte?.ef_method);
      if (method) adultTte.ef_method = method;
      else delete adultTte.ef_method;
    }
    if (changes.has('adult_tte.measured_at')) {
      if (echoData.adult_tte?.measured_at) adultTte.measured_at = echoData.adult_tte.measured_at;
      else delete adultTte.measured_at;
    }
    if (Object.keys(measurements).length > 0 || adultTte.ef_method || adultTte.measured_at) {
      echo.adult_tte = { ...adultTte, recorded_at: recordedAt, source_visit_id: visitId };
    } else if (existingEcho.adult_tte) {
      echo.adult_tte = adultTte;
    }
  }

  return {
    data: {
      ...currentData,
      specialty: currentData.specialty || 'cardiology',
      specialty_data: {
        ...((currentData.specialty_data as Record<string, unknown>) || {}),
        echo,
      }
    },
    row_version: existingEmr?.row_version ?? 0,
    is_draft: true
  };
}

const EchoForm = ({ visitId, onSave, onDataUpdate, initialData = null }: EchoFormProps) => {
  const { t: rawT } = useTranslation(); const t = rawT;
  const fieldIdPrefix = useId();
  const [echoData, setEchoData] = useState<EchoData>(DEFAULT_ECHO_DATA as EchoData);
  // RETRO-3947-01 (post-merge review of PR 3947, dossier PR 3958): mirror of the
  // visible form data so async hydration handlers can read the doctor's
  // CURRENT draft without stale render closures.
  const echoDataRef = useRef<EchoData>(DEFAULT_ECHO_DATA as EchoData);
  const applyEchoData = (next: EchoData) => {
    echoDataRef.current = next;
    setEchoData(next);
  };

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  // ECHO-FE-001 (audit 3886 round 20): hydration and dirty tracking.
  // The form previously initialized blank and hydrated ONLY from an
  // `initialData` prop that no caller passed, while Save unconditionally
  // replaced `specialty_data.echo` with the local state — an untouched
  // Save could wipe stored EF/EDD/conclusion with a blank revision.
  const [hydrating, setHydrating] = useState(false);
  const [readOnly, setReadOnly] = useState(false);
  const [info, setInfo] = useState('');
  const dirtyRef = useRef(false);
  const savedEchoRef = useRef<string | undefined>(undefined);
  const formEpochRef = useRef(0);
  // RETRO-3941-02 (post-merge review of PR 3941): a hydration failure of the
  // canonical EMR must fail CLOSED — the stored echo subtree is unknown, so
  // a blank/partial local form may never overwrite it. Save stays blocked
  // until a canonical load succeeds, including a requested reload.
  const [hydrationFailed, setHydrationFailed] = useState(false);
  const [saveConflict, setSaveConflict] = useState(false);
  const [reloadRequest, setReloadRequest] = useState<{ visit: typeof visitId }>();
  // RETRO-3941-03: edits are counted per form epoch so a save that lands
  // AFTER newer edits never clears the dirty flag for them.
  const editEpochRef = useRef(0);
  // Keep the latest unsaved edit for each path. Reload can overlay only
  // those fields, and a save acknowledgment can retire earlier edits.
  const draftTouchedRef = useRef<Map<string, number>>(new Map());
  const lastVisitIdRef = useRef<string | number | null | undefined>(undefined);
  const [expandedSections, setExpandedSections] = useState({
    leftVentricle: true,
    rightVentricle: false,
    atria: false,
    valves: false,
    additional: false
  });

  useEffect(() => {
    const epoch = ++formEpochRef.current;
    const cancel = () => { formEpochRef.current += 1; };
    // RETRO-3947-01: a local draft belongs to ONE visit lifecycle — a visit
    // switch voids it (the draft would belong to the previous visit).
    if (lastVisitIdRef.current !== visitId) {
      lastVisitIdRef.current = visitId;
      draftTouchedRef.current.clear();
      setSaveConflict(false);
    }
    dirtyRef.current = draftTouchedRef.current.size > 0;
    savedEchoRef.current = undefined;
    setLoading(false);
    setInfo('');
    setSuccess('');
    setError('');
    setHydrationFailed(false);
    setReadOnly(false);

    // Explicit data still pre-populates the form. Recovery reads the server.
    if (!visitId || (initialData && (!reloadRequest || reloadRequest.visit !== visitId))) {
      applyEchoData(hydrateEcho(initialData, echoDataRef.current, draftTouchedRef.current.keys()));
      savedEchoRef.current = echoSnapshot(initialData);
      setHydrating(false);
      return cancel;
    }

    setHydrating(true);
    loadExistingEmrDraft(visitId)
      .then((existing) => {
        if (epoch !== formEpochRef.current) return; // visit switched mid-flight
        const storedEcho = getStoredEcho(existing);
        const locked = isReadOnlyEmr(existing);
        savedEchoRef.current = echoSnapshot(storedEcho);
        setReadOnly(locked);
        applyEchoData(hydrateEcho(storedEcho, echoDataRef.current, draftTouchedRef.current.keys()));
        dirtyRef.current = draftTouchedRef.current.size > 0;
        if (dirtyRef.current) {
          setInfo(t(locked ? 'cardio.cardio_echo_finalized' : 'cardio.cardio_echo_draft_preserved'));
        }
        setSaveConflict(false);
      })
      .catch(() => {
        if (epoch !== formEpochRef.current) return;
        // RETRO-3941-02: fail CLOSED. The canonical echo subtree could not
        // be read (transient 5xx / network error): we do not know what is
        // stored, so the blank local form must not be savable — a save
        // would overwrite every stored field it did not hydrate. Surface
        // the failure, block Save and offer an explicit retry.
        // RETRO-3947-01: a failed retry must not destroy the typed draft
        // either — the draft survives until a canonical load succeeds;
        // with no draft the previous blank-reset behavior applies.
        if (draftTouchedRef.current.size === 0) {
          applyEchoData(DEFAULT_ECHO_DATA as EchoData);
          dirtyRef.current = false;
        }
        setHydrationFailed(true);
      })
      .finally(() => {
        if (epoch === formEpochRef.current) {
          setHydrating(false);
        }
      });
    return cancel;
  // eslint-disable-next-line react-hooks/exhaustive-deps -- `t` is a stable i18n lookup; adding it would re-trigger the canonical hydration on every render.
  }, [visitId, initialData, reloadRequest]);

  const markEdited = (path: string) => {
    dirtyRef.current = true;
    editEpochRef.current += 1;
    draftTouchedRef.current.set(path, editEpochRef.current);
    setInfo('');
    setSuccess('');
  };

  const handleChange = (section: string, field: string, value: unknown) => {
    if (readOnly) return;
    markEdited(`${section}.${field}`);
    const prev = echoDataRef.current;
    const nextSection = field.includes('.')
      ? setNestedValue((prev[section] || {}) as Record<string, unknown>, field, value)
      : {
          ...((prev[section] as Record<string, unknown>) || {}),
          [field]: value
        };
    applyEchoData({ ...prev, [section]: nextSection } as EchoData);
  };

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const adultTte = echoData.adult_tte;
  const unsupportedAdultTte = adultTte?.version !== undefined && adultTte?.version !== 2;
  const adultTteSaveBlocked = unsupportedAdultTte && [...draftTouchedRef.current.keys()].some(isAdultTtePath);
  const adultTteInvalidKeys = ADULT_TTE_MEASUREMENT_KEYS.filter(key => {
    const value = adultTte?.measurements?.[key]?.value;
    if (!draftTouchedRef.current.has(`adult_tte.measurements.${key}`) ||
      typeof value !== 'string' || value.trim() === '') return false;
    const parsed = parseAdultTteMeasurement(value);
    return parsed === null || (key === 'lvef' && parsed > 100);
  });
  const hasLegacyMeasurements = [
    echoData.leftVentricle, echoData.rightVentricle, echoData.atria, echoData.valves,
    echoData.additional?.pericardium, echoData.additional?.aorta,
    echoData.measurement_metadata?.ef_method, echoData.measurement_metadata?.measured_at,
  ].some(containsEnteredValue) || [...draftTouchedRef.current.keys()].some(isLegacyMeasurementPath);

  const handleSave = async () => {
    if (readOnly || loading || saveConflict || adultTteSaveBlocked || adultTteInvalidKeys.length > 0) return;
    const epoch = formEpochRef.current;
    // RETRO-3941-03: snapshot the edit counter at submission start. If the
    // doctor edits while the GET/POST is in flight, the request persists
    // this submitted snapshot — the newer values must stay marked unsaved.
    const editEpochAtSubmit = editEpochRef.current;
    const dirtyAtSubmit = dirtyRef.current;
    const submittedEcho = echoDataRef.current;
    const submittedPaths = new Set(draftTouchedRef.current.keys());
    try {
      setLoading(true);
      setError('');
      setInfo('');
      setSuccess('');

      if (!visitId) {
        if (onSave) {
          onSave(submittedEcho);
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
      if (hydrating || hydrationFailed || savedEchoRef.current === undefined) {
        setInfo(t('cardio.cardio_echo_loading_existing'));
        return;
      }

      const existingEmr = await loadExistingEmrDraft(visitId);
      if (epoch !== formEpochRef.current) return;

      if (isReadOnlyEmr(existingEmr)) {
        setReadOnly(true);
        setInfo(t('cardio.cardio_echo_finalized'));
        return;
      }

      const existingEcho = getStoredEcho(existingEmr);
      if (echoSnapshot(existingEcho) !== savedEchoRef.current) {
        setSaveConflict(true);
        return;
      }

      // A pristine form does not author a new Echo revision.
      if (!dirtyAtSubmit) {
        setInfo(t(editEpochRef.current === editEpochAtSubmit
          ? 'cardio.cardio_echo_no_changes'
          : 'cardio.cardio_echo_draft_preserved'));
        return;
      }

      const payload = buildEchoEmrPayload(existingEmr, submittedEcho, visitId, submittedPaths);
      const response = await api.post(`/v2/emr/${visitId}`, payload);

      if (epoch !== formEpochRef.current) return; // visit switched mid-save

      if (response.status === 200) {
        invalidateEMRCache(visitId);
        const acknowledgedEcho = getStoredEcho(response.data);
        const savedEcho = acknowledgedEcho ?? payload.data.specialty_data.echo;
        savedEchoRef.current = echoSnapshot(savedEcho);
        for (const [path, editEpoch] of draftTouchedRef.current) {
          if (editEpoch <= editEpochAtSubmit) draftTouchedRef.current.delete(path);
        }
        const next = hydrateEcho(savedEcho, echoDataRef.current, draftTouchedRef.current.keys());
        applyEchoData(next);
        dirtyRef.current = draftTouchedRef.current.size > 0;
        if (dirtyRef.current) {
          setInfo(t('cardio.cardio_echo_saved_stale_edit'));
          return;
        }
        setSuccess(t('cardio.cardio_echo_saved_success'));
        onSave?.((acknowledgedEcho as EchoData | null) ?? submittedEcho);
        onDataUpdate?.();
      }
    } catch (err) {
      if (epoch !== formEpochRef.current) return;
      if ((err as HttpApiError)?.response?.status === 409) {
        setSaveConflict(true);
        return;
      }
      setError(t('cardio.cardio_echo_save_error'));
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
    fields: Array<{ key: string; label: string; placeholder?: string }>,
    expanded: boolean
  ) =>
  <div style={{ marginBottom: 24 }}>
      <div
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
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
            {fields.map((field) => {
              const fieldId = `${fieldIdPrefix}-${section}-${field.key}`;
              return (
                <div key={field.key}>
                  <label htmlFor={fieldId}>{field.label}</label>
                  <Input
                    id={fieldId}
                    readOnly={readOnly}
                    inputMode={section === 'additional' ? 'text' : 'decimal'}
                    value={String(getNestedValue(echoData[section], field.key) ?? '')}
                    onChange={event => handleChange(section, field.key, event.target.value)}
                    placeholder={field.placeholder}
                  />
                </div>
              );
            })}
          </div>
        </div>
    }
    </div>;

  const renderAdultTteMeasurements = (group: 'core' | 'extended') => (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))', gap: 16 }}>
      {ADULT_TTE_MEASUREMENT_KEYS.filter(key => ADULT_TTE_MEASUREMENTS[key].group === group).map(key => {
        const { unit } = ADULT_TTE_MEASUREMENTS[key];
        const id = `${fieldIdPrefix}-adult-tte-${key}`;
        const measurement = adultTte?.measurements?.[key];
        const invalid = adultTteInvalidKeys.includes(key);
        return (
          <div key={key}>
            <label htmlFor={id}>{t(`emr_workspace.echo_tte_${key}`)} ({unit})</label>
            <Input
              id={id}
              readOnly={readOnly}
              inputMode="decimal"
              value={measurement?.unit === unit ? measurement.value : ''}
              aria-invalid={invalid}
              aria-describedby={invalid ? `${fieldIdPrefix}-invalid-tte` : undefined}
              onChange={event => handleChange('adult_tte', `measurements.${key}`, { value: event.target.value, unit })}
            />
          </div>
        );
      })}
    </div>
  );


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
              disabled={readOnly || loading || hydrating || hydrationFailed || saveConflict || adultTteSaveBlocked || adultTteInvalidKeys.length > 0}>
              
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

        {saveConflict && !hydrating && !hydrationFailed && (
          <Alert severity="error" style={ALERT_MARGIN_STYLE}>
            {t('cardio.cardio_echo_conflict')}
            <Button variant="outline" size="small" style={RETRY_BUTTON_STYLE}
              onClick={() => setReloadRequest({ visit: visitId })}>
              {t('cardio.cardio_echo_rebase')}
            </Button>
          </Alert>
        )}

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
              onClick={() => setReloadRequest({ visit: visitId })}>
              {t('cardio.cardio_echo_retry')}
            </Button>
          </Alert>
        }

        <section aria-labelledby={`${fieldIdPrefix}-adult-tte-title`}>
          <h3 id={`${fieldIdPrefix}-adult-tte-title`}>{t('emr_workspace.echo_tte_reporting')}</h3>
          {unsupportedAdultTte ? (
            <p>{t('emr_workspace.echo_tte_unsupported_version')}</p>
          ) : <>
            {renderAdultTteMeasurements('core')}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))', gap: 16, marginTop: 16 }}>
              <div>
                <label htmlFor={`${fieldIdPrefix}-adult-tte-method`}>{t('emr_workspace.echo_tte_ef_method')}</label>
                <select
                  id={`${fieldIdPrefix}-adult-tte-method`}
                  disabled={readOnly}
                  value={adultTte?.ef_method ?? ''}
                  onChange={event => handleChange('adult_tte', 'ef_method', event.target.value)}
                  style={{ width: '100%', minHeight: 36, border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-md)', color: 'var(--mac-text-primary)', background: 'var(--mac-bg-primary)' }}
                >
                  <option value="">{t('emr_workspace.unknown_method')}</option>
                  {ADULT_TTE_EF_METHODS.map(method => (
                    <option key={method} value={method}>{t(`emr_workspace.echo_method_${method}`)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor={`${fieldIdPrefix}-adult-tte-date`}>{t('emr_workspace.echo_tte_study_date')}</label>
                <Input
                  id={`${fieldIdPrefix}-adult-tte-date`}
                  type="date"
                  readOnly={readOnly}
                  value={adultTte?.measured_at ?? ''}
                  onChange={event => handleChange('adult_tte', 'measured_at', event.target.value)}
                />
              </div>
            </div>
            <details style={{ marginTop: 16 }}>
              <summary>{t('emr_workspace.echo_tte_extended')}</summary>
              {renderAdultTteMeasurements('extended')}
            </details>
            {adultTte?.recorded_at && (
              <p>{t('emr_workspace.measurement_recorded', { date: new Date(adultTte.recorded_at).toLocaleString() })}</p>
            )}
            {adultTteInvalidKeys.length > 0 && (
              <p role="alert" id={`${fieldIdPrefix}-invalid-tte`}>
                {t('emr_workspace.echo_tte_number_error')}
                {adultTteInvalidKeys.includes('lvef') && ` ${t('emr_workspace.echo_tte_lvef')} (0–100%).`}
              </p>
            )}
          </>}
        </section>

        {(hasLegacyMeasurements || hydrating || hydrationFailed) && (
        <details open={hasLegacyMeasurements || hydrationFailed} style={{ marginTop: 24 }}>
          <summary>{t('emr_workspace.echo_legacy_measurements')}</summary>
        {/* Левый желудочек */}
        {renderSection(
          t('cardio.cardio_echo_section_left_ventricle'),
          'leftVentricle',
          [
          { key: 'edd', label: t('cardio.cardio_echo_field_edd') },
          { key: 'esd', label: t('cardio.cardio_echo_field_esd') },
          { key: 'ef', label: t('cardio.cardio_echo_field_ef') },
          { key: 'fs', label: t('cardio.cardio_echo_field_fs') },
          { key: 'ivs', label: t('cardio.cardio_echo_field_ivs') },
          { key: 'pw', label: t('cardio.cardio_echo_field_pw') }],

          expandedSections.leftVentricle
        )}

        {/* Правый желудочек */}
        {renderSection(
          t('cardio.cardio_echo_section_right_ventricle'),
          'rightVentricle',
          [
          { key: 'rvdd', label: t('cardio.cardio_echo_field_rvdd') },
          { key: 'rvot', label: t('cardio.cardio_echo_field_rvot') }],

          expandedSections.rightVentricle
        )}

        {/* Предсердия */}
        {renderSection(
          t('cardio.cardio_echo_section_atria'),
          'atria',
          [
          { key: 'la', label: t('cardio.cardio_echo_field_la') },
          { key: 'ra', label: t('cardio.cardio_echo_field_ra') }],

          expandedSections.atria
        )}

        {/* Клапаны */}
        {renderSection(
          t('cardio.cardio_echo_section_valves'),
          'valves',
          [
          { key: 'mitral.e', label: t('cardio.cardio_echo_field_mitral_e') },
          { key: 'mitral.a', label: t('cardio.cardio_echo_field_mitral_a') },
          { key: 'aortic.peak_velocity', label: t('cardio.cardio_echo_field_aortic') },
          { key: 'tricuspid.e', label: t('cardio.cardio_echo_field_tricuspid_e') }],

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

        <label htmlFor={`${fieldIdPrefix}-ef-method`}>{t('emr_workspace.ef_method')}</label>
        <Input id={`${fieldIdPrefix}-ef-method`}
          value={echoData.measurement_metadata?.ef_method ?? ''} maxLength={120} readOnly={readOnly}
          onChange={event => handleChange('measurement_metadata', 'ef_method', event.target.value)} />
        <label htmlFor={`${fieldIdPrefix}-measurement-date`}>{t('emr_workspace.measurement_date')}</label>
        <Input id={`${fieldIdPrefix}-measurement-date`} type="date" readOnly={readOnly}
          value={echoData.measurement_metadata?.measured_at ?? ''}
          onChange={event => handleChange('measurement_metadata', 'measured_at', event.target.value)} />
        {echoData.measurement_metadata?.recorded_at && (
          <p>{t('emr_workspace.measurement_recorded', {
            date: new Date(echoData.measurement_metadata.recorded_at).toLocaleString(),
          })}</p>
        )}
        </details>
        )}

        <div style={{ marginTop: 24 }}>
          <Typography variant="subtitle1" style={{ marginBottom: 8 }}>
            <label htmlFor={`${fieldIdPrefix}-comments`}>{t('cardio.cardio_echo_comments_title')}</label>
          </Typography>
          <Textarea
            id={`${fieldIdPrefix}-comments`}
            value={echoData.additional?.comments ?? ''}
            readOnly={readOnly}
            onChange={event => handleChange('additional', 'comments', event.target.value)}
            placeholder={t('cardio.cardio_echo_ph_comments')}
            rows={4}
          />
        </div>

        <div style={{ marginTop: 24 }}>
          <Typography variant="subtitle1" style={{ marginBottom: 8 }}>
            <label htmlFor={`${fieldIdPrefix}-conclusion`}>{t('cardio.cardio_echo_conclusion_title')}</label>
          </Typography>
          <Textarea
            id={`${fieldIdPrefix}-conclusion`}
            value={echoData.conclusion}
            readOnly={readOnly}
            onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
              if (readOnly) return;
              markEdited('conclusion');
              applyEchoData({ ...echoDataRef.current, conclusion: e.target.value });
            }}
            placeholder={t('cardio.cardio_echo_ph_conclusion')}
            rows={6} />
          
        </div>
      </CardContent>
    </Card>);

};


// audit/strict: removed self-referencing propTypes spread

export default EchoForm;
