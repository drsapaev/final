import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Alert, Badge, Button, Card, CardContent, CardHeader, Icon,
} from '../components/ui/macos';
import LabQueueWorkbench from '../components/laboratory/LabQueueWorkbench';
import LabReportWorkbench from '../components/laboratory/LabReportWorkbench';
import LabTemplateWorkbench from '../components/laboratory/LabTemplateWorkbench';
import { labReportingApi } from '../api/labReporting';
import { getErrorMessage } from '../utils/errorHandler';
import logger from '../utils/logger';
import RoleNotificationCenter from '../components/notifications/RoleNotificationCenter';

// P-03 fix: API_V1_BASE и tokenManager больше не нужны — loadLabAppointments
// использует labReportingApi.listQueueToday() с собственным auth-токеном.

const tabs = [
  { id: 'queue', label: 'Очередь', icon: 'testtube.2' },
  { id: 'templates', label: 'Шаблоны', icon: 'rectangle.stack.badge.plus' },
  { id: 'reports', label: 'Бланки', icon: 'doc.text' }
];

const LAB_PANEL_TITLE_ID = 'lab-panel-title';
const LAB_PANEL_TABLIST_ID = 'lab-panel-tabs';

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
    navigate(`/lab?tab=${tabId}`, { replace: true });
  }, [navigate]);

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
    setAppointmentsLoading(true);
    try {
      // P-03 fix: используем lab-specific façade endpoint вместо прямого
      // fetch к /registrar/queues/today. Façade имеет собственный контракт,
      // собственную RBAC и нормализует ответ в плоский формат — это убирает
      // жёсткую связку с registrar endpoint и промежуточную нормализацию
      // через formatAppointmentEntry.
      const payload = await labReportingApi.listQueueToday();
      const queueEntries = normalizeListPayload(payload?.entries ?? []);
      setAppointments(queueEntries);
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
  }, [notify, selectedTemplate?.id]);

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
        getErrorMessage(error, 'Не удалось загрузить историю лабораторных бланков. Проверьте соединение и попробуйте снова.'),
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
        getErrorMessage(error, 'Не удалось загрузить список лабораторных бланков. Проверьте соединение и попробуйте снова.'),
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
          'Не удалось определить доступные бланки для выбранного визита. Проверьте соединение и попробуйте снова.'
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
        await loadReportHistory(instance.patient_snapshot.patient_id);
      }
      switchTab('reports');
    } catch (error) {
      logger.error('[LabPanel] loadInstance failed', error);
      notify(
        'error',
        getErrorMessage(error, 'Не удалось открыть лабораторный бланк. Проверьте соединение и попробуйте снова.')
      );
    }
  }, [loadReportHistory, notify, switchTab]);

  useEffect(() => {
    loadLabAppointments();
    loadTemplates();
    loadRecentReports();
  }, [loadLabAppointments, loadRecentReports, loadTemplates]);

  useEffect(() => {
    if (selectedAppointment?.patient_id) {
      loadReportHistory(selectedAppointment.patient_id);
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
      style={{
        padding: '24px',
        display: 'grid',
        gap: '16px',
        background: 'var(--mac-bg-primary)',
        minHeight: '100%'
      }}
    >
      {/* P-13 fix: skip-to-content link для keyboard-пользователей.
          Скрыт визуально, появляется при фокусе. Позволяет перескочить
          tablist и попасть прямо к содержимому активного таба. */}
      <a
        href={`#${LAB_PANEL_TABLIST_ID}`}
        style={{
          position: 'absolute',
          left: -9999,
          top: 'auto',
          width: 1,
          height: 1,
          overflow: 'hidden',
          padding: 0,
          margin: 0,
          clip: 'rect(0 0 0 0)',
          whiteSpace: 'nowrap',
          border: 0,
        }}
        onFocus={(e) => {
          e.target.style.cssText = [
            'position:fixed',
            'top:8px',
            'left:8px',
            'width:auto',
            'height:auto',
            'overflow:visible',
            'padding:8px 16px',
            'margin:0',
            'clip:auto',
            'white-space:nowrap',
            'background:var(--mac-accent)',
            'color:white',
            'border-radius:8px',
            'z-index:9999',
            'font-weight:600',
            'box-shadow:0 4px 12px rgba(0,0,0,0.2)',
          ].join(';');
        }}
        onBlur={(e) => {
          e.target.style.cssText = '';
        }}
      >
        Перейти к навигации по табам
      </a>
      <Card variant="filled" padding="none">
        <CardHeader
          style={{
            background: 'linear-gradient(135deg, color-mix(in oklab, var(--mac-accent) 12%, var(--mac-bg-tertiary)), var(--mac-bg-tertiary))',
            borderBottom: '1px solid var(--mac-border)',
            padding: '18px 20px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
            <h1
              id={LAB_PANEL_TITLE_ID}
              style={{
                margin: 0,
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-xl)',
                fontWeight: 700,
                lineHeight: 1.2
              }}
            >
              <Icon name="cross.case" size={22} />
              <span>Панель лаборатории</span>
            </h1>
            <div
              id={LAB_PANEL_TABLIST_ID}
              role="tablist"
              aria-labelledby={LAB_PANEL_TITLE_ID}
              style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}
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
            style={{ padding: '16px', background: 'var(--mac-bg-secondary)' }}
          >
            {/* QW-4 fix: Alert с кнопками «Повторить» (если есть retryAction)
                и «Закрыть». Раньше Alert только показывал текст — теперь
                пользователь может восстановиться после ошибки одним кликом. */}
            <Alert
              severity={message.type === 'error' ? 'error' : 'info'}
              action={(
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
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

      {activeTab === 'queue' && (
        <section
          id={getLabPanelTabPanelId('queue')}
          role="tabpanel"
          aria-labelledby={getLabPanelTabId('queue')}
          tabIndex={0}
        >
          <LabQueueWorkbench
            appointments={appointments}
            loading={appointmentsLoading}
            onRefresh={loadLabAppointments}
            onOpenAppointment={(appointment) => {
              setSelectedAppointment(appointment);
              setActiveInstance(null);
              setTemplateResolution(null);
              switchTab('reports');
            }}
            selectedAppointment={selectedAppointment}
            reportHistory={reportHistory}
          />
        </section>
      )}

      {activeTab === 'templates' && (
        <section
          id={getLabPanelTabPanelId('templates')}
          role="tabpanel"
          aria-labelledby={getLabPanelTabId('templates')}
          tabIndex={0}
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
      )}

      {activeTab === 'reports' && (
        <section
          id={getLabPanelTabPanelId('reports')}
          role="tabpanel"
          aria-labelledby={getLabPanelTabId('reports')}
          tabIndex={0}
        >
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
      )}

      <RoleNotificationCenter userRole="lab" />
    </main>
  );
}
