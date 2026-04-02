import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Icon } from '../ui/macos';
import { labReportingApi } from '../../api/labReporting';
import { printService } from '../../services/print';
import {
  formatLabStatus,
  formatSeverityLabel,
  getLabStatusVariant,
  signerFieldLabels
} from './labUiLabels';

function extractFieldValue(field) {
  if (field.value_numeric !== null && field.value_numeric !== undefined) {
    return formatDecimalInputValue(field.value_numeric);
  }
  return field.value_text || '';
}

function formatDecimalInputValue(value) {
  if (value === null || value === undefined || value === '') {
    return '';
  }
  const text = String(value);
  if (!text.includes('.')) {
    return text;
  }
  const [integerPart, decimalPart = ''] = text.split('.');
  const trimmedDecimal = decimalPart.replace(/0+$/, '');
  return trimmedDecimal ? `${integerPart}.${trimmedDecimal}` : integerPart;
}

function flagVariant(flag, severity = null) {
  if (severity !== null && severity >= 300) {
    return 'danger';
  }
  if (flag === 'high' || flag === 'warning' || flag === 'abnormal') {
    return 'warning';
  }
  if (flag === 'low') {
    return 'primary';
  }
  return 'info';
}

function formatFlagLabel(field) {
  if (!field?.resolved_flag) {
    return 'норма';
  }
  const label = {
    high: 'выше нормы',
    low: 'ниже нормы',
    warning: 'предупреждение',
    abnormal: 'отклонение',
    critical: 'критично'
  }[field.resolved_flag] || field.resolved_flag;
  const direction = field?.resolved_flag_meta?.direction;
  return direction ? `${label} ${direction}` : label;
}

function formatThreshold(meta) {
  const matchedThreshold = meta?.matched_threshold;
  if (!matchedThreshold?.value) {
    return '';
  }
  const operator = {
    lt: '<',
    lte: '<=',
    gt: '>',
    gte: '>='
  }[matchedThreshold.operator] || matchedThreshold.operator || '';
  return `${operator} ${formatDecimalInputValue(matchedThreshold.value)}`.trim();
}

function historySeverityState(item) {
  if ((item.critical_findings_count || 0) > 0) {
    return { label: 'critical', variant: 'danger', order: 300 };
  }
  if ((item.max_flag_severity || 0) >= 200) {
    return { label: 'flagged', variant: 'warning', order: 200 };
  }
  if ((item.max_flag_severity || 0) >= 100) {
    return { label: 'warning', variant: 'warning', order: 100 };
  }
  return { label: 'clean', variant: 'success', order: 0 };
}

function matchesHistoryFilter(item, filter) {
  const severity = historySeverityState(item);
  if (filter === 'critical') {
    return severity.label === 'critical';
  }
  if (filter === 'flagged') {
    return severity.order >= 100;
  }
  if (filter === 'clean') {
    return severity.order === 0;
  }
  return true;
}

function getServiceContextItems(appointment) {
  const serviceDetails = appointment?.service_details || [];
  if (serviceDetails.length > 0) {
    return serviceDetails
      .map((item) => ({
        key: item.id || item.code || item.name,
        label: item.name || item.code || 'Услуга',
        code: item.code || ''
      }))
      .filter((item) => item.key);
  }
  const serviceCodes = appointment?.service_codes || [];
  return serviceCodes.map((code) => ({
    key: code,
    label: code,
    code
  }));
}

function normalizeLabSections(sections = []) {
  return sections.map((section, sectionIndex) => ({
    key: section.key || section.section_key || section.id || `section-${sectionIndex}`,
    title: section.title || section.name || section.key || `Раздел ${sectionIndex + 1}`,
    fields: (section.fields || []).map((field, fieldIndex) => ({
      field_key: field.field_key || field.key || field.id || `${section.key || `section-${sectionIndex}`}-field-${fieldIndex}`,
      label: field.label || field.name || field.field_key || `Показатель ${fieldIndex + 1}`,
      value_numeric: field.value_numeric ?? null,
      value_text: field.value_text ?? '',
      reference_text: field.reference_text ?? '',
      unit: field.unit ?? '',
      resolved_flag: field.resolved_flag ?? null,
      resolved_flag_severity: field.resolved_flag_severity ?? null
    }))
  }));
}

