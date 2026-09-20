import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Alert, Badge, Button, Card, CardContent, CardHeader } from '../components/ui/macos';
import LabQueueWorkbench from '../components/laboratory/LabQueueWorkbench';
import LabReportWorkbench, {
  type LabInstanceChangeContext,
  type LabReportOperationContext,
} from '../components/laboratory/LabReportWorkbench';
import LabTemplateWorkbench from '../components/laboratory/LabTemplateWorkbench';
import { useDirtyTransitionGuard } from '../components/laboratory/hooks/useDirtyTransitionGuard';
import { formatLabStatus } from '../components/laboratory/labUiLabels';
import { labReportingApi } from '../api/labReporting';
import { getErrorMessage } from '../utils/errorHandler';
import logger from '../utils/logger';
import { useSessionTimeoutWarning } from '../hooks/useSessionTimeoutWarning';
import { useLabHotkeys } from '../hooks/useLabHotkeys';
import notifyService from '../services/notify';
import './lab.css';
import { useTranslation } from '../i18n/useTranslation';
import { BriefcaseMedical, FileText, RotateCw, SquareStack, TestTube2, X } from 'lucide-react';

// P-03 fix: API_V1_BASE и tokenManager больше не нужны — loadLabAppointments
// использует labReportingApi.listQueueToday() с собственным auth-токеном.

const LAB_PANEL_TITLE_ID = 'lab-panel-title';
const LAB_PANEL_TABLIST_ID = 'lab-panel-tabs';

// STRAT#7: размер страницы для server-side pagination очереди.
// 50 записей — баланс между network overhead и UX (минимум прокруток).
// Backend maximum — 500 (Query(ge=1, le=500)).
const LAB_QUEUE_PAGE_SIZE = 50;

function getLabPanelTabId(tabId: string) {
  return `lab-panel-tab-${tabId}`;
}

function getLabPanelTabPanelId(tabId: string) {
  return `lab-panel-tabpanel-${tabId}`;
}

function normalizeListPayload(payload: unknown): Record<string, unknown>[] {
  if (Array.isArray(payload)) {
    return payload as Record<string, unknown>[];
  }
  const obj = (payload || {}) as Record<string, unknown>;
  if (Array.isArray(obj?.items)) {
    return obj.items as Record<string, unknown>[];
  }
  if (Array.isArray(obj?.results)) {
    return obj.results as Record<string, unknown>[];
  }
  if (Array.isArray(obj?.data)) {
    return obj.data as Record<string, unknown>[];
  }
  return [];
}

function isAbortLikeError(error: unknown) {
  const err = error as Record<string, unknown> | null | undefined;
  const name = String(err?.name || '').toLowerCase();
  const message = String(err?.message || '').toLowerCase();
  return name === 'aborterror' || message.includes('aborted');
}

function instanceIdsMatch(
  left: string | number | null | undefined,
  right: string | number | null | undefined,
) {
  if (left == null || right == null) {
    return left == null && right == null;
  }
  return String(left) === String(right);
}

function getInstancePatientId(instance: Record<string, unknown> | null) {
  return (
    instance?.patient_id
    ?? (instance?.patient_snapshot as Record<string, unknown> | undefined)?.patient_id
    ?? null
  ) as string | number | null;
}

function getAppointmentSelectionKey(appointment: Record<string, unknown> | null) {
  if (!appointment) return null;
  if (appointment.appointment_id != null) return `appointment:${String(appointment.appointment_id)}`;
  if (appointment.id != null) return `row:${String(appointment.id)}`;
  if (appointment.visit_id != null) return `visit:${String(appointment.visit_id)}`;
  if (appointment.patient_id != null) return `patient:${String(appointment.patient_id)}`;
  return null;
}

function appointmentMatchesInstance(
  appointment: Record<string, unknown>,
  instance: Record<string, unknown>,
) {
  const patientId = getInstancePatientId(instance);
  if (!instanceIdsMatch(appointment.patient_id as string | number | null | undefined, patientId)) {
    return false;
  }
  if (
    appointment.report_instance_id != null
    && instance.id != null
    && instanceIdsMatch(
      appointment.report_instance_id as string | number,
      instance.id as string | number,
    )
  ) {
    return true;
  }
  return appointment.visit_id != null
    && instance.visit_id != null
    && instanceIdsMatch(
      appointment.visit_id as string | number,
      instance.visit_id as string | number,
    );
}

function buildTemplateResolutionPayload(appointment: Record<string, unknown> | null) {
  if (!appointment) {
    return null;
  }
  const serviceDetails = (appointment.service_details || []) as Array<Record<string, unknown>>;
  return {
    patient_id: appointment.patient_id || null,
    appointment_id: appointment.appointment_id || null,
    visit_id: appointment.visit_id || null,
    service_codes: appointment.service_codes || [],
    service_items: serviceDetails.map((item) => ({
      service_id: item.id || null,
      code: item.code || null,
      name: item.name || null
    }))
  };
}

function getTemplateResolutionContextKey(appointment: Record<string, unknown> | null) {
  return JSON.stringify(buildTemplateResolutionPayload(appointment));
}

