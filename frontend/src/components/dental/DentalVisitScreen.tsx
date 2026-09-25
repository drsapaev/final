import { useTranslation } from '../../i18n/useTranslation';
/**
 * DentalVisitScreen — Phase 4+ minimalist visit screen for dentistry.
 *
 * Goal: 3 клика от очереди до закрытого визита.
 *   1. Очередь → клик на пациента → открывается этот экран
 *   2. Врач пишет 1-2 строки анамнеза
 *   3. Кликает на зуб в схеме → ToothModal → сохранение
 *   4. "Завершить визит" → confirm (C1) + critical diagnosis check (C3)
 *
 * Layout:
 *   ┌─────────────────────────────────────────────────┐
 *   │  Пациент: ...           [Завершить визит]       │
 *   ├─────────────────────────────────────────────────┤
 *   │  Жалобы/Анамнез (1-2 строки, всегда виден)      │
 *   ├─────────────────────────────────────────────────┤
 *   │  Схема зубов (TeethChart) — всегда виден        │
 *   │  Клик на зуб → ToothModal                       │
 *   ├─────────────────────────────────────────────────┤
 *   │  ▸ Дополнительно (свернуто: Гигиена/Пародонт/   │
 *   │    Прикус/Рентген) — разворачивается по желанию │
 *   ├─────────────────────────────────────────────────┤
 *   │  История визитов пациента (read-only)           │
 *   └─────────────────────────────────────────────────┘
 *
 * Все данные persist в EMR v2 через POST /v2/emr/{visitId}.
 * Поле specialty_data.tooth_status[toothNumber] обновляется через ToothModal.
 * Поля anamnesis_morbi / examination / diagnosis сохраняются через saveEMR().
 *
 * AI integration (исправление главной проблемы эффективности):
 *   - ICD-10 suggestion по жалобе → записывает код в visitPayload.icd10
 *   - Встроен в экран, не отдельная вкладка
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Button, Card, Badge, Input, Textarea, Label,
  Dialog, DialogTitle, DialogContent, DialogActions,
  Typography, Box, Alert, Skeleton,
} from '../ui/macos';
import {
  ArrowLeft, Stethoscope, CheckCircle, ChevronDown, ChevronUp,
  Brain, Plus, Trash2,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import logger from '../../utils/logger';
import notify from '../../services/notify';
import TeethChart from '../dental/TeethChart';
import ToothModal from '../dental/ToothModal';
import {
  TOOTH_STATUS_LABELS,
  TOOTH_STATUS_COLORS,
  getToothName,
} from '../dental/dentalConstants';
import AIAssistant from '../ai/AIAssistant';

// =============================================================================
// Helpers
// =============================================================================

const EMPTY_EMR_DATA = {
  complaints: '',
  anamnesis_morbi: '',
  examination: '',
  diagnosis: '',
  icd10_code: '',
  specialty: 'dentistry',
  specialty_data: {
    tooth_status: {},
    hygiene_indices: {},
    periodontal_pockets: {},
    measurements: {},
    radiographs: {},
    visit_protocol: {},
  },
  recommendations: '',
  notes: '',
};

const loadExistingEMR = async (visitId: string | number) => {
  if (!visitId) return null;
  const response = await apiClient.get(`/v2/emr/${visitId}`, {
    silent: true,
    validateStatus: (status: number) => status === 404 || (status >= 200 && status < 300),
  } as Record<string, unknown>);
  if (response.status === 404) return null;
  return response.data as { data?: Record<string, unknown>; row_version?: number };
};

const saveEMR = async (visitId: string | number, data: unknown, rowVersion: unknown, isDraft = true) => {
  const response = await apiClient.post(`/v2/emr/${visitId}`, {
    data,
    row_version: rowVersion ?? 0,
    is_draft: isDraft,
  });
  return response.data;
};

const isSameVisit = (left: string | number | null | undefined, right: string | number | null | undefined) =>
  left !== null && left !== undefined && right !== null && right !== undefined && String(left) === String(right);

const getHttpStatus = (error: unknown): number | undefined => {
  if (!error || typeof error !== 'object') return undefined;
  const response = (error as { response?: { status?: unknown } }).response;
  return typeof response?.status === 'number' ? response.status : undefined;
};

// =============================================================================
// Sub-components
// =============================================================================

interface PatientHeaderProps {
  patient: Record<string, unknown> | null;
  onCompleteVisit: () => void | Promise<void>;
  onBackToQueue?: () => void | Promise<void>;
  backDisabled?: boolean;
  loading?: boolean;
}

const PatientHeader = ({ patient, onCompleteVisit, onBackToQueue, backDisabled, loading }: PatientHeaderProps) => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  const patientName =
    patient?.patient_name ||
    patient?.name ||
    `№${patient?.number || '?'}`;
  const patientInfo = (patient?.patient as Record<string, unknown> | undefined)?.phone || patient?.phone || '';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 16,
        flexWrap: 'wrap',
        padding: '16px 20px',
        borderBottom: '1px solid var(--mac-border)',
      }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
        <Stethoscope size={24} aria-hidden="true" style={{ color: 'var(--mac-accent-blue)' }} />
        <div style={{ minWidth: 0 }}>
          <Typography variant="h6" style={{ margin: 0, fontWeight: 600 }}>
            {t('dental.dental_dvs_header_title', { name: patientName })}
          </Typography>
          {patientInfo && (
            <Typography variant="body2" color="textSecondary" style={{ margin: 0 }}>
              {String(patientInfo)}
            </Typography>
          )}
        </div>
      </div>
      <div className="dental-flex dental-gap-12">
        {onBackToQueue && (
          <Button
            variant="outline"
            onClick={() => { void onBackToQueue(); }}
            disabled={backDisabled}
            aria-label={t('doctor.tab_queue')}>
            <ArrowLeft size={16} aria-hidden="true" />
            {t('doctor.tab_queue')}
          </Button>
        )}
        <Button
          variant="primary"
          onClick={() => { void onCompleteVisit(); }}
          disabled={loading}
          aria-label={t('dental.dental_dvs_aria_complete')}>
          <CheckCircle size={16} style={{ marginRight: 6 }} aria-hidden="true" />
          {loading ? t('dental.dental_dvs_saving') : t('dental.dental_dvs_complete_visit')}
        </Button>
      </div>
    </div>
  );
};


interface AnamnesisSectionProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

const AnamnesisSection = ({ value, onChange, disabled }: AnamnesisSectionProps) => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  return (
    <div style={{ marginBottom: 16 }}>
      <Label htmlFor="dental-anamnesis" style={{ display: 'block', marginBottom: 6 }}>
        {t('dental.dental_dvs_anamnesis_label')}
      </Label>
      <Textarea
        id="dental-anamnesis"
        aria-label={t('dental.dental_dvs_anamnesis_aria')}
        value={value}
        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onChange(e.target.value)}
        placeholder={t('dental.dental_dvs_anamnesis_placeholder')}
        minRows={2}
        disabled={disabled}
        style={{ width: '100%', boxSizing: 'border-box' }}
      />
      <Typography variant="caption" color="textSecondary" style={{ marginTop: 4, display: 'block' }}>
        {t('dental.dental_dvs_anamnesis_hint')}
      </Typography>
    </div>
  );
};


interface ToothSummaryProps {
  toothStatus?: Record<string, unknown> | null;
}

const ToothSummary = ({ toothStatus }: ToothSummaryProps) => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  const teeth = Object.entries(toothStatus || {});
  if (teeth.length === 0) {
    return (
      <Typography variant="body2" color="textSecondary" style={{ fontStyle: 'italic' }}>
        {t('dental.dental_dvs_no_teeth')}
      </Typography>
    );
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
      {teeth.map(([toothNum, data]: [string, any]) => {
        const status = (data?.status || 'healthy') as keyof typeof TOOTH_STATUS_LABELS | string;
        const label = (TOOTH_STATUS_LABELS as Record<string, string>)[status] || status;
        const color = (TOOTH_STATUS_COLORS as Record<string, string>)[status] || 'var(--mac-text-tertiary)';
        const procedures: Array<{ name?: string } | Record<string, unknown>> =
          Array.isArray(data?.procedures) ? data.procedures : [];
        return (
          <Badge
            key={toothNum}
            variant="default"
            style={{
              backgroundColor: color + '20',
              color,
              border: `1px solid ${color}`,
              padding: '4px 8px',
              fontSize: 12,
            }}
            title={`${t('dental.dental_dvs_tooth_label')} ${toothNum} — ${getToothName(toothNum)}: ${label}${procedures.length > 0 ? ` (${procedures.map((p: { name?: string } | Record<string, unknown>) => (p as { name?: string }).name).join(', ')})` : ''}`}>
            {toothNum}: {label}
            {procedures.length > 0 && ` · ${procedures.length}℅`}
          </Badge>
        );
      })}
    </div>
  );
};


interface DiagnosisSectionProps {
  diagnosis: string;
  icd10: string;
  onDiagnosisChange: (value: string) => void;
  onIcd10Change: (value: string) => void;
  onAISuggestion: () => void;
  disabled?: boolean;
}

const DiagnosisSection = ({ diagnosis, icd10, onDiagnosisChange, onIcd10Change, onAISuggestion, disabled }: DiagnosisSectionProps) => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 200px', gap: 12, marginBottom: 16 }}>
      <div>
        <Label htmlFor="dental-diagnosis" style={{ display: 'block', marginBottom: 6 }}>
          {t('dental.dental_dvs_diagnosis_label')}
        </Label>
        <Input
          id="dental-diagnosis"
          aria-label={t('dental.dental_dvs_diagnosis_aria')}
          value={diagnosis}
          onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onDiagnosisChange(e.target.value)}
          placeholder={t('dental.dental_dvs_diagnosis_placeholder')}
          disabled={disabled}
          style={{ width: '100%', boxSizing: 'border-box' }}
        />
      </div>
      <div>
        <Label htmlFor="dental-icd10" style={{ display: 'block', marginBottom: 6 }}>
          {t('dental.dental_dvs_icd10_label')}
        </Label>
        <Input
          id="dental-icd10"
          aria-label={t('dental.dental_dvs_icd10_aria')}
          value={icd10}
          onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onIcd10Change(e.target.value)}
          placeholder="K02.1"
          disabled={disabled}
          style={{ width: '100%', boxSizing: 'border-box' }}
        />
      </div>
      <div style={{ gridColumn: '1 / -1' }}>
        <Button
          variant="outline"
          size="small"
          onClick={() => document.getElementById('dental-ai-suggest-icd10')?.click()}
          disabled={disabled}
          aria-label={t('dental.dental_dvs_aria_ai_icd10')}>
          <Brain size={14} style={{ marginRight: 6 }} aria-hidden="true" />
          {t('dental.dental_dvs_ai_btn')}
        </Button>
        <button
          id="dental-ai-suggest-icd10"
          style={{ display: 'none' }}
          onClick={onAISuggestion}
          aria-hidden="true"
          aria-label="AI suggest ICD-10 trigger"
          tabIndex={-1}
        />
      </div>
    </div>
  );
};


interface CollapsibleExtrasProps {
  hygieneIndices: Record<string, unknown>;
  onHygieneChange: (key: string, value: string | number) => void;
  disabled?: boolean;
}

const CollapsibleExtras = ({ hygieneIndices, onHygieneChange, disabled }: CollapsibleExtrasProps) => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  const [open, setOpen] = useState(false);

  return (
    <div style={{ marginBottom: 16, border: '1px solid var(--mac-border)', borderRadius: 8 }}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label={t('dental.dental_dvs_aria_extras')}
        style={{
          width: '100%',
          padding: '10px 14px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: 'var(--mac-text-primary)',
          fontSize: 14,
          fontWeight: 500,
        }}>
        <span>{t('dental.dental_dvs_extras_label')}</span>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && (
        <div style={{ padding: '0 14px 14px' }}>
          <Typography variant="caption" color="textSecondary" style={{ display: 'block', marginBottom: 8 }}>
            {t('dental.dental_dvs_extras_hint')}
          </Typography>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
            <div>
              <Label htmlFor="dental-ohis" style={{ display: 'block', marginBottom: 4 }}>OHIS</Label>
              <Input
                id="dental-ohis"
                type="number"
                aria-label={t('dental.dental_dvs_aria_ohis')}
                value={String(hygieneIndices?.ohis ?? '')}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onHygieneChange('ohis', e.target.value)}
                placeholder="0.0 - 6.0"
                disabled={disabled}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
            </div>
            <div>
              <Label htmlFor="dental-pli" style={{ display: 'block', marginBottom: 4 }}>PLI</Label>
              <Input
                id="dental-pli"
                type="number"
                aria-label={t('dental.dental_dvs_aria_pli')}
                value={String(hygieneIndices?.pli ?? '')}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onHygieneChange('pli', e.target.value)}
                placeholder="0.0 - 3.0"
                disabled={disabled}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
            </div>
            <div>
              <Label htmlFor="dental-cpi" style={{ display: 'block', marginBottom: 4 }}>CPI</Label>
              <Input
                id="dental-cpi"
                type="number"
                aria-label={t('dental.dental_dvs_aria_cpi')}
                value={String(hygieneIndices?.cpi ?? '')}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onHygieneChange('cpi', e.target.value)}
                placeholder="0 - 4"
                disabled={disabled}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
            </div>
            <div>
              <Label htmlFor="dental-bleeding" style={{ display: 'block', marginBottom: 4 }}>{t('dental.dental_dvs_bleeding_label')}</Label>
              <Input
                id="dental-bleeding"
                type="number"
                aria-label={t('dental.dental_dvs_aria_bleeding')}
                value={String(hygieneIndices?.bleeding ?? '')}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onHygieneChange('bleeding', e.target.value)}
                placeholder="0 - 100"
                disabled={disabled}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
            </div>
          </div>
          <Typography variant="caption" color="textSecondary" style={{ display: 'block', marginTop: 10 }}>
            {t('dental.dental_dvs_extras_footer')}
          </Typography>
        </div>
      )}
    </div>
  );
};


type VisitProtocolRecord = Record<string, unknown>;
type VisitProtocolUpdater = (current: VisitProtocolRecord) => VisitProtocolRecord;
type VisitProtocolUpdate = (update: VisitProtocolUpdater) => void;

const protocolRecord = (value: unknown): VisitProtocolRecord =>
  value && typeof value === 'object' && !Array.isArray(value)
    ? value as VisitProtocolRecord
    : {};

const VisitProtocolSections = ({
  value,
  onUpdate,
  disabled,
}: {
  value: VisitProtocolRecord;
  onUpdate: VisitProtocolUpdate;
  disabled?: boolean;
}) => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  const entries = (field: string) => Array.isArray(value[field])
    ? (value[field] as unknown[]).map(protocolRecord)
    : [];
  const updateField = (field: string, nextValue: unknown) => {
    onUpdate((current) => ({ ...current, [field]: nextValue }));
  };
  const updateArrayItem = (field: string, index: number, patch: VisitProtocolRecord) => {
    onUpdate((current) => {
      const currentItems = Array.isArray(current[field])
        ? current[field] as unknown[]
        : [];
      return {
        ...current,
        [field]: currentItems.map((item, itemIndex) => itemIndex === index
          ? { ...protocolRecord(item), ...patch }
          : item),
      };
    });
  };
  const addArrayItem = (field: string, item: VisitProtocolRecord) => {
    onUpdate((current) => ({
      ...current,
      [field]: [...(Array.isArray(current[field]) ? current[field] as unknown[] : []), item],
    }));
  };
  const removeArrayItem = (field: string, index: number) => {
    onUpdate((current) => {
      const currentItems = Array.isArray(current[field])
        ? current[field] as unknown[]
        : [];
      return { ...current, [field]: currentItems.filter((_, itemIndex) => itemIndex !== index) };
    });
  };
  const inputValue = (item: VisitProtocolRecord, field: string) => String(item[field] ?? '');
  const procedures = entries('procedures');
  const materials = entries('materials');
  const anesthesia = entries('anesthesia');
  const radiographs = entries('radiographs');
  const prescriptions = entries('prescriptions');
  const nextVisit = protocolRecord(value.nextVisit);

  return (
    <section className="dental-flex-col dental-gap-12" aria-labelledby="dental-visit-protocol-title">
      <div>
        <h3 id="dental-visit-protocol-title" className="dental-text-primary">
          {t('dental.dental_vp_title')}
        </h3>
        <p className="dental-text-desc dental-text-secondary">{t('dental.dental_vp_subtitle')}</p>
      </div>

      <details>
        <summary>{t('dental.dental_vp_tab_procedures')}</summary>
        <p className="dental-text-desc dental-text-secondary">{t('dental.dental_vp_proc_subtitle')}</p>
        <div className="dental-flex-col dental-gap-12">
          {procedures.map((procedure, index) => (
            <div className="dental-flex-col dental-gap-12" key={`procedure-${index}`}>
              <Input
                aria-label={`${t('dental.dental_vp_proc_label_name')} ${index + 1}`}
                value={inputValue(procedure, 'name')}
                onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('procedures', index, { name: event.target.value })}
                disabled={disabled}
              />
              <Input
                type="time"
                aria-label={t('dental.dental_vp_proc_aria_start', { index: index + 1 })}
                value={inputValue(procedure, 'startTime')}
                onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('procedures', index, { startTime: event.target.value })}
                disabled={disabled}
              />
              <Input
                type="time"
                aria-label={t('dental.dental_vp_proc_aria_end', { index: index + 1 })}
                value={inputValue(procedure, 'endTime')}
                onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('procedures', index, { endTime: event.target.value })}
                disabled={disabled}
              />
              <Input
                aria-label={t('dental.dental_vp_proc_aria_teeth', { index: index + 1 })}
                value={inputValue(procedure, 'teeth')}
                placeholder={t('dental.dental_vp_proc_ph_teeth')}
                onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('procedures', index, { teeth: event.target.value })}
                disabled={disabled}
              />
              <Textarea
                aria-label={t('dental.dental_vp_proc_aria_desc', { index: index + 1 })}
                value={inputValue(procedure, 'description')}
                placeholder={t('dental.dental_vp_proc_ph_desc')}
                onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('procedures', index, { description: event.target.value })}
                disabled={disabled}
              />
              <label className="dental-flex dental-gap-12">
                <input
                  type="checkbox"
                  aria-label={t('dental.dental_vp_proc_aria_completed', { index: index + 1 })}
                  checked={Boolean(procedure.completed)}
                  onChange={(event: React.ChangeEvent<HTMLInputElement>) => updateArrayItem('procedures', index, { completed: event.target.checked })}
                  disabled={disabled}
                />
                {t('dental.dental_vp_proc_chk_completed')}
              </label>
              <label className="dental-flex dental-gap-12">
                <input
                  type="checkbox"
                  aria-label={t('dental.dental_vp_proc_aria_complications', { index: index + 1 })}
                  checked={Boolean(procedure.complications)}
                  onChange={(event: React.ChangeEvent<HTMLInputElement>) => updateArrayItem('procedures', index, { complications: event.target.checked })}
                  disabled={disabled}
                />
                {t('dental.dental_vp_proc_chk_complications')}
              </label>
              <Button variant="outline" size="small" onClick={() => removeArrayItem('procedures', index)} disabled={disabled}>
                <Trash2 size={14} aria-hidden="true" />
                {t('dental.dental_vp_proc_aria_remove', { index: index + 1 })}
              </Button>
            </div>
          ))}
          <Button variant="outline" size="small" onClick={() => addArrayItem('procedures', { name: '', teeth: '', description: '' })} disabled={disabled}>
            <Plus size={14} aria-hidden="true" />
            {t('dental.dental_vp_proc_btn_add')}
          </Button>
        </div>
      </details>

      <details>
        <summary>{t('dental.dental_vp_tab_materials')}</summary>
        <p className="dental-text-desc dental-text-secondary">{t('dental.dental_vp_mat_subtitle')}</p>
        <div className="dental-flex-col dental-gap-12">
          {materials.map((material, index) => (
            <div className="dental-flex-col dental-gap-12" key={`material-${index}`}>
              <Input aria-label={t('dental.dental_vp_mat_aria_name', { index: index + 1 })} value={inputValue(material, 'name')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('materials', index, { name: event.target.value })} disabled={disabled} />
              <Input aria-label={t('dental.dental_vp_mat_aria_quantity', { index: index + 1 })} value={inputValue(material, 'quantity')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('materials', index, { quantity: event.target.value })} disabled={disabled} />
              <Input aria-label={t('dental.dental_vp_mat_aria_batch', { index: index + 1 })} value={inputValue(material, 'batch')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('materials', index, { batch: event.target.value })} disabled={disabled} />
              <Textarea aria-label={t('dental.dental_vp_mat_aria_notes', { index: index + 1 })} value={inputValue(material, 'notes')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('materials', index, { notes: event.target.value })} disabled={disabled} />
              <Button variant="outline" size="small" onClick={() => removeArrayItem('materials', index)} disabled={disabled}>
                <Trash2 size={14} aria-hidden="true" />
                {t('dental.dental_vp_mat_aria_remove', { index: index + 1 })}
              </Button>
            </div>
          ))}
          <Button variant="outline" size="small" onClick={() => addArrayItem('materials', { name: '', quantity: '', batch: '', notes: '' })} disabled={disabled}>
            <Plus size={14} aria-hidden="true" />
            {t('dental.dental_vp_mat_btn_add')}
          </Button>
        </div>
      </details>

      <details>
        <summary>{t('dental.dental_vp_tab_anesthesia')}</summary>
        <p className="dental-text-desc dental-text-secondary">{t('dental.dental_vp_anes_subtitle')}</p>
        <div className="dental-flex-col dental-gap-12">
          {anesthesia.map((item, index) => (
            <div className="dental-flex-col dental-gap-12" key={`anesthesia-${index}`}>
              <Input aria-label={t('dental.dental_vp_anes_aria_drug', { index: index + 1 })} value={inputValue(item, 'drug')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('anesthesia', index, { drug: event.target.value })} disabled={disabled} />
              <Input aria-label={t('dental.dental_vp_anes_aria_dose', { index: index + 1 })} value={inputValue(item, 'dose')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('anesthesia', index, { dose: event.target.value })} disabled={disabled} />
              <Input aria-label={t('dental.dental_vp_anes_label_method')} value={inputValue(item, 'method')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('anesthesia', index, { method: event.target.value })} disabled={disabled} />
              <Input aria-label={t('dental.dental_vp_anes_aria_area', { index: index + 1 })} value={inputValue(item, 'area')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('anesthesia', index, { area: event.target.value })} disabled={disabled} />
              <label className="dental-flex dental-gap-12">
                <input
                  type="checkbox"
                  aria-label={t('dental.dental_vp_anes_aria_effective', { index: index + 1 })}
                  checked={Boolean(item.effective)}
                  onChange={(event: React.ChangeEvent<HTMLInputElement>) => updateArrayItem('anesthesia', index, { effective: event.target.checked })}
                  disabled={disabled}
                />
                {t('dental.dental_vp_anes_chk_effective')}
              </label>
              <label className="dental-flex dental-gap-12">
                <input
                  type="checkbox"
                  aria-label={t('dental.dental_vp_anes_aria_complications', { index: index + 1 })}
                  checked={Boolean(item.complications)}
                  onChange={(event: React.ChangeEvent<HTMLInputElement>) => updateArrayItem('anesthesia', index, { complications: event.target.checked })}
                  disabled={disabled}
                />
                {t('dental.dental_vp_anes_chk_complications')}
              </label>
              <Button variant="outline" size="small" onClick={() => removeArrayItem('anesthesia', index)} disabled={disabled}>
                <Trash2 size={14} aria-hidden="true" />
                {t('dental.dental_vp_anes_aria_remove', { index: index + 1 })}
              </Button>
            </div>
          ))}
          <Button variant="outline" size="small" onClick={() => addArrayItem('anesthesia', { drug: '', dose: '', method: '', area: '' })} disabled={disabled}>
            <Plus size={14} aria-hidden="true" />
            {t('dental.dental_vp_anes_btn_add')}
          </Button>
        </div>
      </details>

      <details>
        <summary>{t('dental.dental_vp_tab_radiographs')}</summary>
        <p className="dental-text-desc dental-text-secondary">{t('dental.dental_vp_radio_subtitle')}</p>
        <div className="dental-flex-col dental-gap-12">
          {radiographs.map((item, index) => (
            <div className="dental-flex-col dental-gap-12" key={`radiograph-${index}`}>
              <Input aria-label={t('dental.dental_vp_radio_label_type')} value={inputValue(item, 'type')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('radiographs', index, { type: event.target.value })} disabled={disabled} />
              <Input aria-label={t('dental.dental_vp_radio_aria_area', { index: index + 1 })} value={inputValue(item, 'area')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('radiographs', index, { area: event.target.value })} disabled={disabled} />
              <Textarea aria-label={t('dental.dental_vp_radio_aria_findings', { index: index + 1 })} value={inputValue(item, 'findings')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('radiographs', index, { findings: event.target.value })} disabled={disabled} />
              <Button variant="outline" size="small" onClick={() => removeArrayItem('radiographs', index)} disabled={disabled}>
                <Trash2 size={14} aria-hidden="true" />
                {t('dental.dental_vp_radio_aria_remove', { index: index + 1 })}
              </Button>
            </div>
          ))}
          <Button variant="outline" size="small" onClick={() => addArrayItem('radiographs', { type: '', area: '', findings: '' })} disabled={disabled}>
            <Plus size={14} aria-hidden="true" />
            {t('dental.dental_vp_radio_btn_add')}
          </Button>
        </div>
      </details>

      <details>
        <summary>{t('dental.dental_vp_tab_prescriptions')}</summary>
        <p className="dental-text-desc dental-text-secondary">{t('dental.dental_vp_rx_subtitle')}</p>
        <div className="dental-flex-col dental-gap-12">
          {prescriptions.map((item, index) => (
            <div className="dental-flex-col dental-gap-12" key={`prescription-${index}`}>
              <Input aria-label={t('dental.dental_vp_rx_aria_medication', { index: index + 1 })} value={inputValue(item, 'medication')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('prescriptions', index, { medication: event.target.value })} disabled={disabled} />
              <Input aria-label={t('dental.dental_vp_rx_aria_dosage', { index: index + 1 })} value={inputValue(item, 'dosage')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('prescriptions', index, { dosage: event.target.value })} disabled={disabled} />
              <Textarea aria-label={t('dental.dental_vp_rx_aria_instructions', { index: index + 1 })} value={inputValue(item, 'instructions')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateArrayItem('prescriptions', index, { instructions: event.target.value })} disabled={disabled} />
              <Button variant="outline" size="small" onClick={() => removeArrayItem('prescriptions', index)} disabled={disabled}>
                <Trash2 size={14} aria-hidden="true" />
                {t('dental.dental_vp_rx_aria_remove', { index: index + 1 })}
              </Button>
            </div>
          ))}
          <Button variant="outline" size="small" onClick={() => addArrayItem('prescriptions', { medication: '', dosage: '', instructions: '' })} disabled={disabled}>
            <Plus size={14} aria-hidden="true" />
            {t('dental.dental_vp_rx_btn_add')}
          </Button>
          <Textarea
            aria-label={t('dental.dental_vp_aria_recommendations')}
            value={String(value.recommendations ?? '')}
            placeholder={t('dental.dental_vp_ph_recommendations')}
            onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => updateField('recommendations', event.target.value)}
            disabled={disabled}
          />
        </div>
      </details>

      <details>
        <summary>{t('dental.dental_vp_next_visit_title')}</summary>
        <div className="dental-flex-col dental-gap-12">
          <Input type="date" aria-label={t('dental.dental_vp_next_visit_aria_date')} value={String(nextVisit.date ?? '')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onUpdate((current) => ({ ...current, nextVisit: { ...protocolRecord(current.nextVisit), date: event.target.value } }))} disabled={disabled} />
          <Input type="time" aria-label={t('dental.dental_vp_next_visit_aria_time')} value={String(nextVisit.time ?? '')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onUpdate((current) => ({ ...current, nextVisit: { ...protocolRecord(current.nextVisit), time: event.target.value } }))} disabled={disabled} />
          <Input aria-label={t('dental.dental_vp_next_visit_aria_purpose')} value={String(nextVisit.purpose ?? '')} placeholder={t('dental.dental_vp_next_visit_ph_purpose')} onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onUpdate((current) => ({ ...current, nextVisit: { ...protocolRecord(current.nextVisit), purpose: event.target.value } }))} disabled={disabled} />
        </div>
      </details>
    </section>
  );
};


interface VisitHistoryProps {
  history: Array<Record<string, unknown>>;
  loading?: boolean;
}

const VisitHistory = ({ history, loading }: VisitHistoryProps) => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  if (loading) {
    return <Skeleton style={{ height: 80, borderRadius: 8 }} />;
  }
  if (!history || history.length === 0) {
    return (
      <Typography variant="body2" color="textSecondary" style={{ fontStyle: 'italic' }}>
        {t('dental.dental_dvs_no_history')}
      </Typography>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {history.map((visit, idx) => {
        const v = visit as Record<string, unknown>;
        return (
        <div
          key={String(v.id ?? idx)}
          style={{
            padding: '8px 12px',
            border: '1px solid var(--mac-border)',
            borderRadius: 6,
            background: 'var(--mac-bg-secondary)',
          }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
            <Typography variant="body2" style={{ fontWeight: 500 }}>
              {String(v.date ?? v.created_at ?? '—')}
            </Typography>
            {Boolean(v.icd10_code) && (
              <Badge variant="primary" size="small">{t('dental.dental_dvs_icd10_label')}: {String(v.icd10_code)}</Badge>
            )}
          </div>
          {Boolean(v.diagnosis) && (
            <Typography variant="body2" color="textSecondary" style={{ marginTop: 4 }}>
              {String(v.diagnosis)}
            </Typography>
          )}
          {Boolean(v.complaints) && (
            <Typography variant="caption" color="textSecondary" style={{ marginTop: 2, display: 'block' }}>
              {t('dental.dental_dvs_history_complaints', { text: String(v.complaints) })}
            </Typography>
          )}
        </div>
        );
      })}
    </div>
  );
};


// =============================================================================
// AI Suggestion Dialog (исправляет главную проблему: AI suggestions не попадали в EMR)
// =============================================================================

interface AISuggestionDialogProps {
  open: boolean;
  onClose: () => void;
  onApply: (suggestion: string) => void;
  anamnesis: string;
}

const AISuggestionDialog = ({ open, onClose, onApply, anamnesis }: AISuggestionDialogProps) => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          <Brain size={18} aria-hidden="true" />
          {t('dental.dental_dvs_ai_dialog_title')}
        </Box>
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="textSecondary" style={{ marginBottom: 12 }}>
          {t('dental.dental_dvs_ai_dialog_hint')}
        </Typography>
        <Alert severity="info" style={{ marginBottom: 12 }}>
          {t('dental.dental_dvs_ai_dialog_alert')}
        </Alert>
        <AIAssistant
          analysisType="icd10"
          data={{
            symptoms: [],
            diagnosis: anamnesis || '',
            specialty: 'dentistry',
            maxSuggestions: 8,
          }}
          onSuggestionSelect={(type, suggestion) => {
            if (type === 'icd10') {
              onApply(String(suggestion));
              onClose();
            }
          }}
          title={t('dental.dental_dvs_ai_assistant_title')}
          expanded
        />
      </DialogContent>
      <DialogActions>
        <Button variant="outline" onClick={onClose}>{t('dental.dental_dvs_close')}</Button>
      </DialogActions>
    </Dialog>
  );
};


// =============================================================================
// Main component
// =============================================================================

const DentalVisitScreen = ({
  patient,
  onCompleteVisit,
  onBackToQueue,
  loading: parentLoading,
}: {
  patient?: { visit_id?: string | number; patient_id?: string | number; id?: string | number; patient?: { id?: string | number } };
  onCompleteVisit?: (latestDraft: Record<string, unknown>) => void | Promise<void>;
  onBackToQueue?: () => void | Promise<void>;
  loading?: boolean;
  [k: string]: unknown;
}) => {
  const { t: rawT } = useTranslation();
  // The project adapter creates a new t wrapper on every render. Keep the
  // loader callbacks stable while still using the current locale function.
  const translationRef = useRef(rawT);
  translationRef.current = rawT;
  const t = useCallback(
    (key: string, params?: Record<string, unknown>) => translationRef.current(key, params),
    [],
  );
  const [emrData, setEmrData] = useState(EMPTY_EMR_DATA);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [loadError, setLoadError] = useState<'missing_visit' | 'load' | null>(null);
  const [saveError, setSaveError] = useState<'conflict' | 'save' | null>(null);
  const [loadedVisitId, setLoadedVisitId] = useState<string | number | null>(null);
  const [selectedTooth, setSelectedTooth] = useState<{ number: string | number; data: Record<string, unknown> } | null>(null);
  const [toothModalOpen, setToothModalOpen] = useState(false);
  const [showAIDialog, setShowAIDialog] = useState(false);
  const [history, setHistory] = useState<Array<Record<string, unknown>>>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const visitId = patient?.visit_id;
  const patientId =
    patient?.patient?.id ||
    patient?.patient_id ||
    patient?.id ||
    null;

  const latestDraftRef = useRef<typeof EMPTY_EMR_DATA>(EMPTY_EMR_DATA);
  const rowVersionRef = useRef(0);
  const loadedVisitIdRef = useRef<string | number | null>(null);
  const retryCompletionRef = useRef(false);
  const loadSequenceRef = useRef(0);
  const historySequenceRef = useRef(0);
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // A failed EMR read must not be treated as an empty draft. Keep the visit
  // open and require a successful read before editing or completing it.
  const loadEMR = useCallback(async () => {
    const requestSequence = ++loadSequenceRef.current;
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    setLoading(true);
    setSaving(false);
    setCompleting(false);
    setLoadError(null);
    setSaveError(null);
    retryCompletionRef.current = false;
    setLoadedVisitId(null);
    loadedVisitIdRef.current = null;
    latestDraftRef.current = EMPTY_EMR_DATA;
    rowVersionRef.current = 0;
    setEmrData(EMPTY_EMR_DATA);

    if (visitId === null || visitId === undefined || visitId === '') {
      setLoadError('missing_visit');
      setLoading(false);
      return;
    }

    try {
      const existing = await loadExistingEMR(visitId);
      if (requestSequence !== loadSequenceRef.current) return;

      const rowVersion = existing?.row_version;
      if (existing && (typeof rowVersion !== 'number' || !Number.isInteger(rowVersion))) {
        throw new Error('Invalid EMR version response');
      }

      const data = (existing?.data || EMPTY_EMR_DATA) as typeof EMPTY_EMR_DATA;
      const specialtyData = data.specialty_data || EMPTY_EMR_DATA.specialty_data;
      const protocolData = specialtyData.visit_protocol || (data as Record<string, unknown>).visit_protocol;
      const nextDraft = {
        ...EMPTY_EMR_DATA,
        ...data,
        specialty_data: {
          ...EMPTY_EMR_DATA.specialty_data,
          ...specialtyData,
          visit_protocol: protocolData || EMPTY_EMR_DATA.specialty_data.visit_protocol,
        },
      };
      latestDraftRef.current = nextDraft;
      rowVersionRef.current = rowVersion ?? 0;
      loadedVisitIdRef.current = visitId;
      setLoadedVisitId(visitId);
      setEmrData(nextDraft);
    } catch {
      if (requestSequence !== loadSequenceRef.current) return;
      logger.warn('[DentalVisitScreen] loadEMR failed');
      setLoadError('load');
      notify.error(t('dental2.visit_map_load_failed'));
    } finally {
      if (requestSequence === loadSequenceRef.current) setLoading(false);
    }
  }, [visitId, t]);

  // Load patient history
  const loadHistory = useCallback(async () => {
    const requestSequence = ++historySequenceRef.current;
    if (!patientId) {
      setHistory([]);
      setHistoryLoading(false);
      return;
    }
    setHistory([]);
    setHistoryLoading(true);
    try {
      const response = await apiClient.get(`/v2/emr/patient/${patientId}`, {
        silent: true,
        validateStatus: (status: number) => status === 404 || (status >= 200 && status < 300),
      } as Record<string, unknown>);
      if (requestSequence !== historySequenceRef.current) return;
      if (response.status === 404) {
        setHistory([]);
      } else {
        const summaries = response.data?.summaries || response.data || [];
        setHistory(Array.isArray(summaries) ? summaries : []);
      }
    } catch {
      if (requestSequence !== historySequenceRef.current) return;
      logger.warn('[DentalVisitScreen] loadHistory failed');
      setHistory([]);
    } finally {
      if (requestSequence === historySequenceRef.current) setHistoryLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    void loadEMR();
    void loadHistory();
    return () => {
      loadSequenceRef.current += 1;
      historySequenceRef.current += 1;
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
    };
  }, [loadEMR, loadHistory]);

  const persistDraft = useCallback((targetVisitId: string | number, snapshot: typeof EMPTY_EMR_DATA) => {
    const operation = saveQueueRef.current.catch(() => undefined).then(async () => {
      if (!isSameVisit(loadedVisitIdRef.current, targetVisitId)) {
        throw new Error('Visit changed before EMR save');
      }

      const response = await saveEMR(targetVisitId, snapshot, rowVersionRef.current, true) as { row_version?: unknown };
      if (typeof response.row_version !== 'number' || !Number.isInteger(response.row_version)) {
        throw new Error('EMR save response is missing row_version');
      }
      if (isSameVisit(loadedVisitIdRef.current, targetVisitId)) {
        rowVersionRef.current = response.row_version;
      }
    });
    saveQueueRef.current = operation.then(() => undefined, () => undefined);
    return operation;
  }, []);

  // Keep draft writes sequential so each POST uses the version returned by
  // the previous successful save.
  const scheduleAutosave = useCallback((nextData: typeof EMPTY_EMR_DATA) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    const scheduledVisitId = visitId;
    saveTimerRef.current = setTimeout(() => {
      saveTimerRef.current = null;
      if (scheduledVisitId === null || scheduledVisitId === undefined || !isSameVisit(loadedVisitIdRef.current, scheduledVisitId)) return;

      setSaving(true);
      void persistDraft(scheduledVisitId, nextData).then(() => {
        if (isSameVisit(loadedVisitIdRef.current, scheduledVisitId)) setSaveError(null);
      }).catch((error: unknown) => {
        if (!isSameVisit(loadedVisitIdRef.current, scheduledVisitId)) return;
        setSaveError(getHttpStatus(error) === 409 ? 'conflict' : 'save');
        logger.warn('[DentalVisitScreen] autosave failed');
        notify.error(t('dental2.visit_protocol_save_failed'));
      }).finally(() => {
        if (isSameVisit(loadedVisitIdRef.current, scheduledVisitId)) setSaving(false);
      });
    }, 1500);
  }, [persistDraft, t, visitId]);

  const updateField = useCallback((field: string, value: unknown) => {
    const next = { ...latestDraftRef.current, [field]: value } as typeof EMPTY_EMR_DATA;
    latestDraftRef.current = next;
    setEmrData(next);
    setSaveError(null);
    scheduleAutosave(next);
  }, [scheduleAutosave]);

  const updateSpecialtyData = useCallback((field: string, value: unknown) => {
    const next = {
      ...latestDraftRef.current,
      specialty_data: {
        ...latestDraftRef.current.specialty_data,
        [field]: value,
      },
    } as typeof EMPTY_EMR_DATA;
    latestDraftRef.current = next;
    setEmrData(next);
    setSaveError(null);
    scheduleAutosave(next);
  }, [scheduleAutosave]);

  const updateVisitProtocol = useCallback((update: VisitProtocolUpdater) => {
    const current = protocolRecord(latestDraftRef.current.specialty_data.visit_protocol);
    updateSpecialtyData('visit_protocol', update(current));
  }, [updateSpecialtyData]);

  const handleCompleteVisit = useCallback(async () => {
    const targetVisitId = visitId;
    if (targetVisitId === null || targetVisitId === undefined || targetVisitId === '') {
      setLoadError('missing_visit');
      return;
    }
    if (!isSameVisit(loadedVisitIdRef.current, targetVisitId)) {
      setLoadError('load');
      return;
    }

    const snapshot = latestDraftRef.current;
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    setCompleting(true);
    setSaveError(null);
    retryCompletionRef.current = false;
    try {
      await persistDraft(targetVisitId, snapshot);
    } catch (error: unknown) {
      if (isSameVisit(loadedVisitIdRef.current, targetVisitId)) {
        setSaveError(getHttpStatus(error) === 409 ? 'conflict' : 'save');
        retryCompletionRef.current = true;
        logger.warn('[DentalVisitScreen] save before completion failed');
        notify.error(t('dental2.visit_protocol_save_failed'));
      }
      setCompleting(false);
      return;
    }

    if (isSameVisit(loadedVisitIdRef.current, targetVisitId)) {
      setSaveError(null);
      try {
        await onCompleteVisit?.(snapshot);
      } catch {
        logger.warn('[DentalVisitScreen] queue completion callback failed');
      }
    }
    setCompleting(false);
  }, [onCompleteVisit, persistDraft, t, visitId]);

  const handleBackToQueue = useCallback(async () => {
    if (!onBackToQueue) return;
    const targetVisitId = visitId;
    if (targetVisitId === null || targetVisitId === undefined || targetVisitId === '') {
      await onBackToQueue();
      return;
    }
    if (!isSameVisit(loadedVisitIdRef.current, targetVisitId)) {
      await onBackToQueue();
      return;
    }

    const snapshot = latestDraftRef.current;
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    setCompleting(true);
    setSaveError(null);
    try {
      await persistDraft(targetVisitId, snapshot);
      if (isSameVisit(loadedVisitIdRef.current, targetVisitId)) {
        await onBackToQueue();
      }
    } catch (error: unknown) {
      if (isSameVisit(loadedVisitIdRef.current, targetVisitId)) {
        setSaveError(getHttpStatus(error) === 409 ? 'conflict' : 'save');
        logger.warn('[DentalVisitScreen] save before queue navigation failed');
        notify.error(t('dental2.visit_protocol_save_failed'));
      }
    } finally {
      if (isSameVisit(loadedVisitIdRef.current, targetVisitId)) setCompleting(false);
    }
  }, [onBackToQueue, persistDraft, t, visitId]);

  const handleRetrySave = useCallback(async () => {
    if (retryCompletionRef.current) {
      await handleCompleteVisit();
      return;
    }

    const targetVisitId = visitId;
    if (targetVisitId === null || targetVisitId === undefined || targetVisitId === '') {
      setLoadError('missing_visit');
      return;
    }
    if (!isSameVisit(loadedVisitIdRef.current, targetVisitId)) {
      setLoadError('load');
      return;
    }

    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    setSaving(true);
    try {
      await persistDraft(targetVisitId, latestDraftRef.current);
      setSaveError(null);
    } catch (error: unknown) {
      if (isSameVisit(loadedVisitIdRef.current, targetVisitId)) {
        setSaveError(getHttpStatus(error) === 409 ? 'conflict' : 'save');
        logger.warn('[DentalVisitScreen] retry save failed');
        notify.error(t('dental2.visit_protocol_save_failed'));
      }
    } finally {
      if (isSameVisit(loadedVisitIdRef.current, targetVisitId)) setSaving(false);
    }
  }, [handleCompleteVisit, persistDraft, t, visitId]);

  // Tooth click → open ToothModal
  const handleToothClick = useCallback((toothNumber: string | number, toothData: Record<string, unknown> | null) => {
    setSelectedTooth({ number: toothNumber, data: toothData || {} });
    setToothModalOpen(true);
  }, []);

  const handleToothSave = useCallback((toothNumber: string | number, toothData: Record<string, unknown>) => {
    updateSpecialtyData('tooth_status', {
      ...(emrData.specialty_data?.tooth_status || {}),
      [toothNumber]: toothData,
    });
    setToothModalOpen(false);
    setSelectedTooth(null);
    notify.success(t('dental.dental_dvs_tooth_saved', { toothNumber }));
  }, [emrData.specialty_data, updateSpecialtyData, t]);

  // AI suggestion apply → writes to icd10_code field
  const handleAISuggestion = useCallback(() => {
    setShowAIDialog(true);
  }, []);

  const applyAISuggestion = useCallback((icd10Code: string) => {
    updateField('icd10_code', icd10Code);
    notify.success(t('dental.dental_dvs_icd10_added', { code: icd10Code }));
  }, [updateField, t]);

  const isEMRLoaded = isSameVisit(loadedVisitId, visitId);
  const isLoading = loading || parentLoading || (Boolean(visitId) && !isEMRLoaded && !loadError);
  const fieldsDisabled = completing || !isEMRLoaded;
  const toothStatus = emrData.specialty_data?.tooth_status || {};

  return (
    <div className="dental-flex-col dental-gap-24">
      <Card padding="default">
        <PatientHeader
          patient={patient as Record<string, unknown> | null}
          onCompleteVisit={handleCompleteVisit}
          onBackToQueue={onBackToQueue ? handleBackToQueue : undefined}
          backDisabled={completing || Boolean(parentLoading) || (loading && !loadError)}
          loading={saving || completing || parentLoading || !isEMRLoaded || Boolean(loadError)}
        />

        {loadError && (
          <Alert
            type="error"
            description={loadError === 'missing_visit' ? t('dental.protocol_needs_visit_id') : t('dental2.visit_map_load_failed')}
            action={(
              <Button variant="outline" onClick={() => { void loadEMR(); }}>
                {t('doctor.btn_retry')}
              </Button>
            )}
          />
        )}

        {saveError && (
          <Alert
            type="error"
            description={t('dental2.visit_protocol_save_failed')}
            action={(
              <Button variant="outline" onClick={() => { void handleRetrySave(); }} disabled={saving || completing}>
                {t('doctor.btn_retry')}
              </Button>
            )}
          />
        )}

        {loadError ? null : isLoading ? (
          <div style={{ padding: 20 }}>
            <Skeleton style={{ height: 60, marginBottom: 12 }} />
            <Skeleton style={{ height: 200, marginBottom: 12 }} />
            <Skeleton style={{ height: 80 }} />
          </div>
        ) : (
          <div style={{ padding: 20 }}>
            {/* Anamnesis — 1-2 строки, всегда виден */}
            <AnamnesisSection
              value={emrData.anamnesis_morbi || emrData.complaints || ''}
              onChange={(v: string) => updateField('anamnesis_morbi', v)}
              disabled={fieldsDisabled}
            />

            {/* Diagnosis + ICD-10 + AI button */}
            <DiagnosisSection
              diagnosis={emrData.diagnosis || ''}
              icd10={emrData.icd10_code || ''}
              onDiagnosisChange={(v) => updateField('diagnosis', v)}
              onIcd10Change={(v) => updateField('icd10_code', v)}
              onAISuggestion={handleAISuggestion}
              disabled={fieldsDisabled}
            />

            {/* Tooth chart — основная рабочая область */}
            <div style={{ marginBottom: 16 }}>
              <Label style={{ display: 'block', marginBottom: 6 }}>
                {t('dental.dental_dvs_chart_label')}
              </Label>
              <TeethChart
                initialData={toothStatus}
                onToothClick={handleToothClick}
                readOnly={fieldsDisabled}
              />
              <ToothSummary toothStatus={toothStatus} />
            </div>

            {/* Collapsible extras */}
            <CollapsibleExtras
              hygieneIndices={emrData.specialty_data?.hygiene_indices || {}}
              onHygieneChange={(field, value) => updateSpecialtyData('hygiene_indices', {
                ...(emrData.specialty_data?.hygiene_indices || {}),
                [field]: value,
              })}
              disabled={fieldsDisabled}
            />

            <VisitProtocolSections
              value={protocolRecord(emrData.specialty_data?.visit_protocol)}
              onUpdate={updateVisitProtocol}
              disabled={fieldsDisabled}
            />

            {/* Visit history — read-only */}
            <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--mac-border)' }}>
              <Typography variant="subtitle1" style={{ marginBottom: 12, fontWeight: 600 }}>
                {t('dental.dental_dvs_history_title')}
              </Typography>
              <VisitHistory history={history} loading={historyLoading} />
            </div>
          </div>
        )}
      </Card>

      {/* ToothModal */}
      {toothModalOpen && selectedTooth && (
        <ToothModal
          open={toothModalOpen}
          onClose={() => { setToothModalOpen(false); setSelectedTooth(null); }}
          toothNumber={selectedTooth.number}
          toothData={selectedTooth.data}
          onSave={(data: unknown) => handleToothSave(selectedTooth?.number, data as Record<string, unknown>)}
          visitId={visitId}
        />
      )}

      {/* AI Suggestion Dialog */}
      <AISuggestionDialog
        open={showAIDialog}
        onClose={() => setShowAIDialog(false)}
        onApply={applyAISuggestion}
        anamnesis={emrData.anamnesis_morbi || emrData.complaints || ''}
      />
    </div>
  );
};


export default DentalVisitScreen;
