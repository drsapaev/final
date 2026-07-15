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
import { useTranslation } from '../../i18n/adapter';

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
  const { t } = useTranslation();
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

const EchoForm = ({ visitId, onSave, onDataUpdate, initialData = null }) => {
  const [echoData, setEchoData] = useState(DEFAULT_ECHO_DATA);

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

  const handleChange = (section, field, value) => {
    setEchoData((prev) => ({
      ...prev,
      [section]: field.includes('.')
        ? setNestedValue(prev[section] || {}, field, value)
        : {
          ...(prev[section] || {}),
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
          setSuccess('Результаты ЭхоКГ сохранены в черновике приема');
          return;
        }
        throw new Error('visit_id is required to save Echo results');
      }

      const existingEmr = await loadExistingEmrDraft(visitId);
      const response = await api.post(`/v2/emr/${visitId}`, buildEchoEmrPayload(existingEmr, echoData));

      if (response.status === 200) {
        setSuccess('Результаты ЭхоКГ сохранены успешно');
        if (onSave) {
          onSave(response.data?.data?.specialty_data?.echo || echoData);
        }
        onDataUpdate?.(response.data);
      }
    } catch (err) {
      setError('Ошибка при сохранении результатов ЭхоКГ');
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
      onKeyDown={(event) => {
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
            onChange={(e) => handleChange(section, field.key, e.target.value)}
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
            Результаты ЭхоКГ
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
              Сохранить
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
          'Левый желудочек',
          'leftVentricle',
          [
          { key: 'edd', label: 'КДР', placeholder: 'Норма: 35-55 мм' },
          { key: 'esd', label: 'КСР', placeholder: 'Норма: 20-35 мм' },
          { key: 'ef', label: 'ФВ', placeholder: 'Норма: 55-75%' },
          { key: 'fs', label: 'ФС', placeholder: 'Норма: 28-45%' },
          { key: 'ivs', label: 'МЖП', placeholder: 'Норма: 6-11 мм' },
          { key: 'pw', label: 'ЗС', placeholder: 'Норма: 6-11 мм' }],

          expandedSections.leftVentricle
        )}

        {/* Правый желудочек */}
        {renderSection(
          'Правый желудочек',
          'rightVentricle',
          [
          { key: 'rvdd', label: 'КДР ПЖ', placeholder: 'Норма: 19-28 мм' },
          { key: 'rvot', label: 'ВТ ПЖ', placeholder: 'Норма: 19-28 мм' }],

          expandedSections.rightVentricle
        )}

        {/* Предсердия */}
        {renderSection(
          'Предсердия',
          'atria',
          [
          { key: 'la', label: 'ЛП', placeholder: 'Норма: 19-40 мм' },
          { key: 'ra', label: 'ПП', placeholder: 'Норма: 19-40 мм' }],

          expandedSections.atria
        )}

        {/* Клапаны */}
        {renderSection(
          'Клапаны',
          'valves',
          [
          { key: 'mitral.e', label: 'Митральный клапан E', placeholder: 'Норма: 0.6-1.3 м/с' },
          { key: 'mitral.a', label: 'Митральный клапан A', placeholder: 'Норма: 0.4-0.8 м/с' },
          { key: 'aortic.peak_velocity', label: 'Аортальный клапан', placeholder: 'Норма: 1.0-1.7 м/с' },
          { key: 'tricuspid.e', label: 'Трехстворчатый клапан E', placeholder: 'Норма: 0.3-0.7 м/с' }],

          expandedSections.valves
        )}

        {/* Дополнительные параметры */}
        {renderSection(
          'Дополнительные параметры',
          'additional',
          [
          { key: 'pericardium', label: 'Перикард', placeholder: 'Описание состояния перикарда' },
          { key: 'aorta', label: 'Аорта', placeholder: 'Описание состояния аорты' }],

          expandedSections.additional
        )}

        {/* Комментарии */}
        <div style={{ marginTop: 24 }}>
          <Typography variant="subtitle1" style={{ marginBottom: 8 }}>
            Комментарии
          </Typography>
          <Textarea
            value={echoData.additional.comments}
            onChange={(e) => handleChange('additional', 'comments', e.target.value)}
            placeholder="Дополнительные замечания и наблюдения..."
            rows={4} />
          
        </div>

        {/* Заключение */}
        <div style={{ marginTop: 24 }}>
          <Typography variant="subtitle1" style={{ marginBottom: 8 }}>
            Заключение
          </Typography>
          <Textarea
            value={echoData.conclusion}
            onChange={(e) => setEchoData((prev) => ({ ...prev, conclusion: e.target.value }))}
            placeholder="Заключение по результатам ЭхоКГ..."
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
