import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import {
  Card, Button, Badge, Icon,
} from '../components/ui/macos';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import logger from '../utils/logger';
import { api } from '../api/client';
import {
  readTelegramMiniAppInitData,
  describePatientError,
} from '../components/patient/patientUtils';
import {
  PATIENT_SECTIONS,
  VISIBLE_PATIENT_TABS,
  normalizeSection,
} from '../components/patient/patientSections';
import PanelEmptyState from '../components/patient/PanelEmptyState';
import PatientBookingPanel from '../components/patient/PatientBookingPanel';
import PatientCabinetSummary from '../components/patient/PatientCabinetSummary';
import PatientFormsPreview from '../components/patient/PatientFormsPreview';
import './patient.css';

/**
 * PatientPanel — корневой контейнер для patient-facing веб-панели.
 *
 * L-H-1 fix: все строки переведены на русский (были на английском).
 * L-H-2 fix: Tailwind utility-classes заменены на CSS-классы .pp-*
 * L-H-3 fix: мёртвый search-input удалён (state обновлялся, но не фильтровал).
 * L-H-4 fix: монолит 1138 строк декомпозирован — подкомпоненты вынесены
 *   в components/patient/ (PanelEmptyState, PatientBookingPanel,
 *   PatientCabinetSummary, PatientFormsPreview).
 * L-H-6 fix: добавлен tablist-pattern для навигации по секциям
 *   (role=tablist + role=tab + aria-selected + keyboard nav).
 * L-H-8 fix: lucide-direct icons заменены на macos <Icon>.
 *
 * Доступ: /patient (hideSidebar:true, homeForRoles:['patient']).
 * Защищённые данные требуют Telegram Mini App identity (initData).
 */
