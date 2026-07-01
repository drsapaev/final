import { useCallback, useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Icon,
} from '../ui/macos';
import { labReportingApi } from '../../api/labReporting';
import { printService } from '../../services/print';
import logger from '../../utils/logger';
import {
  formatLabStatus,
  formatSeverityLabel,
  getLabStatusVariant,
  signerFieldLabels
} from './labUiLabels';

// P-04 fix: декомпозиция монолитного компонента (969 → ~530 строк).
// Helper-функции и подкомпоненты вынесены в отдельные модули:
import {
  extractFieldValue,
  formatFlagLabel,
  formatThreshold,
  getServiceContextItems,
  buildLabPrintPayload,
} from './utils/labReportNormalize';
import {
  hasLabReportAction,
  flagVariant,
} from './utils/labReportActions';
import LabStatusStepper from './LabStatusStepper';
import LabReportActionsBar from './LabReportActionsBar';
import LabReportHistoryPanel from './LabReportHistoryPanel';

export default function LabReportWorkbench({
  selectedAppointment = null,
  templates,
  templateResolution = null,
  templateResolutionLoading = false,
  reportHistory = [],
  recentReports = [],
  activeInstance = null,
  onInstanceChange,
  onOpenInstance,
  onRefreshHistory,
  onRefreshRecentReports = undefined,
  onQueueChanged = undefined,
  notify
}) {
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [draftValues, setDraftValues] = useState({});
  const [signerSnapshot, setSignerSnapshot] = useState({});
  const [saving, setSaving] = useState(false);
  const [busyAction, setBusyAction] = useState('');
  const [printFeedback, setPrintFeedback] = useState(null);
  const [historySeverityFilter, setHistorySeverityFilter] = useState('all');

  const publishedTemplates = useMemo(
    () => templates.filter((template) => template.published_version_id || template.draft_version_id),
    [templates]
  );
  const serviceContextItems = useMemo(
    () => getServiceContextItems(selectedAppointment),
    [selectedAppointment]
  );
  const resolvedTemplates = templateResolution?.allowed_templates || [];
  const serviceContextPresent = (templateResolution?.service_codes || []).length > 0;
  const templateOptions = serviceContextPresent ? resolvedTemplates : publishedTemplates;
  const resolutionHasBlockingGap = serviceContextPresent && resolvedTemplates.length === 0;
  const singleAllowedTemplate =
    serviceContextPresent && templateOptions.length === 1 ? templateOptions[0] : null;

  const showRecentReportsBrowser = !selectedAppointment && !activeInstance;
  const canEditActiveInstance = hasLabReportAction(activeInstance, 'edit');
  const canSaveDraft = hasLabReportAction(activeInstance, 'save_draft');
  const canMarkReady = hasLabReportAction(activeInstance, 'mark_ready');
  const canFinalize = hasLabReportAction(activeInstance, 'finalize');
  const canRevise = hasLabReportAction(activeInstance, 'revise');
  const canPrint = hasLabReportAction(activeInstance, 'print');

  const handleCreateInstance = useCallback(async (templateIdOverride = null, options = {}) => {
    const templateId = templateIdOverride || selectedTemplateId;
    if (!selectedAppointment?.patient_id || !templateId) {
      notify('error', 'Выберите запись и шаблон.');
      return;
    }
    if (resolutionHasBlockingGap) {
      notify('error', 'Для выбранных услуг нет настроенного лабораторного бланка. Добавьте mapping service_code -> template.');
      return;
    }
    setSaving(true);
    setBusyAction('create');
    try {
      const instance = await labReportingApi.createInstance({
        patient_id: selectedAppointment.patient_id,
        appointment_id: selectedAppointment.appointment_id || null,
        visit_id: templateResolution?.visit_id || selectedAppointment.visit_id || null,
        template_id: Number(templateId),
        service_codes: templateResolution?.service_codes || selectedAppointment.service_codes || [],
        service_items: (selectedAppointment.service_details || []).map((item) => ({
          service_id: item.id || null,
          code: item.code || null,
          name: item.name || null
        }))
      });
      onInstanceChange(instance);
      await onRefreshHistory(selectedAppointment.patient_id);
      await onRefreshRecentReports?.();
      await onQueueChanged?.();
      notify('success', options.successMessage || 'Новый лабораторный бланк создан.');
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
      setBusyAction(null);
    }
  }, [
    notify,
    onInstanceChange,
    onRefreshHistory,
    onRefreshRecentReports,
    onQueueChanged,
    resolutionHasBlockingGap,
    selectedAppointment,
    selectedTemplateId,
    templateResolution
  ]);

  useEffect(() => {
    if (!activeInstance) {
      setDraftValues({});
      setSignerSnapshot({});
      setPrintFeedback(null);
      return;
    }
    const values = {};
    activeInstance.sections.forEach((section) => {
      section.fields.forEach((field) => {
        values[field.field_key] = extractFieldValue(field);
      });
    });
    setDraftValues(values);
    setSignerSnapshot(activeInstance.signer_snapshot || {});
    setSelectedTemplateId(String(activeInstance.template_id));
  }, [activeInstance]);

  useEffect(() => {
    if (activeInstance || !selectedAppointment) {
      return;
    }
    const defaultTemplateId =
      templateResolution?.default_template?.id
      || (!serviceContextPresent ? templateOptions[0]?.id : '')
      || '';
    setSelectedTemplateId((current) => {
      if (current && templateOptions.some((template) => String(template.id) === String(current))) {
        return current;
      }
      return defaultTemplateId ? String(defaultTemplateId) : '';
    });
  }, [
    activeInstance,
    selectedAppointment,
    serviceContextPresent,
    templateOptions,
    templateResolution?.default_template?.id
  ]);

  function updateField(fieldKey, value) {
    setDraftValues((prev) => ({ ...prev, [fieldKey]: value }));
  }

  async function persistDraft() {
    if (!activeInstance) {
      return null;
    }
    const payload = [];
    activeInstance.sections.forEach((section) => {
      section.fields.forEach((field) => {
        const currentValue = draftValues[field.field_key];
        if (currentValue === undefined) {
          return;
        }
        payload.push({
          field_key: field.field_key,
          value_text: currentValue === '' ? null : currentValue,
          value_numeric: field.value_type === 'numeric' && currentValue !== '' ? currentValue : null,
          comment: field.comment || null
        });
      });
    });

    let latestInstance = activeInstance;
    if (JSON.stringify(activeInstance.signer_snapshot || {}) !== JSON.stringify(signerSnapshot || {})) {
      latestInstance = await labReportingApi.updateInstance(activeInstance.id, {
        signer_snapshot: signerSnapshot
      });
    }
    if (payload.length > 0) {
      const response = await labReportingApi.bulkSaveValues(activeInstance.id, payload);
      latestInstance = response.instance;
    }
    onInstanceChange(latestInstance);
    return latestInstance;
  }

  async function handleSaveDraft() {
    if (!activeInstance) {
      notify('error', 'Сначала создайте или откройте бланк.');
      return;
    }
    setSaving(true);
    setBusyAction('save');
    try {
      await persistDraft();
      await onRefreshHistory(activeInstance.patient_id);
      notify('success', 'Черновик сохранён.');
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
      setBusyAction('');
    }
  }

  async function handleMarkReady() {
    if (!activeInstance) return;
    setSaving(true);
    setBusyAction('ready');
    try {
      const latest = await persistDraft();
      const ready = await labReportingApi.markReady((latest || activeInstance).id);
      onInstanceChange(ready);
      await onRefreshHistory(ready.patient_id);
      await onRefreshRecentReports?.();
      await onQueueChanged?.();
      notify('success', 'Бланк отмечен как готовый.');
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
      setBusyAction('');
    }
  }

  async function handleFinalize() {
    if (!activeInstance) return;
    setSaving(true);
    setBusyAction('finalize');
    try {
      const latest = await persistDraft();
      const finalized = await labReportingApi.finalize((latest || activeInstance).id);
      onInstanceChange(finalized);
      await onRefreshHistory(finalized.patient_id);
      await onRefreshRecentReports?.();
      await onQueueChanged?.();
      notify('success', 'Бланк финализирован.');
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
      setBusyAction('');
    }
  }

  async function handleRevise() {
    if (!activeInstance) return;
    setSaving(true);
    setBusyAction('revise');
    try {
      const revised = await labReportingApi.revise(activeInstance.id);
      onInstanceChange(revised);
      await onRefreshHistory(revised.patient_id);
      await onRefreshRecentReports?.();
      notify('success', 'Создана ревизия бланка.');
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
      setBusyAction('');
    }
  }

  async function handlePrint() {
    if (!activeInstance) return;
    setSaving(true);
    setBusyAction('print');
    setPrintFeedback({
      severity: 'info',
      text: 'Отправляю лабораторный бланк на печать...'
    });
    try {
      notify('info', 'Пытаюсь отправить бланк на принтер...');

      const printResult = await printService.printLabResults(
        buildLabPrintPayload(activeInstance, selectedAppointment)
      );

      if (printResult.success) {
        const printed = await labReportingApi.markPrinted(activeInstance.id);
        onInstanceChange(printed);
        await onRefreshHistory(printed.patient_id);
        await onRefreshRecentReports?.();
        await onQueueChanged?.();
        setPrintFeedback({
          severity: 'success',
          text: `Лабораторный бланк отправлен на печать${printResult.data?.printer ? ` (${printResult.data.printer})` : ''}.`
        });
        notify(
          'success',
          `Лабораторный бланк отправлен на печать${printResult.data?.printer ? ` (${printResult.data.printer})` : ''}.`
        );
        return;
      }

      logger.warn('[LabReportWorkbench] direct lab print failed, falling back to PDF', {
        instanceId: activeInstance.id,
        error: printResult.error
      });
      notify('warning', 'Прямая печать недоступна, использую PDF-файл как запасной вариант.');

      const blob = await labReportingApi.downloadPdf(activeInstance.id);
      const url = URL.createObjectURL(blob);
      const popup = window.open(url, '_blank', 'noopener,noreferrer');
      const printed = await labReportingApi.markPrinted(activeInstance.id);
      onInstanceChange(printed);
      await onRefreshHistory(printed.patient_id);
      await onRefreshRecentReports?.();
      await onQueueChanged?.();
      setPrintFeedback({
        severity: popup ? 'success' : 'warning',
        text: popup
          ? 'PDF открыт в новой вкладке. Статус печати обновлён.'
          : 'PDF сформирован. Если новая вкладка не открылась, проверьте блокировку pop-up.'
      });
      notify(
        popup ? 'success' : 'info',
        popup
          ? 'PDF открыт в новой вкладке и статус печати обновлён.'
          : 'PDF сформирован. Если вкладка не открылась, проверьте блокировку pop-up.'
      );
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      setPrintFeedback({
        severity: 'error',
        text: error.message
      });
      notify('error', error.message);
    } finally {
      setSaving(false);
      setBusyAction('');
    }
  }

  return (
    <div style={{ display: 'grid', gap: '16px' }}>
      <Card variant="filled" padding="none">
        <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: '16px' }}>
          <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Icon name="doc.text" size={20} />
            Редактор лабораторного бланка
          </CardTitle>
        </CardHeader>
        <CardContent style={{ padding: '16px', background: 'var(--mac-bg-secondary)', display: 'grid', gap: '16px' }}>
          {!selectedAppointment && !activeInstance ? (
            <Alert severity="info">
              {recentReports.length > 0
                ? 'Выберите пациента из очереди или откройте уже существующий лабораторный бланк из списка ниже.'
                : 'Выберите пациента из очереди или откройте уже существующий лабораторный бланк.'}
            </Alert>
          ) : !activeInstance ? (
            <div style={{ display: 'grid', gap: '12px' }}>
              <div style={{ color: 'var(--mac-text-secondary)' }}>
                Пациент: <strong style={{ color: 'var(--mac-text-primary)' }}>{selectedAppointment?.patient_fio}</strong>
              </div>
              {serviceContextItems.length > 0 && (
                <div style={{ display: 'grid', gap: '8px' }}>
                  <div style={{ color: 'var(--mac-text-secondary)', fontSize: '14px' }}>
                    Услуги визита
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {serviceContextItems.map((item) => (
                      <Badge key={item.key} variant="info">
                        {item.label}
                        {item.code ? ` • ${item.code}` : ''}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {templateResolutionLoading && (
                <Alert severity="info">Подбираю доступные бланки для выбранного визита...</Alert>
              )}
              {!templateResolutionLoading && templateResolution?.default_template && (
                <Alert severity="info">
                  Рекомендуемый бланк: <strong>{templateResolution.default_template.name}</strong>
                </Alert>
              )}
              {!templateResolutionLoading && templateResolution?.unmapped_service_codes?.length > 0 && (
                <Alert severity={resolvedTemplates.length > 0 ? 'warning' : 'error'}>
                  Ненастроенные service codes: {templateResolution.unmapped_service_codes.join(', ')}
                </Alert>
              )}
              {!templateResolutionLoading && resolutionHasBlockingGap && (
                <Alert severity="error">
                  Для выбранного визита не найдено ни одного допустимого бланка. Сначала настройте mapping услуги к шаблону.
                </Alert>
              )}
              {!templateResolutionLoading && singleAllowedTemplate && !resolutionHasBlockingGap && (
                <Alert severity="info">
                  Единственный допустимый бланк найден: <strong>{singleAllowedTemplate.name}</strong>. Нажмите «Создать бланк», чтобы открыть его для заполнения.
                </Alert>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '12px', alignItems: 'end' }}>
                <label style={{ display: 'grid', gap: '6px' }}>
                  <span>{serviceContextPresent ? 'Допустимый бланк' : 'Шаблон бланка'}</span>
                  <select
                    className="macos-input"
                    value={selectedTemplateId}
                    onChange={(event) => setSelectedTemplateId(event.target.value)}
                    disabled={templateResolutionLoading || resolutionHasBlockingGap}
                  >
                    <option value="">Выберите шаблон</option>
                    {templateOptions.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.name} ({template.family})
                      </option>
                    ))}
                  </select>
                </label>
                <Button
                  variant="primary"
                  onClick={() => handleCreateInstance()}
                  disabled={saving || templateResolutionLoading || resolutionHasBlockingGap || !selectedTemplateId}
                >
                  <Icon name="plus.rectangle.on.folder" size={16} />
                  {busyAction === 'create' ? 'Создаю...' : 'Создать бланк'}
                </Button>
              </div>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
                <div style={{ display: 'grid', gap: '6px' }}>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <div style={{ fontSize: '18px', fontWeight: 600, color: 'var(--mac-text-primary)' }}>
                      {activeInstance.patient_snapshot?.full_name || `Пациент #${activeInstance.patient_id}`}
                    </div>
                    <Badge variant={getLabStatusVariant(activeInstance.status)}>{formatLabStatus(activeInstance.status)}</Badge>
                    <Badge variant="info">{activeInstance.template?.name}</Badge>
                  </div>
                  <div style={{ color: 'var(--mac-text-secondary)', fontSize: '14px' }}>
                    Визит: {activeInstance.visit_id || 'без визита'} | Бланк #{activeInstance.id}
                  </div>
                  {/* P-20 fix: визуальный stepper жизненного цикла бланка.
                      Показывает текущую фазу и будущие шаги. */}
                  <LabStatusStepper status={activeInstance.status} />
                </div>

                {/* P-04 fix: панель действий вынесена в LabReportActionsBar */}
                <LabReportActionsBar
                  saving={saving}
                  busyAction={busyAction}
                  canSaveDraft={canSaveDraft}
                  canMarkReady={canMarkReady}
                  canFinalize={canFinalize}
                  canRevise={canRevise}
                  canPrint={canPrint}
                  onSaveDraft={handleSaveDraft}
                  onMarkReady={handleMarkReady}
                  onFinalize={handleFinalize}
                  onRevise={handleRevise}
                  onPrint={handlePrint}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                {['lab_technician_label', 'lab_technician_name', 'approver_label', 'approver_name'].map((key) => (
                  <label key={key} style={{ display: 'grid', gap: '6px' }}>
                    <span>{signerFieldLabels[key] || key}</span>
                    <input
                      className="macos-input"
                      aria-label={signerFieldLabels[key] || key}
                      value={signerSnapshot?.[key] || ''}
                      onChange={(event) => setSignerSnapshot((prev) => ({ ...prev, [key]: event.target.value }))}
                    />
                  </label>
                ))}
              </div>

              {printFeedback && (
                <Alert severity={printFeedback.severity}>{printFeedback.text}</Alert>
              )}

              {activeInstance.critical_findings?.length > 0 && (
                <Alert severity="error">
                  <div style={{ display: 'grid', gap: '8px' }}>
                    <strong>Критические результаты</strong>
                    {activeInstance.critical_findings.map((finding) => (
                      <div
                        key={`${finding.section_key}-${finding.field_key}`}
                        style={{
                          display: 'grid',
                          gridTemplateColumns: 'minmax(180px, 1.4fr) minmax(110px, 0.7fr) minmax(110px, 0.7fr) minmax(100px, 0.6fr)',
                          gap: '8px',
                          alignItems: 'center'
                        }}
                      >
                        <div style={{ display: 'grid', gap: '2px' }}>
                          <strong>{finding.label}</strong>
                          <span style={{ fontSize: '12px', color: 'var(--mac-text-secondary)' }}>
                            {finding.section_title || finding.section_key}
                          </span>
                        </div>
                        <div>
                          {finding.value_display}
                          {finding.unit ? ` ${finding.unit}` : ''}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--mac-text-secondary)' }}>
                          {finding.threshold_display || finding.reference_text || '—'}
                        </div>
                          <Badge variant={flagVariant(finding.resolved_flag, finding.resolved_flag_severity)}>
                            {formatFlagLabel(finding)}
                          </Badge>
                      </div>
                    ))}
                  </div>
                </Alert>
              )}

              <div style={{ display: 'grid', gap: '16px' }}>
                {activeInstance.sections.map((section) => (
                  <div key={section.key} style={{ border: '1px solid var(--mac-border)', borderRadius: '16px', overflow: 'hidden', background: 'var(--mac-bg-primary)' }}>
                    <div style={{ padding: '12px 16px', background: 'var(--mac-bg-tertiary)', fontWeight: 600 }}>
                      {section.title || section.key}
                    </div>
                    <div style={{ padding: '12px 16px', display: 'grid', gap: '10px' }}>
                      {section.fields.map((field) => {
                        const choiceOptions = field.choice_options || [];
                        const currentValue = draftValues[field.field_key] ?? '';

                        return (
                          <div
                            key={field.field_key}
                            style={{
                              display: 'grid',
                              gridTemplateColumns:
                                'minmax(220px, 1.2fr) minmax(140px, 0.9fr) minmax(80px, 0.5fr) minmax(90px, 0.7fr) minmax(70px, 0.4fr)',
                              gap: '8px',
                              alignItems: 'center'
                            }}
                          >
                            <div style={{ display: 'grid', gap: '4px' }}>
                              <strong style={{ color: 'var(--mac-text-primary)' }}>{field.label}</strong>
                              <div style={{ display: 'grid', gap: '2px', color: 'var(--mac-text-secondary)', fontSize: '12px' }}>
                                <span>Норма: {field.reference_text || 'не задана'}</span>
                                {field.resolved_flag_meta?.matched_threshold && (
                                  <span>
                                    Порог: {formatThreshold(field.resolved_flag_meta)}
                                    {field.resolved_flag_source ? ` • ${field.resolved_flag_source}` : ''}
                                  </span>
                                )}
                              </div>
                            </div>
                            {field.value_type === 'choice' && choiceOptions.length > 0 ? (
                              <select
                                className="macos-input"
                                value={currentValue}
                                onChange={(event) => updateField(field.field_key, event.target.value)}
                                disabled={!canEditActiveInstance}
                              >
                                <option value="">Выберите значение</option>
                                {currentValue && !choiceOptions.includes(currentValue) && (
                                  <option value={currentValue}>{currentValue}</option>
                                )}
                                {choiceOptions.map((option) => (
                                  <option key={option} value={option}>
                                    {option}
                                  </option>
                                ))}
                              </select>
                            ) : field.value_type === 'multiline' ? (
                              <textarea
                                className="macos-input"
                                aria-label={`Lab result for ${field.label}`}
                                rows={3}
                                value={currentValue}
                                onChange={(event) => updateField(field.field_key, event.target.value)}
                                disabled={!canEditActiveInstance}
                              />
                            ) : (
                              <input
                                className="macos-input"
                                aria-label={`Lab result for ${field.label}`}
                                value={currentValue}
                                onChange={(event) => updateField(field.field_key, event.target.value)}
                                disabled={!canEditActiveInstance}
                              />
                            )}
                            <div style={{ color: 'var(--mac-text-secondary)', fontSize: '13px' }}>
                              {field.unit || '—'}
                            </div>
                            <Badge variant={flagVariant(field.resolved_flag, field.resolved_flag_severity)}>
                              {formatFlagLabel(field)}
                            </Badge>
                            {field.required ? <Badge variant="warning">обязательное</Badge> : <span />}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {(showRecentReportsBrowser || reportHistory.length > 0) && (
        // P-04 fix: панель истории вынесена в LabReportHistoryPanel
        <LabReportHistoryPanel
          showRecentReportsBrowser={showRecentReportsBrowser}
          recentReports={recentReports}
          reportHistory={reportHistory}
          historySeverityFilter={historySeverityFilter}
          onSeverityFilterChange={setHistorySeverityFilter}
          activeInstanceId={activeInstance?.id}
          onOpenInstance={onOpenInstance}
        />
      )}
    </div>
  );
}

LabReportWorkbench.propTypes = {
  selectedAppointment: PropTypes.object,
  templates: PropTypes.array.isRequired,
  templateResolution: PropTypes.object,
  templateResolutionLoading: PropTypes.bool,
  reportHistory: PropTypes.array,
  recentReports: PropTypes.array,
  activeInstance: PropTypes.object,
  onInstanceChange: PropTypes.func.isRequired,
  onOpenInstance: PropTypes.func.isRequired,
  onRefreshHistory: PropTypes.func.isRequired,
  onRefreshRecentReports: PropTypes.func,
  onQueueChanged: PropTypes.func,
  notify: PropTypes.func.isRequired
};