function flattenLabResults(sections = []) {
  return sections.flatMap((section) =>
    (section.fields || []).map((field) => ({
      section_key: section.key,
      section_title: section.title,
      field_key: field.field_key,
      label: field.label,
      value_numeric: field.value_numeric,
      value_text: field.value_text,
      reference_text: field.reference_text,
      unit: field.unit,
      resolved_flag: field.resolved_flag,
      resolved_flag_severity: field.resolved_flag_severity
    }))
  );
}

function buildLabPrintPayload(instance, appointment) {
  const sections = normalizeLabSections(instance?.sections || []);
  const patientSnapshot = instance?.patient_snapshot || {};
  const appointmentSnapshot = appointment || {};
  const clinic = instance?.clinic || appointmentSnapshot?.clinic || {};
  const templateName = instance?.template?.name || instance?.template_name || 'Лабораторный бланк';
  const reportDate =
    instance?.printed_at
    || instance?.finalized_at
    || instance?.updated_at
    || instance?.created_at
    || new Date().toISOString();

  return {
    lab_order: {
      id: instance?.id || null,
      visit_id: instance?.visit_id || appointmentSnapshot?.visit_id || null,
      patient_id: instance?.patient_id || appointmentSnapshot?.patient_id || null,
      template_id: instance?.template_id || null,
      template_name: templateName,
      status: instance?.status || 'DRAFT',
      created_at: instance?.created_at || null,
      finalized_at: instance?.finalized_at || null,
      printed_at: instance?.printed_at || null
    },
    lab_results: flattenLabResults(sections),
    patient: {
      full_name:
        patientSnapshot.full_name
        || appointmentSnapshot.patient_fio
        || appointmentSnapshot.patient_name
        || `Пациент #${instance?.patient_id || appointmentSnapshot.patient_id || ''}`,
      birth_date: patientSnapshot.birth_date || appointmentSnapshot.patient_birth_year || '',
      address: patientSnapshot.address || appointmentSnapshot.address || '',
      phone: patientSnapshot.phone || appointmentSnapshot.patient_phone || '',
      sex: patientSnapshot.sex || appointmentSnapshot.sex || ''
    },
    clinic: {
      name: clinic.name || clinic.clinic_name || 'МЕДИЦИНСКАЯ КЛИНИКА',
      address: clinic.address || '',
      phone: clinic.phone || '',
      website: clinic.website || ''
    },
    branding: {
      clinic_name: clinic.name || clinic.clinic_name || 'МЕДИЦИНСКАЯ КЛИНИКА',
      address: clinic.address || '',
      phone: clinic.phone || '',
      document_title: templateName,
      document_subtitle: instance?.template?.subtitle || ''
    },
    signers: instance?.signer_snapshot || {},
    sections,
    template_name: templateName,
    report_date: typeof reportDate === 'string' ? reportDate : new Date(reportDate).toISOString(),
    footer_notes: instance?.footer_notes || instance?.template?.footer_notes || '',
    critical_findings: instance?.critical_findings || [],
    smear_matrix_mode: Boolean(instance?.template?.layout_mode === 'smear_matrix'),
    oam_docx_mode: Boolean(instance?.template?.layout_mode === 'oam'),
    docx_three_column_mode: Boolean(instance?.template?.layout_mode === 'docx_three_column')
  };
}

