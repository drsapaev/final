import React, { useState, useEffect, useRef } from 'react';
import { Monitor, Volume2, VolumeX, Wifi, WifiOff, Users, Clock, AlertCircle } from 'lucide-react';
import { Card, Badge } from '../design-system/components';
import { useTheme } from '../contexts/ThemeContext';

const QueueBoard = () => {
  const { theme } = useTheme();
  const [isConnected, setIsConnected] = useState(false);
  const [queue, setQueue] = useState([]);
  const [currentCall, setCurrentCall] = useState(null);
  const [lastCalls, setLastCalls] = useState([]);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const wsRef = useRef(null);
  const audioRef = useRef(null);

  useEffect(() => {
    // WebSocket подключение к табло очереди
    const connectWebSocket = () => {
      const wsUrl = `ws://localhost:8000/ws/queue-board`;
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('QueueBoard: WebSocket connected');
        setIsConnected(true);
      };

      wsRef.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      };

      wsRef.current.onclose = () => {
        console.log('QueueBoard: WebSocket disconnected');
        setIsConnected(false);
        // Переподключение через 3 секунды
        setTimeout(connectWebSocket, 3000);
      };

      wsRef.current.onerror = (error) => {
        console.error('QueueBoard: WebSocket error:', error);
      };
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const handleWebSocketMessage = (data) => {
    switch (data.type) {
      case 'queue_update':
        setQueue(data.queue || []);
        break;
      case 'call_patient':
        setCurrentCall(data.call);
        setLastCalls(prev => [data.call, ...prev.slice(0, 4)]);
        if (soundEnabled) {
          playCallSound();
        }
        break;
      case 'clear_call':
        setCurrentCall(null);
        break;
      default:
        console.log('QueueBoard: Unknown message type:', data.type);
    }
  };

  const playCallSound = () => {
    if (audioRef.current) {
      audioRef.current.play().catch(e => {
        console.log('QueueBoard: Cannot play sound:', e);
      });
    }
  };

  const getSpecialistColor = (specialist) => {
    const colors = {
      'Кардиолог': 'bg-red-500',
      'Дерматолог': 'bg-green-500',
      'Стоматолог': 'bg-blue-500',
      'Лаборатория': 'bg-purple-500',
      'Педиатр': 'bg-yellow-500',
      'Терапевт': 'bg-gray-500'
    };
    return colors[specialist] || 'bg-gray-400';
  };

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className={`min-h-screen ${theme === 'dark' ? 'bg-gray-900' : 'bg-gray-100'} p-4`}>
      {/* Звуковой файл */}
      <audio ref={audioRef} preload="auto">
        <source src="/sounds/call-beep.mp3" type="audio/mpeg" />
        <source src="/sounds/call-beep.wav" type="audio/wav" />
      </audio>

      <div className="max-w-7xl mx-auto">
        {/* Заголовок */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <Monitor className="w-8 h-8 text-blue-600" />
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Табло очереди</h1>
              <p className="text-gray-600">Клиника - Электронная очередь</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            {/* Статус подключения */}
            <div className="flex items-center gap-2">
              {isConnected ? (
                <><Wifi className="w-5 h-5 text-green-500" />
                <span className="text-green-600">Онлайн</span></>
              ) : (
                <><WifiOff className="w-5 h-5 text-red-500" />
                <span className="text-red-600">Офлайн</span></>
              )}
            </div>
            
            {/* Переключатель звука */}
            <button
              onClick={() => setSoundEnabled(!soundEnabled)}
              className="p-2 rounded-lg border border-gray-300 hover:bg-gray-50"
            >
              {soundEnabled ? (
                <Volume2 className="w-5 h-5 text-blue-600" />
              ) : (
                <VolumeX className="w-5 h-5 text-gray-400" />
              )}
            </button>
            
            {/* Текущее время */}
            <div className="text-right">
              <div className="text-lg font-mono font-bold">
                {new Date().toLocaleTimeString('ru-RU')}
              </div>
              <div className="text-sm text-gray-500">
                {new Date().toLocaleDateString('ru-RU')}
              </div>
            </div>
          </div>
        </div>

        {/* Текущий вызов */}
        {currentCall && (
          <Card className="mb-6 p-6 border-2 border-blue-500 bg-blue-50 animate-pulse">
            <div className="text-center">
              <div className="text-6xl font-bold text-blue-600 mb-2">
                №{currentCall.number}
              </div>
              <div className="text-xl font-semibold text-gray-800 mb-2">
                {currentCall.patient_name}
              </div>
              <div className="flex items-center justify-center gap-4">
                <Badge variant="info" className="text-lg px-4 py-2">
                  {currentCall.specialist}
                </Badge>
                <Badge variant="warning" className="text-lg px-4 py-2">
                  Кабинет {currentCall.room}
                </Badge>
              </div>
            </div>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Живая очередь */}
          <div className="lg:col-span-2">
            <Card className="p-6">
              <div className="flex items-center gap-3 mb-6">
                <Users className="w-6 h-6 text-blue-600" />
                <h2 className="text-xl font-semibold">Очередь на сегодня</h2>
                <Badge variant="info">{queue.length}</Badge>
              </div>
              
              {queue.length === 0 ? (
                <div className="text-center py-12">
                  <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-500">Очередь пуста</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {queue.map((item, index) => (
                    <div
                      key={item.id}
                      className={`flex items-center justify-between p-4 rounded-lg border ${
                        index === 0 ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                      }`}
                    >
                      <div className="flex items-center gap-4">
                        <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold ${
                          index === 0 ? 'bg-blue-500' : 'bg-gray-400'
                        }`}>
                          {item.number}
                        </div>
                        <div>
                          <div className="font-medium text-gray-900">
                            {item.patient_name}
                          </div>
                          <div className="text-sm text-gray-500">
                            {item.type} • {formatTime(item.created_at)}
                          </div>
                        </div>
                      </div>
                      
                      <div className="text-right">
                        <div className={`inline-block w-3 h-3 rounded-full ${getSpecialistColor(item.specialist)}`}></div>
                        <div className="text-sm font-medium mt-1">{item.specialist}</div>
                        <div className="text-xs text-gray-500">Каб. {item.room}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* Последние вызовы */}
          <div>
            <Card className="p-6">
              <div className="flex items-center gap-3 mb-6">
                <Clock className="w-6 h-6 text-green-600" />
                <h2 className="text-xl font-semibold">Последние вызовы</h2>
              </div>
              
              {lastCalls.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-gray-500">Пока нет вызовов</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {lastCalls.map((call, index) => (
                    <div
                      key={`${call.number}-${call.timestamp}`}
                      className="flex items-center justify-between p-3 rounded-lg bg-gray-50"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center text-sm font-bold">
                          {call.number}
                        </div>
                        <div>
                          <div className="text-sm font-medium">{call.patient_name}</div>
                          <div className="text-xs text-gray-500">{call.specialist}</div>
                        </div>
                      </div>
                      <div className="text-xs text-gray-500">
                        {formatTime(call.timestamp)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Статистика дня */}
            <Card className="p-6 mt-6">
              <h3 className="text-lg font-semibold mb-4">Статистика дня</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-600">Всего талонов:</span>
                  <span className="font-semibold">{queue.length + lastCalls.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Обслужено:</span>
                  <span className="font-semibold text-green-600">{lastCalls.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">В очереди:</span>
                  <span className="font-semibold text-blue-600">{queue.length}</span>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default QueueBoard;

