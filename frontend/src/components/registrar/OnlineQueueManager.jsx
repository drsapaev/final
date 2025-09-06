import React, { useState, useEffect } from 'react';
import { 
  QrCode, 
  Users, 
  Clock, 
  Play,
  Pause,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Copy,
  Download,
  Eye,
  Hash,
  Calendar
} from 'lucide-react';
import { Card, Button, Badge } from '../../design-system/components';

/**
 * Компонент управления онлайн-очередью для регистратуры
 * Основа: detail.md стр. 224-257
 */
const OnlineQueueManager = ({ 
  selectedDoctorId = null,
  selectedDate = null,
  onQueueUpdate,
  className = ''
}) => {
  const [loading, setLoading] = useState(false);
  const [queueData, setQueueData] = useState(null);
  const [qrToken, setQrToken] = useState('');
  const [queueStatus, setQueueStatus] = useState(null);
  const [todayQueues, setTodayQueues] = useState([]);
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    if (selectedDate) {
      loadQueueStatus();
      loadTodayQueues();
    }
  }, [selectedDoctorId, selectedDate]);

  const loadQueueStatus = async () => {
    if (!selectedDoctorId || !selectedDate) return;

    try {
      const response = await fetch(
        `/api/v1/online-queue/status?day=${selectedDate}&specialist_id=${selectedDoctorId}`,
        {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        }
      );

      if (response.ok) {
        const data = await response.json();
        setQueueStatus(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки статуса очереди:', error);
    }
  };

  const loadTodayQueues = async () => {
    try {
      const response = await fetch('/api/v1/registrar/queues/today', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (response.ok) {
        const data = await response.json();
        setTodayQueues(data.queues);
      }
    } catch (error) {
      console.error('Ошибка загрузки очередей:', error);
    }
  };

  const generateQRCode = async () => {
    if (!selectedDoctorId || !selectedDate) {
      setMessage({ type: 'error', text: 'Выберите врача и дату' });
      return;
    }

    try {
      setLoading(true);
      setMessage({ type: '', text: '' });

      const response = await fetch(
        `/api/v1/registrar/generate-qr?day=${selectedDate}&specialist_id=${selectedDoctorId}`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        }
      );

      if (response.ok) {
        const data = await response.json();
        setQrToken(data.token);
        setQueueData(data);
        setMessage({ type: 'success', text: 'QR код создан успешно' });
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }
    } catch (error) {
      console.error('Ошибка генерации QR:', error);
      setMessage({ type: 'error', text: error.message });
    } finally {
      setLoading(false);
    }
  };

  const openReception = async () => {
    if (!selectedDoctorId || !selectedDate) return;

    try {
      setLoading(true);

      const response = await fetch(
        `/api/v1/registrar/open-reception?day=${selectedDate}&specialist_id=${selectedDoctorId}`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        }
      );

      if (response.ok) {
        const data = await response.json();
        setMessage({ type: 'success', text: data.message });
        await loadQueueStatus();
        await loadTodayQueues();
        if (onQueueUpdate) onQueueUpdate();
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }
    } catch (error) {
      console.error('Ошибка открытия приема:', error);
      setMessage({ type: 'error', text: error.message });
    } finally {
      setLoading(false);
    }
  };

  const copyQRUrl = () => {
    if (queueData?.qr_url) {
      const fullUrl = `${window.location.origin}${queueData.qr_url}`;
      navigator.clipboard.writeText(fullUrl);
      setMessage({ type: 'success', text: 'Ссылка скопирована' });
    }
  };

  const downloadQRCode = () => {
    if (queueData?.qr_data) {
      // Здесь будет генерация QR кода как изображения
      setMessage({ type: 'info', text: 'Функция в разработке' });
    }
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Сообщения */}
      {message.text && (
        <div className={`flex items-center p-3 rounded-lg ${
          message.type === 'success' 
            ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
            : message.type === 'error'
            ? 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
            : 'bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400'
        }`}>
          {message.type === 'success' ? (
            <CheckCircle size={16} className="mr-2" />
          ) : (
            <AlertCircle size={16} className="mr-2" />
          )}
          {message.text}
        </div>
      )}

      {/* Управление QR */}
      <Card className="p-4">
        <h3 className="text-lg font-medium mb-4 flex items-center">
          <QrCode size={20} className="mr-2 text-blue-600" />
          Онлайн-очередь
        </h3>
        
        <div className="space-y-4">
          {/* Статус очереди */}
          {queueStatus && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className={`text-2xl font-bold ${
                  queueStatus.queue_open ? 'text-red-600' : 'text-green-600'
                }`}>
                  {queueStatus.queue_open ? 'ЗАКРЫТА' : 'ОТКРЫТА'}
                </div>
                <div className="text-sm text-gray-500">Онлайн-запись</div>
              </div>
              
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {queueStatus.current_time?.split('T')[1]?.split('.')[0] || '--:--'}
                </div>
                <div className="text-sm text-gray-500">Текущее время</div>
              </div>
              
              <div className="text-center">
                <div className="text-2xl font-bold text-orange-600">
                  {queueStatus.queue_start_time || '07:00'}
                </div>
                <div className="text-sm text-gray-500">Начало записи</div>
              </div>
              
              <div className="text-center">
                <div className={`text-2xl font-bold ${
                  queueStatus.has_slots ? 'text-green-600' : 'text-red-600'
                }`}>
                  {queueStatus.has_slots ? 'ЕСТЬ' : 'НЕТ'}
                </div>
                <div className="text-sm text-gray-500">Свободные места</div>
              </div>
            </div>
          )}

          {/* Действия */}
          <div className="flex gap-3 flex-wrap">
            <Button
              onClick={generateQRCode}
              disabled={loading || !selectedDoctorId || !selectedDate}
              className="flex-1 min-w-0"
            >
              {loading ? (
                <RefreshCw size={16} className="animate-spin mr-2" />
              ) : (
                <QrCode size={16} className="mr-2" />
              )}
              Сгенерировать QR
            </Button>
            
            <Button
              onClick={openReception}
              disabled={loading || !selectedDoctorId || !selectedDate || queueStatus?.queue_open}
              variant="outline"
              className="flex-1 min-w-0"
            >
              <Play size={16} className="mr-2" />
              Открыть прием
            </Button>
          </div>

          {/* QR код информация */}
          {queueData && (
            <Card className="p-4 bg-green-50 border-green-200 dark:bg-green-900/20">
              <h4 className="font-medium text-green-800 dark:text-green-400 mb-3">
                QR код создан:
              </h4>
              <div className="space-y-2 text-sm">
                <div><strong>Врач:</strong> {queueData.specialist}</div>
                <div><strong>Кабинет:</strong> {queueData.cabinet}</div>
                <div><strong>Дата:</strong> {queueData.day}</div>
                <div><strong>Записей:</strong> {queueData.current_count}/{queueData.max_slots}</div>
                <div><strong>URL:</strong> 
                  <code className="ml-2 px-2 py-1 bg-green-100 rounded dark:bg-green-800">
                    {queueData.qr_url}
                  </code>
                </div>
              </div>
              
              <div className="flex gap-2 mt-3">
                <Button size="sm" onClick={copyQRUrl}>
                  <Copy size={14} className="mr-1" />
                  Копировать
                </Button>
                <Button size="sm" variant="outline" onClick={downloadQRCode}>
                  <Download size={14} className="mr-1" />
                  Скачать
                </Button>
                <Button 
                  size="sm" 
                  variant="outline"
                  onClick={() => window.open(`${window.location.origin}${queueData.qr_url}`, '_blank')}
                >
                  <Eye size={14} className="mr-1" />
                  Открыть
                </Button>
              </div>
            </Card>
          )}
        </div>
      </Card>

      {/* Текущие очереди */}
      {todayQueues.length > 0 && (
        <Card className="p-4">
          <h3 className="text-lg font-medium mb-4 flex items-center">
            <Users size={20} className="mr-2 text-green-600" />
            Очереди сегодня
          </h3>
          
          <div className="space-y-3">
            {todayQueues.map(queue => (
              <div key={queue.queue_id} className="border border-gray-200 rounded-lg p-3 dark:border-gray-700">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center">
                    <div className="font-medium">{queue.specialist_name}</div>
                    <Badge variant="outline" className="ml-2">{queue.cabinet}</Badge>
                    <Badge 
                      variant={queue.opened_at ? 'success' : 'warning'} 
                      className="ml-2"
                    >
                      {queue.opened_at ? 'Открыта' : 'Не открыта'}
                    </Badge>
                  </div>
                  
                  <div className="text-sm text-gray-500">
                    {queue.stats.total} записей
                  </div>
                </div>
                
                <div className="grid grid-cols-4 gap-2 text-sm">
                  <div className="text-center">
                    <div className="text-blue-600 font-bold">{queue.stats.waiting}</div>
                    <div className="text-gray-500">Ожидают</div>
                  </div>
                  <div className="text-center">
                    <div className="text-orange-600 font-bold">{queue.stats.called}</div>
                    <div className="text-gray-500">Вызваны</div>
                  </div>
                  <div className="text-center">
                    <div className="text-green-600 font-bold">{queue.stats.served}</div>
                    <div className="text-gray-500">Приняты</div>
                  </div>
                  <div className="text-center">
                    <div className="text-purple-600 font-bold">{queue.stats.online_entries}</div>
                    <div className="text-gray-500">Онлайн</div>
                  </div>
                </div>
                
                {/* Номера в очереди */}
                {queue.entries.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                    <div className="text-sm font-medium mb-2">Номера в очереди:</div>
                    <div className="flex flex-wrap gap-2">
                      {queue.entries.slice(0, 10).map(entry => (
                        <Badge 
                          key={entry.id}
                          variant={
                            entry.status === 'waiting' ? 'info' :
                            entry.status === 'called' ? 'warning' :
                            entry.status === 'served' ? 'success' : 'secondary'
                          }
                          className="text-sm"
                        >
                          #{entry.number}
                          {entry.source === 'online' && ' 📱'}
                        </Badge>
                      ))}
                      {queue.entries.length > 10 && (
                        <Badge variant="outline">+{queue.entries.length - 10}</Badge>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Инструкция по использованию */}
      <Card className="p-4 bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-700">
        <h4 className="font-medium text-blue-800 dark:text-blue-400 mb-2">
          💡 Как работает онлайн-очередь:
        </h4>
        <div className="text-sm text-blue-700 dark:text-blue-300 space-y-1">
          <p>1. Сгенерируйте QR код для врача на нужную дату</p>
          <p>2. Пациенты сканируют QR с 07:00 до открытия приема</p>
          <p>3. Каждый телефон получает уникальный номер</p>
          <p>4. Нажмите "Открыть прием" чтобы закрыть онлайн-набор</p>
          <p>5. Онлайн-записи автоматически попадают в очередь</p>
        </div>
      </Card>
    </div>
  );
};

export default OnlineQueueManager;
