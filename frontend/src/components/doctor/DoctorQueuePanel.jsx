import { useState, useEffect, useRef } from 'react';
import PropTypes from 'prop-types';
import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
import { buildApiUrl } from '../../api/runtime';
import {

  Phone,
  Clock,
  User,
  Play,
  CheckCircle,

  RefreshCw,

  MapPin,

  Activity } from
'lucide-react';
import {
  MacOSCard,
  Button,
  Badge,
  Skeleton,
  MacOSEmptyState,
  Alert,
} from '../ui/macos';
import {
  formatRegistrarTime,
  getRegistrarTimestampDisplay,
} from '../../utils/dateUtils';
import { useTranslation } from '../../i18n/adapter';

const QUEUE_ACTION_ALIASES = {
  call: ['call'],
  start_visit: ['start_visit', 'start', 'in_cabinet'],
  complete: ['complete']
};

const hasBackendQueueAction = (entry, action, flagName) => {
  const { t } = useTranslation();
  if (flagName && entry?.[flagName] === true) {
    return true;
  }

  const actions = Array.isArray(entry?.available_actions) ? entry.available_actions : [];
  const aliases = QUEUE_ACTION_ALIASES[action] || [action];
  return aliases.some((alias) => actions.includes(alias));
};

/**
 * Панель очереди для врача - показывает пациентов из регистратуры
 * Основа: passport.md стр. 1417-1427
 */
