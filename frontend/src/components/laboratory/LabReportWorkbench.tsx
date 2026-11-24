
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type FocusEvent } from 'react';
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
// PR 3351 (review round 9, P1): устойчивый Idempotency-Key операции CREATE.
import {
  clearCreateInstanceIdempotencyKey,
  resolveCreateInstanceIdempotencyKey,
} from './createInstanceIdempotency';

// WF-08 fix: confirmation dialog для irreversible actions (Finalize, Revise).
import { useConfirm } from '../common/ConfirmDialog';

import {
  getEvaluationLabelKey,
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
import { hasDraftDifference, useLabReportState } from './hooks/useLabReportState';
import type { LabReportInstance, ReportDraftSnapshot } from './hooks/useLabReportState';
import ReportSaveStatus from './ReportSaveStatus';
import ReportWorkflowPanel, {
  ReportWorkflowDialog, type LabWorkflowDetails, type LabWorkflowPrompt,
} from './ReportWorkflowPanel';
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

interface ReportTelegramFeedback {
  reportId: string;
  patientId: string;
  operation: LabReportOperationContext;
  state: 'pending' | 'sent' | 'not_sent' | 'unconfirmed';
}

const TELEGRAM_FEEDBACK_KEYS = {
  manual: 'workbench.telegram_delivery_manual',
  pending: 'workbench.telegram_delivery_pending',
  sent: 'success.notified',
  not_sent: 'errors.notify_not_delivered',
  unconfirmed: 'errors.notify_failed',
};

interface DraftSaveScope {
  instanceId: string | number;
  patientId: unknown;
  baseUpdatedAt: string | null;
}

interface DraftSaveAttempt extends DraftSaveScope {
  submitted: ReportDraftSnapshot;
  editSequence: number;
  metadata: Record<string, unknown> | null;
  values: Array<Record<string, unknown>>;
  expectedUpdatedAt: string | null;
  requestId: string;
}

interface PartialDraftCommit extends DraftSaveScope {
  instance: Record<string, unknown>;
  updatedAt: string;
  signerSnapshot: Record<string, unknown>;
  studyDate: string;
}

class StaleLabReportContextError extends Error {}

function draftSaveScopeMatches(left: DraftSaveScope, right: DraftSaveScope) {
  return String(left.instanceId) === String(right.instanceId)
    && String(left.patientId ?? '') === String(right.patientId ?? '')
    && left.baseUpdatedAt === right.baseUpdatedAt;
}

function newDraftRequestId() {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function getRequestStatus(error: unknown) {
  return typeof error === 'object' && error !== null && 'status' in error ? error.status : undefined;
}

function isSaveConflict(error: unknown) {
  return getRequestStatus(error) === 409
    || (error instanceof Error && error.message.includes('другим пользователем'));
}

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
  const { t: rawT, language } = useTranslation();
  const t = rawT;
  // WF-08 fix: confirmation dialog для irreversible actions.
  // Finalize делает бланк immutable (можно только revise). Revise создаёт
  // новый instance. Оба действия необратимы без объяснения последствий.
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw;
  // ADR-0015: lab reporting API accessed via hook.
  const labReportingApi = useLabReporting();
  const partialDraftCommitRef = useRef<PartialDraftCommit | null>(null);
  const pendingDraftSaveRef = useRef<DraftSaveAttempt | null>(null);
  const draftSaveInFlightRef = useRef(false);
  const editSequenceRef = useRef(0);
  const visibleReportRef = useRef(activeInstance);
  visibleReportRef.current = activeInstance;
  const telegramAttemptRef = useRef<symbol | null>(null);
  const [telegramFeedback, setTelegramFeedback] = useState<ReportTelegramFeedback | null>(null);
  useEffect(() => () => {
    telegramAttemptRef.current = null;
  }, []);
  const [conflictReport, setConflictReport] = useState<LabReportInstance | null>(null);
  const [loadingConflict, setLoadingConflict] = useState(false);
  const conflictAttemptRef = useRef(0);
  const [workflowPrompt, setWorkflowPrompt] = useState<{
    action: LabWorkflowPrompt;
    id: string | number;
    version: string;
    operation: LabReportOperationContext;
  } | null>(null);
  const printAttemptRef = useRef(0);
  // LABR-FE-002 (audit 3886): preview attempt epoch — a late preview
  // response must never open/report into a context that replaced it.
  const previewAttemptRef = useRef(0);
  // RETRO-3970-01 review follow-up: an in-flight preview must not outlive
  // its unmount — the reservation is mirrored so the unmount cleanup can
  // close it, and the mounted mirror owns previewStillCurrent().
  const previewReservedRef = useRef<Window | null>(null);
  const previewMountedRef = useRef(true);
  const printFeedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // RETRO-3970-01 review follow-up: on unmount the in-flight preview loses
  // its ownership (mounted mirror + attempt invalidation) and its reserved
  // blank tab is closed — a late blob response must never navigate a
  // departed report's document into a popup nobody is watching.
  useEffect(() => {
    previewMountedRef.current = true;
    return () => {
      previewMountedRef.current = false;
      previewAttemptRef.current += 1;
      previewReservedRef.current?.close();
      previewReservedRef.current = null;
    };
  }, []);
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
  // LABR-FE-002 (audit 3886): the CURRENT operation context through a ref —
  // an awaited continuation must re-check against the LIVE context, not the
  // callback captured in the render that launched it.
  const operationContextRef = useRef<LabReportOperationContext>(EMPTY_OPERATION_CONTEXT);
  operationContextRef.current = getOperationContext?.() ?? EMPTY_OPERATION_CONTEXT;

  // PR6: серверно разрешённое действие «Добавить бланк». Единственный
  // источник разрешения — backend факт templateResolution.allowed_templates
  // (resolve_template_options); React не изобретает список и не прячет
  // шаблоны сам. При несохранённых изменениях действие заблокировано,
  // чтобы переключение на новый бланк не потеряло черновик.
  const [addBlankTemplateId, setAddBlankTemplateId] = useState<string>('');
  const [assignedServices, setAssignedServices] = useState<number[]>([]);
  const serviceDetails = selectedAppointment?.service_details;
  const serviceAssignments = useMemo(() => Array.isArray(serviceDetails)
    ? serviceDetails.flatMap((item: { visit_service_id?: number | null; name?: string; code?: string }) => {
      const id = item.visit_service_id;
      return typeof id === 'number' && Number.isSafeInteger(id) && id > 0
        ? [{ id, label: item.name || item.code || String(id) }]
        : [];
    })
    : [], [serviceDetails]);
  const selectedVisitServiceIds = useMemo(
    () => assignedServices.filter((id) => serviceAssignments.some((item) => item.id === id)),
    [assignedServices, serviceAssignments],
  );
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
    studyDate,
    setStudyDate,
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
    lastSavedAt,
    setLastSavedAt,
    saveFailure,
    setSaveFailure,
    reconcileReportDraft,
    initialValues,
    initialValuesRef,
    autoSaveTimerRef,
    handleSaveDraftRef,
    isDirty,
    isInstanceHydrated,
    serviceContextItems,
    resolvedTemplates,
    serviceContextPresent,
    effectiveTemplateOptions,
    resolutionHasBlockingGap,
    singleAllowedTemplate,
    showRecentReportsBrowser,
    canEditActiveInstance,
    canSaveDraft,
    canFinalize,
    canRevise,
    canPrint,
    canPreview,
    missingRequiredFields,
    hasMissingRequired,
    canFinalizeWithValidation,
  } = useLabReportState({
    selectedAppointment: selectedAppointment as never,
    templates: (templates as never) || [],
    templateResolution: templateResolution as never,
    activeInstance: activeInstance as never,
  });
  const holdReason = selectedAppointment?.hold_reason;
  const allocationHold = holdReason === 'historical_allocation_unknown' || holdReason === 'specimen_order_ambiguous';
  const useUnassignedTemplate = escapeHatchActive && !allocationHold;
  const requiresAssignment = allocationHold || (serviceAssignments.length > 0 && !useUnassignedTemplate);
  const missingAssignment = requiresAssignment && selectedVisitServiceIds.length === 0;
  const allocationUnavailable = allocationHold && serviceAssignments.length === 0;
  const availableTemplateOptions = allocationHold ? resolvedTemplates : effectiveTemplateOptions;
  const templateHasBlockingGap = allocationHold ? resolvedTemplates.length === 0 : resolutionHasBlockingGap;
  useLayoutEffect(() => {
    setAssignedServices([]);
  }, [selectedAppointment?.patient_id, selectedAppointment?.visit_id, selectedAppointment?.order_id]);
  const canEditVisibleInstance = canEditActiveInstance
    && isInstanceHydrated
    && !instanceTransitionPending
    && (!saving || busyAction === 'save');

  // PR 3351 pending-контракт (review round 7, P1; уточнение round 8, P1):
  // ДВА уровня pending-защиты, и CREATE блокирует ОБА.
  //
  // Round 7 держал CREATE вне контекстного уровня (latest-wins: поздний
  // ответ отбрасывается по operation-context в handleInstanceChange).
  // Round 8 закрывает это как небезопасное для неидемпотентного POST
  // /lab/report-instances: серверный side effect коммитится ДО любого
  // решения UI, а смена пациента/отчёта в полёте заставляла обработчик
  // молча выбросить ответ — без onRefreshHistory/onRefreshRecentReports/
  // onQueueChanged и уведомления. Оператор не видел созданный бланк и
  // повторял CREATE — второй бланк. Поэтому CREATE, как и save/autosave/
  // finalize/revise/print, блокирует и контекстные переходы, и полный
  // уход с /lab (beforeunload провайдера, guardRouteLeave, sentinel и
  // session-expiry redirect).
  //
  // URL-контракт sentinel-а при этом не страдает: пока sentinel вооружён,
  // WF-15 эффект LabPanel откладывает замену ?instance в адресе (см.
  // historyGuardEngaged в LabDirtyGuardContext) — collapse sentinel-а
  // приземляется на twin с ДО-create URL без расхождения, а отложенная
  // запись выполняется на уже свёрнутую запись после settle.
  const reportBlocksContextTransition = saving;
  const reportBlocksDocumentLeave = saving;
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

  useLayoutEffect(() => {
    return () => {
      pendingDraftSaveRef.current = null;
      partialDraftCommitRef.current = null;
    };
  }, [activeInstance?.id, activeInstance?.patient_id, activeInstance?.updated_at]);

  useLayoutEffect(() => {
    conflictAttemptRef.current += 1;
    setConflictReport(null);
    setLoadingConflict(false);
    setWorkflowPrompt(null);
  }, [activeInstance?.id, activeInstance?.patient_id]);

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
        if (!saving && saveFailure !== 'conflict' && handleSaveDraftRef.current) {
          // PR3: attemptSaveDraft бросает исключение при неудаче — показываем
          // ошибку через общий обработчик (включая конфликтный 409-toast).
          void Promise.resolve(handleSaveDraftRef.current()).catch((saveError: unknown) => {
            notifySaveErrorRef.current(saveError);
          });
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [canSaveDraft, handleSaveDraftRef, instanceTransitionPending, saving, saveFailure]);

  // Leave failed or ambiguous writes visible until the operator retries or
  // resolves a version conflict. Typing still works while a write is in flight.
  useEffect(() => {
    if (!isDirty || !canSaveDraft || saving || saveFailure || instanceTransitionPending || pauseAutoSave) return;
    const scheduledOperation = captureOperationContext();
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    autoSaveTimerRef.current = setTimeout(async () => {
      if (!isOperationCurrent(scheduledOperation)) return;
      try {
        await handleSaveDraftRef.current?.('auto');
      } catch {
        // attemptSaveDraft records a persistent failure for the active report.
      }
    }, 30000); // 30 seconds
    return () => {
      if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    };
  }, [
    isDirty,
    canSaveDraft,
    autoSaveTimerRef,
    handleSaveDraftRef,
    saving,
    saveFailure,
    draftValues,
    signerSnapshot,
    studyDate,
    instanceTransitionPending,
    pauseAutoSave,
    captureOperationContext,
    isOperationCurrent,
  ]);

  const handleCreateInstance = useCallback(async (templateIdOverride: string | number | null = null, options: Record<string, unknown> = {}) => {
    if (instanceTransitionPending || missingAssignment) return;
    const operation = captureOperationContext();
    const expectedInstanceId = (activeInstance?.id as string | number | null | undefined) ?? null;
    const templateId = templateIdOverride || selectedTemplateId;
    if (!selectedAppointment?.patient_id || !templateId) {
      notify?.('error', t('errors.select_patient_template'));
      return;
    }
    if (templateHasBlockingGap || (allocationHold && !availableTemplateOptions.some((option) => String(option.id) === String(templateId)))) {
      notify?.('error', t('errors.no_template_for_services'));
      return;
    }
    setSaving(true);
    setBusyAction('create');
    try {
      const createPayload = {
        patient_id: selectedAppointment.patient_id as string | number,
        appointment_id: (selectedAppointment.appointment_id as string | number) || null,
        visit_id: (templateResolution?.visit_id as string | number) || (selectedAppointment.visit_id as string | number) || null,
        template_id: Number(templateId),
        ...(selectedAppointment.order_id != null ? { order_id: selectedAppointment.order_id } : {}),
        ...(requiresAssignment ? { visit_service_ids: [...selectedVisitServiceIds].sort((left, right) => left - right) } : {}),
        // WF-11 fix: при escape hatch не передаём service_codes —
        // бланк создаётся без привязки к услугам визита.
        service_codes: useUnassignedTemplate ? [] : ((templateResolution?.service_codes as string[]) || (selectedAppointment.service_codes as string[]) || []),
        service_items: useUnassignedTemplate ? [] : ((selectedAppointment.service_details as Array<Record<string, unknown>>) || []).map((item: Record<string, unknown>) => ({
          service_id: item.id || null,
          code: item.code || null,
          name: item.name || null
        }))
      };
      // PR 3351 (review round 9, P1): POST /lab/report-instances без
      // Idempotency-Key неидемпотентен: транспортный разрыв ПОСЛЕ
      // серверного commit (502 reverse proxy, crash вкладки, retry после
      // reload) терял ID созданного бланка — повторный клик коммитил
      // второй бланк. Ключ операции устойчив: генерируется на первой
      // попытке, переживает неопределённый исход в sessionStorage и
      // переиспользуется повтором (backend возвращает закоммиченный ответ
      // ровно для того же payload — слот хранит только односторонний
      // digest тела запроса, CodeQL alert 1315, round 10). Ответ 2xx получен —
      // исход известен, слот освобождается: следующее создание = новая
      // операция = новый легитимный бланк.
      const idempotencyKey = await resolveCreateInstanceIdempotencyKey(createPayload);
      const instance = await labReportingApi.createInstance(createPayload, { idempotencyKey });
      clearCreateInstanceIdempotencyKey(createPayload);
      const accepted = onInstanceChange?.(instance as Record<string, unknown>, {
        kind: 'transition',
        expectedInstanceId,
        operation,
      }) !== false;
      if (!accepted) {
        // PR 3351 (review round 8, P1): серверный side effect уже НЕОБРАТИМ —
        // create_instance() закоммитил бланк ДО любого решения UI. Round 7
        // здесь просто возвращался: поздний (по operation-context) ответ
        // молча выбрасывался — без onRefreshHistory/onRefreshRecentReports/
        // onQueueChanged и уведомления, оператор не видел созданный бланк и
        // повторял CREATE — второй бланк. Round 8 закрывает сам вход в эту
        // ветку (CREATE блокирует контекстные переходы — смена пациента/
        // отчёта в полёте больше не допускается), но server outcome обязан
        // пережить ЛЮБОЙ сценарий: обновляем canonical read-model (история
        // пациента — no-op при уже сменившемся контексте: loadReportHistory
        // гвардится belongsToCurrentContext) и сообщаем оператору, КАКОМУ
        // пациенту создан бланк — не применяя его к текущему UI-контексту.
        await onRefreshHistory?.(selectedAppointment.patient_id as string | number);
        await onRefreshRecentReports?.();
        await onQueueChanged?.();
        notify?.('success', t('success.report_created_for_patient', {
          patient: String(
            selectedAppointment.patient_fio
            ?? selectedAppointment.patient_id
            ?? '',
          ),
        }));
        return;
      }
      setAssignedServices([]);
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
    allocationHold,
    availableTemplateOptions,
    captureOperationContext,
    isOperationCurrent,
    instanceTransitionPending,
    labReportingApi,
    missingAssignment,
    notify,
    onInstanceChange,
    onRefreshHistory,
    onRefreshRecentReports,
    onQueueChanged,
    requiresAssignment,
    templateHasBlockingGap,
    useUnassignedTemplate,
    selectedAppointment,
    selectedTemplateId,
    selectedVisitServiceIds,
    setBusyAction,
    setSaving,
    t,
    templateResolution,
  ]);

  // STRAT#1: init-instance effect, default-template effect, keyboard-shortcut
  // effect и autosave effect — все вынесены в useLabReportState hook.
  // Здесь остались только handlers, которые зависят от notify/onInstanceChange
  // (их нельзя изолировать в хук без прокидания через args).

  function updateField(fieldKey: string, value: unknown) {
    editSequenceRef.current += 1;
    setDraftValues((prev) => ({ ...prev, [fieldKey]: value }));
  }

  function isCurrentReport(id: string | number, operation: LabReportOperationContext) {
    return String(visibleReportRef.current?.id ?? '') === String(id) && isOperationCurrent(operation);
  }

  function buildDraftAttempt(
    instance: Record<string, unknown>,
    scope: DraftSaveScope,
    partial: PartialDraftCommit | null,
    submitted: ReportDraftSnapshot,
    editSequence: number,
  ): DraftSaveAttempt {
    const values: Array<Record<string, unknown>> = [];
    (instance.sections as Array<Record<string, unknown>>).forEach((section: Record<string, unknown>) => {
      ((section.fields as Array<Record<string, unknown>>) || []).forEach((field: Record<string, unknown>) => {
        const fieldKey = String(field.field_key);
        const currentValue = submitted.values[fieldKey];
        if (currentValue === undefined) {
          return;
        }
        const absenceReason = String(submitted.values[`${fieldKey}__absence_reason`] ?? '').trim();
        const unchanged = !hasDraftDifference(currentValue, initialValuesRef.current.values[fieldKey]);
        values.push({
          field_key: field.field_key,
          value_text: absenceReason || currentValue === '' ? null : String(currentValue),
          ...(absenceReason ? { result_kind: 'absent', absence_reason: absenceReason } : {}),
          ...(!absenceReason && unchanged && field.qualitative_code && currentValue !== ''
            ? { result_kind: 'coded_qualitative', qualitative_code: field.qualitative_code }
            : {}),
          ...(unchanged && field.method_code && !absenceReason ? { method_code: field.method_code } : {}),
          comment: submitted.values[`${fieldKey}__comment`] || null,
        });
      });
    });

    const persistedSignerSnapshot = partial?.signerSnapshot ?? initialValuesRef.current.signer;
    const persistedStudyDate = partial?.studyDate ?? initialValuesRef.current.studyDate;
    const instanceChanges: Record<string, unknown> = {};
    if (JSON.stringify(persistedSignerSnapshot) !== JSON.stringify(submitted.signer)) {
      instanceChanges.signer_snapshot = submitted.signer;
    }
    if (persistedStudyDate !== submitted.studyDate) instanceChanges.study_date = submitted.studyDate || null;
    return {
      ...scope,
      submitted,
      editSequence,
      metadata: Object.keys(instanceChanges).length > 0 ? instanceChanges : null,
      values,
      expectedUpdatedAt: partial?.updatedAt ?? scope.baseUpdatedAt,
      requestId: newDraftRequestId(),
    };
  }

  async function persistDraft(
    instance: Record<string, unknown>,
    operation: LabReportOperationContext,
    submitted: ReportDraftSnapshot,
    editSequence: number,
  ) {
    const scope = {
      instanceId: instance.id as string | number,
      patientId: instance.patient_id,
      baseUpdatedAt: initialValuesRef.current.updatedAt,
    };
    const { instanceId } = scope;
    const cachedPartial = partialDraftCommitRef.current;
    const partial = cachedPartial && draftSaveScopeMatches(cachedPartial, scope) ? cachedPartial : null;
    const pending = pendingDraftSaveRef.current;
    let attempt = pending && draftSaveScopeMatches(pending, scope)
      ? pending
      : buildDraftAttempt(instance, scope, partial, submitted, editSequence);
    let latest = partial?.instance ?? instance;

    // Metadata comes first. An ambiguous result keeps the exact request and
    // its submitted values in memory until the operator retries or discards.
    while (attempt.metadata || attempt.values.length) {
      const { metadata, values, expectedUpdatedAt, requestId } = attempt;
      pendingDraftSaveRef.current = attempt;
      let updatedAt: string;
      try {
        const response = metadata
          ? await labReportingApi.updateInstance(instanceId, metadata, expectedUpdatedAt, requestId)
          : await labReportingApi.bulkSaveValues(instanceId, values, expectedUpdatedAt, requestId);
        const saved = (
          metadata ? response : (response as { instance?: unknown } | null)?.instance
        ) as Record<string, unknown> | null;
        if (!saved || String(saved.id) !== String(instanceId)
          || String(saved.patient_id ?? '') !== String(scope.patientId ?? '')
          || typeof saved.updated_at !== 'string' || !saved.updated_at
          || !Array.isArray(saved.sections)) {
          throw new TypeError('Invalid draft save response');
        }
        latest = saved;
        updatedAt = saved.updated_at;
      } catch (error) {
        const status = getRequestStatus(error);
        const rejected = isSaveConflict(error) || (typeof status === 'number'
          && status >= 400 && status < 500 && status !== 401 && status !== 408 && status !== 429);
        if (rejected && pendingDraftSaveRef.current === attempt) pendingDraftSaveRef.current = null;
        throw error;
      }

      if (pendingDraftSaveRef.current !== attempt) throw new StaleLabReportContextError();
      pendingDraftSaveRef.current = null;
      // An acknowledged response can supply the next token if a target
      // transition failed and the same report is still visible.
      partialDraftCommitRef.current = {
        ...scope,
        instance: latest,
        updatedAt,
        signerSnapshot: attempt.submitted.signer,
        studyDate: attempt.submitted.studyDate,
      };
      if (!isCurrentReport(instanceId, operation)) throw new StaleLabReportContextError();
      if (!metadata || !values.length) break;
      attempt = { ...attempt, metadata: null, expectedUpdatedAt: updatedAt, requestId: newDraftRequestId() };
    }
    if (!isCurrentReport(instanceId, operation)) throw new StaleLabReportContextError();
    return { latest, submitted: attempt.submitted, editSequence: attempt.editSequence };
  }

  // PR3: ядро сохранения — бросает исключение при неудаче, чтобы autosave
  // (и любой другой вызывающий) мог достоверно отличить успех от провала
  // и не выставлял lastAutoSave после неуспешного запроса.
  async function attemptSaveDraft(mode: 'manual' | 'auto' | 'leave' = 'manual'): Promise<boolean> {
    if (!activeInstance || !isInstanceHydrated || !canSaveDraft || saving || instanceTransitionPending
      || saveFailure === 'conflict' || draftSaveInFlightRef.current) return false;
    const operation = captureOperationContext();
    const expectedInstanceId = activeInstance.id as string | number;
    const editSequence = editSequenceRef.current;
    const submitted = { values: draftValues, signer: signerSnapshot, studyDate };
    const previousStatus = activeInstance.status;
    draftSaveInFlightRef.current = true;
    setSaveFailure(null);
    setSaving(true);
    setBusyAction('save');
    try {
      const saved = await persistDraft(activeInstance, operation, submitted, editSequence);
      const { latest } = saved;
      if (onInstanceChange?.(latest, { kind: 'update', expectedInstanceId, operation }) === false) return false;
      reconcileReportDraft(latest as unknown as LabReportInstance, saved.submitted, true);
      partialDraftCommitRef.current = null;
      const timestamp = typeof latest.updated_at === 'string' ? Date.parse(latest.updated_at) : NaN;
      setLastSavedAt(Number.isFinite(timestamp) ? new Date(timestamp) : new Date());
      setConflictReport(null);
      // History is an independent read. A delayed refresh cannot keep the
      // acknowledged write pending or convert it to a failed save.
      void Promise.resolve().then(() => onRefreshHistory?.(activeInstance.patient_id as string | number)).catch(() => {});
      if (!isCurrentReport(expectedInstanceId, operation)) return false;
      const allEditsSaved = editSequenceRef.current === saved.editSequence;
      if (mode !== 'auto' && allEditsSaved) {
        if (previousStatus === 'DRAFT' && latest.status === 'IN_PROGRESS') {
          notify?.('info', t('success.draft_saved_in_progress'));
        } else {
          notify?.('success', t('success.draft_saved'));
        }
      }
      // A navigation save covers only the submitted snapshot. Do not proceed
      // if a newer local edit arrived before the guard could leave the report.
      return mode !== 'leave' || allEditsSaved;
    } catch (error) {
      if (!isCurrentReport(expectedInstanceId, operation)) {
        throw new StaleLabReportContextError();
      }
      if (!(error instanceof StaleLabReportContextError)) {
        setSaveFailure(isSaveConflict(error) ? 'conflict' : getRequestStatus(error) === 401 ? 'session' : 'error');
      }
      throw error;
    } finally {
      draftSaveInFlightRef.current = false;
      setSaving(false);
      setBusyAction('');
    }
  }

  // PR3: при 409 optimistic locking показываем локализованное действие
  // «Обновить актуальную версию». Введённый draft НЕ перезаписываем
  // автоматически — актуальная версия открывается только явным кликом.
  function notifySaveError(error: unknown) {
    if (error instanceof StaleLabReportContextError) return;
    const status = getRequestStatus(error);
    const message = isSaveConflict(error) ? t('workbench.save_conflict')
      : status === 401 ? t('workbench.save_session')
        : status === 422 || error instanceof TypeError || (error instanceof DOMException && error.name === 'TimeoutError')
          ? t('workbench.save_error')
          : getErrorMessage(error);
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

  async function loadConflictReport() {
    const expectedInstanceId = activeInstance?.id as string | number | undefined;
    if (expectedInstanceId == null || loadingConflict) return;
    const operation = captureOperationContext();
    const attempt = ++conflictAttemptRef.current;
    setLoadingConflict(true);
    try {
      const latest = await labReportingApi.getInstance(expectedInstanceId) as LabReportInstance;
      if (conflictAttemptRef.current !== attempt || !isCurrentReport(expectedInstanceId, operation)) return;
      if (String(latest?.id) !== String(expectedInstanceId)
        || String(latest?.patient_id ?? '') !== String(activeInstance?.patient_id ?? '')
        || typeof latest.updated_at !== 'string'
        || !Array.isArray(latest.sections)) throw new StaleLabReportContextError();
      setConflictReport(latest);
    } catch {
      if (conflictAttemptRef.current === attempt && isCurrentReport(expectedInstanceId, operation)) {
        notify?.('error', t('workbench.save_compare_error'));
      }
    } finally {
      if (conflictAttemptRef.current === attempt) setLoadingConflict(false);
    }
  }

  function resolveDraftConflict(keepLocal: boolean) {
    const expectedInstanceId = activeInstance?.id as string | number | undefined;
    if (!conflictReport || expectedInstanceId == null || String(conflictReport.id) !== String(expectedInstanceId)) return;
    if (keepLocal && !hasLabReportAction(conflictReport, 'save_draft')) return;
    const operation = captureOperationContext();
    const accepted = onInstanceChange?.(conflictReport, {
      kind: 'update', expectedInstanceId, operation,
    }) !== false;
    if (!accepted || !isCurrentReport(expectedInstanceId, operation)) return;
    reconcileReportDraft(conflictReport, keepLocal ? initialValuesRef.current : undefined);
    pendingDraftSaveRef.current = null;
    partialDraftCommitRef.current = null;
    setLastSavedAt(null);
    setSaveFailure(null);
    setConflictReport(null);
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
          const accepted = await handleSaveDraftRef.current?.('leave');
          if (!accepted) {
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
        pendingDraftSaveRef.current = null;
        partialDraftCommitRef.current = null;
        setDraftValues({ ...baseline.values });
        setSignerSnapshot({ ...baseline.signer });
        setStudyDate(baseline.studyDate);
        setSaveFailure(null);
        setConflictReport(null);
      },
    });
  }, [handleSaveDraftRef, initialValuesRef, setDraftValues, setSaveFailure, setSignerSnapshot, setStudyDate]);

  // WF-round5: handleMarkReady убран — Mark Ready был функционально пустой
  // операцией (backend разрешал одинаковые действия для DRAFT/IN_PROGRESS/READY).

  async function handleFinalize() {
    if (!activeInstance || saving || draftSaveInFlightRef.current || instanceTransitionPending || isDirty || saveFailure) return;
    const expectedInstanceId = activeInstance.id as string | number;
    const version = activeInstance.updated_at as string | undefined;
    const editSequence = editSequenceRef.current;
    const operation = captureOperationContext();
    const ok = await confirm({
      title: t('confirm.finalize_title'),
      message: t('confirm.finalize_message'),
      description: t('confirm.finalize_description'),
      confirmLabel: t('confirm.finalize_confirm'),
      cancelLabel: t('confirm.cancel'),
      intent: 'primary',
    });
    if (!ok || !isCurrentReport(expectedInstanceId, operation)
      || visibleReportRef.current?.updated_at !== version
      || editSequenceRef.current !== editSequence || draftSaveInFlightRef.current) return;
    setSaving(true);
    setBusyAction('finalize');
    try {
      const finalized = await labReportingApi.finalize(expectedInstanceId, version) as Record<string, unknown>;
      const accepted = onInstanceChange?.(finalized, {
        kind: 'update', expectedInstanceId, operation,
      }) !== false;
      if (!accepted || !isCurrentReport(expectedInstanceId, operation)) return;
      await Promise.all([
        onRefreshHistory?.(finalized.patient_id as string | number),
        onRefreshRecentReports?.(),
        onQueueChanged?.(),
      ]);
      if (isCurrentReport(expectedInstanceId, operation)) notify?.('success', t('success.finalized'));
    } catch (error) {
      if (isCurrentReport(expectedInstanceId, operation)) {
        if (isSaveConflict(error)) setSaveFailure('conflict');
        notifySaveError(error);
      }
    } finally {
      setSaving(false);
      setBusyAction('');
    }
  }

  function openWorkflowPrompt(action: LabWorkflowPrompt) {
    if (!activeInstance || saving || isDirty || saveFailure || instanceTransitionPending) return;
    if (typeof activeInstance.updated_at !== 'string') return;
    setWorkflowPrompt({
      action,
      id: activeInstance.id as string | number,
      version: activeInstance.updated_at,
      operation: captureOperationContext(),
    });
  }

  async function handleWorkflowCommand(
    action: 'submit_review' | 'review' | LabWorkflowPrompt,
    details?: LabWorkflowDetails,
  ) {
    if (!activeInstance || saving || draftSaveInFlightRef.current || isDirty || saveFailure || instanceTransitionPending) return;
    const id = activeInstance.id as string | number;
    const version = typeof activeInstance.updated_at === 'string' ? activeInstance.updated_at : '';
    const operation = workflowPrompt?.operation ?? captureOperationContext();
    if (!version || !isCurrentReport(id, operation) || !hasLabReportAction(activeInstance, action)) return;
    if (workflowPrompt && (String(workflowPrompt.id) !== String(id) || workflowPrompt.version !== version)) {
      setWorkflowPrompt(null);
      notify?.('error', t('workbench.save_conflict'));
      return;
    }
    setSaving(true);
    setBusyAction(action);
    try {
      let response: unknown;
      switch (action) {
        case 'submit_review':
          response = await labReportingApi.submitReview(id, version);
          break;
        case 'review':
          response = await labReportingApi.review(id, version);
          break;
        case 'return_to_draft':
          if (!details?.reason) return;
          response = await labReportingApi.returnToDraft(id, { expected_updated_at: version, reason: details.reason });
          break;
        case 'record_qc':
          if (!details?.status) return;
          response = await labReportingApi.recordQC(id, { ...details, status: details.status, expected_updated_at: version });
          break;
        case 'revise':
          if (!details?.reason) return;
          response = await labReportingApi.revise(id, { expected_updated_at: version, reason: details.reason });
          break;
      }
      if (!isCurrentReport(id, operation) || !response) return;
      const changed = response as Record<string, unknown>;
      const accepted = onInstanceChange?.(changed, {
        kind: action === 'revise' ? 'transition' : 'update', expectedInstanceId: id, operation,
      }) !== false;
      if (!accepted) return;
      setWorkflowPrompt(null);
      await Promise.all([
        onRefreshHistory?.(changed.patient_id as string | number),
        onRefreshRecentReports?.(),
        onQueueChanged?.(),
      ]);
      if (action === 'revise') notify?.('success', t('success.revised'));
    } catch (error) {
      if (!isCurrentReport(id, operation)) return;
      if (isSaveConflict(error)) {
        setSaveFailure('conflict');
        setWorkflowPrompt(null);
      }
      notifySaveError(error);
    } finally {
      setSaving(false);
      setBusyAction('');
    }
  }

  // PR8 (codex-lab-workflow-hardening-plan): серверный A4-preview сохранённых
  // значений ДО утверждения — тот же движок, что пойдёт на печать.
  // Контракт: blob открывается в новой вкладке; mark-printed НЕ вызывается,
  // статус/уведомления/финализация не затрагиваются (см. backend endpoint
  // /lab/report-instances/{id}/preview). Unsaved-значения не отправляются:
  // preview рендерит последний сохранённый draft (Save Draft до preview).
  async function handlePreviewPdf() {
    if (!activeInstance || instanceTransitionPending) return;
    const expectedInstanceId = activeInstance.id as string | number;
    // LABR-FE-002 (audit 3886): capture the operation context and a
    // preview epoch — after the awaited read, the response may only open
    // while THIS preview still owns the active instance/context.
    const previewOperation = getOperationContext?.() ?? EMPTY_OPERATION_CONTEXT;
    const previewAttempt = ++previewAttemptRef.current;
    const previewStillCurrent = () =>
      previewMountedRef.current &&
      previewAttemptRef.current === previewAttempt &&
      operationContextsMatch(previewOperation, operationContextRef.current);
    // RETRO-3970-01 (CARDHIST-FE-001 precedent): reserve the browsing
    // context SYNCHRONOUSLY inside the click gesture — before any await.
    // No `noopener` feature string: a null reservation is an HONEST
    // blocked signal, a context is a guaranteed-to-be-fulfilled open.
    // (A noopener window.open returns null even on success — the old
    // post-await call both lost the gesture and lied about the result.)
    const reserved = window.open('', '_blank');
    if (!reserved) {
      setPrintFeedback({ severity: 'error', text: t('workbench.preview_popup_blocked') });
      return;
    }
    previewReservedRef.current = reserved;
    setBusyAction('preview');
    setPrintFeedback({ severity: 'info', text: t('workbench.preview_building') });
    try {
      const blob = await labReportingApi.previewInstancePdf(expectedInstanceId);
      if (!blob || !(blob instanceof Blob) || blob.size === 0) {
        // RETRO-3970-01: never leave the reserved blank tab behind. The
        // review follow-up adds the size guard — a zero-byte payload would
        // otherwise open as a dead document.
        reserved.close();
        if (previewStillCurrent()) {
          setPrintFeedback({ severity: 'error', text: t('workbench.print_pdf_invalid') });
        }
        return;
      }
      // LABR-FE-002: the operator switched the report/patient while the
      // read was pending — drop the stale blob BEFORE any object URL is
      // created; no window.open, no feedback overwrite on the new screen.
      if (!previewStillCurrent()) {
        reserved.close();
        logger.warn('[LabReportWorkbench] Stale PDF preview ignored for a changed report context');
        return;
      }
      const url = URL.createObjectURL(blob);
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
      // RETRO-3970-01: the reserved tab is navigated here — a noopener
      // window.open returns null even on a SUCCESSFUL open (MDN), so the
      // old truthiness check reported every successful preview as
      // «blocked». The reservation returned a context, so this success is
      // a REAL success.
      // WF-05 parity: НЕ помечаем PRINTED и не дёргаем onRefresh* —
      // preview не имеет серверных побочных эффектов.
      reserved.opener = null;
      reserved.location.href = url;
      setPrintFeedback({ severity: 'success', text: t('workbench.preview_opened') });
      if (printFeedbackTimerRef.current) {
        clearTimeout(printFeedbackTimerRef.current);
        printFeedbackTimerRef.current = null;
      }
      printFeedbackTimerRef.current = setTimeout(() => {
        if (previewAttemptRef.current === previewAttempt) {
          setPrintFeedback(null);
          printFeedbackTimerRef.current = null;
        }
      }, 5000);
    } catch (previewError) {
      // RETRO-3970-01: the failed read must not leave the reserved blank
      // tab behind — closing it is safe even when the attempt went stale
      // (the tab belongs to the old attempt either way).
      reserved.close();
      if (!previewStillCurrent()) {
        // LABR-FE-002: a stale preview's failure belongs to the old context.
        logger.warn('[LabReportWorkbench] Stale PDF preview failure ignored for a changed report context');
        return;
      }
      logger.error('[LabReportWorkbench] PDF preview failed', previewError);
      setPrintFeedback({ severity: 'error', text: t('workbench.preview_failed') });
      notify?.('error', getErrorMessage(previewError) || t('errors.print_failed'));
    } finally {
      // LABR-FE-002 + LABR-FE-003 (post-merge review of PR 3909, P2): only
      // the current preview owns the busy flag — and ownership is not the
      // preview epoch alone: the try/catch above also compares the LIVE
      // operation context, so a NEWER report action started in a replaced
      // context owns the busy flag now. Compare-and-clear against the live
      // value: the flag is released only when it is still this preview's
      // (an overlapping newer preview keeps its own flag because the epoch
      // check above already skipped this release).
      if (previewAttemptRef.current === previewAttempt) {
        setBusyAction((current) => (current === 'preview' ? '' : current));
      }
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
      // LABPRINT-FE-001 (audit 3886, round 14): отправляем ТОЛЬКО
      // авторизованный идентификатор отчёта — сервер материализует бланк
      // из БД (тот же пайплайн, что канонический PDF). Клиентские
      // значения больше не собираются и не отправляются.
      const printResult = await printService.printLabResults({
        report_instance_id: Number(expectedInstanceId),
      }) as Record<string, unknown>;

      // LABPRINT-FE-003 (audit 3886, round 14): 2xx без положительного
      // ACK — ambiguous: задание МОГЛО встать в очередь. Никакого
      // слепого повтора и автофолбэка: оператор проверяет очередь печати,
      // статус не помечается.
      if ((printResult as { ambiguous?: boolean }).ambiguous) {
        if (!isOperationCurrent(operation)) {
          clearOwnedPrintFeedback();
          return;
        }
        setPrintFeedback({ severity: 'warning', text: t('workbench.print_unconfirmed') });
        return;
      }

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
      if (!blob || !(blob instanceof Blob) || blob.size === 0) {
        // L-M-9 fix: если blob пустой или не Blob — не открываем window.open('undefined').
        // RETRO-3970-01 review follow-up: size === 0 is the same invalid class.
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
      // RETRO-3970-01: the direct-print attempt NEVER auto-opens a tab —
      // it PREPARES the PDF and hands the decision to the operator via the
      // explicit follow-up click («Открыть PDF для печати»). That click is
      // a fresh user activation whose synchronous reservation either
      // succeeds (a context to navigate) or honestly reports «blocked» —
      // the old noopener window.open returned null even on success, so the
      // LABPRINT-FE-002 confirmation was unreachable on real browsers.
      const preparedUrl = url;
      pdfPreparedUrlRef.current = preparedUrl;
      setTimeout(() => {
        URL.revokeObjectURL(preparedUrl);
        // RETRO-3970-01 review follow-up: the 60s object-URL budget also
        // expires the PREPARATION — an expired link must never back the
        // explicit open (a dead document) nor the printed-confirmation that
        // follows it. Only the still-pending preparation expires; one that
        // was already opened (or dropped) is untouched.
        if (pdfPreparedUrlRef.current === preparedUrl) {
          pdfPreparedUrlRef.current = null;
          setPdfFallbackPrepared(null);
          setPrintFeedback({
            severity: 'warning',
            text: t('workbench.print_pdf_prepared_expired')
          });
        }
      }, 60_000);
      setPdfFallbackPrepared({ instanceId: expectedInstanceId, url });
      setPrintFeedback({
        severity: 'info',
        text: t('workbench.print_pdf_prepared')
      });
      return;
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

  // LABPRINT-FE-002 (audit 3886, round 14): PDF-вкладка открыта, но
  // физическая печать не подтверждена. Пока оператор не нажмёт
  // «Отметить как напечатанное», статус отчёта не меняется: открытый
  // PDF-превью — это не печатное задание. Сбрасывается при смене
  // активного отчёта (WF-12 parity).
  const [pdfConfirmPendingInstanceId, setPdfConfirmPendingInstanceId] = useState<string | number | null>(null);
  // RETRO-3970-01: the PDF fallback prepared after a failed direct print —
  // it holds the object URL until the operator clicks «Открыть PDF для
  // печати» (a fresh user gesture). Reset with the same epoch contract as
  // pdfConfirmPendingInstanceId (WF-12 parity); the URL is revoked so a
  // dropped preparation never leaks a stale report document.
  const [pdfFallbackPrepared, setPdfFallbackPrepared] = useState<{ instanceId: string | number; url: string } | null>(null);
  // Ref mirror of the still-pending prepared URL — the expiry timer and the
  // open action compare against it so a dead link can never be consumed.
  const pdfPreparedUrlRef = useRef<string | null>(null);
  useEffect(() => {
    setPdfConfirmPendingInstanceId(null);
    pdfPreparedUrlRef.current = null;
    setPdfFallbackPrepared((prepared) => {
      if (prepared) {
        URL.revokeObjectURL(prepared.url);
      }
      return null;
    });
  }, [activeInstance?.id]);

  function openPreparedPdf() {
    if (!pdfFallbackPrepared) return;
    if (pdfFallbackPrepared.instanceId !== (activeInstance?.id as string | number)) return;
    if (pdfPreparedUrlRef.current !== pdfFallbackPrepared.url) return;
    // Synchronous reservation inside THIS click gesture — no noopener
    // feature string, so null is a real blocked signal (CARDHIST-FE-001).
    const reserved = window.open('', '_blank');
    if (!reserved) {
      setPrintFeedback({ severity: 'warning', text: t('workbench.print_pdf_blocked') });
      return;
    }
    reserved.opener = null;
    reserved.location.href = pdfFallbackPrepared.url;
    pdfPreparedUrlRef.current = null;
    setPdfFallbackPrepared(null);
    // LABPRINT-FE-002: the opened PDF tab is NOT a physical print — only
    // the operator's explicit confirmation flips the status.
    setPdfConfirmPendingInstanceId(pdfFallbackPrepared.instanceId);
    setPrintFeedback({ severity: 'info', text: t('workbench.print_pdf_opened_confirm') });
  }

  async function confirmPdfPrinted() {
    const targetInstanceId = pdfConfirmPendingInstanceId;
    if (targetInstanceId == null) return;
    const operation = captureOperationContext();
    setBusyAction('print');
    try {
      let printed: Record<string, unknown>;
      try {
        printed = (await labReportingApi.markPrinted(targetInstanceId)) as Record<string, unknown>;
      } catch (markError) {
        logger.error('[LabReportWorkbench] confirmed PDF print status update failed', markError);
        setPrintFeedback({ severity: 'error', text: t('workbench.print_status_failed') });
        notify?.('error', t('workbench.print_status_failed'));
        return;
      }
      setPdfConfirmPendingInstanceId(null);
      const accepted = onInstanceChange?.(printed, {
        kind: 'update',
        expectedInstanceId: targetInstanceId,
        operation,
      }) !== false;
      if (!accepted) return;
      await onRefreshHistory?.(printed.patient_id as string | number);
      await onRefreshRecentReports?.();
      await onQueueChanged?.();
      setPrintFeedback({ severity: 'success', text: t('workbench.print_marked') });
      if (printFeedbackTimerRef.current) {
        clearTimeout(printFeedbackTimerRef.current);
        printFeedbackTimerRef.current = null;
      }
      printFeedbackTimerRef.current = setTimeout(() => {
        setPrintFeedback(null);
        printFeedbackTimerRef.current = null;
      }, 5000);
    } finally {
      setBusyAction((current) => (current === 'print' ? '' : current));
    }
  }

  const telegramReportId = String(activeInstance?.id ?? '');
  const telegramPatientId = String(activeInstance?.patient_id ?? '');
  const canNotifyPatient = Boolean(telegramReportId && telegramPatientId)
    && (activeInstance?.status === 'FINALIZED' || activeInstance?.status === 'PRINTED');
  const telegramFeedbackState = telegramFeedback?.reportId === telegramReportId
    && telegramFeedback.patientId === telegramPatientId
    && operationContextsMatch(telegramFeedback.operation, operationContextRef.current)
    ? telegramFeedback.state
    : 'manual';

  async function handleNotifyPatient() {
    if (!activeInstance || !canNotifyPatient || saving || instanceTransitionPending || telegramAttemptRef.current) return;
    const operation = captureOperationContext();
    const attempt = Symbol();
    telegramAttemptRef.current = attempt;
    const feedbackScope = { reportId: telegramReportId, patientId: telegramPatientId, operation };
    const stillCurrent = () => telegramAttemptRef.current === attempt
      && String(visibleReportRef.current?.id ?? '') === feedbackScope.reportId
      && String(visibleReportRef.current?.patient_id ?? '') === feedbackScope.patientId
      && operationContextsMatch(operation, operationContextRef.current)
      && isOperationCurrent(operation);
    let started = false;

    try {
      const ok = await confirm({
        title: t('confirm.notify_title'),
        message: t('confirm.notify_message'),
        description: t('confirm.notify_description'),
        confirmLabel: t('confirm.notify_confirm'),
        cancelLabel: t('confirm.cancel'),
        intent: 'warning',
      });
      if (!ok) return;
      if (!stillCurrent()) return;

      started = true;
      setSaving(true);
      setBusyAction('notify');
      setTelegramFeedback({ ...feedbackScope, state: 'pending' });
      const response = await api.post('/telegram/send-lab-report-instance', {
        patient_id: activeInstance.patient_id,
        report_instance_id: activeInstance.id,
      });
      if (!stillCurrent()) return;

      const data: unknown = response?.data;
      const payload = data && typeof data === 'object'
        ? data as { success?: unknown; report_instance_id?: unknown; message?: unknown }
        : undefined;
      if (payload?.success === true
        && typeof payload.report_instance_id === 'number'
        && String(payload.report_instance_id) === feedbackScope.reportId) {
        setTelegramFeedback({ ...feedbackScope, state: 'sent' });
        notify?.('success', t('success.notified'));
        return;
      }

      if (payload?.success === false) {
        setTelegramFeedback({ ...feedbackScope, state: 'not_sent' });
        const reason = typeof payload.message === 'string' ? payload.message.trim() : '';
        notify?.('error', reason || t('errors.notify_not_delivered'));
        return;
      }

      setTelegramFeedback({ ...feedbackScope, state: 'unconfirmed' });
      notify?.('error', t('errors.notify_failed'));
    } catch (error) {
      if (started && stillCurrent()) {
        setTelegramFeedback({ ...feedbackScope, state: 'unconfirmed' });
        notify?.('error', getErrorMessage(error) || t('errors.notify_failed'));
      }
    } finally {
      if (telegramAttemptRef.current === attempt) {
        telegramAttemptRef.current = null;
        if (started) {
          setSaving(false);
          setBusyAction((current) => current === 'notify' ? '' : current);
        }
      }
    }
  }

  const assignmentPicker = allocationUnavailable ? (
    <Alert severity="warning">{t(`labWorkspace.hold_${holdReason}`)}</Alert>
  ) : requiresAssignment && (
    <fieldset className="lab-visit-assignment">
      <legend>{t('workbench.visit_service_assignment')}</legend>
      {serviceAssignments.map((service) => (
        <label key={service.id}>
          <input
            type="checkbox"
            aria-label={service.label}
            checked={assignedServices.includes(service.id)}
            disabled={saving || isDirty || instanceTransitionPending}
            onChange={(event) => {
              const checked = event.target.checked;
              setAssignedServices((current) => checked ? [...current, service.id] : current.filter((id) => id !== service.id));
            }}
          />
          {service.label}
        </label>
      ))}
    </fieldset>
  );

  function revealCoveredControl(event: FocusEvent<HTMLDivElement>) {
    const control = event.target;
    const { x, y, width, height } = control.getBoundingClientRect();
    const stickyRegion = document.elementFromPoint?.(x + width / 2, y + height / 2)
      ?.closest('.lab-order-identity, .lab-report-actions-dock');
    if (stickyRegion && !stickyRegion.contains(control)) {
      control.scrollIntoView({ block: 'center', inline: 'nearest' });
    }
  }

  return (
    <div style={{ display: 'grid', gap: 'var(--mac-spacing-4)' }}>
      <Card variant="filled" padding="none" style={{ overflow: 'clip' }}>
        <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: 'var(--mac-spacing-4)' }}>
          <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
            <FileText size={20} aria-hidden="true" />
            {t('workbench.title')}
          </CardTitle>
        </CardHeader>
        <CardContent
          onFocusCapture={revealCoveredControl}
          style={{ padding: 'var(--mac-spacing-4)', background: 'var(--mac-bg-secondary)', display: 'grid', gap: 'var(--mac-spacing-4)' }}>
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
              {!allocationUnavailable && !templateResolutionLoading && Boolean(templateResolution?.default_template) && (
                <Alert severity="info">
                  {t('workbench.recommended_report')}: <strong>{String(((templateResolution as Record<string, unknown> | null)?.default_template as Record<string, unknown> | undefined)?.name ?? '')}</strong>
                </Alert>
              )}
              {!templateResolutionLoading && ((templateResolution?.unmapped_service_codes as string[] | undefined)?.length ?? 0) > 0 && (
                <Alert severity={resolvedTemplates.length > 0 ? 'warning' : 'error'}>
                  {t('workbench.unmapped_services')}: {(templateResolution?.unmapped_service_codes as string[]).join(', ')}
                </Alert>
              )}
              {!allocationUnavailable && !templateResolutionLoading && templateHasBlockingGap && (
                <Alert severity="error">
                  {t('workbench.no_template_found')}
                  <br />
                  {t('workbench.no_template_hint')} {!allocationHold && t('workbench.no_template_escape')}
                  {!allocationHold && <div style={{ marginTop: 'var(--mac-spacing-2)' }}>
                    <Button
                      size="small"
                      variant="outline"
                      onClick={() => setEscapeHatchActive(true)}
                      disabled={instanceTransitionPending}
                    >
                      {t('workbench.show_all_templates')}
                    </Button>
                  </div>}
                </Alert>
              )}
              {/* WF-11 fix: warning когда escape hatch активен */}
              {!templateResolutionLoading && useUnassignedTemplate && (
                <Alert severity="warning">
                  {t('workbench.unassigned_template_warning')}
                </Alert>
              )}
              {!allocationUnavailable && !templateResolutionLoading && singleAllowedTemplate && !templateHasBlockingGap && (
                <Alert severity="info">
                  {t('workbench.single_template_found')} <strong>{String(singleAllowedTemplate.name ?? '')}</strong>. {t('workbench.click_create_to_open')}
                </Alert>
              )}
              {assignmentPicker}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 'var(--mac-spacing-3)', alignItems: 'end' }}>
                <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                  <span>{t(serviceContextPresent && !useUnassignedTemplate ? 'workbench.allowed_report' : 'workbench.report_template')}</span>
                  <select
                    className="macos-input"
                    value={allocationUnavailable ? '' : selectedTemplateId}
                    onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setSelectedTemplateId(event.target.value)}
                    disabled={instanceTransitionPending || templateResolutionLoading || templateHasBlockingGap || allocationUnavailable}
                  >
                    <option value="">{t('workbench.select_report_template')}</option>
                    {availableTemplateOptions.map((template) => (
                      <option key={template.id} value={template.id}>
                        {String(template.name ?? '')} ({String(template.family ?? '')})
                      </option>
                    ))}
                  </select>
                </label>
                <Button
                  variant="primary"
                  onClick={() => handleCreateInstance()}
                  disabled={saving || instanceTransitionPending || templateResolutionLoading || templateHasBlockingGap || !selectedTemplateId || missingAssignment}
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
                    <Badge variant={getLabStatusVariant(activeInstance.status as string)}>
                      {formatLabStatus(String(activeInstance.status ?? ''), t)}
                    </Badge>
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
                  <LabStatusStepper status={activeInstance.status as string} managed={activeInstance.managed_release === true} />
                </div>

