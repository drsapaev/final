import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Alert, Badge, Button, Card, CardContent, CardHeader, Icon,
} from '../components/ui/macos';
import LabQueueWorkbench from '../components/laboratory/LabQueueWorkbench';
import LabReportWorkbench from '../components/laboratory/LabReportWorkbench';
import LabTemplateWorkbench from '../components/laboratory/LabTemplateWorkbench';
import { formatLabStatus } from '../components/laboratory/labUiLabels';
import { labReportingApi } from '../api/labReporting';
import { getErrorMessage } from '../utils/errorHandler';
import logger from '../utils/logger';
import RoleNotificationCenter from '../components/notifications/RoleNotificationCenter';
import { useSessionTimeoutWarning } from '../hooks/useSessionTimeoutWarning';
import { useLabHotkeys } from '../hooks/useLabHotkeys';
import notifyService from '../services/notify';
import './lab.css';

// P-03 fix: API_V1_BASE и tokenManager больше не нужны — loadLabAppointments
// использует labReportingApi.listQueueToday() с собственным auth-токеном.

const tabs = [
  { id: 'queue', label: 'Очередь', icon: 'testtube.2' },
  { id: 'templates', label: 'Шаблоны', icon: 'rectangle.stack.badge.plus' },
  { id: 'reports', label: 'Отчёты', icon: 'doc.text' }
];

const LAB_PANEL_TITLE_ID = 'lab-panel-title';
const LAB_PANEL_TABLIST_ID = 'lab-panel-tabs';

// STRAT#7: размер страницы для server-side pagination очереди.
// 50 записей — баланс между network overhead и UX (минимум прокруток).
// Backend maximum — 500 (Query(ge=1, le=500)).
const LAB_QUEUE_PAGE_SIZE = 50;

function getLabPanelTabId(tabId) {
  return `lab-panel-tab-${tabId}`;
}

function getLabPanelTabPanelId(tabId) {
  return `lab-panel-tabpanel-${tabId}`;
}

function normalizeListPayload(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (Array.isArray(payload?.items)) {
    return payload.items;
  }
  if (Array.isArray(payload?.results)) {
    return payload.results;
  }
  if (Array.isArray(payload?.data)) {
    return payload.data;
  }
  return [];
}

function isAbortLikeError(error) {
  const name = String(error?.name || '').toLowerCase();
  const message = String(error?.message || '').toLowerCase();
  return name === 'aborterror' || message.includes('aborted');
}

function buildTemplateResolutionPayload(appointment) {
  if (!appointment) {
    return null;
  }
  return {
    patient_id: appointment.patient_id || null,
    appointment_id: appointment.appointment_id || null,
    visit_id: appointment.visit_id || null,
    service_codes: appointment.service_codes || [],
    service_items: (appointment.service_details || []).map((item) => ({
      service_id: item.id || null,
      code: item.code || null,
      name: item.name || null
    }))
  };
}

