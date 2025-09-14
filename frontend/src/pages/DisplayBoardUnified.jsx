import React, { useState, useEffect, useRef, useMemo } from 'react';
import { 
  Volume2, 
  VolumeX, 
  Settings, 
  Wifi, 
  WifiOff,
  Monitor,
  Clock,
  Users,
  Activity,
  Maximize2,
  Minimize2,
  Globe,
  Eye,
  EyeOff
} from 'lucide-react';
import { api } from '../api/client';
import { openQueueWS, openDisplayBoardWS } from '../api/ws';
import { useTheme } from '../contexts/ThemeContext';

/**
 * Объединенное табло очереди с полным функционалом
 * Объединяет функции из DisplayBoard.jsx и QueueBoard.jsx
 * 
 * Поддерживает:
 * - WebSocket подключение (новое)
 * - Многоязычность ru/uz/en (старое)
 * - Полноэкранный режим (старое)
 * - Киоск режим (старое)
 * - Контрастный режим (старое)
 * - Масштабирование шрифта (старое)
 * - Окна/кабинеты (старое)
 * - Кэширование (старое)
 * - Звуковые уведомления (новое)
 * - Голосовые объявления (новое)
 * - Темы оформления (новое)
 */
export default function DisplayBoardUnified({
  department = 'Reg',
  dateStr = todayStr(),
  refreshMs = 15000,
  announcement = '',
  lang = 'ru',
  kiosk = false,
  soundInitial = undefined,
  contrast = false,
  fontScale = 1,
  boardId = 'main_board'
}) {
  const { isDark, isLight, getColor, getSpacing, getFontSize } = useTheme();
  
  // Параметры из URL или пропсов
  const qs = useMemo(
    () => ({ department: String(department).trim(), d: String(dateStr).trim() }),
    [department, dateStr]
  );

  // Состояние очереди (новое)
  const [connected, setConnected] = useState(false);
  const [queueData, setQueueData] = useState([]);
  const [currentCall, setCurrentCall] = useState(null);
  const [announcements, setAnnouncements] = useState([]);

  // Состояние статистики (старое)
  const [stats, setStats] = useState({ last_ticket: 0, waiting: 0, serving: 0, done: 0 });
  const [err, setErr] = useState('');
  const [nowStr, setNowStr] = useState(timeNow());
  const [lastUpdatedAt, setLastUpdatedAt] = useState('');

  // Состояние табло (старое)
  const [board, setBoard] = useState({
    brand: 'Clinic',
    logo: '',
    is_paused: false,
    is_closed: false,
    announcement: '',
    announcement_ru: '',
    announcement_uz: '',
    announcement_en: '',
    primary_color: '',
    bg_color: '',
    text_color: '',
    contrast_default: false,
    kiosk_default: false,
    sound_default: true,
  });

  // Окна/кабинеты (старое)
  const [windows, setWindows] = useState([]);
  
  // Настройки (объединенные)
  const [boardSettings, setBoardSettings] = useState({
    theme: 'light',
    showPatientNames: 'initials',
    soundEnabled: true,
    voiceEnabled: false,
    displayCount: 5,
    contrastMode: contrast,
    kioskMode: kiosk,
    fontScale: fontScale,
    language: lang
  });

  // Рефы
  const wsRef = useRef(null);
  const audioRef = useRef(null);
  const lastTicketRef = useRef(0);
  const [online, setOnline] = useState(true);

  // Получаем board_id из URL или используем переданный
  const currentBoardId = new URLSearchParams(window.location.search).get('board') || boardId;

  // Загрузка статистики (старое)
  async function loadStats() {
    setErr('');
    try {
      const s = await api.get('/queues/stats', { query: qs });
      setStats(s || { last_ticket: 0, waiting: 0, serving: 0, done: 0 });
      setLastUpdatedAt(timeNow());
      try {
        localStorage.setItem(`board.stats.${qs.department}`, JSON.stringify(s || {}));
      } catch (_) {}
    } catch (e) {
      setErr(e?.message || 'Ошибка загрузки');
      // fallback из кэша
      try {
        const raw = localStorage.getItem(`board.stats.${qs.department}`);
        if (raw) {
          const cached = JSON.parse(raw);
          if (cached && typeof cached === 'object') setStats({ ...stats, ...cached });
        }
      } catch (_) {}
    }
  }

  // Загрузка состояния табло (старое)
  async function loadBoardState() {
    try {
      const st = await api.get('/board/state');
      if (st && typeof st === 'object') {
        setBoard({
          brand: st.brand || st.title || 'Clinic',
          logo: st.logo || st.logo_url || '',
          is_paused: !!(st.is_paused || st.paused),
          is_closed: !!(st.is_closed || st.closed),
          announcement: st.announcement || st.ticker || '',
          announcement_ru: st.announcement_ru || '',
          announcement_uz: st.announcement_uz || '',
          announcement_en: st.announcement_en || '',
          primary_color: st.primary_color || '',
          bg_color: st.bg_color || '',
          text_color: st.text_color || '',
          contrast_default: !!(st.contrast_default),
          kiosk_default: !!(st.kiosk_default),
          sound_default: st.sound_default !== false,
        });
        if (soundInitial === undefined && typeof st.sound_default !== 'undefined') {
          setBoardSettings(prev => ({ ...prev, soundEnabled: st.sound_default !== false }));
        }
        try { localStorage.setItem('board.state', JSON.stringify(st)); } catch(_){}
      }
    } catch (_) {
      // fallback из кэша
      try {
        const raw = localStorage.getItem('board.state');
        if (raw) {
          const cached = JSON.parse(raw);
          if (cached && typeof cached === 'object') {
            setBoard({
              brand: cached.brand || cached.title || 'Clinic',
              logo: cached.logo || cached.logo_url || '',
              is_paused: !!(cached.is_paused || cached.paused),
              is_closed: !!(cached.is_closed || cached.closed),
              announcement: cached.announcement || cached.ticker || '',
              announcement_ru: cached.announcement_ru || '',
              announcement_uz: cached.announcement_uz || '',
              announcement_en: cached.announcement_en || '',
              primary_color: cached.primary_color || '',
              bg_color: cached.bg_color || '',
              text_color: cached.text_color || '',
              contrast_default: !!(cached.contrast_default),
              kiosk_default: !!(cached.kiosk_default),
              sound_default: cached.sound_default !== false,
            });
          }
        }
      } catch (_) {}
    }
  }

  // Загрузка окон/кабинетов (старое)
  async function loadWindows() {
    try {
      const st = await api.get('/queue/queue/status');
      let arr = [];
      if (Array.isArray(st?.windows)) arr = st.windows;
      else if (Array.isArray(st)) arr = st;
      else if (st && typeof st === 'object' && Array.isArray(st.items)) arr = st.items;
      const norm = arr.map((x) => ({
        window: x.window || x.win || x.cabinet || x.room || '',
        ticket: x.ticket || x.number || x.last_ticket || 0,
        label: x.label || '',
      })).filter((x) => x.window);
      setWindows(norm);
    } catch (_) {
      setWindows([]);
    }
  }

  // WebSocket подключение (новое)
  const connectWebSocket = () => {
    try {
      // Закрываем предыдущее соединение если есть
      if (wsRef.current) {
        wsRef.current();
        wsRef.current = null;
      }
      
      // Создаем новое соединение
      const closeWS = openDisplayBoardWS(
        currentBoardId,
        handleWebSocketMessage,
        () => setConnected(true),
        () => setConnected(false)
      );
      
      wsRef.current = closeWS;
      
    } catch (error) {
      console.error('Ошибка создания WebSocket:', error);
      setConnected(false);
    }
  };

  // Обработка WebSocket сообщений (новое)
  const handleWebSocketMessage = (message) => {
    console.log('Получено WebSocket сообщение:', message);
    
    switch (message.type) {
      case 'initial_state':
        setQueueData(message.data.queue_entries || []);
        setCurrentCall(message.data.current_call || null);
        setAnnouncements(message.data.announcements || []);
        break;
        
      case 'patient_call':
        setCurrentCall(message.data);
        if (boardSettings.soundEnabled) {
          playCallSound(message);
        }
        break;
        
      case 'call_completed':
        setCurrentCall(null);
        break;
        
      case 'queue_update':
        // Обновляем очередь при добавлении/изменении записей
        if (message.event_type === 'queue.created') {
          // Добавляем новую запись в очередь
          setQueueData(prev => [...prev, message.data]);
          console.log(`➕ Новая запись в очереди: №${message.data.number}`);
        } else {
          // Обновляем всю очередь
          setQueueData(message.data.queue_entries || []);
        }
        break;
        
      case 'announcement':
        setAnnouncements(prev => [message.data, ...prev.slice(0, 4)]);
        if (boardSettings.soundEnabled) {
          playAnnouncementSound(message);
        }
        break;
        
      case 'announcement_removed':
        setAnnouncements(prev => prev.filter(a => a.created_at !== message.data.created_at));
        break;
        
      default:
        console.log('Неизвестный тип сообщения:', message.type);
    }
  };

  // Звуковые эффекты (новое)
  const playCallSound = (message) => {
    if (!boardSettings.soundEnabled) return;
    
    try {
      // Создаем звуковой сигнал с помощью Web Audio API
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      
      // Настройки звука вызова (приятный двойной сигнал)
      oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
      oscillator.frequency.setValueAtTime(1000, audioContext.currentTime + 0.1);
      oscillator.frequency.setValueAtTime(800, audioContext.currentTime + 0.2);
      
      gainNode.gain.setValueAtTime(0, audioContext.currentTime);
      gainNode.gain.linearRampToValueAtTime(0.3, audioContext.currentTime + 0.05);
      gainNode.gain.linearRampToValueAtTime(0, audioContext.currentTime + 0.15);
      gainNode.gain.linearRampToValueAtTime(0.3, audioContext.currentTime + 0.2);
      gainNode.gain.linearRampToValueAtTime(0, audioContext.currentTime + 0.4);
      
      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.4);
      
      console.log(`🔊 Звуковой сигнал для пациента №${message.data.number}`);
      
      // Голосовое объявление
      if (boardSettings.voiceEnabled) {
        const text = `Пациент номер ${message.data.number}, ${message.data.patient_name}, пройдите к врачу ${message.data.doctor_name}`;
        playVoiceAnnouncement(text);
      }
    } catch (error) {
      console.error('Ошибка воспроизведения звука:', error);
    }
  };

  const playAnnouncementSound = (message) => {
    if (!boardSettings.soundEnabled) return;
    
    try {
      let soundFile = '/sounds/announcement.mp3';
      
      if (message.data.announcement_type === 'warning') {
        soundFile = '/sounds/warning-beep.mp3';
      } else if (message.data.announcement_type === 'emergency') {
        soundFile = '/sounds/emergency-beep.mp3';
      }
      
      const audio = new Audio(soundFile);
      audio.volume = 0.8;
      audio.play().catch(console.error);
      
      // Голосовое объявление
      if (boardSettings.voiceEnabled && message.voice_text) {
        playVoiceAnnouncement(message.voice_text);
      }
    } catch (error) {
      console.error('Ошибка воспроизведения звука объявления:', error);
    }
  };

  const playVoiceAnnouncement = (text) => {
    if (!boardSettings.voiceEnabled || !('speechSynthesis' in window)) return;
    
    try {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'ru-RU';
      utterance.rate = 0.9;
      utterance.pitch = 1.0;
      utterance.volume = 0.8;
      
      speechSynthesis.speak(utterance);
    } catch (error) {
      console.error('Ошибка голосового объявления:', error);
    }
  };

  // Звук при смене номера (старое)
  useEffect(() => {
    const prev = Number(lastTicketRef.current || 0);
    const cur = Number(stats.last_ticket || 0);
    if (cur && cur !== prev && boardSettings.soundEnabled) playBeep();
    lastTicketRef.current = cur;
  }, [stats.last_ticket, boardSettings.soundEnabled]);

  // Инициализация
  useEffect(() => {
    loadStats();
    loadBoardState();
    loadWindows();
    connectWebSocket();
    
    const t = setInterval(loadStats, Math.max(5000, Number(refreshMs || 0)));
    const tb = setInterval(loadBoardState, Math.max(15000, Number(refreshMs || 0)));
    const tw = setInterval(loadWindows, Math.max(5000, Number(refreshMs || 0)));
    const clock = setInterval(() => setNowStr(timeNow()), 1000);
    
    return () => {
      clearInterval(t);
      clearInterval(tb);
      clearInterval(tw);
      clearInterval(clock);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [qs.department, qs.d, refreshMs, currentBoardId]);

  // Online/offline (старое)
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    setOnline(navigator.onLine);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);

  // Полноэкранный режим (старое)
  const toggleFullscreen = () => {
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      document.documentElement.requestFullscreen();
    }
  };

  // Переключение звука (объединенное)
  const toggleSound = () => {
    setBoardSettings(prev => ({ ...prev, soundEnabled: !prev.soundEnabled }));
  };

  // Переключение контрастного режима (старое)
  const toggleContrast = () => {
    setBoardSettings(prev => ({ ...prev, contrastMode: !prev.contrastMode }));
  };

  // Переключение киоск режима (старое)
  const toggleKiosk = () => {
    setBoardSettings(prev => ({ ...prev, kioskMode: !prev.kioskMode }));
  };

  // Переключение языка (старое)
  const toggleLanguage = () => {
    const languages = ['ru', 'uz', 'en'];
    const currentIndex = languages.indexOf(boardSettings.language);
    const nextIndex = (currentIndex + 1) % languages.length;
    setBoardSettings(prev => ({ ...prev, language: languages[nextIndex] }));
  };

  // Получение объявления по языку (старое)
  const getAnnouncement = (board, lang) => {
    if (lang === 'ru') return board.announcement_ru || board.announcement || '';
    if (lang === 'uz') return board.announcement_uz || board.announcement || '';
    if (lang === 'en') return board.announcement_en || board.announcement || '';
    return board.announcement || '';
  };

  // Получение следующего номера (старое)
  const getNextNumbers = (last, count) => {
    const nums = [];
    for (let i = 1; i <= count; i++) {
      nums.push(last + i);
    }
    return nums;
  };

  // Воспроизведение звука (старое)
  function playBeep() {
    try {
      const audio = new Audio('/sounds/beep.mp3');
      audio.volume = 0.5;
      audio.play().catch(console.error);
    } catch (error) {
      console.error('Ошибка воспроизведения звука:', error);
    }
  }

  // Получение цвета статуса (новое)
  const getStatusColor = (status) => {
    const colors = {
      'waiting': '#f59e0b',
      'called': '#dc3545',
      'serving': '#10b981',
      'completed': '#3b82f6',
      'cancelled': '#6c757d'
    };
    return colors[status] || '#6c757d';
  };

  // Получение текста статуса (новое)
  const getStatusText = (status) => {
    const texts = {
      'waiting': 'Ожидает',
      'called': 'Вызван',
      'serving': 'На приеме',
      'completed': 'Завершен',
      'cancelled': 'Отменен'
    };
    return texts[status] || status;
  };

  // Форматирование времени (новое)
  const formatTime = (dateString) => {
    if (!dateString) return '';
    return new Date(dateString).toLocaleTimeString('ru-RU', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  // Темы оформления (новое)
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
      textPrimary: '#1a202c',
      textSecondary: '#4a5568',
      border: '#c6f6d5'
    }
  };

  const currentTheme = themes[boardSettings.theme] || themes.light;

  // Стили (объединенные)
  const containerStyle = {
    minHeight: '100vh',
    background: board.bg_color || currentTheme.background,
    color: board.text_color || currentTheme.textPrimary,
    fontSize: `calc(1rem * ${boardSettings.fontScale})`,
    fontFamily: 'system-ui, -apple-system, sans-serif',
    padding: '20px',
    ...(boardSettings.contrastMode ? {
      background: '#000000',
      color: '#ffffff',
      filter: 'contrast(150%)'
    } : {}),
    ...(boardSettings.kioskMode ? {
      cursor: 'none',
      userSelect: 'none'
    } : {})
  };

  const headerStyle = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '20px',
    background: currentTheme.cardBg,
    borderRadius: '12px',
    marginBottom: '20px',
    border: `1px solid ${currentTheme.border}`,
    boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
  };

  const currentCallStyle = {
    background: currentCall ? 'linear-gradient(135deg, #dc3545 0%, #e74c3c 100%)' : currentTheme.cardBg,
    color: currentCall ? '#ffffff' : currentTheme.textPrimary,
    padding: '40px',
    borderRadius: '16px',
    marginBottom: '30px',
    textAlign: 'center',
    border: currentCall ? 'none' : `1px solid ${currentTheme.border}`,
    boxShadow: currentCall ? '0 8px 16px rgba(220, 53, 69, 0.3)' : '0 4px 6px rgba(0, 0, 0, 0.1)',
    transform: currentCall ? 'scale(1.02)' : 'scale(1)',
    transition: 'all 0.3s ease',
    animation: currentCall ? 'pulse 2s infinite' : 'none'
  };

  const statsGridStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '20px',
    marginBottom: '30px'
  };

  const statCardStyle = {
    background: currentTheme.cardBg,
    padding: '20px',
    borderRadius: '12px',
    textAlign: 'center',
    border: `1px solid ${currentTheme.border}`,
    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)'
  };

  const queueGridStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
    gap: '15px',
    marginBottom: '30px'
  };

  const queueCardStyle = {
    background: currentTheme.cardBg,
    padding: '20px',
    borderRadius: '12px',
    textAlign: 'center',
    border: `2px solid ${getStatusColor('waiting')}`,
    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
    transition: 'all 0.3s ease'
  };

  const announcementStyle = {
    background: 'linear-gradient(135deg, #007bff 0%, #0056b3 100%)',
    color: '#ffffff',
    padding: '15px',
    borderRadius: '8px',
    marginBottom: '10px',
    textAlign: 'center',
    animation: 'slideIn 0.5s ease'
  };

  return (
    <div style={containerStyle}>
      {/* Заголовок */}
      <div style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          {board.logo ? (
            <img src={board.logo} alt={board.brand} style={{ height: '50px' }} />
          ) : (
            <div style={{ fontSize: '2rem' }}>🏥</div>
          )}
          <div>
            <h1 style={{ fontSize: '2rem', fontWeight: 'bold', margin: 0, color: currentTheme.textPrimary }}>
              {board.brand}
            </h1>
            <p style={{ margin: 0, color: currentTheme.textSecondary }}>
              {department} • {dateStr}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          {/* Статус соединения */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {connected ? <Wifi size={20} color="#10b981" /> : <WifiOff size={20} color="#dc3545" />}
            <span style={{ 
              fontSize: '0.9rem',
              color: currentTheme.textSecondary,
            }}>
              {connected ? 'Подключено' : 'Отключено'}
            </span>
          </div>

          {/* Время */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={20} color={currentTheme.textSecondary} />
            <span style={{ 
              fontSize: '1.2rem',
              fontWeight: 'bold',
              color: currentTheme.textPrimary
            }}>
              {nowStr}
            </span>
          </div>

          {/* Кнопки управления */}
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={toggleFullscreen}
              style={{
                background: 'transparent',
                border: '1px solid ' + currentTheme.border,
                borderRadius: '8px',
                padding: '8px',
                cursor: 'pointer',
                color: currentTheme.textSecondary,
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
              title="Полноэкранный режим"
            >
              {document.fullscreenElement ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            </button>

            <button
              onClick={toggleSound}
              style={{
                background: 'transparent',
                border: '1px solid ' + currentTheme.border,
                borderRadius: '8px',
                padding: '8px',
                cursor: 'pointer',
                color: currentTheme.textSecondary,
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
              title={boardSettings.soundEnabled ? 'Выключить звук' : 'Включить звук'}
            >
              {boardSettings.soundEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
            </button>

            <button
              onClick={toggleContrast}
              style={{
                background: 'transparent',
                border: '1px solid ' + currentTheme.border,
                borderRadius: '8px',
                padding: '8px',
                cursor: 'pointer',
                color: currentTheme.textSecondary,
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
              title="Контрастный режим"
            >
              {boardSettings.contrastMode ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>

            <button
              onClick={toggleLanguage}
              style={{
                background: 'transparent',
                border: '1px solid ' + currentTheme.border,
                borderRadius: '8px',
                padding: '8px',
                cursor: 'pointer',
                color: currentTheme.textSecondary,
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
              title="Переключить язык"
            >
              <Globe size={16} />
              {boardSettings.language.toUpperCase()}
            </button>
          </div>
        </div>
      </div>

      {/* Статусные баннеры */}
      {!online && (
        <div style={{
          background: 'rgba(59,130,246,0.25)',
          border: '1px solid rgba(59,130,246,0.5)',
          padding: '15px',
          borderRadius: '8px',
          marginBottom: '20px',
          textAlign: 'center',
          color: '#1e40af'
        }}>
          Нет соединения. Показаны данные из кэша.
        </div>
      )}

      {board.is_closed && (
        <div style={{
          background: 'rgba(239,68,68,0.25)',
          border: '1px solid rgba(239,68,68,0.5)',
          padding: '15px',
          borderRadius: '8px',
          marginBottom: '20px',
          textAlign: 'center',
          color: '#dc2626'
        }}>
          {t('closed', boardSettings.language)}
        </div>
      )}

      {!board.is_closed && board.is_paused && (
        <div style={{
          background: 'rgba(245,158,11,0.25)',
          border: '1px solid rgba(245,158,11,0.5)',
          padding: '15px',
          borderRadius: '8px',
          marginBottom: '20px',
          textAlign: 'center',
          color: '#d97706'
        }}>
          {t('paused', boardSettings.language)}
        </div>
      )}

      {/* Текущий вызов */}
      <div style={currentCallStyle}>
        {currentCall ? (
          <div>
            <div style={{ fontSize: '4rem', fontWeight: 'bold', marginBottom: '20px' }}>
              № {currentCall.queue_number}
            </div>
            <div style={{ fontSize: '1.5rem', marginBottom: '10px' }}>
              {currentCall.patient_name}
            </div>
            <div style={{ fontSize: '1.2rem', marginBottom: '10px' }}>
              👨‍⚕️ {currentCall.doctor_name}
            </div>
            {currentCall.cabinet && (
              <div style={{ fontSize: '1.1rem' }}>
                🚪 {currentCall.cabinet}
              </div>
            )}
          </div>
        ) : (
          <div>
            <Monitor size={64} style={{ color: currentTheme.textSecondary, marginBottom: '20px' }} />
            <div style={{ fontSize: '1.5rem', color: currentTheme.textSecondary }}>
              {t('now_serving', boardSettings.language)}
            </div>
            <div style={{ fontSize: '3rem', fontWeight: 'bold', marginTop: '20px' }}>
              {stats.last_ticket || 0}
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
                ...announcementStyle,
                background: announcement.announcement_type === 'emergency' 
                  ? 'linear-gradient(135deg, #dc3545 0%, #c82333 100%)'
                  : announcement.announcement_type === 'warning'
                  ? 'linear-gradient(135deg, #ffc107 0%, #e0a800 100%)'
                  : 'linear-gradient(135deg, #007bff 0%, #0056b3 100%)',
                marginBottom: '10px',
                padding: '15px',
                borderRadius: '8px',
                textAlign: 'center',
                animation: 'slideIn 0.5s ease'
              }}
            >
              📢 {announcement.text}
            </div>
          ))}
        </div>
      )}

      {/* Очередь */}
      <div style={queueGridStyle}>
        {queueData.slice(0, boardSettings.displayCount).map(entry => (
          <div
            key={entry.number}
            style={{
              ...queueCardStyle,
              borderColor: getStatusColor(entry.status),
              background: entry.status === 'called' ? 'rgba(220, 53, 69, 0.1)' : currentTheme.cardBg
            }}
          >
            <div style={{
              fontSize: '2rem',
              fontWeight: 'bold',
              color: getStatusColor(entry.status),
              marginBottom: '10px'
            }}>
              {entry.number}
            </div>
            
            {boardSettings.showPatientNames !== 'none' && (
              <div style={{
                fontSize: '1rem',
                color: currentTheme.textPrimary,
                marginBottom: '10px'
              }}>
                {entry.patient_name}
              </div>
            )}

            <div style={{
              background: getStatusColor(entry.status),
              color: '#ffffff',
              padding: '5px 10px',
              borderRadius: '20px',
              fontSize: '0.9rem',
              fontWeight: 'bold',
              marginBottom: '10px'
            }}>
              {getStatusText(entry.status)}
            </div>

            <div style={{
              fontSize: '0.8rem',
              color: currentTheme.textSecondary,
              marginBottom: '5px'
            }}>
              {entry.status === 'called' && entry.called_at ? (
                `Вызван: ${formatTime(entry.called_at)}`
              ) : (
                `Записан: ${formatTime(entry.created_at)}`
              )}
            </div>

            <div style={{
              fontSize: '0.8rem',
              color: currentTheme.textSecondary,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '5px'
            }}>
              {entry.source === 'online' ? '📱 Онлайн' : '🏥 Регистратура'}
            </div>
          </div>
        ))}
      </div>

      {/* Окна/кабинеты */}
      {windows && windows.length > 0 && (
        <div style={{ marginBottom: '30px' }}>
          <h3 style={{ fontSize: '1.5rem', marginBottom: '20px', color: currentTheme.textPrimary }}>
            Окна
          </h3>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: '15px'
          }}>
            {windows.map((w, i) => (
              <div key={i} style={{
                background: currentTheme.cardBg,
                padding: '20px',
                borderRadius: '12px',
                textAlign: 'center',
                border: `1px solid ${currentTheme.border}`,
                boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)'
              }}>
                <div style={{ fontSize: '1.2rem', fontWeight: 'bold', marginBottom: '10px', color: currentTheme.textPrimary }}>
                  Окно {w.window}
                </div>
                <div style={{ fontSize: '2rem', fontWeight: 'bold', color: getStatusColor('serving') }}>
                  {w.ticket || '—'}
                </div>
                {w.label && (
                  <div style={{ fontSize: '0.9rem', color: currentTheme.textSecondary, marginTop: '5px' }}>
                    {w.label}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Статистика */}
      <div style={statsGridStyle}>
        <div style={statCardStyle}>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: currentTheme.textPrimary }}>
            {queueData.length}
          </div>
          <div style={{ color: currentTheme.textSecondary }}>Всего в очереди</div>
        </div>

        <div style={statCardStyle}>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: currentTheme.textPrimary }}>
            {queueData.filter(e => e.status === 'waiting').length}
          </div>
          <div style={{ color: currentTheme.textSecondary }}>Ожидают</div>
        </div>

        <div style={statCardStyle}>
          <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: currentTheme.textPrimary }}>
            {new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
          </div>
          <div style={{ color: currentTheme.textSecondary }}>Текущее время</div>
        </div>

        <div style={statCardStyle}>
          <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: currentTheme.textPrimary }}>
            {stats.waiting}
          </div>
          <div style={{ color: currentTheme.textSecondary }}>Ожидают (старая)</div>
        </div>

        <div style={statCardStyle}>
          <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: currentTheme.textPrimary }}>
            {stats.serving}
          </div>
          <div style={{ color: currentTheme.textSecondary }}>Принимаются</div>
        </div>

        <div style={statCardStyle}>
          <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: currentTheme.textPrimary }}>
            {stats.done}
          </div>
          <div style={{ color: currentTheme.textSecondary }}>Готово</div>
        </div>
      </div>

      {/* Объявление внизу */}
      {(getAnnouncement(board, boardSettings.language) || announcement) && (
        <div style={{
          background: currentTheme.cardBg,
          padding: '20px',
          borderRadius: '12px',
          textAlign: 'center',
          border: `1px solid ${currentTheme.border}`,
          marginTop: '30px'
        }}>
          <div style={{
            fontSize: '1.1rem',
            color: currentTheme.textPrimary,
            animation: 'scroll 20s linear infinite'
          }}>
            {getAnnouncement(board, boardSettings.language) || announcement || 'Добро пожаловать! Пожалуйста, ожидайте своей очереди.'}
          </div>
        </div>
      )}

      {/* Ошибки */}
      {err && (
        <div style={{
          background: 'rgba(239,68,68,0.1)',
          border: '1px solid rgba(239,68,68,0.3)',
          color: '#dc2626',
          padding: '15px',
          borderRadius: '8px',
          marginTop: '20px',
          textAlign: 'center'
        }}>
          {err}
        </div>
      )}

      {/* CSS анимации */}
      <style>{`
        @keyframes pulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.05); }
        }
        
        @keyframes slideIn {
          from { transform: translateY(-20px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        
        @keyframes scroll {
          0% { transform: translateX(100%); }
          100% { transform: translateX(-100%); }
        }
      `}</style>
    </div>
  );
}

// Вспомогательные функции (старые)
function todayStr() {
  const d = new Date();
  return d.getFullYear() + '-' + 
    String(d.getMonth() + 1).padStart(2, '0') + '-' + 
    String(d.getDate()).padStart(2, '0');
}

function timeNow() {
  const d = new Date();
  return String(d.getHours()).padStart(2, '0') + ':' + 
    String(d.getMinutes()).padStart(2, '0') + ':' + 
    String(d.getSeconds()).padStart(2, '0');
}

function t(key, lang = 'ru') {
  const translations = {
    ru: {
      'now_serving': 'Сейчас обслуживается',
      'closed': 'Клиника закрыта',
      'paused': 'Работа приостановлена',
      'updated': 'Обновлено'
    },
    uz: {
      'now_serving': 'Hozir xizmat ko\'rsatilmoqda',
      'closed': 'Klinika yopiq',
      'paused': 'Ish to\'xtatilgan',
      'updated': 'Yangilandi'
    },
    en: {
      'now_serving': 'Now serving',
      'closed': 'Clinic is closed',
      'paused': 'Service paused',
      'updated': 'Updated'
    }
  };
  
  return (translations[lang] && translations[lang][key]) || translations.ru[key] || key;
}
