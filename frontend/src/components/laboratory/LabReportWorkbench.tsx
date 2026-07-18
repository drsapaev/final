
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import PropTypes from 'prop-types';
import { toast } from 'react-toastify';  // STRAT#2: retained for backward-compat;
// новые callers должны использовать useLabToast.interactive* вместо прямого toast.
import {
  Alert as RawAlert, Badge as RawBadge, Button as RawButton, Card as RawCard, CardContent, CardHeader, CardTitle, Icon,
  Input as RawInput } from '../ui/macos';
const Alert = RawAlert as unknown as React.ComponentType<Record<string, unknown>>;
const Badge = RawBadge as unknown as React.ComponentType<Record<string, unknown>>;
const Button = RawButton as unknown as React.ComponentType<Record<string, unknown>>;
const Card = RawCard as unknown as React.ComponentType<Record<string, unknown>>;
const Input = RawInput as unknown as React.ComponentType<Record<string, unknown>>;
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
// STRAT#24: sections/fields editor extracted to ReportEditor component.
import ReportEditor from './ReportEditor';
// STRAT#25: supplementary content (AI + history) grouped in ReportSidebar.
import ReportSidebar from './ReportSidebar';
// STRAT#1: state-логика вынесена в useLabReportState hook.
// Компонент теперь содержит только handlers + JSX. Это уменьшает
// god-компонент на ~200 строк и изолирует state для тестирования.
import { useLabReportState } from './hooks/useLabReportState';
// STRAT#2: единый хук для нотификаций. Простые messages идут через notify
// callback (parent inline Alert), interactive toasts (с onClick undo) —
// через toast.* напрямую. Соответствует Nielsen Heuristic #4.
import { useLabToast } from './hooks/useLabToast';
// STRAT#9: t() для i18n — confirm dialogs мигрированы на translation keys.
import { useTranslation } from '../../i18n/useTranslation';

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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // WF-08 fix: confirmation dialog для irreversible actions.
  // Finalize делает бланк immutable (можно только revise). Revise создаёт
  // новый instance. Оба действия необратимы без объяснения последствий.
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;

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

  const handleCreateInstance = useCallback(async (templateIdOverride = null, options: any = {}) => {
    const templateId = templateIdOverride || selectedTemplateId;
    if (!selectedAppointment?.patient_id || !templateId) {
      notify('error', t('errors.select_patient_template'));
      return;
    }
    if (resolutionHasBlockingGap) {
      notify('error', t('errors.no_template_for_services'));
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
      notify('success', options.successMessage || t('success.report_created'));
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
      const response = await labReportingApi.bulkSaveValues(activeInstance.id, payload, expectedUpdatedAt) as any;
      latestInstance = response.instance;
    }
    onInstanceChange(latestInstance);
    return latestInstance;
  }

  async function handleSaveDraft() {
    if (!activeInstance) {
      notify('error', t('errors.open_or_create_first'));
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
        notify('info', t('success.draft_saved_in_progress'));
      } else {
        notify('success', t('success.draft_saved'));
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
    // STRAT#9: строки мигрированы на t() из labTranslations.
    const ok = await confirm({
      title: t('confirm.finalize_title'),
      message: t('confirm.finalize_message'),
      description: t('confirm.finalize_description'),
      confirmLabel: t('confirm.finalize_confirm'),
      cancelLabel: t('confirm.cancel'),
      intent: 'primary',
    });
    if (!ok) return;
    setSaving(true);
    setBusyAction('finalize');
    try {
      const latest = await persistDraft();
      const finalized = await labReportingApi.finalize((latest || activeInstance).id) as any;
      onInstanceChange(finalized);
      await onRefreshHistory(finalized.patient_id);
      await onRefreshRecentReports?.();
      await onQueueChanged?.();
      notify('success', t('success.finalized'));
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
    // STRAT#9: строки мигрированы на t() из labTranslations.
    const ok = await confirm({
      title: t('confirm.revise_title'),
      message: t('confirm.revise_message'),
      description: t('confirm.revise_description'),
      confirmLabel: t('confirm.revise_confirm'),
      cancelLabel: t('confirm.cancel'),
      intent: 'warning',
    });
    if (!ok) return;
    setSaving(true);
    setBusyAction('revise');
    try {
      const revised = await labReportingApi.revise(activeInstance.id) as any;
      onInstanceChange(revised);
      await onRefreshHistory(revised.patient_id);
      await onRefreshRecentReports?.();
      notify('success', t('success.revised'));
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
      text: t('workbench.print_sending')
    });
    try {
      const printResult = await printService.printLabResults(
        buildLabPrintPayload(activeInstance, selectedAppointment)
      ) as any;

      if (printResult.success) {
        const printed = await labReportingApi.markPrinted(activeInstance.id) as any;
        onInstanceChange(printed);
        await onRefreshHistory(printed.patient_id);
        await onRefreshRecentReports?.();
        await onQueueChanged?.();
        setPrintFeedback({
          severity: 'success',
          text: `${t('workbench.print_sent')}${printResult.data?.printer ? ` (${printResult.data.printer})` : ''}.`
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
          text: t('workbench.print_pdf_failed')
        });
        notify('error', downloadError.message || t('errors.print_failed'));
        return;
      }
      if (!blob || !(blob instanceof Blob)) {
        // L-M-9 fix: если blob пустой или не Blob — не открываем window.open('undefined')
        setPrintFeedback({
          severity: 'error',
          text: t('workbench.print_pdf_invalid')
        });
        return;
      }
      const url = URL.createObjectURL(blob);
      const popup = window.open(url, '_blank', 'noopener,noreferrer');
      // WF-05 fix: не помечаем как PRINTED при неудаче popup.
      if (popup) {
        const printed = await labReportingApi.markPrinted(activeInstance.id) as any;
        onInstanceChange(printed);
        await onRefreshHistory(printed.patient_id);
        await onRefreshRecentReports?.();
        await onQueueChanged?.();
        setPrintFeedback({
          severity: 'success',
          text: t('workbench.print_pdf_opened')
        });
      } else {
        setPrintFeedback({
          severity: 'warning',
          text: t('workbench.print_pdf_blocked')
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
    // STRAT#9: строки мигрированы на t() из labTranslations.
    const ok = await confirm({
      title: t('confirm.notify_title'),
      message: t('confirm.notify_message'),
      description: t('confirm.notify_description'),
      confirmLabel: t('confirm.notify_confirm'),
      cancelLabel: t('confirm.cancel'),
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
      notify('success', t('success.notified'));
    } catch (error) {
      const msg = error?.response?.data?.detail || error?.message || 'Не удалось отправить результаты пациенту.';
      notify('error', typeof msg === 'string' ? msg : t('errors.notify_failed'));
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
            <Icon name="doc.text" size={20 as never} />
            {t('workbench.title')}
          </CardTitle>
        </CardHeader>
        <CardContent style={{ padding: 'var(--mac-spacing-4)', background: 'var(--mac-bg-secondary)', display: 'grid', gap: 'var(--mac-spacing-4)' }}>
          {!selectedAppointment && !activeInstance ? (
            <Alert severity="info">
              {recentReports.length > 0
                ? t('workbench.select_patient_prompt')
                : t('workbench.select_patient_short')}
            </Alert>
          ) : !activeInstance ? (
            <div style={{ display: 'grid', gap: 'var(--mac-spacing-3)' }}>
              <div style={{ color: 'var(--mac-text-secondary)' }}>
                {t('workbench.patient_label')}: <strong style={{ color: 'var(--mac-text-primary)' }}>{selectedAppointment?.patient_fio}</strong>
              </div>
              {serviceContextItems.length > 0 && (
                <div style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                  <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-base)' }}>
                    {t('workbench.visit_services')}
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
                <Alert severity="info">{t('workbench.resolving_templates')}</Alert>
              )}
              {!templateResolutionLoading && templateResolution?.default_template && (
                <Alert severity="info">
                  {t('workbench.recommended_report')}: <strong>{templateResolution.default_template.name}</strong>
                </Alert>
              )}
              {!templateResolutionLoading && templateResolution?.unmapped_service_codes?.length > 0 && (
                <Alert severity={resolvedTemplates.length > 0 ? 'warning' : 'error'}>
                  {t('workbench.unmapped_services')}: {templateResolution.unmapped_service_codes.join(', ')}
                </Alert>
              )}
              {!templateResolutionLoading && resolutionHasBlockingGap && (
                <Alert severity="error">
                  {t('workbench.no_template_found')}
                  <br />
                  {t('workbench.no_template_hint')} {t('workbench.no_template_escape')}
                  <div style={{ marginTop: 'var(--mac-spacing-2)' }}>
                    <Button
                      size="small"
                      variant="outline"
                      onClick={() => setEscapeHatchActive(true)}
                    >
                      {t('workbench.show_all_templates')}
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
                  {t('workbench.single_template_found')} <strong>{singleAllowedTemplate.name}</strong>. {t('workbench.click_create_to_open')}
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
                  <Icon name="plus.rectangle.on.folder" size={16 as never} />
                  {busyAction === 'create' ? t('workbench.creating_report') : t('workbench.create_report')}
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
                  {/* STRAT#25: AI analysis moved to ReportSidebar — rendered after the editor card. */}
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

              {/* STRAT#24: sections/fields editor extracted to ReportEditor component */}
              <ReportEditor
                activeInstance={activeInstance}
                draftValues={draftValues}
                collapsedSections={collapsedSections}
                onToggleSection={(sectionKey) => {
                  setCollapsedSections((prev) => {
                    const next = new Set(prev);
                    if (next.has(sectionKey)) next.delete(sectionKey);
                    else next.add(sectionKey);
                    return next;
                  });
                }}
                onUpdateField={updateField}
                canEditActiveInstance={canEditActiveInstance}
                reportHistory={reportHistory}
                notify={notify}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* STRAT#25: supplementary content (AI analysis + history) grouped in ReportSidebar */}
      <ReportSidebar
        activeInstance={activeInstance}
        notify={notify}
        showRecentReportsBrowser={showRecentReportsBrowser}
        recentReports={recentReports}
        reportHistory={reportHistory}
        historySeverityFilter={historySeverityFilter}
        onSeverityFilterChange={setHistorySeverityFilter}
        onOpenInstance={onOpenInstance}
      />
      {/* WF-08 fix: portal-mounted ConfirmDialog для irreversible actions */}
      {confirmDialog as unknown as React.ReactNode}
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
