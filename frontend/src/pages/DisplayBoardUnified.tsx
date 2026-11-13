import { useState, useEffect, useRef, useMemo, type FormEvent } from 'react';
import type { CSSProperties } from 'react';
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
import {
  exchangeDisplayDeviceCredential,
  forgetDisplayDeviceCredential,
  readDisplayDeviceCredential,
  saveDisplayDeviceCredential,
} from '../api/displayDeviceAuth';
import { useTheme } from '../contexts/ThemeContext';

import logger from '../utils/logger';
import { formatRegistrarTime } from '../utils/dateUtils';
import './displayboard.css';
import { useTranslation } from '../i18n/useTranslation';
import { safeJsonParse } from '../utils/safeJsonParse';
import { tokenManager } from '../utils/tokenManager';

const DEFAULT_BOARD_STATS = { last_ticket: 0, waiting: 0, serving: 0, done: 0 };

type BoardStats = typeof DEFAULT_BOARD_STATS;

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
  cabinet?: string;
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
  queue_number?: number | string;
  patient_name?: string;
  doctor_name?: string;
  cabinet?: string;
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
  voiceEnabled: boolean;
  displayCount: number;
  // DISPLAYOPTIONS-FE-001 (audit PR #3961): show_announcements табло
  // управляет показом блока объявлений на живом экране.
  showAnnouncements: boolean;
  contrastMode: boolean;
  kioskMode: boolean;
  fontScale: number;
  language: string;
}

interface WSMessageData {
  number?: number | string;
  cabinet?: string;
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

const extractBoardStats = (source: Record<string, unknown> | null | undefined): BoardStats => ({
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
}: DisplayBoardUnifiedProps) {void
  useTheme();
  const { t: rawT } = useTranslation();
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
  const [wsEverConnected, setWsEverConnected] = useState(false);
  const [queueData, setQueueData] = useState<QueueEntryDto[]>([]);
  const [currentCall, setCurrentCall] = useState<CurrentCall | null>(null);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);

