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
  AlertTriangle,
  Hospital,
  Plus,
  Trash2,
} from 'lucide-react';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import notify from '../../services/notify';
import {
  TOOTH_PROCEDURES,
  MATERIALS,
  TOOTH_STATUS,
  TOOTH_STATUS_LABELS,
  getToothName as ssotGetToothName,
  computeToothTotalPrice,
  isProstheticProcedure,
} from './dentalConstants';
import { safeJsonParse } from '../../utils/safeJsonParse';

const iconSize = 15;

// DENTMODAL-FE-004 (audit 3892): wall-clock milliseconds are not a unique
// identity — same-millisecond procedure additions used to share one React
// key, and deleting one silently removed both. A module-local monotonic
// counter guarantees collision resistance even under a frozen clock.
let procedureIdSequence = 0;

interface Procedure {
  id: string;
  name: string;
  price: number;
  isProsthetic?: boolean;
  date?: string;
  [key: string]: unknown;
}

interface ToothFormData {
  status: string;
  procedures: Procedure[];
  material: string;
  notes: string;
  price: number;
  nextVisitDate: string;
  requiresFollowUp: boolean;
  shade: string;
  fitQuality: string;
  warrantyPeriod: string;
  patientSatisfaction: string;
}

function clonePlainObject(value: unknown) {
  if (!value || typeof value !== 'object') {
    return {};
  }

  if (typeof structuredClone === 'function') {
    return structuredClone(value);
  }

  return safeJsonParse(JSON.stringify(value));
}

async function loadExistingEmrDraft(visitId: string | number) {
  const response = await api.get(`/v2/emr/${visitId}`, {
    silent: true,
    validateStatus: (status: number) => status === 404 || (status >= 200 && status < 300),
  } as Record<string, unknown>) as unknown as { data?: Record<string, unknown> };

  return (response as { status?: number }).status === 404 ? null : response.data;
}

