
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { toast } from 'react-toastify';  // STRAT#2: retained for backward-compat;
// новые callers должны использовать useLabToast.interactive* вместо прямого toast.
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Input } from '../ui/macos';
// ADR-0015: use useLabReporting hook instead of importing api/labReporting directly.
import { useLabReporting } from '../../hooks/useLabReporting';
import { api } from '../../api/client';
import { printService } from '../../services/print';
import logger from '../../utils/logger';
import {
  formatLabStatus,
  getLabStatusVariant,
  signerFieldLabels
} from './labUiLabels';
// PR 3351 (review round 7, P1): split-уровни pending-защиты (см. operationPending.ts).
import type { LabOperationPendingState } from './operationPending';

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
import { getErrorMessage } from '../../utils/type-guards';
import { FileText, FolderPlus } from 'lucide-react';

export interface LabInstanceChangeContext {
  kind: 'update' | 'transition';
  expectedInstanceId: string | number | null;
  operation: LabReportOperationContext;
}

export interface LabReportOperationContext {
  epoch: number;
  selectionKey: string | null;
  patientId: string | number | null;
}

interface PersistDraftResult {
  instance: Record<string, unknown> | null;
  accepted: boolean;
}

class StaleLabReportContextError extends Error {}

const EMPTY_OPERATION_CONTEXT: LabReportOperationContext = {
  epoch: 0,
  selectionKey: null,
  patientId: null,
};

function operationContextsMatch(
  left: LabReportOperationContext,
  right: LabReportOperationContext,
) {
  return left.epoch === right.epoch
    && left.selectionKey === right.selectionKey
    && String(left.patientId ?? '') === String(right.patientId ?? '');
}