  // Состояние статистики (старое)
  const [stats, setStats] = useState<BoardStats>(DEFAULT_BOARD_STATS);
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
    voiceEnabled: false,
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
  const lastTicketRef = useRef(0);
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
    return readDisplayDeviceCredential(currentBoardId) ? 'ready' : 'unconfigured';
  });
  const [setupDeviceId, setSetupDeviceId] = useState('');
  const [setupDeviceSecret, setSetupDeviceSecret] = useState('');
  const [setupError, setSetupError] = useState('');
  const [setupSubmitting, setSetupSubmitting] = useState(false);

  // /board/state is a stats/settings snapshot; live rows/calls/announcements come from WebSocket initial_state.
  // DISPLAYDEPT-FE-001: department уходит в params только когда валиден —
  // литеральный "undefined" не отправляется; DISPLAYCONFIG-FE-001:
  // снапшот настроек запрашивается для ТЕКУЩЕГО табло (board=...).
  async function loadBoardState() {setErr('');try {const st = (await api.get('/board/state', { params: { date: qs.d, ...(qs.department ? { department: qs.department } : {}), board: currentBoardId } })).data as Record<string, unknown> | undefined;if (st && typeof st === 'object') {
        setStats(extractBoardStats(st));
        setBoard({
          brand: String(st.brand ?? st.title ?? 'Clinic'),
          logo: String(st.logo ?? st.logo_url ?? ''),
          is_paused: !!(st.is_paused || st.paused),
          is_closed: !!(st.is_closed || st.closed),
          announcement: String(st.announcement ?? st.ticker ?? ''),
          announcement_ru: String(st.announcement_ru ?? ''),
          announcement_uz: String(st.announcement_uz ?? ''),
          announcement_en: String(st.announcement_en ?? ''),
          primary_color: String(st.primary_color ?? ''),
          bg_color: String(st.bg_color ?? ''),
          text_color: String(st.text_color ?? ''),
          contrast_default: !!st.contrast_default,
          kiosk_default: !!st.kiosk_default,
          sound_default: st.sound_default !== false
        });
        // DISPLAYAUDIO-FE-001: бэкенд-дефолт применяется, пока оператор
        // не сделал ручной выбор в этой сессии (иначе мьют переживает опрос).
        if (
          soundInitial === undefined &&
          soundOverrideRef.current === null &&
          typeof st.sound_default !== 'undefined'
        ) {
          setBoardSettings((prev) => ({ ...prev, soundEnabled: st.sound_default !== false }));
        }
        // RQ-24.a.1: sync the board privacy setting (full/initials/none)
        // DISPLAYCONFIG-FE-001: значение ТЕКУЩЕГО табло (/board/state?board=),
        // а не main_board.
        if (typeof st.show_patient_names === 'string') {
          const fmt = st.show_patient_names;
          if (fmt === 'none' || fmt === 'initials' || fmt === 'full') {
            setBoardSettings((prev) => ({ ...prev, showPatientNames: fmt }));
          }
        }
        // DISPLAYOPTIONS-FE-001: сохранённые админом настройки показа
        // применяются живым экраном (непубличные поля не затрагиваются).
        if (typeof st.queue_display_count === 'number' && st.queue_display_count >= 1) {
          const count = Math.min(Math.floor(st.queue_display_count), 20);
          setBoardSettings((prev) => ({ ...prev, displayCount: count }));
        }
        if (typeof st.voice_announcements === 'boolean') {
          const voiceAnnouncements = st.voice_announcements as boolean;
          setBoardSettings((prev) => ({ ...prev, voiceEnabled: voiceAnnouncements }));
        }
        if (typeof st.show_announcements === 'boolean') {
          const showAnnouncements = st.show_announcements as boolean;
          setBoardSettings((prev) => ({ ...prev, showAnnouncements }));
        }
        try {localStorage.setItem('board.state', JSON.stringify(st));} catch {







          // Игнорируем ошибки localStorage
        }}} catch (e: unknown) {setErr((e as { message?: string })?.message || t('misc.dbu_err_load')); // fallback из кэша
      try {const raw = localStorage.getItem('board.state');if (raw) {const cached = safeJsonParse(raw) as Record<string, unknown>;if (cached && typeof cached === 'object') {
            setStats(extractBoardStats(cached));
            setBoard({
              brand: String(cached.brand ?? cached.title ?? 'Clinic'),
              logo: String(cached.logo ?? cached.logo_url ?? ''),
              is_paused: !!(cached.is_paused || cached.paused),
              is_closed: !!(cached.is_closed || cached.closed),
              announcement: String(cached.announcement ?? cached.ticker ?? ''),
              announcement_ru: String(cached.announcement_ru ?? ''),
              announcement_uz: String(cached.announcement_uz ?? ''),
              announcement_en: String(cached.announcement_en ?? ''),
              primary_color: String(cached.primary_color ?? ''),
              bg_color: String(cached.bg_color ?? ''),
              text_color: String(cached.text_color ?? ''),
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

      const staffToken = tokenManager.getAccessToken();
      const deviceCredential = !staffToken && isBoardView
        ? readDisplayDeviceCredential(currentBoardId)
        : null;
      if (isBoardView && !staffToken && !deviceCredential) {
        setDisplayDeviceState('unconfigured');
        setConnected(false);
        return;
      }

      if (deviceCredential && !staffToken) setDisplayDeviceState('connecting');
      const tokenProvider = deviceCredential
        ? async () => {
            // Staff access always takes precedence, including on reconnect
            // after a staff session is established in this browser.
            const currentStaffToken = tokenManager.getAccessToken();
            if (currentStaffToken) return currentStaffToken;
            const currentCredential = readDisplayDeviceCredential(currentBoardId);
            if (!currentCredential) throw new Error('Display device needs provisioning');
            try {
              const deviceToken = await exchangeDisplayDeviceCredential(
                currentCredential,
                currentBoardId,
              );
              setDisplayDeviceState('ready');
              setSetupError('');
              return deviceToken;
            } catch (error) {
              setDisplayDeviceState('unconfigured');
              setSetupError('Не удалось подтвердить устройство. Проверьте данные или обратитесь к администратору.');
              throw error;
            }
          }
        : undefined;

      // Создаем новое соединение
      const closeWS = openDisplayBoardWS(
        currentBoardId,
        handleWebSocketMessage,
        () => { setConnected(true); setWsEverConnected(true); },
        () => setConnected(false),
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
    const credential = { deviceId, secret };
    try {
      // Validate before storing. The short-lived JWT is kept in memory by
      // the socket helper; only the per-board device credential is persisted.
      await exchangeDisplayDeviceCredential(credential, currentBoardId);
      saveDisplayDeviceCredential(currentBoardId, credential);
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

  // Обработка WebSocket сообщений (новое)
  const handleWebSocketMessage = (messageRaw: unknown) => {
    const message = messageRaw as WSMessage;
    logger.log('Получено WebSocket сообщение:', message);

    switch (message.type) {
      case 'initial_state': {
        const data = message.data || {};
        // DISPLAYERROR-FE-001 (audit PR #3961): сбой снапшота бэкенда
        // приходит как initial_state с data.error и пустыми строками —
        // это НЕ «живая пустая очередь». Показываем видимый баннер,
        // последние корректные строки сохраняем (не затираем), повтор
        // — кнопка Retry / авто-реконнект WS.
        if (typeof data.error === 'string' && data.error.trim()) {
          setSnapshotError(data.error);
          break;
        }
        setSnapshotError('');
        setQueueData(Array.isArray(data.queue_entries) ? data.queue_entries : []);
        setCurrentCall(data.current_call ?? null);
        setAnnouncements(
          (Array.isArray(data.announcements) ? data.announcements : []).map(
            (item: Announcement) => ({
              ...item,
              expires_at: undefined,
            })
          )
        );
        break;
      }

      case 'patient_call': {
        // DISPLAYCALL-FE-001 (audit PR #3961): подсветка последнего вызова
        // истекает по display_duration из payload (бэкенд-контракт, 30с
        // по умолчанию) — больше не «навсегда» до следующего вызова.
        setCurrentCall(message.data);
        clearCallExpiry();
        const durationSeconds = Number(message.data?.display_duration ?? 30);
        if (Number.isFinite(durationSeconds) && durationSeconds > 0) {
          callExpiryRef.current = setTimeout(() => {
            setCurrentCall(null);
            callExpiryRef.current = null;
          }, durationSeconds * 1000);
        }
        if (boardSettings.soundEnabled) {
          playCallSound(message);
        }
        break;
      }

      case 'call_completed':
        clearCallExpiry();
        setCurrentCall(null);
        break;

      case 'queue_update': {
        const data = message.data || {};
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
          };
          setQueueData((prev) => [...prev, newEntry]);
          logger.log(`➕ Новая запись в очереди: №${data.number ?? ''}`);
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
              cabinet: entry.cabinet ?? queueCabinet,
            }));
          // DISPLAYCALL-FE-001 (audit PR #3961): реальный жизненный цикл
          // вызова приходит как queue_update — если вызванная строка ушла
          // в терминальный статус (served/completed/no_show/cancelled),
          // подсветка последнего вызова гаснет, а не висит до следующего.
          // Проверка по СЫРОМУ payload (терминальные строки отфильтрованы
          // из read-model) и функциональный setCurrentCall: WS-хэндлер
          // держит замыкание на момент подключения, prev-состояние в
          // updater — единственный честный источник.
          const terminalStatuses = ['served', 'completed', 'no_show', 'cancelled'];
          const terminalNumbers = new Set(
            rawEntries
              .filter((entry) => terminalStatuses.includes(String(entry.status)))
              .map((entry) => String(entry.number))
          );
          if (terminalNumbers.size > 0) {
            clearCallExpiry();
            setCurrentCall((prev) =>
              prev && terminalNumbers.has(String(prev.queue_number ?? ''))
                ? null
                : prev
            );
          }
          setQueueData((prev) => {
            if (eventQueueId === undefined) {
              // Защита от дрифта контракта (старый бэкенд без queue_id):
              // прежнее поведение — полная замена. Владение очередью по
              // номеру/метке специализации не восстанавливаем.
              return scopedEntries;
            }
            const kept = prev.filter((entry) => entry.queue_id !== eventQueueId);
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
        // DISPLAYANNOUNCE-FE-001 (audit PR #3961): display_duration из
        // payload — каждое объявление живёт запрошенное окно и исчезает
        // без зависимости от новых событий (раньше оставалось навсегда).
        const durationSeconds = Number(message.data?.display_duration ?? 0);
        const announcementKey =
          typeof message.data?.created_at === 'string'
            ? message.data.created_at
            : `announce-${Date.now()}-${Math.random()}`;
        const newAnnouncement: Announcement = {
          created_at: announcementKey,
          announcement_type: typeof message.data?.announcement_type === 'string' ? message.data.announcement_type : undefined,
          text: typeof message.data?.text === 'string' ? message.data.text : undefined,
          expires_at:
            Number.isFinite(durationSeconds) && durationSeconds > 0
              ? Date.now() + durationSeconds * 1000
              : undefined,
        };
        setAnnouncements((prev) => [newAnnouncement, ...prev.slice(0, 4)]);
        if (Number.isFinite(durationSeconds) && durationSeconds > 0) {
          const timer = setTimeout(() => {
            setAnnouncements((prev) => prev.filter((a) => a !== newAnnouncement));
            announceTimersRef.current.delete(announcementKey);
          }, durationSeconds * 1000);
          announceTimersRef.current.set(announcementKey, timer);
        }
        if (boardSettings.soundEnabled) {
          playAnnouncementSound(message);
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

  // Звуковые эффекты (новое)
  const playCallSound = (message: WSMessage) => {
    if (!boardSettings.soundEnabled) return;

    try {
      // Создаем звуковой сигнал с помощью Web Audio API
      const audioContext = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
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

      logger.log(`🔊 Звуковой сигнал для пациента №${message.data?.number ?? ''}`);

      // Голосовое объявление
      if (boardSettings.voiceEnabled) {
        // QUEUE-AUDIT-28 P0-9: PHI removed — patient name no longer spoken aloud.
        // Раньше speechSynthesis произносил "Lastname F." в публичном зале ожидания.
        const text = t('misc.dbu_voice_patient_call', { number: message.data?.number ?? '', cabinet: message.data?.cabinet || t('misc.dbu_voice_default_cabinet') });
        playVoiceAnnouncement(text);
      }
    } catch (error) {
      logger.error('Ошибка воспроизведения звука:', error);
    }
  };

  const playAnnouncementSound = (message: WSMessage) => {
    if (!boardSettings.soundEnabled) return;

    try {
      let soundFile = '/sounds/announcement.mp3';

      if (message.data?.announcement_type === 'warning') {
        soundFile = '/sounds/warning-beep.mp3';
      } else if (message.data?.announcement_type === 'emergency') {
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

  const playVoiceAnnouncement = (text: string) => {
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
    const params = new URLSearchParams(window.location.search);
    if (params.get('forget-device') === '1') {
      forgetDisplayDeviceCredential(currentBoardId);
      params.delete('forget-device');
      const query = params.toString();
      window.history.replaceState(
        null,
        '',
        `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`,
      );
      if (!tokenManager.getAccessToken()) {
        setDisplayDeviceState('unconfigured');
        setSetupDeviceId('');
        setSetupDeviceSecret('');
      }
    }
    loadBoardStateRef.current();
    loadWindowsRef.current();
    connectWebSocketRef.current();

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
      if (tb) clearInterval(tb);
      if (tw) clearInterval(tw);
      clearInterval(clock);
      clearCallExpiry();
      clearAnnounceTimers();
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
  // DISPLAYAUDIO-FE-001: ручное решение живёт в ref — опрос /board/state
  // больше не перезатирает мьют оператора бэкенд-дефолтом.
  const toggleSound = () => {
    setBoardSettings((prev) => {
      soundOverrideRef.current = !prev.soundEnabled;
      return { ...prev, soundEnabled: !prev.soundEnabled };
    });
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
            {connected ? <Wifi size={20} color="var(--mac-success)" /> : <WifiOff size={20} color="#dc3545" />}
            <span className="displayboard-conn-status">
              {connected ? t('misc.dbu_conn_connected') : t('misc.dbu_conn_disconnected')}
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
      {!connected && wsEverConnected &&
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
      <div className={`displayboard-current-call${currentCall ? ' displayboard-current-call--active' : ''}`}>
        {currentCall ?
        <div>
            <div className="displayboard-call-number">
              № {currentCall.queue_number}
            </div>
            {/* RQ-24.a.1: тот же PHI-гейт, что и у строк очереди */}
            {boardSettings.showPatientNames !== 'none' &&
            <div className="displayboard-call-patient">
              {currentCall.patient_name}
            </div>}
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
              {tBoard('now_serving', boardSettings.language)}
            </div>
            <div className="displayboard-no-call-ticket">
              {stats.last_ticket || 0}
            </div>
          </div>
        }
      </div>

      {/* Объявления: DISPLAYOPTIONS-FE-001 — show_announcements табло
          управляет показом; DISPLAYANNOUNCE-FE-001 — истёкшие уходят. */}
      {boardSettings.showAnnouncements && announcements.length > 0 &&
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

      {/* Статистика */}
      <div className="displayboard-stats-grid">
        <div className="displayboard-stat-card">
          <div className="displayboard-stat-value-lg">
            {queueData.length}
          </div>
          <div className="displayboard-stat-label">{t('misc.dbu_stat_total')}</div>
        </div>

        <div className="displayboard-stat-card">
          <div className="displayboard-stat-value-lg">
            {queueData.filter((e) => e.status === 'waiting').length}
          </div>
          <div className="displayboard-stat-label">{t('misc.dbu_stat_waiting')}</div>
        </div>

        <div className="displayboard-stat-card">
          <div className="displayboard-stat-value-md">
            {formatRegistrarTime(new Date().toISOString())}
          </div>
          <div className="displayboard-stat-label">{t('misc.dbu_stat_current_time')}</div>
        </div>

        <div className="displayboard-stat-card">
          <div className="displayboard-stat-value-md">
            {stats.waiting}
          </div>
          <div className="displayboard-stat-label">{t('misc.dbu_stat_waiting_legacy')}</div>
        </div>

        <div className="displayboard-stat-card">
          <div className="displayboard-stat-value-md">
            {stats.serving}
          </div>
          <div className="displayboard-stat-label">{t('misc.dbu_stat_serving')}</div>
        </div>

        <div className="displayboard-stat-card">
          <div className="displayboard-stat-value-md">
            {stats.done}
          </div>
          <div className="displayboard-stat-label">{t('misc.dbu_stat_done')}</div>
        </div>
      </div>

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