const PatientPanel = () => {
  useBreakpoint();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();

  // L-H-6 fix: activeSection вычисляется из URL (path или ?tab=).
  const activeSection = (() => {
    if (location.pathname === '/patient/bookings') {
      return 'booking';
    }
    if (location.pathname === '/patient/payments') {
      return 'payments';
    }
    return normalizeSection(searchParams.get('tab'));
  })();

  const [formsPreview, setFormsPreview] = useState(null);
  const [formsStatus, setFormsStatus] = useState('idle');
  const [formsError, setFormsError] = useState('');
  const [formsInitData, setFormsInitData] = useState('');

  // P1 fix: backend endpoints /patients/appointments and /patients/results
  const [appointments, setAppointments] = useState([]);
  const [results, setResults] = useState([]);

  useEffect(() => {
    let cancelled = false;

    async function loadPatientData() {
      try {
        const [apptRes, resultsRes] = await Promise.allSettled([
          api.get('/patients/appointments'),
          api.get('/patients/results'),
        ]);
        if (cancelled) return;
        if (apptRes.status === 'fulfilled') {
          setAppointments(Array.isArray(apptRes.value.data) ? apptRes.value.data : []);
        }
        if (resultsRes.status === 'fulfilled') {
          setResults(Array.isArray(resultsRes.value.data) ? resultsRes.value.data : []);
        }
      } catch (error) {
        logger.error('Error loading patient data:', error);
      }
    }

    loadPatientData();
    return () => { cancelled = true; };
  }, []);

  const hasPatientData = appointments.length > 0 || results.length > 0;
  const sectionConfig = PATIENT_SECTIONS[activeSection];
  const isSectionMode = Boolean(sectionConfig);
  const sectionTitle = sectionConfig?.title || 'Главная пациента';

  useEffect(() => {
    if (activeSection !== 'forms') {
      setFormsStatus('idle');
      setFormsPreview(null);
      setFormsError('');
      setFormsInitData('');
      return undefined;
    }

    const initData = readTelegramMiniAppInitData();
    if (!initData) {
      setFormsStatus('missing-init-data');
      setFormsPreview(null);
      setFormsError('');
      setFormsInitData('');
      return undefined;
    }

    let cancelled = false;
    setFormsStatus('loading');
    setFormsError('');
    setFormsPreview(null);
    setFormsInitData(initData);

    api.post('/telegram/mini-app/forms/preview', { initData })
      .then((response) => {
        if (cancelled) return;
        setFormsPreview(response.data);
        setFormsStatus('ready');
      })
      .catch((err) => {
        if (cancelled) return;
        const reason = err?.response?.data?.detail?.reason || 'forms_preview_failed';
        setFormsError(describePatientError('forms', reason));
        setFormsStatus('error');
      });

    return () => { cancelled = true; };
  }, [activeSection]);

  // L-H-6 fix: tablist navigation handlers.
  const switchSection = useCallback((sectionId) => {
    // 'home' — отдельный случай (no ?tab= param)
    if (sectionId === 'home') {
      setSearchParams({}, { replace: true });
      return;
    }
    setSearchParams({ tab: sectionId }, { replace: true });
  }, [setSearchParams]);

  const handleTabKeyDown = useCallback((event, currentSectionId) => {
    const tabs = ['home', ...VISIBLE_PATIENT_TABS];
    const currentIndex = tabs.indexOf(currentSectionId);
    if (currentIndex === -1) return;

    let nextIndex = null;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      nextIndex = (currentIndex + 1) % tabs.length;
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    } else if (event.key === 'Home') {
      nextIndex = 0;
    } else if (event.key === 'End') {
      nextIndex = tabs.length - 1;
    }

    if (nextIndex !== null) {
      event.preventDefault();
      switchSection(tabs[nextIndex]);
      window.requestAnimationFrame(() => {
        document.getElementById(`pp-tab-${tabs[nextIndex]}`)?.focus();
      });
    }
  }, [switchSection]);

  // L-H-6 fix: build tablist items (home + visible sections).
  const tabItems = useMemo(() => [
    { id: 'home', label: 'Главная', icon: 'house' },
    ...VISIBLE_PATIENT_TABS.map((key) => ({
      id: key,
      label: PATIENT_SECTIONS[key].title,
      icon: PATIENT_SECTIONS[key].icon,
    })),
  ], []);

  return (
    <div className="patient-root">
      <div className="patient-container">
        {/* L-H-6 fix: tablist-pattern для навигации по секциям.
            Заменяет скрытую URL-only навигацию на видимую tab-bar.
            role=tablist + role=tab + aria-selected + keyboard nav. */}
        <div
          className="pp-tablist"
          role="tablist"
          aria-label="Разделы панели пациента"
        >
          {tabItems.map((tab) => {
            const isActive = activeSection === tab.id || (tab.id === 'home' && !isSectionMode);
            return (
              <button
                key={tab.id}
                id={`pp-tab-${tab.id}`}
                type="button"
                role="tab"
                aria-selected={isActive}
                aria-controls="pp-tabpanel"
                tabIndex={isActive ? 0 : -1}
                onClick={() => switchSection(tab.id)}
                onKeyDown={(e) => handleTabKeyDown(e, tab.id)}
                className={`pp-tab ${isActive ? 'pp-tab-active' : ''}`}
              >
                <Icon name={tab.icon} size={16} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* L-H-3 fix: мёртвый search-input удалён.
            Раньше state `query` обновлялся, но не использовался для фильтрации.
            Search будет добавлен когда появится реальный search-target. */}

        <div id="pp-tabpanel" role="tabpanel" tabIndex={0}>
          {isSectionMode ? (
            <Card className="pp-card" data-testid={`patient-section-${activeSection}`}>
              <div className="pp-home-card-header">
                <Icon name={sectionConfig.icon} size={16} />
                <h3 className="pp-home-card-title">{sectionTitle}</h3>
              </div>
              <div className="pp-card-body">
                {activeSection === 'forms' ? (
                  <PatientFormsPreview
                    status={formsStatus}
                    preview={formsPreview}
                    error={formsError}
                    initData={formsInitData}
                  />
                ) : activeSection === 'booking' ? (
                  <PatientBookingPanel />
                ) : activeSection === 'cabinet' ? (
                  <PatientCabinetSummary />
                ) : activeSection === 'payments' ? (
                  <PatientCabinetSummary mode="payments" />
                ) : activeSection === 'documents' ? (
                  <PatientCabinetSummary mode="reports" />
                ) : (
                  <PanelEmptyState
                    icon={sectionConfig.icon}
                    title={sectionConfig.title}
                    description={sectionConfig.description}
                  />
                )}
              </div>
            </Card>
          ) : (
            <div className="pp-home-grid">
              <Card className="pp-card">
                <div className="pp-home-card-header">
                  <Icon name="calendar" size={16} />
                  <h3 className="pp-home-card-title">Предстоящие визиты</h3>
                </div>
                <div className="pp-home-list">
                  {appointments.length > 0 ? (
                    appointments.map((a) => (
                      <div key={a.id} className="pp-home-list-item">
                        <div>
                          <div className="pp-list-item-primary">{a.doctor}</div>
                          <div className="pp-list-item-secondary">{a.date} · {a.time}</div>
                        </div>
                        <Badge variant={a.status === 'scheduled' ? 'info' : 'success'}>
                          {a.status === 'scheduled' ? 'Запланирован' : 'Завершён'}
                        </Badge>
                      </div>
                    ))
                  ) : (
                    <PanelEmptyState
                      icon="calendar"
                      title="Визитов пока нет"
                      description="Добавьте визит после привязки с записью в клинике или регистратурой."
                    />
                  )}
                </div>
              </Card>

              <Card className="pp-card">
                <div className="pp-home-card-header">
                  <Icon name="heart" size={16} />
                  <h3 className="pp-home-card-title">Результаты анализов</h3>
                </div>
                <div className="pp-home-list">
                  {results.length > 0 ? (
                    results.map((r) => (
                      <div key={r.id} className="pp-home-list-item">
                        <div>
                          <div className="pp-list-item-primary">{r.title}</div>
                          <div className="pp-list-item-secondary">{r.date}</div>
                        </div>
                        <Button variant="outline" size="small">
                          <Icon name="doc.text" size={16} />
                          Открыть
                        </Button>
                      </div>
                    ))
                  ) : (
                    <PanelEmptyState
                      icon="doc.text"
                      title="Результатов пока нет"
                      description="Используйте защищённую ссылку на отчёт, когда результаты будут готовы."
                    />
                  )}
                </div>
              </Card>
            </div>
          )}
        </div>

        {/* L-H-3 fix: подсказка для Quick Action вместо мёртвого disabled-button.
            Показываем контекстную подсказку вместо disabled-кнопки без объяснения. */}
        {!hasPatientData && (
          <Card className="pp-card">
            <div className="pp-card-body">
              <PanelEmptyState
                icon="exclamationmark.triangle"
                title="Данные пациента загружаются"
                description="Записи и результаты появятся после загрузки. Используйте вкладки выше для доступа к защищённым разделам."
                variant="loading"
              />
            </div>
          </Card>
        )}
      </div>
    </div>
  );
};

export default PatientPanel;