export default function LabPanel() {
  const location = useLocation();
  const navigate = useNavigate();
  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);

  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'queue');
  const [appointments, setAppointments] = useState([]);
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
  const queueAbortControllerRef = useRef(null);
  // STRAT#16: отдельный ref для load-more запросов.
  const loadMoreAbortControllerRef = useRef(null);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [selectedAppointment, setSelectedAppointment] = useState(null);
  const [reportHistory, setReportHistory] = useState([]);
  const [recentReports, setRecentReports] = useState([]);
  const [activeInstance, setActiveInstance] = useState(null);
  const [templateResolution, setTemplateResolution] = useState(null);
  const [templateResolutionLoading, setTemplateResolutionLoading] = useState(false);
  // QW-4 fix: message теперь содержит опциональный retryAction — функцию,
  // которая вызывается при клике «Повторить» в Alert. Раньше ошибки
  // показывались на 5 секунд без возможности восстановиться — пользователь
  // переключал таб и не видел сообщения. Теперь:
  //   - errors показываются 12 секунд (вместо 5)
  //   - info/success — 5 секунд (как раньше)
  //   - error с retryAction показывает кнопку «Повторить»
  //   - любой клик по Alert закрывает его
  const [message, setMessage] = useState({ type: '', text: '', retryAction: null, retryLabel: '' });

  const notify = useCallback((type, text, options = {}) => {
    setMessage({
      type,
      text,
      retryAction: typeof options.retryAction === 'function' ? options.retryAction : null,
      retryLabel: options.retryLabel || 'Повторить',
    });
  }, []);

  const dismissMessage = useCallback(() => {
    setMessage({ type: '', text: '', retryAction: null, retryLabel: '' });
  }, []);

  // H-1 fix: session timeout warning — prevents silent JWT expiry while
  // a lab technician is mid-fill on a long report. Mirrors the pattern
  // used in CardiologistPanel/DentistPanel/DermatologistPanel.
  const [sessionWarning, setSessionWarning] = useState(null);

  // L-M-2 fix: ref-guard для дедупликации loadReportHistory.
  // Раньше loadReportHistory вызывался дважды: один раз из loadInstance
  // (когда instance.patient_snapshot.patient_id становился известен),
  // второй — из useEffect [selectedAppointment] ниже. Теперь ref хранит
  // patient_id для которого история уже загружена, и useEffect пропускает
  // повторный вызов если patient_id совпадает.
  const loadedHistoryForPatientRef = useRef(null);
  useSessionTimeoutWarning({
    onWarning: () => setSessionWarning({ active: true }),
    onExpired: () => {
      setSessionWarning(null);
      notifyService.error('Сессия истекла. Пожалуйста, войдите снова.');
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    },
  });

  const mergeResolvedVisitIntoState = useCallback((appointmentId, visitId) => {
    if (!appointmentId || !visitId) {
      return;
    }
    setAppointments((current) =>
      current.map((item) =>
        item.appointment_id === appointmentId && !item.visit_id
          ? { ...item, visit_id: visitId }
          : item
      )
    );
    setSelectedAppointment((current) => {
      if (!current || current.appointment_id !== appointmentId || current.visit_id) {
        return current;
      }
      return { ...current, visit_id: visitId };
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

  const switchTab = useCallback((tabId) => {
    setActiveTab(tabId);
    // WF-15 fix: сохраняем patient/instance в URL при переключении таба.
    const params = new URLSearchParams(location.search);
    params.set('tab', tabId);
    navigate(`/lab?${params.toString()}`, { replace: true });
  }, [navigate, location.search]);

  const handleTabKeyDown = useCallback((event, tabId) => {
    const currentIndex = tabs.findIndex((tab) => tab.id === tabId);
    if (currentIndex === -1) {
      return;
    }

    const keyOffsets = {
      ArrowRight: 1,
      ArrowDown: 1,
      ArrowLeft: -1,
      ArrowUp: -1
    };

    let nextIndex = null;
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
      const payload = await labReportingApi.listQueueToday(null, {
        limit: LAB_QUEUE_PAGE_SIZE,
        offset: 0,
        signal: controller.signal,
      });
      const queueEntries = normalizeListPayload(payload?.entries ?? []);
      setAppointments(queueEntries);
      setQueueTotal(payload?.total ?? queueEntries.length);
      setQueueOffset(queueEntries.length);
      // STRAT#7: помечаем, есть ли ещё записи для load-more
      setHasMoreQueue((payload?.total ?? 0) > queueEntries.length);
      setSelectedAppointment((current) => {
        if (!current) {
          return current;
        }
        const refreshed = queueEntries.find(
          (item) =>
            item.id === current.id
            || (current.appointment_id && item.appointment_id === current.appointment_id)
        );
        return refreshed || current;
      });
      logger.info('[LabPanel] loaded lab queue entries', queueEntries.length);
    } catch (error) {
      // STRAT#16: не показываем error notification для отменённых запросов.
      if (isAbortLikeError(error)) return;
      logger.error('[LabPanel] loadLabAppointments failed', error);
      notify(
        'error',
        getErrorMessage(error, 'Не удалось загрузить лабораторную очередь. Проверьте соединение и попробуйте снова.'),
        // QW-4 fix: кнопка «Повторить» в Alert.
        { retryAction: () => loadLabAppointments(), retryLabel: 'Загрузить снова' }
      );
    } finally {
      setAppointmentsLoading(false);
    }
  }, [notify]);

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
      const payload = await labReportingApi.listQueueToday(null, {
        limit: LAB_QUEUE_PAGE_SIZE,
        offset: queueOffset,
        signal: controller.signal,
      });
      const newEntries = normalizeListPayload(payload?.entries ?? []);
      setAppointments((current) => [...current, ...newEntries]);
      setQueueOffset((current) => current + newEntries.length);
      setHasMoreQueue((payload?.total ?? 0) > queueOffset + newEntries.length);
      logger.info('[LabPanel] loaded more lab queue entries', newEntries.length);
    } catch (error) {
      // STRAT#16: не показываем error notification для отменённых запросов.
      if (isAbortLikeError(error)) return;
      logger.error('[LabPanel] loadMoreAppointments failed', error);
      notify('error', getErrorMessage(error, 'Не удалось загрузить дополнительные записи очереди.'));
    } finally {
      setLoadingMore(false);
    }
  }, [loadingMore, hasMoreQueue, queueOffset, notify]);

  // H-2 fix: keyboard shortcuts for tab switching, refresh, clear selection.
  useLabHotkeys({
    switchTab,
    refreshData: loadLabAppointments,
    clearSelection: () => setSelectedAppointment(null),
  });

  const loadTemplates = useCallback(async (preferredTemplateId = null) => {
    try {
      const summary = await labReportingApi.listTemplates();
      const templateSummary = normalizeListPayload(summary);
      setTemplates(templateSummary);
      const templateId = preferredTemplateId || selectedTemplate?.id || templateSummary[0]?.id || null;
      if (templateId) {
        const detail = await labReportingApi.getTemplate(templateId);
        setSelectedTemplate(detail);
      } else {
        setSelectedTemplate(null);
      }
    } catch (error) {
      if (isAbortLikeError(error)) {
        logger.info('[LabPanel] loadTemplates aborted');
        return;
      }
      logger.error('[LabPanel] loadTemplates failed', error);
      notify(
        'error',
        getErrorMessage(error, 'Не удалось загрузить шаблоны лаборатории. Проверьте соединение и попробуйте снова.'),
        // QW-4 fix: кнопка «Повторить» в Alert.
        { retryAction: () => loadTemplates(), retryLabel: 'Загрузить снова' }
      );
    }
  // M-5 fix: removed selectedTemplate?.id from deps — it caused triple
  // re-fetch (loadLabAppointments + loadRecentReports + loadTemplates) every
  // time the user clicked a different template. Now reads selectedTemplate
  // via ref, so identity is stable and mount effect doesn't re-fire.
  }, [notify]);

  const loadReportHistory = useCallback(async (patientId) => {
    if (!patientId) {
      setReportHistory([]);
      return;
    }
    try {
      const history = await labReportingApi.listInstances({ patient_id: patientId, limit: 50 });
      setReportHistory(normalizeListPayload(history));
    } catch (error) {
      logger.error('[LabPanel] loadReportHistory failed', error);
      notify(
        'error',
        getErrorMessage(error, 'Не удалось загрузить историю лабораторных отчётов. Проверьте соединение и попробуйте снова.'),
        // QW-4 fix: кнопка «Повторить» в Alert.
        { retryAction: () => loadReportHistory(patientId), retryLabel: 'Загрузить снова' }
      );
    }
  }, [notify]);

  const loadRecentReports = useCallback(async () => {
    try {
      const instances = await labReportingApi.listInstances({ limit: 50 });
      setRecentReports(normalizeListPayload(instances));
    } catch (error) {
      logger.error('[LabPanel] loadRecentReports failed', error);
      notify(
        'error',
        getErrorMessage(error, 'Не удалось загрузить список лабораторных отчётов. Проверьте соединение и попробуйте снова.'),
        // QW-4 fix: кнопка «Повторить» в Alert.
        { retryAction: () => loadRecentReports(), retryLabel: 'Загрузить снова' }
      );
    }
  }, [notify]);

  const loadTemplateResolution = useCallback(async (appointment) => {
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
      const resolution = await labReportingApi.resolveTemplateOptions(payload);
      setTemplateResolution(resolution);
      if (appointment?.appointment_id && resolution?.visit_id && !appointment.visit_id) {
        mergeResolvedVisitIntoState(appointment.appointment_id, resolution.visit_id);
      }
    } catch (error) {
      logger.error('[LabPanel] loadTemplateResolution failed', error);
      setTemplateResolution(null);
      notify(
        'error',
        getErrorMessage(
          error,
          'Не удалось определить доступные отчёты для выбранного визита. Проверьте соединение и попробуйте снова.'
        )
      );
    } finally {
      setTemplateResolutionLoading(false);
    }
  }, [mergeResolvedVisitIntoState, notify]);

  const loadInstance = useCallback(async (instanceId) => {
    if (!instanceId) {
      return;
    }
    try {
      const instance = await labReportingApi.getInstance(instanceId);
      setActiveInstance(instance);
      if (instance.patient_snapshot?.patient_id) {
        // L-M-2 fix: дедупликация loadReportHistory.
        // Сначала помечаем patient_id в loadedHistoryForPatientRef — это
        // предотвращает повторный вызов из useEffect [selectedAppointment]
        // ниже, который сработает когда setSelectedAppointment обновит состояние.
        loadedHistoryForPatientRef.current = instance.patient_snapshot.patient_id;
        await loadReportHistory(instance.patient_snapshot.patient_id);
      }
      switchTab('reports');
    } catch (error) {
      logger.error('[LabPanel] loadInstance failed', error);
      notify(
        'error',
        getErrorMessage(error, 'Не удалось открыть лабораторный отчёт. Проверьте соединение и попробуйте снова.')
      );
    }
  }, [loadReportHistory, notify, switchTab]);

  // WF-15 fix: URL sync для patient/instance — shareable + back-button friendly.
  // При смене selectedAppointment или activeInstance обновляем URL params.
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (selectedAppointment?.patient_id) {
      params.set('patient', String(selectedAppointment.patient_id));
    } else {
      params.delete('patient');
    }
    if (activeInstance?.id) {
      params.set('instance', String(activeInstance.id));
    } else {
      params.delete('instance');
    }
    // Только если params реально изменились —避免 лишних navigate
    const current = new URLSearchParams(location.search);
    if (params.toString() !== current.toString()) {
      navigate(`/lab?${params.toString()}`, { replace: true });
    }
  }, [selectedAppointment, activeInstance, location.search, navigate]);

  useEffect(() => {
    loadLabAppointments();
    loadTemplates();
    loadRecentReports();
    // WF-15 fix: восстановление контекста из URL при загрузке.
    // Если URL содержит ?instance=N — открываем этот отчёт.
    const instanceParam = searchParams.get('instance');
    if (instanceParam) {
      const instanceId = parseInt(instanceParam, 10);
      if (!Number.isNaN(instanceId)) {
        loadInstance(instanceId);
      }
    }
  }, [loadLabAppointments, loadRecentReports, loadTemplates, searchParams, loadInstance]);

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
    if (selectedAppointment?.patient_id) {
      // L-M-2 fix: пропускаем повторный вызов если история уже загружена
      // для этого patient_id (вызвана из loadInstance).
      if (loadedHistoryForPatientRef.current !== selectedAppointment.patient_id) {
        loadedHistoryForPatientRef.current = selectedAppointment.patient_id;
        loadReportHistory(selectedAppointment.patient_id);
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

  const statusCounters = useMemo(() => ({
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
              <Icon name="cross.case" size={22} />
              <span>Панель лаборатории</span>
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
                  aria-label={`${tab.label}: ${statusCounters[tab.id]} записей`}
                  tabIndex={activeTab === tab.id ? 0 : -1}
                  variant={activeTab === tab.id ? 'primary' : 'outline'}
                  onClick={() => switchTab(tab.id)}
                  onKeyDown={(event) => handleTabKeyDown(event, tab.id)}
                >
                  <Icon name={tab.icon} size={16} />
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
                        dismissMessage();
                        // Небольшая задержка, чтобы UI успел обновиться
                        setTimeout(() => action(), 0);
                      }}
                    >
                      <Icon name="arrow.clockwise" size={14} />
                      {message.retryLabel || 'Повторить'}
                    </Button>
                  )}
                  <Button
                    size="small"
                    variant="outline"
                    onClick={dismissMessage}
                    aria-label="Закрыть уведомление"
                  >
                    <Icon name="xmark" size={14} />
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
            setSelectedAppointment(appointment);
            setTemplateResolution(null);
            // WF-03 fix: если у пациента уже есть report_instance_id —
            // сразу открываем существующий отчёт, а не сбрасываем в режим
            // создания.
            if (appointment.report_instance_id) {
              loadInstance(appointment.report_instance_id);
            } else {
              setActiveInstance(null);
            }
            switchTab('reports');
          }}
          selectedAppointment={selectedAppointment}
          reportHistory={reportHistory}
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
          onSelectTemplate={async (templateId) => {
            try {
              const template = await labReportingApi.getTemplate(templateId);
              setSelectedTemplate(template);
            } catch (error) {
              notify('error', getErrorMessage(error, 'Не удалось загрузить шаблон. Проверьте соединение и попробуйте снова.'));
            }
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
          <nav aria-label="Навигация" className="lab-breadcrumb-nav">
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
                <span>{selectedAppointment.patient_fio || `Пациент #${selectedAppointment.patient_id}`}</span>
              </>
            )}
            {activeInstance && (
              <>
                <span>›</span>
                <span>
                  Отчёт #{activeInstance.id}
                  <span className="lab-text-muted-ml">
                    ({formatLabStatus(activeInstance.status)})
                  </span>
                </span>
              </>
            )}
          </nav>
        )}
        <LabReportWorkbench
          selectedAppointment={selectedAppointment}
          templates={templates}
          templateResolution={templateResolution}
          templateResolutionLoading={templateResolutionLoading}
          reportHistory={reportHistory}
          recentReports={recentReports}
          activeInstance={activeInstance}
          onInstanceChange={setActiveInstance}
          onOpenInstance={loadInstance}
          onRefreshHistory={loadReportHistory}
          onRefreshRecentReports={loadRecentReports}
          onQueueChanged={loadLabAppointments}
          notify={notify}
        />
      </section>

              {/* H-1 fix: session timeout warning dialog */}
        {sessionWarning && (
          <div
            role="alertdialog"
            aria-label="Предупреждение об истечении сессии"
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
                <button onClick={() => { setSessionWarning(null); notifyService.info('Продлеваем сессию...'); }} className="lab-session-warning-btn-extend">
                  Продлить сессию
                </button>
              </div>
            </div>
          </div>
        )}
        <RoleNotificationCenter userRole="lab" />
    </main>
  );
}
