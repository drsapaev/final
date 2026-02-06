import React, { useState, useEffect } from 'react';
import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
import {
  Users,
  Phone,
  Clock,
  User,
  Play,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Calendar,
  MapPin,
  Hash,
  Activity
} from 'lucide-react';
import {
  MacOSCard,
  MacOSButton,
  MacOSBadge,
  MacOSLoadingSkeleton,
  MacOSEmptyState,
  MacOSAlert
} from '../ui/macos';

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
  const isDemoMode = window.location.pathname.includes('/medilab-demo') ||
    (window.location.hostname === 'localhost' &&
      window.location.port === '5173');

  const [loading, setLoading] = useState(true);
  const [queueData, setQueueData] = useState(null);
  const [doctorInfo, setDoctorInfo] = useState(null);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [message, setMessage] = useState({ type: '', text: '' });

  // Статусы пациентов с цветами
  const statusConfig = {
    waiting: { label: 'Ожидает', color: 'info', icon: Clock },
    called: { label: 'Вызван', color: 'warning', icon: Play },
    in_progress: { label: 'На приеме', color: 'primary', icon: Activity },
    served: { label: 'Принят', color: 'success', icon: CheckCircle }
  };

  // Источники записи
  const sourceConfig = {
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
            source: 'online',
            phone: '+998 90 123-45-67',
            created_at: '2024-01-15T09:00:00Z'
          },
          {
            id: 2,
            number: 'A002',
            patient_name: 'Мария Петрова',
            status: 'waiting',
            source: 'desk',
            phone: '+998 90 765-43-21',
            created_at: '2024-01-15T09:15:00Z'
          }
        ]
      });
    } else {
      logger.log('Loading real data for DoctorQueuePanel');
      loadDoctorData();
      loadQueueData();

      // Обновляем каждые 30 секунд
      const interval = setInterval(() => {
        loadQueueData();
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

    try {
      const response = await fetch('http://127.0.0.1:8000/api/v1/doctor/my-info', {
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

    try {
      setLoading(true);

      const response = await fetch(`http://127.0.0.1:8000/api/v1/doctor/${specialty}/queue/today`, {
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

  const handleCallPatient = async (entryId) => {
    // В демо-режиме имитируем вызов
    if (isDemoMode) {
      setMessage({ type: 'success', text: 'Пациент вызван (демо)' });
      setQueueData((prev) => ({
        ...prev,
        entries: prev.entries.map(e => e.id === entryId ? { ...e, status: 'called', called_at: new Date().toISOString() } : e)
      }));
      return;
    }

    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/doctor/queue/${entryId}/call`, {
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
        entries: prev.entries.map(e => e.id === entryId ? { ...e, status: 'in_progress' } : e)
      }));
      return;
    }

    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/doctor/queue/${entryId}/start-visit`, {
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
        entries: prev.entries.map(e => e.id === entryId ? { ...e, status: 'served' } : e),
        stats: { ...prev.stats, served: (prev.stats?.served || 0) + 1, waiting: Math.max(0, (prev.stats?.waiting || 1) - 1) }
      }));
      return;
    }

    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/doctor/queue/${entryId}/complete`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          // Здесь будут данные визита
        })
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
      logger.error('Ошибка завершения приема:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  if (loading && !queueData) {
    return (
      <MacOSCard style={{ padding: '24px' }}>
        <MacOSLoadingSkeleton type="card" count={3} />
      </MacOSCard>
    );
  }

  if (!queueData?.queue_exists) {
    return (
      <MacOSEmptyState
        type="users"
        title="Очередь не создана"
        description="Очередь будет создана когда регистратура добавит первого пациента"
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Сообщения */}
      {message.text && (
        <MacOSAlert
          type={message.type === 'success' ? 'success' : 'error'}
          title={message.type === 'success' ? 'Успешно' : 'Ошибка'}
          description={message.text}
          onClose={() => setMessage({ type: '', text: '' })}
        />
      )}

      {/* Информация о враче и очереди */}
      <MacOSCard style={{ padding: '16px' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '16px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <User size={24} style={{ marginRight: '12px', color: 'var(--mac-accent)' }} />
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
                gap: '16px',
                marginTop: '4px'
              }}>
                <span>{queueData.doctor.specialty}</span>
                {queueData.doctor.cabinet && (
                  <>
                    <MapPin size={14} />
                    <span>Каб. {queueData.doctor.cabinet}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          <div style={{ textAlign: 'right' }}>
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)',
              marginBottom: '4px'
            }}>
              Статус очереди:
            </div>
            <MacOSBadge variant={queueData.opened_at ? 'success' : 'warning'}>
              {queueData.opened_at ? 'Открыта' : 'Не открыта'}
            </MacOSBadge>
          </div>
        </div>

        {/* Статистика очереди */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
          gap: '16px'
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-accent)',
              marginBottom: '4px'
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
              marginBottom: '4px'
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
              marginBottom: '4px'
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
              marginBottom: '4px'
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
          padding: '16px',
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
            <MacOSButton variant="outline" onClick={loadQueueData}>
              <RefreshCw size={14} style={{ marginRight: '4px' }} />
              Обновить
            </MacOSButton>
          </div>
        </div>

        <div style={{ borderTop: '1px solid var(--mac-border)' }}>
          {queueData.entries.length === 0 ? (
            <MacOSEmptyState
              type="users"
              title="Пациентов в очереди нет"
              description="Ожидайте поступления новых пациентов от регистратуры"
            />
          ) : (
            queueData.entries.map(entry => {
              const status = statusConfig[entry.status] || statusConfig.waiting;
              const source = sourceConfig[entry.source] || sourceConfig.desk;
              const StatusIcon = status.icon;

              return (
                <div
                  key={entry.id}
                  style={{
                    padding: '16px',
                    cursor: 'pointer',
                    transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
                    backgroundColor: selectedPatient?.id === entry.id ? 'var(--mac-bg-accent)' : 'transparent',
                    borderBottom: '1px solid var(--mac-border)'
                  }}
                  onClick={() => {
                    setSelectedPatient(entry);
                    if (onPatientSelect) onPatientSelect(entry);
                  }}
                >
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
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
                          marginBottom: '4px'
                        }}>
                          {entry.patient_name}
                        </div>
                        {entry.phone && (
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            fontSize: 'var(--mac-font-size-sm)',
                            color: 'var(--mac-text-secondary)',
                            marginBottom: '4px'
                          }}>
                            <Phone size={16} style={{ marginRight: '4px', color: 'var(--mac-accent)' }} />
                            {entry.phone}
                          </div>
                        )}
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px'
                        }}>
                          <MacOSBadge variant="outline">
                            {source.icon} {source.label}
                          </MacOSBadge>
                          <span style={{
                            fontSize: 'var(--mac-font-size-xs)',
                            color: 'var(--mac-text-tertiary)'
                          }}>
                            {new Date(entry.created_at).toLocaleTimeString('ru-RU', {
                              hour: '2-digit',
                              minute: '2-digit'
                            })}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px'
                    }}>
                      {/* Статус */}
                      <div style={{ textAlign: 'center' }}>
                        <MacOSBadge variant={status.color}>
                          <StatusIcon size={14} style={{ marginRight: '4px' }} />
                          {status.label}
                        </MacOSBadge>
                        {entry.called_at && (
                          <div style={{
                            fontSize: 'var(--mac-font-size-xs)',
                            color: 'var(--mac-text-tertiary)',
                            marginTop: '4px'
                          }}>
                            Вызван: {new Date(entry.called_at).toLocaleTimeString('ru-RU', {
                              hour: '2-digit',
                              minute: '2-digit'
                            })}
                          </div>
                        )}
                      </div>

                      {/* Действия */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {entry.status === 'waiting' && (
                          <MacOSButton
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCallPatient(entry.id);
                            }}
                          >
                            <Play size={14} style={{ marginRight: '4px' }} />
                            Вызвать
                          </MacOSButton>
                        )}

                        {entry.status === 'called' && (
                          <MacOSButton
                            variant="outline"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleStartVisit(entry.id);
                            }}
                          >
                            <Activity size={14} style={{ marginRight: '4px' }} />
                            Начать
                          </MacOSButton>
                        )}

                        {entry.status === 'in_progress' && (
                          <MacOSButton
                            variant="success"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCompleteVisit(entry.id);
                            }}
                          >
                            <CheckCircle size={14} style={{ marginRight: '4px' }} />
                            Завершить
                          </MacOSButton>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </MacOSCard>

      {/* Информация о настройках очереди */}
      {doctorInfo && (
        <MacOSCard style={{
          padding: '16px',
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
            gap: '8px'
          }}>
            ⚙️ Настройки очереди:
          </h4>
          <div style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-secondary)',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px'
          }}>
            <div>Стартовый номер онлайн: #{doctorInfo?.queue_settings?.start_number || '—'}</div>
            <div>Лимит в день: {doctorInfo?.queue_settings?.max_per_day ?? '—'}</div>
            <div>Часовой пояс: {doctorInfo?.queue_settings?.timezone || '—'}</div>
            {doctorInfo?.doctor?.cabinet && (
              <div>Кабинет: {doctorInfo.doctor.cabinet}</div>
            )}
          </div>
        </MacOSCard>
      )}
    </div>
  );
};

export default DoctorQueuePanel;

