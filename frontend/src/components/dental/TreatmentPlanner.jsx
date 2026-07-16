import { useTranslation } from '../../i18n/useTranslation';
/**
 * Treatment Planner Component  
 * План лечения с этапами
 * Согласно MASTER_TODO_LIST строка 286
 */
import { Fragment, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Input,
  Select,
  Textarea,
} from '../ui/macos';
import {
  CalendarDays,
  ClipboardList,
  Clock,
  DollarSign,
  Hospital,
  Plus,
  Printer,
  Trash2,
} from 'lucide-react';
import { openPrintableWindow } from '../../utils/printWindow';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import notify from '../../services/notify';

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

function buildTreatmentPlanEmrPayload(existingEmr, treatmentPlan) {
  const data = clonePlainObject(existingEmr?.data);
  const specialtyData = clonePlainObject(data.specialty_data);

  return {
    data: {
      ...data,
      specialty: data.specialty || 'dentistry',
      specialty_data: {
        ...specialtyData,
        treatment_plan: clonePlainObject(treatmentPlan),
      },
      treatment_plan: clonePlainObject(treatmentPlan),
    },
    row_version: existingEmr?.row_version ?? 0,
    is_draft: true,
  };
}

const styles = {
  panel: {
    display: 'block',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 'var(--mac-spacing-3)',
    marginBottom: 'var(--mac-spacing-5)',
  },
  title: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--mac-spacing-2)',
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-xl)',
    fontWeight: 'var(--mac-font-weight-semibold)',
  },
  actions: {
    display: 'flex',
    gap: 'var(--mac-spacing-2)',
    flexWrap: 'wrap',
    justifyContent: 'flex-end',
  },
  fieldGrid: {
    display: 'grid',
    gap: '14px',
    marginBottom: 'var(--mac-spacing-5)',
  },
  twoColumnGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: '14px',
  },
  metrics: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
    gap: 'var(--mac-spacing-3)',
    padding: '14px',
    marginBottom: 'var(--mac-spacing-5)',
    border: '1px solid var(--mac-border)',
    borderRadius: 'var(--mac-radius-lg)',
    background: 'var(--mac-bg-secondary)',
  },
  metric: {
    textAlign: 'center',
  },
  metricValue: {
    display: 'block',
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-3xl)',
    fontWeight: 'var(--mac-font-weight-bold)',
    lineHeight: 1.1,
  },
  metricLabel: {
    display: 'block',
    marginTop: 'var(--mac-spacing-1)',
    color: 'var(--mac-text-secondary)',
    fontSize: 'var(--mac-font-size-xs)',
  },
  stageList: {
    display: 'grid',
    gap: '0',
    margin: 0,
    padding: 0,
    listStyle: 'none',
  },
  stageItem: {
    display: 'grid',
    gridTemplateColumns: '28px minmax(0, 1fr) auto',
    gap: '10px',
    alignItems: 'start',
    padding: '12px 0',
  },
  stageDivider: {
    borderTop: '1px solid var(--mac-border)',
  },
  stageIcon: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '28px',
    height: '28px',
    borderRadius: '50%',
    color: 'var(--mac-accent-blue)',
    background: 'var(--mac-accent-bg)',
  },
  stageName: {
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-base)',
    fontWeight: 'var(--mac-font-weight-semibold)',
  },
  stageDescription: {
    margin: '4px 0 0',
    color: 'var(--mac-text-secondary)',
    fontSize: 'var(--mac-font-size-sm)',
    lineHeight: 1.4,
  },
  stageMeta: {
    display: 'flex',
    gap: 'var(--mac-spacing-2)',
    flexWrap: 'wrap',
    marginTop: 'var(--mac-spacing-2)',
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
  saveRow: {
    display: 'flex',
    justifyContent: 'center',
    marginTop: 'var(--mac-spacing-5)',
  },
  dialogGrid: {
    display: 'grid',
    gap: '14px',
    marginTop: 'var(--mac-spacing-1)',
  },
  badgeIcon: {
    width: '13px',
    height: '13px',
    marginRight: 'var(--mac-spacing-1)',
  },
};