export default function LabPanel() {
  const { t: rawT } = useTranslation();
  const t = rawT;
  const tabs = [
    { id: 'queue', label: t('misc.lp_ochered'), icon: TestTube2 },
    { id: 'templates', label: t('misc.lp_shablony'), icon: SquareStack },
    { id: 'reports', label: t('misc.lp_otchety'), icon: FileText },
  ];
  const location = useLocation();
  const navigate = useNavigate();
  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const instanceParam = searchParams.get('instance');
  const parsedInstanceParam = instanceParam == null ? null : Number.parseInt(instanceParam, 10);
  const instanceParamId = parsedInstanceParam != null && !Number.isNaN(parsedInstanceParam)
    ? parsedInstanceParam
    : null;

  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'queue');
  const [appointments, setAppointments] = useState<Record<string, unknown>[]>([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  // STRAT#7: server-side pagination state для очереди.
  // queueTotal — общее количество записей на сервере (из payload.total).
  // queueOffset — текущий offset для следующей страницы.
  // hasMoreQueue — флаг, есть ли ещё записи для load-more.
  const [queueTotal, setQueueTotal] = useState(0);
  const [queueOffset, setQueueOffset] = useState(0);
  const [hasMoreQueue, setHasMoreQueue] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  // STRAT#16: ref для AbortController очереди — отменяет предыдущий
  // запрос при быстром повторном вызове loadLabAppointments.
  const queueAbortControllerRef = useRef<AbortController | null>(null);
  // STRAT#16: отдельный ref для load-more запросов.
  const loadMoreAbortControllerRef = useRef<AbortController | null>(null);
  const [templates, setTemplates] = useState<Record<string, unknown>[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<Record<string, unknown> | null>(null);
  const [templateTransitionPending, setTemplateTransitionPending] = useState(false);
  const selectedTemplateRef = useRef<Record<string, unknown> | null>(selectedTemplate);
  const selectedTemplateIdRef = useRef<string | number | null>(null);
  const templateRequestEpochRef = useRef(0);
  const [selectedAppointment, setSelectedAppointment] = useState<Record<string, unknown> | null>(null);
  const selectedAppointmentRef = useRef<Record<string, unknown> | null>(selectedAppointment);
  const appointmentsRef = useRef<Record<string, unknown>[]>(appointments);
  const [reportHistory, setReportHistory] = useState<Record<string, unknown>[]>([]);
  const [recentReports, setRecentReports] = useState<Record<string, unknown>[]>([]);
  const [activeInstance, setActiveInstance] = useState<Record<string, unknown> | null>(null);
  const [instanceTransitionPending, setInstanceTransitionPending] = useState(false);
  const activeInstanceId = (activeInstance?.id as string | number | null | undefined) ?? null;
  const activeInstanceRef = useRef<Record<string, unknown> | null>(activeInstance);
  const activeInstanceIdRef = useRef<string | number | null>(activeInstanceId);
  const activeInstancePatientIdRef = useRef<string | number | null>(
    getInstancePatientId(activeInstance),
  );
  const selectedAppointmentPatientIdRef = useRef<string | number | null>(
    (selectedAppointment?.patient_id as string | number | null | undefined) ?? null,
  );
  const instanceParamRef = useRef<string | null>(instanceParam);
  const locationSearchRef = useRef(location.search);
  activeInstanceIdRef.current = activeInstanceId;
  activeInstancePatientIdRef.current = getInstancePatientId(activeInstance);
  selectedAppointmentRef.current = selectedAppointment;
  appointmentsRef.current = appointments;
  selectedAppointmentPatientIdRef.current =
    (selectedAppointment?.patient_id as string | number | null | undefined) ?? null;
  instanceParamRef.current = instanceParam;
  locationSearchRef.current = location.search;
  activeInstanceRef.current = activeInstance;
  // Internal state changes and URL restoration are two directions of the same
  // contract. The pending object deliberately represents `targetId: null` too:
  // clearing a report must suppress restoration from the previous URL value.
  const instanceRequestSequenceRef = useRef(0);
  const labOperationEpochRef = useRef(0);
  const activeInstanceEpochRef = useRef(0);
  const pendingInstanceUrlSyncRef = useRef<{
    targetId: string | number | null;
    requestId: number;
    sourceUrlId: string | number | null;
  } | null>(null);
  const pendingUrlIntentRef = useRef<{ targetId: string | number | null } | null>(null);
  const getReportOperationContext = useCallback((): LabReportOperationContext => {
    const appointment = selectedAppointmentRef.current;
    const instanceId = activeInstanceIdRef.current;
    return {
      epoch: labOperationEpochRef.current,
      selectionKey: instanceId != null
        ? `instance:${String(instanceId)}`
        : getAppointmentSelectionKey(appointment),
      patientId: (
        appointment?.patient_id
        ?? activeInstancePatientIdRef.current
        ?? null
      ) as string | number | null,
    };
  }, []);
  const [templateResolution, setTemplateResolution] = useState<Record<string, unknown> | null>(null);
  const [templateResolutionLoading, setTemplateResolutionLoading] = useState(false);
  const templateResolutionRequestRef = useRef(0);
  // QW-4 fix: message теперь содержит опциональный retryAction — функцию,
  // которая вызывается при клике «Повторить» в Alert. Раньше ошибки
  // показывались на 5 секунд без возможности восстановиться — пользователь
  // переключал таб и не видел сообщения. Теперь:
  //   - errors показываются 12 секунд (вместо 5)
  //   - info/success — 5 секунд (как раньше)
  //   - error с retryAction показывает кнопку «Повторить»
  //   - любой клик по Alert закрывает его
  const [message, setMessage] = useState<{
    text?: string;
    type?: string;
    retryAction?: (() => boolean | void | Promise<unknown>) | null;
    [k: string]: unknown;
  }>({});

  const notify = useCallback((type: string, text: string, options: Record<string, unknown> = {}) => {
    setMessage({
      type,
      text,
      retryAction: typeof options.retryAction === 'function'
        ? (options.retryAction as () => boolean | void | Promise<unknown>)
        : null,
      retryLabel: options.retryLabel || t('misc.lp_povtorit'),
    });
  }, []);

  const dismissMessage = useCallback(() => {
    setMessage({ type: '', text: '', retryAction: null, retryLabel: '' });
  }, []);

  // H-1 fix: session timeout warning — prevents silent JWT expiry while
  // a lab technician is mid-fill on a long report. Mirrors the pattern
  // used in CardiologistPanel/DentistPanel/DermatologistPanel.
  const [sessionWarning, setSessionWarning] = useState<Record<string, unknown> | null>(null);

  // L-M-2 fix: ref-guard для дедупликации loadReportHistory.
  // Раньше loadReportHistory вызывался дважды: один раз из loadInstance
  // (когда instance.patient_snapshot.patient_id становился известен),
  // второй — из useEffect [selectedAppointment] ниже. Теперь ref хранит
  // patient_id для которого история уже загружена, и useEffect пропускает
  // повторный вызов если patient_id совпадает.
  const loadedHistoryForPatientRef = useRef<string | number | null>(null);
  const reportHistoryRequestRef = useRef(0);
  const recentReportsRequestRef = useRef(0);
  useSessionTimeoutWarning({
    onWarning: () => setSessionWarning({ active: true }),
    onExpired: () => {
      setSessionWarning(null);
      notifyService.error(t('misc.lp_sessiya_istekla_pozhaluysta_'));
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    },
  });

  const mergeResolvedVisitIntoState = useCallback((appointmentId: string | number, visitId: string | number) => {
    if (!appointmentId || !visitId) {
      return;
    }
    setAppointments((current) => {
      const next = current.map((item) =>
        item.appointment_id === appointmentId && !item.visit_id
          ? { ...item, visit_id: visitId }
          : item
      );
      appointmentsRef.current = next;
      return next;
    });
    setSelectedAppointment((current) => {
      if (!current || current.appointment_id !== appointmentId || current.visit_id) {
        return current;
      }
      const next = { ...current, visit_id: visitId };
      selectedAppointmentRef.current = next;
      return next;
    });
  }, []);

  useEffect(() => {
    const nextTab = searchParams.get('tab');
    if (!nextTab) {
      return;
    }
    if (nextTab !== activeTab) {
      setActiveTab(nextTab);
    }
  }, [activeTab, searchParams]);

  const switchTab = useCallback((tabId: string) => {
    setActiveTab(tabId);
    // WF-15 fix: сохраняем patient/instance в URL при переключении таба.
    const params = new URLSearchParams(locationSearchRef.current);
    params.set('tab', tabId);
    const query = params.toString();
    locationSearchRef.current = query ? `?${query}` : '';
    navigate(`/lab${query ? `?${query}` : ''}`, { replace: true });
  }, [navigate]);

  const syncUrlToCurrentContext = useCallback(() => {
    const params = new URLSearchParams(locationSearchRef.current);
    const currentAppointment = selectedAppointmentRef.current;
    const currentInstanceId = activeInstanceIdRef.current;
    if (currentAppointment?.patient_id != null) {
      params.set('patient', String(currentAppointment.patient_id));
    } else {
      params.delete('patient');
    }
    if (currentInstanceId != null) {
      params.set('instance', String(currentInstanceId));
    } else {
      params.delete('instance');
    }
    const query = params.toString();
    navigate(`/lab${query ? `?${query}` : ''}`, { replace: true });
  }, [navigate]);

  const handleTabKeyDown = useCallback((event: React.KeyboardEvent, tabId: string) => {
    const currentIndex = tabs.findIndex((tab) => tab.id === tabId);
    if (currentIndex === -1) {
      return;
    }

    const keyOffsets: Record<string, number> = {
      ArrowRight: 1,
      ArrowDown: 1,
      ArrowLeft: -1,
      ArrowUp: -1
    };

    let nextIndex: number | null = null;
    if (event.key === 'Home') {
      nextIndex = 0;
    } else if (event.key === 'End') {
      nextIndex = tabs.length - 1;
    } else if (keyOffsets[event.key]) {
      nextIndex = (currentIndex + keyOffsets[event.key] + tabs.length) % tabs.length;
    }

    if (nextIndex === null) {
      return;
    }

    event.preventDefault();
    const nextTab = tabs[nextIndex];
    switchTab(nextTab.id);
    window.requestAnimationFrame(() => {
      document.getElementById(getLabPanelTabId(nextTab.id))?.focus();
    });
  }, [switchTab]);

  const bindAppointmentForActiveInstance = useCallback((entries: Record<string, unknown>[]) => {
    if (selectedAppointmentRef.current != null) return false;
    const currentInstance = activeInstanceRef.current;
    if (!currentInstance) return false;
    const currentInstanceId = currentInstance.id as string | number | null | undefined;
    const matchingAppointment = entries.find((item) => (
      currentInstanceId != null
      && item.report_instance_id != null
      && instanceIdsMatch(item.report_instance_id as string | number, currentInstanceId)
    )) ?? entries.find((item) => appointmentMatchesInstance(item, currentInstance)) ?? null;
    if (!matchingAppointment) return false;
    selectedAppointmentRef.current = matchingAppointment;
    selectedAppointmentPatientIdRef.current = (
      matchingAppointment.patient_id as string | number | null | undefined
    ) ?? null;
    templateResolutionRequestRef.current += 1;
    setTemplateResolution(null);
    setTemplateResolutionLoading(true);
    setSelectedAppointment(matchingAppointment);
    return true;
  }, []);

  const refreshSelectedAppointmentFromEntries = useCallback((entries: Record<string, unknown>[]) => {
    const current = selectedAppointmentRef.current;
    if (!current) return false;
    const refreshed = entries.find(
      (item) =>
        item.id === current.id
        || (current.appointment_id && item.appointment_id === current.appointment_id)
    );
    if (!refreshed) return false;
    selectedAppointmentRef.current = refreshed;
    selectedAppointmentPatientIdRef.current = (
      refreshed.patient_id as string | number | null | undefined
    ) ?? null;
    if (getTemplateResolutionContextKey(refreshed) !== getTemplateResolutionContextKey(current)) {
      templateResolutionRequestRef.current += 1;
      setTemplateResolution(null);
      setTemplateResolutionLoading(true);
    }
    setSelectedAppointment(refreshed);
    return true;
  }, []);

  const loadLabAppointments = useCallback(async () => {
    // STRAT#16: AbortController для отмены предыдущего запроса при
    // быстром повторном вызове (refresh, tab switch). Предотвращает
    // setState-after-unmount и race conditions.
    if (queueAbortControllerRef.current) {
      queueAbortControllerRef.current.abort();
    }
    const controller = new AbortController();
    queueAbortControllerRef.current = controller;

    setAppointmentsLoading(true);
    try {
      // P-03 fix: используем lab-specific façade endpoint вместо прямого
      // fetch к registrar endpoint. Façade имеет собственный контракт,
      // собственную RBAC и нормализует ответ в плоский формат — это убирает
      // жёсткую связку с registrar module и промежуточную нормализацию.
      //
      // STRAT#7: передаём { limit: LAB_QUEUE_PAGE_SIZE, offset: 0 } для
      // server-side pagination. Backend уже поддерживает limit/offset
      // (STRAT#4), но frontend ранее грузил все записи сразу. Теперь
      // initial load получает первые LAB_QUEUE_PAGE_SIZE=50 записей;
      // loadMoreAppointments() догружает следующие.
      //
      // STRAT#16: передаём signal для отмены запроса при быстром повторе.
      const payload = (await labReportingApi.listQueueToday(null, {
        limit: LAB_QUEUE_PAGE_SIZE,
        offset: 0,
        signal: controller.signal,
      })) as Record<string, unknown>;
      const queueEntries = normalizeListPayload(payload?.entries ?? []);
      appointmentsRef.current = queueEntries;
      setAppointments(queueEntries);
      const totalCount = typeof payload?.total === 'number' ? payload.total : queueEntries.length;
      setQueueTotal(totalCount);
      setQueueOffset(queueEntries.length);
      // STRAT#7: помечаем, есть ли ещё записи для load-more
      setHasMoreQueue(totalCount > queueEntries.length);
      if (!bindAppointmentForActiveInstance(queueEntries)) {
        refreshSelectedAppointmentFromEntries(queueEntries);
      }
      logger.info('[LabPanel] loaded lab queue entries', queueEntries.length);
    } catch (error) {
      // STRAT#16: не показываем error notification для отменённых запросов.
      if (isAbortLikeError(error)) return;
      logger.error('[LabPanel] loadLabAppointments failed', error);
      notify(
        'error',
        getErrorMessage(error, t('misc.lp_ne_udalos_zagruzit_laborator')),
        // QW-4 fix: кнопка «Повторить» в Alert.
        { retryAction: () => loadLabAppointments(), retryLabel: t('misc.lp_zagruzit_snova') }
      );
    } finally {
      setAppointmentsLoading(false);
    }
  }, [bindAppointmentForActiveInstance, notify, refreshSelectedAppointmentFromEntries]);

  // STRAT#7: loadMoreAppointments — incremental server-side pagination.
  // Догружает следующую страницу (offset = queueOffset) и аппендит к
  // существующему списку. Используется кнопкой «Показать ещё» в
  // LabQueueWorkbench (заменит client-side load-more из FIX#13).
  const loadMoreAppointments = useCallback(async () => {
    if (loadingMore || !hasMoreQueue) return;
    // STRAT#16: AbortController для load-more (аналогично loadLabAppointments).
    if (loadMoreAbortControllerRef.current) {
      loadMoreAbortControllerRef.current.abort();
    }
    const controller = new AbortController();
    loadMoreAbortControllerRef.current = controller;

    setLoadingMore(true);
    try {
      const payload = (await labReportingApi.listQueueToday(null, {
        limit: LAB_QUEUE_PAGE_SIZE,
        offset: queueOffset,
        signal: controller.signal,
      })) as Record<string, unknown>;
      const newEntries = normalizeListPayload(payload?.entries ?? []);
      appointmentsRef.current = [...appointmentsRef.current, ...newEntries];
      setAppointments((current) => [...current, ...newEntries]);
      if (!refreshSelectedAppointmentFromEntries(newEntries)) {
        bindAppointmentForActiveInstance(newEntries);
      }
      setQueueOffset((current) => current + newEntries.length);
      const totalCount = typeof payload?.total === 'number' ? payload.total : 0;
      setHasMoreQueue(totalCount > queueOffset + newEntries.length);
      logger.info('[LabPanel] loaded more lab queue entries', newEntries.length);
    } catch (error) {
      // STRAT#16: не показываем error notification для отменённых запросов.
      if (isAbortLikeError(error)) return;
      logger.error('[LabPanel] loadMoreAppointments failed', error);
      notify('error', getErrorMessage(error, t('misc.lp_ne_udalos_zagruzit_dopolnite')));
    } finally {
      setLoadingMore(false);
    }
  }, [
    bindAppointmentForActiveInstance,
    loadingMore,
    hasMoreQueue,
    queueOffset,
    notify,
    refreshSelectedAppointmentFromEntries,
  ]);

  // H-2 fix: keyboard shortcuts for tab switching, refresh, clear selection.
  // PR5: единый dirty-guard для переходов, уничтожающих введённый draft
  // (смена пациента/отчёта/шаблона, Escape, восстановление из URL).
  const {
    registerDirtySource,
    guardTransition: guardDirtyTransition,
    dismissPendingTransition,
    guardDialog,
    isDialogOpen,
  } = useDirtyTransitionGuard();
  const pendingOperationSourcesRef = useRef(new Set<string>());
  const setOperationSourcePending = useCallback((source: string, pending: boolean) => {
    if (pending) pendingOperationSourcesRef.current.add(source);
    else pendingOperationSourcesRef.current.delete(source);
  }, []);
  const handleReportOperationPendingChange = useCallback(
    (pending: boolean) => setOperationSourcePending('report', pending),
    [setOperationSourcePending],
  );
  const handleTemplateOperationPendingChange = useCallback(
    (pending: boolean) => setOperationSourcePending('template', pending),
    [setOperationSourcePending],
  );
  const guardTransition = useCallback((
    transition: () => void | Promise<void>,
    options?: { onCancel?: () => void | Promise<void> },
  ) => {
    if (pendingOperationSourcesRef.current.size > 0) {
      notify('info', t('workbench.saving'));
      void options?.onCancel?.();
      return false;
    }
    return guardDirtyTransition(transition, options);
  }, [guardDirtyTransition, notify]);

  useEffect(() => {
    selectedTemplateIdRef.current = (selectedTemplate?.id as string | number | null | undefined) ?? null;
  }, [selectedTemplate]);

  useLabHotkeys({
    switchTab,
    refreshData: loadLabAppointments,
    clearSelection: () => guardTransition(() => {
      labOperationEpochRef.current += 1;
      selectedAppointmentRef.current = null;
      selectedAppointmentPatientIdRef.current = null;
      setSelectedAppointment(null);
      clearActiveInstance();
      switchTab('queue');
    }),
    disabled: isDialogOpen,
  });

  const loadTemplates = useCallback(async (preferredTemplateId: string | number | null = null) => {
    const requestEpoch = ++templateRequestEpochRef.current;
    const replacesEditableTemplate = selectedTemplateIdRef.current != null;
    if (replacesEditableTemplate) {
      setTemplateTransitionPending(true);
    }
    try {
      const summary = await labReportingApi.listTemplates() as Record<string, unknown>;
      if (requestEpoch !== templateRequestEpochRef.current) return;
      const templateSummary = normalizeListPayload(summary);
      setTemplates(templateSummary);
      const templateId = preferredTemplateId
        ?? selectedTemplateIdRef.current
        ?? (templateSummary[0]?.id as string | number | undefined)
        ?? null;
      if (templateId != null) {
        const detail = (await labReportingApi.getTemplate(templateId)) as Record<string, unknown>;
        if (requestEpoch !== templateRequestEpochRef.current) return;
        selectedTemplateIdRef.current = (detail?.id as string | number | null | undefined) ?? templateId;
        selectedTemplateRef.current = detail;
        setSelectedTemplate(detail);
      } else {
        if (requestEpoch !== templateRequestEpochRef.current) return;
        selectedTemplateIdRef.current = null;
        selectedTemplateRef.current = null;
        setSelectedTemplate(null);
      }
    } catch (error) {
      if (requestEpoch !== templateRequestEpochRef.current) return;
      if (isAbortLikeError(error)) {
        logger.info('[LabPanel] loadTemplates aborted');
        return;
      }
      logger.error('[LabPanel] loadTemplates failed', error);
      notify(
        'error',
        getErrorMessage(error, t('misc.lp_ne_udalos_zagruzit_shablony_')),
        // QW-4 fix: кнопка «Повторить» в Alert.
        {
          retryAction: () => guardTransition(async () => {
            dismissMessage();
            await loadTemplates(preferredTemplateId);
          }),
          retryLabel: t('misc.lp_zagruzit_snova'),
        }
      );
    } finally {
      if (requestEpoch === templateRequestEpochRef.current && replacesEditableTemplate) {
        setTemplateTransitionPending(false);
      }
    }
  // M-5 fix: removed selectedTemplate?.id from deps — it caused triple
  // re-fetch (loadLabAppointments + loadRecentReports + loadTemplates) every
  // time the user clicked a different template. Now reads selectedTemplate
  // via ref, so identity is stable and mount effect doesn't re-fire.
  }, [dismissMessage, guardTransition, notify]);

  const loadReportHistory = useCallback(async (patientId: string | number) => {
    if (!patientId) {
      reportHistoryRequestRef.current += 1;
      setReportHistory([]);
      return;
    }
    const belongsToCurrentContext = () => instanceIdsMatch(
      selectedAppointmentRef.current?.patient_id as string | number | null | undefined,
      patientId,
    ) || instanceIdsMatch(activeInstancePatientIdRef.current, patientId);
    if (!belongsToCurrentContext()) return;
    const requestId = ++reportHistoryRequestRef.current;
    try {
      const history = (await labReportingApi.listInstances({ patient_id: patientId, limit: 50 })) as Record<string, unknown>;
      if (requestId !== reportHistoryRequestRef.current || !belongsToCurrentContext()) return;
      setReportHistory(normalizeListPayload(history));
    } catch (error) {
      if (requestId !== reportHistoryRequestRef.current || !belongsToCurrentContext()) return;
      logger.error('[LabPanel] loadReportHistory failed', error);
      notify(
        'error',
        getErrorMessage(error, t('misc.lp_ne_udalos_zagruzit_istoriyu_')),
        // QW-4 fix: кнопка «Повторить» в Alert.
        { retryAction: () => loadReportHistory(patientId), retryLabel: t('misc.lp_zagruzit_snova') }
      );
    }
  }, [notify]);

  const loadRecentReports = useCallback(async () => {
    const requestId = ++recentReportsRequestRef.current;
    try {
      const instances = (await labReportingApi.listInstances({ limit: 50 })) as Record<string, unknown>;
      if (requestId !== recentReportsRequestRef.current) return;
      setRecentReports(normalizeListPayload(instances));
    } catch (error) {
      if (requestId !== recentReportsRequestRef.current) return;
      logger.error('[LabPanel] loadRecentReports failed', error);
      notify(
        'error',
        getErrorMessage(error, t('misc.lp_ne_udalos_zagruzit_spisok_la')),
        // QW-4 fix: кнопка «Повторить» в Alert.
        { retryAction: () => loadRecentReports(), retryLabel: t('misc.lp_zagruzit_snova') }
      );
    }
  }, [notify]);

  const loadTemplateResolution = useCallback(async (appointment: Record<string, unknown> | null) => {
    const requestId = ++templateResolutionRequestRef.current;
    if (!appointment) {
      setTemplateResolution(null);
      setTemplateResolutionLoading(false);
      return;
    }

    const payload = buildTemplateResolutionPayload(appointment);
    if (!payload) {
      setTemplateResolution(null);
      setTemplateResolutionLoading(false);
      return;
    }

    setTemplateResolutionLoading(true);
    try {
      const resolution = (await labReportingApi.resolveTemplateOptions(payload)) as Record<string, unknown>;
      if (requestId !== templateResolutionRequestRef.current) return;
      setTemplateResolution(resolution);
      const apptId = appointment?.appointment_id as string | number | undefined;
      const visitId = resolution?.visit_id as string | number | undefined;
      if (apptId && visitId && !appointment.visit_id) {
        mergeResolvedVisitIntoState(apptId, visitId);
      }
    } catch (error) {
      if (requestId !== templateResolutionRequestRef.current) return;
      logger.error('[LabPanel] loadTemplateResolution failed', error);
      setTemplateResolution(null);
      notify(
        'error',
        getErrorMessage(
          error,
          t('misc.lp_ne_udalos_opredelit_dostupny')
        )
      );
    } finally {
      if (requestId === templateResolutionRequestRef.current) {
        setTemplateResolutionLoading(false);
      }
    }
  }, [mergeResolvedVisitIntoState, notify]);

  const beginInstanceTransition = useCallback((
    targetId: string | number | null,
    options: { forcePending?: boolean; preserveOperationEpoch?: boolean } = {},
  ) => {
    const requestId = ++instanceRequestSequenceRef.current;
    if (!options.preserveOperationEpoch) {
      labOperationEpochRef.current += 1;
      setReportHistory([]);
    }
    // Invalidate any history response that belongs to the previous patient.
    reportHistoryRequestRef.current += 1;
    loadedHistoryForPatientRef.current = null;
    const stateAndUrlAlreadyMatch = instanceIdsMatch(activeInstanceIdRef.current, targetId)
      && instanceIdsMatch(instanceParamRef.current, targetId);
    pendingInstanceUrlSyncRef.current = !options.forcePending && stateAndUrlAlreadyMatch
      ? null
      : {
        targetId,
        requestId,
        sourceUrlId: instanceParamRef.current,
      };
    return requestId;
  }, []);

  const handleInstanceChange = useCallback((
    instance: Record<string, unknown>,
    change: LabInstanceChangeContext,
  ) => {
    const targetId = (instance?.id as string | number | null | undefined) ?? null;
    const resultPatientId = getInstancePatientId(instance);
    const currentOperation = getReportOperationContext();

    // A response belongs to the instance/patient that started the operation.
    // Late save/finalize/create responses must never supersede a newer patient
    // or report transition.
    const operationStillCurrent = (
      currentOperation.epoch !== change.operation.epoch
      || currentOperation.selectionKey !== change.operation.selectionKey
      || !instanceIdsMatch(currentOperation.patientId, change.operation.patientId)
    ) === false;
    if (!instanceIdsMatch(activeInstanceIdRef.current, change.expectedInstanceId)) return false;
    if (
      change.operation.patientId != null
      && resultPatientId != null
      && !instanceIdsMatch(change.operation.patientId, resultPatientId)
    ) return false;

    if (change.kind === 'update') {
      // A committed update may finish while a newer target GET is still
      // pending and the old instance remains visible. Reconcile that write,
      // but reject ABA responses after A was left and opened again.
      if (!operationStillCurrent && activeInstanceEpochRef.current !== change.operation.epoch) {
        return false;
      }
      if (!instanceIdsMatch(targetId, change.expectedInstanceId)) return false;
      activeInstanceRef.current = instance;
      activeInstanceEpochRef.current = change.operation.epoch;
      activeInstanceIdRef.current = targetId;
      activeInstancePatientIdRef.current = resultPatientId;
      setActiveInstance(instance);
      return true;
    }

    if (!operationStillCurrent) return false;

    beginInstanceTransition(targetId, { preserveOperationEpoch: true });
    setInstanceTransitionPending(false);
    activeInstanceRef.current = instance;
    activeInstanceEpochRef.current = labOperationEpochRef.current;
    activeInstanceIdRef.current = targetId;
    activeInstancePatientIdRef.current = resultPatientId;
    setActiveInstance(instance);
    return true;
  }, [beginInstanceTransition, getReportOperationContext]);

  const clearActiveInstance = useCallback(() => {
    beginInstanceTransition(null);
    setInstanceTransitionPending(false);
    activeInstanceRef.current = null;
    activeInstanceEpochRef.current = labOperationEpochRef.current;
    activeInstanceIdRef.current = null;
    activeInstancePatientIdRef.current = null;
    setActiveInstance(null);
  }, [beginInstanceTransition]);

  // PR5-review: «сырое» открытие отчёта без guard — вызывается ВНУТРИ уже
  // подтверждённого перехода (смена пациента), чтобы не запускать вложенный
  // guard и не оставлять частично изменённый контекст при отмене.
  const applyInstanceTransition = useCallback(async (
    instanceId: string | number,
    options: { clearCurrent?: boolean; urlIntent?: boolean } = {},
  ) => {
    setInstanceTransitionPending(true);
    const requestId = beginInstanceTransition(instanceId, {
      forcePending: options.clearCurrent,
    });
    if (options.clearCurrent) {
      activeInstanceRef.current = null;
      activeInstanceEpochRef.current = labOperationEpochRef.current;
      activeInstanceIdRef.current = null;
      activeInstancePatientIdRef.current = null;
      setActiveInstance(null);
    }
    try {
      const instance = (await labReportingApi.getInstance(instanceId)) as { patient_snapshot?: { patient_id?: string | number; [k: string]: unknown }; [k: string]: unknown };
      if (requestId !== instanceRequestSequenceRef.current) return;
      const resultPatientId = getInstancePatientId(instance);
      const currentAppointment = selectedAppointmentRef.current;
      if (!currentAppointment || !appointmentMatchesInstance(currentAppointment, instance)) {
        const matchingAppointment = appointmentsRef.current.find((appointment) => (
          appointmentMatchesInstance(appointment, instance)
        )) ?? null;
        selectedAppointmentRef.current = matchingAppointment;
        selectedAppointmentPatientIdRef.current = (
          matchingAppointment?.patient_id as string | number | null | undefined
        ) ?? null;
        setSelectedAppointment(matchingAppointment);
        setTemplateResolution(null);
        if (matchingAppointment) setTemplateResolutionLoading(true);
      }
      activeInstanceIdRef.current = (instance?.id as string | number | null | undefined) ?? instanceId;
      activeInstancePatientIdRef.current = resultPatientId;
      activeInstanceRef.current = instance;
      activeInstanceEpochRef.current = labOperationEpochRef.current;
      setActiveInstance(instance);
      setInstanceTransitionPending(false);
      const patientId = resultPatientId;
      if (patientId && !instanceIdsMatch(loadedHistoryForPatientRef.current, patientId)) {
        // L-M-2 fix: дедупликация loadReportHistory.
        // Сначала помечаем patient_id в loadedHistoryForPatientRef — это
        // предотвращает повторный вызов из useEffect [selectedAppointment]
        // ниже, который сработает когда setSelectedAppointment обновит состояние.
        loadedHistoryForPatientRef.current = patientId;
        await loadReportHistory(patientId);
      }
      if (requestId !== instanceRequestSequenceRef.current) return;
      setInstanceTransitionPending(false);
      switchTab('reports');
    } catch (error) {
      if (requestId !== instanceRequestSequenceRef.current) return;
      setInstanceTransitionPending(false);
      pendingInstanceUrlSyncRef.current = options.clearCurrent && instanceParamRef.current != null
        ? { targetId: null, requestId, sourceUrlId: instanceParamRef.current }
        : null;
      syncUrlToCurrentContext();
      const historyPatientId = (
        selectedAppointmentRef.current?.patient_id
        ?? activeInstancePatientIdRef.current
        ?? null
      ) as string | number | null;
      if (
        historyPatientId != null
        && !instanceIdsMatch(loadedHistoryForPatientRef.current, historyPatientId)
      ) {
        loadedHistoryForPatientRef.current = historyPatientId;
        void loadReportHistory(historyPatientId);
      }
      logger.error('[LabPanel] loadInstance failed', error);
      notify(
        'error',
        getErrorMessage(error, t('misc.lp_ne_udalos_otkryt_laboratorny'))
      );
    }
  }, [beginInstanceTransition, loadReportHistory, notify, switchTab, syncUrlToCurrentContext]);

  const loadInstance = useCallback((
    instanceId: string | number | null,
    options: { urlIntent?: boolean } = {},
  ) => {
    if (options.urlIntent) {
      pendingUrlIntentRef.current = { targetId: instanceId };
    }
    // PR5: публичный переход через dirty-guard (недавние отчёты,
    // восстановление ?instance=N из URL). Внутри подтверждённого перехода
    // используется applyInstanceTransition — подтверждение один раз.
    guardTransition(
      () => {
        if (options.urlIntent) {
          pendingUrlIntentRef.current = null;
        }
        if (instanceId == null) {
          clearActiveInstance();
          const patientId = selectedAppointmentRef.current?.patient_id as string | number | undefined;
          if (patientId != null) {
            loadedHistoryForPatientRef.current = patientId;
            void loadReportHistory(patientId);
          }
          switchTab('reports');
          return;
        }
        void applyInstanceTransition(instanceId, { urlIntent: options.urlIntent });
      },
      {
        onCancel: options.urlIntent ? () => {
          // Keep a rollback contract while React Router is still exposing the
          // cancelled external URL. Otherwise the restore effect observes it
          // once more and immediately opens a second dirty-state dialog.
          const requestId = ++instanceRequestSequenceRef.current;
          pendingInstanceUrlSyncRef.current = {
            targetId: activeInstanceIdRef.current,
            requestId,
            sourceUrlId: instanceParamRef.current,
          };
          pendingUrlIntentRef.current = null;
          syncUrlToCurrentContext();
        } : undefined,
      },
    );
  }, [
    guardTransition,
    applyInstanceTransition,
    clearActiveInstance,
    loadReportHistory,
    syncUrlToCurrentContext,
    switchTab,
  ]);

  // WF-15 fix: URL sync для patient/instance — shareable + back-button friendly.
  // При смене selectedAppointment или activeInstance обновляем URL params.
  useEffect(() => {
    // A URL intent waiting behind the shared dirty dialog owns the address bar
    // until the user decides. A late report mutation may update local state,
    // but must not erase that newer navigation request or dismiss its dialog.
    if (pendingUrlIntentRef.current) return;
    const pendingSync = pendingInstanceUrlSyncRef.current;
    if (
      pendingSync
      && !instanceIdsMatch(instanceParamId, pendingSync.sourceUrlId)
      && !instanceIdsMatch(instanceParamId, pendingSync.targetId)
    ) return;
    if (pendingSync && !instanceIdsMatch(activeInstanceId, pendingSync.targetId)) return;
    // A differing explicit URL id is navigation intent. Let the restore effect
    // guard and load it before state-to-URL synchronization writes anything.
    if (
      pendingSync == null
      && !instanceIdsMatch(activeInstanceId, instanceParamId)
    ) return;

    const params = new URLSearchParams(location.search);
    if (selectedAppointment?.patient_id) {
      params.set('patient', String(selectedAppointment.patient_id));
    } else {
      params.delete('patient');
    }
    if (activeInstanceId != null) {
      params.set('instance', String(activeInstanceId));
    } else {
      params.delete('instance');
    }
    // Только если params реально изменились —避免 лишних navigate
    const current = new URLSearchParams(location.search);
    if (params.toString() !== current.toString()) {
      navigate(`/lab?${params.toString()}`, { replace: true });
    }
  }, [activeInstanceId, instanceParamId, selectedAppointment, location.search, navigate]);

  // Initial data loaders are independent of URL changes. Keeping them in the
  // URL-restore effect re-fetched templates on every tab/query update and
  // re-hydrated over an unsaved template draft.
  useEffect(() => {
    loadLabAppointments();
    loadTemplates();
    loadRecentReports();
  }, [loadLabAppointments, loadRecentReports, loadTemplates]);

  // The virtualized queue is hidden while another tab is active. Refresh its
  // page when the user returns so it receives a new item array and measures
  // visible rows again. This preserves the prior queue-tab behavior without
  // reloading templates (which would overwrite a dirty template draft).
  const previousActiveTabRef = useRef(activeTab);
  useEffect(() => {
    const previousTab = previousActiveTabRef.current;
    previousActiveTabRef.current = activeTab;
    if (activeTab === 'queue' && previousTab !== 'queue') {
      loadLabAppointments();
    }
  }, [activeTab, loadLabAppointments]);

  // Restore only the instance URL contract. During an internal report switch,
  // the URL can briefly retain the old instance id; do not let that stale id
  // overwrite the report already selected by the user.
  useEffect(() => {
    const instanceId = instanceParamId;
    const pendingSync = pendingInstanceUrlSyncRef.current;

    if (pendingSync) {
      const urlMatchesPendingContract = instanceIdsMatch(instanceId, pendingSync.targetId)
        || instanceIdsMatch(instanceId, pendingSync.sourceUrlId);
      if (!urlMatchesPendingContract) {
        instanceRequestSequenceRef.current += 1;
        pendingInstanceUrlSyncRef.current = null;
        setInstanceTransitionPending(false);
        loadInstance(instanceId, { urlIntent: true });
        return;
      }
      if (
        instanceIdsMatch(instanceId, pendingSync.targetId)
        && instanceIdsMatch(activeInstanceId, pendingSync.targetId)
      ) {
        pendingInstanceUrlSyncRef.current = null;
      }
      return;
    }

    if (instanceIdsMatch(activeInstanceId, instanceId)) {
      if (pendingUrlIntentRef.current) {
        pendingUrlIntentRef.current = null;
        dismissPendingTransition();
      }
      return;
    }
    loadInstance(instanceId, { urlIntent: true });
  }, [activeInstanceId, dismissPendingTransition, instanceParamId, loadInstance]);

  // STRAT#16: cleanup — отменяем все pending запросы при unmount компонента.
  // Предотвращает setState-after-unmark warnings и network waste.
  useEffect(() => {
    return () => {
      if (queueAbortControllerRef.current) {
        queueAbortControllerRef.current.abort();
      }
      if (loadMoreAbortControllerRef.current) {
        loadMoreAbortControllerRef.current.abort();
      }
    };
  }, []);

  useEffect(() => {
    const patientId = selectedAppointment?.patient_id as string | number | undefined;
    if (patientId) {
      // L-M-2 fix: пропускаем повторный вызов если история уже загружена
      // для этого patient_id (вызвана из loadInstance).
      if (loadedHistoryForPatientRef.current !== patientId) {
        loadedHistoryForPatientRef.current = patientId;
        loadReportHistory(patientId);
      }
    } else {
      // Сброс ref при очистке выбора
      loadedHistoryForPatientRef.current = null;
    }
    loadTemplateResolution(selectedAppointment);
  }, [selectedAppointment, loadReportHistory, loadTemplateResolution]);

  useEffect(() => {
    if (!message.text) {
      return undefined;
    }
    // QW-4 fix: errors показываются дольше (12 сек), т.к. требуют внимания;
    // info/success — 5 сек. Если есть retryAction, не скрываем автоматически
    // (пользователь должен либо нажать «Повторить», либо закрыть вручную).
    if (message.retryAction) {
      return undefined;
    }
    const delay = message.type === 'error' ? 12000 : 5000;
    const timer = window.setTimeout(
      () => setMessage({ type: '', text: '', retryAction: null, retryLabel: '' }),
      delay
    );
    return () => window.clearTimeout(timer);
  }, [message]);

  const reportsCounter = selectedAppointment || activeInstance
    ? reportHistory.length
    : recentReports.length;

  const statusCounters = useMemo<Record<string, number>>(() => ({
    queue: appointments.length,
    templates: templates.length,
    reports: reportsCounter
  }), [appointments.length, reportsCounter, templates.length]);

  return (
    <main
      aria-labelledby={LAB_PANEL_TITLE_ID}
      className="lab-main"
    >
      {/* P-13 fix: skip-to-content link для keyboard-пользователей.
          Скрыт визуально, появляется при фокусе. Позволяет перескочить
          tablist и попасть прямо к содержимому активного таба. */}
      <a
        href={`#${LAB_PANEL_TABLIST_ID}`}
        className="lab-skip-link"
      >
        Перейти к навигации по табам
      </a>
      <Card variant="filled" padding="none">
        <CardHeader
          className="lab-card-header"
        >
          <div className="lab-flex-between-wrap">
            <h1
              id={LAB_PANEL_TITLE_ID}
              className="lab-panel-title"
            >
              <BriefcaseMedical size={22} aria-hidden="true" />
              <span>{t('misc.lp_panel_laboratorii')}</span>
            </h1>
            <div
              id={LAB_PANEL_TABLIST_ID}
              role="tablist"
              aria-labelledby={LAB_PANEL_TITLE_ID}
              className="lab-tablist"
            >
              {tabs.map((tab) => (
                <Button
                  key={tab.id}
                  id={getLabPanelTabId(tab.id)}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  aria-controls={getLabPanelTabPanelId(tab.id)}
                  aria-label={t('misc.lp_tab_label_statuscounters_tab', { label: tab.label, id: statusCounters[tab.id] })}
                  tabIndex={activeTab === tab.id ? 0 : -1}
                  variant={activeTab === tab.id ? 'primary' : 'outline'}
                  onClick={() => switchTab(tab.id)}
                  onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleTabKeyDown(event, tab.id)}
                >
                  <tab.icon size={16} aria-hidden="true" />
                  {tab.label}
                  <Badge
                    aria-hidden="true"
                    variant={activeTab === tab.id ? 'success' : 'info'}
                  >
                    {statusCounters[tab.id]}
                  </Badge>
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>
        {message.text && (
          <CardContent
            role={message.type === 'error' ? 'alert' : 'status'}
            aria-live={message.type === 'error' ? 'assertive' : 'polite'}
            className="lab-card-secondary"
          >
            {/* QW-4 fix: Alert с кнопками «Повторить» (если есть retryAction)
                и «Закрыть». Раньше Alert только показывал текст — теперь
                пользователь может восстановиться после ошибки одним кликом. */}
            <Alert
              severity={message.type === 'error' ? 'error' : 'info'}
              action={(
                <div className="lab-flex-center-8">
                  {message.retryAction && (
                    <Button
                      size="small"
                      variant="primary"
                      onClick={() => {
                        const action = message.retryAction;
                        if (typeof action === 'function') {
                          // A guarded retry returns false while its unsaved-
                          // changes dialog is pending. Keep the alert visible
                          // so Cancel does not remove the only retry action.
                          setTimeout(() => {
                            const started = action();
                            if (started !== false) dismissMessage();
                          }, 0);
                        }
                      }}
                    >
                      <RotateCw size={14} aria-hidden="true" />
                      {String(message.retryLabel || t('misc.lp_povtorit'))}
                    </Button>
                  )}
                  <Button
                    size="small"
                    variant="outline"
                    onClick={dismissMessage}
                    aria-label={t('misc.lp_zakryt_uvedomlenie')}
                  >
                    <X size={14} aria-hidden="true" />
                  </Button>
                </div>
              )}
            >
              {message.text}
            </Alert>
          </CardContent>
        )}
      </Card>

      {/* WF-14 fix: используем hidden вместо conditional render.
          Раньше activeTab === 'queue' && (...) размонтировало компонент
          при переключении — searchQuery и statusFilter терялись.
          Теперь все 3 секции смонтированы, скрытые через hidden —
          local state сохраняется. aria-hidden для accessibility. */}
      <section
        id={getLabPanelTabPanelId('queue')}
        role="tabpanel"
        aria-labelledby={getLabPanelTabId('queue')}
        tabIndex={0}
        hidden={activeTab !== 'queue'}
      >
        <LabQueueWorkbench
          appointments={appointments}
          loading={appointmentsLoading}
          onRefresh={loadLabAppointments}
          // STRAT#7: server-side pagination props
          onLoadMore={loadMoreAppointments}
          hasMore={hasMoreQueue}
          loadingMore={loadingMore}
          queueTotal={queueTotal}
          onOpenAppointment={(appointment) => {
            // PR5: смена пациента — переход через dirty-guard.
            guardTransition(() => {
              const nextAppointment = appointment as Record<string, unknown>;
              selectedAppointmentRef.current = nextAppointment;
              selectedAppointmentPatientIdRef.current = (
                nextAppointment.patient_id as string | number | null | undefined
              ) ?? null;
              setSelectedAppointment(nextAppointment);
              setTemplateResolution(null);
              setTemplateResolutionLoading(true);
              // WF-03 fix: если у пациента уже есть report_instance_id —
              // сразу открываем существующий отчёт, а не сбрасываем в режим
              // создания.
              const instanceId = appointment.report_instance_id as string | number | undefined;
              if (instanceId) {
                // Clear the previous patient's report before the async load.
                // Otherwise URL sync can combine the new patient with the old
                // instance id and restore that stale report over the result.
                void applyInstanceTransition(instanceId, { clearCurrent: true });
              } else {
                clearActiveInstance();
                switchTab('reports');
              }
            });
          }}
          selectedAppointment={selectedAppointment as Record<string, unknown> & { id?: string | number; patient_fio?: string; patient_phone?: string; patient_id?: string | number; visit_id?: string | number; appointment_time?: string; status?: string }}
          reportHistory={reportHistory as unknown as Array<Record<string, unknown> & { id: string | number; created_at: string; status: string; flagged_findings_count: number; critical_findings_count: number; max_flag_severity?: number }>}
        />
      </section>

      <section
        id={getLabPanelTabPanelId('templates')}
        role="tabpanel"
        aria-labelledby={getLabPanelTabId('templates')}
        tabIndex={0}
        hidden={activeTab !== 'templates'}
      >
        <LabTemplateWorkbench
          templates={templates}
          selectedTemplate={selectedTemplate}
          registerDirtySource={registerDirtySource}
          guardTransition={guardTransition}
          templateTransitionPending={templateTransitionPending}
          onOperationPendingChange={handleTemplateOperationPendingChange}
          onSelectTemplate={async (template) => {
            // PR5: смена шаблона — переход через dirty-guard.
            guardTransition(async () => {
              const templateId = (template as { id?: string | number })?.id;
              if (templateId == null) return;
              const requestEpoch = ++templateRequestEpochRef.current;
              const previousTemplate = selectedTemplateRef.current;
              const previousTemplateId = selectedTemplateIdRef.current;
              setTemplateTransitionPending(true);
              try {
                selectedTemplateIdRef.current = templateId;
                selectedTemplateRef.current = template as Record<string, unknown>;
                setSelectedTemplate(template as Record<string, unknown>);
                const loaded = (await labReportingApi.getTemplate(templateId)) as Record<string, unknown>;
                if (requestEpoch !== templateRequestEpochRef.current) return;
                selectedTemplateIdRef.current = (
                  loaded?.id as string | number | null | undefined
                ) ?? templateId;
                selectedTemplateRef.current = loaded;
                setSelectedTemplate(loaded);
              } catch (error) {
                if (requestEpoch !== templateRequestEpochRef.current) return;
                selectedTemplateIdRef.current = previousTemplateId;
                selectedTemplateRef.current = previousTemplate;
                setSelectedTemplate(previousTemplate);
                notify('error', getErrorMessage(error, t('misc.lp_ne_udalos_zagruzit_shablon_p')));
              } finally {
                if (requestEpoch === templateRequestEpochRef.current) {
                  setTemplateTransitionPending(false);
                }
              }
            });
          }}
          onTemplatesChanged={async (preferredTemplateId = null) => {
            await loadTemplates(preferredTemplateId);
          }}
          notify={notify}
        />
      </section>

      <section
        id={getLabPanelTabPanelId('reports')}
        role="tabpanel"
        aria-labelledby={getLabPanelTabId('reports')}
        tabIndex={0}
        hidden={activeTab !== 'reports'}
      >
        {/* WF-16 fix: breadcrumb навигация для wayfinding.
            Показывает путь: Очередь → Пациент → Отчёт #N (статус). */}
        {(selectedAppointment || activeInstance) && (
          <nav aria-label={t('misc.lp_navigatsiya')} className="lab-breadcrumb-nav">
            <button
              type="button"
              onClick={() => switchTab('queue')}
              className="lab-breadcrumb-link"
            >
              Очередь
            </button>
            {selectedAppointment && (
              <>
                <span>›</span>
                <span>{String(selectedAppointment.patient_fio || t('misc.lp_patsient_selectedappointment', { patient_id: selectedAppointment.patient_id }))}</span>
              </>
            )}
            {activeInstance && (
              <>
                <span>›</span>
                <span>
                  Отчёт #{String(activeInstance.id)}
                  <span className="lab-text-muted-ml">
                    ({formatLabStatus(activeInstance.status as string)})
                  </span>
                </span>
              </>
            )}
          </nav>
        )}
        <LabReportWorkbench
          selectedAppointment={selectedAppointment as unknown as null}
          templates={templates}
          templateResolution={templateResolution as unknown as null}
          templateResolutionLoading={templateResolutionLoading}
          reportHistory={reportHistory as unknown as never[]}
          recentReports={recentReports as unknown as never[]}
          registerDirtySource={registerDirtySource}
          onOperationPendingChange={handleReportOperationPendingChange}
          activeInstance={activeInstance as unknown as null}
          instanceTransitionPending={instanceTransitionPending}
          pauseAutoSave={isDialogOpen}
          getOperationContext={getReportOperationContext}
          onInstanceChange={handleInstanceChange}
          onOpenInstance={loadInstance}
          onRefreshHistory={loadReportHistory as unknown as (patientId: string | number) => Promise<void>}
          onRefreshRecentReports={loadRecentReports as unknown as undefined}
          onQueueChanged={loadLabAppointments as unknown as undefined}
          notify={notify}
        />
      </section>

              {/* PR5: единый dirty-guard диалог */}
        {guardDialog}
        {/* H-1 fix: session timeout warning dialog */}
        {sessionWarning && (
          <div
            role="alertdialog"
            aria-label={t('misc.lp_preduprezhdenie_ob_istecheni')}
            className="lab-session-warning-overlay"
          >
            <div className="lab-session-warning-dialog">
              <h3 className="lab-session-warning-title">
                Сессия скоро истечёт
              </h3>
              <p className="lab-session-warning-text">
                Ваша сессия истекает. Несохранённые данные могут быть потеряны.
                Сохраните текущий отчёт или продлите сессию.
              </p>
              <div className="lab-session-warning-actions">
                <button onClick={() => setSessionWarning(null)} className="lab-session-warning-btn-later">
                  Позже
                </button>
                <button onClick={() => { setSessionWarning(null); notifyService.info(t('misc.lp_prodlevaem_sessiyu')); }} className="lab-session-warning-btn-extend">
                  Продлить сессию
                </button>
              </div>
            </div>
          </div>
        )}
    </main>
  );
}
