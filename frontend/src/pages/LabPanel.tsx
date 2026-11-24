import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Alert, Badge, Button, Card, CardContent, CardHeader } from '../components/ui/macos';
import LabQueueWorkbench from '../components/laboratory/LabQueueWorkbench';
import LabSpecimenWorkbench from '../components/laboratory/LabSpecimenWorkbench';
import LabOrderIdentity from '../components/laboratory/LabOrderIdentity';
import LabOperationsWorkbench from '../components/laboratory/LabOperationsWorkbench';
import LabOrderedTests from '../components/laboratory/LabOrderedTests';
import LabReportWorkbench, {
  type LabInstanceChangeContext,
  type LabReportOperationContext,
} from '../components/laboratory/LabReportWorkbench';
import LabTemplateWorkbench from '../components/laboratory/LabTemplateWorkbench';
import type { DirtyGuardTransitionOptions } from '../components/laboratory/hooks/useDirtyTransitionGuard';
import { useLabDirtyGuard } from '../components/laboratory/LabDirtyGuardContext';
import { LAB_OPERATION_PENDING_ALL, type LabOperationPendingState } from '../components/laboratory/operationPending';
import { labReportingApi } from '../api/labReporting';
import { INITIAL_LAB_WORKLIST_QUERY, type LabWorklistPage, type LabWorklistQuery } from '../types/features/labWorkspace';
import { getErrorMessage } from '../utils/errorHandler';
import logger from '../utils/logger';
import { usePendingAwareSessionExpiry } from '../hooks/usePendingAwareSessionExpiry';
import { getTokenExpiryMs } from '../hooks/useSessionTimeoutWarning';
import { forceRefreshToken } from '../api/client';
import { useLabHotkeys } from '../hooks/useLabHotkeys';
import notifyService from '../services/notify';
import './lab.css';
import { useTranslation } from '../i18n/useTranslation';
import { BriefcaseMedical, FileText, ListChecks, RotateCw, SquareStack, TestTube2, X } from 'lucide-react';

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

// PR 3351: фактический instance param из ТЕКУЩЕГО адреса браузера.
// instanceParamRef обновляется только на рендере и может отставать от
// последнего navigate (например, быстрый второй клик пациента до
// popstate/render URL-записи первого перехода): тогда pendingSync получал
// sourceUrlId=null вместо реального id, restore effect считал свежий URL
// «чужим» и делал supersede НАЗАД к предыдущему отчёту. Для контрактов,
// описывающих адресную строку, нужен именно текущий URL, а не последний
// отрендеренный.
function getCurrentUrlInstanceId(fallback: string | null | undefined) {
  if (typeof window === 'undefined') return fallback ?? null;
  return new URLSearchParams(window.location.search).get('instance');
}

function getInstancePatientId(instance: Record<string, unknown> | null) {
  return (
    instance?.patient_id
    ?? (instance?.patient_snapshot as Record<string, unknown> | undefined)?.patient_id
    ?? null
  ) as string | number | null;
}

