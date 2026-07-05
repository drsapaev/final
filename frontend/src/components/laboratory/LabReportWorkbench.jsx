import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Icon,
  Input } from '../ui/macos';
import { labReportingApi } from '../../api/labReporting';
import { printService } from '../../services/print';
import logger from '../../utils/logger';
import {
  formatLabStatus,
  getLabStatusVariant,
  signerFieldLabels
} from './labUiLabels';

// WF-08 fix: confirmation dialog для irreversible actions (Finalize, Revise).
import { useConfirm } from '../common/ConfirmDialog';

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
// P-01 fix: AI-анализ перенесён из LabResultsManager в LabReportWorkbench.
import LabReportAIAnalysis from './LabReportAIAnalysis';

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
  // WF-08 fix: confirmation dialog для irreversible actions.
  // Finalize делает бланк immutable (можно только revise). Revise создаёт
  // новый instance. Оба действия необратимы без объяснения последствий.
  const [confirm, confirmDialog] = useConfirm();

  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [draftValues, setDraftValues] = useState({});
  const [signerSnapshot, setSignerSnapshot] = useState({});
  const [saving, setSaving] = useState(false);
  const [busyAction, setBusyAction] = useState('');
  const [printFeedback, setPrintFeedback] = useState(null);
  const [historySeverityFilter, setHistorySeverityFilter] = useState('all');
  // WF-11 fix: escape hatch для template resolution blocking gap.
  // Если услуги есть, но ни один template не смаплен — лаборант застревал.
  // Теперь можно нажать "Показать все шаблоны" и создать бланк без привязки.
  const [escapeHatchActive, setEscapeHatchActive] = useState(false);

  // Dirty state tracking: храним snapshot значений при загрузке instance,
  // сравниваем с текущими draftValues для определения несохранённых изменений.
  const initialValuesRef = useRef({ values: {}, signer: {} });

  const isDirty = useMemo(() => {
    if (!activeInstance) return false;
    // Сравниваем draftValues с initialValues
    const initial = initialValuesRef.current.values;
    const draftKeys = new Set([...Object.keys(draftValues), ...Object.keys(initial)]);
    for (const key of draftKeys) {
      if ((draftValues[key] || '') !== (initial[key] || '')) return true;
    }
    // Сравниваем signerSnapshot
    const initialSigner = initialValuesRef.current.signer;
    const signerKeys = ['lab_technician_label', 'lab_technician_name', 'approver_label', 'approver_name'];
    for (const key of signerKeys) {
      if ((signerSnapshot?.[key] || '') !== (initialSigner?.[key] || '')) return true;
    }
    return false;
  }, [activeInstance, draftValues, signerSnapshot]);

  // Navigation guard: предотвращает потерю данных при refresh/close.
  // Используем beforeunload напрямую (без useNavigationGuard) —
  // useNavigationGuard требует <Router> context, что ломает unit-тесты.
  // Переключение табов внутри SPA не теряет state (LabPanel хранит
  // selectedAppointment/activeInstance в useState).
  useEffect(() => {
    if (!isDirty) return;
    const handler = (event) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

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
  // WF-11 fix: при escape hatch показываем все published templates,
  // даже если service context есть, но resolution не нашёл шаблон.
  const templateOptions = serviceContextPresent ? resolvedTemplates : publishedTemplates;
  const effectiveTemplateOptions = escapeHatchActive
    ? publishedTemplates
    : templateOptions;
  const resolutionHasBlockingGap = serviceContextPresent && resolvedTemplates.length === 0 && !escapeHatchActive;
  const singleAllowedTemplate =
    serviceContextPresent && effectiveTemplateOptions.length === 1 ? effectiveTemplateOptions[0] : null;

  const showRecentReportsBrowser = !selectedAppointment && !activeInstance;
  const canEditActiveInstance = hasLabReportAction(activeInstance, 'edit');
  const canSaveDraft = hasLabReportAction(activeInstance, 'save_draft');
  // WF-round5: Mark Ready убран — был функционально пустой операцией.
  const canFinalize = hasLabReportAction(activeInstance, 'finalize'); // Утвердить
  const canRevise = hasLabReportAction(activeInstance, 'revise');
  const canPrint = hasLabReportAction(activeInstance, 'print');

  // WF-10 fix: inline-валидация required fields. Раньше валидация происходила
  // только на backend при finalize → late feedback (error toast со списком).
  // Теперь вычисляем missing required fields на frontend и:
  //   - disable кнопку Finalize пока есть незаполненные обязательные поля
  //   - показываем tooltip со списком missing полей
  const missingRequiredFields = useMemo(() => {
    if (!activeInstance?.sections) return [];
    const missing = [];
    activeInstance.sections.forEach((section) => {
      (section.fields || []).forEach((field) => {
        if (field.required) {
          const value = draftValues[field.field_key];
          if (value === undefined || value === '' || value === null) {
            missing.push(field.label || field.field_key);
          }
        }
      });
    });
    return missing;
  }, [activeInstance, draftValues]);
  const hasMissingRequired = missingRequiredFields.length > 0;
  // Finalize disabled если есть missing required fields (даже если backend
  // разрешает action — лучше предотвратить, чем получить 400 error).
  const canFinalizeWithValidation = canFinalize && !hasMissingRequired;

  const handleCreateInstance = useCallback(async (templateIdOverride = null, options = {}) => {
    const templateId = templateIdOverride || selectedTemplateId;
    if (!selectedAppointment?.patient_id || !templateId) {
      notify('error', 'Выберите запись и шаблон.');
      return;
    }
    if (resolutionHasBlockingGap) {
      notify('error', 'Для выбранных услуг нет настроенного лабораторного отчёта. Добавьте mapping service_code -> template.');
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
        // WF-11 fix: при escape hatch не передаём service_codes —
        // бланк создаётся без привязки к услугам визита.
        service_codes: escapeHatchActive ? [] : (templateResolution?.service_codes || selectedAppointment.service_codes || []),
        service_items: escapeHatchActive ? [] : (selectedAppointment.service_details || []).map((item) => ({
          service_id: item.id || null,
          code: item.code || null,
          name: item.name || null
        }))
      });
      onInstanceChange(instance);
      await onRefreshHistory(selectedAppointment.patient_id);
      await onRefreshRecentReports?.();
      await onQueueChanged?.();
      notify('success', options.successMessage || 'Новый лабораторный отчёт создан.');
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
    escapeHatchActive,
    selectedAppointment,
    selectedTemplateId,
    templateResolution
  ]);

  useEffect(() => {
    if (!activeInstance) {
      setDraftValues({});
      setSignerSnapshot({});
      setPrintFeedback(null);
      initialValuesRef.current = { values: {}, signer: {} };
      // WF-11 fix: сбрасываем escape hatch при смене/закрытии instance
      setEscapeHatchActive(false);
      return;
    }
    // WF-12 fix: сбрасываем printFeedback при смене activeInstance,
    // иначе лаборант видит stale success-сообщение от печати предыдущего
    // бланка. useEffect зависит от activeInstance.id, не от объекта —
    // поэтому сработает именно при смене instance, а не при любом re-render.
    setPrintFeedback(null);
    const values = {};
    activeInstance.sections.forEach((section) => {
      section.fields.forEach((field) => {
        values[field.field_key] = extractFieldValue(field);
      });
    });
    setDraftValues(values);
    setSignerSnapshot(activeInstance.signer_snapshot || {});
    setSelectedTemplateId(String(activeInstance.template_id));
    // Dirty state: сохраняем snapshot загруженных значений как "чистых".
    // isDirty будет true только если пользователь изменит что-то после этого.
    initialValuesRef.current = {
      values: { ...values },
      signer: { ...(activeInstance.signer_snapshot || {}) },
    };
  }, [activeInstance]);

  // WF-22 fix: keyboard shortcuts для efficiency.
  // Ctrl+S (Cmd+S на Mac) → save draft (preventDefault — браузер не показывает Save Dialog)
  // Доступно только когда canSaveDraft (editable state).
  const handleSaveDraftRef = useRef(null);
  useEffect(() => {
    if (!canSaveDraft) return;
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (!saving && handleSaveDraftRef.current) {
          handleSaveDraftRef.current();
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [canSaveDraft, saving]);

  useEffect(() => {
    if (activeInstance || !selectedAppointment) {
      return;
    }
    const defaultTemplateId =
      templateResolution?.default_template?.id
      || (!serviceContextPresent ? effectiveTemplateOptions[0]?.id : '')
      || '';
    setSelectedTemplateId((current) => {
      if (current && effectiveTemplateOptions.some((template) => String(template.id) === String(current))) {
        return current;
      }
      return defaultTemplateId ? String(defaultTemplateId) : '';
    });
  }, [
    activeInstance,
    selectedAppointment,
    serviceContextPresent,
    effectiveTemplateOptions,
    templateResolution?.default_template?.id
  ]);

  function updateField(fieldKey, value) {
    setDraftValues((prev) => ({ ...prev, [fieldKey]: value }));
  }

  async function persistDraft() {
    if (!activeInstance) {
      return null;
    }
    // WF-06 fix: передаём updated_at для optimistic locking.
    // Если backend обнаружит, что бланк был изменён другим пользователем
    // после этого timestamp — вернёт 409, persistDraft выбросит exception.
    const expectedUpdatedAt = activeInstance.updated_at
      ? new Date(activeInstance.updated_at).toISOString()
      : null;

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
      }, expectedUpdatedAt);
    }
    if (payload.length > 0) {
      const response = await labReportingApi.bulkSaveValues(activeInstance.id, payload, expectedUpdatedAt);
      latestInstance = response.instance;
    }
    onInstanceChange(latestInstance);
    return latestInstance;
  }

  async function handleSaveDraft() {
    if (!activeInstance) {
      notify('error', 'Сначала создайте или откройте отчёт.');
      return;
    }
    // WF-07 fix: запоминаем статус до save, чтобы обнаружить auto-transition.
    const previousStatus = activeInstance.status;
    setSaving(true);
    setBusyAction('save');
    try {
      const latest = await persistDraft();
      await onRefreshHistory(activeInstance.patient_id);
      // Dirty state: после успешного save сбрасываем dirty flag.
      initialValuesRef.current = {
        values: { ...draftValues },
        signer: { ...signerSnapshot },
      };
      const newStatus = latest?.status || previousStatus;
      if (previousStatus === 'DRAFT' && newStatus === 'IN_PROGRESS') {
        notify('info', 'Черновик сохранён. Статус изменён на «Заполняется» — отчёт теперь в работе.');
      } else {
        notify('success', 'Черновик сохранён.');
      }
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
      setBusyAction('');
    }
  }
  // WF-22 fix: обновляем ref для keyboard shortcut.
  handleSaveDraftRef.current = handleSaveDraft;

  // WF-round5: handleMarkReady убран — Mark Ready был функционально пустой
  // операцией (backend разрешал одинаковые действия для DRAFT/IN_PROGRESS/READY).

  async function handleFinalize() {
    if (!activeInstance) return;
    // WF-08 fix: Finalize — необратимое действие. Бланк становится immutable,
    // единственный путь правки — revise (создание нового instance).
    // Показываем confirmation dialog с объяснением последствий.
    const ok = await confirm({
      title: 'Утверждение отчёта',
      message: 'После утверждения отчёт становится неизменяемым.',
      description: 'Редактирование полей и подписей будет заблокировано. ' +
        'Для исправления потребуется создать исправленную версию. ' +
        'Действие нельзя отменить.',
      confirmLabel: 'Утвердить',
      cancelLabel: 'Отмена',
      intent: 'primary',
    });
    if (!ok) return;
    setSaving(true);
    setBusyAction('finalize');
    try {
      const latest = await persistDraft();
      const finalized = await labReportingApi.finalize((latest || activeInstance).id);
      onInstanceChange(finalized);
      await onRefreshHistory(finalized.patient_id);
      await onRefreshRecentReports?.();
      await onQueueChanged?.();
      notify('success', 'Отчёт утверждён.');
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
      notify('success', 'Создана исправленная версия отчёта.');
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
      text: 'Отправляю лабораторный отчёт на печать...'
    });
    try {
      notify('info', 'Пытаюсь отправить отчёт на принтер...');

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
          text: `Лабораторный отчёт отправлен на печать${printResult.data?.printer ? ` (${printResult.data.printer})` : ''}.`
        });
        notify(
          'success',
          `Лабораторный отчёт отправлен на печать${printResult.data?.printer ? ` (${printResult.data.printer})` : ''}.`
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
      // WF-05 fix: не помечаем как PRINTED при неудаче popup.
      // Раньше markPrinted вызывался безусловно → false audit trail:
      // статус PRINTED, но PDF не открыт. Теперь:
      //   - popup OK → markPrinted + success feedback
      //   - popup blocked → НЕ markPrinted, warning feedback,
      //     лаборант может retry после разрешения pop-up
      if (popup) {
        const printed = await labReportingApi.markPrinted(activeInstance.id);
        onInstanceChange(printed);
        await onRefreshHistory(printed.patient_id);
        await onRefreshRecentReports?.();
        await onQueueChanged?.();
        setPrintFeedback({
          severity: 'success',
          text: 'PDF открыт в новой вкладке. Статус печати обновлён.'
        });
        notify('success', 'PDF открыт в новой вкладке и статус печати обновлён.');
      } else {
        // PDF сформирован, но не открыт. Статус НЕ меняем.
        setPrintFeedback({
          severity: 'warning',
          text: 'PDF сформирован, но новая вкладка заблокирована. ' +
            'Разрешите pop-up для этого сайта и нажмите «Печать» снова, ' +
            'чтобы обновить статус отчёта.'
        });
        notify('warning', 'PDF сформирован, но вкладка заблокирована. Статус печати не обновлён.');
      }
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
    <div style={{ display: 'grid', gap: 'var(--mac-spacing-4)' }}>
      <Card variant="filled" padding="none">
        <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: 'var(--mac-spacing-4)' }}>
          <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
            <Icon name="doc.text" size={20} />
            Редактор лабораторного отчёта
          </CardTitle>
        </CardHeader>
        <CardContent style={{ padding: 'var(--mac-spacing-4)', background: 'var(--mac-bg-secondary)', display: 'grid', gap: 'var(--mac-spacing-4)' }}>
          {!selectedAppointment && !activeInstance ? (
            <Alert severity="info">
              {recentReports.length > 0
                ? 'Выберите пациента из очереди или откройте уже существующий лабораторный отчёт из списка ниже.'
                : 'Выберите пациента из очереди или откройте уже существующий лабораторный отчёт.'}
            </Alert>
          ) : !activeInstance ? (
            <div style={{ display: 'grid', gap: 'var(--mac-spacing-3)' }}>
              <div style={{ color: 'var(--mac-text-secondary)' }}>
                Пациент: <strong style={{ color: 'var(--mac-text-primary)' }}>{selectedAppointment?.patient_fio}</strong>
              </div>
              {serviceContextItems.length > 0 && (
                <div style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                  <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-base)' }}>
                    Услуги визита
                  </div>
                  <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap' }}>
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
                <Alert severity="info">Подбираю доступные отчёты для выбранного визита...</Alert>
              )}
              {!templateResolutionLoading && templateResolution?.default_template && (
                <Alert severity="info">
                  Рекомендуемый отчёт: <strong>{templateResolution.default_template.name}</strong>
                </Alert>
              )}
              {!templateResolutionLoading && templateResolution?.unmapped_service_codes?.length > 0 && (
                <Alert severity={resolvedTemplates.length > 0 ? 'warning' : 'error'}>
                  Ненастроенные услуги визита: {templateResolution.unmapped_service_codes.join(', ')}
                </Alert>
              )}
              {!templateResolutionLoading && resolutionHasBlockingGap && (
                <Alert severity="error">
                  Для выбранного визита не найдено ни одного допустимого отчёта.
                  Настройте mapping услуги к шаблону (требуется роль Admin)
                  или создайте отчёт без привязки к услугам.
                  <div style={{ marginTop: 'var(--mac-spacing-2)' }}>
                    <Button
                      size="small"
                      variant="outline"
                      onClick={() => setEscapeHatchActive(true)}
                    >
                      Показать все шаблоны (без привязки к услугам)
                    </Button>
                  </div>
                </Alert>
              )}
              {/* WF-11 fix: warning когда escape hatch активен */}
              {!templateResolutionLoading && escapeHatchActive && (
                <Alert severity="warning">
                  Создание отчёта без привязки к услугам визита. Убедитесь,
                  что выбрали правильный шаблон — проверка соответствия отключена.
                </Alert>
              )}
              {!templateResolutionLoading && singleAllowedTemplate && !resolutionHasBlockingGap && (
                <Alert severity="info">
                  Единственный допустимый отчёт найден: <strong>{singleAllowedTemplate.name}</strong>. Нажмите «Создать отчёт», чтобы открыть его для заполнения.
                </Alert>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 'var(--mac-spacing-3)', alignItems: 'end' }}>
                <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                  <span>{serviceContextPresent && !escapeHatchActive ? 'Допустимый отчёт' : 'Шаблон отчёта'}</span>
                  <select
                    className="macos-input"
                    value={selectedTemplateId}
                    onChange={(event) => setSelectedTemplateId(event.target.value)}
                    disabled={templateResolutionLoading || (resolutionHasBlockingGap && !escapeHatchActive)}
                  >
                    <option value="">Выберите шаблон</option>
                    {effectiveTemplateOptions.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.name} ({template.family})
                      </option>
                    ))}
                  </select>
                </label>
                <Button
                  variant="primary"
                  onClick={() => handleCreateInstance()}
                  disabled={saving || templateResolutionLoading || (resolutionHasBlockingGap && !escapeHatchActive) || !selectedTemplateId}
                >
                  <Icon name="plus.rectangle.on.folder" size={16} />
                  {busyAction === 'create' ? 'Создаю...' : 'Создать отчёт'}
                </Button>
              </div>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 'var(--mac-spacing-4)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--mac-spacing-4)', alignItems: 'center', flexWrap: 'wrap' }}>
                <div style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                  <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', alignItems: 'center', flexWrap: 'wrap' }}>
                    <div style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                      {activeInstance.patient_snapshot?.full_name || `Пациент #${activeInstance.patient_id}`}
                    </div>
                    <Badge variant={getLabStatusVariant(activeInstance.status)}>{formatLabStatus(activeInstance.status)}</Badge>
                    <Badge variant="info">{activeInstance.template?.name}</Badge>
                  </div>
                  <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-base)' }}>
                    Визит: {activeInstance.visit_id || 'без визита'} | Отчёт #{activeInstance.id}
                    {/* WF-04 fix: показываем supersedes relationship для audit trail.
                        Если этот отчёт — ревизия другого, лаборант видит связь.
                        Backend поле: supersedes_instance_id (см. lab_reporting_service.py:785). */}
                    {activeInstance.supersedes_instance_id && (
                      <span style={{ marginLeft: 'var(--mac-spacing-2)', color: 'var(--mac-accent)' }}>
                        ← исправленная версия отчёта #{activeInstance.supersedes_instance_id}
                      </span>
                    )}
                  </div>
                  {/* P-20 fix: визуальный stepper жизненного цикла бланка.
                      Показывает текущую фазу и будущие шаги. */}
                  <LabStatusStepper status={activeInstance.status} />
                </div>

                {/* P-04 fix: панель действий вынесена в LabReportActionsBar */}
                <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap', alignItems: 'center' }}>
                  <LabReportActionsBar
                    saving={saving}
                    busyAction={busyAction}
                    canSaveDraft={canSaveDraft}
                    // WF-10 fix: Finalize disabled пока есть missing required fields.
                    canFinalize={canFinalizeWithValidation}
                    canRevise={canRevise}
                    canPrint={canPrint}
                    onSaveDraft={handleSaveDraft}
                    onFinalize={handleFinalize}
                    onRevise={handleRevise}
                    onPrint={handlePrint}
                  />
                  {/* WF-10 fix: inline-индикатор missing required fields.
                      Показываем сколько обязательных полей ещё не заполнено,
                      чтобы лаборант понимал, почему Finalize disabled. */}
                  {canFinalize && hasMissingRequired && (
                    <span style={{
                      fontSize: 'var(--mac-font-size-xs)',
                      color: 'var(--mac-accent-orange, #c2410c)',
                      marginLeft: 'var(--mac-spacing-2)',
                    }}>
                      Не заполнено обязательных полей: {missingRequiredFields.length}
                    </span>
                  )}
                  {/* Dirty state indicator: показываем, что есть несохранённые
                      изменения. Предотвращает потерю данных при переключении. */}
                  {isDirty && canEditActiveInstance && (
                    <span style={{
                      fontSize: 'var(--mac-font-size-xs)',
                      color: 'var(--mac-accent-orange, #c2410c)',
                      marginLeft: 'var(--mac-spacing-2)',
                      fontWeight: 'var(--mac-font-weight-medium)',
                    }}>
                      ● несохранённые изменения
                    </span>
                  )}
                  {/* P-01 fix: AI-анализ бланка. Перенесён из LabResultsManager
                      с сохранением P-02 fix (блокировка при отсутствии возраста/пола).
                      Использует patient_snapshot из activeInstance — отдельный
                      запрос GET /patients/{id} не нужен. */}
                  <LabReportAIAnalysis
                    activeInstance={activeInstance}
                    notify={notify}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--mac-spacing-3)' }}>
                {['lab_technician_label', 'lab_technician_name', 'approver_label', 'approver_name'].map((key) => (
                  <label key={key} style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                    <span>{signerFieldLabels[key] || key}</span>
                    <Input
                      className="macos-input"
                      aria-label={signerFieldLabels[key] || key}
                      value={signerSnapshot?.[key] || ''}
                      onChange={(event) => setSignerSnapshot((prev) => ({ ...prev, [key]: event.target.value }))}
                      // WF-09 fix: signer fields должны блокироваться на FINALIZED/PRINTED,
                      // иначе persistDraft вызовет updateInstance → 409 Conflict (silent failure).
                      disabled={!canEditActiveInstance}
                    />
                  </label>
                ))}
              </div>

              {printFeedback && (
                <Alert severity={printFeedback.severity}>{printFeedback.text}</Alert>
              )}

              {activeInstance.critical_findings?.length > 0 && (
                <Alert severity="error">
                  <div style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                    <strong>Критические результаты</strong>
                    {activeInstance.critical_findings.map((finding) => (
                      <div
                        key={`${finding.section_key}-${finding.field_key}`}
                        style={{
                          display: 'grid',
                          gridTemplateColumns: 'minmax(180px, 1.4fr) minmax(110px, 0.7fr) minmax(110px, 0.7fr) minmax(100px, 0.6fr)',
                          gap: 'var(--mac-spacing-2)',
                          alignItems: 'center'
                        }}
                      >
                        <div style={{ display: 'grid', gap: 'var(--mac-spacing-1)' }}>
                          <strong>{finding.label}</strong>
                          <span style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>
                            {finding.section_title || finding.section_key}
                          </span>
                        </div>
                        <div>
                          {finding.value_display}
                          {finding.unit ? ` ${finding.unit}` : ''}
                        </div>
                        <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>
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

              <div style={{ display: 'grid', gap: 'var(--mac-spacing-4)' }}>
                {activeInstance.sections.map((section) => (
                  <div key={section.key} style={{ border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-xl)', overflow: 'hidden', background: 'var(--mac-bg-primary)' }}>
                    <div style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', background: 'var(--mac-bg-tertiary)', fontWeight: 'var(--mac-font-weight-semibold)' }}>
                      {section.title || section.key}
                    </div>
                    <div style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', display: 'grid', gap: '10px' }}>
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
                              gap: 'var(--mac-spacing-2)',
                              alignItems: 'center'
                            }}
                          >
                            <div style={{ display: 'grid', gap: 'var(--mac-spacing-1)' }}>
                              <strong style={{ color: 'var(--mac-text-primary)' }}>{field.label}</strong>
                              <div style={{ display: 'grid', gap: 'var(--mac-spacing-1)', color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-xs)' }}>
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
                              <Input
                                className="macos-input"
                                aria-label={`Lab result for ${field.label}`}
                                value={currentValue}
                                onChange={(event) => updateField(field.field_key, event.target.value)}
                                disabled={!canEditActiveInstance}
                              />
                            )}
                            <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
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
      {/* WF-08 fix: portal-mounted ConfirmDialog для irreversible actions */}
      {confirmDialog}
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
