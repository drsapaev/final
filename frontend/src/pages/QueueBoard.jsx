import React, { useState, useEffect, useRef } from 'react';
import { 
  Volume2, 
  VolumeX, 
  Settings, 
  Wifi, 
  WifiOff,
  Monitor,
  Clock,
  Users,
  Activity
} from 'lucide-react';

/**
 * Табло очереди с WebSocket подключением
 * Основа: passport.md стр. 2571-3324, detail.md стр. 1567-1789
 */
const QueueBoard = () => {
  const [connected, setConnected] = useState(false);
  const [queueData, setQueueData] = useState([]);
  const [currentCall, setCurrentCall] = useState(null);
  const [announcements, setAnnouncements] = useState([]);
  const [boardSettings, setBoardSettings] = useState({
    theme: 'light',
    showPatientNames: 'initials',
    soundEnabled: true,
    voiceEnabled: false,
    displayCount: 5
  });
  const [lastUpdate, setLastUpdate] = useState(null);

  const wsRef = useRef(null);
  const audioRef = useRef(null);

  // Получаем board_id из URL или используем default
  const boardId = new URLSearchParams(window.location.search).get('board') || 'main_board';

  useEffect(() => {
    connectWebSocket();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [boardId]);

  const connectWebSocket = () => {
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/v1/display/ws/board/${boardId}`;
      
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = () => {
        console.log('WebSocket подключен к табло');
        setConnected(true);
        
        // Отправляем ping каждые 30 секунд
        setInterval(() => {
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          handleWebSocketMessage(message);
        } catch (error) {
          console.error('Ошибка парсинга WebSocket сообщения:', error);
        }
      };
      
      wsRef.current.onclose = () => {
        console.log('WebSocket отключен');
        setConnected(false);
        
        // Переподключение через 5 секунд
        setTimeout(() => {
          connectWebSocket();
        }, 5000);
      };
      
      wsRef.current.onerror = (error) => {
        console.error('Ошибка WebSocket:', error);
        setConnected(false);
      };
      
    } catch (error) {
      console.error('Ошибка подключения WebSocket:', error);
    }
  };

  const handleWebSocketMessage = (message) => {
    console.log('Получено WebSocket сообщение:', message);
    
    switch (message.type) {
      case 'initial_state':
        if (message.data) {
          setQueueData(message.data.queue_entries || []);
          setCurrentCall(message.data.current_call || null);
          setAnnouncements(message.data.announcements || []);
        }
        break;
        
      case 'patient_call':
        setCurrentCall(message.data);
        playCallSound(message);
        
        // Автоматически убираем вызов через указанное время
        setTimeout(() => {
          setCurrentCall(null);
        }, (message.display_duration || 30) * 1000);
        break;
        
      case 'queue_update':
        setQueueData(message.data.queue_entries || []);
        break;
        
      case 'announcement':
        setAnnouncements(prev => [message.data, ...prev.slice(0, 4)]); // Последние 5
        playAnnouncementSound(message);
        
        // Убираем объявление через указанное время
        setTimeout(() => {
          setAnnouncements(prev => prev.filter(a => a.created_at !== message.data.created_at));
        }, (message.display_duration || 60) * 1000);
        break;
        
      case 'pong':
        setLastUpdate(new Date());
        break;
        
      default:
        console.log('Неизвестный тип сообщения:', message.type);
    }
  };

  const playCallSound = (message) => {
    if (!boardSettings.soundEnabled) return;
    
    try {
      // Звуковой сигнал вызова
      const audio = new Audio('/sounds/call-beep.mp3'); // Нужно добавить звук
      audio.volume = 0.7;
      audio.play().catch(console.error);
      
      // Голосовое объявление
      if (boardSettings.voiceEnabled && message.voice_text) {
        setTimeout(() => {
          playVoiceAnnouncement(message.voice_text);
        }, 1000);
      }
      
    } catch (error) {
      console.error('Ошибка воспроизведения звука:', error);
    }
  };

  const playAnnouncementSound = (message) => {
    if (!boardSettings.soundEnabled) return;
    
    try {
      let soundFile = '/sounds/info-beep.mp3';
      
      if (message.data.announcement_type === 'warning') {
        soundFile = '/sounds/warning-beep.mp3';
      } else if (message.data.announcement_type === 'emergency') {
        soundFile = '/sounds/emergency-beep.mp3';
      }
      
      const audio = new Audio(soundFile);
      audio.volume = 0.8;
      audio.play().catch(console.error);
      
      // Голосовое объявление для критических сообщений
      if (boardSettings.voiceEnabled && message.voice_text) {
        setTimeout(() => {
          playVoiceAnnouncement(message.voice_text);
        }, 2000);
      }
      
    } catch (error) {
      console.error('Ошибка воспроизведения звука объявления:', error);
    }
  };

  const playVoiceAnnouncement = (text) => {
    if (!boardSettings.voiceEnabled) return;
    
    try {
      // Используем Web Speech API для синтеза речи
      if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'ru-RU';
        utterance.rate = 0.8;
        utterance.volume = 0.7;
        
        window.speechSynthesis.speak(utterance);
      }
    } catch (error) {
      console.error('Ошибка голосового объявления:', error);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      waiting: '#3b82f6',    // Синий
      called: '#f59e0b',     // Оранжевый  
      in_progress: '#10b981', // Зеленый
      served: '#6b7280'      // Серый
    };
    return colors[status] || '#6b7280';
  };

  const getStatusText = (status) => {
    const texts = {
      waiting: 'Ожидает',
      called: 'Вызван',
      in_progress: 'На приеме',
      served: 'Принят'
    };
    return texts[status] || status;
  };

  const formatTime = (dateString) => {
    if (!dateString) return '';
    return new Date(dateString).toLocaleTimeString('ru-RU', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  // Стили для разных тем
  const themes = {
    light: {
      background: 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)',
      cardBg: '#ffffff',
      textPrimary: '#1a202c',
      textSecondary: '#4a5568',
      border: '#e2e8f0'
    },
    dark: {
      background: 'linear-gradient(135deg, #1a202c 0%, #2d3748 100%)',
      cardBg: '#2d3748',
      textPrimary: '#f7fafc',
      textSecondary: '#a0aec0',
      border: '#4a5568'
    },
    medical: {
      background: 'linear-gradient(135deg, #f0fff4 0%, #dcfce7 100%)',
      cardBg: '#ffffff',
      textPrimary: '#065f46',
      textSecondary: '#047857',
      border: '#a7f3d0'
    }
  };

  const currentTheme = themes[boardSettings.theme] || themes.light;

  const pageStyle = {
    background: currentTheme.background,
    minHeight: '100vh',
    padding: '20px',
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
  };

  const headerStyle = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '30px',
    padding: '20px',
    background: currentTheme.cardBg,
    borderRadius: '12px',
    border: `1px solid ${currentTheme.border}`,
    boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
  };

  const callCardStyle = {
    background: currentCall ? 'linear-gradient(135deg, #dc3545 0%, #e74c3c 100%)' : currentTheme.cardBg,
    color: currentCall ? '#ffffff' : currentTheme.textPrimary,
    padding: '40px',
    borderRadius: '16px',
    textAlign: 'center',
    marginBottom: '30px',
    border: currentCall ? 'none' : `1px solid ${currentTheme.border}`,
    boxShadow: currentCall ? '0 8px 16px rgba(220, 53, 69, 0.3)' : '0 4px 6px rgba(0, 0, 0, 0.1)',
    transform: currentCall ? 'scale(1.02)' : 'scale(1)',
    transition: 'all 0.3s ease',
    animation: currentCall ? 'pulse 2s infinite' : 'none'
  };

  const queueGridStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: '20px',
    marginBottom: '30px'
  };

  return (
    <div style={pageStyle}>
      {/* Заголовок табло */}
      <div style={headerStyle}>
        <div>
          <h1 style={{ 
            fontSize: '2.5rem', 
            fontWeight: 'bold', 
            margin: 0,
            color: currentTheme.textPrimary
          }}>
            📺 Табло очереди
          </h1>
          <p style={{ 
            color: currentTheme.textSecondary, 
            margin: '5px 0 0 0',
            fontSize: '1.1rem'
          }}>
            Медицинский центр
          </p>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          {/* Статус подключения */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {connected ? (
              <>
                <Wifi size={24} style={{ color: '#10b981' }} />
                <span style={{ color: '#10b981', fontWeight: '500' }}>Онлайн</span>
              </>
            ) : (
              <>
                <WifiOff size={24} style={{ color: '#ef4444' }} />
                <span style={{ color: '#ef4444', fontWeight: '500' }}>Офлайн</span>
              </>
            )}
          </div>
          
          {/* Время последнего обновления */}
          {lastUpdate && (
            <div style={{ 
              color: currentTheme.textSecondary,
              fontSize: '0.9rem',
              display: 'flex',
              alignItems: 'center',
              gap: '5px'
            }}>
              <Clock size={16} />
              {lastUpdate.toLocaleTimeString('ru-RU')}
            </div>
          )}
          
          {/* Звук */}
          <button
            onClick={() => setBoardSettings(prev => ({ ...prev, soundEnabled: !prev.soundEnabled }))}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: currentTheme.textSecondary,
              padding: '8px'
            }}
          >
            {boardSettings.soundEnabled ? <Volume2 size={24} /> : <VolumeX size={24} />}
          </button>
        </div>
      </div>

      {/* Текущий вызов */}
      <div style={callCardStyle}>
        {currentCall ? (
          <div>
            <div style={{ fontSize: '1.2rem', marginBottom: '10px', opacity: 0.9 }}>
              ВЫЗЫВАЕТСЯ ПАЦИЕНТ
            </div>
            <div style={{ fontSize: '4rem', fontWeight: 'bold', marginBottom: '20px' }}>
              № {currentCall.queue_number}
            </div>
            <div style={{ fontSize: '1.8rem', marginBottom: '10px' }}>
              {currentCall.patient_name}
            </div>
            <div style={{ fontSize: '1.4rem', opacity: 0.9 }}>
              👨‍⚕️ {currentCall.doctor_name}
            </div>
            {currentCall.cabinet && (
              <div style={{ fontSize: '1.6rem', marginTop: '15px', fontWeight: 'bold' }}>
                🚪 {currentCall.cabinet}
              </div>
            )}
          </div>
        ) : (
          <div>
            <Monitor size={64} style={{ color: currentTheme.textSecondary, marginBottom: '20px' }} />
            <div style={{ fontSize: '1.5rem', color: currentTheme.textSecondary }}>
              Ожидание вызова пациента
            </div>
          </div>
        )}
      </div>

      {/* Объявления */}
      {announcements.length > 0 && (
        <div style={{ marginBottom: '30px' }}>
          {announcements.map((announcement, index) => (
            <div
              key={announcement.created_at}
              style={{
                background: announcement.announcement_type === 'emergency' 
                  ? 'linear-gradient(135deg, #dc3545 0%, #c82333 100%)'
                  : announcement.announcement_type === 'warning'
                  ? 'linear-gradient(135deg, #ffc107 0%, #e0a800 100%)'
                  : 'linear-gradient(135deg, #007bff 0%, #0056b3 100%)',
                color: '#ffffff',
                padding: '20px',
                borderRadius: '12px',
                marginBottom: '10px',
                fontSize: '1.3rem',
                textAlign: 'center',
                animation: 'slideInDown 0.5s ease'
              }}
            >
              📢 {announcement.text}
            </div>
          ))}
        </div>
      )}

      {/* Очередь пациентов */}
      <div style={queueGridStyle}>
        {queueData.slice(0, boardSettings.displayCount).map(entry => (
          <div
            key={entry.number}
            style={{
              background: currentTheme.cardBg,
              border: `2px solid ${getStatusColor(entry.status)}`,
              borderRadius: '12px',
              padding: '20px',
              textAlign: 'center',
              boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
              transition: 'all 0.3s ease'
            }}
          >
            {/* Номер в очереди */}
            <div style={{
              fontSize: '3rem',
              fontWeight: 'bold',
              color: getStatusColor(entry.status),
              marginBottom: '10px'
            }}>
              {entry.number}
            </div>
            
            {/* Имя пациента */}
            {boardSettings.showPatientNames !== 'none' && (
              <div style={{
                fontSize: '1.3rem',
                fontWeight: '500',
                color: currentTheme.textPrimary,
                marginBottom: '8px'
              }}>
                {entry.patient_name}
              </div>
            )}
            
            {/* Статус */}
            <div style={{
              background: getStatusColor(entry.status),
              color: '#ffffff',
              padding: '8px 16px',
              borderRadius: '20px',
              fontSize: '0.9rem',
              fontWeight: '500',
              display: 'inline-block',
              marginBottom: '8px'
            }}>
              {getStatusText(entry.status)}
            </div>
            
            {/* Время */}
            <div style={{
              color: currentTheme.textSecondary,
              fontSize: '0.9rem'
            }}>
              {entry.status === 'called' && entry.called_at ? (
                `Вызван: ${formatTime(entry.called_at)}`
              ) : (
                `Записан: ${formatTime(entry.created_at)}`
              )}
            </div>
            
            {/* Источник записи */}
            <div style={{
              color: currentTheme.textSecondary,
              fontSize: '0.8rem',
              marginTop: '5px'
            }}>
              {entry.source === 'online' ? '📱 Онлайн' : '🏥 Регистратура'}
            </div>
          </div>
        ))}
      </div>

      {/* Статистика очереди */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '20px',
        marginTop: '30px'
      }}>
        <div style={{
          background: currentTheme.cardBg,
          padding: '20px',
          borderRadius: '12px',
          textAlign: 'center',
          border: `1px solid ${currentTheme.border}`
        }}>
          <Users size={32} style={{ color: '#3b82f6', marginBottom: '10px' }} />
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: currentTheme.textPrimary }}>
            {queueData.length}
          </div>
          <div style={{ color: currentTheme.textSecondary }}>Всего в очереди</div>
        </div>
        
        <div style={{
          background: currentTheme.cardBg,
          padding: '20px',
          borderRadius: '12px',
          textAlign: 'center',
          border: `1px solid ${currentTheme.border}`
        }}>
          <Activity size={32} style={{ color: '#10b981', marginBottom: '10px' }} />
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: currentTheme.textPrimary }}>
            {queueData.filter(e => e.status === 'waiting').length}
          </div>
          <div style={{ color: currentTheme.textSecondary }}>Ожидают</div>
        </div>
        
        <div style={{
          background: currentTheme.cardBg,
          padding: '20px',
          borderRadius: '12px',
          textAlign: 'center',
          border: `1px solid ${currentTheme.border}`
        }}>
          <Clock size={32} style={{ color: '#f59e0b', marginBottom: '10px' }} />
          <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: currentTheme.textPrimary }}>
            {new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
          </div>
          <div style={{ color: currentTheme.textSecondary }}>Текущее время</div>
        </div>
      </div>

      {/* CSS анимации */}
      <style jsx>{`
        @keyframes pulse {
          0%, 100% { transform: scale(1.02); }
          50% { transform: scale(1.05); }
        }
        
        @keyframes slideInDown {
          from {
            transform: translateY(-100%);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
        
        .queue-board {
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
      `}</style>
    </div>
  );
};

export default QueueBoard;