export default function LabReportWorkbench({
  selectedAppointment,
  templates,
  templateResolution,
  templateResolutionLoading,
  reportHistory,
  recentReports,
  activeInstance,
  onInstanceChange,
  onOpenInstance,
  onRefreshHistory,
  onRefreshRecentReports,
  onQueueChanged,
  notify
}) {
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [draftValues, setDraftValues] = useState({});
  const [signerSnapshot, setSignerSnapshot] = useState({});
  const [saving, setSaving] = useState(false);
  const [busyAction, setBusyAction] = useState('');
  const [printFeedback, setPrintFeedback] = useState(null);
  const [historySeverityFilter, setHistorySeverityFilter] = useState('all');
  const autoActionRef = useRef('');

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
  const resolvedVisitId = templateResolution?.visit_id || selectedAppointment?.visit_id || null;
  const singleAllowedTemplate =
    serviceContextPresent && templateOptions.length === 1 ? templateOptions[0] : null;

  const filteredHistory = useMemo(() => {
    const items = reportHistory.filter((item) => matchesHistoryFilter(item, historySeverityFilter));
    return [...items].sort((left, right) => {
      const leftSeverity = historySeverityState(left);
      const rightSeverity = historySeverityState(right);
      if (rightSeverity.order !== leftSeverity.order) {
        return rightSeverity.order - leftSeverity.order;
      }
      return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
    });
  }, [historySeverityFilter, reportHistory]);
  const filteredRecentReports = useMemo(() => {
    const items = recentReports.filter((item) => matchesHistoryFilter(item, historySeverityFilter));
    return [...items].sort((left, right) => {
      const leftSeverity = historySeverityState(left);
      const rightSeverity = historySeverityState(right);
      if (rightSeverity.order !== leftSeverity.order) {
        return rightSeverity.order - leftSeverity.order;
      }
      return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
    });
  }, [historySeverityFilter, recentReports]);
  const showRecentReportsBrowser = !selectedAppointment && !activeInstance;

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
    autoActionRef.current = '';
  }, [selectedAppointment?.id, selectedAppointment?.appointment_id, resolvedVisitId]);

  useEffect(() => {
    if (activeInstance || !selectedAppointment) {
      return;
    }
    const defaultTemplateId =
      templateResolution?.default_template?.id || templateOptions[0]?.id || '';
    setSelectedTemplateId((current) => {
      if (current && templateOptions.some((template) => String(template.id) === String(current))) {
        return current;
      }
      return defaultTemplateId ? String(defaultTemplateId) : '';
    });
  }, [activeInstance, selectedAppointment, templateOptions, templateResolution?.default_template?.id]);

  useEffect(() => {
    if (
      activeInstance
      || !selectedAppointment
      || !singleAllowedTemplate
      || templateResolutionLoading
      || resolutionHasBlockingGap
      || saving
    ) {
      return;
    }

    const templateId = String(singleAllowedTemplate.id);
    const existingInstance = reportHistory
      .filter(
        (item) =>
          String(item.template?.id || item.template_id) === templateId
          && String(item.visit_id || '') === String(resolvedVisitId || '')
      )
      .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime())[0];
    const autoKey = `${selectedAppointment.id || selectedAppointment.appointment_id || 'patient'}:${resolvedVisitId || 'no-visit'}:${templateId}:${existingInstance?.id || 'new'}`;
    if (autoActionRef.current === autoKey) {
      return;
    }
    autoActionRef.current = autoKey;
    setSelectedTemplateId(templateId);

    if (existingInstance) {
      notify('info', 'Открываю уже созданный бланк для этого визита.');
      void onOpenInstance(existingInstance.id);
      return;
    }

    void handleCreateInstance(templateId, {
      successMessage: `Бланк "${singleAllowedTemplate.name}" создан автоматически.`
    });
  }, [
    activeInstance,
    handleCreateInstance,
    notify,
    onOpenInstance,
    reportHistory,
    resolvedVisitId,
    resolutionHasBlockingGap,
    saving,
    selectedAppointment,
    singleAllowedTemplate,
    templateResolutionLoading
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
                  Единственный допустимый бланк найден: <strong>{singleAllowedTemplate.name}</strong>. Открываю его автоматически.
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
                  disabled={saving || templateResolutionLoading || resolutionHasBlockingGap}
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
                </div>

                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {activeInstance.status !== 'FINALIZED' && activeInstance.status !== 'PRINTED' && (
                    <>
                      <Button variant="outline" onClick={handleSaveDraft} disabled={saving}>
                        <Icon name="square.and.arrow.down" size={16} />
                        {busyAction === 'save' ? 'Сохраняю...' : 'Сохранить черновик'}
                      </Button>
                      <Button variant="outline" onClick={handleMarkReady} disabled={saving}>
                        <Icon name="checkmark.circle" size={16} />
                        {busyAction === 'ready' ? 'Перевожу...' : 'Отметить готовым'}
                      </Button>
                      <Button variant="primary" onClick={handleFinalize} disabled={saving}>
                        <Icon name="lock.circle" size={16} />
                        {busyAction === 'finalize' ? 'Финализирую...' : 'Финализировать'}
                      </Button>
                    </>
                  )}
                  {(activeInstance.status === 'FINALIZED' || activeInstance.status === 'PRINTED') && (
                    <>
                      <Button variant="outline" onClick={handleRevise} disabled={saving}>
                        <Icon name="arrow.triangle.branch" size={16} />
                        {busyAction === 'revise' ? 'Создаю ревизию...' : 'Создать ревизию'}
                      </Button>
                      <Button variant="primary" onClick={handlePrint} disabled={saving}>
                        <Icon name="printer" size={16} />
                        {busyAction === 'print' ? 'Отправляю...' : 'Печать результата'}
                      </Button>
                    </>
                  )}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                {['lab_technician_label', 'lab_technician_name', 'approver_label', 'approver_name'].map((key) => (
                  <label key={key} style={{ display: 'grid', gap: '6px' }}>
                    <span>{signerFieldLabels[key] || key}</span>
                    <input className="macos-input" value={signerSnapshot?.[key] || ''} onChange={(event) => setSignerSnapshot((prev) => ({ ...prev, [key]: event.target.value }))} />
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
                                disabled={activeInstance.status === 'FINALIZED' || activeInstance.status === 'PRINTED'}
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
                                rows={3}
                                value={currentValue}
                                onChange={(event) => updateField(field.field_key, event.target.value)}
                                disabled={activeInstance.status === 'FINALIZED' || activeInstance.status === 'PRINTED'}
                              />
                            ) : (
                              <input
                                className="macos-input"
                                value={currentValue}
                                onChange={(event) => updateField(field.field_key, event.target.value)}
                                disabled={activeInstance.status === 'FINALIZED' || activeInstance.status === 'PRINTED'}
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
        <Card variant="filled" padding="none">
          <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: '16px' }}>
            <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Icon name="clock.arrow.circlepath" size={20} />
              {showRecentReportsBrowser ? 'Недавние лабораторные бланки' : 'Доступные бланки пациента'}
            </CardTitle>
          </CardHeader>
          <CardContent style={{ padding: '16px', background: 'var(--mac-bg-secondary)', display: 'grid', gap: '12px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {[
                { id: 'all', label: 'Все' },
                { id: 'clean', label: 'Без флагов' },
                { id: 'flagged', label: 'С флагами' },
                { id: 'critical', label: 'Критические' }
              ].map((filter) => (
                <Button
                  key={filter.id}
                  variant={historySeverityFilter === filter.id ? 'primary' : 'outline'}
                  onClick={() => setHistorySeverityFilter(filter.id)}
                >
                  {filter.label}
                </Button>
              ))}
            </div>

            {(showRecentReportsBrowser ? filteredRecentReports : filteredHistory).length === 0 ? (
              <Alert severity="info">
                {showRecentReportsBrowser
                  ? 'В лаборатории пока нет сохранённых бланков для повторного открытия.'
                  : 'Для выбранного фильтра нет лабораторных бланков.'}
              </Alert>
            ) : (
              (showRecentReportsBrowser ? filteredRecentReports : filteredHistory).map((item) => {
                const severity = historySeverityState(item);
                const patientLabel = item.patient_snapshot?.full_name || `Пациент #${item.patient_id}`;
                return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onOpenInstance(item.id)}
                  style={{
                  border: '1px solid var(--mac-border)',
                  borderRadius: '14px',
                  background: activeInstance?.id === item.id ? 'color-mix(in oklab, var(--mac-accent) 10%, var(--mac-bg-primary))' : 'var(--mac-bg-primary)',
                  padding: '12px 14px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: '12px',
                  alignItems: 'center',
                  cursor: 'pointer'
                }}
                  >
                    <div style={{ display: 'grid', gap: '4px', textAlign: 'left' }}>
                      <div style={{ fontWeight: 600, color: 'var(--mac-text-primary)' }}>{item.template?.name || `Бланк #${item.id}`}</div>
                      <div style={{ color: 'var(--mac-text-secondary)', fontSize: '13px' }}>
                        {showRecentReportsBrowser
                          ? `${patientLabel} | ${new Date(item.created_at).toLocaleString()}`
                          : new Date(item.created_at).toLocaleString()}
                      </div>
                      {showRecentReportsBrowser && (
                        <div style={{ color: 'var(--mac-text-secondary)', fontSize: '12px' }}>
                          Визит: {item.visit_id || 'без визита'}
                        </div>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                      <Badge variant={getLabStatusVariant(item.status)}>{formatLabStatus(item.status)}</Badge>
                      <Badge variant={severity.variant}>{formatSeverityLabel(severity.label)}</Badge>
                      {item.flagged_findings_count > 0 && (
                        <Badge variant="info">{item.flagged_findings_count} флагов</Badge>
                      )}
                      {item.critical_findings_count > 0 && (
                        <Badge variant="danger">{item.critical_findings_count} критич.</Badge>
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </CardContent>
        </Card>
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

LabReportWorkbench.defaultProps = {
  selectedAppointment: null,
  templateResolution: null,
  templateResolutionLoading: false,
  reportHistory: [],
  recentReports: [],
  onRefreshRecentReports: undefined,
  onQueueChanged: undefined,
  activeInstance: null
};
