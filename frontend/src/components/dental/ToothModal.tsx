// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useTranslation } from '../../i18n/useTranslation';
/**
 * Tooth Modal Component
 * Модальное окно для работы с зубом
 * Согласно MASTER_TODO_LIST строка 285
 */
import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import {
  Alert,
  Badge,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Input,
  Select,
  Textarea,
} from '../ui/macos';
import {
  Activity,
  CheckCircle,
  History,
  Hospital,
  Plus,
  Trash2,
} from 'lucide-react';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import notify from '../../services/notify';
import {
  TOOTH_PROCEDURES,
  MATERIALS,
  getToothName as ssotGetToothName,
  computeToothTotalPrice,
  isProstheticProcedure,
} from './dentalConstants';

const iconSize = 15;

function clonePlainObject(value) {
  if (!value || typeof value !== 'object') {
    return {};
  }

  if (typeof structuredClone === 'function') {
    return structuredClone(value);
  }

  return JSON.parse(JSON.stringify(value));
}

async function loadExistingEmrDraft(visitId) {
  const response = await api.get(`/v2/emr/${visitId}`, {
    silent: true,
    validateStatus: (status) => status === 404 || (status >= 200 && status < 300),
  });

  return response.status === 404 ? null : response.data;
}

function buildToothEmrPayload(existingEmr, toothNumber, toothData) {
  const data = clonePlainObject(existingEmr?.data);
  const specialtyData = clonePlainObject(data.specialty_data);
  const toothStatus = clonePlainObject(specialtyData.tooth_status);

  toothStatus[toothNumber] = clonePlainObject(toothData);

  return {
    data: {
      ...data,
      specialty: data.specialty || 'dentistry',
      specialty_data: {
        ...specialtyData,
        tooth_status: toothStatus,
      },
      tooth_status: toothStatus,
    },
    row_version: existingEmr?.row_version ?? 0,
    is_draft: true,
  };
}

const styles = {
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '12px',
  },
  title: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: '17px',
    fontWeight: 600,
  },
  content: {
    display: 'grid',
    gap: '20px',
    maxHeight: '72vh',
    overflow: 'auto',
  },
  section: {
    display: 'grid',
    gap: '10px',
  },
  sectionTitle: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: '15px',
    fontWeight: 600,
  },
  buttonGrid: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
  },
  twoColumnGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: '14px',
  },
  list: {
    display: 'grid',
    gap: '8px',
    margin: 0,
    padding: 0,
    listStyle: 'none',
  },
  listItem: {
    display: 'grid',
    gridTemplateColumns: '28px minmax(0, 1fr) auto',
    gap: '10px',
    alignItems: 'center',
    padding: '8px 0',
    borderBottom: '1px solid var(--mac-border)',
  },
  listItemStatic: {
    display: 'grid',
    gridTemplateColumns: '28px minmax(0, 1fr)',
    gap: '10px',
    alignItems: 'start',
    padding: '8px 0',
    borderBottom: '1px solid var(--mac-border)',
  },
  listIcon: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '28px',
    height: '28px',
    borderRadius: '50%',
    color: 'var(--mac-accent-blue)',
    background: 'rgba(0, 122, 255, 0.08)',
  },
  itemTitle: {
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: '14px',
    fontWeight: 600,
  },
  itemMeta: {
    margin: '3px 0 0',
    color: 'var(--mac-text-secondary)',
    fontSize: '12px',
  },
  iconButton: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '32px',
    height: '32px',
    border: '1px solid var(--mac-border)',
    borderRadius: 'var(--mac-radius-md)',
    color: 'var(--mac-danger, #ff3b30)',
    background: 'var(--mac-card-bg)',
    cursor: 'pointer',
  },
  checkboxRow: {
    display: 'grid',
    gridTemplateColumns: 'auto minmax(0, 1fr)',
    gap: '10px',
    alignItems: 'center',
    color: 'var(--mac-text-primary)',
    fontSize: '13px',
  },
  divider: {
    height: '1px',
    background: 'var(--mac-border)',
  },
  totalTitle: {
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: '17px',
    fontWeight: 600,
  },
  totalCaption: {
    display: 'block',
    marginTop: '6px',
    color: 'var(--mac-text-secondary)',
    fontSize: '12px',
  },
};