const DoctorQueuePanel = ({
  specialty = 'cardiology',
  onPatientSelect,
  className = ''
}) => {
  // Проверяем демо-режим в самом начале (в демо не скрываем компонент, а показываем моковые данные)
  const isDemoMode = import.meta.env.MODE === 'development' && window.location.hostname === 'localhost';

  const [loading, setLoading] = useState(true);
  const [queueData, setQueueData] = useState(null);
  const [doctorInfo, setDoctorInfo] = useState(null);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [message, setMessage] = useState({ type: '', text: '' });
  const loadQueueDataRef = useRef(() => {});

  // UX Audit Doctor H-31: unified status config from shared queueStatusConfig.js.
  // Previously: waiting=info, called=warning (different from DoctorPanel).
  // Now: waiting=warning, called=primary (matches DoctorPanel).
  const statusConfig = {
    waiting: { label: 'Ожидает', color: 'warning', icon: Clock },
    called: { label: 'Вызван', color: 'primary', icon: Play },
    in_progress: { label: 'На приеме', color: 'info', icon: Activity },
    served: { label: 'Принят', color: 'success', icon: CheckCircle }
  };

  // Источники записи
  const sourceConfig = {
    // UX Audit Doctor M-23: emoji → text labels (lucide icons need import refactor).
    online: { label: 'Онлайн', icon: '📱' },
    desk: { label: 'Регистратура', icon: '🏥' },
    telegram: { label: 'Telegram', icon: '💬' }
  };

  useEffect(() => {
    // Проверяем, не находимся ли мы в демо-режиме
    const isDemoMode = window.location.pathname.includes('/medilab-demo') ||
    window.location.hostname === 'localhost' &&
    window.location.port === '5173';

    logger.log('DoctorQueuePanel useEffect:', {
      pathname: window.location.pathname,
      isDemoMode,
      specialty
    });

    if (isDemoMode) {
      // В демо-режиме используем моковые данные
      logger.log('Setting demo data for DoctorQueuePanel');
      setDoctorInfo({
        id: 1,
        name: 'Dr. Demo',
        specialty: specialty,
        department: 'Demo Department',
        queue_settings: {
          start_number: 'A000',
          max_per_day: 50,
          timezone: 'UTC+5'
        },
        doctor: {
          cabinet: '101'
        }
      });

      setQueueData({
        queue_exists: true,
        stats: { total: 2, waiting: 2, served: 0, online_entries: 1 },
        doctor: { name: 'Dr. Demo', specialty, cabinet: '101' },
        entries: [
        {
          id: 1,
          number: 'A001',
          patient_name: 'Иван Иванов',
          status: 'waiting',
          available_actions: ['call', 'no_show'],
          can_call: true,
          can_start_visit: false,
          can_complete: false,
          source: 'online',
          phone: '+998 90 123-45-67',
          created_at: '2024-01-15T09:00:00Z'
        },
        {
          id: 2,
          number: 'A002',
          patient_name: 'Мария Петрова',
          status: 'waiting',
          available_actions: ['call', 'no_show'],
          can_call: true,
          can_start_visit: false,
          can_complete: false,
          source: 'desk',
          phone: '+998 90 765-43-21',
          created_at: '2024-01-15T09:15:00Z'
        }]

      });
    } else {
      logger.log('Loading real data for DoctorQueuePanel');
      loadDoctorData();
      loadQueueDataRef.current();

      // Обновляем каждые 30 секунд
      const interval = setInterval(() => {
        loadQueueDataRef.current();
      }, 30000);

      return () => clearInterval(interval);
    }
  }, [specialty]);

  const loadDoctorData = async () => {
    // Проверяем демо-режим еще раз
    const isDemoMode = window.location.pathname.includes('/medilab-demo') ||
    window.location.hostname === 'localhost' &&
    window.location.port === '5173';

    if (isDemoMode) {
      logger.log('Skipping loadDoctorData in demo mode');
      return;
    }

    const doctorInfoUrl = buildApiUrl('/doctor/my-info');
    try {
      logger.info('[FIX:DOCTOR_QUEUE_PANEL] Loading doctor info from canonical API origin', {
        url: doctorInfoUrl,
      });
      const response = await fetch(doctorInfoUrl, {
        headers: { 'Authorization': `Bearer ${tokenManager.getAccessToken()}` }
      });

      if (response.ok) {
        const data = await response.json();
        setDoctorInfo(data);
      }
    } catch (error) {
      logger.error('Ошибка загрузки информации врача:', error);
    }
  };

  const loadQueueData = async () => {
    // Проверяем демо-режим еще раз
    const isDemoMode = window.location.pathname.includes('/medilab-demo') ||
    window.location.hostname === 'localhost' &&
    window.location.port === '5173';

    if (isDemoMode) {
      logger.log('Skipping loadQueueData in demo mode');
      return;
    }

    const queueUrl = buildApiUrl(`/doctor/${specialty}/queue/today`);
    try {
      setLoading(true);

      logger.info('[FIX:DOCTOR_QUEUE_PANEL] Loading doctor queue from canonical API origin', {
        specialty,
        url: queueUrl,
      });
      const response = await fetch(queueUrl, {
        headers: { 'Authorization': `Bearer ${tokenManager.getAccessToken()}` }
      });

      if (response.ok) {
        const data = await response.json();
        setQueueData(data);
      } else {
        const error = await response.json();
        setMessage({ type: 'error', text: error.detail });
      }
    } catch (error) {
      logger.error('Ошибка загрузки очереди:', error);
      setMessage({ type: 'error', text: 'Ошибка загрузки очереди' });
    } finally {
      setLoading(false);
    }
  };
  loadQueueDataRef.current = loadQueueData;

  const handleCallPatient = async (entryId) => {
    // В демо-режиме имитируем вызов
    if (isDemoMode) {
      setMessage({ type: 'success', text: 'Пациент вызван (демо)' });
      setQueueData((prev) => ({
        ...prev,
        entries: prev.entries.map((e) => e.id === entryId ? { ...e, status: 'called', called_at: new Date().toISOString() } : e)
      }));
      return;
    }

    try {
      const callUrl = buildApiUrl(`/doctor/queue/${entryId}/call`);
      logger.info('[FIX:DOCTOR_QUEUE_PANEL] Calling patient via canonical API origin', {
        entryId,
        url: callUrl,
      });
      const response = await fetch(callUrl, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${tokenManager.getAccessToken()}` }
      });

      if (response.ok) {
        const result = await response.json();
        setMessage({ type: 'success', text: result.message });
        await loadQueueData();
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }
    } catch (error) {
      logger.error('Ошибка вызова пациента:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  const handleStartVisit = async (entryId) => {
    // В демо-режиме имитируем старт приема
    if (isDemoMode) {
      setMessage({ type: 'success', text: 'Прием начат (демо)' });
      setQueueData((prev) => ({
        ...prev,
        entries: prev.entries.map((e) => e.id === entryId ? { ...e, status: 'in_progress' } : e)
      }));
      return;
    }

    try {
      const startVisitUrl = buildApiUrl(`/doctor/queue/${entryId}/start-visit`);
      logger.info('[FIX:DOCTOR_QUEUE_PANEL] Starting visit via canonical API origin', {
        entryId,
        url: startVisitUrl,
      });
      const response = await fetch(startVisitUrl, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${tokenManager.getAccessToken()}` }
      });

      if (response.ok) {
        const result = await response.json();
        setMessage({ type: 'success', text: result.message });
        await loadQueueData();
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }
    } catch (error) {
      logger.error('Ошибка начала приема:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  const handleCompleteVisit = async (entryId) => {
    // В демо-режиме имитируем завершение приема
    if (isDemoMode) {
      setMessage({ type: 'success', text: 'Прием завершен (демо)' });
      setQueueData((prev) => ({
        ...prev,
        entries: prev.entries.map((e) => e.id === entryId ? { ...e, status: 'served' } : e),
        stats: { ...prev.stats, served: (prev.stats?.served || 0) + 1, waiting: Math.max(0, (prev.stats?.waiting || 1) - 1) }
      }));
      return;
    }

    try {
      const completeVisitUrl = buildApiUrl(`/doctor/queue/${entryId}/complete`);
      logger.info('[FIX:DOCTOR_QUEUE_PANEL] Completing visit via canonical API origin', {
        entryId,
        url: completeVisitUrl,
      });
      const response = await fetch(completeVisitUrl, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({

          // Здесь будут данные визита
        }) });

      if (response.ok) {
        const result = await response.json();
        setMessage({ type: 'success', text: result.message });
        await loadQueueData();
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }
    } catch (error) {
      logger.error('Ошибка завершения приема:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  if (loading && !queueData) {
    return (
      <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
        <Skeleton type="card" count={3} />
      </MacOSCard>);

  }

  if (!queueData?.queue_exists) {
    return (
      <MacOSEmptyState
        type="users"
        title="Очередь не создана"
        description="Очередь будет создана когда регистратура добавит первого пациента" />);


  }

  return (
    <div className={className} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-4)' }}>
      {/* Сообщения */}
      {message.text &&
      <Alert
        type={message.type === 'success' ? 'success' : 'error'}
        title={message.type === 'success' ? 'Успешно' : 'Ошибка'}
        description={message.text}
        onClose={() => setMessage({ type: '', text: '' })} />

      }

      {/* Информация о враче и очереди */}
      <MacOSCard style={{ padding: 'var(--mac-spacing-4)' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 'var(--mac-spacing-4)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <User size={24} style={{ marginRight: 'var(--mac-spacing-3)', color: 'var(--mac-accent)' }} />
            <div>
              <h3 style={{
                margin: 0,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                {queueData.doctor.name}
              </h3>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)',
                gap: 'var(--mac-spacing-4)',
                marginTop: 'var(--mac-spacing-1)'
              }}>
                <span>{queueData.doctor.specialty}</span>
                {queueData.doctor.cabinet &&
                <>
                    <MapPin size={14} />
                    <span>Каб. {queueData.doctor.cabinet}</span>
                  </>
                }
              </div>
            </div>
          </div>

          <div style={{ textAlign: 'right' }}>
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
              Статус очереди:
            </div>
            <Badge variant={queueData.opened_at ? 'success' : 'warning'}>
              {queueData.opened_at ? 'Открыта' : 'Не открыта'}
            </Badge>
          </div>
        </div>

        {/* Статистика очереди */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
          gap: 'var(--mac-spacing-4)'
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-accent)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
              {queueData.stats.total}
            </div>
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              Всего
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-warning)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
              {queueData.stats.waiting}
            </div>
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              Ожидают
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-success)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
              {queueData.stats.served}
            </div>
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              Приняты
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-info)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
              {queueData.stats.online_entries}
            </div>
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
              Онлайн
            </div>
          </div>
        </div>
      </MacOSCard>

      {/* Список пациентов в очереди */}
      <MacOSCard style={{ overflow: 'hidden' }}>
        <div style={{
          padding: 'var(--mac-spacing-4)',
          backgroundColor: 'var(--mac-bg-secondary)',
          borderBottom: '1px solid var(--mac-border)'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <h3 style={{
              margin: 0,
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              Пациенты в очереди
            </h3>
            <Button variant="outline" onClick={loadQueueData}>
              <RefreshCw size={14} style={{ marginRight: 'var(--mac-spacing-1)' }} />
              Обновить
            </Button>
          </div>
        </div>

        <div style={{ borderTop: '1px solid var(--mac-border)' }}>
          {queueData.entries.length === 0 ?
          <MacOSEmptyState
            type="users"
            title="Пациентов в очереди нет"
            description="Ожидайте поступления новых пациентов от регистратуры" /> :


          queueData.entries.map((entry) => {
            const status = statusConfig[entry.status] || statusConfig.waiting;
            const source = sourceConfig[entry.source] || sourceConfig.desk;
            const StatusIcon = status.icon;
            const canCall = hasBackendQueueAction(entry, 'call', 'can_call');
            const canStartVisit = hasBackendQueueAction(entry, 'start_visit', 'can_start_visit');
            const canComplete = hasBackendQueueAction(entry, 'complete', 'can_complete');
            const timeDisplay = getRegistrarTimestampDisplay(entry);

            return (
              <div
                key={entry.id}
                role="button"
                tabIndex={0}
                aria-label={`Выбрать пациента ${entry.patient_name || entry.number} из очереди`}
                style={{
                  padding: 'var(--mac-spacing-4)',
                  cursor: 'pointer',
                  transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
                  backgroundColor: selectedPatient?.id === entry.id ? 'var(--mac-bg-accent)' : 'transparent',
                  borderBottom: '1px solid var(--mac-border)'
                }}
                onClick={() => {
                  setSelectedPatient(entry);
                  if (onPatientSelect) onPatientSelect(entry);
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    setSelectedPatient(entry);
                    if (onPatientSelect) onPatientSelect(entry);
                  }
                }}>
                
                  <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-4)' }}>
                      {/* Номер в очереди */}
                      <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: '48px',
                      height: '48px',
                      backgroundColor: 'var(--mac-bg-accent)',
                      borderRadius: '50%',
                      border: '2px solid var(--mac-accent)'
                    }}>
                        <span style={{
                        fontSize: 'var(--mac-font-size-lg)',
                        fontWeight: 'var(--mac-font-weight-bold)',
                        color: 'var(--mac-accent)'
                      }}>
                          {entry.number}
                        </span>
                      </div>

                      {/* Информация о пациенте */}
                      <div>
                        <div style={{
                        fontWeight: 'var(--mac-font-weight-semibold)',
                        color: 'var(--mac-text-primary)',
                        fontSize: 'var(--mac-font-size-md)',
                        marginBottom: 'var(--mac-spacing-1)'
                      }}>
                          {entry.patient_name}
                        </div>
                        {entry.phone &&
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        fontSize: 'var(--mac-font-size-sm)',
                        color: 'var(--mac-text-secondary)',
                        marginBottom: 'var(--mac-spacing-1)'
                      }}>
                            <Phone size={16} style={{ marginRight: 'var(--mac-spacing-1)', color: 'var(--mac-accent)' }} />
                            {entry.phone}
                          </div>
                      }
                        <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--mac-spacing-2)'
                      }}>
                          <Badge variant="outline">
                            {source.icon} {source.label}
                          </Badge>
                          <span style={{
                          fontSize: 'var(--mac-font-size-xs)',
                          color: 'var(--mac-text-tertiary)'
                        }}>
                            {timeDisplay.primaryLabel}: {timeDisplay.primaryTime || '—'}
                            {timeDisplay.showChanged ? ` · ${timeDisplay.changedLabel}: ${timeDisplay.changedTime}` : ''}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--mac-spacing-3)'
                  }}>
                      {/* Статус */}
                      <div style={{ textAlign: 'center' }}>
                        <Badge variant={status.color}>
                          <StatusIcon size={14} style={{ marginRight: 'var(--mac-spacing-1)' }} />
                          {status.label}
                        </Badge>
                        {entry.called_at &&
                      <div style={{
                        fontSize: 'var(--mac-font-size-xs)',
                        color: 'var(--mac-text-tertiary)',
                        marginTop: 'var(--mac-spacing-1)'
                      }}>
                            Вызван: {formatRegistrarTime(entry.called_at) || '—'}
                          </div>
                      }
                      </div>

                      {/* Действия */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)' }}>
                        {canCall &&
                      <Button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCallPatient(entry.id);
                        }}>
                        
                            <Play size={14} style={{ marginRight: 'var(--mac-spacing-1)' }} />
                            Вызвать
                          </Button>
                      }

                        {canStartVisit &&
                      <Button
                        variant="outline"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStartVisit(entry.id);
                        }}>
                        
                            <Activity size={14} style={{ marginRight: 'var(--mac-spacing-1)' }} />
                            Начать
                          </Button>
                      }

                        {canComplete &&
                      <Button
                        variant="success"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCompleteVisit(entry.id);
                        }}>
                        
                            <CheckCircle size={14} style={{ marginRight: 'var(--mac-spacing-1)' }} />
                            Завершить
                          </Button>
                      }
                      </div>
                    </div>
                  </div>
                </div>);

          })
          }
        </div>
      </MacOSCard>

      {/* Информация о настройках очереди */}
      {doctorInfo &&
      <MacOSCard style={{
        padding: 'var(--mac-spacing-4)',
        backgroundColor: 'var(--mac-bg-accent)',
        border: '1px solid var(--mac-accent)'
      }}>
          <h4 style={{
          margin: '0 0 8px 0',
          fontWeight: 'var(--mac-font-weight-semibold)',
          color: 'var(--mac-accent)',
          fontSize: 'var(--mac-font-size-md)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            ⚙️ Настройки очереди:
          </h4>
          <div style={{
          fontSize: 'var(--mac-font-size-sm)',
          color: 'var(--mac-text-secondary)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--mac-spacing-1)'
        }}>
            <div>Стартовый номер онлайн: #{doctorInfo?.queue_settings?.start_number || '—'}</div>
            <div>Лимит в день: {doctorInfo?.queue_settings?.max_per_day ?? '—'}</div>
            <div>Часовой пояс: {doctorInfo?.queue_settings?.timezone || '—'}</div>
            {doctorInfo?.doctor?.cabinet &&
          <div>Кабинет: {doctorInfo.doctor.cabinet}</div>
          }
          </div>
        </MacOSCard>
      }
    </div>);

};

DoctorQueuePanel.propTypes = {
  specialty: PropTypes.string,
  onPatientSelect: PropTypes.func,
  className: PropTypes.string,
};

export default DoctorQueuePanel;