export default function LabReportWorkbench({
  selectedAppointment = null,
  templates,
  templateResolution = null,
  templateResolutionLoading = false,
  reportHistory = [],
  recentReports = [],
  activeInstance = null,
  instanceTransitionPending = false,
  pauseAutoSave = false,
  getOperationContext = undefined,
  onInstanceChange,
  onOpenInstance,
  onRefreshHistory,
  onRefreshRecentReports = undefined,
  onQueueChanged = undefined,
  registerDirtySource = undefined,
  onDirtyStateChange = undefined,
  onOperationPendingChange = undefined,
  notify
}: {
  selectedAppointment?: Record<string, unknown> | null;
  templates?: Array<Record<string, unknown>>;
  templateResolution?: Record<string, unknown> | null;
  templateResolutionLoading?: boolean;
  reportHistory?: Array<Record<string, unknown>>;
  recentReports?: Array<Record<string, unknown>>;
  activeInstance?: Record<string, unknown> | null;
  instanceTransitionPending?: boolean;
  pauseAutoSave?: boolean;
  getOperationContext?: () => LabReportOperationContext;
  onInstanceChange?: (
    instance: Record<string, unknown>,
    change: LabInstanceChangeContext,
  ) => boolean | void;
  onOpenInstance?: (instanceId: string | number) => void;
  onRefreshHistory?: (patientId: string | number) => Promise<void>;
  onRefreshRecentReports?: () => Promise<void>;
  onQueueChanged?: () => Promise<void>;
  notify?: (type: string, message: string) => void;
  registerDirtySource?: (source: {
    id: string;
    isDirty: () => boolean;
    save: () => Promise<void>;
    discard?: () => void;
  }) => () => void;
  /** PR 3351: вызывается при каждом изменении dirty-состояния (sentinel route-guard). */
  onDirtyStateChange?: () => void;
  /**
   * PR 3351 (review round 7, P1): split-уровни pending-защиты.
   * blocksContextTransition — контекстные переходы report-области;
   * blocksDocumentLeave — полный уход с /lab (beforeunload/route-leave/
   * sentinel/session-expiry). null (cleanup) снимает источник с обоих
   * уровней.
   */
  onOperationPendingChange?: (state: LabOperationPendingState | null) => void;
  [k: string]: unknown;
}) {
  const { t: rawT } = useTranslation();
  const t = rawT;
  // WF-08 fix: confirmation dialog для irreversible actions.
  // Finalize делает бланк immutable (можно только revise). Revise создаёт
  // новый instance. Оба действия необратимы без объяснения последствий.
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw;
  // ADR-0015: lab reporting API accessed via hook.
  const labReportingApi = useLabReporting();
  const partialDraftCommitRef = useRef<{
    instanceId: string | number;
    baseUpdatedAt: string | null;
    updatedAt: string;
    signerSnapshot: Record<string, unknown>;
  } | null>(null);
  const printAttemptRef = useRef(0);
  const printFeedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const captureOperationContext = useCallback(
    () => getOperationContext?.() ?? EMPTY_OPERATION_CONTEXT,
    [getOperationContext],
  );
  const isOperationCurrent = useCallback(
    (operation: LabReportOperationContext) => operationContextsMatch(
      operation,
      getOperationContext?.() ?? EMPTY_OPERATION_CONTEXT,
    ),
    [getOperationContext],
  );

  // STRAT#2: единый канал нотификаций.
  const labToast = useLabToast(notify as (type: string, message: string) => void);
  // PR6: серверно разрешённое действие «Добавить бланк». Единственный
  // источник разрешения — backend факт templateResolution.allowed_templates
  // (resolve_template_options); React не изобретает список и не прячет
  // шаблоны сам. При несохранённых изменениях действие заблокировано,
  // чтобы переключение на новый бланк не потеряло черновик.
  const [addBlankTemplateId, setAddBlankTemplateId] = useState<string>('');
  const allowedTemplates = ((templateResolution?.allowed_templates ?? []) as Array<Record<string, unknown>>);
  const addBlankTemplateIdValue = addBlankTemplateId || String(allowedTemplates[0]?.id ?? '');

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
    isInstanceHydrated,
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
    selectedAppointment: selectedAppointment as never,
    templates: (templates as never) || [],
    templateResolution: templateResolution as never,
    activeInstance: activeInstance as never,
  });
  const canEditVisibleInstance = canEditActiveInstance
    && isInstanceHydrated
    && !instanceTransitionPending
    && !saving
    && !autoSaving;

  // PR 3351 pending-контракт (review round 7, P1): два независимых уровня.
  // CREATE остаётся latest-wins для КОНТЕКСТНЫХ переходов (поздний ответ
  // отбрасывается по operation-context в handleInstanceChange — смена
  // пациента/отчёта не ждёт POST), но POST /lab/report-instances
  // неидемпотентен: refresh/закрытие вкладки/уход с /lab/истечение сессии
  // поверх летящего create теряли ответ, и оператор после повторного входа
  // создавал второй бланк. Поэтому CREATE (как и save/autosave/finalize/
  // revise/print/notify) блокирует ДОКУМЕНТ/маршрут: beforeunload
  // провайдера, guardRouteLeave, sentinel и session-expiry redirect.
  const reportBlocksContextTransition = (saving && busyAction !== 'create') || autoSaving;
  const reportBlocksDocumentLeave = saving || autoSaving;
  useLayoutEffect(() => {
    onOperationPendingChange?.({
      blocksContextTransition: reportBlocksContextTransition,
      blocksDocumentLeave: reportBlocksDocumentLeave,
    });
    return () => {
      if (reportBlocksContextTransition || reportBlocksDocumentLeave) {
        onOperationPendingChange?.(null);
      }
    };
  }, [onOperationPendingChange, reportBlocksContextTransition, reportBlocksDocumentLeave]);

  useEffect(() => {
    const partial = partialDraftCommitRef.current;
    if (!partial) return;
    const activeId = activeInstance?.id as string | number | null | undefined;
    const activeUpdatedAt = activeInstance?.updated_at == null
      ? null
      : String(activeInstance.updated_at);
    if (
      String(activeId ?? '') !== String(partial.instanceId)
      || activeUpdatedAt !== partial.baseUpdatedAt
    ) {
      partialDraftCommitRef.current = null;
    }
  }, [activeInstance?.id, activeInstance?.updated_at]);

  useEffect(() => {
    if (printFeedbackTimerRef.current) {
      clearTimeout(printFeedbackTimerRef.current);
      printFeedbackTimerRef.current = null;
    }
    return () => {
      if (printFeedbackTimerRef.current) {
        clearTimeout(printFeedbackTimerRef.current);
        printFeedbackTimerRef.current = null;
      }
    };
  }, [activeInstance?.id]);

  // PR 3351 (review round 6, P1): beforeunload для полного документа
  // (refresh/закрытие вкладки) больше не ставится здесь. Единственный
  // владелец — LabDirtyGuardProvider: он видит ОБЩЕЕ состояние
  // (dirty-источники ИЛИ незавершённые операции), поэтому pending-only
  // мутация (finalize/print чистого отчёта) тоже блокирует unload.
  // Workbench-хук на одном isDirty этот сценарий пропускал. Внутренние
  // SPA-переходы по-прежнему идут через guardTransition (scope-контракт).

  // WF-22 fix: keyboard shortcuts для efficiency.
  // Ctrl+S (Cmd+S на Mac) → save draft (preventDefault — браузер не показывает Save Dialog)
  // Доступно только когда canSaveDraft (editable state).
  useEffect(() => {
    if (!canSaveDraft || instanceTransitionPending) return;
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (!saving && handleSaveDraftRef.current) {
          // PR3: attemptSaveDraft бросает исключение при неудаче — показываем
          // ошибку через общий обработчик (включая конфликтный 409-toast).
          void Promise.resolve(handleSaveDraftRef.current()).catch((saveError: unknown) => {
            notifySaveError(saveError);
          });
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [canSaveDraft, instanceTransitionPending, saving]);

  // PR-58: autosave — 30-second debounce when dirty + canSaveDraft
  // L-L-6 fix: добавлен autoSaving state — отображается в индикаторе
  // во время сохранения (а не только после успешного завершения).
  useEffect(() => {
    if (!isDirty || !canSaveDraft || saving || instanceTransitionPending || pauseAutoSave) return;
    const scheduledOperation = captureOperationContext();
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    autoSaveTimerRef.current = setTimeout(async () => {
      if (handleSaveDraftRef.current && !saving) {
        if (!isOperationCurrent(scheduledOperation)) return;
        try {
          setAutoSaving(true);
          const accepted = await handleSaveDraftRef.current();
          if (accepted) {
            setLastAutoSave(new Date());
          }
        } catch (e) {
          // Autosave failure is non-fatal — manual save is still available
          if (!(e instanceof StaleLabReportContextError)) {
            logger.warn('Lab autosave failed:', e);
          }
        } finally {
          setAutoSaving(false);
        }
      }
    }, 30000); // 30 seconds
    return () => {
      if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    };
  }, [
    isDirty,
    canSaveDraft,
    saving,
    draftValues,
    instanceTransitionPending,
    pauseAutoSave,
    captureOperationContext,
    isOperationCurrent,
  ]);

  const handleCreateInstance = useCallback(async (templateIdOverride: string | number | null = null, options: Record<string, unknown> = {}) => {
    if (instanceTransitionPending) return;
    const operation = captureOperationContext();
    const expectedInstanceId = (activeInstance?.id as string | number | null | undefined) ?? null;
    const templateId = templateIdOverride || selectedTemplateId;
    if (!selectedAppointment?.patient_id || !templateId) {
      notify?.('error', t('errors.select_patient_template'));
      return;
    }
    if (resolutionHasBlockingGap) {
      notify?.('error', t('errors.no_template_for_services'));
      return;
    }
    setSaving(true);
    setBusyAction('create');
    try {
      const instance = await labReportingApi.createInstance({
        patient_id: selectedAppointment.patient_id as string | number,
        appointment_id: (selectedAppointment.appointment_id as string | number) || null,
        visit_id: (templateResolution?.visit_id as string | number) || (selectedAppointment.visit_id as string | number) || null,
        template_id: Number(templateId),
        // WF-11 fix: при escape hatch не передаём service_codes —
        // бланк создаётся без привязки к услугам визита.
        service_codes: escapeHatchActive ? [] : ((templateResolution?.service_codes as string[]) || (selectedAppointment.service_codes as string[]) || []),
        service_items: escapeHatchActive ? [] : ((selectedAppointment.service_details as Array<Record<string, unknown>>) || []).map((item: Record<string, unknown>) => ({
          service_id: item.id || null,
          code: item.code || null,
          name: item.name || null
        }))
      });
      const accepted = onInstanceChange?.(instance as Record<string, unknown>, {
        kind: 'transition',
        expectedInstanceId,
        operation,
      }) !== false;
      if (!accepted) return;
      const transitionedOperation = captureOperationContext();
      await onRefreshHistory?.(selectedAppointment.patient_id as string | number);
      if (!isOperationCurrent(transitionedOperation)) return;
      await onRefreshRecentReports?.();
      if (!isOperationCurrent(transitionedOperation)) return;
      await onQueueChanged?.();
      if (!isOperationCurrent(transitionedOperation)) return;
      notify?.('success', (options.successMessage as string) || t('success.report_created'));
    } catch (error) {
      if (!isOperationCurrent(operation)) return;
      notify?.('error', (error instanceof Error ? error.message : String(error)));
    } finally {
      setSaving(false);
      setBusyAction(null);
    }
  }, [
    activeInstance,
    captureOperationContext,
    isOperationCurrent,
    instanceTransitionPending,
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

  function updateField(fieldKey: string, value: unknown) {
    setDraftValues((prev) => ({ ...prev, [fieldKey]: value }));
  }

  async function persistDraft(operation: LabReportOperationContext): Promise<PersistDraftResult> {
    if (!activeInstance) {
      return { instance: null, accepted: false };
    }
    const expectedInstanceId = activeInstance.id as string | number;
    // WF-06 fix: передаём updated_at для optimistic locking.
    // Если backend обнаружит, что бланк был изменён другим пользователем
    // после этого timestamp — вернёт 409, persistDraft выбросит exception.
    const activeUpdatedAt = activeInstance.updated_at
      ? activeInstance.updated_at as string
      : null;
    const cachedPartial = partialDraftCommitRef.current;
    const reusablePartial = cachedPartial
      && String(cachedPartial.instanceId) === String(expectedInstanceId)
      && cachedPartial.baseUpdatedAt === activeUpdatedAt
      ? cachedPartial
      : null;
    if (!reusablePartial && cachedPartial) {
      partialDraftCommitRef.current = null;
    }
    let expectedUpdatedAt = reusablePartial?.updatedAt ?? activeUpdatedAt;

    const payload: Array<Record<string, unknown>> = [];
    (activeInstance.sections as Array<Record<string, unknown>>).forEach((section: Record<string, unknown>) => {
      ((section.fields as Array<Record<string, unknown>>) || []).forEach((field: Record<string, unknown>) => {
        const currentValue = draftValues[field.field_key as string];
        if (currentValue === undefined) {
          return;
        }
        payload.push({
          field_key: field.field_key,
          value_text: currentValue === '' ? null : currentValue,
          value_numeric: field.value_type === 'numeric' && currentValue !== '' ? currentValue : null,
          // PR-65 / Medium-15: per-field comment from draftValues
          comment: draftValues[`${field.field_key as string}__comment`] || null
        });
      });
    });

    let latestInstance: Record<string, unknown> | null = reusablePartial
      ? {
        ...activeInstance,
        updated_at: reusablePartial.updatedAt,
        signer_snapshot: reusablePartial.signerSnapshot,
      }
      : activeInstance;
    const persistedSignerSnapshot = reusablePartial?.signerSnapshot
      ?? (activeInstance.signer_snapshot as Record<string, unknown> | undefined)
      ?? {};
    if (JSON.stringify(persistedSignerSnapshot) !== JSON.stringify(signerSnapshot || {})) {
      latestInstance = await labReportingApi.updateInstance(activeInstance.id as string | number, {
        signer_snapshot: signerSnapshot
      }, expectedUpdatedAt) as Record<string, unknown>;
      // PR3: signer-запрос продвинул updated_at — последующий bulk-запрос
      // обязан использовать token из ответа первого запроса, иначе получит
      // 409 от собственного сохранения.
      const signerUpdatedAt = latestInstance?.updated_at as string | undefined;
      if (signerUpdatedAt) {
        expectedUpdatedAt = signerUpdatedAt;
        partialDraftCommitRef.current = {
          instanceId: expectedInstanceId,
          baseUpdatedAt: reusablePartial?.baseUpdatedAt ?? activeUpdatedAt,
          updatedAt: signerUpdatedAt,
          signerSnapshot: { ...(signerSnapshot || {}) },
        };
      }
      if (!isOperationCurrent(operation)) throw new StaleLabReportContextError();
    }
    if (payload.length > 0) {
      const response = (await labReportingApi.bulkSaveValues(activeInstance.id as string | number, payload, expectedUpdatedAt)) as Record<string, unknown>;
      latestInstance = response.instance as Record<string, unknown>;
      // The server commit is authoritative even if navigation changed while
      // the request was in flight. Cache its advanced token before rejecting
      // stale UI work so a failed target transition can safely retry the still
      // visible report instead of conflicting with our own completed write.
      const committedUpdatedAt = latestInstance?.updated_at as string | undefined;
      if (committedUpdatedAt) {
        partialDraftCommitRef.current = {
          instanceId: expectedInstanceId,
          baseUpdatedAt: reusablePartial?.baseUpdatedAt ?? activeUpdatedAt,
          updatedAt: committedUpdatedAt,
          signerSnapshot: { ...(signerSnapshot || {}) },
        };
      }
      if (!isOperationCurrent(operation)) throw new StaleLabReportContextError();
    }
    const accepted = onInstanceChange?.(latestInstance as Record<string, unknown>, {
      kind: 'update',
      expectedInstanceId,
      operation,
    }) !== false;
    if (accepted && isOperationCurrent(operation)) {
      partialDraftCommitRef.current = null;
    }
    return {
      instance: latestInstance,
      accepted: accepted && isOperationCurrent(operation),
    };
  }

  // PR3: ядро сохранения — бросает исключение при неудаче, чтобы autosave
  // (и любой другой вызывающий) мог достоверно отличить успех от провала
  // и не выставлял lastAutoSave после неуспешного запроса.
  async function attemptSaveDraft(): Promise<boolean> {
    if (!activeInstance || instanceTransitionPending) {
      if (instanceTransitionPending) return false;
      throw new Error(t('errors.open_or_create_first'));
    }
    const operation = captureOperationContext();
    // WF-07 fix: запоминаем статус до save, чтобы обнаружить auto-transition.
    const previousStatus = activeInstance.status;
    setSaving(true);
    setBusyAction('save');
    try {
      const { instance: latest, accepted } = await persistDraft(operation);
      if (!accepted) return false;
      await onRefreshHistory?.(activeInstance.patient_id as string | number);
      if (!isOperationCurrent(operation)) return false;
      // Dirty state: после успешного save сбрасываем dirty flag.
      initialValuesRef.current = {
        instanceId: activeInstance.id as string | number,
        values: { ...draftValues },
        signer: { ...signerSnapshot },
      };
      // PR3: isDirty-мемо кэшируется по draftValues — сброс baseline в ref
      // сам по себе не перерисует бейдж «несохранённые изменения» и
      // индикатор «✓ сохранено». Форсируем перерасчёт новой ссылкой.
      setDraftValues((prev) => ({ ...prev }));
      const newStatus = latest?.status || previousStatus;
      if (previousStatus === 'DRAFT' && newStatus === 'IN_PROGRESS') {
        notify?.('info', t('success.draft_saved_in_progress'));
      } else {
        notify?.('success', t('success.draft_saved'));
      }
      return true;
    } catch (error) {
      if (!isOperationCurrent(operation)) {
        throw new StaleLabReportContextError();
      }
      throw error;
    } finally {
      setSaving(false);
      setBusyAction('');
    }
  }

  // PR3: при 409 optimistic locking показываем локализованное действие
  // «Обновить актуальную версию». Введённый draft НЕ перезаписываем
  // автоматически — актуальная версия открывается только явным кликом.
  function notifySaveError(error: unknown) {
    if (error instanceof StaleLabReportContextError) return;
    const message = error instanceof Error ? error.message : String(error);
    if (message.includes('другим пользователем') && activeInstance) {
      labToast.interactiveError(
        'Бланк изменён другим пользователем. Нажмите здесь, чтобы обновить актуальную версию; ваш черновик не перезаписан.',
        {
          autoClose: 10000,
          onClick: () => {
            void (async () => {
              const operation = captureOperationContext();
              const fresh = await labReportingApi.getInstance(activeInstance.id as string | number);
              if (!isOperationCurrent(operation)) return;
              onInstanceChange?.(fresh as Record<string, unknown>, {
                kind: 'update',
                expectedInstanceId: activeInstance.id as string | number,
                operation,
              });
            })();
          },
        }
      );
      return;
    }
    notify?.('error', message);
  }
  const notifySaveErrorRef = useRef(notifySaveError);
  useEffect(() => {
    notifySaveErrorRef.current = notifySaveError;
  });

  async function handleSaveDraft(): Promise<boolean> {
    try {
      return await attemptSaveDraft();
    } catch (error) {
      notifySaveError(error);
      return false;
    }
  }
  // WF-22 fix: обновляем ref для keyboard shortcut.
  // L-L-4 fix: присваивание перенесено в useEffect (было при каждом render,
  // что может вызывать stale-closure проблемы в race conditions).
  // Намеренно без deps array — обновляем ref на каждом render (дешёвая операция).
  // PR3: ref указывает на attemptSaveDraft (бросает исключение), чтобы
  // autosave достоверно различал успех и провал.
  useEffect(() => {
    handleSaveDraftRef.current = attemptSaveDraft;
  });

  // PR5: регистрация dirty-состояния отчёта в панели — guard переходов
  // решает (сохранить / выйти без сохранения / отмена) по этому источнику.
  const isDirtyRef = useRef(isDirty);
  // PR 3351 (route-level leave guard): обновляемый ref + notify на каждом
  // рендере — route-guard перевзвешивает sentinel при флипе dirty.
  const onDirtyStateChangeRef = useRef(onDirtyStateChange);
  useEffect(() => {
    onDirtyStateChangeRef.current = onDirtyStateChange;
  });
  useEffect(() => {
    isDirtyRef.current = isDirty;
    onDirtyStateChangeRef.current?.();
  });
  const registerDirtySourceRef = useRef(registerDirtySource);
  useEffect(() => {
    if (!registerDirtySourceRef.current) return;
    return registerDirtySourceRef.current({
      id: 'report',
      isDirty: () => isDirtyRef.current,
      save: async () => {
        try {
          const accepted = await handleSaveDraftRef.current?.();
          if (accepted === false) {
            throw new StaleLabReportContextError();
          }
        } catch (error) {
          // Dirty-transition guard intentionally swallows save failures so the
          // source must surface the error before rethrowing to block navigation.
          if (!(error instanceof StaleLabReportContextError)) {
            notifySaveErrorRef.current(error);
          }
          throw error;
        }
      },
      // PR 3351: Discard сбрасывает черновик к baseline активного
      // instance. Выбор необратим: если переход упадёт (загрузка новой
      // цели завершилась ошибкой), сброшенный draft не останется dirty и
      // не будет закоммичен autosave от старого контекста.
      discard: () => {
        const baseline = initialValuesRef.current;
        setDraftValues({ ...baseline.values });
        setSignerSnapshot({ ...baseline.signer });
      },
    });
  }, []);

  // WF-round5: handleMarkReady убран — Mark Ready был функционально пустой
  // операцией (backend разрешал одинаковые действия для DRAFT/IN_PROGRESS/READY).

  async function handleFinalize() {
    if (!activeInstance || instanceTransitionPending) return;
    const expectedInstanceId = activeInstance.id as string | number;
    const operation = captureOperationContext();
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
    if (!isOperationCurrent(operation)) return;
    setSaving(true);
    setBusyAction('finalize');
    try {
      const { instance: latest, accepted: draftAccepted } = await persistDraft(operation);
      if (!draftAccepted || !isOperationCurrent(operation)) return;
      const finalized = await labReportingApi.finalize(((latest || activeInstance) as Record<string, unknown>).id as string | number) as Record<string, unknown>;
      const accepted = onInstanceChange?.(finalized, {
        kind: 'update',
        expectedInstanceId,
        operation,
      }) !== false;
      if (!accepted || !isOperationCurrent(operation)) return;
      await onRefreshHistory?.(finalized.patient_id as string | number);
      if (!isOperationCurrent(operation)) return;
      await onRefreshRecentReports?.();
      if (!isOperationCurrent(operation)) return;
      await onQueueChanged?.();
      if (!isOperationCurrent(operation)) return;
      notify?.('success', t('success.finalized'));
    } catch (error) {
      if (!isOperationCurrent(operation)) return;
      // PR3: конфликт 409 при финализации показывает действие
      // «Обновить актуальную версию» вместо сырой ошибки.
      notifySaveError(error);
    } finally {
      setSaving(false);
      setBusyAction('');
    }
  }

  async function handleRevise() {
    if (!activeInstance || instanceTransitionPending) return;
    const expectedInstanceId = activeInstance.id as string | number;
    const operation = captureOperationContext();
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
    if (!isOperationCurrent(operation)) return;
    setSaving(true);
    setBusyAction('revise');
    try {
      const revised = (await labReportingApi.revise(activeInstance.id as string | number)) as Record<string, unknown>;
      const accepted = onInstanceChange?.(revised, {
        kind: 'transition',
        expectedInstanceId,
        operation,
      }) !== false;
      if (!accepted) return;
      const transitionedOperation = captureOperationContext();
      await onRefreshHistory?.(revised.patient_id as string | number);
      if (!isOperationCurrent(transitionedOperation)) return;
      await onRefreshRecentReports?.();
      if (!isOperationCurrent(transitionedOperation)) return;
      notify?.('success', t('success.revised'));
    } catch (error) {
      if (!isOperationCurrent(operation)) return;
      // PR3: конфликт 409 при revise показывает действие
      // «Обновить актуальную версию» вместо сырой ошибки.
      notifySaveError(error);
    } finally {
      setSaving(false);
      setBusyAction('');
    }
  }

  async function handlePrint() {
    if (!activeInstance || instanceTransitionPending) return;
    const printAttempt = ++printAttemptRef.current;
    if (printFeedbackTimerRef.current) {
      clearTimeout(printFeedbackTimerRef.current);
      printFeedbackTimerRef.current = null;
    }
    const clearOwnedPrintFeedback = () => {
      if (printAttemptRef.current === printAttempt) setPrintFeedback(null);
    };
    const operation = captureOperationContext();
    const expectedInstanceId = activeInstance.id as string | number;
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
      ) as Record<string, unknown>;

      if (printResult.success) {
        let printed: Record<string, unknown>;
        try {
          printed = (await labReportingApi.markPrinted(expectedInstanceId)) as Record<string, unknown>;
        } catch (markError) {
          logger.error('[LabReportWorkbench] printed document status update failed', markError);
          if (isOperationCurrent(operation) && printAttemptRef.current === printAttempt) {
            setPrintFeedback({ severity: 'error', text: t('workbench.print_status_failed') });
          }
          notify?.('error', t('workbench.print_status_failed'));
          return;
        }
        // The physical print already happened, so persist its audit/status even
        // if the operator navigated away while the printer request was pending.
        // Only the old screen's UI follow-ups are suppressed.
        if (!isOperationCurrent(operation)) {
          clearOwnedPrintFeedback();
          return;
        }
        const accepted = onInstanceChange?.(printed, {
          kind: 'update',
          expectedInstanceId,
          operation,
        }) !== false;
        if (!accepted || !isOperationCurrent(operation)) {
          clearOwnedPrintFeedback();
          return;
        }
        await onRefreshHistory?.(printed.patient_id as string | number);
        if (!isOperationCurrent(operation)) {
          clearOwnedPrintFeedback();
          return;
        }
        await onRefreshRecentReports?.();
        if (!isOperationCurrent(operation)) {
          clearOwnedPrintFeedback();
          return;
        }
        await onQueueChanged?.();
        if (!isOperationCurrent(operation)) {
          clearOwnedPrintFeedback();
          return;
        }
        setPrintFeedback({
          severity: 'success',
          text: `${t('workbench.print_sent')}${(printResult as { data?: { printer?: string } })?.data?.printer ? ` (${(printResult as { data?: { printer?: string } })?.data?.printer})` : ''}.`
        });
        // PR-59: auto-dismiss success feedback after 5 seconds
        printFeedbackTimerRef.current = setTimeout(() => {
          if (printAttemptRef.current === printAttempt) {
            setPrintFeedback(null);
            printFeedbackTimerRef.current = null;
          }
        }, 5000);
        return;
      }

      if (!isOperationCurrent(operation)) {
        clearOwnedPrintFeedback();
        return;
      }

      logger.warn('[LabReportWorkbench] direct lab print failed, falling back to PDF', {
        instanceId: activeInstance.id,
        error: printResult.error
      });

      // L-M-9 fix: проверяем что blob-запрос успешен перед window.open.
      // Раньше если downloadPdf упадёт с 500, переменная blob будет undefined,
      // URL.createObjectURL(undefined) выбросит, и labourant увидит белый экран.
      let blob: Blob | unknown;
      try {
        blob = await labReportingApi.downloadPdf(expectedInstanceId);
      } catch (downloadError) {
        if (!isOperationCurrent(operation)) {
          clearOwnedPrintFeedback();
          return;
        }
        logger.error('[LabReportWorkbench] PDF download failed', downloadError);
        setPrintFeedback({
          severity: 'error',
          text: t('workbench.print_pdf_failed')
        });
        notify?.('error', getErrorMessage(downloadError) || t('errors.print_failed'));
        return;
      }
      if (!isOperationCurrent(operation)) {
        clearOwnedPrintFeedback();
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
      if (!isOperationCurrent(operation)) {
        URL.revokeObjectURL(url);
        clearOwnedPrintFeedback();
        return;
      }
      const popup = window.open(url, '_blank', 'noopener,noreferrer');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
      // WF-05 fix: не помечаем как PRINTED при неудаче popup.
      if (popup) {
        let printed: Record<string, unknown>;
        try {
          printed = (await labReportingApi.markPrinted(expectedInstanceId)) as Record<string, unknown>;
        } catch (markError) {
          logger.error('[LabReportWorkbench] opened PDF status update failed', markError);
          if (isOperationCurrent(operation) && printAttemptRef.current === printAttempt) {
            setPrintFeedback({ severity: 'error', text: t('workbench.print_status_failed') });
          }
          notify?.('error', t('workbench.print_status_failed'));
          return;
        }
        const accepted = onInstanceChange?.(printed, {
          kind: 'update',
          expectedInstanceId,
          operation,
        }) !== false;
        if (!accepted || !isOperationCurrent(operation)) {
          clearOwnedPrintFeedback();
          return;
        }
        await onRefreshHistory?.(printed.patient_id as string | number);
        if (!isOperationCurrent(operation)) {
          clearOwnedPrintFeedback();
          return;
        }
        await onRefreshRecentReports?.();
        if (!isOperationCurrent(operation)) {
          clearOwnedPrintFeedback();
          return;
        }
        await onQueueChanged?.();
        if (!isOperationCurrent(operation)) {
          clearOwnedPrintFeedback();
          return;
        }
        setPrintFeedback({
          severity: 'success',
          text: t('workbench.print_pdf_opened')
        });
      } else {
        if (!isOperationCurrent(operation)) return;
        setPrintFeedback({
          severity: 'warning',
          text: t('workbench.print_pdf_blocked')
        });
      }
    } catch (error) {
      if (!isOperationCurrent(operation)) {
        clearOwnedPrintFeedback();
        return;
      }
      setPrintFeedback({
        severity: 'error',
        text: (error instanceof Error ? error.message : String(error))
      });
      notify?.('error', getErrorMessage(error));
    } finally {
      if (printAttemptRef.current === printAttempt) {
        setSaving(false);
        setBusyAction('');
      }
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
    if (!activeInstance || instanceTransitionPending) return;
    const operation = captureOperationContext();
    const patientId = activeInstance.patient_id;
    const instanceId = activeInstance.id;
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
    if (!isOperationCurrent(operation)) return;
    setSaving(true);
    setBusyAction('notify');
    try {
      await api.post('/telegram/send-lab-results', {
        patient_id: patientId,
        instance_id: instanceId,
      });
      if (!isOperationCurrent(operation)) return;
      notify?.('success', t('success.notified'));
    } catch (error) {
      if (!isOperationCurrent(operation)) return;
      const msg = getErrorMessage(error) || 'Не удалось отправить результаты пациенту.';
      notify?.('error', typeof msg === 'string' ? msg : t('errors.notify_failed'));
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
            <FileText size={20} aria-hidden="true" />
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
                {t('workbench.patient_label')}: <strong style={{ color: 'var(--mac-text-primary)' }}>{String(selectedAppointment?.patient_fio ?? '')}</strong>
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
              {!templateResolutionLoading && Boolean(templateResolution?.default_template) && (
                <Alert severity="info">
                  {t('workbench.recommended_report')}: <strong>{String(((templateResolution as Record<string, unknown> | null)?.default_template as Record<string, unknown> | undefined)?.name ?? '')}</strong>
                </Alert>
              )}
              {!templateResolutionLoading && ((templateResolution?.unmapped_service_codes as string[] | undefined)?.length ?? 0) > 0 && (
                <Alert severity={resolvedTemplates.length > 0 ? 'warning' : 'error'}>
                  {t('workbench.unmapped_services')}: {(templateResolution?.unmapped_service_codes as string[]).join(', ')}
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
                      disabled={instanceTransitionPending}
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
                  {t('workbench.single_template_found')} <strong>{String(singleAllowedTemplate.name ?? '')}</strong>. {t('workbench.click_create_to_open')}
                </Alert>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 'var(--mac-spacing-3)', alignItems: 'end' }}>
                <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                  <span>{serviceContextPresent && !escapeHatchActive ? 'Допустимый отчёт' : 'Шаблон отчёта'}</span>
                  <select
                    className="macos-input"
                    value={selectedTemplateId}
                    onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setSelectedTemplateId(event.target.value)}
                    disabled={instanceTransitionPending || templateResolutionLoading || (resolutionHasBlockingGap && !escapeHatchActive)}
                  >
                    <option value="">Выберите шаблон</option>
                    {effectiveTemplateOptions.map((template) => (
                      <option key={template.id} value={template.id}>
                        {String(template.name ?? '')} ({String(template.family ?? '')})
                      </option>
                    ))}
                  </select>
                </label>
                <Button
                  variant="primary"
                  onClick={() => handleCreateInstance()}
                  disabled={saving || instanceTransitionPending || templateResolutionLoading || (resolutionHasBlockingGap && !escapeHatchActive) || !selectedTemplateId}
                >
                  <FolderPlus size={16} aria-hidden="true" />
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
                      {String((activeInstance.patient_snapshot as Record<string, unknown> | undefined)?.full_name ?? '') || `Пациент #${String(activeInstance.patient_id ?? '')}`}
                    </div>
                    <Badge variant={getLabStatusVariant(activeInstance.status as string)}>{formatLabStatus(activeInstance.status as string)}</Badge>
                    <Badge variant="info">{String((activeInstance.template as Record<string, unknown> | undefined)?.name ?? '')}</Badge>
                  </div>
                  <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-base)' }}>
                    Визит: {String(activeInstance.visit_id ?? '') || 'без визита'} | Отчёт #{String(activeInstance.id ?? '')}
                    {/* WF-04 fix: показываем supersedes relationship для audit trail.
                        Если этот отчёт — ревизия другого, лаборант видит связь.
                        Backend поле: supersedes_instance_id (см. lab_reporting_service.py:785). */}
                    {/* PR-60 / Low-31: supersedes link now clickable — navigates to original instance */}
                    {Boolean(activeInstance.supersedes_instance_id) && (
                      <button
                        type="button"
                        onClick={() => {
                          // PR5: every report switch must pass through the panel's
                          // dirty-transition guard exposed by onOpenInstance.
                          const instanceId = activeInstance.supersedes_instance_id;
                          if (
                            onOpenInstance
                            && (typeof instanceId === 'string' || typeof instanceId === 'number')
                          ) {
                            onOpenInstance(instanceId);
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
                        ← исправленная версия отчёта #{String(activeInstance.supersedes_instance_id ?? '')}
                      </button>
                    )}
                  </div>
                  {/* P-20 fix: визуальный stepper жизненного цикла бланка.
                      Показывает текущую фазу и будущие шаги. */}
                  <LabStatusStepper status={activeInstance.status as string} />
                </div>

{/* PR6: «Добавить бланк» — только серверно разрешённые шаблоны
                      (templateResolution.allowed_templates). Заблокировано при
                      isDirty: несохранённый черновик не теряется. Существующие
                      отчёты остаются в истории (reportHistory / недавние). */}
                  {selectedAppointment && !templateResolutionLoading && allowedTemplates.length > 0 && (
                    <Alert severity="info">
                      <span>Добавить ещё бланк:</span>
                      <select
                        className="macos-input"
                        aria-label="Шаблон дополнительного бланка"
                        value={addBlankTemplateIdValue}
                        onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setAddBlankTemplateId(event.target.value)}
                        disabled={instanceTransitionPending}
                      >
                        {allowedTemplates.map((template) => (
                          <option key={String(template.id)} value={String(template.id)}>
                            {String(template.name ?? '')} ({String(template.family ?? '')})
                          </option>
                        ))}
                      </select>
                      <Button
                        variant="outline"
                        size="small"
                        disabled={saving || isDirty || instanceTransitionPending || busyAction === 'create' || !addBlankTemplateIdValue}
                        title={isDirty ? 'Сначала сохраните несохранённые изменения черновика' : undefined}
                        onClick={() => handleCreateInstance(addBlankTemplateIdValue)}
                      >
                        <FolderPlus size={14} aria-hidden="true" />
                        Добавить бланк
                      </Button>
                      {isDirty && (
                        <span> — сначала сохраните несохранённые изменения черновика</span>
                      )}
                    </Alert>
                  )}
                {/* P-04 fix: панель действий вынесена в LabReportActionsBar */}
                <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap', alignItems: 'center' }}>
                  <LabReportActionsBar
                    saving={saving || instanceTransitionPending}
                    busyAction={busyAction ?? undefined}
                    canSaveDraft={canSaveDraft}
                    // WF-10 fix: Finalize disabled пока есть missing required fields.
                    canFinalize={canFinalizeWithValidation}
                    canRevise={canRevise}
                    canPrint={canPrint}
                    // P1 fix: Notify patient — only for finalized/printed reports.
                    canNotify={String(activeInstance?.status ?? '') === 'FINALIZED' || String(activeInstance?.status ?? '') === 'PRINTED'}
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
                  {(['lab_technician_label', 'lab_technician_name', 'approver_label', 'approver_name'] as Array<keyof typeof signerFieldLabels>).map((key) => (
                    <label key={key} style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                      <span>{signerFieldLabels[key] || key}</span>
                      <Input
                        className="macos-input"
                        aria-label={signerFieldLabels[key] || key}
                        value={String(signerSnapshot?.[key] ?? '')}
                        onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setSignerSnapshot((prev) => ({ ...prev, [key]: event.target.value }))}
                        // WF-09 fix: signer fields должны блокироваться на FINALIZED/PRINTED,
                        // иначе persistDraft вызовет updateInstance → 409 Conflict (silent failure).
                        disabled={!canEditVisibleInstance}
                      />
                    </label>
                  ))}
                </div>
              </details>

              {printFeedback && (
                <Alert severity={printFeedback.severity}>{printFeedback.text}</Alert>
              )}

              {((activeInstance.critical_findings as Array<Record<string, unknown>> | undefined)?.length ?? 0) > 0 && (
                <Alert severity="error" role="alert">  {/* PR-59: role=alert for screen readers */}
                  <div style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                    <strong>Критические результаты</strong>
                    {(activeInstance.critical_findings as Array<Record<string, unknown>>).map((finding: Record<string, unknown>) => (
                      <div
                        key={`${String(finding.section_key ?? '')}-${String(finding.field_key ?? '')}`}
                        style={{
                          display: 'grid',
                          gridTemplateColumns: 'minmax(180px, 1.4fr) minmax(110px, 0.7fr) minmax(110px, 0.7fr) minmax(100px, 0.6fr)',
                          gap: 'var(--mac-spacing-2)',
                          alignItems: 'center'
                        }}
                      >
                        <div style={{ display: 'grid', gap: 'var(--mac-spacing-1)' }}>
                          <strong>{String(finding.label ?? '')}</strong>
                          <span style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>
                            {String(finding.section_title ?? finding.section_key ?? '')}
                          </span>
                        </div>
                        <div>
                          {String(finding.value_display ?? '')}
                          {finding.unit ? ` ${String(finding.unit)}` : ''}
                        </div>
                        <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>
                          {String(finding.threshold_display ?? finding.reference_text ?? '—')}
                        </div>
                          <Badge variant={flagVariant(String(finding.resolved_flag ?? ''), (finding.resolved_flag_severity as number | null) ?? null)}>
                            {formatFlagLabel(finding as Record<string, unknown>)}
                          </Badge>
                      </div>
                    ))}
                  </div>
                </Alert>
              )}

              {/* STRAT#24: sections/fields editor extracted to ReportEditor component */}
              <ReportEditor
                activeInstance={activeInstance as never}
                draftValues={draftValues as Record<string, string>}
                collapsedSections={collapsedSections}
                onToggleSection={(sectionKey: string) => {
                  setCollapsedSections((prev) => {
                    const next = new Set(prev);
                    if (next.has(sectionKey)) next.delete(sectionKey);
                    else next.add(sectionKey);
                    return next;
                  });
                }}
                onUpdateField={updateField}
                canEditActiveInstance={canEditVisibleInstance}
                reportHistory={reportHistory}
                notify={notify}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* STRAT#25: supplementary content (AI analysis + history) grouped in ReportSidebar */}
      <ReportSidebar
        activeInstance={activeInstance as never}
        notify={notify as (type: string, message: string) => void}
        showRecentReportsBrowser={showRecentReportsBrowser}
        recentReports={recentReports as never}
        reportHistory={reportHistory as never}
        historySeverityFilter={historySeverityFilter}
        onSeverityFilterChange={setHistorySeverityFilter}
        onOpenInstance={onOpenInstance}
      />
      {/* WF-08 fix: portal-mounted ConfirmDialog для irreversible actions */}
      {confirmDialog}
    </div>
  );
}

