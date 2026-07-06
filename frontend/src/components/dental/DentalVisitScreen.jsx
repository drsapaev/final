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

import { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  Button, Card, Badge, Input, Textarea, Label,
  Dialog, DialogTitle, DialogContent, DialogActions,
  Typography, Box, Alert, Skeleton,
} from '../ui/macos';
import {
  Stethoscope, CheckCircle, ChevronDown, ChevronUp,
  Brain,
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
  },
  recommendations: '',
  notes: '',
};

const loadExistingEMR = async (visitId) => {
  if (!visitId) return null;
  try {
    const response = await apiClient.get(`/v2/emr/${visitId}`, {
      silent: true,
      validateStatus: (status) => status === 404 || (status >= 200 && status < 300),
    });
    if (response.status === 404) return null;
    return response.data;
  } catch (error) {
    logger.warn('[DentalVisitScreen] Failed to load EMR', { visitId, error: error?.message });
    return null;
  }
};

const saveEMR = async (visitId, data, rowVersion, isDraft = true) => {
  const response = await apiClient.post(`/v2/emr/${visitId}`, {
    data,
    row_version: rowVersion ?? 0,
    is_draft: isDraft,
  });
  return response.data;
};

// =============================================================================
// Sub-components
// =============================================================================

const PatientHeader = ({ patient, onCompleteVisit, loading }) => {
  const patientName =
    patient?.patient_name ||
    patient?.name ||
    `№${patient?.number || '?'}`;
  const patientInfo = patient?.patient?.phone || patient?.phone || '';

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
            Приём: {patientName}
          </Typography>
          {patientInfo && (
            <Typography variant="body2" color="textSecondary" style={{ margin: 0 }}>
              {patientInfo}
            </Typography>
          )}
        </div>
      </div>
      <Button
        variant="primary"
        onClick={onCompleteVisit}
        disabled={loading}
        aria-label="Завершить приём и вызвать следующего пациента">
        <CheckCircle size={16} style={{ marginRight: 6 }} aria-hidden="true" />
        {loading ? 'Сохранение...' : 'Завершить визит'}
      </Button>
    </div>
  );
};

PatientHeader.propTypes = {
  patient: PropTypes.object.isRequired,
  onCompleteVisit: PropTypes.func.isRequired,
  loading: PropTypes.bool,
};

const AnamnesisSection = ({ value, onChange, disabled }) => (
  <div style={{ marginBottom: 16 }}>
    <Label htmlFor="dental-anamnesis" style={{ display: 'block', marginBottom: 6 }}>
      Жалобы и анамнез
    </Label>
    <Textarea
      id="dental-anamnesis"
      aria-label="Жалобы и анамнез пациента"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Напр.: Боль в зубе 16 при накусывании, 3 дня. Ранее — лечение кариеса."
      minRows={2}
      disabled={disabled}
      style={{ width: '100%', boxSizing: 'border-box' }}
    />
    <Typography variant="caption" color="textSecondary" style={{ marginTop: 4, display: 'block' }}>
      1-2 строки достаточно. Детальный анамнез — в EMRContainerV2 (вкладка «Протоколы визитов»).
    </Typography>
  </div>
);

AnamnesisSection.propTypes = {
  value: PropTypes.string,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};

const ToothSummary = ({ toothStatus }) => {
  const teeth = Object.entries(toothStatus || {});
  if (teeth.length === 0) {
    return (
      <Typography variant="body2" color="textSecondary" style={{ fontStyle: 'italic' }}>
        Зубы не отмечены. Кликните на зуб в схеме выше.
      </Typography>
    );
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
      {teeth.map(([toothNum, data]) => {
        const status = data?.status || 'healthy';
        const label = TOOTH_STATUS_LABELS[status] || status;
        const color = TOOTH_STATUS_COLORS[status] || 'var(--mac-text-tertiary)';
        const procedures = Array.isArray(data?.procedures) ? data.procedures : [];
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
            title={`Зуб ${toothNum} — ${getToothName(toothNum)}: ${label}${procedures.length > 0 ? ` (${procedures.map(p => p.name).join(', ')})` : ''}`}>
            {toothNum}: {label}
            {procedures.length > 0 && ` · ${procedures.length}℅`}
          </Badge>
        );
      })}
    </div>
  );
};

