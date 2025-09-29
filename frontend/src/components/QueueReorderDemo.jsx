import React, { useState, useEffect } from 'react';
import { Card, Button, Badge } from './ui/native';
import { Users, RefreshCw, AlertCircle, CheckCircle, ArrowUpDown } from 'lucide-react';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import { getQueueStatusBySpecialist, moveQueueEntry, reorderQueue } from '../utils/queueApi';

const QueueReorderDemo = () => {
  const [queue, setQueue] = useState([]);
  const [queueId, setQueueId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [specialistId, setSpecialistId] = useState(1); // Тестовый ID

  const showMessage = (text, type = 'info') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };

  const loadTestQueue = async () => {
    setLoading(true);
    try {
      const queueData = await getQueueStatusBySpecialist(specialistId);
      setQueueId(queueData.queue_id);
      
      const formattedQueue = queueData.entries.map(entry => ({
        id: entry.id,
        number: entry.number,
        patient_name: entry.patient_name || `Пациент ${entry.id}`,
        phone: entry.phone || '+998901234567',
        status: entry.status,
        source: entry.source
      }));
      
      setQueue(formattedQueue);
      showMessage('Очередь загружена успешно', 'success');
    } catch (error) {
      console.error('Error loading queue:', error);
      showMessage('Ошибка загрузки очереди', 'error');
      
      // Создаем тестовую очередь
      const testQueue = [
        { id: 1, number: 1, patient_name: 'Иванов И.И.', phone: '+998901234567', status: 'waiting', source: 'desk' },
        { id: 2, number: 2, patient_name: 'Петров П.П.', phone: '+998907654321', status: 'waiting', source: 'online' },
        { id: 3, number: 3, patient_name: 'Сидоров С.С.', phone: '+998905555555', status: 'waiting', source: 'desk' },
        { id: 4, number: 4, patient_name: 'Козлов К.К.', phone: '+998903333333', status: 'waiting', source: 'online' }
      ];
      setQueue(testQueue);
      setQueueId(999); // Тестовый ID
    } finally {
      setLoading(false);
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
    showMessage(`Перемещение: №${moved.number} → позиция ${destination.index + 1}`, 'info');

    try {
      const result = await moveQueueEntry(moved.id, destination.index + 1);
      
      if (result.success && result.queue_info?.entries) {
        const serverQueue = result.queue_info.entries.map(entry => ({
          id: entry.id,
          number: entry.number,
          patient_name: entry.patient_name || `Пациент ${entry.id}`,
          phone: entry.phone || '+998901234567',
          status: entry.status,
          source: entry.source
        }));
        setQueue(serverQueue);
        showMessage(`Порядок сохранен: №${moved.number} → позиция ${destination.index + 1}`, 'success');
      }
    } catch (error) {
      console.error('Error moving queue entry:', error);
      
      // Откатываем изменения
      const reverted = Array.from(updated);
      const [revertMoved] = reverted.splice(destination.index, 1);
      reverted.splice(source.index, 0, revertMoved);
      setQueue(reverted);
      
      showMessage('Ошибка сохранения. Изменения отменены.', 'error');
    }
  };

  const testBulkReorder = async () => {
    if (!queueId || queue.length < 2) {
      showMessage('Недостаточно записей для тестирования', 'error');
      return;
    }

    setLoading(true);
    try {
      // Меняем местами первые две записи
      const entryOrders = [
        { entry_id: queue[0].id, new_position: 2 },
        { entry_id: queue[1].id, new_position: 1 }
      ];

      const result = await reorderQueue(queueId, entryOrders);
      
      if (result.success && result.queue_info?.entries) {
        const serverQueue = result.queue_info.entries.map(entry => ({
          id: entry.id,
          number: entry.number,
          patient_name: entry.patient_name || `Пациент ${entry.id}`,
          phone: entry.phone || '+998901234567',
          status: entry.status,
          source: entry.source
        }));
        setQueue(serverQueue);
        showMessage('Массовое изменение порядка выполнено', 'success');
      }
    } catch (error) {
      console.error('Error bulk reordering:', error);
      showMessage('Ошибка массового изменения порядка', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTestQueue();
  }, []);

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Users className="w-6 h-6 text-blue-600" />
            <div>
              <h2 className="text-xl font-semibold">Демо: Изменение порядка очереди</h2>
              <p className="text-gray-500">Тестирование drag & drop функциональности</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <Button
              onClick={loadTestQueue}
              disabled={loading}
              variant="outline"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Обновить
            </Button>
            
            <Button
              onClick={testBulkReorder}
              disabled={loading || queue.length < 2}
            >
              <ArrowUpDown className="w-4 h-4 mr-2" />
              Тест массового изменения
            </Button>
          </div>
        </div>

        {/* Сообщения */}
        {message && (
          <div className={`mb-4 p-3 rounded-lg flex items-center gap-2 ${
            message.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' :
            message.type === 'error' ? 'bg-red-50 text-red-700 border border-red-200' :
            'bg-blue-50 text-blue-700 border border-blue-200'
          }`}>
            {message.type === 'success' ? <CheckCircle className="w-4 h-4" /> :
             message.type === 'error' ? <AlertCircle className="w-4 h-4" /> :
             <AlertCircle className="w-4 h-4" />}
            {message.text}
          </div>
        )}

        {/* Информация */}
        <div className="mb-4 p-3 bg-gray-50 rounded-lg">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="font-medium">Специалист ID:</span> {specialistId}
            </div>
            <div>
              <span className="font-medium">Очередь ID:</span> {queueId || 'N/A'}
            </div>
            <div>
              <span className="font-medium">Записей:</span> {queue.length}
            </div>
            <div>
              <span className="font-medium">Статус:</span> {loading ? 'Загрузка...' : 'Готово'}
            </div>
          </div>
        </div>

        {/* Инструкции */}
        <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
          <h4 className="font-medium text-blue-800 mb-2">Инструкции:</h4>
          <ul className="text-sm text-blue-700 space-y-1">
            <li>• Перетащите записи мышью для изменения порядка</li>
            <li>• Изменения автоматически сохраняются на сервере</li>
            <li>• При ошибке изменения откатываются</li>
            <li>• Используйте кнопку "Тест массового изменения" для проверки bulk API</li>
          </ul>
        </div>
      </Card>

      {/* Список очереди */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Очередь ({queue.length})</h3>
        
        {queue.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            {loading ? 'Загрузка очереди...' : 'Очередь пуста'}
          </div>
        ) : (
          <DragDropContext onDragEnd={onDragEnd}>
            <Droppable droppableId="demo-queue-list">
              {(provided) => (
                <div ref={provided.innerRef} {...provided.droppableProps} className="space-y-3">
                  {queue.map((patient, index) => (
                    <Draggable key={String(patient.id)} draggableId={String(patient.id)} index={index}>
                      {(draggableProvided, snapshot) => (
                        <div
                          ref={draggableProvided.innerRef}
                          {...draggableProvided.draggableProps}
                          {...draggableProvided.dragHandleProps}
                          className={`flex items-center justify-between p-4 rounded-lg border transition-all ${
                            index === 0 ? 'border-blue-500 bg-blue-50' : 'border-gray-200 bg-white'
                          } ${snapshot.isDragging ? 'ring-2 ring-blue-300 shadow-lg' : 'hover:shadow-md'}`}
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
                                {patient.phone} • ID: {patient.id}
                              </div>
                            </div>
                          </div>
                          
                          <div className="flex items-center gap-2">
                            <Badge variant={patient.source === 'online' ? 'success' : 'info'}>
                              {patient.source === 'online' ? 'Онлайн' : 'Регистратура'}
                            </Badge>
                            <Badge variant="outline">
                              {patient.status}
                            </Badge>
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
    </div>
  );
};

export default QueueReorderDemo;