function buildToothEmrPayload(existingEmr: { data?: unknown; row_version?: number } | null, toothNumber: string | number, toothData: unknown) {
  const data = clonePlainObject(existingEmr?.data) as Record<string, unknown>;
  const specialtyData = clonePlainObject(data.specialty_data) as Record<string, unknown>;
  const toothStatus = clonePlainObject(specialtyData.tooth_status) as Record<string, unknown>;

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

const styles: Record<string, CSSProperties> = {
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
  toothData = {} as Record<string, unknown>,
  onSave,
  visitId,
  suggestedStatus,
  // RETRO-3966-01 (post-merge review PR 3968): explicit inspection-only mode.
  // A locked/signed (or otherwise non-editable) visit opens this modal for
  // clinical inspection ONLY: no editable control may receive input and no
  // save path may fire — the modal must never offer or attempt an EMR write
  // while the declared UI contract is read-only.
  readOnly = false,
}: { toothData?: Record<string, unknown>; onClose?: () => void; onSave?: (data: unknown, rowVersion?: number) => void; toothNumber?: string | number; visitId?: string | number; suggestedStatus?: string; open?: boolean; readOnly?: boolean; [k: string]: unknown }) => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  const [formData, setFormData] = useState<ToothFormData>({
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

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // DENTMODAL-FE-002 (audit 3892): re-hydrate the clinical form whenever the
    // bound visit changes while the modal stays open, so local edits made for
    // the previous patient's tooth are never kept against the new visit.
    if (open && toothData) {
      const td = toothData as Record<string, unknown>;
      setFormData({
        // DENTVISIT-FE-003 (audit 3892): the tooth's own persisted status is
        // authoritative; the chart palette's suggested status only seeds a
        // tooth that has no status yet. The clinician confirms it here.
        status: String(td.status ?? suggestedStatus ?? ''),
        procedures: (td.procedures as Procedure[]) || [],
        material: String(td.material ?? ''),
        notes: String(td.notes ?? ''),
        price: Number(td.price ?? 0),
        nextVisitDate: String(td.nextVisitDate ?? ''),
        requiresFollowUp: Boolean(td.requiresFollowUp ?? false),
        shade: String(td.shade ?? ''),
        fitQuality: String(td.fitQuality ?? td.fit_quality ?? ''),
        warrantyPeriod: String(td.warrantyPeriod ?? td.warranty_period ?? ''),
        patientSatisfaction: String(td.patientSatisfaction ?? td.patient_satisfaction ?? ''),
      });
    }
  }, [open, toothData, visitId, suggestedStatus]);

  // Добавление процедуры
  const addProcedure = (procedureId: string) => {
    const procedure = (TOOTH_PROCEDURES as Record<string, typeof TOOTH_PROCEDURES[keyof typeof TOOTH_PROCEDURES]>)[procedureId];
    if (!procedure) return;

    const newProcedure = {
      ...procedure,
      id: `${procedure.id}_${Date.now()}_${++procedureIdSequence}`,
      date: new Date().toISOString(),
    };

    setFormData(prev => ({
      ...prev,
      procedures: [...prev.procedures, newProcedure],
      price: prev.price + procedure.price,
    }));
  };

  // Удаление процедуры
  const removeProcedure = (procedureId: string) => {
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

  // DENTMODAL-FE-003 (audit 3892): Save must be available for ANY clinically
  // meaningful tooth record — notes, material, follow-up, next-visit date or
  // status are all persistable without a procedure. Only a truly empty,
  // no-op form stays disabled.
  const hasMeaningfulToothRecord = Boolean(
    formData.status ||
    formData.procedures.length > 0 ||
    formData.material ||
    formData.notes ||
    formData.nextVisitDate ||
    formData.requiresFollowUp ||
    formData.shade ||
    formData.fitQuality ||
    formData.warrantyPeriod ||
    formData.patientSatisfaction
  );

  // DENTDIALOG-FE-001 (audit 3892): without a canonical visit the modal has
  // no EMR destination — it must fail closed instead of pretending that a
  // local-state change was a save.
  const missingVisit = visitId === null || visitId === undefined || visitId === '';

  // Сохранение данных
  const handleSave = async () => {
    // RETRO-3966-01: defense in depth — even a programmatic/keyboard-triggered
    // save can never reach the EMR endpoint in inspection-only mode.
    if (readOnly) {
      logger.warn('[ToothModal] save blocked: inspection-only mode', { toothNumber: String(toothNumber) });
      return;
    }
    if (missingVisit) {
      notify.error(t('dental2.tooth_save_requires_visit'));
      return;
    }

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
        const response = await api.post(
          `/v2/emr/${visitId}`,
          buildToothEmrPayload(existingEmr as { data?: unknown; row_version?: number } | null, toothNumber ?? '', dataToSave)
        ) as { data?: { row_version?: unknown } };
        // DENTMODAL-FE-001 (audit 3892): this POST advances the server's
        // row_version; hand it back to the parent so its next autosave does
        // not reuse the stale optimistic-lock version.
        const savedRowVersion = response?.data?.row_version;
        if (typeof onSave === 'function') {
          onSave(dataToSave as Record<string, unknown>, typeof savedRowVersion === 'number' ? savedRowVersion : undefined);
        }
      }

      if (typeof onClose === 'function') onClose();

    } catch (error) {
      logger.error('Ошибка сохранения данных зуба:', error);
      notify.error(t('dental2.tooth_save_failed'));
    } finally {
      setLoading(false);
    }
  };

  // H6 fix: getToothName now delegates to SSOT (dentalConstants.getToothName).
  const getToothName = (number: string | number) => ssotGetToothName(number);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <div style={styles.header}>
          <h2 style={styles.title}>
            <Hospital size={18} aria-hidden="true" />
            {t('dental.dental_tm_tooth_prefix')}{toothNumber} - {getToothName(toothNumber ?? '')}
          </h2>
          <Badge variant="primary" size="small">
            {`${Math.floor(Number(toothNumber) / 10)} ${t('dental.dental_tm_quadrant_suffix')}`}
          </Badge>
        </div>
      </DialogTitle>
      <DialogContent style={styles.content}>
        {readOnly && (
          // RETRO-3966-01: honest inspection-only state — the modal is opened
          // from a locked/signed record; it shows the tooth's current clinical
          // data and offers no editing affordance at all.
          <Alert severity="info">
            <span className="dental-flex dental-gap-8">
              <AlertTriangle size={16} aria-hidden="true" />
              {t('dental.dental_tm_inspection_only')}
            </span>
          </Alert>
        )}

        {missingVisit && (
          // DENTDIALOG-FE-001 (audit 3892): honest failure state — a tooth
          // record cannot be saved without a canonical visit to write to.
          <Alert severity="warning">
            <span className="dental-flex dental-gap-8">
              <AlertTriangle size={16} aria-hidden="true" />
              {t('dental2.tooth_save_requires_visit')}
            </span>
          </Alert>
        )}

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
                disabled={readOnly}
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
                    disabled={readOnly}
                  >
                    <Trash2 size={16} aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div style={styles.twoColumnGrid}>
          {/* DENTVISIT-FE-003 (audit 3892): the tooth's clinical status is
              confirmed HERE — seeded from the chart palette's suggestion for
              a statusless tooth — instead of being painted onto the chart
              before this modal is accepted. */}
          <Select
            label={t('dental.dental_tm_status_label')}
            value={formData.status}
            onValueChange={(value) => setFormData({ ...formData, status: String(value) })}
            disabled={readOnly}
            options={[
              { value: '', label: '—' },
              ...Object.entries(TOOTH_STATUS).map(([, status]) => ({
                value: status,
                label: TOOTH_STATUS_LABELS[status as keyof typeof TOOTH_STATUS_LABELS],
              })),
            ]}
          />

          <Select
            label={t('dental.dental_tm_material_label')}
            value={formData.material}
            onValueChange={(value) => setFormData({ ...formData, material: String(value) })}
            disabled={readOnly}
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
            disabled={readOnly}
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
                disabled={readOnly}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
              <Select
                label={t('dental.dental_tm_fit_quality_label')}
                value={formData.fitQuality}
                onValueChange={(value) => setFormData({ ...formData, fitQuality: String(value) })}
                disabled={readOnly}
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
                disabled={readOnly}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
              <Select
                label={t('dental.dental_tm_patient_satisfaction_label')}
                value={formData.patientSatisfaction}
                onValueChange={(value) => setFormData({ ...formData, patientSatisfaction: String(value) })}
                disabled={readOnly}
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
          disabled={readOnly}
          textareaStyle={{ width: '100%', boxSizing: 'border-box' }}
        />

        <label style={styles.checkboxRow}>
          <input
            type="checkbox"
            aria-label={t('dental.dental_tm_follow_up_label')}
            checked={formData.requiresFollowUp}
            onChange={(e) => setFormData({ ...formData, requiresFollowUp: e.target.checked })}
            disabled={readOnly}
          />
          <span>{t('dental.dental_tm_follow_up_label')}</span>
        </label>

        <Alert severity="info">
          <h3 style={styles.totalTitle}>
            {t('dental.dental_tm_total_cost_label')}: {(calculateTotalPrice() / 1000).toFixed(0)}k {t('dental.dental_tm_currency_suffix')}
          </h3>
          {formData.procedures.length > 0 && (
            <span style={styles.totalCaption}>
              {t('dental.dental_tm_includes_label')}: {formData.procedures.map(p => p.name).join(', ')}
              {formData.material && `, ${t('dental.dental_tm_material_prefix')}: ${(MATERIALS as Record<string, { id: string; name: string; price: number }>)[formData.material]?.name}`}
            </span>
          )}
        </Alert>
      </DialogContent>

      <DialogActions>
        <Button type="button" onClick={onClose}>
          {t('dental.dental_tm_cancel')}
        </Button>
        {!readOnly && (
          <Button
            type="button"
            variant="primary"
            onClick={handleSave}
            disabled={loading || missingVisit || !hasMeaningfulToothRecord}
            loading={loading}
          >
            {t('dental.dental_tm_save')}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};


// audit/strict: removed self-referencing propTypes spread

export default ToothModal;