ToothSummary.propTypes = {
  toothStatus: PropTypes.object,
};

const DiagnosisSection = ({ diagnosis, icd10, onDiagnosisChange, onIcd10Change, onAISuggestion, disabled }) => (
  <div style={{ display: 'grid', gridTemplateColumns: '1fr 200px', gap: 12, marginBottom: 16 }}>
    <div>
      <Label htmlFor="dental-diagnosis" style={{ display: 'block', marginBottom: 6 }}>
        Диагноз
      </Label>
      <Input
        id="dental-diagnosis"
        aria-label="Диагноз"
        value={diagnosis}
        onChange={(e) => onDiagnosisChange(e.target.value)}
        placeholder="Напр.: Кариес дентина зуба 16"
        disabled={disabled}
        style={{ width: '100%', boxSizing: 'border-box' }}
      />
    </div>
    <div>
      <Label htmlFor="dental-icd10" style={{ display: 'block', marginBottom: 6 }}>
        МКБ-10
      </Label>
      <Input
        id="dental-icd10"
        aria-label="Код МКБ-10"
        value={icd10}
        onChange={(e) => onIcd10Change(e.target.value)}
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
        aria-label="AI-подбор кода МКБ-10 по жалобе">
        <Brain size={14} style={{ marginRight: 6 }} aria-hidden="true" />
        AI: подобрать МКБ-10
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

DiagnosisSection.propTypes = {
  diagnosis: PropTypes.string,
  icd10: PropTypes.string,
  onDiagnosisChange: PropTypes.func.isRequired,
  onIcd10Change: PropTypes.func.isRequired,
  onAISuggestion: PropTypes.func,
  disabled: PropTypes.bool,
};

const CollapsibleExtras = ({ hygieneIndices, onHygieneChange, disabled }) => {
  const [open, setOpen] = useState(false);

  return (
    <div style={{ marginBottom: 16, border: '1px solid var(--mac-border)', borderRadius: 8 }}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label="Развернуть дополнительные поля: гигиена, пародонт, прикус, рентген"
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
        <span>Дополнительно (Гигиена / Пародонт / Прикус / Рентген)</span>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && (
        <div style={{ padding: '0 14px 14px' }}>
          <Typography variant="caption" color="textSecondary" style={{ display: 'block', marginBottom: 8 }}>
            Заполняется по желанию. По умолчанию свернуто, чтобы не мешать рутинному приёму.
          </Typography>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
            <div>
              <Label htmlFor="dental-ohis" style={{ display: 'block', marginBottom: 4 }}>OHIS</Label>
              <Input
                id="dental-ohis"
                type="number"
                aria-label="OHIS индекс гигиены"
                value={hygieneIndices?.ohis || ''}
                onChange={(e) => onHygieneChange('ohis', e.target.value)}
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
                aria-label="PLI индекс налёта"
                value={hygieneIndices?.pli || ''}
                onChange={(e) => onHygieneChange('pli', e.target.value)}
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
                aria-label="CPI пародонтальный индекс"
                value={hygieneIndices?.cpi || ''}
                onChange={(e) => onHygieneChange('cpi', e.target.value)}
                placeholder="0 - 4"
                disabled={disabled}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
            </div>
            <div>
              <Label htmlFor="dental-bleeding" style={{ display: 'block', marginBottom: 4 }}>Кровоточивость %</Label>
              <Input
                id="dental-bleeding"
                type="number"
                aria-label="Индекс кровоточивости"
                value={hygieneIndices?.bleeding || ''}
                onChange={(e) => onHygieneChange('bleeding', e.target.value)}
                placeholder="0 - 100"
                disabled={disabled}
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
            </div>
          </div>
          <Typography variant="caption" color="textSecondary" style={{ display: 'block', marginTop: 10 }}>
            Пародонтальные карманы, прикус и рентген — в EMRContainerV2 (вкладка «Протоколы визитов»).
          </Typography>
        </div>
      )}
    </div>
  );
};

CollapsibleExtras.propTypes = {
  hygieneIndices: PropTypes.object,
  onHygieneChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};

