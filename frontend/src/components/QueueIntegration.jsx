import React, { useState, useEffect } from 'react';
import { Users, Clock, UserCheck, AlertCircle, CheckCircle } from 'lucide-react';
import { Card, Button, Badge } from './ui/native';
import { APPOINTMENT_STATUS, STATUS_LABELS, STATUS_COLORS } from '../constants/appointmentStatus';

const QueueIntegration = ({ specialist = 'Дерматолог', onPatientSelect }) => {
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
    // Обновляем очередь каждые 30 секунд
    const interval = setInterval(loadQueue, 30000);
    return () => clearInterval(interval);
  }, [specialist]);

  const loadQueue = async () => {
    setLoading(true);
    try {
      // Используем новый API endpoint для получения всех очередей
      const apiUrl = 'http://localhost:8000/api/v1/registrar/queues/today';

      const response = await fetch(apiUrl, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        
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
            }
            return false;
          });
          
          if (specialistQueue && specialistQueue.entries) {
            queueEntries = specialistQueue.entries.map(entry => ({
              id: entry.id,
              patient_name: entry.patient_name,
              number: entry.number,
              status: entry.status,
              created_at: entry.created_at
            }));
          }
        }
        
        setQueue(queueEntries);
      }
    } catch (error) {
      console.error('QueueIntegration: Load queue error:', error);
    } finally {
      setLoading(false);
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
      // Создаем запись на прием
      const appointmentData = {
        patient_id: patient.id,
        patient_name: patient.patient_name,
        specialist: specialist,
        date: new Date().toISOString().split('T')[0],
        time: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
        status: APPOINTMENT_STATUS.PAID, // Предполагаем, что оплата уже прошла
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
        onPatientSelect(appointment);
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
    <div className="space-y-6">
      {/* Текущий вызов */}
      {currentCall && (
        <Card className="p-6 border-2 border-blue-500 bg-blue-50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 bg-blue-500 text-white rounded-full flex items-center justify-center text-2xl font-bold">
                {currentCall.number}
              </div>
              <div>
                <div className="text-xl font-semibold">{currentCall.patient_name}</div>
                <div className="text-blue-600">Вызван в кабинет</div>
              </div>
            </div>
            
            <div className="flex gap-2">
              <Button
                variant="success"
                onClick={() => startVisit(currentCall)}
              >
                <UserCheck className="w-4 h-4 mr-2" />
                Начать прием
              </Button>
              <Button
                variant="outline"
                onClick={() => setCurrentCall(null)}
              >
                Отменить
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Очередь */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Users className="w-6 h-6 text-blue-600" />
            <div>
              <h3 className="text-lg font-semibold">Очередь: {specialist}</h3>
              <p className="text-sm text-gray-600">
                {loading ? 'Загрузка...' : `${queue.length} пациентов в очереди`}
              </p>
            </div>
          </div>
          
          <Button
            size="sm"
            variant="outline"
            onClick={loadQueue}
            disabled={loading}
          >
            <Clock className="w-4 h-4 mr-2" />
            Обновить
          </Button>
        </div>

        {loading ? (
          <div className="text-center py-8">
            <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4"></div>
            <p className="text-gray-500">Загрузка очереди...</p>
          </div>
        ) : queue.length === 0 ? (
          <div className="text-center py-8">
            <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-500">Очередь пуста</p>
          </div>
        ) : (
          <div className="space-y-3">
            {queue.map((patient, index) => (
              <div
                key={patient.id}
                className={`flex items-center justify-between p-4 rounded-lg border ${
                  index === 0 ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                }`}
              >
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold ${
                    index === 0 ? 'bg-blue-500' : 'bg-gray-400'
                  }`}>
                    {patient.number}
                  </div>
                  <div>
                    <div className="font-medium">{patient.patient_name}</div>
                    <div className="text-sm text-gray-500">
                      {patient.type} • {patient.phone}
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  <Badge variant={patient.source === 'online' ? 'success' : 'info'}>
                    {patient.source === 'online' ? 'Онлайн' : 'Регистратура'}
                  </Badge>
                  
                  <Button
                    size="sm"
                    onClick={() => callPatient(patient)}
                    disabled={!!currentCall}
                  >
                    <UserCheck className="w-4 h-4 mr-2" />
                    Вызвать
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Статистика */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Статистика дня</h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">{queue.length}</div>
            <div className="text-sm text-gray-500">В очереди</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">0</div>
            <div className="text-sm text-gray-500">Обслужено</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-orange-600">0</div>
            <div className="text-sm text-gray-500">Среднее время</div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default QueueIntegration;

