import React, { useState, useEffect, useRef } from 'react';
import { Users, Plus, Phone, UserCheck, Clock, Mic, MicOff, Printer, QrCode } from 'lucide-react';
import { Card, Button, Badge } from './ui/native';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import AnimatedToast from './AnimatedToast';
import { moveQueueEntry } from '../utils/queueApi';

const QueueManager = ({ specialist = 'Терапевт', room = '101', specialistId = null }) => {
  const [queue, setQueue] = useState([]);
  const [currentNumber, setCurrentNumber] = useState(1);
  const [isCallActive, setIsCallActive] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [isOnlineOpen, setIsOnlineOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const [queueId, setQueueId] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    // Подключение к WebSocket для синхронизации очереди
    const connectWebSocket = () => {
      const token = localStorage.getItem('access_token');
      const baseUrl = `ws://localhost:8000/api/v1/ws-auth/ws/queue/optional-auth`;
      const params = new URLSearchParams({
        department: specialist,
        date: new Date().toISOString().split('T')[0]
      });
      if (token) {
        params.append('token', token);
      }
      const wsUrl = `${baseUrl}?${params.toString()}`;
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('QueueManager: Connected to queue WebSocket');
      };

      wsRef.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleQueueUpdate(data);
      };

      wsRef.current.onclose = () => {
        console.log('QueueManager: WebSocket disconnected');
        setTimeout(connectWebSocket, 3000);
      };
    };

    connectWebSocket();

    // Загрузка текущей очереди
    loadQueue();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [specialist]);

  const loadQueue = async () => {
    try {
      // Получаем текущую очередь для специалиста
      const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
      
      // Сначала пытаемся найти очередь по specialistId
      if (specialistId) {
        const statusResponse = await fetch(`/api/v1/queue/status/by-specialist?specialist_id=${specialistId}&day=${today}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
          }
        });

        if (statusResponse.ok) {
          const queueData = await statusResponse.json();
          setQueueId(queueData.queue_id);
          
          const formattedQueue = queueData.entries.map(entry => ({
            id: entry.id,
            number: entry.number,
            patient_name: entry.patient_name,
            phone: entry.phone,
            type: entry.source === 'online' ? 'Онлайн' : 'Регистратура',
            source: entry.source,
            status: entry.status
          }));
          
          setQueue(formattedQueue);
          setCurrentNumber(formattedQueue.length + 1);
          setIsOnlineOpen(queueData.is_active || false);
          return;
        }
      }
      
      // Fallback: старый API
      const response = await fetch(`/api/v1/queue/${specialist}/today`);
      if (response.ok) {
        const data = await response.json();
        setQueue(data.queue || []);
        setCurrentNumber(data.next_number || 1);
        setIsOnlineOpen(data.online_open || false);
      }
    } catch (error) {
      console.error('QueueManager: Error loading queue:', error);
    }
  };

  const handleQueueUpdate = (data) => {
    switch (data.type) {
      case 'queue_updated':
        setQueue(data.queue);
        break;
      case 'patient_added':
        setQueue(prev => [...prev, data.patient]);
        break;
      case 'patient_called':
        setQueue(prev => prev.filter(p => p.id !== data.patient_id));
        break;
      case 'online_status':
        setIsOnlineOpen(data.status);
        break;
    }
  };

  const addPatient = async (patientData) => {
    try {
      const response = await fetch(`/api/v1/queue/${specialist}/add`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({
          ...patientData,
          room: room,
          specialist: specialist,
          number: currentNumber
        })
      });

      if (response.ok) {
        const newPatient = await response.json();
        setQueue(prev => [...prev, newPatient]);
        setCurrentNumber(prev => prev + 1);
        
        // Печать талона
        if (patientData.print_ticket) {
          printTicket(newPatient);
        }
      }
    } catch (error) {
      console.error('QueueManager: Error adding patient:', error);
    }
  };

  const callPatient = async (patient) => {
    try {
      const response = await fetch(`/api/v1/queue/${specialist}/call`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({
          patient_id: patient.id,
          number: patient.number,
          room: room
        })
      });

      if (response.ok) {
        setIsCallActive(true);
        setSelectedPatient(patient);
        
        // Убираем пациента из очереди
        setQueue(prev => prev.filter(p => p.id !== patient.id));
        
        // Автоматически скрываем вызов через 30 секунд
        setTimeout(() => {
          setIsCallActive(false);
          setSelectedPatient(null);
        }, 30000);
      }
    } catch (error) {
      console.error('QueueManager: Error calling patient:', error);
    }
  };

  const toggleOnlineQueue = async () => {
    try {
      const response = await fetch(`/api/v1/queue/${specialist}/online-toggle`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({
          status: !isOnlineOpen
        })
      });

      if (response.ok) {
        setIsOnlineOpen(!isOnlineOpen);
      }
    } catch (error) {
      console.error('QueueManager: Error toggling online queue:', error);
    }
  };

  const printTicket = async (patient) => {
    try {
      const response = await fetch('/api/v1/print/ticket', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({
          number: patient.number,
          patient_name: patient.patient_name,
          specialist: specialist,
          room: room,
          date: new Date().toLocaleDateString('ru-RU'),
          time: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
        })
      });

      if (!response.ok) {
        console.error('QueueManager: Print error');
      }
    } catch (error) {
      console.error('QueueManager: Print error:', error);
    }
  };

  const generateQR = async () => {
    try {
      const response = await fetch(`/api/v1/queue/${specialist}/qr`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `queue-${specialist}-qr.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('QueueManager: Error generating QR:', error);
    }
  };

  const onDragEnd = async (result) => {
    const { source, destination } = result || {};
    if (!destination || destination.index === source.index) return;

    const updated = Array.from(queue);
    const [moved] = updated.splice(source.index, 1);
    updated.splice(destination.index, 0, moved);
    
    // Оптимистично обновляем UI
    setQueue(updated);

    setToast({
      message: `Порядок обновлен: №${moved?.number ?? ''} → позиция ${destination.index + 1}`,
      type: 'success'
    });

    // Сохраняем изменения на backend
    try {
      const result = await moveQueueEntry(moved.id, destination.index + 1);
      
      // Обновляем очередь с данными от сервера для синхронизации
      if (result.success && result.queue_info?.entries) {
        const serverQueue = result.queue_info.entries.map(entry => ({
          id: entry.id,
          number: entry.number,
          patient_name: entry.patient_name,
          phone: entry.phone,
          status: entry.status,
          source: entry.source,
          type: entry.source === 'online' ? 'Онлайн' : 'Регистратура'
        }));
        setQueue(serverQueue);
      }

      setToast({
        message: `Порядок сохранен: №${moved?.number ?? ''} → позиция ${destination.index + 1}`,
        type: 'success'
      });

    } catch (error) {
      console.error('QueueManager: Error updating queue order:', error);
      
      // Откатываем изменения в UI при ошибке
      const reverted = Array.from(updated);
      const [revertMoved] = reverted.splice(destination.index, 1);
      reverted.splice(source.index, 0, revertMoved);
      setQueue(reverted);

      setToast({
        message: 'Ошибка сохранения порядка очереди. Изменения отменены.',
        type: 'error'
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Панель управления */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Users className="w-6 h-6 text-blue-600" />
            <div>
              <h2 className="text-xl font-semibold">Очередь: {specialist}</h2>
              <p className="text-gray-500">Кабинет {room}</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <Button
              variant={isOnlineOpen ? 'danger' : 'success'}
              onClick={toggleOnlineQueue}
            >
              {isOnlineOpen ? 'Закрыть онлайн запись' : 'Открыть онлайн запись'}
            </Button>
            
            <Button variant="outline" onClick={generateQR}>
              <QrCode className="w-4 h-4 mr-2" />
              QR код
            </Button>
          </div>
        </div>

        {/* Статистика */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">{queue.length}</div>
            <div className="text-sm text-gray-500">В очереди</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">{currentNumber - 1}</div>
            <div className="text-sm text-gray-500">Обслужено</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-orange-600">{currentNumber}</div>
            <div className="text-sm text-gray-500">Следующий номер</div>
          </div>
          <div className="text-center">
            <Badge variant={isOnlineOpen ? 'success' : 'danger'}>
              {isOnlineOpen ? 'Онлайн открыт' : 'Онлайн закрыт'}
            </Badge>
          </div>
        </div>

        {/* Быстрое добавление пациента */}
        <PatientForm onAdd={addPatient} nextNumber={currentNumber} />
      </Card>

      {/* Текущий вызов */}
      {isCallActive && selectedPatient && (
        <Card className="p-6 border-2 border-blue-500 bg-blue-50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 bg-blue-500 text-white rounded-full flex items-center justify-center text-2xl font-bold">
                {selectedPatient.number}
              </div>
              <div>
                <div className="text-xl font-semibold">{selectedPatient.patient_name}</div>
                <div className="text-blue-600">Вызван в кабинет {room}</div>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Mic className="w-5 h-5 text-blue-600 animate-pulse" />
              <span className="text-blue-600 font-medium">Объявление</span>
            </div>
          </div>
        </Card>
      )}

      {/* Список очереди */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Очередь ({queue.length})</h3>
        {queue.length === 0 ? (
          <div className="text-center py-8 text-gray-500">Очередь пуста</div>
        ) : (
          <DragDropContext onDragEnd={onDragEnd}>
            <Droppable droppableId="queue-list">
              {(provided) => (
                <div ref={provided.innerRef} {...provided.droppableProps} className="space-y-3">
                  {queue.map((patient, index) => (
                    <Draggable key={String(patient.id)} draggableId={String(patient.id)} index={index}>
                      {(draggableProvided, snapshot) => (
                        <div
                          ref={draggableProvided.innerRef}
                          {...draggableProvided.draggableProps}
                          {...draggableProvided.dragHandleProps}
                          className={`flex items-center justify-between p-4 rounded-lg border ${
                            index === 0 ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                          } ${snapshot.isDragging ? 'ring-2 ring-blue-300' : ''}`}
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
                            <Button size="sm" onClick={() => callPatient(patient)} disabled={isCallActive}>
                              <UserCheck className="w-4 h-4 mr-2" />
                              Вызвать
                            </Button>
                          </div>
                        </div>
                      )}
                    </Draggable>
                  ))}
                  {provided.placeholder}
                </div>
              )}
            </Droppable>
          </DragDropContext>
        )}
      </Card>

      {toast && (
        <AnimatedToast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
          position="bottom-right"
        />
      )}
    </div>
  );
};

// Компонент формы добавления пациента
const PatientForm = ({ onAdd, nextNumber }) => {
  const [formData, setFormData] = useState({
    patient_name: '',
    phone: '',
    type: 'Первичный',
    print_ticket: true
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (formData.patient_name.trim()) {
      onAdd(formData);
      setFormData({
        patient_name: '',
        phone: '',
        type: 'Первичный',
        print_ticket: true
      });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="border-t pt-4">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">ФИО пациента</label>
          <input
            type="text"
            value={formData.patient_name}
            onChange={(e) => setFormData({...formData, patient_name: e.target.value})}
            className="w-full p-2 border border-gray-300 rounded-lg"
            placeholder="Введите ФИО"
            required
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium mb-1">Телефон</label>
          <input
            type="tel"
            value={formData.phone}
            onChange={(e) => setFormData({...formData, phone: e.target.value})}
            className="w-full p-2 border border-gray-300 rounded-lg"
            placeholder="+998 90 123 45 67"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium mb-1">Тип обращения</label>
          <select
            value={formData.type}
            onChange={(e) => setFormData({...formData, type: e.target.value})}
            className="w-full p-2 border border-gray-300 rounded-lg"
          >
            <option value="Первичный">Первичный</option>
            <option value="Повторный">Повторный</option>
            <option value="Льготный">Льготный</option>
          </select>
        </div>
        
        <div className="flex items-end gap-2">
          <Button type="submit" className="flex-1">
            <Plus className="w-4 h-4 mr-2" />
            Добавить (№{nextNumber})
          </Button>
          
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={formData.print_ticket}
              onChange={(e) => setFormData({...formData, print_ticket: e.target.checked})}
            />
            <Printer className="w-4 h-4" />
          </label>
        </div>
      </div>
    </form>
  );
};

export default QueueManager;


