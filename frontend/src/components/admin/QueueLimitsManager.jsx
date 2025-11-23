import React, { useState, useEffect } from 'react';
import { 
  Settings, 
  Users, 
  AlertCircle, 
  CheckCircle, 
  Edit, 
  Save, 
  X, 
  RefreshCw,
  TrendingUp,
  Clock,
  Shield
} from 'lucide-react';
import { toast } from 'react-toastify';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSInput, 
  MacOSTable,
  MacOSLoadingSkeleton
} from '../ui/macos';

/**
 * Компонент управления лимитами очередей
 * Позволяет настраивать максимальное количество записей по специальностям
 */
const QueueLimitsManager = () => {
  const [limits, setLimits] = useState([]);
  const [queueStatus, setQueueStatus] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingSpecialty, setEditingSpecialty] = useState(null);
  const [editValues, setEditValues] = useState({});

  // Загрузка данных
  const loadData = async () => {
    setLoading(true);
    try {
      const [limitsResponse, statusResponse] = await Promise.all([
        fetch('/api/admin/queue-limits', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }),
        fetch('/api/admin/queue-status', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        })
      ]);

      if (limitsResponse.ok) {
        const limitsData = await limitsResponse.json();
        setLimits(limitsData);
      } else {
        // Fallback данные для демонстрации
        setLimits([
          { specialty: 'cardiology', doctors_count: 3, max_per_day: 20, start_number: 1 },
          { specialty: 'dermatology', doctors_count: 2, max_per_day: 15, start_number: 1 },
          { specialty: 'dentistry', doctors_count: 4, max_per_day: 25, start_number: 1 }
        ]);
      }

      if (statusResponse.ok) {
        const statusData = await statusResponse.json();
        setQueueStatus(statusData);
      } else {
        // Fallback данные для демонстрации
        setQueueStatus([
          { doctor_id: 1, doctor_name: 'Доктор Иванов', specialty: 'cardiology', cabinet: '101', current_entries: 8, max_entries: 20, limit_reached: false, queue_opened: true, online_available: true },
          { doctor_id: 2, doctor_name: 'Доктор Петров', specialty: 'dermatology', cabinet: '102', current_entries: 12, max_entries: 15, limit_reached: false, queue_opened: false, online_available: true },
          { doctor_id: 3, doctor_name: 'Доктор Сидоров', specialty: 'dentistry', cabinet: '103', current_entries: 5, max_entries: 25, limit_reached: false, queue_opened: true, online_available: false }
        ]);
      }
    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
      toast.error('Ошибка загрузки данных о лимитах');
      
      // Fallback данные при ошибке
      setLimits([
        { specialty: 'cardiology', doctors_count: 3, max_per_day: 20, start_number: 1 },
        { specialty: 'dermatology', doctors_count: 2, max_per_day: 15, start_number: 1 },
        { specialty: 'dentistry', doctors_count: 4, max_per_day: 25, start_number: 1 }
      ]);
      setQueueStatus([
        { doctor_id: 1, doctor_name: 'Доктор Иванов', specialty: 'cardiology', cabinet: '101', current_entries: 8, max_entries: 20, limit_reached: false, queue_opened: true, online_available: true },
        { doctor_id: 2, doctor_name: 'Доктор Петров', specialty: 'dermatology', cabinet: '102', current_entries: 12, max_entries: 15, limit_reached: false, queue_opened: false, online_available: true },
        { doctor_id: 3, doctor_name: 'Доктор Сидоров', specialty: 'dentistry', cabinet: '103', current_entries: 5, max_entries: 25, limit_reached: false, queue_opened: true, online_available: false }
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Начать редактирование
  const startEditing = (specialty, currentLimits) => {
    setEditingSpecialty(specialty);
    setEditValues({
      max_per_day: currentLimits.max_per_day,
      start_number: currentLimits.start_number
    });
  };

  // Отменить редактирование
  const cancelEditing = () => {
    setEditingSpecialty(null);
    setEditValues({});
  };

  // Сохранить изменения
  const saveChanges = async (specialty) => {
    setSaving(true);
    try {
      const response = await fetch('/api/admin/queue-limits', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify([{
          specialty: specialty,
          max_per_day: parseInt(editValues.max_per_day),
          start_number: parseInt(editValues.start_number)
        }])
      });

      if (response.ok) {
        const result = await response.json();
        toast.success(result.message);
        setEditingSpecialty(null);
        setEditValues({});
        await loadData(); // Перезагружаем данные
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Ошибка сохранения');
      }
    } catch (error) {
      console.error('Ошибка сохранения:', error);
      toast.error('Ошибка сохранения изменений');
    } finally {
      setSaving(false);
    }
  };

  // Сброс лимитов
  const resetLimits = async (specialty = null) => {
    if (!confirm(specialty ? 
      `Сбросить лимиты для специальности "${specialty}"?` : 
      'Сбросить все лимиты к значениям по умолчанию?'
    )) {
      return;
    }

    try {
      const url = specialty ? 
        `/api/admin/reset-queue-limits?specialty=${specialty}` : 
        '/api/admin/reset-queue-limits';
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (response.ok) {
        const result = await response.json();
        toast.success(result.message);
        await loadData();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Ошибка сброса');
      }
    } catch (error) {
      console.error('Ошибка сброса:', error);
      toast.error('Ошибка сброса лимитов');
    }
  };

  // Получить статистику по специальности
  const getSpecialtyStats = (specialty) => {
    return queueStatus.filter(status => status.specialty === specialty);
  };

  if (loading) {
    return (
      <div style={{ 
        padding: 0,
        backgroundColor: 'var(--mac-bg-primary)'
      }}>
        <MacOSCard style={{ padding: 0, textAlign: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px' }}>
            <RefreshCw style={{ 
              width: '32px', 
              height: '32px', 
              color: 'var(--mac-accent-blue)',
              animation: 'spin 1s linear infinite'
            }} />
            <span style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              color: 'var(--mac-text-secondary)',
              fontWeight: 'var(--mac-font-weight-medium)'
            }}>
              Загрузка лимитов...
            </span>
          </div>
        </MacOSCard>
      </div>
    );
  }

  return (
    <div style={{ 
      padding: 0,
      backgroundColor: 'var(--mac-bg-primary)'
    }}>
      <MacOSCard style={{ padding: 0 }}>
        <div style={{ padding: '24px' }}>
        {/* Заголовок */}
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          marginBottom: '24px',
          paddingBottom: '24px',
          borderBottom: '1px solid var(--mac-border)'
        }}>
          <div>
            <h2 style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: '0 0 8px 0',
              display: 'flex',
              alignItems: 'center',
              gap: '12px'
            }}>
              <Shield style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
              Лимиты очередей
            </h2>
            <p style={{ 
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-sm)',
              margin: 0
            }}>
              Управление максимальным количеством онлайн записей по специальностям
            </p>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <MacOSButton
              onClick={() => loadData()}
              variant="outline"
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                padding: '8px 16px'
              }}
            >
              <RefreshCw style={{ width: '16px', height: '16px' }} />
              Обновить
            </MacOSButton>
            <MacOSButton
              onClick={() => resetLimits()}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                padding: '8px 16px',
                backgroundColor: 'var(--mac-danger)',
                border: 'none'
              }}
            >
              Сбросить все
            </MacOSButton>
          </div>
        </div>

        {/* Карточки специальностей */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', 
          gap: '24px',
          marginBottom: '24px'
        }}>
          {limits.map((limit) => {
            const specialtyStats = getSpecialtyStats(limit.specialty);
            const isEditing = editingSpecialty === limit.specialty;
            const totalCurrentEntries = specialtyStats.reduce((sum, stat) => sum + stat.current_entries, 0);
            const totalMaxEntries = specialtyStats.reduce((sum, stat) => sum + stat.max_entries, 0);
            const utilizationPercent = totalMaxEntries > 0 ? (totalCurrentEntries / totalMaxEntries) * 100 : 0;

            return (
              <MacOSCard key={limit.specialty} style={{ padding: '20px' }}>
                {/* Заголовок специальности */}
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'space-between', 
                  marginBottom: '16px' 
                }}>
                  <div>
                    <h3 style={{ 
                      fontSize: 'var(--mac-font-size-lg)', 
                      fontWeight: 'var(--mac-font-weight-semibold)', 
                      color: 'var(--mac-text-primary)',
                      margin: '0 0 4px 0',
                      textTransform: 'capitalize'
                    }}>
                      {limit.specialty}
                    </h3>
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)',
                      margin: 0
                    }}>
                      {limit.doctors_count} врач(ей)
                    </p>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {utilizationPercent > 80 ? (
                      <AlertCircle style={{ width: '20px', height: '20px', color: 'var(--mac-error)' }} />
                    ) : (
                      <CheckCircle style={{ width: '20px', height: '20px', color: 'var(--mac-success)' }} />
                    )}
                  </div>
                </div>

                {/* Статистика использования */}
                <MacOSCard style={{ 
                  padding: '16px', 
                  backgroundColor: 'var(--mac-bg-secondary)', 
                  border: '1px solid var(--mac-border)',
                  marginBottom: '16px'
                }}>
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between', 
                    marginBottom: '8px' 
                  }}>
                    <span style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)' 
                    }}>
                      Использование сегодня
                    </span>
                    <span style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      fontWeight: 'var(--mac-font-weight-medium)',
                      color: 'var(--mac-text-primary)'
                    }}>
                      {totalCurrentEntries} / {totalMaxEntries}
                    </span>
                  </div>
                  <div style={{ 
                    width: '100%', 
                    backgroundColor: 'var(--mac-border)', 
                    borderRadius: 'var(--mac-radius-full)', 
                    height: '8px',
                    overflow: 'hidden'
                  }}>
                    <div 
                      style={{ 
                        height: '100%', 
                        borderRadius: 'var(--mac-radius-full)', 
                        transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                        backgroundColor: utilizationPercent > 80 ? 'var(--mac-error)' : 
                                        utilizationPercent > 60 ? 'var(--mac-warning)' : 'var(--mac-success)',
                        width: `${Math.min(utilizationPercent, 100)}%`
                      }}
                    />
                  </div>
                  <div style={{ 
                    fontSize: 'var(--mac-font-size-xs)', 
                    color: 'var(--mac-text-tertiary)', 
                    marginTop: '4px' 
                  }}>
                    {utilizationPercent.toFixed(1)}% заполнено
                  </div>
                </MacOSCard>

                {/* Настройки лимитов */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '16px' }}>
                  {/* Максимум в день */}
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between' 
                  }}>
                    <label style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      fontWeight: 'var(--mac-font-weight-medium)', 
                      color: 'var(--mac-text-primary)' 
                    }}>
                      Максимум в день:
                    </label>
                    {isEditing ? (
                      <MacOSInput
                        type="number"
                        min="1"
                        max="100"
                        value={editValues.max_per_day}
                        onChange={(e) => setEditValues({
                          ...editValues,
                          max_per_day: e.target.value
                        })}
                        style={{ width: '80px', textAlign: 'center' }}
                      />
                    ) : (
                      <span style={{ 
                        fontSize: 'var(--mac-font-size-sm)', 
                        fontWeight: 'var(--mac-font-weight-semibold)', 
                        color: 'var(--mac-text-primary)' 
                      }}>
                        {limit.max_per_day}
                      </span>
                    )}
                  </div>

                  {/* Начальный номер */}
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between' 
                  }}>
                    <label style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      fontWeight: 'var(--mac-font-weight-medium)', 
                      color: 'var(--mac-text-primary)' 
                    }}>
                      Начальный номер:
                    </label>
                    {isEditing ? (
                      <MacOSInput
                        type="number"
                        min="1"
                        max="999"
                        value={editValues.start_number}
                        onChange={(e) => setEditValues({
                          ...editValues,
                          start_number: e.target.value
                        })}
                        style={{ width: '80px', textAlign: 'center' }}
                      />
                    ) : (
                      <span style={{ 
                        fontSize: 'var(--mac-font-size-sm)', 
                        fontWeight: 'var(--mac-font-weight-semibold)', 
                        color: 'var(--mac-text-primary)' 
                      }}>
                        {limit.start_number}
                      </span>
                    )}
                  </div>
                </div>

                {/* Кнопки действий */}
                <div style={{ 
                  marginTop: '16px', 
                  paddingTop: '16px', 
                  borderTop: '1px solid var(--mac-border)' 
                }}>
                  {isEditing ? (
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <MacOSButton
                        onClick={() => saveChanges(limit.specialty)}
                        disabled={saving}
                        style={{ 
                          flex: 1,
                          display: 'flex', 
                          alignItems: 'center', 
                          justifyContent: 'center', 
                          gap: '8px',
                          backgroundColor: 'var(--mac-success)',
                          border: 'none',
                          padding: '8px 16px'
                        }}
                      >
                        <Save style={{ width: '16px', height: '16px' }} />
                        {saving ? 'Сохранение...' : 'Сохранить'}
                      </MacOSButton>
                      <MacOSButton
                        onClick={cancelEditing}
                        disabled={saving}
                        variant="outline"
                        style={{ 
                          padding: '8px 16px',
                          minWidth: 'auto'
                        }}
                      >
                        <X style={{ width: '16px', height: '16px' }} />
                      </MacOSButton>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <MacOSButton
                        onClick={() => startEditing(limit.specialty, limit)}
                        style={{ 
                          flex: 1,
                          display: 'flex', 
                          alignItems: 'center', 
                          justifyContent: 'center', 
                          gap: '8px',
                          backgroundColor: 'var(--mac-accent-blue)',
                          border: 'none',
                          padding: '8px 16px'
                        }}
                      >
                        <Edit style={{ width: '16px', height: '16px' }} />
                        Изменить
                      </MacOSButton>
                      <MacOSButton
                        onClick={() => resetLimits(limit.specialty)}
                        variant="outline"
                        style={{ 
                          padding: '8px 16px',
                          minWidth: 'auto'
                        }}
                      >
                        Сброс
                      </MacOSButton>
                    </div>
                  )}
                </div>
              </MacOSCard>
            );
          })}
        </div>

        {/* Детальная статистика по врачам */}
        {queueStatus.length > 0 && (
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <TrendingUp style={{ width: '20px', height: '20px', color: 'var(--mac-accent-blue)' }} />
              Статус очередей по врачам
            </h3>
            
            <MacOSTable
              columns={[
                { key: 'doctor', label: 'Врач', width: '25%' },
                { key: 'specialty', label: 'Специальность', width: '20%' },
                { key: 'cabinet', label: 'Кабинет', width: '15%' },
                { key: 'entries', label: 'Записи', width: '20%' },
                { key: 'status', label: 'Статус', width: '20%' }
              ]}
              data={queueStatus.map(status => ({
                doctor: (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ 
                      width: '32px', 
                      height: '32px', 
                      borderRadius: 'var(--mac-radius-full)', 
                      backgroundColor: 'var(--mac-bg-secondary)', 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center' 
                    }}>
                      <Users style={{ width: '16px', height: '16px', color: 'var(--mac-accent-blue)' }} />
                    </div>
                    <div>
                      <div style={{ 
                        fontSize: 'var(--mac-font-size-sm)', 
                        fontWeight: 'var(--mac-font-weight-medium)', 
                        color: 'var(--mac-text-primary)' 
                      }}>
                        {status.doctor_name}
                      </div>
                    </div>
                  </div>
                ),
                specialty: (
                  <span style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-primary)',
                    textTransform: 'capitalize'
                  }}>
                    {status.specialty}
                  </span>
                ),
                cabinet: (
                  <span style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-primary)' 
                  }}>
                    {status.cabinet || 'Не указан'}
                  </span>
                ),
                entries: (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-primary)' 
                    }}>
                      {status.current_entries} / {status.max_entries}
                    </span>
                    {status.limit_reached && (
                      <AlertCircle style={{ width: '16px', height: '16px', color: 'var(--mac-error)' }} />
                    )}
                  </div>
                ),
                status: (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {status.queue_opened ? (
                      <div style={{ 
                        backgroundColor: 'var(--mac-bg-primary)', 
                        color: 'var(--mac-success)',
                        border: '1px solid var(--mac-border)',
                        fontSize: 'var(--mac-font-size-xs)',
                        padding: '4px 8px',
                        borderRadius: 'var(--mac-radius-full)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontWeight: 'var(--mac-font-weight-medium)'
                      }}>
                        <Clock style={{ width: '12px', height: '12px' }} />
                        Прием открыт
                      </div>
                    ) : status.online_available ? (
                      <div style={{ 
                        backgroundColor: 'var(--mac-bg-primary)', 
                        color: 'var(--mac-text-primary)',
                        border: '1px solid var(--mac-border)',
                        fontSize: 'var(--mac-font-size-xs)',
                        padding: '4px 8px',
                        borderRadius: 'var(--mac-radius-full)',
                        fontWeight: 'var(--mac-font-weight-medium)'
                      }}>
                        Онлайн доступен
                      </div>
                    ) : (
                      <div style={{ 
                        backgroundColor: 'var(--mac-bg-primary)', 
                        color: 'var(--mac-danger)',
                        border: '1px solid var(--mac-border)',
                        fontSize: 'var(--mac-font-size-xs)',
                        padding: '4px 8px',
                        borderRadius: 'var(--mac-radius-full)',
                        fontWeight: 'var(--mac-font-weight-medium)'
                      }}>
                        Недоступен
                      </div>
                    )}
                  </div>
                )
              }))}
              emptyState="Нет данных о статусе очередей"
            />
          </MacOSCard>
        )}
        </div>
      </MacOSCard>
    </div>
  );
};

export default QueueLimitsManager;



