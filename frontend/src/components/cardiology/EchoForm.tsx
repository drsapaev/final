
/**
 * Echo Form Component
 * Форма для ввода результатов ЭхоКГ
 * Phase 3: stale MASTER_TODO_LIST reference removed.
 */
import { useState, useEffect } from 'react';
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
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";

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

function deepMerge(base, incoming) {
  if (!incoming || typeof incoming !== 'object' || Array.isArray(incoming)) {
    return base;
  }

  const result = Array.isArray(base) ? [...base] : { ...base };
  for (const [key, value] of Object.entries(incoming)) {
    if (value && typeof value === 'object' && !Array.isArray(value) && base?.[key] && typeof base[key] === 'object') {
      result[key] = deepMerge(base[key], value);
    } else {
      result[key] = value;
    }
  }
  return result;
}

function getNestedValue(source, path) {
  if (!source || !path) return '';
  return String(path).split('.').reduce((acc, key) => acc?.[key], source) ?? '';
}

function setNestedValue(source, path, value) {
  const keys = String(path).split('.');
  const result = { ...source };
  let current = result;
  for (let i = 0; i < keys.length - 1; i += 1) {
    const key = keys[i];
    current[key] = current[key] && typeof current[key] === 'object' ? { ...current[key] } : {};
    current = current[key];
  }
  current[keys[keys.length - 1]] = value;
  return result;
}

async function loadExistingEmrDraft(visitId) {
  try {
    const response = await api.get(`/v2/emr/${visitId}`);
    return response.data || null;
  } catch (err) {
    if (err?.response?.status === 404) {
      return null;
    }
    throw err;
  }
}

function buildEchoEmrPayload(existingEmr, echoData) {
  const currentData = existingEmr?.data || {};
  return {
    data: {
      ...currentData,
      specialty: currentData.specialty || 'cardiology',
      specialty_data: {
        ...(currentData.specialty_data || {}),
        echo: echoData
      }
    },
    row_version: existingEmr?.row_version ?? 0,
    is_draft: true
  };
}

const EchoForm = ({ visitId, onSave, onDataUpdate, initialData = null }: EchoFormProps) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [echoData, setEchoData] = useState<EchoData>(DEFAULT_ECHO_DATA as EchoData);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [expandedSections, setExpandedSections] = useState({
    leftVentricle: true,
    rightVentricle: false,
    atria: false,
    valves: false,
    additional: false
  });

  useEffect(() => {
    if (initialData) {
      setEchoData(deepMerge(DEFAULT_ECHO_DATA, initialData));
    }
  }, [initialData]);

  const handleChange = (section: string, field: string, value: unknown) => {
    setEchoData((prev) => ({
      ...prev,
      [section]: field.includes('.')
        ? setNestedValue(prev[section] || {}, field, value)
        : {
          ...(prev[section] as Record<string, unknown> || {}),
          [field]: value
        }
    }));
  };

  const toggleSection = (section) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      setError('');

      if (!visitId) {
        if (onSave) {
          onSave(echoData);
          setSuccess(t('cardio.cardio_echo_saved_draft'));
          return;
        }
        throw new Error('visit_id is required to save Echo results');
      }

      const existingEmr = await loadExistingEmrDraft(visitId);
      const response = await api.post(`/v2/emr/${visitId}`, buildEchoEmrPayload(existingEmr, echoData));

      if (response.status === 200) {
        setSuccess(t('cardio.cardio_echo_saved_success'));
        if (onSave) {
          onSave(response.data?.data?.specialty_data?.echo || echoData);
        }
        onDataUpdate?.();
      }
    } catch (err) {
      setError(t('cardio.cardio_echo_save_error'));
      logger.error('Echo form save error:', err);
    } finally {
      setLoading(false);
    }
  };

  const renderSection = (title, section, fields, expanded) =>
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
              disabled={loading}>
              
              <Save style={{ width: 16, height: 16, marginRight: 8 }} />
              {t('cardio.cardio_echo_save_button')}
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
            onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setEchoData((prev) => ({ ...prev, conclusion: e.target.value }))}
            placeholder={t('cardio.cardio_echo_ph_conclusion')}
            rows={6} />
          
        </div>
      </CardContent>
    </Card>);

};


EchoForm.propTypes = {
  ...(EchoForm.propTypes || {}),
  initialData: PropTypes.any,
  onDataUpdate: PropTypes.func,
  onSave: PropTypes.any,
  patientId: PropTypes.any,
  visitId: PropTypes.any,
};

export default EchoForm;
