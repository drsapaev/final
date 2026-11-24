import { useState, useCallback, useEffect, useRef, useMemo, type FormEvent } from 'react';
import type { CSSProperties } from 'react';
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
import { openDisplayBoardWS, type DisplayTestAudioStatus, type DisplayTestReply } from '../api/ws';
import {
  exchangeDisplayDeviceSession,
  exchangeDisplayDeviceCredential,
  forgetDisplayDeviceSession,
  DisplayDeviceProvisioningRequiredError,
} from '../api/displayDeviceAuth';
import { useTheme } from '../contexts/ThemeContext';

import logger from '../utils/logger';
import { formatRegistrarTime } from '../utils/dateUtils';
import './displayboard.css';
import { useTranslation } from '../i18n/useTranslation';
import { safeJsonParse } from '../utils/safeJsonParse';
import { tokenManager } from '../utils/tokenManager';

interface BoardStats {
  waiting: number;
  serving: number;
  done: number;
}

interface BoardState {
  brand: string;
  logo: string;
  is_paused: boolean;
  is_closed: boolean;
  announcement: string;
  announcement_ru: string;
  announcement_uz: string;
  announcement_en: string;
  primary_color: string;
  bg_color: string;
  text_color: string;
  contrast_default: boolean;
  kiosk_default: boolean;
  sound_default: boolean;
  show_patient_names?: string;
}

interface QueueEntryDto {
  // RQ-24.a.2: identity/owner fields delivered by the WS channels
  // (initial_state carries id/specialist_name per entry; queue_update
  // attaches doctor_name/specialty/cabinet per queue message).
  id?: number | string;
  queue_id?: number | string;
  number: number | string;
  patient_name?: string;
  status: string;
  called_at?: string;
  created_at?: string;
  source?: string;
  doctor_name?: string;
  specialist_name?: string;
  specialty?: string;
  cabinet?: string | null;
}

// RQ-24.a.2: rows from different queues can share one board (every queue is
// broadcast to every board), so a bare ticket number is not a unique/stable
// React key. Scope the key by any available queue identity, keep it stable
// across re-renders, and fall back to a deterministic index key only when the
// payload carries no scope fields at all.
export const resolveBoardEntryKey = (entry: QueueEntryDto, index: number): string => {
  const scopeParts = [
    entry.id !== undefined && entry.id !== null ? String(entry.id) : '',
    entry.queue_id !== undefined && entry.queue_id !== null ? String(entry.queue_id) : '',
    entry.doctor_name ?? entry.specialist_name ?? '',
    entry.cabinet ?? '',
  ].filter((part) => part !== '');
  if (scopeParts.length === 0) {
    return `board-entry-${index}-${entry.number}`;
  }
  return `${scopeParts.join('|')}#${entry.number}`;
};

interface CurrentCall {
  queue_id?: string | number;
  queue_entry_id?: string | number;
  event_id?: string;
  issued_at?: string;
  expires_at?: string;
  queue_number?: number | string;
  patient_name?: string;
  doctor_name?: string;
  cabinet?: string | null;
}

type VoiceLanguage = 'ru' | 'uz' | 'en';
const voiceLocale = (language: VoiceLanguage) => language === 'uz' ? 'uz-Latn' : language;

interface BoardAudioProfile {
  enabled: boolean;
  voiceEnabled: boolean;
  voiceLanguage: VoiceLanguage;
  volume: number;
  voiceReady?: Promise<void>;
}

interface DisplayTest {
  id: string;
  call: CurrentCall | null;
  expiresAt: number;
  reply: DisplayTestReply;
}

interface Announcement {
  created_at?: string;
  announcement_type?: string;
  text?: string;
  // DISPLAYANNOUNCE-FE-001 (audit PR #3961): backend-owned expiry
  // (display_duration seconds) — the notice must leave the TV when the
  // requested window passes, not stay for the whole session.
  expires_at?: number;
}

interface WindowItem {
  window?: string | number;
  ticket?: string | number;
  label?: string;
}

interface BoardSettingsState {
  theme: string;
  showPatientNames: string;
  soundEnabled: boolean;
  displayCount: number;
  // DISPLAYOPTIONS-FE-001 (audit PR #3961): show_announcements табло
  // управляет показом блока объявлений на живом экране.
  showAnnouncements: boolean;
  contrastMode: boolean;
  kioskMode: boolean;
  fontScale: number;
  language: string;
}

interface WSMessageData extends CurrentCall {
  number?: number | string;
  queue_entries?: QueueEntryDto[];
  current_call?: CurrentCall | null;
  announcements?: Announcement[];
  created_at?: string;
  voice_text?: string;
  announcement_type?: string;
  [key: string]: unknown;
}

interface WSMessage {
  type: string;
  data: WSMessageData;
  event_type?: string;
  voice_text?: string;
  sound_enabled?: boolean;
  display_duration?: number;
}

interface DisplayBoardUnifiedProps {
  department?: string;
  dateStr?: string;
  refreshMs?: number;
  announcement?: string;
  lang?: string;
  kiosk?: boolean;
  soundInitial?: boolean;
  contrast?: boolean;
  fontScale?: number;
  boardId?: string;
}

const extractBoardStats = (source: Record<string, unknown>): BoardStats => ({
  waiting: Number(source.waiting || 0),
  serving: Number(source.serving || 0),
  done: Number(source.done || 0)
});

const boardPresentation = (state: Record<string, unknown>): BoardState => ({
  brand: String(state.brand ?? state.title ?? 'Clinic'),
  logo: String(state.logo ?? state.logo_url ?? ''),
  is_paused: Boolean(state.is_paused || state.paused),
  is_closed: Boolean(state.is_closed || state.closed),
  announcement: String(state.announcement ?? state.ticker ?? ''),
  announcement_ru: String(state.announcement_ru ?? ''),
  announcement_uz: String(state.announcement_uz ?? ''),
  announcement_en: String(state.announcement_en ?? ''),
  primary_color: String(state.primary_color ?? ''),
  bg_color: String(state.bg_color ?? ''),
  text_color: String(state.text_color ?? ''),
  contrast_default: Boolean(state.contrast_default),
  kiosk_default: Boolean(state.kiosk_default),
  sound_default: state.sound_enabled !== undefined
    ? state.sound_enabled === true
    : state.sound_default !== false,
});

function eventDeadline(value: unknown, fallbackSeconds?: number) {
  if (typeof value === 'string') return Date.parse(value);
  return fallbackSeconds ? Date.now() + fallbackSeconds * 1000 : Number.NaN;
}

function sameId(a: unknown, b: unknown) {
  return a != null && b != null && String(a) === String(b);
}