// H6 fix: TOOTH_PROCEDURES and MATERIALS now imported from dentalConstants.js (SSOT).
const ToothModal = ({
  open,
  onClose,
  toothNumber,
  toothData = {},
  onSave,
  visitId
}) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [formData, setFormData] = useState({
    status: '',
    procedures: [],
    material: '',
    notes: '',
    price: 0,
    nextVisitDate: '',
    requiresFollowUp: false,
    // Phase 4A: prosthetic-specific fields. Persisted into EMR JSONB
    // alongside other tooth data; populated only when a prosthetic
    // procedure is in the procedures list.
    shade: '',
    fitQuality: '',
    warrantyPeriod: '',
    patientSatisfaction: '',
  });
  
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && toothData) {
      setFormData({
        status: toothData.status || '',
        procedures: toothData.procedures || [],
        material: toothData.material || '',
        notes: toothData.notes || '',
        price: toothData.price || 0,
        nextVisitDate: toothData.nextVisitDate || '',
        requiresFollowUp: toothData.requiresFollowUp || false,
        shade: toothData.shade || '',
        fitQuality: toothData.fitQuality || toothData.fit_quality || '',
        warrantyPeriod: toothData.warrantyPeriod || toothData.warranty_period || '',
        patientSatisfaction: toothData.patientSatisfaction || toothData.patient_satisfaction || '',
      });

      setHistory([]);
    }
  }, [open, toothData]);

  // Добавление процедуры
  const addProcedure = (procedureId) => {
    const procedure = TOOTH_PROCEDURES[procedureId];
    if (!procedure) return;
    
    const newProcedure = {
      ...procedure,
      id: `${procedure.id}_${Date.now()}`,
      date: new Date().toISOString(),
    };
    
    setFormData(prev => ({
      ...prev,
      procedures: [...prev.procedures, newProcedure],
      price: prev.price + procedure.price,
    }));
  };

  // Удаление процедуры
  const removeProcedure = (procedureId) => {
    setFormData(prev => {
      const procedure = prev.procedures.find(p => p.id === procedureId);
      return {
        ...prev,
        procedures: prev.procedures.filter(p => p.id !== procedureId),
        price: prev.price - (procedure?.price || 0),
      };
    });
  };

  // Расчет общей стоимости — H6 fix: delegates to SSOT helper.
  const calculateTotalPrice = () =>
    computeToothTotalPrice({ procedures: formData.procedures, materialId: formData.material });

  // Phase 4A: detect prosthetic mode — when true, show shade / fit_quality /
  // warranty_period / patient_satisfaction fields below the material select.
  const hasProstheticProcedure = formData.procedures.some(
    (proc) => isProstheticProcedure(proc.id) || proc.isProsthetic === true,
  );

  // Сохранение данных
  const handleSave = async () => {
    setLoading(true);
    
    try {
      const dataToSave = {
        ...formData,
        toothNumber,
        price: calculateTotalPrice(),
        updatedAt: new Date().toISOString(),
      };
      
      if (visitId) {
        const existingEmr = await loadExistingEmrDraft(visitId);
        await api.post(
          `/v2/emr/${visitId}`,
          buildToothEmrPayload(existingEmr, toothNumber, dataToSave)
        );
      }
      
      onSave && onSave(toothNumber, dataToSave);
      onClose();
      
    } catch (error) {
      logger.error('Ошибка сохранения данных зуба:', error);
      notify.error(t('dental2.tooth_save_failed'));
    } finally {
      setLoading(false);
    }
  };

  // H6 fix: getToothName now delegates to SSOT (dentalConstants.getToothName).
  const getToothName = (number) => ssotGetToothName(number);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <div style={styles.header}>
          <h2 style={styles.title}>
            <Hospital size={18} aria-hidden="true" />
            {t('dental.dental_tm_tooth_prefix')}{toothNumber} - {getToothName(toothNumber)}
          </h2>
          <Badge variant="primary" size="small">
            {`${Math.floor(toothNumber / 10)} ${t('dental.dental_tm_quadrant_suffix')}`}
          </Badge>
        </div>
      </DialogTitle>

      <DialogContent style={styles.content}>
        <section style={styles.section}>
          <h3 style={styles.sectionTitle}>{t('dental.dental_tm_procedures_title')}</h3>

          <div style={styles.buttonGrid}>
            {Object.entries(TOOTH_PROCEDURES).map(([key, procedure]) => (
              <Button
                key={key}
                type="button"
                size="small"
                variant="outline"
                onClick={() => addProcedure(key)}
              >
                <Plus size={iconSize} aria-hidden="true" />
                {procedure.name}
              </Button>
            ))}
          </div>

          {formData.procedures.length > 0 && (
            <ul style={styles.list}>
              {formData.procedures.map((procedure) => (
                <li key={procedure.id} style={styles.listItem}>
                  <span style={styles.listIcon} aria-hidden="true">
                    <Activity size={16} />
                  </span>
                  <div>
                    <p style={styles.itemTitle}>{procedure.name}</p>
                    <p style={styles.itemMeta}>{`${(procedure.price / 1000).toFixed(0)}k ${t('dental.dental_tm_currency_suffix')}`}</p>
                  </div>
                  <button
                    type="button"
                    aria-label={t('dental.dental_tm_delete')}
                    title={t('dental.dental_tm_delete')}
                    style={styles.iconButton}
                    onClick={() => removeProcedure(procedure.id)}
                  >
                    <Trash2 size={16} aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div style={styles.twoColumnGrid}>
          <Select
            label={t('dental.dental_tm_material_label')}
            value={formData.material}
            onChange={(value) => setFormData({ ...formData, material: value })}
            options={[
              { value: '', label: t('dental.dental_tm_no_material') },
              ...Object.entries(MATERIALS).map(([key, material]) => ({
                value: key,
                label: `${material.name} - ${(material.price / 1000).toFixed(0)}k ${t('dental.dental_tm_currency_suffix')}`,
              })),
            ]}
          />

          <Input
            type="date"
            label={t('dental.dental_tm_next_visit_label')}
            value={formData.nextVisitDate}
            onChange={(e) => setFormData({ ...formData, nextVisitDate: e.target.value })}
            style={{ width: '100%', boxSizing: 'border-box' }}
          />
        </div>

        {hasProstheticProcedure && (
          <section style={styles.section}>
            <div style={styles.divider} />
            <h3 style={styles.sectionTitle}>
              {t('dental.dental_tm_prosthetic_section_title')}
            </h3>
            <div style={styles.twoColumnGrid}>
              <Input
                type="text"
                label={t('dental.dental_tm_shade_label')}
                value={formData.shade}
                onChange={(e) => setFormData({ ...formData, shade: e.target.value })}
                placeholder={t('dental.dental_tm_shade_placeholder')}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
              <Select
                label={t('dental.dental_tm_fit_quality_label')}
                value={formData.fitQuality}
                onChange={(value) => setFormData({ ...formData, fitQuality: value })}
                options={[
                  { value: '', label: '—' },
                  { value: 'excellent', label: t('dental.dental_tm_fit_excellent') },
                  { value: 'good', label: t('dental.dental_tm_fit_good') },
                  { value: 'satisfactory', label: t('dental.dental_tm_fit_satisfactory') },
                  { value: 'poor', label: t('dental.dental_tm_fit_poor') },
                ]}
              />
              <Input
                type="number"
                label={t('dental.dental_tm_warranty_period_label')}
                value={formData.warrantyPeriod}
                onChange={(e) => setFormData({ ...formData, warrantyPeriod: e.target.value })}
                placeholder={t('dental.dental_tm_warranty_placeholder')}
                min="0"
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
              <Select
                label={t('dental.dental_tm_patient_satisfaction_label')}
                value={formData.patientSatisfaction}
                onChange={(value) => setFormData({ ...formData, patientSatisfaction: value })}
                options={[
                  { value: '', label: '—' },
                  { value: '5', label: t('dental.dental_tm_sat_5') },
                  { value: '4', label: t('dental.dental_tm_sat_4') },
                  { value: '3', label: t('dental.dental_tm_sat_3') },
                  { value: '2', label: t('dental.dental_tm_sat_2') },
                  { value: '1', label: t('dental.dental_tm_sat_1') },
                ]}
              />
            </div>
          </section>
        )}

        <Textarea
          label={t('dental.dental_tm_notes_label')}
          value={formData.notes}
          onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
          placeholder={t('dental.dental_tm_notes_placeholder')}
          minRows={3}
          textareaStyle={{ width: '100%', boxSizing: 'border-box' }}
        />

        <label style={styles.checkboxRow}>
          <input
            type="checkbox"
            aria-label={t('dental.dental_tm_follow_up_label')}
            checked={formData.requiresFollowUp}
            onChange={(e) => setFormData({ ...formData, requiresFollowUp: e.target.checked })}
          />
          <span>{t('dental.dental_tm_follow_up_label')}</span>
        </label>

        {history.length > 0 && (
          <section style={styles.section}>
            <div style={styles.divider} />
            <h3 style={styles.sectionTitle}>
              <History size={16} aria-hidden="true" />
              {t('dental.dental_tm_history_title')}
            </h3>

            <ul style={styles.list}>
              {history.map((record, index) => (
                <li key={index} style={styles.listItemStatic}>
                  <span style={styles.listIcon} aria-hidden="true">
                    <CheckCircle size={15} />
                  </span>
                  <div>
                    <p style={styles.itemTitle}>{record.procedure}</p>
                    <p style={styles.itemMeta}>
                      {new Date(record.date).toLocaleDateString()} - {record.doctor}
                    </p>
                    {record.notes && <p style={styles.itemMeta}>{record.notes}</p>}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        <Alert severity="info">
          <h3 style={styles.totalTitle}>
            {t('dental.dental_tm_total_cost_label')}: {(calculateTotalPrice() / 1000).toFixed(0)}k {t('dental.dental_tm_currency_suffix')}
          </h3>
          {formData.procedures.length > 0 && (
            <span style={styles.totalCaption}>
              {t('dental.dental_tm_includes_label')}: {formData.procedures.map(p => p.name).join(', ')}
              {formData.material && `, ${t('dental.dental_tm_material_prefix')}: ${MATERIALS[formData.material]?.name}`}
            </span>
          )}
        </Alert>
      </DialogContent>

      <DialogActions>
        <Button type="button" onClick={onClose}>
          {t('dental.dental_tm_cancel')}
        </Button>
        <Button
          type="button"
          variant="primary"
          onClick={handleSave}
          disabled={loading || formData.procedures.length === 0}
          loading={loading}
        >
          {t('dental.dental_tm_save')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};


ToothModal.propTypes = {
  ...(ToothModal.propTypes || {}),
  onClose: PropTypes.any,
  onSave: PropTypes.any,
  open: PropTypes.any,
  patientId: PropTypes.any,
  toothData: PropTypes.any,
  toothNumber: PropTypes.any,
  visitId: PropTypes.any,
};

export default ToothModal;