const priorityBadgeVariant = {
  high: 'danger',
  medium: 'warning',
  low: 'info',
};

const TreatmentPlanner = ({ visitId, onUpdate }) => {
  const { t } = useTranslation();
  const [treatmentPlan, setTreatmentPlan] = useState({
    name: '',
    stages: [],
    totalCost: 0,
    totalDuration: 0,
  });
  
  const [stageDialog, setStageDialog] = useState(false);
  const [stageForm, setStageForm] = useState({
    name: '',
    description: '',
    teeth: [],
    date: '',
    duration: 1,
    cost: 0,
    priority: 'medium',
  });

  const PRIORITIES = {
    high: { label: t('dental.dental_tp_priority_high'), color: 'error' },
    medium: { label: t('dental.dental_tp_priority_medium'), color: 'warning' },
    low: { label: t('dental.dental_tp_priority_low'), color: 'info' },
  };

  const handleSaveStage = () => {
    const stage = {
      ...stageForm,
      id: `stage_${Date.now()}`,
      status: 'planned',
    };
    
    setTreatmentPlan(prev => ({
      ...prev,
      stages: [...prev.stages, stage],
      totalCost: prev.totalCost + stage.cost,
      totalDuration: prev.totalDuration + stage.duration,
    }));
    
    setStageDialog(false);
    setStageForm({
      name: '',
      description: '',
      teeth: [],
      date: '',
      duration: 1,
      cost: 0,
      priority: 'medium',
    });
  };

  const handleDeleteStage = (stageId) => {
    setTreatmentPlan(prev => {
      const stage = prev.stages.find(s => s.id === stageId);
      return {
        ...prev,
        stages: prev.stages.filter(s => s.id !== stageId),
        totalCost: prev.totalCost - (stage?.cost || 0),
        totalDuration: prev.totalDuration - (stage?.duration || 0),
      };
    });
  };

  const savePlan = async () => {
    try {
      if (!visitId) {
        throw new Error('Treatment plan save requires visitId');
      }

      const existingEmr = await loadExistingEmrDraft(visitId);
      await api.post(
        `/v2/emr/${visitId}`,
        buildTreatmentPlanEmrPayload(existingEmr, treatmentPlan)
      );
      onUpdate && onUpdate(treatmentPlan);
    } catch (error) {
      logger.error('Ошибка сохранения плана:', error);
      notify.error(t('dental2.treatment_plan_save_failed'));
    }
  };

  const handlePrint = () => {
    const stagesHtml = treatmentPlan.stages.length
      ? treatmentPlan.stages
          .map(
            (stage, index) => `
              <tr>
                <td>${index + 1}</td>
                <td>${stage.name || ''}</td>
                <td>${stage.description || ''}</td>
                <td>${stage.date || t('dental.dental_tp_no_date')}</td>
                <td>${stage.duration || 0}</td>
                <td>${stage.cost || 0}</td>
                <td>${PRIORITIES[stage.priority]?.label || stage.priority || ''}</td>
              </tr>
            `
          )
          .join('')
      : `<tr><td colspan="7">${t('dental.dental_tp_print_no_stages')}</td></tr>`;

    openPrintableWindow({
      html: `
      <!doctype html>
      <html lang="ru">
        <head>
          <title>${t('dental.dental_tp_print_doc_title')}</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 24px; color: #111827; }
            h1 { margin: 0 0 12px; font-size: 24px; }
            h2 { margin: 24px 0 12px; font-size: 18px; }
            .meta { margin-bottom: 20px; color: #374151; }
            table { width: 100%; border-collapse: collapse; }
            th, td { border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; }
            th { background: #f3f4f6; }
            .summary { display: flex; gap: 24px; margin: 12px 0 20px; }
            .summary div { min-width: 120px; }
            .muted { color: #6b7280; }
          </style>
        </head>
        <body>
          <h1>${treatmentPlan.name || t('dental.dental_tp_print_default_name')}</h1>
          <div class="meta muted">${t('dental.dental_tp_print_doc_meta')}</div>
          <div class="summary">
            <div><strong>${t('dental.dental_tp_print_summary_stages')}</strong> ${treatmentPlan.stages.length}</div>
            <div><strong>${t('dental.dental_tp_print_summary_visits')}</strong> ${treatmentPlan.totalDuration}</div>
            <div><strong>${t('dental.dental_tp_print_summary_cost')}</strong> ${t('dental.dental_tp_print_summary_cost_value', { value: (treatmentPlan.totalCost / 1000).toFixed(0) })}</div>
          </div>
          <h2>${t('dental.dental_tp_print_stages_heading')}</h2>
          <div className="admin-table-wrapper">
<table>
            <thead>
              <tr>
                <th>#</th>
                <th>${t('dental.dental_tp_print_th_name')}</th>
                <th>${t('dental.dental_tp_print_th_description')}</th>
                <th>${t('dental.dental_tp_print_th_date')}</th>
                <th>${t('dental.dental_tp_print_th_visits')}</th>
                <th>${t('dental.dental_tp_print_th_cost')}</th>
                <th>${t('dental.dental_tp_print_th_priority')}</th>
              </tr>
            </thead>
            <tbody>${stagesHtml}</tbody>
          </table>
</div>
        </body>
      </html>
    `
    });
  };

  return (
    <div style={styles.panel}>
      <Card>
        <CardContent>
          <div style={styles.header}>
            <h2 style={styles.title}>
              <ClipboardList size={18} aria-hidden="true" />
              {t('dental.dental_tp_title')}
            </h2>

            <div style={styles.actions}>
              <Button type="button" size="small" onClick={() => setStageDialog(true)}>
                <Plus size={iconSize} aria-hidden="true" />
                {t('dental.dental_tp_add_stage')}
              </Button>
              <Button type="button" size="small" onClick={handlePrint}>
                <Printer size={iconSize} aria-hidden="true" />
                {t('dental.dental_tp_print')}
              </Button>
            </div>
          </div>

          <div style={styles.fieldGrid}>
            <Input
              label={t('dental.dental_tp_plan_name_label')}
              value={treatmentPlan.name}
              onChange={(e) => setTreatmentPlan({ ...treatmentPlan, name: e.target.value })}
              style={{ width: '100%', boxSizing: 'border-box' }}
            />
          </div>

          <div style={styles.metrics} aria-label={t('dental.dental_tp_aria_summary')}>
            <div style={styles.metric}>
              <span style={styles.metricValue}>{treatmentPlan.stages.length}</span>
              <span style={styles.metricLabel}>{t('dental.dental_tp_metric_stages')}</span>
            </div>
            <div style={styles.metric}>
              <span style={styles.metricValue}>{treatmentPlan.totalDuration}</span>
              <span style={styles.metricLabel}>{t('dental.dental_tp_metric_visits')}</span>
            </div>
            <div style={styles.metric}>
              <span style={styles.metricValue}>{(treatmentPlan.totalCost / 1000).toFixed(0)}k</span>
              <span style={styles.metricLabel}>{t('dental.dental_tp_metric_cost')}</span>
            </div>
          </div>

          {treatmentPlan.stages.length > 0 ? (
            <ul style={styles.stageList}>
              {treatmentPlan.stages.map((stage, index) => (
                <Fragment key={stage.id}>
                  <li style={{ ...styles.stageItem, ...(index > 0 ? styles.stageDivider : {}) }}>
                    <span style={styles.stageIcon} aria-hidden="true">
                      <Hospital size={16} />
                    </span>
                    <div>
                      <h3 style={styles.stageName}>{stage.name}</h3>
                      <p style={styles.stageDescription}>{stage.description}</p>
                      <div style={styles.stageMeta}>
                        <Badge size="small" variant="outline">
                          <CalendarDays style={styles.badgeIcon} aria-hidden="true" />
                          {stage.date || t('dental.dental_tp_no_date')}
                        </Badge>
                        <Badge size="small" variant="outline">
                          <Clock style={styles.badgeIcon} aria-hidden="true" />
                          {`${stage.duration} ${t('dental.dental_tp_visit_suffix')}`}
                        </Badge>
                        <Badge size="small" variant="outline">
                          <DollarSign style={styles.badgeIcon} aria-hidden="true" />
                          {`${(stage.cost / 1000).toFixed(0)}k`}
                        </Badge>
                        <Badge size="small" variant={priorityBadgeVariant[stage.priority] || 'default'}>
                          {PRIORITIES[stage.priority]?.label || stage.priority}
                        </Badge>
                      </div>
                    </div>
                    <button
                      type="button"
                      aria-label={t('dental.dental_tp_delete')}
                      title={t('dental.dental_tp_delete')}
                      style={styles.iconButton}
                      onClick={() => handleDeleteStage(stage.id)}
                    >
                      <Trash2 size={16} aria-hidden="true" />
                    </button>
                  </li>
                </Fragment>
              ))}
            </ul>
          ) : (
            <Alert severity="info">
              {t('dental.dental_tp_empty_plan')}
            </Alert>
          )}

          {treatmentPlan.stages.length > 0 && (
            <div style={styles.saveRow}>
              <Button type="button" variant="primary" size="large" onClick={savePlan}>
                {t('dental.dental_tp_save_plan')}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={stageDialog} onClose={() => setStageDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t('dental.dental_tp_dialog_title')}</DialogTitle>

        <DialogContent style={{ maxHeight: '70vh', overflow: 'auto' }}>
          <div style={styles.dialogGrid}>
            <Input
              label={t('dental.dental_tp_stage_name_label')}
              value={stageForm.name}
              onChange={(e) => setStageForm({ ...stageForm, name: e.target.value })}
              style={{ width: '100%', boxSizing: 'border-box' }}
            />

            <Textarea
              label={t('dental.dental_tp_description_label')}
              value={stageForm.description}
              onChange={(e) => setStageForm({ ...stageForm, description: e.target.value })}
              minRows={2}
              textareaStyle={{ width: '100%', boxSizing: 'border-box' }}
            />

            <div style={styles.twoColumnGrid}>
              <Input
                type="date"
                label={t('dental.dental_tp_date_label')}
                value={stageForm.date}
                onChange={(e) => setStageForm({ ...stageForm, date: e.target.value })}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />

              <Select
                label={t('dental.dental_tp_priority_label')}
                value={stageForm.priority}
                onChange={(value) => setStageForm({ ...stageForm, priority: value })}
                options={Object.entries(PRIORITIES).map(([key, priority]) => ({
                  value: key,
                  label: priority.label,
                }))}
              />

              <Input
                type="number"
                label={t('dental.dental_tp_duration_label')}
                value={stageForm.duration}
                onChange={(e) => setStageForm({ ...stageForm, duration: parseInt(e.target.value) || 1 })}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />

              <Input
                type="number"
                label={t('dental.dental_tp_cost_label')}
                value={stageForm.cost}
                onChange={(e) => setStageForm({ ...stageForm, cost: parseInt(e.target.value) || 0 })}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
            </div>
          </div>
        </DialogContent>

        <DialogActions>
          <Button type="button" onClick={() => setStageDialog(false)}>{t('dental.dental_tp_cancel')}</Button>
          <Button type="button" variant="primary" onClick={handleSaveStage} disabled={!stageForm.name}>
            {t('dental.dental_tp_add')}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
};


TreatmentPlanner.propTypes = {
  ...(TreatmentPlanner.propTypes || {}),
  onUpdate: PropTypes.any,
  visitId: PropTypes.any,
};

export default TreatmentPlanner;

