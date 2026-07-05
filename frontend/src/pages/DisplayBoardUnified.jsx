import { useState, useEffect, useRef, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
  Volume2,
  VolumeX,

  Wifi,
  WifiOff,
  Monitor,
  Clock,


  Maximize2,
  Minimize2,
  Globe,
  Eye,
  EyeOff } from
'lucide-react';
import { api } from '../api/client';
import { openDisplayBoardWS } from '../api/ws';
import { useTheme } from '../contexts/ThemeContext';

import logger from '../utils/logger';
import PropTypes from 'prop-types';
import { formatRegistrarTime } from '../utils/dateUtils';
import './displayboard.css';

const DEFAULT_BOARD_STATS = { last_ticket: 0, waiting: 0, serving: 0, done: 0 };

const extractBoardStats = (source) => ({
  last_ticket: Number(source?.last_ticket || 0),
  waiting: Number(source?.waiting || 0),
  serving: Number(source?.serving || 0),
  done: Number(source?.done || 0)
});

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
  department: departmentProp,
  dateStr = todayStr(),
  refreshMs = 15000,
  announcement = '',
  lang = 'ru',
  kiosk = false,
  soundInitial = undefined,
  contrast = false,
  fontScale = 1,
  boardId = 'main_board'
}) {void
  useTheme();

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
  const [stats, setStats] = useState(DEFAULT_BOARD_STATS);
  const [err, setErr] = useState('');
  const [nowStr, setNowStr] = useState(timeNow());

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
    sound_default: true
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
  const legacyWindowsLookupWarnedRef = useRef(false);
  const loadBoardStateRef = useRef(() => {});
  const loadWindowsRef = useRef(() => {});
  const connectWebSocketRef = useRef(() => {});
  const lastTicketRef = useRef(0);
  const [online, setOnline] = useState(true);

  // Получаем board_id из URL или используем переданный
  const currentBoardId = new URLSearchParams(window.location.search).get('board') || boardId;
  const isBoardView = window.location.pathname.startsWith('/queue-board') || window.location.pathname.startsWith('/display-board');

  // /board/state is a stats/settings snapshot; live rows/calls/announcements come from WebSocket initial_state.
  async function loadBoardState() {setErr('');try {const st = (await api.get('/board/state', { params: { department: qs.department, date: qs.d } })).data;if (st && typeof st === 'object') {
        setStats(extractBoardStats(st));
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
          contrast_default: !!st.contrast_default,
          kiosk_default: !!st.kiosk_default,
          sound_default: st.sound_default !== false
        });
        if (soundInitial === undefined && typeof st.sound_default !== 'undefined') {
          setBoardSettings((prev) => ({ ...prev, soundEnabled: st.sound_default !== false }));
        }
        try {localStorage.setItem('board.state', JSON.stringify(st));} catch {







          // Игнорируем ошибки localStorage
        }}} catch (e) {setErr(e?.message || 'Ошибка загрузки'); // fallback из кэша
      try {const raw = localStorage.getItem('board.state');if (raw) {const cached = JSON.parse(raw);if (cached && typeof cached === 'object') {
            setStats(extractBoardStats(cached));
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
              contrast_default: !!cached.contrast_default,
              kiosk_default: !!cached.kiosk_default,
              sound_default: cached.sound_default !== false
            });
          }
        }
      } catch {







        // Игнорируем ошибки localStorage
      }}} // Загрузка окон/кабинетов (старое)
  async function loadWindows() {
    // Legacy windows endpoint no longer exists in the current backend contract.
    // Keep the section empty instead of hammering a dead route every refresh tick.
    if (!legacyWindowsLookupWarnedRef.current) {
      logger.info('[DisplayBoardUnified] Legacy windows lookup disabled; backend no longer exposes queue/queue/status');
      legacyWindowsLookupWarnedRef.current = true;
    }
    setWindows([]);
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
      logger.error('Ошибка создания WebSocket:', error);
      setConnected(false);
    }
  };

  // Обработка WebSocket сообщений (новое)
  const handleWebSocketMessage = (message) => {
    logger.log('Получено WebSocket сообщение:', message);

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
          setQueueData((prev) => [...prev, message.data]);
          logger.log(`➕ Новая запись в очереди: №${message.data.number}`);
        } else {
          // Обновляем всю очередь
          setQueueData(message.data.queue_entries || []);
        }
        break;

      case 'announcement':
        setAnnouncements((prev) => [message.data, ...prev.slice(0, 4)]);
        if (boardSettings.soundEnabled) {
          playAnnouncementSound(message);
        }
        break;

      case 'announcement_removed':
        setAnnouncements((prev) => prev.filter((a) => a.created_at !== message.data.created_at));
        break;

      default:
        logger.log('Неизвестный тип сообщения:', message.type);
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

      logger.log(`🔊 Звуковой сигнал для пациента №${message.data.number}`);

      // Голосовое объявление
      if (boardSettings.voiceEnabled) {
        const text = `Пациент номер ${message.data.number}, ${message.data.patient_name}, пройдите к врачу ${message.data.doctor_name}`;
        playVoiceAnnouncement(text);
      }
    } catch (error) {
      logger.error('Ошибка воспроизведения звука:', error);
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
      audio.play().catch((playError) => logger.error('Ошибка воспроизведения звука объявления:', playError));

      // Голосовое объявление
      if (boardSettings.voiceEnabled && message.voice_text) {
        playVoiceAnnouncement(message.voice_text);
      }
    } catch (error) {
      logger.error('Ошибка воспроизведения звука объявления:', error);
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
      logger.error('Ошибка голосового объявления:', error);
    }
  };

  loadBoardStateRef.current = loadBoardState;
  loadWindowsRef.current = loadWindows;
  connectWebSocketRef.current = connectWebSocket;

  // Звук при смене номера (старое)
  useEffect(() => {
    const prev = Number(lastTicketRef.current || 0);
    const cur = Number(stats.last_ticket || 0);
    if (cur && cur !== prev && boardSettings.soundEnabled) playBeep();
    lastTicketRef.current = cur;
  }, [stats.last_ticket, boardSettings.soundEnabled]);

  // Инициализация
  useEffect(() => {
    loadBoardStateRef.current();
    loadWindowsRef.current();
    connectWebSocketRef.current();

    const clock = setInterval(() => setNowStr(timeNow()), 1000);
    const tb = isBoardView ? null : setInterval(() => loadBoardStateRef.current(), Math.max(15000, Number(refreshMs || 0)));
    const tw = isBoardView ? null : setInterval(() => loadWindowsRef.current(), Math.max(5000, Number(refreshMs || 0)));

    return () => {
      if (tb) clearInterval(tb);
      if (tw) clearInterval(tw);
      clearInterval(clock);
      if (wsRef.current) {
        const closeWS = wsRef.current;
        wsRef.current = null;
        try {
          closeWS();
          logger.info('[DisplayBoardUnified] WebSocket cleanup completed');
        } catch (error) {
          logger.warn('[DisplayBoardUnified] WebSocket cleanup failed', error);
        }
      }
    };
  }, [isBoardView, qs.department, qs.d, refreshMs, currentBoardId]);

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
    setBoardSettings((prev) => ({ ...prev, soundEnabled: !prev.soundEnabled }));
  };

  // Переключение контрастного режима (старое)
  const toggleContrast = () => {
    setBoardSettings((prev) => ({ ...prev, contrastMode: !prev.contrastMode }));
  };

  // Переключение киоск режима (старое)




  // Переключение языка (старое)
  const toggleLanguage = () => {
    const languages = ['ru', 'uz', 'en'];
    const currentIndex = languages.indexOf(boardSettings.language);
    const nextIndex = (currentIndex + 1) % languages.length;
    setBoardSettings((prev) => ({ ...prev, language: languages[nextIndex] }));
  };

  // Получение объявления по языку (старое)
  const getAnnouncement = (board, lang) => {
    if (lang === 'ru') return board.announcement_ru || board.announcement || '';
    if (lang === 'uz') return board.announcement_uz || board.announcement || '';
    if (lang === 'en') return board.announcement_en || board.announcement || '';
    return board.announcement || '';
  };

  // Получение следующего номера (старое)








  // Воспроизведение звука (старое)
  function playBeep() {
    try {
      const audio = new Audio('/sounds/beep.mp3');
      audio.volume = 0.5;
      audio.play().catch((playError) => logger.error('Ошибка воспроизведения сигнала:', playError));
    } catch (error) {
      logger.error('Ошибка воспроизведения звука:', error);
    }
  }

  // Получение цвета статуса (новое) — цвета теперь декларированы в displayboard.css
  // через [data-status="..."] селекторы на .displayboard-queue-card. Эта обертка
  // оставлена для возможных будущих потребителей и тестов.

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
    return formatRegistrarTime(dateString);
  };

  // Темы оформления (новое)
  const themes = {
    light: {
      background: 'linear-gradient(135deg, var(--mac-bg-secondary) 0%, var(--mac-border) 100%)',
      cardBg: 'var(--mac-bg-primary)',
      textPrimary: '#1a202c',
      textSecondary: '#4a5568',
      border: 'var(--mac-border)'
    },
    dark: {
      background: 'linear-gradient(135deg, #1a202c 0%, #2d3748 100%)',
      cardBg: '#2d3748',
      textPrimary: '#f7fafc',
      textSecondary: '#a0aec0',
      border: '#4a5568'
    },
    medical: {
      background: 'linear-gradient(135deg, #f0fff4 0%, var(--mac-success-bg) 100%)',
      cardBg: 'var(--mac-bg-primary)',
      textPrimary: '#1a202c',
      textSecondary: '#4a5568',
      border: '#c6f6d5'
    }
  };

  const currentTheme = themes[boardSettings.theme] || themes.light;

  // Стили (объединенные) — см. displayboard.css. Тема инжектируется как
  // CSS custom properties на корневом контейнере, чтобы классы могли ссылаться
  // на var(--board-*). Контраст/киоск переключаются модификаторами класса.

  const rootClassName = [
    'displayboard-root',
    boardSettings.contrastMode ? 'displayboard-root--contrast' : '',
    boardSettings.kioskMode ? 'displayboard-root--kiosk' : ''
  ].filter(Boolean).join(' ');

  const rootCssVars = {
    '--board-bg': board.bg_color || currentTheme.background,
    '--board-text-primary': board.text_color || currentTheme.textPrimary,
    '--board-text-secondary': currentTheme.textSecondary,
    '--board-card-bg': currentTheme.cardBg,
    '--board-border': currentTheme.border,
    '--board-font-scale': String(boardSettings.fontScale)
  };

  return (
    <div className={rootClassName} style={rootCssVars}>
      {/* Заголовок */}
      <div className="displayboard-header">
        <div className="displayboard-flex-center-20">
          {board.logo ?
          <img src={board.logo} alt={board.brand} className="displayboard-logo" /> :

          <div className="displayboard-emoji-2rem">🏥</div>
          }
          <div>
            <h1 className="displayboard-brand-title">
              {board.brand}
            </h1>
            <p className="displayboard-brand-subtitle">
              {department} • {dateStr}
            </p>
          </div>
        </div>

        <div className="displayboard-flex-center-20">
          {/* Статус соединения */}
          <div className="displayboard-flex-center-8">
            {connected ? <Wifi size={20} color="var(--mac-success)" /> : <WifiOff size={20} color="#dc3545" />}
            <span className="displayboard-conn-status">
              {connected ? 'Подключено' : 'Отключено'}
            </span>
          </div>

          {/* Время */}
          <div className="displayboard-flex-center-8">
            <Clock size={20} color={currentTheme.textSecondary} />
            <span className="displayboard-clock">
              {nowStr}
            </span>
          </div>

          {/* Кнопки управления */}
          <div className="displayboard-flex-gap-10">
            <button
              onClick={toggleFullscreen}
              className="displayboard-btn"
              title="Полноэкранный режим"
              aria-label={document.fullscreenElement ? 'Выйти из полноэкранного режима' : 'Включить полноэкранный режим'}>
              
              {document.fullscreenElement ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            </button>

            <button
              onClick={toggleSound}
              className="displayboard-btn"
              title={boardSettings.soundEnabled ? 'Выключить звук' : 'Включить звук'}
              aria-label={boardSettings.soundEnabled ? 'Выключить звук' : 'Включить звук'}>
              
              {boardSettings.soundEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
            </button>

            <button
              onClick={toggleContrast}
              className="displayboard-btn"
              title="Контрастный режим"
              aria-label={boardSettings.contrastMode ? 'Выключить контрастный режим' : 'Включить контрастный режим'}>
              
              {boardSettings.contrastMode ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>

            <button
              onClick={toggleLanguage}
              className="displayboard-btn"
              title="Переключить язык">
              
              <Globe size={16} />
              {boardSettings.language.toUpperCase()}
            </button>
          </div>
        </div>
      </div>

      {/* Статусные баннеры */}
      {!online &&
      <div className="displayboard-banner displayboard-banner--info">
          Нет соединения. Показаны данные из кэша.
        </div>
      }

      {board.is_closed &&
      <div className="displayboard-banner displayboard-banner--danger">
          {t('closed', boardSettings.language)}
        </div>
      }

      {!board.is_closed && board.is_paused &&
      <div className="displayboard-banner displayboard-banner--warning">
          {t('paused', boardSettings.language)}
        </div>
      }

      {/* Текущий вызов */}
      <div className={`displayboard-current-call${currentCall ? ' displayboard-current-call--active' : ''}`}>
        {currentCall ?
        <div>
            <div className="displayboard-call-number">
              № {currentCall.queue_number}
            </div>
            <div className="displayboard-call-patient">
              {currentCall.patient_name}
            </div>
            <div className="displayboard-call-doctor">
              👨‍⚕️ {currentCall.doctor_name}
            </div>
            {currentCall.cabinet &&
          <div className="displayboard-call-cabinet">
                🚪 {currentCall.cabinet}
              </div>
          }
          </div> :

        <div>
            <Monitor size={64} className="displayboard-no-call-icon" />
            <div className="displayboard-no-call-title">
              {t('now_serving', boardSettings.language)}
            </div>
            <div className="displayboard-no-call-ticket">
              {stats.last_ticket || 0}
            </div>
          </div>
        }
      </div>

      {/* Объявления */}
      {announcements.length > 0 &&
      <div className="displayboard-announcements-wrap">
          {announcements.map((announcement) =>
        <div
          key={announcement.created_at}
          className="displayboard-announcement"
          data-announcement-type={announcement.announcement_type}>
          
              📢 {announcement.text}
            </div>
        )}
        </div>
      }

      {/* Очередь */}
      <div className="displayboard-queue-grid">
        {queueData.slice(0, boardSettings.displayCount).map((entry) =>
        <div
          key={entry.number}
          className="displayboard-queue-card"
          data-status={entry.status}>
          
            <div className="displayboard-queue-number">
              {entry.number}
            </div>
            
            {boardSettings.showPatientNames !== 'none' &&
          <div className="displayboard-queue-patient">
                {entry.patient_name}
              </div>
          }

            <div className="displayboard-queue-badge">
              {getStatusText(entry.status)}
            </div>

            <div className="displayboard-queue-time">
              {entry.status === 'called' && entry.called_at ?
            `Вызван: ${formatTime(entry.called_at)}` :

            `Записан: ${formatTime(entry.created_at)}`
            }
            </div>

            <div className="displayboard-queue-source">
              {entry.source === 'online' ? '📱 Онлайн' : '🏥 Регистратура'}
            </div>
          </div>
        )}
      </div>

      {/* Окна/кабинеты */}
      {windows && windows.length > 0 &&
      <div className="displayboard-windows-wrap">
          <h3 className="displayboard-windows-title">
            Окна
          </h3>
          <div className="displayboard-windows-grid">
            {windows.map((w, i) =>
          <div key={i} className="displayboard-window-card">
                <div className="displayboard-window-label">
                  Окно {w.window}
                </div>
                <div className="displayboard-window-ticket">
                  {w.ticket || '—'}
                </div>
                {w.label &&
            <div className="displayboard-window-sub">
                    {w.label}
                  </div>
            }
              </div>
          )}
          </div>
        </div>
      }

      {/* Статистика */}
      <div className="displayboard-stats-grid">
        <div className="displayboard-stat-card">
          <div className="displayboard-stat-value-lg">
            {queueData.length}
          </div>
          <div className="displayboard-stat-label">Всего в очереди</div>
        </div>

        <div className="displayboard-stat-card">
          <div className="displayboard-stat-value-lg">
            {queueData.filter((e) => e.status === 'waiting').length}
          </div>
          <div className="displayboard-stat-label">Ожидают</div>
        </div>

        <div className="displayboard-stat-card">
          <div className="displayboard-stat-value-md">
            {formatRegistrarTime(new Date().toISOString())}
          </div>
          <div className="displayboard-stat-label">Текущее время</div>
        </div>

        <div className="displayboard-stat-card">
          <div className="displayboard-stat-value-md">
            {stats.waiting}
          </div>
          <div className="displayboard-stat-label">Ожидают (старая)</div>
        </div>

        <div className="displayboard-stat-card">
          <div className="displayboard-stat-value-md">
            {stats.serving}
          </div>
          <div className="displayboard-stat-label">Принимаются</div>
        </div>

        <div className="displayboard-stat-card">
          <div className="displayboard-stat-value-md">
            {stats.done}
          </div>
          <div className="displayboard-stat-label">Готово</div>
        </div>
      </div>

      {/* Объявление внизу */}
      {(getAnnouncement(board, boardSettings.language) || announcement) &&
      <div className="displayboard-bottom-announcement">
          <div className="displayboard-bottom-announcement-text">
            {getAnnouncement(board, boardSettings.language) || announcement || 'Добро пожаловать! Пожалуйста, ожидайте своей очереди.'}
          </div>
        </div>
      }

      {/* Ошибки */}
      {err &&
      <div className="displayboard-error">
          {err}
        </div>
      }
    </div>);

}


DisplayBoardUnified.propTypes = {
  ...(DisplayBoardUnified.propTypes || {}),
  announcement: PropTypes.any,
  boardId: PropTypes.any,
  contrast: PropTypes.any,
  dateStr: PropTypes.any,
  department: PropTypes.any,
  fontScale: PropTypes.any,
  kiosk: PropTypes.any,
  lang: PropTypes.any,
  refreshMs: PropTypes.any,
  soundInitial: PropTypes.any,
};

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

  return translations[lang] && translations[lang][key] || translations.ru[key] || key;
}