const VisitHistory = ({ history, loading }) => {
  if (loading) {
    return <Skeleton style={{ height: 80, borderRadius: 8 }} />;
  }
  if (!history || history.length === 0) {
    return (
      <Typography variant="body2" color="textSecondary" style={{ fontStyle: 'italic' }}>
        Нет предыдущих визитов.
      </Typography>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {history.map((visit, idx) => (
        <div
          key={visit.id || idx}
          style={{
            padding: '8px 12px',
            border: '1px solid var(--mac-border)',
            borderRadius: 6,
            background: 'var(--mac-bg-secondary)',
          }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
            <Typography variant="body2" style={{ fontWeight: 500 }}>
              {visit.date || visit.created_at || '—'}
            </Typography>
            {visit.icd10_code && (
              <Badge variant="primary" size="small">МКБ-10: {visit.icd10_code}</Badge>
            )}
          </div>
          {visit.diagnosis && (
            <Typography variant="body2" color="textSecondary" style={{ marginTop: 4 }}>
              {visit.diagnosis}
            </Typography>
          )}
          {visit.complaints && (
            <Typography variant="caption" color="textSecondary" style={{ marginTop: 2, display: 'block' }}>
              Жалобы: {visit.complaints}
            </Typography>
          )}
        </div>
      ))}
    </div>
  );
};

VisitHistory.propTypes = {
  history: PropTypes.array,
  loading: PropTypes.bool,
};

// =============================================================================
// AI Suggestion Dialog (исправляет главную проблему: AI suggestions не попадали в EMR)
// =============================================================================

const AISuggestionDialog = ({ open, onClose, onApply, anamnesis }) => {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          <Brain size={18} aria-hidden="true" />
          AI-подбор МКБ-10
        </Box>
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="textSecondary" style={{ marginBottom: 12 }}>
          AI анализирует жалобу/анамнез и предлагает подходящие коды МКБ-10.
          Нажмите «Добавить» рядом с кодом, чтобы вставить его в форму.
        </Typography>
        <Alert severity="info" style={{ marginBottom: 12 }}>
          AI формирует только черновик. Финальное медицинское решение должен подтвердить врач.
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
              onApply(suggestion);
              onClose();
            }
          }}
          title="AI: коды МКБ-10 по жалобе"
          expanded
        />
      </DialogContent>
      <DialogActions>
        <Button variant="outline" onClick={onClose}>Закрыть</Button>
      </DialogActions>
    </Dialog>
  );
};

AISuggestionDialog.propTypes = {
  open: PropTypes.bool,
  onClose: PropTypes.func.isRequired,
  onApply: PropTypes.func.isRequired,
  anamnesis: PropTypes.string,
};

// =============================================================================
// Main component
// =============================================================================

