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
    fontWeight: 600,
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
    fontWeight: 700,
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
    background: 'rgba(0, 122, 255, 0.08)',
  },
  stageName: {
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-base)',
    fontWeight: 600,
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

const COPY = {
  title: 'План лечения',
  addStageAction: 'Добавить этап',
  printAction: 'Печать',
  planNameLabel: 'Название плана',
  metricStages: 'Этапов',
  metricVisits: 'Визитов',
  metricCost: 'Стоимость (сум)',
  noDate: 'Не назначено',
  visitSuffix: 'визит',
  emptyPlan: 'План лечения пуст. Добавьте этапы лечения.',
  savePlan: 'Сохранить план',
  dialogTitle: 'Добавить этап лечения',
  stageNameLabel: 'Название этапа',
  descriptionLabel: 'Описание',
  dateLabel: 'Дата',
  priorityLabel: 'Приоритет',
  durationLabel: 'Визитов',
  costLabel: 'Стоимость (сум)',
  cancelAction: 'Отмена',
  addDialogAction: 'Добавить',
  deleteAction: 'Удалить',
};
const TreatmentPlanner = ({ visitId, onUpdate }) => {
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
    high: { label: 'Высокий', color: 'error' },
    medium: { label: 'Средний', color: 'warning' },
    low: { label: 'Низкий', color: 'info' },
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
                <td>${stage.date || 'Не назначено'}</td>
                <td>${stage.duration || 0}</td>
                <td>${stage.cost || 0}</td>
                <td>${PRIORITIES[stage.priority]?.label || stage.priority || ''}</td>
              </tr>
            `
          )
          .join('')
      : '<tr><td colspan="7">Этапы лечения не добавлены</td></tr>';

    openPrintableWindow({
      html: `
      <!doctype html>
      <html lang="ru">
        <head>
          <title>План лечения</title>
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
          <h1>${treatmentPlan.name || 'План лечения'}</h1>
          <div class="meta muted">План лечения для печати из стоматологической панели</div>
          <div class="summary">
            <div><strong>Этапов:</strong> ${treatmentPlan.stages.length}</div>
            <div><strong>Визитов:</strong> ${treatmentPlan.totalDuration}</div>
            <div><strong>Стоимость:</strong> ${(treatmentPlan.totalCost / 1000).toFixed(0)}k сум</div>
          </div>
          <h2>Этапы</h2>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Название</th>
                <th>Описание</th>
                <th>Дата</th>
                <th>Визиты</th>
                <th>Стоимость</th>
                <th>Приоритет</th>
              </tr>
            </thead>
            <tbody>${stagesHtml}</tbody>
          </table>
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
              {COPY.title}
            </h2>

            <div style={styles.actions}>
              <Button type="button" size="small" onClick={() => setStageDialog(true)}>
                <Plus size={iconSize} aria-hidden="true" />
                {COPY.addStageAction}
              </Button>
              <Button type="button" size="small" onClick={handlePrint}>
                <Printer size={iconSize} aria-hidden="true" />
                {COPY.printAction}
              </Button>
            </div>
          </div>

          <div style={styles.fieldGrid}>
            <Input
              label={COPY.planNameLabel}
              value={treatmentPlan.name}
              onChange={(e) => setTreatmentPlan({ ...treatmentPlan, name: e.target.value })}
              style={{ width: '100%', boxSizing: 'border-box' }}
            />
          </div>

          <div style={styles.metrics} aria-label="Сводка плана лечения">
            <div style={styles.metric}>
              <span style={styles.metricValue}>{treatmentPlan.stages.length}</span>
              <span style={styles.metricLabel}>{COPY.metricStages}</span>
            </div>
            <div style={styles.metric}>
              <span style={styles.metricValue}>{treatmentPlan.totalDuration}</span>
              <span style={styles.metricLabel}>{COPY.metricVisits}</span>
            </div>
            <div style={styles.metric}>
              <span style={styles.metricValue}>{(treatmentPlan.totalCost / 1000).toFixed(0)}k</span>
              <span style={styles.metricLabel}>{COPY.metricCost}</span>
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
                          {stage.date || COPY.noDate}
                        </Badge>
                        <Badge size="small" variant="outline">
                          <Clock style={styles.badgeIcon} aria-hidden="true" />
                          {`${stage.duration} ${COPY.visitSuffix}`}
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
                      aria-label={COPY.deleteAction}
                      title={COPY.deleteAction}
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
              {COPY.emptyPlan}
            </Alert>
          )}

          {treatmentPlan.stages.length > 0 && (
            <div style={styles.saveRow}>
              <Button type="button" variant="primary" size="large" onClick={savePlan}>
                {COPY.savePlan}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={stageDialog} onClose={() => setStageDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{COPY.dialogTitle}</DialogTitle>

        <DialogContent style={{ maxHeight: '70vh', overflow: 'auto' }}>
          <div style={styles.dialogGrid}>
            <Input
              label={COPY.stageNameLabel}
              value={stageForm.name}
              onChange={(e) => setStageForm({ ...stageForm, name: e.target.value })}
              style={{ width: '100%', boxSizing: 'border-box' }}
            />

            <Textarea
              label={COPY.descriptionLabel}
              value={stageForm.description}
              onChange={(e) => setStageForm({ ...stageForm, description: e.target.value })}
              minRows={2}
              textareaStyle={{ width: '100%', boxSizing: 'border-box' }}
            />

            <div style={styles.twoColumnGrid}>
              <Input
                type="date"
                label={COPY.dateLabel}
                value={stageForm.date}
                onChange={(e) => setStageForm({ ...stageForm, date: e.target.value })}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />

              <Select
                label={COPY.priorityLabel}
                value={stageForm.priority}
                onChange={(value) => setStageForm({ ...stageForm, priority: value })}
                options={Object.entries(PRIORITIES).map(([key, priority]) => ({
                  value: key,
                  label: priority.label,
                }))}
              />

              <Input
                type="number"
                label={COPY.durationLabel}
                value={stageForm.duration}
                onChange={(e) => setStageForm({ ...stageForm, duration: parseInt(e.target.value) || 1 })}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />

              <Input
                type="number"
                label={COPY.costLabel}
                value={stageForm.cost}
                onChange={(e) => setStageForm({ ...stageForm, cost: parseInt(e.target.value) || 0 })}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
            </div>
          </div>
        </DialogContent>

        <DialogActions>
          <Button type="button" onClick={() => setStageDialog(false)}>{COPY.cancelAction}</Button>
          <Button type="button" variant="primary" onClick={handleSaveStage} disabled={!stageForm.name}>
            {COPY.addDialogAction}
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

