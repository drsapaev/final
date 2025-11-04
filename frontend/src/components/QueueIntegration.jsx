import React, { useState, useEffect } from 'react';
import { Users, Clock, UserCheck, AlertCircle, CheckCircle } from 'lucide-react';
import { MacOSCard, MacOSButton, MacOSBadge, MacOSLoadingSkeleton, MacOSEmptyState } from './ui/macos';
import { APPOINTMENT_STATUS, STATUS_LABELS, STATUS_COLORS } from '../constants/appointmentStatus';

const QueueIntegration = ({ specialist = 'Дерматолог', onPatientSelect, onStartVisit, department }) => {
  // Проверяем демо-режим в самом начале
  const isDemoMode = window.location.pathname.includes('/medilab-demo');
  
  // В демо-режиме не рендерим компонент
  if (isDemoMode) {
    console.log('QueueIntegration: Skipping render in demo mode');
    return null;
  }
  
  const [queue, setQueue] = useState([]);
  const [currentCall, setCurrentCall] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadQueue();
    // Обновляем очередь каждые 15 секунд для лучшей синхронизации
    const interval = setInterval(loadQueue, 15000);
    
    // Слушаем глобальные события обновления очереди
    const handleQueueUpdate = (event) => {
      console.log('[QueueIntegration] Получено событие обновления очереди:', event.detail);
      const { action } = event.detail || {};
      
      // Для завершения приёма добавляем задержку для гарантии синхронизации с бэкендом
      if (action === 'visitCompleted') {
        console.log('[QueueIntegration] Обновление очереди после завершения приёма с задержкой');
        setTimeout(() => {
          loadQueue();
        }, 800); // Увеличиваем задержку для гарантии синхронизации
      } else {
        // Для других действий обновляем немедленно
        loadQueue();
      }
    };
    window.addEventListener('queueUpdated', handleQueueUpdate);
    
    return () => {
      clearInterval(interval);
      window.removeEventListener('queueUpdated', handleQueueUpdate);
    };
  }, [specialist]);

  const loadQueue = async () => {
    setLoading(true);
    try {
      console.log('[QueueIntegration] loadQueue: start', { specialist });
      // Используем новый API endpoint для получения всех очередей
      const apiUrl = 'http://localhost:8000/api/v1/registrar/queues/today';
      const token = localStorage.getItem('auth_token');

      if (!token) {
        console.warn('[QueueIntegration] loadQueue: нет токена авторизации');
        setLoading(false);
        return;
      }

      const response = await fetch(apiUrl, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        const errorText = await response.text().catch(() => '');
        console.error('[QueueIntegration] loadQueue: HTTP error', {
          status: response.status,
          statusText: response.statusText,
          error: errorText
        });
        throw new Error(`Ошибка загрузки очереди: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log('[QueueIntegration] loadQueue: данные получены', { queuesCount: data?.queues?.length || 0 });
      
      // Обрабатываем новую структуру API с массивами очередей
      let queueEntries = [];
      if (data && data.queues && Array.isArray(data.queues)) {
        // Находим очередь для текущего специалиста
        const specialistQueue = data.queues.find(queue => {
          const queueSpecialty = queue.specialty;
          if (specialist === 'Дерматолог') {
            return queueSpecialty === 'derma' || queueSpecialty === 'dermatology';
          } else if (specialist === 'Кардиолог') {
            return queueSpecialty === 'cardio' || queueSpecialty === 'cardiology';
          } else if (specialist === 'Стоматолог') {
            return queueSpecialty === 'dental' || queueSpecialty === 'dentist' || queueSpecialty === 'dentistry';
          } else if (specialist === 'Лаборатория') {
            return queueSpecialty === 'lab' || queueSpecialty === 'laboratory';
          }
          return false;
        });
        
        if (specialistQueue && specialistQueue.entries) {
          // Дедупликация записей: один пациент может иметь несколько визитов в день,
          // но один и тот же appointment_id/record_id должен показываться только один раз
          const seenKeys = new Set();
          const uniqueEntries = [];
          
          // Сортируем записи по времени создания (самые ранние первыми)
          const sortedEntries = [...specialistQueue.entries].sort((a, b) => {
            const dateA = a.created_at ? new Date(a.created_at) : new Date(0);
            const dateB = b.created_at ? new Date(b.created_at) : new Date(0);
            return dateA - dateB;
          });
          
          for (const entry of sortedEntries) {
            // Создаем уникальный ключ: patient_id + appointment_id/id + created_at (дата без времени)
            // Это позволяет показывать несколько визитов одного пациента в день, но исключает точные дубликаты
            const recordId = entry.appointment_id || entry.id;
            const entryDate = entry.created_at ? entry.created_at.split('T')[0] : 'unknown';
            const uniqueKey = `${entry.patient_id}_${recordId}_${entryDate}`;
            
            if (seenKeys.has(uniqueKey)) {
              console.log('[QueueIntegration] Пропущен дубликат записи:', uniqueKey, entry.patient_name);
              continue;
            }
            
            seenKeys.add(uniqueKey);
            uniqueEntries.push({
              id: entry.id,
              patient_name: entry.patient_name,
              number: uniqueEntries.length + 1, // Переназначаем номера после дедупликации
              status: entry.status,
              created_at: entry.created_at,
              appointment_id: entry.appointment_id || entry.id,
              patient_id: entry.patient_id,
              payment_status: entry.payment_status || (entry.discount_mode === 'paid' ? 'paid' : 'pending'),
              discount_mode: entry.discount_mode || 'none'
            });
          }
          
          queueEntries = uniqueEntries;
          console.log('[QueueIntegration] После дедупликации:', queueEntries.length, 'уникальных записей из', sortedEntries.length, 'всего');
        }
      }
      
      console.log('[QueueIntegration] loadQueue: успешно загружено', queueEntries.length, 'записей');
      setQueue(queueEntries);
    } catch (error) {
      console.error('[QueueIntegration] loadQueue: ошибка', error);
      // Не показываем ошибку пользователю, так как это может быть временная проблема
    } finally {
      setLoading(false);
      console.log('[QueueIntegration] loadQueue: finish');
    }
  };

  const callPatient = async (patient) => {
    try {
      // Используем новый API endpoint для вызова пациента
      const apiUrl = `http://localhost:8000/api/v1/registrar/queue/${patient.id}/start-visit`;

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (response.ok) {
        setCurrentCall(patient);
        // Обновляем статус пациента в очереди
        setQueue(prev => prev.map(p => 
          p.id === patient.id ? { ...p, status: 'called' } : p
        ));
        
        // Автоматически скрываем вызов через 30 секунд
        setTimeout(() => {
          setCurrentCall(null);
        }, 30000);
      }
    } catch (error) {
      console.error('QueueIntegration: Call patient error:', error);
    }
  };

  const startVisit = async (patient) => {
    try {
      // Используем переданную функцию onStartVisit, если она есть
      if (onStartVisit) {
        onStartVisit(patient);
        setCurrentCall(null);
        return;
      }

      // Иначе создаем запись на прием через API
      const appointmentData = {
        patient_id: patient.id,
        patient_name: patient.patient_name,
        specialist: specialist,
        date: new Date().toISOString().split('T')[0],
        time: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
        status: APPOINTMENT_STATUS.PAID,
        services: [],
        total_cost: 0
      };

      const response = await fetch('http://localhost:8000/api/v1/appointments', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify(appointmentData)
      });

      if (response.ok) {
        const appointment = await response.json();
        if (onPatientSelect) {
          onPatientSelect(appointment);
        }
        setCurrentCall(null);
      }
    } catch (error) {
      console.error('QueueIntegration: Start visit error:', error);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case APPOINTMENT_STATUS.PENDING:
        return 'warning';
      case APPOINTMENT_STATUS.PAID:
        return 'success';
      case APPOINTMENT_STATUS.IN_VISIT:
        return 'info';
      case APPOINTMENT_STATUS.COMPLETED:
        return 'success';
      default:
        return 'secondary';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Текущий вызов */}
      {currentCall && (
        <MacOSCard style={{
          padding: '24px',
          border: '2px solid var(--mac-blue-500)',
          backgroundColor: 'var(--mac-blue-50)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{
                width: '64px',
                height: '64px',
                backgroundColor: 'var(--mac-blue-500)',
                color: 'white',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '24px',
                fontWeight: '700'
              }}>
                {currentCall.number}
              </div>
              <div>
                <div style={{
                  fontSize: '20px',
                  fontWeight: '600',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
                  marginBottom: '4px'
                }}>{currentCall.patient_name}</div>
                <div style={{
                  color: 'var(--mac-blue-600)',
                  fontSize: '14px',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                }}>Вызван в кабинет</div>
              </div>
            </div>
            
            <div style={{ display: 'flex', gap: '8px' }}>
              <MacOSButton
                variant="success"
                onClick={() => startVisit(currentCall)}
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <UserCheck size={16} />
                Начать прием
              </MacOSButton>
              <MacOSButton
                variant="outline"
                onClick={() => setCurrentCall(null)}
              >
                Отменить
              </MacOSButton>
            </div>
          </div>
        </MacOSCard>
      )}

      {/* Очередь */}
      <MacOSCard style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Users size={24} style={{ color: 'var(--mac-blue-500)' }} />
            <div>
              <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
                margin: 0,
                marginBottom: '4px'
              }}>Очередь: {specialist}</h3>
              <p style={{
                fontSize: '13px',
                color: 'var(--mac-text-secondary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
                margin: 0
              }}>
                {loading ? 'Загрузка...' : `${queue.length} пациентов в очереди`}
              </p>
            </div>
          </div>
          
          <MacOSButton
            variant="outline"
            onClick={loadQueue}
            disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', padding: '6px 12px' }}
          >
            <Clock size={16} />
            Обновить
          </MacOSButton>
        </div>

        {loading ? (
          <MacOSLoadingSkeleton type="list" count={5} />
        ) : queue.length === 0 ? (
          <MacOSEmptyState
            type="users"
            title="Очередь пуста"
            description="В очереди пока нет пациентов"
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {queue.map((patient, index) => (
              <div
                key={patient.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '16px',
                  borderRadius: 'var(--mac-radius-lg)',
                  border: index === 0 ? '2px solid var(--mac-blue-500)' : '1px solid var(--mac-border)',
                  backgroundColor: index === 0 ? 'var(--mac-blue-50)' : 'var(--mac-bg-primary)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    fontWeight: '700',
                    backgroundColor: index === 0 ? 'var(--mac-blue-500)' : 'var(--mac-gray-500)'
                  }}>
                    {patient.number}
                  </div>
                  <div>
                    <div style={{
                      fontSize: '16px',
                      fontWeight: '600',
                      color: 'var(--mac-text-primary)',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
                      marginBottom: '4px'
                    }}>{patient.patient_name}</div>
                    <div style={{
                      fontSize: '13px',
                      color: 'var(--mac-text-secondary)',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                      {patient.type} • {patient.phone}
                    </div>
                  </div>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <MacOSBadge variant={patient.source === 'online' ? 'success' : 'info'}>
                    {patient.source === 'online' ? 'Онлайн' : 'Регистратура'}
                  </MacOSBadge>
                  
                  <MacOSButton
                    onClick={() => callPatient(patient)}
                    disabled={!!currentCall}
                    style={{ fontSize: '13px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    <UserCheck size={16} />
                    Вызвать
                  </MacOSButton>
                </div>
              </div>
            ))}
          </div>
        )}
      </MacOSCard>

      {/* Статистика */}
      <MacOSCard style={{ padding: '24px' }}>
        <h3 style={{
          fontSize: '18px',
          fontWeight: '600',
          marginBottom: '20px',
          color: 'var(--mac-text-primary)',
          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
        }}>Статистика дня</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: '32px',
              fontWeight: '700',
              color: 'var(--mac-blue-500)',
              fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
              marginBottom: '8px'
            }}>{queue.length}</div>
            <div style={{
              fontSize: '13px',
              color: 'var(--mac-text-secondary)',
              fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
            }}>В очереди</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: '32px',
              fontWeight: '700',
              color: 'var(--mac-green-500)',
              fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
              marginBottom: '8px'
            }}>0</div>
            <div style={{
              fontSize: '13px',
              color: 'var(--mac-text-secondary)',
              fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
            }}>Обслужено</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: '32px',
              fontWeight: '700',
              color: 'var(--mac-orange-500)',
              fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
              marginBottom: '8px'
            }}>0</div>
            <div style={{
              fontSize: '13px',
              color: 'var(--mac-text-secondary)',
              fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
            }}>Среднее время</div>
          </div>
        </div>
      </MacOSCard>
    </div>
  );
};

export default QueueIntegration;

