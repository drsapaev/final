import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { toast } from 'react-toastify';  // STRAT#2: retained for backward-compat;
// новые callers должны использовать useLabToast.interactive* вместо прямого toast.
import {
  Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Icon,
  Input } from '../ui/macos';
import { labReportingApi } from '../../api/labReporting';
import { api } from '../../api/client';
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
// STRAT#1: state-логика вынесена в useLabReportState hook.
// Компонент теперь содержит только handlers + JSX. Это уменьшает
// god-компонент на ~200 строк и изолирует state для тестирования.
import { useLabReportState } from './hooks/useLabReportState';
// STRAT#2: единый хук для нотификаций. Простые messages идут через notify
// callback (parent inline Alert), interactive toasts (с onClick undo) —
// через toast.* напрямую. Соответствует Nielsen Heuristic #4.
import { useLabToast } from './hooks/useLabToast';

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

  // STRAT#2: единый канал нотификаций.
  const labToast = useLabToast(notify);

  // STRAT#1: state declarations + derived memos + init effects
  // теперь в useLabReportState hook (hooks/useLabReportState.js).
  const {
    selectedTemplateId,
    setSelectedTemplateId,
    draftValues,
    setDraftValues,
    signerSnapshot,
    setSignerSnapshot,
    collapsedSections,
    setCollapsedSections,
    saving,
    setSaving,
    busyAction,
    setBusyAction,
    printFeedback,
    setPrintFeedback,
    historySeverityFilter,
    setHistorySeverityFilter,
    escapeHatchActive,
    setEscapeHatchActive,
    lastAutoSave,
    setLastAutoSave,
    autoSaving,
    setAutoSaving,
    initialValuesRef,
    autoSaveTimerRef,
    handleSaveDraftRef,
    isDirty,
    publishedTemplates,
    serviceContextItems,
    resolvedTemplates,
    serviceContextPresent,
    templateOptions,
    effectiveTemplateOptions,
    resolutionHasBlockingGap,
    singleAllowedTemplate,
    showRecentReportsBrowser,
    canEditActiveInstance,
    canSaveDraft,
    canFinalize,
    canRevise,
    canPrint,
    missingRequiredFields,
    hasMissingRequired,
    canFinalizeWithValidation,
  } = useLabReportState({
    selectedAppointment,
    templates,
    templateResolution,
    activeInstance,
  });

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

  // WF-22 fix: keyboard shortcuts для efficiency.
  // Ctrl+S (Cmd+S на Mac) → save draft (preventDefault — браузер не показывает Save Dialog)
  // Доступно только когда canSaveDraft (editable state).
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

  // PR-58: autosave — 30-second debounce when dirty + canSaveDraft
  // L-L-6 fix: добавлен autoSaving state — отображается в индикаторе
  // во время сохранения (а не только после успешного завершения).
  useEffect(() => {
    if (!isDirty || !canSaveDraft || saving) return;
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    autoSaveTimerRef.current = setTimeout(async () => {
      if (handleSaveDraftRef.current && !saving) {
        try {
          setAutoSaving(true);
          await handleSaveDraftRef.current();
          setLastAutoSave(new Date());
        } catch (e) {
          // Autosave failure is non-fatal — manual save is still available
          logger.warn('Lab autosave failed:', e);
        } finally {
          setAutoSaving(false);
        }
      }
    }, 30000); // 30 seconds
    return () => {
      if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    };
  }, [isDirty, canSaveDraft, saving, draftValues]);

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

  // STRAT#1: init-instance effect, default-template effect, keyboard-shortcut
  // effect и autosave effect — все вынесены в useLabReportState hook.
  // Здесь остались только handlers, которые зависят от notify/onInstanceChange
  // (их нельзя изолировать в хук без прокидания через args).

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
          // PR-65 / Medium-15: per-field comment from draftValues
          comment: draftValues[`${field.field_key}__comment`] || null
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
  // L-L-4 fix: присваивание перенесено в useEffect (было при каждом render,
  // что может вызывать stale-closure проблемы в race conditions).
  // Намеренно без deps array — обновляем ref на каждом render (дешёвая операция).
  useEffect(() => {
    handleSaveDraftRef.current = handleSaveDraft;
  });

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
    // M-1 fix: Revise creates a new instance (old one preserved as FINALIZED),
    // but it changes which instance is "active" and creates audit-trail entries.
    // The comment at L52-55 promised a guard — now delivered.
    const ok = await confirm({
      title: 'Создание исправленной версии',
      message: 'Будет создана новая версия отчёта на основе утверждённой.',
      description: 'Старая версия останется в истории как утверждённая. ' +
        'Новая версия станет активной и доступной для редактирования. ' +
        'Это действие создаёт запись в аудите.',
      confirmLabel: 'Создать версию',
      cancelLabel: 'Отмена',
      intent: 'warning',
    });
    if (!ok) return;
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
    // L-5 fix: use setPrintFeedback (inline Alert) as the single feedback
    // channel. Previously handlePrint called notify() up to 5 times per
    // print attempt, producing stacked toasts alongside the inline Alert.
    setPrintFeedback({
      severity: 'info',
      text: 'Отправляю лабораторный отчёт на печать...'
    });
    try {
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
        // PR-59: auto-dismiss success feedback after 5 seconds
        setTimeout(() => setPrintFeedback(null), 5000);
        return;
      }

      logger.warn('[LabReportWorkbench] direct lab print failed, falling back to PDF', {
        instanceId: activeInstance.id,
        error: printResult.error
      });

      // L-M-9 fix: проверяем что blob-запрос успешен перед window.open.
      // Раньше если downloadPdf упадёт с 500, переменная blob будет undefined,
      // URL.createObjectURL(undefined) выбросит, и labourant увидит белый экран.
      let blob;
      try {
        blob = await labReportingApi.downloadPdf(activeInstance.id);
      } catch (downloadError) {
        logger.error('[LabReportWorkbench] PDF download failed', downloadError);
        setPrintFeedback({
          severity: 'error',
          text: 'Не удалось сформировать PDF. Проверьте соединение и попробуйте снова.'
        });
        notify('error', downloadError.message || 'Не удалось сформировать PDF.');
        return;
      }
      if (!blob || !(blob instanceof Blob)) {
        // L-M-9 fix: если blob пустой или не Blob — не открываем window.open('undefined')
        setPrintFeedback({
          severity: 'error',
          text: 'PDF сформирован некорректно. Обратитесь к администратору.'
        });
        return;
      }
      const url = URL.createObjectURL(blob);
      const popup = window.open(url, '_blank', 'noopener,noreferrer');
      // WF-05 fix: не помечаем как PRINTED при неудаче popup.
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
      } else {
        setPrintFeedback({
          severity: 'warning',
          text: 'PDF сформирован, но новая вкладка заблокирована. ' +
            'Разрешите pop-up для этого сайта и нажмите «Печать» снова, ' +
            'чтобы обновить статус отчёта.'
        });
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

  // P1 fix: Notify patient via Telegram — sends lab results PDF to patient's
  // Telegram chat via POST /telegram/send-lab-results backend endpoint.
  //
  // UX-AUDIT-QW1: Добавлен ConfirmDialog. Отправка в Telegram необратима
  // (нельзя отозвать сообщение). Соответствие Nielsen Heuristic #5
  // (Error Prevention) и консистентность с handleFinalize/handleRevise,
  // которые уже используют useConfirm() для необратимых действий.
  async function handleNotifyPatient() {
    if (!activeInstance) return;
    const ok = await confirm({
      title: 'Отправка результатов пациенту',
      message: 'Результаты будут отправлены в Telegram.',
      description:
        'Сообщение нельзя отозвать. Пациент получит PDF с результатами ' +
        'лабораторных анализов. Перед отправкой убедитесь, что отчёт ' +
        'утверждён и не содержит ошибок.',
      confirmLabel: 'Отправить',
      cancelLabel: 'Отмена',
      intent: 'warning',
    });
    if (!ok) return;
    setSaving(true);
    setBusyAction('notify');
    try {
      const patientId = activeInstance.patient_id;
      await api.post('/telegram/send-lab-results', {
        patient_id: patientId,
        instance_id: activeInstance.id,
      });
      notify('success', 'Результаты отправлены пациенту через Telegram.');
    } catch (error) {
      const msg = error?.response?.data?.detail || error?.message || 'Не удалось отправить результаты пациенту.';
      notify('error', typeof msg === 'string' ? msg : 'Не удалось отправить результаты пациенту.');
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
                    {/* PR-60 / Low-31: supersedes link now clickable — navigates to original instance */}
                    {activeInstance.supersedes_instance_id && (
                      <button
                        type="button"
                        onClick={() => {
                          // PR-60 / Low-31: navigate to the superseded instance
                          if (onInstanceChange && activeInstance.supersedes_instance_id) {
                            labReportingApi.getInstance(activeInstance.supersedes_instance_id)
                              .then((instance) => onInstanceChange(instance))
                              .catch((e) => logger.warn('Failed to load superseded instance:', e));
                          }
                        }}
                        style={{
                          marginLeft: 'var(--mac-spacing-2)',
                          color: 'var(--mac-accent)',
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          fontSize: 'inherit',
                          textDecoration: 'underline',
                          padding: 0,
                        }}
                      >
                        ← исправленная версия отчёта #{activeInstance.supersedes_instance_id}
                      </button>
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
                    // P1 fix: Notify patient — only for finalized/printed reports.
                    canNotify={activeInstance?.status === 'FINALIZED' || activeInstance?.status === 'PRINTED'}
                    onSaveDraft={handleSaveDraft}
                    onFinalize={handleFinalize}
                    onRevise={handleRevise}
                    onPrint={handlePrint}
                    onNotify={handleNotifyPatient}
                  />
                  {/* WF-10 fix: inline-индикатор missing required fields.
                      Показываем сколько обязательных полей ещё не заполнено,
                      чтобы лаборант понимал, почему Finalize disabled. */}
                  {/* PR-66 / Low-27: replaced plain text spans with Badge components */}
                  {canFinalize && hasMissingRequired && (
                    <Badge variant="warning" style={{ marginLeft: 'var(--mac-spacing-2)' }}>
                      ⚠ Не заполнено: {missingRequiredFields.length}
                    </Badge>
                  )}
                  {isDirty && canEditActiveInstance && (
                    <Badge variant="warning" style={{ marginLeft: 'var(--mac-spacing-2)' }}>
                      ● несохранённые изменения
                    </Badge>
                  )}
                  {/* PR-58: autosave indicator
                      L-L-6 fix: показываем «сохраняется…» во время autosave.
                      Раньше индикатор пропадал когда labourant начинал печатать,
                      потому что !isDirty скрывало его. Теперь индикатор виден
                      во время активного autosave — feedback не прерывается. */}
                  {autoSaving && (
                    <span
                      style={{
                        fontSize: 'var(--mac-font-size-xs)',
                        color: 'var(--mac-text-tertiary, #6b7280)',
                        marginLeft: 'var(--mac-spacing-2)',
                      }}
                      aria-live="polite"
                    >
                      ◌ сохраняется…
                    </span>
                  )}
                  {!isDirty && !autoSaving && lastAutoSave && (
                    <span style={{
                      fontSize: 'var(--mac-font-size-xs)',
                      color: 'var(--mac-text-tertiary, #6b7280)',
                      marginLeft: 'var(--mac-spacing-2)',
                    }}>
                      ✓ сохранено {lastAutoSave.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                  )}
                  {/* P-01 fix: AI-анализ бланка. Перенесён из LabResultsManager
                      с сохранением P-02 fix (блокировка при отсутствии возраста/пола).
                      Использует patient_snapshot из activeInstance — отдельный
                      запрос GET /patients/{id} не нужен. */}
                  {/* PR-61 / Medium-22: AI button styled as secondary (was visually mixed with operational buttons) */}
                  <span style={{ opacity: 0.85, borderLeft: '1px solid var(--mac-border)', paddingLeft: 'var(--mac-spacing-2)' }}>
                  <LabReportAIAnalysis
                    activeInstance={activeInstance}
                    notify={notify}
                  />
                  </span>
                </div>
              </div>

              {/* UX-AUDIT-FIX8: signer fields свёрнуты в <details>.
                  Ранее 4 поля (lab_technician_label/name, approver_label/name)
                  всегда занимали vertical space, даже в DRAFT, когда подпись
                  ещё не нужна. Это нарушает Nielsen Heuristic #8 (Aesthetic
                  and Minimalist Design). Теперь по умолчанию свернуты;
                  раскрываются одним кликом когда нужны.

                  Auto-expand когда отчёт нередактируем (FINALIZED/PRINTED) —
                  для семантической согласованности (Nielsen Heuristic #2).
                  Используем canEditActiveInstance (backend-owned action)
                  вместо прямой проверки status — соответствует SSOT-контракту. */}
              <details open={!canEditActiveInstance}>
                <summary
                  style={{
                    cursor: 'pointer',
                    fontWeight: 600,
                    color: 'var(--mac-text-secondary)',
                    padding: 'var(--mac-spacing-2) 0',
                    listStyle: 'none',
                  }}
                >
                  Подписи
                  {!canEditActiveInstance && (
                    <span style={{ marginLeft: 'var(--mac-spacing-2)', fontWeight: 400, fontSize: '0.85em', opacity: 0.7 }}>
                      (только для чтения — отчёт утверждён)
                    </span>
                  )}
                </summary>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--mac-spacing-3)', paddingTop: 'var(--mac-spacing-2)' }}>
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
              </details>

              {printFeedback && (
                <Alert severity={printFeedback.severity}>{printFeedback.text}</Alert>
              )}

              {activeInstance.critical_findings?.length > 0 && (
                <Alert severity="error" role="alert">  {/* PR-59: role=alert for screen readers */}
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
                {activeInstance.sections.map((section) => {
                  const isCollapsed = collapsedSections.has(section.key);
                  return (
                  <div key={section.key} style={{ border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-xl)', overflow: 'hidden', background: 'var(--mac-bg-primary)' }}>
                    {/* PR-64 / Medium-16: collapsible section header */}
                    <div
                      style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', background: 'var(--mac-bg-tertiary)', fontWeight: 'var(--mac-font-weight-semibold)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', userSelect: 'none' }}
                      onClick={() => {
                        setCollapsedSections((prev) => {
                          const next = new Set(prev);
                          if (next.has(section.key)) next.delete(section.key);
                          else next.add(section.key);
                          return next;
                        });
                      }}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.currentTarget.click(); } }}
                      aria-expanded={!isCollapsed}
                    >
                      {section.title || section.key}
                      {/* L-M-11 fix: заменены ▶/▼ (CJK punctuation) на lucide chevron icons
                          для консистентности с LabTemplateWorkbench (там уже chevron.down/right). */}
                      <Icon name={isCollapsed ? 'chevron.right' : 'chevron.down'} size={14} />
                    </div>
                    {!isCollapsed && (
                    <div style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', display: 'grid', gap: '10px' }}>
                      {section.fields.map((field) => {
                        const choiceOptions = field.choice_options || [];
                        const currentValue = draftValues[field.field_key] ?? '';
                        // PR-65 / Medium-15: per-field comment
                        const commentKey = `${field.field_key}__comment`;
                        const currentComment = draftValues[commentKey] ?? '';

                        return (
                          <div
                            key={field.field_key}
                            className="lrw-field-row"
                          >
                            <div className="lrw-field-label">
                              <strong className="lrw-field-label-name">{field.label}</strong>
                              <div className="lrw-field-meta">
                                <span>Норма: {field.reference_text || 'не задана'}</span>
                                {field.resolved_flag_meta?.matched_threshold && (
                                  <span>
                                    Порог: {formatThreshold(field.resolved_flag_meta)}
                                    {field.resolved_flag_source ? ` • ${field.resolved_flag_source}` : ''}
                                  </span>
                                )}
                              </div>
                            </div>
                            {/* PR-67 / High-9: previous-result trending — show last value from reportHistory */}
                            {reportHistory.length > 1 && (() => {
                              const prevReport = reportHistory[1]; // [0] = current, [1] = previous
                              if (!prevReport?.sections) return null;
                              let prevValue = null;
                              for (const sec of prevReport.sections) {
                                for (const f of (sec.fields || [])) {
                                  if (f.field_key === field.field_key && f.value_text) {
                                    prevValue = f.value_text;
                                    break;
                                  }
                                }
                                if (prevValue) break;
                              }
                              if (!prevValue) return null;
                              const prevDate = prevReport.created_at ? new Date(prevReport.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) : '';
                              return (
                                <span style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', whiteSpace: 'nowrap' }}>
                                  ↗ {prevValue} {prevDate && `(${prevDate})`}
                                </span>
                              );
                            })()}
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
                                aria-label={`Результат: ${field.label}`}
                                rows={3}
                                value={currentValue}
                                onChange={(event) => updateField(field.field_key, event.target.value)}
                                disabled={!canEditActiveInstance}
                              />
                            ) : (
                              <Input
                                className="macos-input"
                                aria-label={`Результат: ${field.label}`}
                                value={currentValue}
                                onChange={(event) => updateField(field.field_key, event.target.value)}
                                disabled={!canEditActiveInstance}
                                // PR-55: numeric input safety — type=number + inputMode=decimal + validation
                                type={field.value_type === 'numeric' ? 'number' : 'text'}
                                inputMode={field.value_type === 'numeric' ? 'decimal' : undefined}
                                step={field.value_type === 'numeric' ? 'any' : undefined}
                                onBlur={(event) => {
                                  if (field.value_type !== 'numeric') return;
                                  const val = event.target.value;
                                  if (val === '' || val === null || val === undefined) return;
                                  const parsed = parseFloat(val);
                                  if (isNaN(parsed)) {
                                    // L-M-1 fix: undo вместо безвозвратной потери данных.
                                    // Раньше при некорректном numeric-вводе (например, "abc")
                                    // onBlur сбрасывал поле в '' — данные терялись безвозвратно.
                                    // Теперь показываем toast с кнопкой undo, которая
                                    // восстанавливает предыдущее валидное значение.
                                    const previousValue = draftValues[field.field_key] || '';
                                    // STRAT#2: используем labToast.interactiveError вместо
                                    // прямого toast.error — единая точка для future migration.
                                    labToast.interactiveError(
                                      `Некорректное числовое значение: "${val}". Поле возвращено к предыдущему значению.`,
                                      {
                                        autoClose: 6000,
                                        onClick: () => {
                                          updateField(field.field_key, previousValue);
                                        },
                                      }
                                    );
                                    updateField(field.field_key, previousValue);
                                    return;
                                  }
                                  // PR-56: out-of-range confirmation
                                  // Check if value exceeds matched_threshold (critical value)
                                  const threshold = field.resolved_flag_meta?.matched_threshold;
                                  if (threshold && threshold.value) {
                                    const thresholdVal = parseFloat(threshold.value);
                                    if (!isNaN(thresholdVal)) {
                                      const op = threshold.operator;
                                      let isCritical = false;
                                      if (op === 'gt' && parsed > thresholdVal) isCritical = true;
                                      else if (op === 'gte' && parsed >= thresholdVal) isCritical = true;
                                      else if (op === 'lt' && parsed < thresholdVal) isCritical = true;
                                      else if (op === 'lte' && parsed <= thresholdVal) isCritical = true;
                                      if (isCritical) {
                                        // STRAT#2: labToast.interactiveWarning для critical value
                                        labToast.interactiveWarning(
                                          `⚠ Критическое значение: ${field.label} = ${parsed} ${field.unit || ''} ` +
                                          `(порог: ${op} ${thresholdVal}). Проверьте правильность ввода.`,
                                          { autoClose: 8000 }
                                        );
                                      }
                                    }
                                  }
                                  // Check if value is outside reference_text range (e.g., "120-160")
                                  const refText = field.reference_text || '';
                                  const rangeMatch = refText.match(/(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)/);
                                  if (rangeMatch) {
                                    const low = parseFloat(rangeMatch[1]);
                                    const high = parseFloat(rangeMatch[2]);
                                    if (!isNaN(low) && !isNaN(high) && (parsed < low || parsed > high)) {
                                      // STRAT#2: labToast.interactiveInfo для out-of-range
                                      labToast.interactiveInfo(
                                        `Значение ${parsed} вне референсного диапазона (${low}–${high}) для «${field.label}».`,
                                        { autoClose: 5000 }
                                      );
                                    }
                                  }
                                }}
                              />
                            )}
                            <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
                              {field.unit || '—'}
                            </div>
                            <Badge variant={flagVariant(field.resolved_flag, field.resolved_flag_severity)}>
                              {formatFlagLabel(field)}
                            </Badge>
                            {/* PR-60 / Low-32: was <span /> placeholder, now aria-hidden empty cell */}
                            {field.required ? <Badge variant="warning">обязательное</Badge> : <span aria-hidden="true" />}
                            {/* PR-65 / Medium-15: per-field comment input
                                L-M-10 fix: убрана emoji 💬 из placeholder.
                                На macOS emoji рендерится как цветной glyph,
                                что ломает визуальную иерархию input'а. */}
                            <input
                              type="text"
                              className="macos-input"
                              placeholder="комментарий…"
                              value={currentComment}
                              onChange={(e) => updateField(commentKey, e.target.value)}
                              disabled={!canEditActiveInstance}
                              aria-label={`Комментарий к полю: ${field.label}`}
                              style={{
                                fontSize: 'var(--mac-font-size-xs)',
                                padding: '4px 8px',
                                minWidth: '100px',
                                color: 'var(--mac-text-secondary)',
                                fontStyle: currentComment ? 'normal' : 'italic',
                              }}
                            />
                          </div>
                        );
                      })}
                    </div>
                    )}
                  </div>
                  );
                })}
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