function sameCall(a: CurrentCall | null, b: CurrentCall) {
  if (!a) return false;
  if (a === b) return true;
  if (a.event_id || b.event_id) return sameId(a.event_id, b.event_id);
  return sameId(a.queue_id, b.queue_id) && sameId(a.queue_entry_id, b.queue_entry_id);
}

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
}: DisplayBoardUnifiedProps) {void
  useTheme();
  const { t: rawT, i18n } = useTranslation();
  const t = rawT;

  // Параметры из URL или пропсов
  // PR #1910 bugfix: department destructured as departmentProp, но использовался
  // как department — ReferenceError. Возвращаем корректное имя.
  // DISPLAYDEPT-FE-001 (audit PR #3961): публичный роут /display-board не
  // имеет department-пропа — литеральная строка "undefined" больше не
  // уходит в REST-статистику как ключ отдела; без валидного отдела
  // статистика подавляется (backend stats_available=false).
  const department = (() => {
    const raw = typeof departmentProp === 'string' ? departmentProp.trim() : '';
    if (!raw || raw.toLowerCase() === 'undefined' || raw.toLowerCase() === 'null') {
      return undefined;
    }
    return raw;
  })();
  const qs = useMemo(
    () => ({ department, d: String(dateStr).trim() }),
    [department, dateStr]
  );

  // Состояние очереди (новое)
  const [connected, setConnected] = useState(false);
  // QR-FE-009: была ли WS-сессия хотя бы раз успешной. Отличает
  // «борд ещё подключается» (баннер не нужен) от устойчивой потери
  // соединения после успешной сессии (строки могут устареть).
  const [hasSnapshot, setHasSnapshot] = useState(false);
  const [snapshotReady, setSnapshotReady] = useState(false);
  const [callStateAvailable, setCallStateAvailable] = useState(true);
  const [queueData, setQueueData] = useState<QueueEntryDto[]>([]);
  const [currentCall, setCurrentCall] = useState<CurrentCall | null>(null);
  const [displayTest, setDisplayTest] = useState<DisplayTest | null>(null);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);

  // Состояние статистики (старое)
  const [stats, setStats] = useState<BoardStats | null>(null);
  const [err, setErr] = useState('');
  const [nowStr, setNowStr] = useState(timeNow());

  // Состояние табло (старое)
  const [board, setBoard] = useState<BoardState>({
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
  const [windows, setWindows] = useState<WindowItem[]>([]);

  // Настройки (объединенные)
  // DISPLAYAUDIO-FE-001 (audit PR #3961): явный soundInitial=false
  // применяется на первом рендере — дефолт true только когда проп
  // не задан.
  const [boardSettings, setBoardSettings] = useState<BoardSettingsState>({
    theme: 'light',
    showPatientNames: 'initials',
    soundEnabled: soundInitial === undefined ? true : soundInitial,
    displayCount: 5,
    showAnnouncements: true,
    contrastMode: contrast,
    kioskMode: kiosk,
    fontScale: fontScale,
    language: lang
  });

  // Рефы
  const wsRef = useRef<(() => void) | null>(null);
  const legacyWindowsLookupWarnedRef = useRef(false);
  const loadBoardStateRef = useRef<() => void>(() => {});
  const loadWindowsRef = useRef<() => void>(() => {});
  const connectWebSocketRef = useRef<() => void>(() => {});
  const stateRequestRef = useRef(0);
  const invalidateBoardStateRequests = useCallback(() => { stateRequestRef.current++; }, []);
  const snapshotReadyRef = useRef(false);
  const currentCallRef = useRef<CurrentCall | null>(null);
  const liveAudioCallRef = useRef<CurrentCall | null>(null);
  const pendingLiveAudioRef = useRef<CurrentCall | null>(null);
  const latestCallOrderRef = useRef('');
  const displayTestRef = useRef<DisplayTest | null>(null);
  const audioProfileRef = useRef<BoardAudioProfile | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioSequenceRef = useRef(0);
  const activeToneRef = useRef<OscillatorNode | null>(null);
  const activeSpeechRef = useRef<SpeechSynthesisUtterance | null>(null);
  const showAnnouncementsRef = useRef(true);
  const [online, setOnline] = useState(true);

  // DISPLAYAUDIO-FE-001 (audit PR #3961): сессионное ручное решение звука.
  // Пока оператор не трогал кнопку мьюта, применяется бэкенд-дефолт;
  // после ручного мьюта/включения опрос НЕ перезатирает выбор.
  const soundOverrideRef = useRef<boolean | null>(
    soundInitial === undefined ? null : soundInitial
  );
  // DISPLAYCALL-FE-001 (audit PR #3961): таймер истечения подсветки вызова
  // (display_duration секунд из payload, бэкенд-владелец решения).
  const callExpiryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clearCallExpiry = () => {
    if (callExpiryRef.current !== null) {
      clearTimeout(callExpiryRef.current);
      callExpiryRef.current = null;
    }
  };
  // DISPLAYANNOUNCE-FE-001 (audit PR #3961): независимые таймеры
  // истечения объявлений (display_duration секунд каждое).
  const announceTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const clearAnnounceTimers = () => {
    announceTimersRef.current.forEach((timer) => clearTimeout(timer));
    announceTimersRef.current.clear();
  };
  // DISPLAYERROR-FE-001 (audit PR #3961): ошибка снапшота initial_state —
  // честный видимый баннер вместо маскировки под пустую живую очередь;
  // последние корректные строки сохраняются (не затираются пустым payload).
  const [snapshotError, setSnapshotError] = useState('');

  // Получаем board_id из URL или используем переданный
  const currentBoardId = new URLSearchParams(window.location.search).get('board') || boardId;
  const isBoardView = window.location.pathname.startsWith('/queue-board') || window.location.pathname.startsWith('/display-board');
  const [displayDeviceState, setDisplayDeviceState] = useState<'ready' | 'connecting' | 'unconfigured'>(() => {
    if (!isBoardView || tokenManager.getAccessToken()) return 'ready';
    return 'connecting';
  });
  const [setupDeviceId, setSetupDeviceId] = useState('');
  const [setupDeviceSecret, setSetupDeviceSecret] = useState('');
  const [setupError, setSetupError] = useState('');
  const [setupSubmitting, setSetupSubmitting] = useState(false);

  // /board/state is a stats/settings snapshot; live rows/calls/announcements come from WebSocket initial_state.
  // DISPLAYDEPT-FE-001: department уходит в params только когда валиден —
  // литеральный "undefined" не отправляется; DISPLAYCONFIG-FE-001:
  // снапшот настроек запрашивается для ТЕКУЩЕГО табло (board=...).
  async function loadBoardState() {
    const requestId = ++stateRequestRef.current;
    const cacheKey = 'board.state:' + JSON.stringify([currentBoardId, qs.department, qs.d]);
    try {
      const { data } = await api.get('/board/state', {
        params: { date: qs.d, ...(qs.department ? { department: qs.department } : {}), board: currentBoardId },
      });
      if (requestId !== stateRequestRef.current) return;
      const state = data as Record<string, unknown> | null;
      if (!state || typeof state !== 'object') throw new Error('Missing display state');

      const presentation = boardPresentation(state);
      const voiceLanguage = state.voice_language === 'uz' || state.voice_language === 'en'
        ? state.voice_language
        : 'ru';
      const volume = typeof state.volume_level === 'number' && Number.isFinite(state.volume_level)
        ? Math.max(0, Math.min(100, state.volume_level)) / 100
        : 0.7;
      const previousAudio = audioProfileRef.current;
      let voiceReady = previousAudio?.voiceLanguage === voiceLanguage ? previousAudio.voiceReady : undefined;
      const locale = voiceLocale(voiceLanguage);
      if (state.voice_announcements === true && !i18n.hasResourceBundle(locale, 'translation') && !voiceReady) {
        // A failed i18next load remains marked as failed; reloadResources is
        // required to retry it after connectivity returns.
        const pending = i18n.reloadResources([locale], ['translation']).then(() => {}, () => {});
        voiceReady = pending;
        void pending.then(() => {
          if (audioProfileRef.current?.voiceReady === pending) {
            audioProfileRef.current.voiceReady = undefined;
          }
        });
      }
      audioProfileRef.current = {
        enabled: presentation.sound_default,
        voiceEnabled: state.voice_announcements === true,
        voiceLanguage,
        volume,
        voiceReady,
      };
      playPendingLiveCall();
      showAnnouncementsRef.current = state.show_announcements !== false;
      const soundEnabled = presentation.sound_default && volume > 0 && soundOverrideRef.current !== false;
      if (!soundEnabled) stopBoardAudio();
      const nameFormat = state.show_patient_names;
      setBoardSettings((prev) => ({
        ...prev,
        soundEnabled,
        showPatientNames: nameFormat === 'none' || nameFormat === 'initials' || nameFormat === 'full'
          ? nameFormat : prev.showPatientNames,
        displayCount: typeof state.queue_display_count === 'number' && state.queue_display_count >= 1
          ? Math.min(Math.floor(state.queue_display_count), 20) : prev.displayCount,
        showAnnouncements: showAnnouncementsRef.current,
      }));
      setBoard(presentation);
      setStats(state.stats_available === true ? extractBoardStats(state) : null);
      setErr('');
      try {
        // eslint-disable-next-line no-restricted-properties -- Non-auth display preferences only.
        localStorage.setItem(cacheKey, JSON.stringify(presentation));
      } catch {
        // The live profile is available even when browser storage is disabled.
      }
    } catch {
      if (requestId !== stateRequestRef.current) return;
      setStats(null);
      setErr(t('misc.dbu_err_load'));
      try {
        const raw = localStorage.getItem(cacheKey);
        if (raw) {
          const cached = safeJsonParse(raw);
          if (cached && typeof cached === 'object') setBoard(boardPresentation(cached as Record<string, unknown>));
        }
      } catch {
        // The last live presentation remains on screen.
      }
    }
  }

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
      snapshotReadyRef.current = false;
      setSnapshotReady(false);
      setConnected(false);
      showCall(null);
      dismissTest();
      stopBoardAudio();
      // Закрываем предыдущее соединение если есть
      if (wsRef.current) {
        wsRef.current();
        wsRef.current = null;
      }

      const staffToken = tokenManager.getAccessToken();
      const needsDeviceSession = !staffToken && isBoardView;
      if (needsDeviceSession) setDisplayDeviceState('connecting');
      const tokenProvider = needsDeviceSession
        ? async () => {
            // Staff access always takes precedence, including on reconnect
            // after a staff session is established in this browser.
            const currentStaffToken = tokenManager.getAccessToken();
            if (currentStaffToken) return currentStaffToken;
            try {
              const deviceToken = await exchangeDisplayDeviceSession(currentBoardId);
              setDisplayDeviceState('ready');
              setSetupError('');
              return deviceToken;
            } catch (error) {
              if (error instanceof DisplayDeviceProvisioningRequiredError) {
                setDisplayDeviceState('unconfigured');
                setSetupError('Табло не настроено или доступ отозван. Введите выданный администратором код.');
              }
              throw error;
            }
          }
        : undefined;

      // Создаем новое соединение
      const closeWS = openDisplayBoardWS(
        currentBoardId,
        handleWebSocketMessage,
        () => setConnected(true),
        () => {
          setConnected(false);
          snapshotReadyRef.current = false;
          setSnapshotReady(false);
          showCall(null);
          dismissTest();
          stopBoardAudio();
        },
        tokenProvider,
      );

      wsRef.current = closeWS;

    } catch (error) {
      logger.error('Ошибка создания WebSocket:', error);
      setConnected(false);
    }
  };

  const submitDeviceProvisioning = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const deviceId = Number(setupDeviceId.trim());
    const secret = setupDeviceSecret.trim();
    if (!Number.isSafeInteger(deviceId) || deviceId <= 0 || secret.length < 32 || secret.length > 128) {
      setSetupError('Введите корректный ID устройства и выданный администратором код.');
      return;
    }

    setSetupSubmitting(true);
    setSetupError('');
    try {
      // The server replaces the one-time code with an HttpOnly, board-scoped
      // session cookie; the reusable secret is never persisted by the page.
      await exchangeDisplayDeviceCredential(deviceId, secret, currentBoardId);
      setSetupDeviceSecret('');
      setDisplayDeviceState('connecting');
      connectWebSocketRef.current();
    } catch {
      setSetupError('Не удалось подтвердить устройство. Проверьте данные или обратитесь к администратору.');
      setDisplayDeviceState('unconfigured');
    } finally {
      setSetupSubmitting(false);
    }
  };

  function showCall(call: CurrentCall | null, deadline?: number) {
    clearCallExpiry();
    const pending = pendingLiveAudioRef.current;
    if (!call || (pending && !sameCall(call, pending))) {
      pendingLiveAudioRef.current = null;
    }
    const live = liveAudioCallRef.current;
    if (!call || (live && !sameCall(call, live))) liveAudioCallRef.current = null;
    currentCallRef.current = call;
    setCurrentCall(call);
    if (call && deadline !== undefined && deadline > Date.now()) {
      callExpiryRef.current = setTimeout(() => {
        showCall(null);
        stopBoardAudio();
      }, deadline - Date.now());
    }
  }

  function dismissTest() {
    displayTestRef.current = null;
    setDisplayTest(null);
  }

  function playPendingLiveCall() {
    const pending = pendingLiveAudioRef.current;
    if (!pending || !snapshotReadyRef.current || !audioProfileRef.current) return;
    if (!sameCall(currentCallRef.current, pending)) {
      pendingLiveAudioRef.current = null;
      return;
    }
    pendingLiveAudioRef.current = null;
    void playBoardAudio((voiceLanguage) => {
      const current = currentCallRef.current;
      return callText(current && sameCall(current, pending) ? current : pending, voiceLanguage);
    });
  }

  const handleWebSocketMessage = (messageRaw: unknown, replyToTest?: DisplayTestReply) => {
    if (!messageRaw || typeof messageRaw !== 'object') return;
    const message = messageRaw as WSMessage;
    const data = message.data ?? {};

    switch (message.type) {
      case 'initial_state': {
        const snapshotError = typeof data.error === 'string' ? data.error.trim() : '';
        if (snapshotError || !Array.isArray(data.queue_entries)) {
          snapshotReadyRef.current = false;
          setSnapshotReady(false);
          setSnapshotError(snapshotError || t('misc.dbu_err_load'));
          dismissTest();
          stopBoardAudio();
          break;
        }
        const call = data.current_call;
        const deadline = call ? eventDeadline(call.expires_at, 30) : Number.NaN;
        const displayed = currentCallRef.current;
        // A live invitation may arrive while the server is making the snapshot.
        if (!displayed?.issued_at || typeof data.last_update !== 'string' || displayed.issued_at <= data.last_update) {
          showCall(call && deadline > Date.now() ? call : null, deadline);
        }
        if (call?.issued_at && call.event_id) {
          const order = call.issued_at + '|' + call.event_id;
          if (order > latestCallOrderRef.current) latestCallOrderRef.current = order;
        }
        setCallStateAvailable(data.call_state_available !== false);
        setSnapshotError('');
        setHasSnapshot(true);
        snapshotReadyRef.current = true;
        setSnapshotReady(true);
        playPendingLiveCall();
        setQueueData(data.queue_entries);
        clearAnnounceTimers();
        setAnnouncements(Array.isArray(data.announcements) ? data.announcements : []);
        break;
      }

      case 'patient_call': {
        if (typeof data.queue_number !== 'number' && typeof data.queue_number !== 'string') break;
        const deadline = eventDeadline(data.expires_at, Number(message.display_duration ?? data.display_duration ?? 30));
        if (!(deadline > Date.now())) break;
        if (data.issued_at && data.event_id) {
          const order = data.issued_at + '|' + data.event_id;
          if (order <= latestCallOrderRef.current) break;
          latestCallOrderRef.current = order;
        }
        if (displayTestRef.current) {
          displayTestRef.current.reply({ test_id: displayTestRef.current.id, status: 'busy' });
          dismissTest();
        }
        stopBoardAudio();
        showCall(data, deadline);
        liveAudioCallRef.current = data;
        setCallStateAvailable(true);
        pendingLiveAudioRef.current = data;
        playPendingLiveCall();
        break;
      }

      case 'call_completed': {
        const call = currentCallRef.current;
        if (call && sameId(call.queue_id, data.queue_id) && sameId(call.queue_entry_id, data.queue_entry_id ?? data.id)) {
          showCall(null);
          stopBoardAudio();
        }
        break;
      }

      case 'display_test': {
        const id = data.test_id;
        const deadline = eventDeadline(data.expires_at);
        if (!replyToTest || typeof id !== 'string' || !(deadline > Date.now()) || !snapshotReadyRef.current) break;
        if (currentCallRef.current || displayTestRef.current) {
          replyToTest({ test_id: id, status: 'busy' });
          break;
        }
        const test = {
          id,
          call: data.test_type === 'call' ? data : null,
          expiresAt: deadline,
          reply: replyToTest,
        };
        displayTestRef.current = test;
        setDisplayTest(test);
        break;
      }

      case 'queue_update': {
        // Обновляем очередь при добавлении/изменении записей
        if (message.event_type === 'queue.created') {
          // Добавляем новую запись в очередь
          const newEntry: QueueEntryDto = {
            id: typeof data.queue_entry_id === 'number' || typeof data.queue_entry_id === 'string'
              ? data.queue_entry_id
              : undefined,
            queue_id: typeof data.queue_id === 'number' || typeof data.queue_id === 'string'
              ? data.queue_id
              : undefined,
            number: Number(data.number ?? 0),
            patient_name: typeof data.patient_name === 'string' ? data.patient_name : undefined,
            status: typeof data.status === 'string' ? data.status : '',
            called_at: typeof data.called_at === 'string' ? data.called_at : undefined,
            created_at: typeof data.created_at === 'string' ? data.created_at : undefined,
            source: typeof data.source === 'string' ? data.source : undefined,
            doctor_name: data.doctor_name,
            specialty: typeof data.specialty === 'string' ? data.specialty : undefined,
            cabinet: data.cabinet ?? undefined,
          };
          setQueueData((prev) => prev.some((entry) => sameId(entry.id, newEntry.id))
            ? prev : [...prev, newEntry]);
        } else {
          // Обновляем очередь; RQ-24.a.2: владелец/кабинет приходят
          // на уровне сообщения очереди — прикрепляем к строкам, чтобы
          // одинаковые номера разных очередей были различимы на борде.
          const queueDoctor = typeof data.doctor_name === 'string' ? data.doctor_name : undefined;
          const queueSpecialty = typeof data.specialty === 'string' ? data.specialty : undefined;
          const queueCabinet = typeof data.cabinet === 'string' ? data.cabinet : undefined;
          // QR-FE-008: событие несёт backend-owned scope (queue_id) — payload
          // описывает ровно ОДНУ дневную очередь. Вливаем по queue_id:
          // заменяем только строки этой очереди, строки других очередей того
          // же борда сохраняются. Владельца не угадываем по номеру/специальности.
          const eventQueueId = typeof data.queue_id === 'number' || typeof data.queue_id === 'string'
            ? data.queue_id
            : undefined;
          // Read-model доски зеркалит контракт initial_state: видимы только
          // waiting/called (бэкенд _send_current_state фильтрует так же),
          // поэтому completed/cancelled/no-show строки из per-queue сабсета
          // на борд не возвращаются.
          const rawEntries = Array.isArray(data.queue_entries) ? data.queue_entries : [];
          const scopedEntries = rawEntries
            .filter((entry) => entry.status === 'waiting' || entry.status === 'called')
            .map((entry) => ({
              ...entry,
              queue_id: entry.queue_id ?? eventQueueId,
              doctor_name: entry.doctor_name ?? queueDoctor,
              specialty: entry.specialty ?? queueSpecialty,
              cabinet: entry.cabinet === null ? undefined : entry.cabinet ?? queueCabinet,
            }));
          const call = currentCallRef.current;
          const matchingEntry = call && rawEntries.find((entry) =>
            sameId(entry.queue_id ?? eventQueueId, call.queue_id) &&
            sameId(entry.id, call.queue_entry_id));
          if (call && matchingEntry) {
            if (matchingEntry.status !== 'called') {
              showCall(null);
              stopBoardAudio();
            } else {
              // A null resource-room means the update cannot determine the
              // station. Keep the room from this exact live invitation.
              const cabinet = matchingEntry.cabinet === null
                ? call.cabinet
                : matchingEntry.cabinet ?? queueCabinet ?? call.cabinet;
              const updatedCall = { ...call, cabinet };
              currentCallRef.current = updatedCall;
              setCurrentCall(updatedCall);
              // Correct a live invitation if its destination changes, but do
              // not replay an invitation restored silently on reconnect.
              if ((cabinet ?? '') !== (call.cabinet ?? '') && sameCall(liveAudioCallRef.current, call)) {
                liveAudioCallRef.current = updatedCall;
                stopBoardAudio();
                pendingLiveAudioRef.current = updatedCall;
                playPendingLiveCall();
              }
            }
          }
          setQueueData((prev) => {
            if (eventQueueId === undefined) {
              // Защита от дрифта контракта (старый бэкенд без queue_id):
              // прежнее поведение — полная замена. Владение очередью по
              // номеру/метке специализации не восстанавливаем.
              return scopedEntries;
            }
            const kept = prev.filter((entry) => !sameId(entry.queue_id, eventQueueId));
            // Стабильный порядок ТВ-раскладки: группировка по очереди,
            // внутри — по номеру (стабильный sort сохраняет порядок остальных).
            const merged = [...kept, ...scopedEntries];
            merged.sort((a, b) => {
              const qa = a.queue_id === undefined || a.queue_id === null ? '' : String(a.queue_id);
              const qb = b.queue_id === undefined || b.queue_id === null ? '' : String(b.queue_id);
              if (qa !== qb) return qa.localeCompare(qb);
              return Number(a.number ?? 0) - Number(b.number ?? 0);
            });
            return merged;
          });
        }
        break;
      }

      case 'announcement': {
        const duration = Number(message.display_duration ?? data.display_duration ?? 0);
        const deadline = eventDeadline(data.expires_at, duration);
        if (Number.isFinite(deadline) && deadline <= Date.now()) break;
        const announcementKey = data.created_at ?? Date.now().toString();
        const newAnnouncement: Announcement = {
          created_at: announcementKey,
          announcement_type: data.announcement_type,
          text: typeof data.text === 'string' ? data.text : undefined,
          expires_at: Number.isFinite(deadline) ? deadline : undefined,
        };
        const previous = announceTimersRef.current.get(announcementKey);
        if (previous !== undefined) clearTimeout(previous);
        setAnnouncements((items) => [
          newAnnouncement, ...items.filter((item) => item.created_at !== announcementKey).slice(0, 4),
        ]);
        if (Number.isFinite(deadline)) {
          const timer = setTimeout(() => {
            setAnnouncements((items) => items.filter((item) => item !== newAnnouncement));
            announceTimersRef.current.delete(announcementKey);
          }, deadline - Date.now());
          announceTimersRef.current.set(announcementKey, timer);
        }
        if (snapshotReadyRef.current && showAnnouncementsRef.current && !currentCallRef.current &&
            !displayTestRef.current && message.sound_enabled !== false) {
          stopBoardAudio();
          const voice = message.voice_text;
          void playBoardAudio(voice ? () => voice : undefined);
        }
        break;
      }

      case 'announcement_removed':
        setAnnouncements((prev) => prev.filter((a) => a.created_at !== message.data?.created_at));
        break;

      default:
        logger.log('Неизвестный тип сообщения:', message.type);
    }
  };

  function stopBoardAudio() {
    audioSequenceRef.current++;
    const tone = activeToneRef.current;
    if (tone) {
      activeToneRef.current = null;
      try {
        tone.stop();
      } catch {
        // The oscillator may already have stopped.
      }
    }
    if (activeSpeechRef.current) {
      activeSpeechRef.current = null;
      window.speechSynthesis?.cancel();
    }
  }

  function callText(call: CurrentCall, voiceLanguage: VoiceLanguage) {
    return t(call.cabinet ? 'misc.dbu_voice_patient_call' : 'misc.dbu_voice_call_no_cabinet', {
      lng: voiceLocale(voiceLanguage), number: call.queue_number, cabinet: call.cabinet,
    });
  }

  async function playBoardAudio(text?: (language: VoiceLanguage) => string): Promise<DisplayTestAudioStatus> {
    const profile = audioProfileRef.current;
    if (!profile) return 'unavailable';
    if (!profile.enabled || soundOverrideRef.current === false || profile.volume === 0) return 'disabled';
    const sequence = audioSequenceRef.current;
    let signal: DisplayTestAudioStatus = 'unavailable';

    try {
      const AudioContextClass = window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (AudioContextClass) {
        const context = audioContextRef.current ?? new AudioContextClass();
        audioContextRef.current = context;
        if (context.state !== 'running') {
          signal = 'blocked';
        } else {
          const oscillator = context.createOscillator();
          const gain = context.createGain();
          const start = context.currentTime;
          oscillator.connect(gain);
          gain.connect(context.destination);
          oscillator.frequency.setValueAtTime(800, start);
          oscillator.frequency.setValueAtTime(1000, start + 0.11);
          gain.gain.setValueAtTime(0, start);
          gain.gain.linearRampToValueAtTime(profile.volume * 0.3, start + 0.03);
          gain.gain.linearRampToValueAtTime(0, start + 0.22);
          activeToneRef.current = oscillator;
          oscillator.onended = () => {
            oscillator.disconnect();
            gain.disconnect();
            if (activeToneRef.current === oscillator) activeToneRef.current = null;
          };
          oscillator.start(start);
          oscillator.stop(start + 0.23);
          signal = 'started';
        }
      }
    } catch {
      signal = 'unavailable';
    }

    if (!text || !profile.voiceEnabled) return signal;
    const synth = window.speechSynthesis;
    if (!synth || !window.SpeechSynthesisUtterance) return 'unavailable';
    const voice = synth.getVoices().find((candidate) => candidate.lang.split(/[-_]/)[0].toLowerCase() === profile.voiceLanguage);
    if (!voice) return 'unavailable';
    const locale = voiceLocale(profile.voiceLanguage);
    if (!i18n.hasResourceBundle(locale, 'translation')) {
      await profile.voiceReady;
      if (!i18n.hasResourceBundle(locale, 'translation')) return 'unavailable';
    }
    if (signal === 'started') await new Promise((resolve) => setTimeout(resolve, 250));
    if (sequence !== audioSequenceRef.current) return 'unavailable';

    return new Promise((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text(profile.voiceLanguage));
      utterance.voice = voice;
      utterance.lang = voice.lang;
      utterance.rate = 0.9;
      utterance.volume = profile.volume;
      activeSpeechRef.current = utterance;
      const finish = (result: DisplayTestAudioStatus) => {
        clearTimeout(timeout);
        resolve(result);
      };
      const timeout = setTimeout(() => {
        if (activeSpeechRef.current === utterance) {
          activeSpeechRef.current = null;
          synth.cancel();
        }
        finish('unavailable');
      }, 1000);
      utterance.onstart = () => finish('started');
      utterance.onend = () => {
        if (activeSpeechRef.current === utterance) activeSpeechRef.current = null;
        finish('started');
      };
      utterance.onerror = (event) => {
        if (activeSpeechRef.current === utterance) activeSpeechRef.current = null;
        finish(event.error === 'not-allowed' ? 'blocked' : 'unavailable');
      };
      try {
        synth.speak(utterance);
      } catch {
        if (activeSpeechRef.current === utterance) activeSpeechRef.current = null;
        finish('unavailable');
      }
    });
  }

  loadBoardStateRef.current = loadBoardState;
  loadWindowsRef.current = loadWindows;
  connectWebSocketRef.current = connectWebSocket;

  const liveData = online && connected && snapshotReady;
  const liveCall = liveData ? currentCall : null;
  const playTestAudioRef = useRef<(test: DisplayTest) => Promise<DisplayTestAudioStatus>>(async () => 'unavailable');
  playTestAudioRef.current = (test) => {
    stopBoardAudio();
    const call = test.call;
    return playBoardAudio(call
      ? (language) => callText(call, language)
      : (language) => t('misc.dbu_test_announcement', { lng: voiceLocale(language) }));
  };

  useEffect(() => {
    if (!displayTest || !liveData) return;
    let audioDeadline: ReturnType<typeof setTimeout> | undefined;
    const frame = requestAnimationFrame(() => {
      if (document.hidden || displayTest.expiresAt <= Date.now()) return;
      const timeout = new Promise<DisplayTestAudioStatus>((resolve) => {
        audioDeadline = setTimeout(() => resolve('unavailable'), 1500);
      });
      const audio = playTestAudioRef.current(displayTest).catch((): DisplayTestAudioStatus => 'unavailable');
      void Promise.race([audio, timeout]).then((audioStatus) => {
        clearTimeout(audioDeadline);
        if (document.hidden) return;
        if (displayTestRef.current === displayTest && displayTest.expiresAt > Date.now()) {
          displayTest.reply({
            test_id: displayTest.id, status: 'displayed', audio_status: audioStatus,
          });
        }
      });
    });
    const expiration = setTimeout(() => {
      if (displayTestRef.current === displayTest) {
        displayTestRef.current = null;
        setDisplayTest(null);
        stopBoardAudio();
      }
    }, Math.max(0, displayTest.expiresAt - Date.now()));
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(expiration);
      clearTimeout(audioDeadline);
    };
  }, [displayTest, liveData]);

  // Инициализация
  useEffect(() => {
    setHasSnapshot(false);
    setQueueData([]);
    setStats(null);
    setAnnouncements([]);
    setSnapshotError('');
    latestCallOrderRef.current = '';
    audioProfileRef.current = null;
    window.speechSynthesis?.getVoices();
    const params = new URLSearchParams(window.location.search);
    const forgetDeviceRequested = params.get('forget-device') === '1';
    const hasStaffToken = Boolean(tokenManager.getAccessToken());
    if (forgetDeviceRequested) {
      if (!hasStaffToken) {
        setDisplayDeviceState('unconfigured');
        setSetupDeviceId('');
        setSetupDeviceSecret('');
        setSetupSubmitting(true);
      }
      void forgetDisplayDeviceSession(currentBoardId).then(() => {
        params.delete('forget-device');
        const query = params.toString();
        window.history.replaceState(
          null,
          '',
          `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`,
        );
        setSetupError('');
      }).catch(() => {
        if (!hasStaffToken) {
          setSetupError('Не удалось удалить данные табло. Проверьте соединение и повторите попытку.');
        }
      }).finally(() => {
        if (!hasStaffToken) setSetupSubmitting(false);
      });
    }
    loadBoardStateRef.current();
    loadWindowsRef.current();
    if (!forgetDeviceRequested || hasStaffToken) connectWebSocketRef.current();

    const clock = setInterval(() => setNowStr(timeNow()), 1000);

    // QR-FE-009: polling здесь обновляет ТОЛЬКО снапшот статистики/настроек
    // (/board/state) — по бэкенд-контракту (backend/app/api/v1/endpoints/
    // board.py) этот эндпоинт не несёт живых строк очереди (только
    // агрегаты и настройки приватности). Строки/вызовы/объявления
    // восстанавливаются исключительно через WebSocket (initial_state при
    // каждом реконнекте). Пока WS лежит после успешной сессии, борд
    // показывает заметный stale-баннер вместо молчаливой претензии на
    // живые данные.
    //
    // H-7 (Launch Blockers Audit): polling fallback MUST run in
    // board view too. Previously the condition `isBoardView ? null`
    // disabled polling entirely when the page ran on a TV/kiosk at
    // /queue-board or /display-board. Now polling runs unconditionally:
    //   - In admin/preview view: 15s / 5s (unchanged).
    //   - In board view: 30s / 10s (slower to avoid hammering the
    //     server from many kiosks).
    const boardStateIntervalMs = isBoardView
      ? Math.max(30000, Number(refreshMs || 0))
      : Math.max(15000, Number(refreshMs || 0));
    const windowsIntervalMs = isBoardView
      ? Math.max(10000, Number(refreshMs || 0))
      : Math.max(5000, Number(refreshMs || 0));

    const tb = setInterval(() => loadBoardStateRef.current(), boardStateIntervalMs);
    const tw = setInterval(() => loadWindowsRef.current(), windowsIntervalMs);

    return () => {
      invalidateBoardStateRequests();
      if (tb) clearInterval(tb);
      if (tw) clearInterval(tw);
      clearInterval(clock);
      clearCallExpiry();
      clearAnnounceTimers();
      stopBoardAudio();
      const context = audioContextRef.current;
      audioContextRef.current = null;
      if (context) void context.close().catch(() => {});
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
  }, [isBoardView, qs.department, qs.d, refreshMs, currentBoardId, invalidateBoardStateRequests]);

  // Online/offline (старое)
  useEffect(() => {
    const on = () => {
      setOnline(true);
      connectWebSocketRef.current();
    };
    const off = () => {
      setOnline(false);
      snapshotReadyRef.current = false;
      setSnapshotReady(false);
      stopBoardAudio();
    };
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
  // DISPLAYAUDIO-FE-001: ручное решение живёт в ref — опрос /board/state
  // больше не перезатирает мьют оператора бэкенд-дефолтом.
  const toggleSound = () => {
    const profile = audioProfileRef.current;
    if (!profile?.enabled || profile.volume === 0) return;
    const context = audioContextRef.current;
    if (context?.state === 'suspended' && boardSettings.soundEnabled) {
      void context.resume().catch(() => {});
      return;
    }
    const enabled = !boardSettings.soundEnabled;
    soundOverrideRef.current = enabled;
    if (enabled && context) void context.resume().catch(() => {});
    if (!enabled) stopBoardAudio();
    setBoardSettings((prev) => ({ ...prev, soundEnabled: enabled }));
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
  const getAnnouncement = (boardState: BoardState, langCode: string) => {
    if (langCode === 'ru') return boardState.announcement_ru || boardState.announcement || '';
    if (langCode === 'uz') return boardState.announcement_uz || boardState.announcement || '';
    if (langCode === 'en') return boardState.announcement_en || boardState.announcement || '';
    return boardState.announcement || '';
  };

  // Получение следующего номера (старое)








  // Получение цвета статуса (новое) — цвета теперь декларированы в displayboard.css
  // через [data-status="..."] селекторы на .displayboard-queue-card. Эта обертка
  // оставлена для возможных будущих потребителей и тестов.

  // Получение текста статуса (новое)
  const getStatusText = (status: string) => {
    const texts = {
      'waiting': t('misc.dbu_status_waiting'),
      'called': t('misc.dbu_status_called'),
      'serving': t('misc.dbu_status_serving'),
      'completed': t('misc.dbu_status_completed'),
      'cancelled': t('misc.dbu_status_cancelled')
    };
    return texts[status as keyof typeof texts] || status;
  };

  // Форматирование времени (новое)
  const formatTime = (dateString?: string) => {
    if (!dateString) return '';
    return formatRegistrarTime(dateString);
  };

  // Темы оформления (новое)
  // CC-4 (UI color-contrast track): board themes are SELF-CONTAINED constant
  // palettes. The previous light/medical entries mixed constant dark ink
  // (#1a202c) with app-theme-resolving tokens (var(--mac-bg-primary) etc.) —
  // under a dark app the card surfaces resolved dark while the ink stayed
  // dark → 1.04:1, invisible (axe color-contrast, e2e/a11y-baseline.json,
  // display-board:dark). The constants below are exactly the values the
  // tokens resolved to in the light app, so the light-app rendering is
  // pixel-identical; the board no longer depends on the viewer's app theme
  // (it is a stable TV/waiting-room surface). boardSettings.theme is never
  // overridden from the API (only sound_default is), so 'light' remains the
  // de-facto board theme; 'dark'/'medical' keep their self-contained palettes.
  const themes = {
    light: {
      background: 'var(--displayboard-light-bg)',
      cardBg: 'var(--displayboard-light-card)',
      textPrimary: 'var(--displayboard-light-ink)',
      textSecondary: 'var(--displayboard-light-ink-muted)',
      border: 'var(--displayboard-light-border)'
    },
    dark: {
      background: 'var(--displayboard-dark-bg)',
      cardBg: 'var(--displayboard-dark-card)',
      textPrimary: 'var(--displayboard-dark-ink)',
      textSecondary: 'var(--displayboard-dark-ink-muted)',
      border: 'var(--displayboard-dark-border)'
    },
    medical: {
      background: 'var(--displayboard-medical-bg)',
      cardBg: 'var(--displayboard-medical-card)',
      textPrimary: 'var(--displayboard-medical-ink)',
      textSecondary: 'var(--displayboard-medical-ink-muted)',
      border: 'var(--displayboard-medical-border)'
    }
  };

  const currentTheme = themes[boardSettings.theme as keyof typeof themes] || themes.light;

  // Стили (объединенные) — см. displayboard.css. Тема инжектируется как
  // CSS custom properties на корневом контейнере, чтобы классы могли ссылаться
  // на var(--board-*). Контраст/киоск переключаются модификаторами класса.

  const rootClassName = [
    'displayboard-root',
    boardSettings.contrastMode ? 'displayboard-root--contrast' : '',
    boardSettings.kioskMode ? 'displayboard-root--kiosk' : ''
  ].filter(Boolean).join(' ');

  const rootCssVars: CSSProperties = {
    '--board-bg': board.bg_color || currentTheme.background,
    '--board-text-primary': board.text_color || currentTheme.textPrimary,
    '--board-text-secondary': currentTheme.textSecondary,
    '--board-card-bg': currentTheme.cardBg,
    '--board-border': currentTheme.border,
    '--board-font-scale': String(boardSettings.fontScale)
  } as CSSProperties;

  if (isBoardView && displayDeviceState === 'unconfigured') {
    return (
      <main
        data-testid="display-device-provisioning"
        className="display-device-provisioning"
      >
        <section className="display-device-provisioning__card">
          <h1 className="display-device-provisioning__title">Табло не настроено</h1>
          <p>Попросите администратора выдать ID устройства и код для этого табло.</p>
          <form onSubmit={submitDeviceProvisioning}>
            <label className="display-device-provisioning__label" htmlFor="display-device-id">ID устройства</label>
            <input
              className="display-device-provisioning__input"
              id="display-device-id"
              aria-label="ID устройства"
              inputMode="numeric"
              autoComplete="off"
              value={setupDeviceId}
              onChange={(event) => setSetupDeviceId(event.target.value)}
              required
            />
            <label className="display-device-provisioning__label" htmlFor="display-device-secret">Код устройства</label>
            <input
              className="display-device-provisioning__input"
              id="display-device-secret"
              aria-label="Код устройства"
              type="password"
              autoComplete="new-password"
              value={setupDeviceSecret}
              onChange={(event) => setSetupDeviceSecret(event.target.value)}
              required
            />
            {setupError && <p className="display-device-provisioning__error" role="alert">{setupError}</p>}
            <button className="display-device-provisioning__submit" type="submit" disabled={setupSubmitting}>
              {setupSubmitting ? 'Проверка…' : 'Подключить табло'}
            </button>
          </form>
        </section>
      </main>
    );
  }

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
            {liveData ? <Wifi size={20} color="var(--mac-success)" /> : <WifiOff size={20} color="var(--mac-error)" />}
            <span className="displayboard-conn-status">
              {liveData ? t('misc.dbu_conn_connected') :
                connected ? t('misc.dbu_awaiting_data') : t('misc.dbu_conn_disconnected')}
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
              title={t('misc.dbu_title_fullscreen')}
              aria-label={document.fullscreenElement ? t('misc.dbu_aria_exit_fullscreen') : t('misc.dbu_aria_enter_fullscreen')}>
              
              {document.fullscreenElement ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            </button>

            <button
              onClick={toggleSound}
              className="displayboard-btn"
              title={boardSettings.soundEnabled ? t('misc.dbu_title_sound_off') : t('misc.dbu_title_sound_on')}
              aria-label={boardSettings.soundEnabled ? t('misc.dbu_title_sound_off') : t('misc.dbu_title_sound_on')}>
              
              {boardSettings.soundEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
            </button>

            <button
              onClick={toggleContrast}
              className="displayboard-btn"
              title={t('misc.dbu_title_contrast')}
              aria-label={boardSettings.contrastMode ? t('misc.dbu_aria_contrast_off') : t('misc.dbu_aria_contrast_on')}>
              
              {boardSettings.contrastMode ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>

            <button
              onClick={toggleLanguage}
              className="displayboard-btn"
              title={t('misc.dbu_title_switch_lang')}>
              
              <Globe size={16} />
              {boardSettings.language.toUpperCase()}
            </button>
          </div>
        </div>
      </div>

      {/* Статусные баннеры */}
      {!online &&
      <div className="displayboard-banner displayboard-banner--info">
          {t('misc.dbu_offline_banner')}
        </div>
      }

      {/* QR-FE-009: честный индикатор устаревания. REST /board/state по
          контракту не несёт строк очереди; строки восстанавливаются только
          WS initial_state при реконнекте. Пока WS лежит после успешной
          сессии — показываем заметный баннер вместо молчаливой выдачи
          возможно устаревших строк как живых. */}
      {!liveData && hasSnapshot &&
      <div className="displayboard-banner displayboard-banner--warning" data-testid="dbu-stale-banner">
          {t('misc.dbu_stale_ws_banner')}
        </div>
      }

      {/* DISPLAYERROR-FE-001: сбой снапшота бэкенда виден как ошибка, а не
          как «живая пустая очередь»; последние строки сохранены. */}
      {snapshotError &&
      <div className="displayboard-banner displayboard-banner--danger" data-testid="dbu-snapshot-error">
          <span>⚠ {snapshotError}</span>
          <button
            type="button"
            className="displayboard-banner-retry"
            data-testid="dbu-snapshot-retry"
            aria-label="Retry"
            onClick={() => connectWebSocketRef.current()}>
            ⟳
          </button>
        </div>
      }

      {board.is_closed &&
      <div className="displayboard-banner displayboard-banner--danger">
          {tBoard('closed', boardSettings.language)}
        </div>
      }

      {!board.is_closed && board.is_paused &&
      <div className="displayboard-banner displayboard-banner--warning">
          {tBoard('paused', boardSettings.language)}
        </div>
      }

      {/* Текущий вызов */}
      <div className={`displayboard-current-call${liveCall ? ' displayboard-current-call--active' : ''}`}>
        {liveCall ?
        <div>
            <div className="displayboard-call-number">
              № {liveCall.queue_number}
            </div>
            {/* RQ-24.a.1: тот же PHI-гейт, что и у строк очереди */}
            {boardSettings.showPatientNames !== 'none' &&
            <div className="displayboard-call-patient">
              {liveCall.patient_name}
            </div>}
            <div className="displayboard-call-doctor">
              👨‍⚕️ {liveCall.doctor_name}
            </div>
            {liveCall.cabinet &&
          <div className="displayboard-call-cabinet">
                🚪 {liveCall.cabinet}
              </div>
          }
          </div> :

        <div>
            <Monitor size={64} className="displayboard-no-call-icon" />
            <div className="displayboard-no-call-title">
              {!liveData ? t('misc.dbu_awaiting_data') : callStateAvailable
                ? t('misc.dbu_no_active_call') : t('misc.dbu_call_unavailable')}
            </div>
          </div>
        }
      </div>

      {liveData && displayTest && !liveCall &&
        <div className="displayboard-banner displayboard-banner--info" role="status" data-testid="display-board-test">
          <strong>{t('misc.dbu_test_label')}</strong>{' '}
          {displayTest.call
            ? t('misc.dbu_test_call', { number: displayTest.call.queue_number, cabinet: displayTest.call.cabinet })
            : t('misc.dbu_test_announcement')}
        </div>
      }

      {/* Объявления: DISPLAYOPTIONS-FE-001 — show_announcements табло
          управляет показом; DISPLAYANNOUNCE-FE-001 — истёкшие уходят. */}
      {liveData && boardSettings.showAnnouncements && announcements.length > 0 &&
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
        {queueData.slice(0, boardSettings.displayCount).map((entry, entryIndex) =>
        <div
          key={resolveBoardEntryKey(entry, entryIndex)}
          className="displayboard-queue-card"
          data-status={entry.status}>
          
            <div className="displayboard-queue-number">
              {entry.number}
            </div>
            
            {/* RQ-24.a.2: владелец/кабинет отличают одинаковые номера разных очередей. */}
            {(entry.doctor_name || entry.specialist_name) &&
          <div className="displayboard-queue-owner">
                👨‍⚕️ {entry.doctor_name ?? entry.specialist_name}
              </div>
          }
            {entry.cabinet &&
          <div className="displayboard-queue-cabinet">
                🚪 {entry.cabinet}
              </div>
          }

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
            t('misc.dbu_queue_called_at', { time: formatTime(entry.called_at) }) :

            t('misc.dbu_queue_created_at', { time: formatTime(entry.created_at) })
            }
            </div>

            <div className="displayboard-queue-source">
              {entry.source === 'online' ? t('misc.dbu_source_online') : t('misc.dbu_source_reception')}
            </div>
          </div>
        )}
      </div>

      {/* Окна/кабинеты */}
      {windows && windows.length > 0 &&
      <div className="displayboard-windows-wrap">
          <h3 className="displayboard-windows-title">
            {t('misc.dbu_windows_title')}
          </h3>
          <div className="displayboard-windows-grid">
            {windows.map((w, i) =>
          <div key={i} className="displayboard-window-card">
                <div className="displayboard-window-label">
                  {t('misc.dbu_window_label', { window: w.window })}
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

      {/* Статистика по выбранному отделению */}
      {liveData && stats &&
        <div className="displayboard-stats-grid">
          <div className="displayboard-stat-card">
            <div className="displayboard-stat-value-md">{stats.waiting}</div>
            <div className="displayboard-stat-label">{t('misc.dbu_stat_waiting')}</div>
          </div>
          <div className="displayboard-stat-card">
            <div className="displayboard-stat-value-md">{stats.serving}</div>
            <div className="displayboard-stat-label">{t('misc.dbu_stat_serving')}</div>
          </div>
          <div className="displayboard-stat-card">
            <div className="displayboard-stat-value-md">{stats.done}</div>
            <div className="displayboard-stat-label">{t('misc.dbu_stat_done')}</div>
          </div>
        </div>
      }

      {/* Объявление внизу */}
      {(getAnnouncement(board, boardSettings.language) || announcement) &&
      <div className="displayboard-bottom-announcement">
          <div className="displayboard-bottom-announcement-text">
            {getAnnouncement(board, boardSettings.language) || announcement || t('misc.dbu_welcome')}
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


// audit/strict: removed self-referencing propTypes spread

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

function tBoard(key: string, lang: string = 'ru') {
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

  const langTranslations = translations[lang as keyof typeof translations];
  const ruTranslations = translations.ru;
  return (langTranslations && langTranslations[key as keyof typeof ruTranslations]) || ruTranslations[key as keyof typeof ruTranslations] || key;
}