{/* PR6: «Добавить бланк» — только серверно разрешённые шаблоны
                      (templateResolution.allowed_templates). Заблокировано при
                      isDirty: несохранённый черновик не теряется. Существующие
                      отчёты остаются в истории (reportHistory / недавние). */}
                  {selectedAppointment && !templateResolutionLoading && allowedTemplates.length > 0 && (
                    <Alert severity="info">
                      <span>{t('workbench.additional_report_heading')}</span>
                      <select
                        className="macos-input"
                        aria-label={t('workbench.additional_report_template')}
                        value={addBlankTemplateIdValue}
                        onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setAddBlankTemplateId(event.target.value)}
                        disabled={instanceTransitionPending || allocationUnavailable}
                      >
                        {allowedTemplates.map((template) => (
                          <option key={String(template.id)} value={String(template.id)}>
                            {String(template.name ?? '')} ({String(template.family ?? '')})
                          </option>
                        ))}
                      </select>
                      {assignmentPicker}
                      <Button
                        variant="outline"
                        size="small"
                        disabled={saving || isDirty || instanceTransitionPending || busyAction === 'create' || !addBlankTemplateIdValue
                          || missingAssignment}
                        title={isDirty ? t('workbench.additional_report_save_first') : undefined}
                        onClick={() => handleCreateInstance(addBlankTemplateIdValue)}
                      >
                        <FolderPlus size={14} aria-hidden="true" />
                        {t('workbench.additional_report_add')}
                      </Button>
                      {isDirty && (
                        <span>{t('workbench.additional_report_save_first_inline')}</span>
                      )}
                    </Alert>
                  )}
              </div>

              <ReportWorkflowPanel
                report={activeInstance}
                canSubmit={!hasMissingRequired}
                disabled={saving || instanceTransitionPending || isDirty || saveFailure != null}
                onReview={(action) => { void handleWorkflowCommand(action); }}
                onPrompt={openWorkflowPrompt}
              />

              {(canSaveDraft || saveFailure != null) && (
                <ReportSaveStatus
                  language={language}
                  saving={saving && busyAction === 'save'}
                  isDirty={isDirty}
                  lastSavedAt={lastSavedAt}
                  failure={saveFailure}
                  comparing={loadingConflict}
                  baseline={initialValues}
                  current={{ values: draftValues, signer: signerSnapshot, studyDate }}
                  comparison={conflictReport}
                  onRetry={() => { void handleSaveDraft(); }}
                  onCompare={() => { void loadConflictReport(); }}
                  onResolve={resolveDraftConflict}
                />
              )}

              {canEditActiveInstance && (
                <label className="lab-report-study-date">
                  {t('workbench.study_date')}
                  <Input
                    type="date"
                    value={studyDate}
                    disabled={!canEditVisibleInstance}
                    onChange={(event) => {
                      editSequenceRef.current += 1;
                      setStudyDate(event.target.value);
                    }}
                  />
                </label>
              )}

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
                        onChange={(event) => {
                          const value = event.target.value;
                          editSequenceRef.current += 1;
                          setSignerSnapshot((prev) => ({ ...prev, [key]: value }));
                        }}
                        // WF-09 fix: signer fields должны блокироваться на FINALIZED/PRINTED,
                        // иначе persistDraft вызовет updateInstance → 409 Conflict (silent failure).
                        disabled={!canEditVisibleInstance}
                      />
                    </label>
                  ))}
                </div>
              </details>

              {printFeedback && (
                <div>
                  <Alert severity={printFeedback.severity}>{printFeedback.text}</Alert>
                  {pdfConfirmPendingInstanceId == null
                    && pdfFallbackPrepared != null
                    && pdfFallbackPrepared.instanceId === (activeInstance?.id as string | number) && (
                    <Button
                      variant="primary"
                      size="default"
                      onClick={openPreparedPdf}
                    >
                      {t('workbench.print_pdf_open_action')}
                    </Button>
                  )}
                  {pdfConfirmPendingInstanceId != null && (
                    <Button
                      variant="primary"
                      size="default"
                      onClick={() => { void confirmPdfPrinted(); }}
                    >
                      {t('workbench.print_confirm_mark_printed')}
                    </Button>
                  )}
                </div>
              )}

              {((activeInstance.critical_findings as Array<Record<string, unknown>> | undefined)?.length ?? 0) > 0 && (
                <Alert severity="error" role="alert">  {/* PR-59: role=alert for screen readers */}
                  <div style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                    <strong>{t('workbench.critical_findings')}</strong>
                    {isDirty && <span>{t('workbench.critical_saved_snapshot')}</span>}
                    {(activeInstance.critical_findings as Array<Record<string, unknown>>).map((finding: Record<string, unknown>) => (
                      <div
                        key={`${String(finding.section_key ?? '')}-${String(finding.field_key ?? '')}`}
                        className="lab-critical-findings-row"
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
                            {t(getEvaluationLabelKey(finding))}
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
                acceptedValues={activeInstance.updated_at === initialValues.updatedAt ? initialValues.values : undefined}
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
              />
              <div className="lab-report-actions-dock">
                <LabReportActionsBar
                  saving={saving || instanceTransitionPending}
                  busyAction={busyAction ?? undefined}
                  canSaveDraft={canSaveDraft && saveFailure !== 'conflict'}
                  // WF-10 fix: Finalize disabled пока есть missing required fields.
                  canFinalize={canFinalizeWithValidation && !isDirty && !saveFailure
                    && !(activeInstance.release_holds as string[] | undefined)?.length}
                  canRevise={canRevise}
                  canPrint={canPrint}
                  canPreview={canPreview}
                  canNotify={canNotifyPatient}
                  onSaveDraft={handleSaveDraft}
                  onFinalize={handleFinalize}
                  onRevise={() => openWorkflowPrompt('revise')}
                  onPrint={handlePrint}
                  onNotify={handleNotifyPatient}
                  onPreview={handlePreviewPdf}
                />
                {canNotifyPatient && (
                  <small role="status">{t(TELEGRAM_FEEDBACK_KEYS[telegramFeedbackState])}</small>
                )}
                {/* WF-10 fix: inline-индикатор missing required fields.
                    Показываем сколько обязательных полей ещё не заполнено,
                    чтобы лаборант понимал, почему Finalize disabled. */}
                {/* PR-66 / Low-27: replaced plain text spans with Badge components */}
                {(canFinalize || hasLabReportAction(activeInstance, 'submit_review')) && hasMissingRequired && (
                  <Badge variant="warning" style={{ marginLeft: 'var(--mac-spacing-2)' }}>
                    {t('workbench.required_remaining', { count: missingRequiredFields.length })}
                  </Badge>
                )}
              </div>
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
      {workflowPrompt && (
        <ReportWorkflowDialog
          key={workflowPrompt.action}
          action={workflowPrompt.action}
          saving={saving}
          onClose={() => setWorkflowPrompt(null)}
          onSubmit={(details) => { void handleWorkflowCommand(workflowPrompt.action, details); }}
        />
      )}
    </div>
  );
}

