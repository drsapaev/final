import React, { useState, useEffect } from 'react';
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
import { Card, Button, Badge } from '../ui/native';

/**
 * Панель очереди для врача - показывает пациентов из регистратуры
 * Основа: passport.md стр. 1417-1427
 */
const DoctorQueuePanel = ({ 
  specialty = 'cardiology',
  onPatientSelect,
  className = ''
}) => {
  // Проверяем демо-режим в самом начале
  const isDemoMode = window.location.pathname.includes('/medilab-demo') || 
                    window.location.hostname === 'localhost' && 
                    window.location.port === '5173';
  
  // В демо-режиме не рендерим компонент
  if (isDemoMode) {
    console.log('DoctorQueuePanel: Skipping render in demo mode');
    return null;
  }
  
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
    
    console.log('DoctorQueuePanel useEffect:', {
      pathname: window.location.pathname,
      isDemoMode,
      specialty
    });
    
    if (isDemoMode) {
      // В демо-режиме используем моковые данные
      console.log('Setting demo data for DoctorQueuePanel');
      setDoctorInfo({
        id: 1,
        name: 'Dr. Demo',
        specialty: specialty,
        department: 'Demo Department'
      });
      
      setQueueData({
        queue_exists: true,
        entries: [
          {
            id: 1,
            patient_name: 'Иван Иванов',
            ticket_number: 'A001',
            status: 'waiting',
            source: 'online',
            created_at: '2024-01-15T09:00:00Z'
          },
          {
            id: 2,
            patient_name: 'Мария Петрова',
            ticket_number: 'A002',
            status: 'waiting',
            source: 'desk',
            created_at: '2024-01-15T09:15:00Z'
          }
        ]
      });
    } else {
      console.log('Loading real data for DoctorQueuePanel');
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
      console.log('Skipping loadDoctorData in demo mode');
      return;
    }
    
    try {
      const response = await fetch('http://127.0.0.1:8000/api/v1/doctor/my-info', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (response.ok) {
        const data = await response.json();
        setDoctorInfo(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки информации врача:', error);
    }
  };

  const loadQueueData = async () => {
    // Проверяем демо-режим еще раз
    const isDemoMode = window.location.pathname.includes('/medilab-demo') || 
                      window.location.hostname === 'localhost' && 
                      window.location.port === '5173';
    
    if (isDemoMode) {
      console.log('Skipping loadQueueData in demo mode');
      return;
    }
    
    try {
      setLoading(true);
      
      const response = await fetch(`http://127.0.0.1:8000/api/v1/doctor/${specialty}/queue/today`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (response.ok) {
        const data = await response.json();
        setQueueData(data);
      } else {
        const error = await response.json();
        setMessage({ type: 'error', text: error.detail });
      }
    } catch (error) {
      console.error('Ошибка загрузки очереди:', error);
      setMessage({ type: 'error', text: 'Ошибка загрузки очереди' });
    } finally {
      setLoading(false);
    }
  };

  const handleCallPatient = async (entryId) => {
    // Проверяем демо-режим
    const isDemoMode = window.location.pathname.includes('/medilab-demo') || 
                      window.location.hostname === 'localhost' && 
                      window.location.port === '5173';
    
    if (isDemoMode) {
      setMessage({ type: 'success', text: 'Пациент вызван (демо)' });
      return;
    }
    
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/doctor/queue/${entryId}/call`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
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
      console.error('Ошибка вызова пациента:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  const handleStartVisit = async (entryId) => {
    // Проверяем демо-режим
    const isDemoMode = window.location.pathname.includes('/medilab-demo') || 
                      window.location.hostname === 'localhost' && 
                      window.location.port === '5173';
    
    if (isDemoMode) {
      setMessage({ type: 'success', text: 'Прием начат (демо)' });
      return;
    }
    
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/doctor/queue/${entryId}/start-visit`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
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
      console.error('Ошибка начала приема:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  const handleCompleteVisit = async (entryId) => {
    // Проверяем демо-режим
    const isDemoMode = window.location.pathname.includes('/medilab-demo') || 
                      window.location.hostname === 'localhost' && 
                      window.location.port === '5173';
    
    if (isDemoMode) {
      setMessage({ type: 'success', text: 'Прием завершен (демо)' });
      return;
    }
    
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/doctor/queue/${entryId}/complete`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
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
      console.error('Ошибка завершения приема:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  if (loading && !queueData) {
    return (
      <Card className={`p-6 ${className}`}>
        <div className="flex items-center justify-center">
          <RefreshCw className="animate-spin mr-2" size={20} />
          <span>Загрузка очереди...</span>
        </div>
      </Card>
    );
  }

  if (!queueData?.queue_exists) {
    return (
      <Card className={`p-6 text-center ${className}`}>
        <Users size={48} className="mx-auto text-gray-400 mb-4" />
        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
          Очередь не создана
        </h3>
        <p className="text-gray-500">
          Очередь будет создана когда регистратура добавит первого пациента
        </p>
      </Card>
    );
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Сообщения */}
      {message.text && (
        <div className={`flex items-center p-3 rounded-lg ${
          message.type === 'success' 
            ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
            : 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
        }`}>
          {message.type === 'success' ? (
            <CheckCircle size={16} className="mr-2" />
          ) : (
            <AlertCircle size={16} className="mr-2" />
          )}
          {message.text}
        </div>
      )}

      {/* Информация о враче и очереди */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center">
            <User size={24} className="mr-3 text-blue-600" />
            <div>
              <h3 className="text-lg font-medium">{queueData.doctor.name}</h3>
              <div className="flex items-center text-sm text-gray-500 space-x-4">
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
          
          <div className="text-right">
            <div className="text-sm text-gray-500">Статус очереди:</div>
            <Badge variant={queueData.opened_at ? 'success' : 'warning'}>
              {queueData.opened_at ? 'Открыта' : 'Не открыта'}
            </Badge>
          </div>
        </div>

        {/* Статистика очереди */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">{queueData.stats.total}</div>
            <div className="text-sm text-gray-500">Всего</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-orange-600">{queueData.stats.waiting}</div>
            <div className="text-sm text-gray-500">Ожидают</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">{queueData.stats.served}</div>
            <div className="text-sm text-gray-500">Приняты</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600">{queueData.stats.online_entries}</div>
            <div className="text-sm text-gray-500">Онлайн</div>
          </div>
        </div>
      </Card>

      {/* Список пациентов в очереди */}
      <Card className="overflow-hidden">
        <div className="p-4 bg-gray-50 dark:bg-gray-800 border-b">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium">Пациенты в очереди</h3>
            <Button variant="outline" size="sm" onClick={loadQueueData}>
              <RefreshCw size={14} className="mr-1" />
              Обновить
            </Button>
          </div>
        </div>

        <div className="divide-y divide-gray-200 dark:divide-gray-700">
          {queueData.entries.length === 0 ? (
            <div className="p-8 text-center">
              <Users size={48} className="mx-auto text-gray-400 mb-4" />
              <p className="text-gray-500">Пациентов в очереди нет</p>
            </div>
          ) : (
            queueData.entries.map(entry => {
              const status = statusConfig[entry.status] || statusConfig.waiting;
              const source = sourceConfig[entry.source] || sourceConfig.desk;
              const StatusIcon = status.icon;
              
              return (
                <div 
                  key={entry.id} 
                  className={`p-4 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors ${
                    selectedPatient?.id === entry.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                  }`}
                  onClick={() => {
                    setSelectedPatient(entry);
                    if (onPatientSelect) onPatientSelect(entry);
                  }}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      {/* Номер в очереди */}
                      <div className="flex items-center justify-center w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-full">
                        <span className="text-xl font-bold text-blue-600">
                          {entry.number}
                        </span>
                      </div>
                      
                      {/* Информация о пациенте */}
                      <div>
                        <div className="font-medium text-gray-900 dark:text-white">
                          {entry.patient_name}
                        </div>
                        {entry.phone && (
                          <div className="flex items-center text-sm text-gray-500">
                            <Phone size={14} className="mr-1" />
                            {entry.phone}
                          </div>
                        )}
                        <div className="flex items-center space-x-2 mt-1">
                          <Badge variant="outline" size="sm">
                            {source.icon} {source.label}
                          </Badge>
                          <span className="text-xs text-gray-400">
                            {new Date(entry.created_at).toLocaleTimeString('ru-RU', { 
                              hour: '2-digit', 
                              minute: '2-digit' 
                            })}
                          </span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-3">
                      {/* Статус */}
                      <div className="text-center">
                        <Badge variant={status.color}>
                          <StatusIcon size={14} className="mr-1" />
                          {status.label}
                        </Badge>
                        {entry.called_at && (
                          <div className="text-xs text-gray-400 mt-1">
                            Вызван: {new Date(entry.called_at).toLocaleTimeString('ru-RU', { 
                              hour: '2-digit', 
                              minute: '2-digit' 
                            })}
                          </div>
                        )}
                      </div>
                      
                      {/* Действия */}
                      <div className="flex flex-col gap-2">
                        {entry.status === 'waiting' && (
                          <Button 
                            size="sm" 
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCallPatient(entry.id);
                            }}
                          >
                            <Play size={14} className="mr-1" />
                            Вызвать
                          </Button>
                        )}
                        
                        {entry.status === 'called' && (
                          <Button 
                            size="sm"
                            variant="outline"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleStartVisit(entry.id);
                            }}
                          >
                            <Activity size={14} className="mr-1" />
                            Начать
                          </Button>
                        )}
                        
                        {entry.status === 'in_progress' && (
                          <Button 
                            size="sm"
                            variant="success"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCompleteVisit(entry.id);
                            }}
                          >
                            <CheckCircle size={14} className="mr-1" />
                            Завершить
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </Card>

      {/* Информация о настройках очереди */}
      {doctorInfo && (
        <Card className="p-4 bg-blue-50 border-blue-200 dark:bg-blue-900/20">
          <h4 className="font-medium text-blue-800 dark:text-blue-400 mb-2">
            ⚙️ Настройки очереди:
          </h4>
          <div className="text-sm text-blue-700 dark:text-blue-300 space-y-1">
            <div>Стартовый номер онлайн: #{doctorInfo.queue_settings.start_number}</div>
            <div>Лимит в день: {doctorInfo.queue_settings.max_per_day}</div>
            <div>Часовой пояс: {doctorInfo.queue_settings.timezone}</div>
            {doctorInfo.doctor.cabinet && (
              <div>Кабинет: {doctorInfo.doctor.cabinet}</div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
};

export default DoctorQueuePanel;