const DentalVisitScreen = ({
  patient,
  onCompleteVisit,
  loading: parentLoading,
}) => {
  const [emrData, setEmrData] = useState(EMPTY_EMR_DATA);
  const [rowVersion, setRowVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedTooth, setSelectedTooth] = useState(null);
  const [toothModalOpen, setToothModalOpen] = useState(false);
  const [showAIDialog, setShowAIDialog] = useState(false);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const visitId = patient?.visit_id;
  const patientId =
    patient?.patient?.id ||
    patient?.patient_id ||
    patient?.id ||
    null;

  // Load EMR on mount
  const loadEMR = useCallback(async () => {
    if (!visitId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const existing = await loadExistingEMR(visitId);
      if (existing) {
        const data = existing.data || EMPTY_EMR_DATA;
        setEmrData({
          ...EMPTY_EMR_DATA,
          ...data,
          specialty_data: {
            ...EMPTY_EMR_DATA.specialty_data,
            ...(data.specialty_data || {}),
          },
        });
        setRowVersion(existing.row_version || 0);
      } else {
        setEmrData({ ...EMPTY_EMR_DATA });
        setRowVersion(0);
      }
    } catch (error) {
      logger.error('[DentalVisitScreen] loadEMR failed', { error: error?.message });
      notify.error('Не удалось загрузить карту приёма. Проверьте соединение.');
    } finally {
      setLoading(false);
    }
  }, [visitId]);

  // Load patient history
  const loadHistory = useCallback(async () => {
    if (!patientId) return;
    setHistoryLoading(true);
    try {
      const response = await apiClient.get(`/v2/emr/patient/${patientId}`, {
        silent: true,
        validateStatus: (status) => status === 404 || (status >= 200 && status < 300),
      });
      if (response.status === 404) {
        setHistory([]);
      } else {
        const summaries = response.data?.summaries || response.data || [];
        setHistory(Array.isArray(summaries) ? summaries : []);
      }
    } catch (error) {
      logger.warn('[DentalVisitScreen] loadHistory failed', { error: error?.message });
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    loadEMR();
    loadHistory();
  }, [loadEMR, loadHistory]);

  // Auto-save EMR draft (debounced via 1.5s timeout on field changes)
  const [saveTimer, setSaveTimer] = useState(null);
  const scheduleAutosave = useCallback((nextData) => {
    if (saveTimer) clearTimeout(saveTimer);
    const timer = setTimeout(async () => {
      if (!visitId) return;
      setSaving(true);
      try {
        const result = await saveEMR(visitId, nextData, rowVersion, true);
        setRowVersion(result.row_version || rowVersion);
      } catch (error) {
        logger.warn('[DentalVisitScreen] autosave failed', { error: error?.message });
      } finally {
        setSaving(false);
      }
    }, 1500);
    setSaveTimer(timer);
  }, [saveTimer, visitId, rowVersion]);

  // Field change handlers
  const updateField = useCallback((field, value) => {
    setEmrData(prev => {
      const next = { ...prev, [field]: value };
      scheduleAutosave(next);
      return next;
    });
  }, [scheduleAutosave]);

  const updateSpecialtyData = useCallback((field, value) => {
    setEmrData(prev => {
      const next = {
        ...prev,
        specialty_data: {
          ...prev.specialty_data,
          [field]: value,
        },
      };
      scheduleAutosave(next);
      return next;
    });
  }, [scheduleAutosave]);

  // Tooth click → open ToothModal
  const handleToothClick = useCallback((toothNumber, toothData) => {
    setSelectedTooth({ number: toothNumber, data: toothData || {} });
    setToothModalOpen(true);
  }, []);

  const handleToothSave = useCallback((toothNumber, toothData) => {
    updateSpecialtyData('tooth_status', {
      ...(emrData.specialty_data?.tooth_status || {}),
      [toothNumber]: toothData,
    });
    setToothModalOpen(false);
    setSelectedTooth(null);
    notify.success(`Зуб ${toothNumber} сохранён`);
  }, [emrData.specialty_data, updateSpecialtyData]);

  // AI suggestion apply → writes to icd10_code field
  const handleAISuggestion = useCallback(() => {
    setShowAIDialog(true);
  }, []);

  const applyAISuggestion = useCallback((icd10Code) => {
    updateField('icd10_code', icd10Code);
    notify.success(`Код МКБ-10 добавлен: ${icd10Code}`);
  }, [updateField]);

  const isLoading = loading || parentLoading;
  const toothStatus = emrData.specialty_data?.tooth_status || {};

  return (
    <div className="dental-flex-col dental-gap-24">
      <Card padding="default">
        <PatientHeader
          patient={patient}
          onCompleteVisit={onCompleteVisit}
          loading={saving || parentLoading}
        />

        {isLoading ? (
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
              onChange={(v) => updateField('anamnesis_morbi', v)}
              disabled={saving}
            />

            {/* Diagnosis + ICD-10 + AI button */}
            <DiagnosisSection
              diagnosis={emrData.diagnosis || ''}
              icd10={emrData.icd10_code || ''}
              onDiagnosisChange={(v) => updateField('diagnosis', v)}
              onIcd10Change={(v) => updateField('icd10_code', v)}
              onAISuggestion={handleAISuggestion}
              disabled={saving}
            />

            {/* Tooth chart — основная рабочая область */}
            <div style={{ marginBottom: 16 }}>
              <Label style={{ display: 'block', marginBottom: 6 }}>
                Схема зубов
              </Label>
              <TeethChart
                initialData={toothStatus}
                onToothClick={handleToothClick}
                readOnly={false}
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
              disabled={saving}
            />

            {/* Visit history — read-only */}
            <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--mac-border)' }}>
              <Typography variant="subtitle1" style={{ marginBottom: 12, fontWeight: 600 }}>
                История визитов пациента
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
          onSave={handleToothSave}
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

DentalVisitScreen.propTypes = {
  patient: PropTypes.object.isRequired,
  onCompleteVisit: PropTypes.func.isRequired,
  loading: PropTypes.bool,
};

export default DentalVisitScreen;