function getPositiveId(value: unknown): number | null {
  const id = typeof value === 'string' || typeof value === 'number' ? Number(value) : 0;
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

function getAppointmentSelectionKey(appointment: Record<string, unknown> | null) {
  if (!appointment) return null;
  if (appointment.order_id != null) return `order:${String(appointment.order_id)}`;
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
  if (patientId == null || !instanceIdsMatch(appointment.patient_id as string | number | null | undefined, patientId)) {
    return false;
  }
  if (appointment.order_id != null && instance.order_id != null) {
    return String(appointment.order_id) === String(instance.order_id);
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
  const activeDetails = serviceDetails.filter((item) => item.canceled !== true);
  return {
    patient_id: appointment.patient_id || null,
    appointment_id: appointment.appointment_id || null,
    visit_id: appointment.visit_id || null,
    service_codes: activeDetails.length === serviceDetails.length ? appointment.service_codes || [] : activeDetails.map((item) => item.code).filter(Boolean),
    service_items: activeDetails.map((item) => ({
      service_id: item.id || null,
      code: item.code || null,
      name: item.name || null
    }))
  };
}

function getTemplateResolutionContextKey(appointment: Record<string, unknown> | null) {
  return JSON.stringify(buildTemplateResolutionPayload(appointment));
}

// PR 3351 (review round 6, P2): canonical /lab без ?tab= — это вкладка
// очереди (defaultItem: 'queue' в routeRegistry). Синхронизация URL→state
// нормализует отсутствующий/неизвестный tab к дефолту: раньше Header brand
// и Command Palette делали replace на /lab, query удалялся, а activeTab
// оставался Templates — URL показывал одно (Queue после reload), экран —
// другое (Templates); адрес нельзя было ни сохранить, ни скопировать, ни
// восстановить.
const LAB_TAB_IDS = ['queue', 'templates', 'reports', 'operations'] as const;

function resolveLabTabId(requested: string | null): string {
  return (LAB_TAB_IDS as readonly string[]).includes(requested ?? '')
    ? (requested as string)
    : 'queue';
}

// Внешний URL с валидным ?tab= сам владеет видимой вкладкой; без него откат
// внешнего намерения возвращает пользователя на вкладку, активную ДО
// намерения (preUrlIntentTabRef — tab-sync effect мог уже закоммитить
// нормализацию «нет tab → queue», пока висел guard-диалог), а не на
// молчаливый default; последний рубеж — текущая вкладка, затем 'queue'.
function resolveRollbackTabId(
  urlTab: string | null,
  preIntentTab: string | null,
  currentTab: string,
): string {
  const knownTabs = LAB_TAB_IDS as readonly string[];
  if (urlTab != null && knownTabs.includes(urlTab)) {
    return urlTab;
  }
  if (preIntentTab != null && knownTabs.includes(preIntentTab)) {
    return preIntentTab;
  }
  return knownTabs.includes(currentTab) ? currentTab : 'queue';
}

export default function LabPanel() {
  const { t: rawT } = useTranslation();
  const t = rawT;
  const tabs = [
    { id: 'queue', label: t('misc.lp_ochered'), icon: TestTube2 },
    { id: 'templates', label: t('misc.lp_shablony'), icon: SquareStack },
    { id: 'reports', label: t('misc.lp_otchety'), icon: FileText },
    { id: 'operations', label: t('labWorkspace.operations'), icon: ListChecks },
  ];
  const location = useLocation();
  const navigate = useNavigate();
  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const instanceParam = searchParams.get('instance');
  const parsedInstanceParam = instanceParam == null ? null : Number.parseInt(instanceParam, 10);
  const instanceParamId = parsedInstanceParam != null && !Number.isNaN(parsedInstanceParam)
    ? parsedInstanceParam
    : null;

  const [activeTab, setActiveTab] = useState(() => resolveLabTabId(searchParams.get('tab')));
  const [operationsOpened, setOperationsOpened] = useState(false);
  useEffect(() => {
    if (activeTab === 'operations') setOperationsOpened(true);
  }, [activeTab]);
  // PR 3351 (review round 6, P2): render-time ref активной вкладки —
  // захват pre-intent вкладки в loadInstance читает значение ДО того, как
  // tab-sync effect закоммитит нормализацию (эффекты одного прохода
  // видят ещё старый state).
  const activeTabRef = useRef(activeTab);
  activeTabRef.current = activeTab;
  // Вкладка на момент прихода внешнего urlIntent (см. resolveRollbackTabId
  // и rollback-запись в syncUrlToCurrentContext). null — намерения нет,
  // откату нечего восстанавливать.
  const preUrlIntentTabRef = useRef<string | null>(null);
  const [appointments, setAppointments] = useState<Record<string, unknown>[]>([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [appointmentsError, setAppointmentsError] = useState(false);
  const worklistQueryRef = useRef<LabWorklistQuery>(INITIAL_LAB_WORKLIST_QUERY);
  const nextWorklistCursorRef = useRef<string | null>(null);
  const [worklistPage, setWorklistPage] = useState<LabWorklistPage | null>(null);
  const worklistAvailableRef = useRef(typeof labReportingApi.listWorklist === 'function');
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
  // LABQ-FE-001 (audit 3886): shared queue generation — every refresh opens
  // a new generation; load-more pages are owned by the generation they were
  // launched in, so a stale page can never append into a newer snapshot.
  const queueGenerationRef = useRef(0);
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
  // PR 3351 (review round 8, P1): внешний urlIntent, ОТЛОЖЕННЫЙ pending-
  // блоком (незавершённая операция в report-области). Отличает «намерение
  // ждёт завершения операций» (retry-эффект переподнимет его) от
  // «намерение ждёт решения пользователя в dirty-диалоге» (retry не
  // выполняется — диалогом владеет пользователь). Флаг ставится
  // onPendingBlock-ом guardTransition и снимается retry-эффектом.
  const urlIntentDeferredByPendingRef = useRef(false);
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
  // PR 3351 (review round 9, P2): «Продлить сессию» — РЕАЛЬНЫЙ refresh, а
  // не сокрытие предупреждения. Пока refresh в полёте, кнопка заблокирована;
  // неудача оставляет предупреждение ОТКРЫТЫМ с явной ошибкой.
  const [sessionExtending, setSessionExtending] = useState(false);
  const [sessionExtendError, setSessionExtendError] = useState<string | null>(null);
  const sessionDialogRef = useRef<HTMLDialogElement>(null);
  const sessionDialogTitleRef = useRef<HTMLHeadingElement>(null);
  const sessionDialogDescriptionId = useId();

  // PR 3351 (review round 9, P2): «Продлить сессию» — реальная операция
  // обновления, а не декоративное сокрытие предупреждения. Прежняя кнопка
  // только прятала overlay и показывала тост «продлеваем» — JWT оставался
  // прежним, повторное предупреждение для того же поколения больше не
  // срабатывало (warningFired), и через несколько минут сессия всё равно
  // истекала: контроль сообщал об успехе действия, которого не было.
  // Контракт: канонический single-flight refresh (forceRefreshToken — тот
  // же мьютекс, что у 401-recovery); предупреждение закрывается ТОЛЬКО
  // когда в sessionStorage появилось НОВОЕ значение access token с будущим
  // exp; при неудаче предупреждение остаётся открытым с явной ошибкой и
  // рекомендацией сохранить черновик и войти заново.
  const handleExtendSession = useCallback(async () => {
    if (sessionExtending) return;
    const tokenBefore = window.sessionStorage.getItem('auth_token');
    setSessionExtending(true);
    setSessionExtendError(null);
    try {
      const newToken = await forceRefreshToken();
      const tokenAfter = window.sessionStorage.getItem('auth_token');
      const renewed = Boolean(newToken)
        && tokenAfter !== null
        && tokenAfter !== tokenBefore
        && (getTokenExpiryMs(tokenAfter) ?? 0) > Date.now();
      if (renewed) {
        setSessionWarning(null);
        setSessionExtendError(null);
        notifyService.info(t('misc.lp_session_extended'));
      } else {
        setSessionExtendError(t('misc.lp_session_extend_failed'));
      }
    } catch {
      setSessionExtendError(t('misc.lp_session_extend_failed'));
    } finally {
      setSessionExtending(false);
    }
  }, [sessionExtending, t]);

  // L-M-2 fix: ref-guard для дедупликации loadReportHistory.
  // Раньше loadReportHistory вызывался дважды: один раз из loadInstance
  // (когда instance.patient_snapshot.patient_id становился известен),
  // второй — из useEffect [selectedAppointment] ниже. Теперь ref хранит
  // patient_id для которого история уже загружена, и useEffect пропускает
  // повторный вызов если patient_id совпадает.
  const loadedHistoryForPatientRef = useRef<string | number | null>(null);
  const reportHistoryRequestRef = useRef(0);
  const recentReportsRequestRef = useRef(0);

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
    // PR 3351 (review round 6, P2): отсутствующий/неизвестный ?tab=
    // нормализуется к default-вкладке Queue — URL /lab обязан означать
    // ровно то, что откроется после reload (раньше sync молча пропускал
    // «нет таба», и brand/palette рассинхронизировали адрес и экран).
    const requestedTab = searchParams.get('tab');
    const nextTab = resolveLabTabId(requestedTab);
    if (nextTab !== activeTab) {
      setActiveTab(nextTab);
    }
    // PR 3351 (review round 6, P2): URL снова явно владеет вкладкой —
    // память pre-intent вкладки (восстановление в rollback/WF-15)
    // закрывается, чтобы не протечь в будущие shell-переходы на
    // canonical /lab (brand = home = очередь, а не устаревший tab).
    if (requestedTab != null && (LAB_TAB_IDS as readonly string[]).includes(requestedTab)) {
      preUrlIntentTabRef.current = null;
    }
  }, [activeTab, searchParams]);

  // PR 3351: URL-запись строится от АКТУАЛЬНОГО поискового запроса
  // браузера, а не от замыкания location.search конкретного рендера:
  // пассивные эффекты прошлого рендера доливаются ПОСЛЕ нового navigate
  // (replaceState синхронен), и «сохранение» patient/instance из старой
  // базы затирало свежий tab=reports обратно на tab=queue, после чего
  // tab-sync effect возвращал пользователя на вкладку очереди.
  const currentSearchParams = useCallback(() => (
    typeof window === 'undefined'
      ? new URLSearchParams(locationSearchRef.current)
      : new URLSearchParams(window.location.search)
  ), []);
  // Последний query, написанный САМИМ приложением (navigate replace).
  // Различает «наш navigate ещё не отрендерен» (window опережает замыкание,
  // но совпадает с lastAppWrittenSearch — писать можно) и «внешний
  // pushState+popstate ещё не обработан роутером» (window не совпадает ни
  // с нашим последним запросом, ни с location рендера — писать нельзя,
  // restore effect обработает намерение после popstate-рендера).
  const lastAppWrittenSearchRef = useRef<string | null>(null);
  const navigateReplace = useCallback((query: string) => {
    lastAppWrittenSearchRef.current = query ? `?${query}` : '';
    locationSearchRef.current = query ? `?${query}` : '';
    navigate(`/lab${query ? `?${query}` : ''}`, { replace: true });
  }, [navigate]);

  const switchTab = useCallback((tabId: string) => {
    setActiveTab(tabId);
    // WF-15 fix: сохраняем patient/instance в URL при переключении таба.
    const params = currentSearchParams();
    params.set('tab', tabId);
    navigateReplace(params.toString());
  }, [currentSearchParams, navigateReplace]);

  const syncUrlToCurrentContext = useCallback(() => {
    const params = currentSearchParams();
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
    // PR 3351 (review round 6, P2): rollback-URL обязан явно владеть tab.
    // После нормализации «нет tab → queue» в tab-sync эффекте откат внешнего
    // намерения без явного tab молча переключал бы пользователя на вкладку
    // очереди (например: dirty report на /lab?tab=reports → внешний
    // /lab?instance=89 без tab → отмена → очередь вместо reports).
    // Приоритет: валидный tab адреса (внешний URL владеет вкладкой) →
    // вкладка до начала urlIntent → текущая вкладка → default 'queue'.
    params.set('tab', resolveRollbackTabId(
      params.get('tab'),
      preUrlIntentTabRef.current,
      activeTabRef.current,
    ));
    navigateReplace(params.toString());
  }, [currentSearchParams, navigateReplace]);

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
      && appointmentMatchesInstance(item, currentInstance)
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
      (item) => {
        if (item.order_id != null || current.order_id != null) {
          return item.order_id != null && current.order_id != null && String(item.order_id) === String(current.order_id);
        }
        return (current.id != null && item.id === current.id)
          || (current.appointment_id != null && item.appointment_id === current.appointment_id);
      }
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
    // LABQ-FE-001 (audit 3886): every refresh opens a NEW queue generation:
    // an in-flight load-more from an older generation must not append its
    // page into the freshly refreshed snapshot.
    queueGenerationRef.current += 1;
    const generation = queueGenerationRef.current;
    if (loadMoreAbortControllerRef.current) {
      loadMoreAbortControllerRef.current.abort();
    }
    if (queueAbortControllerRef.current) {
      queueAbortControllerRef.current.abort();
    }
    // LABQ-FE-004 (post-merge review of PR 3907, P2): the NEW generation
    // takes ownership of the incremental pagination flag. The aborted
    // page's finally is generation-guarded (LABQ-FE-002) and will NOT
    // release `loadingMore` — without this transfer the flag stays stuck
    // `true` forever after a refresh and the refreshed list can never
    // request further pages (pagination deadlock).
    setLoadingMore(false);
    const controller = new AbortController();
    queueAbortControllerRef.current = controller;

    setAppointmentsLoading(true);
    setAppointmentsError(false);
    try {
      let worklist: LabWorklistPage | null = null;
      if (worklistAvailableRef.current) {
        const query = worklistQueryRef.current;
        const loadedDepth = appointmentsRef.current.length;
        try {
          const firstPage = await labReportingApi.listWorklist(query, { signal: controller.signal });
          const entries = new Map(firstPage.entries.map((entry) => [entry.id, entry]));
          let remaining = loadedDepth - firstPage.entries.length;
          let cursor = firstPage.next_cursor;
          // Refresh the loaded window before replacing its visible rows. A
          // query change clears the window and still needs only the first page.
          while (cursor != null && remaining > 0) {
            if (queueGenerationRef.current !== generation) return;
            const page = await labReportingApi.listWorklist(query, { cursor, signal: controller.signal });
            page.entries.forEach((entry) => entries.set(entry.id, entry));
            remaining -= page.entries.length;
            cursor = page.next_cursor;
          }
          worklist = { ...firstPage, entries: [...entries.values()], next_cursor: cursor };
        } catch (error) {
          if (queueGenerationRef.current !== generation) return;
          const status = (error as { status?: number } | null)?.status;
          // During a staggered upgrade the old API exposes only today's queue.
          if (status !== 404 && status !== 405) throw error;
          worklistAvailableRef.current = false;
        }
      }
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
      const payload = worklist ?? (await labReportingApi.listQueueToday(null, {
        limit: LAB_QUEUE_PAGE_SIZE,
        offset: 0,
        signal: controller.signal,
      })) as Record<string, unknown>;
      // LABQ-FE-001: a newer generation owns the snapshot now — ignore this
      // completion entirely (an epoch guard, not only AbortController
      // cancellation: a request mock resolving despite abort() must not
      // resurrect the stale page).
      if (queueGenerationRef.current !== generation) {
        return;
      }
      const queueEntries = normalizeListPayload(payload?.entries ?? []);
      appointmentsRef.current = queueEntries;
      setAppointments(queueEntries);
      const totalCount = typeof payload?.total === 'number' ? payload.total : queueEntries.length;
      setQueueTotal(totalCount);
      setWorklistPage(worklist);
      nextWorklistCursorRef.current = worklist?.next_cursor ?? null;
      setQueueOffset(queueEntries.length);
      // STRAT#7: помечаем, есть ли ещё записи для load-more
      setHasMoreQueue(worklist ? worklist.next_cursor != null : totalCount > queueEntries.length);
      if (!bindAppointmentForActiveInstance(queueEntries)) {
        refreshSelectedAppointmentFromEntries(queueEntries);
      }
      logger.info('[LabPanel] loaded lab queue entries', queueEntries.length);
    } catch (error) {
      // STRAT#16: не показываем error notification для отменённых запросов.
      // LABQ-FE-001/002: a stale generation's failure is not the current
      // snapshot's failure.
      if (isAbortLikeError(error) || queueGenerationRef.current !== generation) return;
      setAppointmentsError(true);
      logger.error('[LabPanel] loadLabAppointments failed', error);
      notify(
        'error',
        getErrorMessage(error, t('misc.lp_ne_udalos_zagruzit_laborator')),
        // QW-4 fix: кнопка «Повторить» в Alert.
        { retryAction: () => loadLabAppointments(), retryLabel: t('misc.lp_zagruzit_snova') }
      );
    } finally {
      // LABQ-FE-002: an aborted/outdated request must not clear the NEWER
      // request's loading state — only the current generation may unset it.
      if (queueGenerationRef.current === generation) {
        setAppointmentsLoading(false);
      }
    }
  }, [bindAppointmentForActiveInstance, notify, refreshSelectedAppointmentFromEntries]);

  const changeWorklistQuery = useCallback((query: LabWorklistQuery) => {
    worklistQueryRef.current = query;
    appointmentsRef.current = [];
    setAppointments([]);
    setHasMoreQueue(false);
    void loadLabAppointments();
  }, [loadLabAppointments]);

  // STRAT#7: loadMoreAppointments — incremental server-side pagination.
  // Догружает следующую страницу (offset = queueOffset) и аппендит к
  // существующему списку. Используется кнопкой «Показать ещё» в
  // LabQueueWorkbench (заменит client-side load-more из FIX#13).
  const loadMoreAppointments = useCallback(async () => {
    if (loadingMore || !hasMoreQueue || appointmentsLoading) return;
    // LABQ-FE-001 (audit 3886): the page belongs to the CURRENT queue
    // generation — if a refresh opens a new one while this page is in
    // flight, its completion must not append into the newer snapshot.
    const generation = queueGenerationRef.current;
    // STRAT#16: AbortController для load-more (аналогично loadLabAppointments).
    if (loadMoreAbortControllerRef.current) {
      loadMoreAbortControllerRef.current.abort();
    }
    const controller = new AbortController();
    loadMoreAbortControllerRef.current = controller;

    setLoadingMore(true);
    try {
      const cursor = nextWorklistCursorRef.current;
      const worklist = cursor == null ? null : await labReportingApi.listWorklist(worklistQueryRef.current, {
        cursor, signal: controller.signal,
      });
      const payload = worklist ?? (await labReportingApi.listQueueToday(null, {
        limit: LAB_QUEUE_PAGE_SIZE,
        offset: queueOffset,
        signal: controller.signal,
      })) as Record<string, unknown>;
      // LABQ-FE-001: epoch guard — even a request that resolves despite
      // abort() must not append the stale page (and must not advance the
      // current offset/hasMore).
      if (queueGenerationRef.current !== generation) {
        return;
      }
      const newEntries = normalizeListPayload(payload?.entries ?? []);
      const seen = new Set(appointmentsRef.current.map((entry) => entry.id));
      const merged = [...appointmentsRef.current, ...newEntries.filter((entry) => !seen.has(entry.id))];
      appointmentsRef.current = merged;
      setAppointments(merged);
      if (!refreshSelectedAppointmentFromEntries(newEntries)) {
        bindAppointmentForActiveInstance(newEntries);
      }
      setQueueOffset((current) => current + newEntries.length);
      const totalCount = typeof payload?.total === 'number' ? payload.total : 0;
      nextWorklistCursorRef.current = worklist?.next_cursor ?? null;
      setHasMoreQueue(worklist ? worklist.next_cursor != null : totalCount > queueOffset + newEntries.length);
      logger.info('[LabPanel] loaded more lab queue entries', newEntries.length);
    } catch (error) {
      // STRAT#16: не показываем error notification для отменённых запросов.
      // LABQ-FE-001: a stale page's failure belongs to the old generation.
      if (isAbortLikeError(error) || queueGenerationRef.current !== generation) return;
      logger.error('[LabPanel] loadMoreAppointments failed', error);
      if ((error as { status?: number } | null)?.status === 409 && nextWorklistCursorRef.current != null) {
        notify('info', t('labWorkspace.cursorExpired'));
        await loadLabAppointments();
      } else {
        notify('error', getErrorMessage(error, t('misc.lp_ne_udalos_zagruzit_dopolnite')));
      }
    } finally {
      // LABQ-FE-002: only the current generation's page may unset the
      // incremental loading flag.
      if (queueGenerationRef.current === generation) {
        setLoadingMore(false);
      }
    }
  }, [
    bindAppointmentForActiveInstance,
    appointmentsLoading,
    loadingMore,
    hasMoreQueue,
    queueOffset,
    loadLabAppointments,
    notify,
    refreshSelectedAppointmentFromEntries,
  ]);

  // H-2 fix: keyboard shortcuts for tab switching, refresh, clear selection.
  // PR5: единый dirty-guard для переходов, уничтожающих введённый draft
  // (смена пациента/отчёта/шаблона, Escape, восстановление из URL).
  // PR 3351 (review round 2, P1): guard поднят на уровень App через
  // LabDirtyGuardContext — тот же реестр источников и тот же диалог видит
  // route-level leave guard (Header/Profile/Command Palette/logout/browser
  // Back). Без провайдера (unit-тесты) — standalone-экземпляр.
  const {
    registerDirtySource,
    guardTransition: guardDirtyTransition,
    dismissPendingTransition,
    guardDialog,
    isDialogOpen,
    setPendingOperationSources,
    setHistoryGuardPendingSources,
    notifyDirtyStateChange,
    hasPendingOperations,
    // PR 3351 (review round 8, P1): реактивный «sentinel вооружён или
    // сворачивается». Пока true, WF-15 эффект ниже откладывает замену
    // ?instance в адресе: replace разошёлся бы с twin-записью под
    // sentinel-ом, и collapse после завершения операции (например, report
    // CREATE) уводил бы history.back()-ом на устаревший адрес — URL и
    // активный отчёт откатывались на предыдущий бланк (stale restore,
    // round 7). Флип в false (collapse приземлился) перезапускает эффект,
    // и отложенная запись выполняется уже на свёрнутую реальную запись.
    historyGuardEngaged,
  } = useLabDirtyGuard();
  const pendingOperationSourcesRef = useRef(new Set<string>());
  // PR 3351 (review round 7, P1): второй реестр — операции, блокирующие
  // полный уход с /lab (route-level guard/beforeunload/session-expiry
  // через setPendingOperationSources). PR 3351 (review round 8, P1):
  // report CREATE блокирует ОБА уровня (контекстные переходы тоже —
  // latest-wins для неидемпотентного POST небезопасен: серверный side
  // effect уже закоммичен, а отброшенный по operation-context ответ
  // терял и созданный бланк, и обновление read-model). Оба реестра
  // получают 'report' на время CREATE — sentinel вооружается, а
  // расходящийся с twin URL не пишется (historyGuardEngaged, WF-15).
  const documentLeavePendingSourcesRef = useRef(new Set<string>());
  const setOperationSourcePending = useCallback((
    source: string,
    state: LabOperationPendingState | null,
  ) => {
    if (state?.blocksContextTransition) pendingOperationSourcesRef.current.add(source);
    else pendingOperationSourcesRef.current.delete(source);
    if (state?.blocksDocumentLeave) documentLeavePendingSourcesRef.current.add(source);
    else documentLeavePendingSourcesRef.current.delete(source);
    // PR 3351: SSOT pending-источников на уровне App — ДВА сигнала (review
    // round 7). Документ-уровень (guardRouteLeave/beforeunload/session-
    // expiry) видит реестр полного ухода; sentinel (browser Back)
    // вооружается контекстно-блокирующими операциями. PR 3351 (review
    // round 8, P1): CREATE входит в ОБА реестра — Back при его полёте
    // блокируется, а URL-контракт sentinel-а держит отложенная запись
    // WF-15 (historyGuardEngaged), а не исключение из реестра.
    setPendingOperationSources([...documentLeavePendingSourcesRef.current]);
    setHistoryGuardPendingSources([...pendingOperationSourcesRef.current]);
  }, [setPendingOperationSources, setHistoryGuardPendingSources]);
  const handleReportOperationPendingChange = useCallback(
    (state: LabOperationPendingState | null) => setOperationSourcePending('report', state),
    [setOperationSourcePending],
  );
  const handleTemplateOperationPendingChange = useCallback(
    (state: LabOperationPendingState | null) => setOperationSourcePending('template', state),
    [setOperationSourcePending],
  );
  const [specimenPending, setSpecimenPending] = useState(false);
  const [orderedTestPending, setOrderedTestPending] = useState(false);
  const handleSpecimenOperationPendingChange = useCallback((pending: boolean) => {
    setSpecimenPending(pending);
    setOperationSourcePending('specimen', pending ? LAB_OPERATION_PENDING_ALL : null);
  }, [setOperationSourcePending]);
  const handleOrderedTestPendingChange = useCallback((pending: boolean) => {
    setOrderedTestPending(pending);
    setOperationSourcePending('ordered-test', pending ? LAB_OPERATION_PENDING_ALL : null);
  }, [setOperationSourcePending]);
  // PR 3351 (review round 6, P1): истечение сессии больше не делает hard
  // navigation поверх незавершённой операции. Прежний код вызывал
  // window.location.href = '/login' прямо из onExpired опроса — это полная
  // перезагрузка документа ПОВЕРХ висящего неидемпотентного POST (clone
  // без Idempotency-Key, finalize/print): ответ терялся, список не
  // обновлялся, и оператор после повторного входа повторял clone, создавая
  // вторую копию. Теперь: чистое состояние — прежнее поведение (тост +
  // переход); pending-операция — redirectPending рендерит не-dismissable
  // диалог «операция завершается, затем переход», а onExpired (redirect)
  // вызывается ровно один раз после снятия последнего pending-источника.
  // hasPendingOperations из контекста — реактивный boolean (провайдер
  // перерисовывает на флипах 0↔n): render-time ref обёртки всегда держит
  // свежее замыкание, сигнал перевыполняет ожидающий эффект.
  const sessionRedirectPending = usePendingAwareSessionExpiry({
    hasPendingOperations: () => hasPendingOperations,
    pendingOperationsSignal: hasPendingOperations,
    onWarning: () => setSessionWarning({ active: true }),
    onExpired: () => {
      setSessionWarning(null);
      notifyService.error(t('misc.lp_sessiya_istekla_pozhaluysta_'));
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    },
    // PR 3351 (review round 8, P2): сессия восстановлена ПОСЛЕ истечения
    // (refresh токена в полёте) — отложенный redirect отменён, и висящее
    // предупреждение «Сессия скоро истечёт» обязано уйти вместе с ним:
    // новый JWT уже действует, сообщение лгало бы пользователю.
    onSessionRecovered: () => setSessionWarning(null),
  });
  const sessionDialogOpen = sessionWarning !== null || sessionRedirectPending;
  useLayoutEffect(() => {
    const dialog = sessionDialogRef.current;
    if (!sessionDialogOpen || !dialog) return;
    dialog.showModal();
    return () => dialog.close();
  }, [sessionDialogOpen]);

  useLayoutEffect(() => {
    const dialog = sessionDialogRef.current;
    if (!sessionDialogOpen || !dialog) return;
    if (sessionRedirectPending) {
      sessionDialogTitleRef.current?.focus({ preventScroll: true });
    } else if (!dialog.contains(document.activeElement)) {
      dialog.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus({ preventScroll: true });
    }
  }, [sessionDialogOpen, sessionRedirectPending, sessionExtending]);
  // Контракт блокирующих операций (PR 3351, review round 7/8 — split-уровни):
  // - report/template операции (draft save, CREATE, finalize, revise, print,
  //   autosave, шаблонные create/save/clone/archive) блокируют и КОНТЕКСТНЫЕ
  //   переходы затрагиваемого источника, и полный уход с /lab;
  // - route-level уход с /lab (guardRouteLeave) блокируется при ЛЮБОМ
  //   документ-уровневом pending-источнике (см. LabDirtyGuardContext);
  const guardTransition = useCallback((
    transition: () => void | Promise<void>,
    options?: DirtyGuardTransitionOptions,
  ) => {
    const blockedBy = options?.sourceIds
      ? [...pendingOperationSourcesRef.current].filter((source) => options.sourceIds?.includes(source)
        || ((source === 'specimen' || source === 'ordered-test') && options.sourceIds?.includes('report')))
      : [...pendingOperationSourcesRef.current];
    if (blockedBy.length > 0) {
      notify('info', t('workbench.saving'));
      // PR 3351 (review round 8, P1): urlIntent-переходы ОТЛАГАЮТСЯ, а не
      // отменяются: коллбек onPendingBlock удерживает намерение до
      // завершения операций (см. retry-эффект ниже). Откат (onCancel)
      // здесь был бы ошибочен: он переписывал бы URL текущей (sentinel)
      // записи, оставляя под ней неоткаченную внешнюю запись — collapse
      // после завершения операции приземлялся бы на неё и «воскрешал»
      // заблокированный intent через supersede restore-эффекта.
      if (options?.onPendingBlock) {
        options.onPendingBlock();
        return false;
      }
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
    }, { sourceIds: ['report'] }),
    disabled: isDialogOpen || sessionDialogOpen,
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
          }, { sourceIds: ['template'] }),
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
    const currentUrlInstanceId = getCurrentUrlInstanceId(instanceParamRef.current);
    const stateAndUrlAlreadyMatch = instanceIdsMatch(activeInstanceIdRef.current, targetId)
      && instanceIdsMatch(currentUrlInstanceId, targetId);
    pendingInstanceUrlSyncRef.current = !options.forcePending && stateAndUrlAlreadyMatch
      ? null
      : {
        targetId,
        requestId,
        sourceUrlId: currentUrlInstanceId,
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
    const expectedOrderId = getPositiveId(selectedAppointmentRef.current?.order_id);
    const resultOrderId = getPositiveId(instance.order_id);
    if (expectedOrderId != null && resultOrderId != null && expectedOrderId !== resultOrderId) return false;

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
    // PR 3351: instance param, с которого стартовал этот переход. Если за
    // время запроса адресная строка сменилась ВНЕШНЕЙ навигацией на другой
    // instance (не источник и не цель), откат в catch не должен затирать
    // новое намерение — restore effect сделает supersede и откроет его.
    const transitionSourceUrlId = getCurrentUrlInstanceId(instanceParamRef.current);
    if (options.clearCurrent) {
      activeInstanceRef.current = null;
      activeInstanceEpochRef.current = labOperationEpochRef.current;
      activeInstanceIdRef.current = null;
      activeInstancePatientIdRef.current = null;
      setActiveInstance(null);
    }
    try {
      const instance = (await labReportingApi.getInstance(instanceId)) as { patient_snapshot?: { patient_id?: string | number; [k: string]: unknown }; [k: string]: unknown };
      if (requestId !== instanceRequestSequenceRef.current) {
        return;
      }
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
      if (requestId !== instanceRequestSequenceRef.current) {
        return;
      }
      setInstanceTransitionPending(false);
      switchTab('reports');
    } catch (error) {
      if (requestId !== instanceRequestSequenceRef.current) return;
      setInstanceTransitionPending(false);
      // PR 3351: если адресная строка уже принадлежит более новому внешнему
      // намерению (instance param не равен ни цели, ни источнику этого
      // перехода), откат и pending-контракт не нужны: restore effect вот-вот
      // сделает supersede и откроет новый intent. Откат здесь затирал бы
      // новый ?instance=N обратно на старый отчёт.
      const currentUrlInstanceId = typeof window !== 'undefined'
        ? new URLSearchParams(window.location.search).get('instance')
        : null;
      const urlBelongsToThisTransition = instanceIdsMatch(currentUrlInstanceId, instanceId)
        || instanceIdsMatch(currentUrlInstanceId, transitionSourceUrlId);
      if (!urlBelongsToThisTransition) return;
      const rollbackSourceUrlId = getCurrentUrlInstanceId(instanceParamRef.current);
      pendingInstanceUrlSyncRef.current = options.clearCurrent && rollbackSourceUrlId != null
        ? { targetId: null, requestId, sourceUrlId: rollbackSourceUrlId }
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
    // PR 3351 (review round 8, P1): намерение из внешнего URL,
    // заблокированное pending-операцией, ОТЛАДЫВАЕТСЯ (адресная строка
    // остаётся за intent-ом — тот же контракт, что у dirty-диалога) и
    // повторяется после завершения последней операции (retry-эффект
    // ниже). Откат отменял бы намерение, но внешняя запись под sentinel-
    // ом осталась бы — collapse «воскрешал» его произвольным supersede.
    const deferUrlIntentOnPending = options.urlIntent === true;
    if (options.urlIntent) {
      // PR 3351 (review round 7, P2): вкладка-база отката фиксируется
      // ОДИН раз на всю цепочку намерений. Superseding intent, пришедший
      // пока первый ждёт решения в dirty-dialog, видел бы activeTabRef уже
      // нормализованным («нет tab → queue» — tab-sync первого intent-а) и
      // затирал бы исходную вкладку отката (reports): Cancel возвращал бы
      // на очередь вместо редактируемого отчёта.
      if (pendingUrlIntentRef.current == null) {
        preUrlIntentTabRef.current = activeTabRef.current;
      }
      pendingUrlIntentRef.current = { targetId: instanceId };
    }
    // PR5: публичный переход через dirty-guard (недавние отчёты,
    // восстановление ?instance=N из URL). Внутри подтверждённого перехода
    // используется applyInstanceTransition — подтверждение один раз.
    // PR 3351 (review round 2, P1): смена report instance — даже из внешнего
    // URL — затрагивает ТОЛЬКО report-draft: Queue/Templates/Reports
    // смонтированы одновременно (hidden-секции), смена отчёта не уничтожает
    // template-черновик и наоборот. Все источники спрашивает только
    // route-level уход с /lab (guardRouteLeave).
    guardTransition(
      () => {
        if (options.urlIntent) {
          pendingUrlIntentRef.current = null;
        }
        if (instanceId == null) {
          clearActiveInstance();
          // PR 3351 (review round 9, P2): внешний urlIntent с targetId=null —
          // «canonical home» (Header brand / Command Palette → /lab). Вкладкой
          // владеет сам URL: ?tab=reports → очистить отчёт и остаться в
          // Reports; tab-less /lab → Queue (нормализация tab-sync эффекта, БЕЗ
          // URL-записи — canonical /lab не получает ?tab=). Прежний
          // безусловный switchTab('reports') дописывал ?tab=reports поверх
          // canonical /lab: brand-«дом» не был домом — экран оставался на
          // Reports, адрес нельзя было ни скопировать, ни восстановить.
          const urlTabParam = currentSearchParams().get('tab');
          const urlOwnsValidTab = (LAB_TAB_IDS as readonly string[]).includes(urlTabParam ?? '');
          if (urlOwnsValidTab) {
            // Явная вкладка адреса: контекст пациента сохраняется, история
            // перезагружается (reports-список без активного бланка).
            const patientId = selectedAppointmentRef.current?.patient_id as string | number | undefined;
            if (patientId != null) {
              loadedHistoryForPatientRef.current = patientId;
              void loadReportHistory(patientId);
            }
            const resolvedUrlTab = resolveLabTabId(urlTabParam);
            if (resolvedUrlTab !== activeTabRef.current) {
              switchTab(resolvedUrlTab);
            }
          } else {
            // Canonical /lab: reload-parity — после перезагрузки /lab
            // открывает Queue БЕЗ выбранного пациента и бланка. Контекст
            // пациента очищается и здесь, иначе WF-15 дописал бы ?patient
            // в «домашний» адрес (URL обязан оставаться строго /lab).
            // Эпоха инвалидирует in-flight операции старого контекста
            // (тот же контракт, что hotkey clearSelection).
            labOperationEpochRef.current += 1;
            selectedAppointmentRef.current = null;
            selectedAppointmentPatientIdRef.current = null;
            setSelectedAppointment(null);
            loadedHistoryForPatientRef.current = null;
            // tab-sync эффект (объявлен выше) уже нормализовал «нет tab →
            // queue» на этом же коммите; defensive-синк без URL-записи.
            if (activeTabRef.current !== 'queue') {
              setActiveTab('queue');
            }
          }
          // Память pre-intent вкладки закрывается: она служит только
          // cancel-rollback-у, а подтверждённое canonical-приземление не
          // откатывается. Без этого WF-15 воскрешал бы «reports» поверх
          // tab-less /lab (round 6: память закрывается только когда URL
          // владеет ВАЛИДНЫМ tab — tab-less canonical не закрывал её).
          preUrlIntentTabRef.current = null;
          return;
        }
        void applyInstanceTransition(instanceId, { urlIntent: options.urlIntent });
      },
      {
        sourceIds: ['report'],
        // PR 3351 (review round 8, P1): pending-блок ОТЛАГАЕТ намерение
        // (флаг для retry-эффекта), откат не выполняется.
        onPendingBlock: deferUrlIntentOnPending
          ? () => { urlIntentDeferredByPendingRef.current = true; }
          : undefined,
        onCancel: options.urlIntent ? () => {
          // Keep a rollback contract while React Router is still exposing the
          // cancelled external URL. Otherwise the restore effect observes it
          // once more and immediately opens a second dirty-state dialog.
          // PR 3351: если адресная строка уже занята более новым внешним
          // намерением (другой instance), откат не должен его затирать —
          // restore effect сделает supersede и обработает новый intent.
          const cancelledUrlInstanceId = getCurrentUrlInstanceId(instanceParamRef.current);
          if (!instanceIdsMatch(cancelledUrlInstanceId, instanceId)) {
            pendingUrlIntentRef.current = null;
            return;
          }
          const requestId = ++instanceRequestSequenceRef.current;
          pendingInstanceUrlSyncRef.current = {
            targetId: activeInstanceIdRef.current,
            requestId,
            sourceUrlId: cancelledUrlInstanceId,
          };
          pendingUrlIntentRef.current = null;
          syncUrlToCurrentContext();
          // Откат потребил pre-intent вкладку — URL снова явно владеет tab.
          preUrlIntentTabRef.current = null;
        } : undefined,
      },
    );
  }, [
    guardTransition,
    applyInstanceTransition,
    clearActiveInstance,
    currentSearchParams,
    loadReportHistory,
    syncUrlToCurrentContext,
    switchTab,
  ]);

  // PR 3351 (review round 8, P1): RETRY отложенного pending-блоком
  // urlIntent-а. Флаг urlIntentDeferredByPendingRef ставится
  // onPendingBlock-ом guardTransition, когда внешний URL-переход пришёл
  // поверх незавершённой report-операции (round 8: включая CREATE).
  // Намерение удерживается (pendingUrlIntentRef + адресная строка — тот же
  // контракт, что у dirty-диалога), а когда последняя операция завершается
  // (реактивный флип hasPendingOperations), restore-эффект намерения
  // повторяется: guardTransition уже чист — либо выполняет переход, либо,
  // если за время полёта появился dirty-черновик, честно открывает диалог.
  // Без retry откат наPendingBlock не выполнялся бы вовсе, а внешний
  // intent зависал до перезагрузки; с немедленным откатом (round 7)
  // неоткаченная внешняя запись ПОД sentinel-ом «воскрешалась» бы collapse
  // через произвольный supersede restore-эффекта.
  useEffect(() => {
    if (hasPendingOperations) return;
    if (!urlIntentDeferredByPendingRef.current) return;
    const heldIntent = pendingUrlIntentRef.current;
    urlIntentDeferredByPendingRef.current = false;
    if (heldIntent == null) return;
    loadInstance(heldIntent.targetId, { urlIntent: true });
    // hasPendingOperations — реактивный сигнал провайдера (флипы 0↔n);
    // loadInstance стабилен (useCallback).
  }, [hasPendingOperations, loadInstance]);

  // WF-15 fix: URL sync для patient/instance — shareable + back-button friendly.
  // При смене selectedAppointment или activeInstance обновляем URL params.
  useEffect(() => {
    // A URL intent waiting behind the shared dirty dialog owns the address bar
    // until the user decides. A late report mutation may update local state,
    // but must not erase that newer navigation request or dismiss its dialog.
    if (pendingUrlIntentRef.current) return;
    // PR 3351 (review round 8, P1): sentinel занят (armed || collapsing) —
    // запись ?instance в адрес ОТКЛАДЫВАЕТСЯ. Вооружённый sentinel пушил копию
    // текущей записи (twin) ПОД себя: replace нового ?instance действовал бы
    // на саму sentinel-запись, twin ниже хранил бы до-create URL, и collapse
    // после завершения операции приземлял бы history.back()-ом на устаревший
    // адрес — URL и активный отчёт молча откатывались на предыдущий бланк
    // (stale restore, находка round-7). Пока engaged=true, адрес не пишется:
    // collapse приземляется на twin БЕЗ расхождения, а отложенная запись
    // выполняется уже на свёрнутую РЕАЛЬНУЮ запись — флип engaged=false
    // (finishCollapse в popstate-обработчике) перезапускает этот эффект.
    // pendingSync-контракт при этом не расходится: restore-эффект ниже видит
    // twin-URL == sourceUrlId и не грузит устаревший отчёт.
    if (historyGuardEngaged) return;
    // Внешняя URL-навигация (pushState + popstate), которую React Router ещё
    // не отрендерил, владеет адресной строкой: window.location.search в этом
    // окне не совпадает НИ с последним запросом, написанным приложением, НИ
    // с location текущего рендера. Синхронизация state→URL не должна писать
    // поверх ещё не обработанного намерения (иначе instance=89 из внешнего
    // URL затирался обратно на instance=88 до того, как restore effect
    // успевал его открыть — PR 3351). Собственные navigate тоже опережают
    // замыкание эффекта, но тогда window совпадает с lastAppWrittenSearch —
    // это наш URL, и писать из него как из базы безопасно.
    if (
      typeof window !== 'undefined'
      && window.location.search !== location.search
      && window.location.search !== lastAppWrittenSearchRef.current
    ) {
      return;
    }
    const pendingSync = pendingInstanceUrlSyncRef.current;
    // PR 3351: сравниваем с фактическим instance param текущего адреса —
    // замыкание instanceParamId может отставать от последней URL-записи.
    const currentUrlInstanceId = getCurrentUrlInstanceId(
      instanceParamId != null ? String(instanceParamId) : null,
    );
    if (
      pendingSync
      && !instanceIdsMatch(currentUrlInstanceId, pendingSync.sourceUrlId)
      && !instanceIdsMatch(currentUrlInstanceId, pendingSync.targetId)
    ) return;
    if (pendingSync && !instanceIdsMatch(activeInstanceId, pendingSync.targetId)) return;
    // A differing explicit URL id is navigation intent. Let the restore effect
    // guard and load it before state-to-URL synchronization writes anything.
    if (
      pendingSync == null
      && !instanceIdsMatch(activeInstanceId, currentUrlInstanceId)
    ) return;

    const params = currentSearchParams();
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
    // PR 3351 (review round 6, P2): URL без валидного tab при живой памяти
    // pre-intent вкладки получает её явно. Два сценария: (1) подтверждённый
    // urlIntent-откат — sentinel-collapse (dirty→clean) делает history.back()
    // на внешнюю tab-less запись, её POP-рендер запускает нормализацию
    // «нет tab → queue», и без этой записи WF-15 дописывал бы patient без
    // tab, молча уводя пользователя с вкладки подтверждённого перехода;
    // (2) возврат внешнего URL к АКТИВНОМУ отчёту без tab — отчёт открыт,
    // редактор должен остаться видимым, а не прятаться за вкладкой очереди.
    // Память закрывается в tab-sync эффекте, как только URL снова владеет
    // валидным tab (canonical /lab при shell-переходе её не наследует).
    const intentTab = preUrlIntentTabRef.current;
    const urlTab = params.get('tab');
    if (
      intentTab != null
      && (LAB_TAB_IDS as readonly string[]).includes(intentTab)
      && !(LAB_TAB_IDS as readonly string[]).includes(urlTab ?? '')
    ) {
      params.set('tab', intentTab);
    }
    // Только если params реально изменились —避免 лишних navigate
    const current = currentSearchParams();
    if (params.toString() !== current.toString()) {
      navigateReplace(params.toString());
    }
  }, [activeInstanceId, currentSearchParams, historyGuardEngaged, instanceParamId, selectedAppointment, location.search, navigateReplace]);

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
    // PR 3351: фактический instance param из ТЕКУЩЕГО адреса, а не из
    // замыкания рендера: URL-запись предыдущего перехода могла ещё не
    // отрендериться (быстрый второй клик пациента), и замыкание со
    // старым/null значением разрывало pendingSync-контракт ложным
    // supersede (например, обратно на null и удалением instance из URL).
    const instanceId = getCurrentUrlInstanceId(instanceParamId != null ? String(instanceParamId) : null);
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
        // PR 3351 (review round 6, P2): URL вернулся к АКТИВНОМУ отчёту,
        // диалог снят. WF-15 в этом же проходе эффектов уже пропущен
        // (pendingUrlIntentRef ещё висел при его запуске), а после закрытия
        // диалога его deps не изменятся — эффект не перезапустится. Без
        // явной записи внешние tab-less URL (?patient&instance без tab)
        // нормализуются на вкладку очереди, и открытый редактор отчёта
        // прячется. Пишем tab из pre-intent памяти (rollback-контракт
        // syncUrlToCurrentContext: валидный tab адреса → pre-intent →
        // текущая вкладка), URL становится полностью явным.
        syncUrlToCurrentContext();
      }
      return;
    }
    loadInstance(instanceId, { urlIntent: true });
  }, [activeInstanceId, dismissPendingTransition, instanceParamId, loadInstance, syncUrlToCurrentContext]);

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
    queue: worklistPage ? queueTotal : appointments.length,
    templates: templates.length,
    reports: reportsCounter
  }), [appointments.length, queueTotal, reportsCounter, templates.length, worklistPage]);

  const expectedOrderId = getPositiveId(selectedAppointment?.order_id);
  const activeOrderId = getPositiveId(activeInstance?.order_id);
  const activePatientId = getInstancePatientId(activeInstance);
  const scopedInstance = activeInstance && (!selectedAppointment || (
    activePatientId != null && String(selectedAppointment.patient_id) === String(activePatientId)
    && (expectedOrderId == null || expectedOrderId === activeOrderId)
  )) ? activeInstance : null;
  const selectedOrderId = getPositiveId(selectedAppointment?.order_id ?? scopedInstance?.order_id);
  const selectedVisitId = getPositiveId(selectedAppointment?.visit_id ?? scopedInstance?.visit_id);
  const selectedReportId = getPositiveId(scopedInstance?.id);
  const orderedTests = Array.isArray(selectedAppointment?.service_details)
    ? (selectedAppointment.service_details as Record<string, unknown>[]).flatMap((service) => {
        const id = getPositiveId(service.visit_service_id);
        return id == null ? [] : [{
          id, label: String(service.name ?? service.code ?? `#${id}`),
          canceled: service.canceled === true, canCancel: service.can_cancel === true,
        }];
      }) : [];
  const selectedServices = orderedTests.filter((test) => !test.canceled);
  const awaitingVisit = typeof selectedAppointment?.id === 'string' && selectedAppointment.id.startsWith('queue:')
    && selectedAppointment.visit_id == null && selectedAppointment.appointment_id == null && selectedOrderId == null;

  const establishSpecimenOrder = useCallback((orderId: number, visitId: number) => {
    const current = selectedAppointmentRef.current;
    if (!current || getPositiveId(current.visit_id) !== visitId || current.order_id != null) return;
    const updated = { ...current, order_id: orderId, id: `order:${orderId}` };
    selectedAppointmentRef.current = updated;
    setSelectedAppointment(updated);
  }, []);

  const handleSpecimenChanged = useCallback(async () => {
    void loadLabAppointments();
    const report = activeInstanceRef.current;
    const reportId = getPositiveId(report?.id);
    if (!report?.managed_release || reportId == null || selectedOrderId == null
      || getPositiveId(report.order_id) !== selectedOrderId) return;

    const epoch = labOperationEpochRef.current;
    const stillCurrent = () => activeInstanceRef.current === report && labOperationEpochRef.current === epoch;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15_000);
    try {
      const fresh = await labReportingApi.getInstance(reportId, { signal: controller.signal }) as Record<string, unknown>;
      if (!stillCurrent()) return;
      if (getPositiveId(fresh.id) !== reportId || getPositiveId(fresh.order_id) !== selectedOrderId
        || !instanceIdsMatch(getInstancePatientId(fresh), getInstancePatientId(report))) return;
      if (typeof report.updated_at !== 'string' || fresh.updated_at !== report.updated_at) {
        notify('error', t('workbench.save_conflict'));
        return;
      }
      if (fresh.managed_release !== true || !Array.isArray(fresh.release_holds)
        || !Array.isArray(fresh.available_actions)) {
        notify('error', t('misc.lp_ne_udalos_otkryt_laboratorny'));
        return;
      }
      // Specimen evidence can change without modifying the report version.
      // Update the server's workflow metadata and retain the draft snapshot.
      if (JSON.stringify(fresh.release_holds) === JSON.stringify(report.release_holds)
        && JSON.stringify(fresh.available_actions) === JSON.stringify(report.available_actions)) return;
      const refreshed = { ...report, release_holds: fresh.release_holds, available_actions: fresh.available_actions };
      activeInstanceRef.current = refreshed;
      setActiveInstance(refreshed);
    } catch {
      if (stillCurrent()) notify('error', t('misc.lp_ne_udalos_otkryt_laboratorny'));
    } finally {
      window.clearTimeout(timeout);
    }
  }, [loadLabAppointments, notify, selectedOrderId, t]);

  const handleOrderedTestChanged = useCallback((testId?: number) => {
    const current = selectedAppointmentRef.current;
    if (testId != null && current && getPositiveId(current.visit_id) === selectedVisitId && Array.isArray(current.service_details)) {
      const updated = {
        ...current,
        service_details: (current.service_details as Record<string, unknown>[]).map((item) => (
          getPositiveId(item.visit_service_id) === testId ? { ...item, canceled: true, can_cancel: false } : item
        )),
      };
      selectedAppointmentRef.current = updated;
      setSelectedAppointment(updated);
    }
    void loadLabAppointments();
  }, [loadLabAppointments, selectedVisitId]);

  const focusReportAfterOpen = useRef(false);
  useEffect(() => {
    if (activeTab === 'reports' && focusReportAfterOpen.current) {
      focusReportAfterOpen.current = false;
      document.getElementById('lab-order-title')?.focus({ preventScroll: true });
    }
  }, [activeTab, selectedAppointment]);

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
        {t('labWorkspace.skipToTabs')}
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
                  aria-label={statusCounters[tab.id] == null ? tab.label : t('misc.lp_tab_label_statuscounters_tab', {
                    label: tab.label, id: statusCounters[tab.id],
                  })}
                  tabIndex={activeTab === tab.id ? 0 : -1}
                  variant={activeTab === tab.id ? 'primary' : 'outline'}
                  onClick={() => switchTab(tab.id)}
                  onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleTabKeyDown(event, tab.id)}
                >
                  <tab.icon size={16} aria-hidden="true" />
                  {tab.label}
                  {statusCounters[tab.id] != null && <Badge
                    aria-hidden="true"
                    variant={activeTab === tab.id ? 'success' : 'info'}
                  >
                    {statusCounters[tab.id]}
                  </Badge>}
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

      <div className={`lab-workspace lab-workspace--${activeTab}`} hidden={activeTab !== 'queue' && activeTab !== 'reports'}>
      <section
        id={getLabPanelTabPanelId('queue')}
        role={activeTab === 'queue' ? 'tabpanel' : 'region'}
        aria-labelledby={getLabPanelTabId('queue')}
        tabIndex={0}
        className="lab-workspace-queue"
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
          worklist={worklistPage}
          scanned={Boolean(worklistQueryRef.current.barcode)}
          error={appointmentsError}
          onQueryChange={changeWorklistQuery}
          onOpenAppointment={(appointment) => {
            const nextAppointment = appointment as Record<string, unknown>;
            // PR5: смена пациента — переход через dirty-guard. Затрагивает
            // только report-draft: шаблонный редактор живёт в отдельном
            // табе и не уничтожается сменой пациента.
            guardTransition(() => {
              focusReportAfterOpen.current = true;
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
            }, { sourceIds: ['report'] });
          }}
          selectedAppointment={selectedAppointment as Record<string, unknown> & { id?: string | number; patient_fio?: string; patient_phone?: string; patient_id?: string | number; visit_id?: string | number; appointment_time?: string; status?: string }}
          reportHistory={reportHistory as unknown as Array<Record<string, unknown> & { id: string | number; created_at: string; status: string; flagged_findings_count: number; critical_findings_count: number; max_flag_severity?: number }>}
        />
      </section>

      <section
        id={getLabPanelTabPanelId('reports')}
        role="tabpanel"
        aria-labelledby={getLabPanelTabId('reports')}
        tabIndex={0}
        className="lab-workspace-report"
        hidden={activeTab !== 'reports'}
      >
        {(selectedAppointment || activeInstance) && (
          <div className="lab-workspace-back">
            <Button type="button" variant="ghost" onClick={() => {
              switchTab('queue');
              window.requestAnimationFrame(() => {
                const queue = document.getElementById(getLabPanelTabPanelId('queue'));
                (queue?.querySelector<HTMLElement>('[aria-current="true"]') ?? queue)?.focus();
              });
            }}>{t('labWorkspace.backToQueue')}</Button>
          </div>
        )}
        {(selectedAppointment || scopedInstance) && (
          <LabOrderIdentity appointment={selectedAppointment} report={scopedInstance} orderId={selectedOrderId} />
        )}
        {selectedVisitId != null && orderedTests.length > 0 && (
          <LabOrderedTests key={`${selectedVisitId}:${selectedOrderId ?? ''}`} visitId={selectedVisitId}
            orderId={selectedOrderId} tests={orderedTests}
            disabled={specimenPending || instanceTransitionPending || pendingOperationSourcesRef.current.has('report')}
            onPendingChange={handleOrderedTestPendingChange} onChanged={handleOrderedTestChanged} />
        )}
        {(selectedOrderId != null || (selectedVisitId != null && selectedServices.length > 0)) && (
          <LabSpecimenWorkbench
            key={selectedOrderId == null ? `visit:${selectedVisitId}` : `order:${selectedOrderId}`}
            orderId={selectedOrderId}
            visitId={selectedVisitId}
            activeReportId={scopedInstance?.available_actions && Array.isArray(scopedInstance.available_actions)
              && scopedInstance.available_actions.includes('edit') ? selectedReportId : null}
            services={selectedServices}
            disabled={selectedAppointment?.status === 'canceled' || orderedTestPending
              || instanceTransitionPending || pendingOperationSourcesRef.current.has('report')}
            onPendingChange={handleSpecimenOperationPendingChange}
            onChanged={handleSpecimenChanged}
            onOrderEstablished={establishSpecimenOrder}
          />
        )}
        {awaitingVisit && <Alert severity="info">{t('labWorkspace.awaitingVisit')}</Alert>}
        <div hidden={awaitingVisit} inert={specimenPending || orderedTestPending}>
        <LabReportWorkbench
          selectedAppointment={awaitingVisit ? null : selectedAppointment}
          templates={templates}
          templateResolution={templateResolution as unknown as null}
          templateResolutionLoading={templateResolutionLoading}
          reportHistory={reportHistory as unknown as never[]}
          recentReports={recentReports as unknown as never[]}
          registerDirtySource={registerDirtySource}
          onDirtyStateChange={notifyDirtyStateChange}
          onOperationPendingChange={handleReportOperationPendingChange}
          activeInstance={scopedInstance}
          instanceTransitionPending={instanceTransitionPending}
          pauseAutoSave={isDialogOpen || specimenPending || orderedTestPending}
          getOperationContext={getReportOperationContext}
          onInstanceChange={handleInstanceChange}
          onOpenInstance={loadInstance}
          onRefreshHistory={loadReportHistory as unknown as (patientId: string | number) => Promise<void>}
          onRefreshRecentReports={loadRecentReports as unknown as undefined}
          onQueueChanged={loadLabAppointments as unknown as undefined}
          notify={notify}
        />
        </div>
      </section>
      {activeTab === 'queue' && <aside className="lab-workspace-empty">{t('labWorkspace.openFromQueue')}</aside>}
      </div>

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
          onDirtyStateChange={notifyDirtyStateChange}
          guardTransition={guardTransition}
          templateTransitionPending={templateTransitionPending}
          onOperationPendingChange={handleTemplateOperationPendingChange}
          onSelectTemplate={async (template) => {
            // PR5: смена шаблона — переход через dirty-guard. Затрагивает
            // только template-draft: report-редактор привязан к
            // activeInstance и не уничтожается сменой шаблона.
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
            }, { sourceIds: ['template'] });
          }}
          onTemplatesChanged={async (preferredTemplateId = null) => {
            await loadTemplates(preferredTemplateId);
          }}
          notify={notify}
        />
      </section>

      <section
        id={getLabPanelTabPanelId('operations')}
        role="tabpanel"
        aria-labelledby={getLabPanelTabId('operations')}
        tabIndex={0}
        hidden={activeTab !== 'operations'}
      >
        {(operationsOpened || activeTab === 'operations') && (
          <LabOperationsWorkbench orderId={selectedOrderId} reportId={selectedReportId} onQueueChanged={loadLabAppointments} />
        )}
      </section>

              {/* PR5: единый dirty-guard диалог */}
        {guardDialog}
        {/* Keep the modal open through the warning → deferred redirect so
            the browser restores focus to the original control on recovery. */}
        <dialog
          ref={sessionDialogRef}
          role="alertdialog"
          aria-modal="true"
          aria-label={t(sessionRedirectPending ? 'misc.lp_perehod_posle_zaversheniya' : 'misc.lp_preduprezhdenie_ob_istecheni')}
          aria-describedby={sessionDialogDescriptionId}
          className="lab-session-warning-dialog"
          onCancel={(event) => event.preventDefault()}
          onKeyDown={(event) => {
            event.stopPropagation();
            if (event.key !== 'Tab') return;
            const buttons = event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)');
            const first = buttons.item(0);
            const last = buttons.item(buttons.length - 1);
            const edge = event.shiftKey ? first : last;
            if (edge && edge !== document.activeElement) return;
            event.preventDefault();
            (event.shiftKey ? last : first)?.focus();
          }}
        >
          <h3 ref={sessionDialogTitleRef} tabIndex={sessionRedirectPending ? -1 : undefined} className="lab-session-warning-title">
            {sessionRedirectPending ? t('misc.lp_sessiya_istekla_zavershenie') : 'Сессия скоро истечёт'}
          </h3>
          <p id={sessionDialogDescriptionId} className="lab-session-warning-text">
            {sessionRedirectPending
              ? t('misc.lp_sessiya_istekla_zavershenie_t')
              : 'Ваша сессия истекает. Несохранённые данные могут быть потеряны. Сохраните текущий отчёт или продлите сессию.'}
          </p>
          {sessionRedirectPending ? (
            <div className="lab-session-redirect-spinner" aria-hidden="true" />
          ) : (
            <>
              {sessionExtendError && (
                <p className="lab-session-warning-text lab-session-extend-error" role="alert">
                  {sessionExtendError}
                </p>
              )}
              <div className="lab-session-warning-actions">
                <button type="button" onClick={() => setSessionWarning(null)} className="lab-session-warning-btn-later">
                  Позже
                </button>
                <button
                  type="button"
                  onClick={() => { void handleExtendSession(); }}
                  disabled={sessionExtending}
                  className="lab-session-warning-btn-extend"
                >
                  {sessionExtending ? t('misc.lp_session_extending') : 'Продлить сессию'}
                </button>
              </div>
            </>
          )}
        </dialog>
    </main>
  );
}
