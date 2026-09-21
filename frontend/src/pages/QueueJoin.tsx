import { useState, useEffect, useCallback, useRef } from 'react';
import type { CSSProperties, FormEvent, ChangeEvent, ReactNode } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Clock,
  Users,
  CheckCircle,
  AlertCircle,
  Phone,
  User,
  MapPin,
  Calendar,
  Timer
} from 'lucide-react';
import './QueueJoin.css';
import {
  fetchQrTokenInfo,
  startQueueJoinSession,
  completeQueueJoinSession,
} from '../api/queue';
import { startPublicDirectionSession } from '../api/queueDirections';
import type { PublicDirectionStartResponse } from '../api/queueDirections';
import { formatRegistrarTime } from '../utils/dateUtils';
import {
  Input,
  Checkbox } from '../components/ui/macos';
import { useTranslation } from '../i18n/useTranslation';
import type { QueueSpecialist } from '../types/domain/queue';
import { safeJsonParse } from '../utils/safeJsonParse';
import type { HttpApiError } from '../types/errors';

interface QueueJoinPageInfo {
  is_clinic_wide?: boolean;
  selectable_specialists?: QueueSpecialist[];
  target_date?: string;
  specialist_name?: string;
  department?: string;
  department_name?: string;
  queue_name?: string;
  minutes_until_open?: number;
  start_time?: string;
  queue_length?: number;
  specialty?: string;
  queue_active?: boolean;
  allowed?: boolean;
  message?: string;
  status?: string;
  valid?: boolean;
  expired?: boolean;
  [key: string]: unknown;
}

interface QueueJoinResultEntry {
  id?: number | string;
  icon?: ReactNode;
  specialist_name?: string;
  department?: string;
  specialty?: string;
  queue_time?: string;
  queue_number?: number;
  number?: number;
  [key: string]: unknown;
}

interface QueueJoinResultLocal {
  success?: boolean;
  message?: string;
  entries?: QueueJoinResultEntry[];
  // RQ-10 (S-08): неуспешные направления из complete_join_session_multiple
  // (backend: errors — список { specialist_id, error } рядом с entries).
  errors?: Array<{
    specialist_id?: number | string;
    error?: string;
    [key: string]: unknown;
  }>;
  queue_number?: number;
  estimated_wait_time?: number;
  specialist_name?: string;
  [key: string]: unknown;
}

// RQ-10 (S-08): сетевой класс сбоя при завершении join — ответ не получен
// (обрыв соединения/таймаут) либо прокси-ошибка 502/503/504, когда запрос
// мог быть уже обработан сервером. Только для этого класса показывается
// «результат неизвестен» и последующий честный совет; обычная серверная
// ошибка 4xx при первой попытке поведение не меняет.
const isNetworkClassSubmitError = (err: unknown): boolean => {
  const status = Number((err as HttpApiError | null)?.response?.status ?? 0);
  return status === 0 || status === 502 || status === 503 || status === 504;
};

// RQ-18 follow-up round-2 (P1): the permanent public code is SHARED by
// every patient of the direction — the typed draft (name/phone) is PHI
// and must never persist in long-lived localStorage under it. The
// direction draft lives in sessionStorage (survives a reload, dies with
// the browser session), carries a short TTL, and is NEVER restored
// silently — its owner must explicitly confirm the restore (and the
// confirmation prompt reveals no PHI either).
const DIRECTION_DRAFT_TTL_MS = 15 * 60 * 1000; // matches the session TTL

interface QueueJoinDraftData {
  patientName: string;
  phone: string;
  telegramId: string;
  [key: string]: unknown;
}

const QueueJoin = () => {
  const { token: paramToken } = useParams();
  // RQ-18 (S-15): public permanent-address route /q/:publicCode renders the
  // SAME QueueJoin experience. Direction mode is detected purely from the
  // route params — no second registration UI, no props plumbing.
  const { publicCode: paramPublicCode } = useParams();
  const directionCode = paramPublicCode || null;
  const directionMode = Boolean(directionCode);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;

  const formatSpecialistLabel = (specialist: QueueSpecialist | null | undefined) => {
    const doctorName =
      specialist?.doctor_name ||
      specialist?.full_name ||
      specialist?.name ||
      specialist?.specialty_display ||
      specialist?.specialty ||
      t('misc.qj_specialist_default');
    const specialtyLabel =
      specialist?.specialty_display ||
      specialist?.specialty ||
      '';
    const cabinetLabel = specialist?.cabinet != null ? t('misc.qj_cabinet_label', { cabinet: String(specialist.cabinet) }) : '';

    return [doctorName, specialtyLabel, cabinetLabel]
      .filter(Boolean)
      .join(' • ');
  };

  const MISSING_QUEUE_TOKEN_MESSAGE = t('misc.qj_missing_token');
  const QUEUE_JOIN_MESSAGES = {
    sessionStartFailed: t('misc.qj_session_start_failed'),
    registrationUnavailable: t('misc.qj_registration_unavailable'),
    qrTokenUnavailable: t('misc.qj_qr_token_unavailable'),
    requiredFields: t('misc.qj_required_fields'),
    sessionExpired: t('misc.qj_session_expired'),
    sessionCreateFailed: t('misc.qj_session_create_failed'),
    nameTooShort: t('misc.qj_name_too_short'),
    nameTooLong: t('misc.qj_name_too_long'),
    phoneTooShort: t('misc.qj_phone_too_short'),
    phoneTooLong: t('misc.qj_phone_too_long'),
    missingSessionToken: t('misc.qj_missing_session_token'),
    joinFailed: t('misc.qj_join_failed'),
    selectSpecialist: t('misc.qj_select_specialist'),
    directionUnavailable: t('misc.qj_direction_unavailable'),
  };

  // Получаем токен из URL параметров или query параметров (для PWA пути).
  // RQ-18 follow-up round-3 (P1): direction mode ignores the legacy token
  // COMPLETELY — a foreign `?token=` query must never define the draft
  // identity of a permanent address. One shared token would otherwise be
  // the SAME storage key for /q/A and /q/B: no rehydration on the switch,
  // A's typed PHI stays in memory and is submitted under B's session —
  // PHI leakage AND wrong clinical routing in one.
  const legacyToken = directionMode
    ? null
    : paramToken || searchParams.get('token');
  // RQ-18 follow-up (P1-2): у постоянного адреса нет legacy QR-токена —
  // черновик формы живёт на СВОЁМ ключе по public_code. Это делает ФИО и
  // телефон восстановимыми после перезагрузки страницы, когда сессия
  // истекла, а также разводит черновики разных направлений при /q/A →
  // /q/B (P2-2: у каждого кода свой черновик).
  // RQ-18 follow-up round-2 (P1): постоянный код ОБЩИЙ для всех пациентов
  // направления — PHI-черновик направления живёт ТОЛЬКО в sessionStorage
  // (переживает reload, умирает с браузерной сессией) с коротким TTL;
  // legacy-ключ по короткоживущему QR-токену сохраняет прежнее поведение.
  const formStorageKey = directionCode
    ? `queue_join_form_qdir_${directionCode}`
    : legacyToken
      ? `queue_join_form_${legacyToken}`
      : null;

  const draftGet = useCallback(
    (key: string): string | null =>
      directionMode
        ? window.sessionStorage.getItem(key)
        : window.localStorage.getItem(key),
    [directionMode],
  );
  const draftSet = useCallback(
    (key: string, value: string): void => {
      if (directionMode) {
        window.sessionStorage.setItem(key, value);
      } else {
        window.localStorage.setItem(key, value);
      }
    },
    [directionMode],
  );
  const draftRemove = useCallback((key: string): void => {
    // Belt & suspenders: clear BOTH stores — no PHI may linger either way.
    window.sessionStorage.removeItem(key);
    window.localStorage.removeItem(key);
  }, []);

  // Состояния
  const [step, setStep] = useState<'loading' | 'waiting' | 'info' | 'select-specialists' | 'form' | 'success' | 'error'>('loading');
  const [queueInfo, setQueueInfo] = useState<QueueJoinPageInfo | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [formData, setFormData] = useState<Record<string, unknown>>({
    patientName: '',
    phone: '',
    telegramId: ''
  });
  const [selectedSpecialists, setSelectedSpecialists] = useState<Array<number | string>>([]); // Выбранные специалисты для общего QR
  const [availableSpecialists, setAvailableSpecialists] = useState<QueueSpecialist[]>([]); // Список доступных специалистов из API
  const [isSpecialistsLoading, setIsSpecialistsLoading] = useState(true);
  const [result, setResult] = useState<QueueJoinResultLocal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  // RQ-10 (S-08): потеря ответа при завершении join — честный статус повторной отправки.
  const [submitResultUnknown, setSubmitResultUnknown] = useState(false);
  const [showSessionConsumedAdvisory, setShowSessionConsumedAdvisory] = useState(false);
  // RQ-18: honest unified-refusal marker for the permanent-address route
  // (unknown/archived/hidden/tombstoned/retired are indistinguishable).
  const [directionUnavailable, setDirectionUnavailable] = useState(false);
  // RQ-18 follow-up (P1-2): client-known expiry of the direction session
  // (QueueJoinSession lives 15 minutes server-side). A token that is
  // ALREADY expired at submit time is transparently renewed BEFORE the
  // first business attempt — a session start duplicates no business
  // action; the RQ-10 result-unknown honesty for a lost complete-response
  // stays fully in force (no renewal after a complete attempt).
  const [sessionExpiresAt, setSessionExpiresAt] = useState<string | null>(null);
  // RQ-18 (§10): EXACTLY ONE public start-session per mount — the ref
  // survives the StrictMode dev double-invoke of effects.
  // RQ-18 follow-up (P2-2): the guard holds the LAST STARTED public code,
  // not a boolean — /q/A → /q/B inside one route instance (same mount,
  // changed :publicCode param) must start B's session and drop A's whole
  // client context; StrictMode re-invokes with the SAME code and skips.
  const directionStartRef = useRef<string | null>(null);
  // RQ-18 follow-up round-2 (P1): request epoch — every async response
  // (start AND complete) is bound to the epoch it was issued in, so a
  // LATE answer for a superseded code can never overwrite the freshly
  // booted direction (out-of-order A/B responses).
  const directionEpochRef = useRef(0);
  // RQ-18 follow-up round-3 (P1): a complete attempt makes the session's
  // business result UNKNOWN (the response may have been lost) — from that
  // moment the automatic session renewal is FORBIDDEN until an explicit
  // start-over (a NEW publicCode resets this). The backend one-shot claim
  // lives INSIDE one session token: silently minting a fresh session
  // after a lost complete response would bypass the whole
  // «used session → reconcile» mechanism and turn a safe retry into a
  // second business attempt.
  const completeAttemptedRef = useRef(false);
  // RQ-18 follow-up round-3 (P1): the submit lock is claimed IMMEDIATELY
  // (before the first await — the button's disabled attribute only flips
  // after a React re-render, so two fast clicks would both pass a mere
  // `loading` check and mint TWO sessions) and it is EPOCH+CODE-SCOPED:
  // a superseded attempt's finally must neither release — nor keep
  // blocking — the NEW direction's submit button.
  const submitAttemptRef = useRef<{
    epoch: number;
    code: string | null;
  } | null>(null);
  // RQ-18 follow-up round-2 (P1): a found-but-unconfirmed draft — never
  // applied to the form until its owner explicitly restores it.
  const [pendingDraft, setPendingDraft] = useState<QueueJoinDraftData | null>(null);
  // The typed direction the session is scoped to — the completion of a
  // direction session is the PROFILE choice of this very direction (§8:
  // the backend rejects doctor/untyped choices for qdir-scoped sessions).
  const [directionInfo, setDirectionInfo] = useState<
    PublicDirectionStartResponse['direction'] | null
  >(null);

  const getApiErrorMessage = useCallback((err: unknown, fallbackMessage: string): string => {
    const responseData = (err as HttpApiError)?.response?.data;
    if (typeof responseData?.detail === 'string') {
      return responseData.detail;
    }
    if (Array.isArray(responseData?.detail)) {
      return responseData.detail
        .map((item: unknown) => (item && typeof item === 'object' && 'msg' in item ? String((item as { msg?: unknown }).msg ?? '') : String(item)))
        .join(', ');
    }
    if (typeof responseData?.message === 'string') {
      return responseData.message;
    }
    return fallbackMessage;
  }, []);

  // RQ-18 follow-up (P1-2): the persist effect runs BEFORE the load
  // effect and is guarded by BOTH the owner key and the hydration flag.
  //  - owner key: on a /q/A → /q/B switch the commit where formStorageKey
  //    changed still carries A's formData — writing it into B's key would
  //    corrupt the new draft; the load effect owns that commit.
  //  - hydration: the ref starts DISARMED and persist stays silent until
  //    the load effect for the current key has actually read the store —
  //    otherwise StrictMode's simulated remount re-runs the persist setup
  //    with the initial empty state and wipes the stored draft.
  // RQ-18 follow-up round-2 (P1): the direction draft is written to
  // sessionStorage in a { ts, data } envelope (TTL refreshed on every
  // write); the legacy per-token draft keeps its raw localStorage shape.
  const formDataOwnerRef = useRef<string | null>(null);
  const [formDraftHydrated, setFormDraftHydrated] = useState(false);
  useEffect(() => {
    if (!formStorageKey || !formDraftHydrated) {
      return;
    }
    if (formDataOwnerRef.current !== formStorageKey) {
      // Stale draft from another code/key — the load effect owns this commit.
      return;
    }
    // RQ-18 follow-up round-3 (P2): a found-but-unconfirmed draft must
    // SURVIVE rerenders and remounts — the empty form under the pending
    // confirmation banner is NOT an empty draft. Erasing here deleted the
    // stored copy right after the banner appeared, so a second reload
    // (or a crash) lost both the banner and the draft for good — the
    // reload-recovery semantics were only true for the FIRST reload.
    if (directionMode && pendingDraft) {
      return;
    }
    if (!formData.patientName && !formData.phone && !formData.telegramId) {
      draftRemove(formStorageKey);
      return;
    }
    if (directionMode) {
      draftSet(formStorageKey, JSON.stringify({ ts: Date.now(), data: formData }));
    } else {
      draftSet(formStorageKey, JSON.stringify(formData));
    }
  }, [formData, formStorageKey, formDraftHydrated, pendingDraft, directionMode, draftSet, draftRemove]);

  useEffect(() => {
    // RQ-18 follow-up round-2 (P1): switching directions discards the
    // PREVIOUS code's draft entirely — permanent codes belong to
    // different directions and their drafts must not linger.
    const previousKey = formDataOwnerRef.current;
    const keyChanged = Boolean(previousKey) && previousKey !== formStorageKey;
    if (previousKey && previousKey !== formStorageKey) {
      draftRemove(previousKey);
    }
    if (!formStorageKey) {
      formDataOwnerRef.current = null;
      setFormDraftHydrated(false);
      setPendingDraft(null);
      return;
    }
    // RQ-18 follow-up round-3 (P1): an explicit context drop on ANY key
    // change — the new key hydrates from a CLEAN slate, never from the
    // previous direction's in-memory form or its held draft. Changing
    // the key string alone is not the contract: the form and the
    // pending-draft state must be provably reset before the new
    // hydration runs.
    if (keyChanged) {
      setPendingDraft(null);
      setFormData({ patientName: '', phone: '', telegramId: '' });
    }
    formDataOwnerRef.current = formStorageKey;
    const saved = draftGet(formStorageKey);
    let restored: QueueJoinDraftData | null = null;
    try {
      const parsed = saved ? safeJsonParse(saved) : null;
      if (directionMode) {
        // { ts, data } envelope with a short TTL — a stale draft is a
        // discarded draft.
        const envelope = parsed as { ts?: unknown; data?: unknown } | null;
        const ts = Number(envelope?.ts ?? 0);
        const data = envelope?.data as Record<string, unknown> | undefined;
        if (data && typeof data === 'object' && Date.now() - ts <= DIRECTION_DRAFT_TTL_MS) {
          restored = {
            patientName: String(data.patientName ?? ''),
            phone: String(data.phone ?? ''),
            telegramId: String(data.telegramId ?? ''),
          };
        } else if (saved) {
          draftRemove(formStorageKey);
        }
      } else if (parsed && typeof parsed === 'object') {
        const record = parsed as Record<string, unknown>;
        restored = {
          patientName: String(record.patientName ?? ''),
          phone: String(record.phone ?? ''),
          telegramId: String(record.telegramId ?? ''),
        };
      }
    } catch {
      draftRemove(formStorageKey);
      restored = null;
    }
    const hasContent = Boolean(
      restored && (restored.patientName || restored.phone || restored.telegramId),
    );
    if (directionMode && hasContent && restored) {
      // NEVER restore PHI silently on the shared permanent route: hold
      // the draft for the owner's explicit confirmation (the prompt
      // itself reveals nothing), keep the form empty meanwhile.
      setPendingDraft(restored);
      setFormData({ patientName: '', phone: '', telegramId: '' });
    } else {
      setPendingDraft(null);
      setFormData(restored ?? { patientName: '', phone: '', telegramId: '' });
    }
    setFormDraftHydrated(true);
  }, [formStorageKey, directionMode, draftGet, draftRemove]);

  // ✅ Функции объявлены до использования в useEffect
  const startJoinSession = useCallback(async () => {
    if (!legacyToken) {
      setIsSpecialistsLoading(false);
      return;
    }
    setIsSpecialistsLoading(true);
    try {
      const sessionData = await startQueueJoinSession(legacyToken);
      const nextQueueInfo: QueueJoinPageInfo = (sessionData.queue_info ?? {}) as QueueJoinPageInfo;
      const selectableSpecialists: QueueSpecialist[] = Array.isArray(nextQueueInfo.selectable_specialists)
        ? nextQueueInfo.selectable_specialists
        : [];

      setSessionToken(sessionData.session_token);
      localStorage.setItem(`queue_session_${legacyToken}`, sessionData.session_token);
      setQueueInfo(nextQueueInfo);
      setAvailableSpecialists(selectableSpecialists);

      if (nextQueueInfo.is_clinic_wide) {
        setStep('select-specialists');
      } else {
        setStep('info');
      }

    } catch (error: unknown) {
      setAvailableSpecialists([]);
      setError(getApiErrorMessage(error, QUEUE_JOIN_MESSAGES.sessionStartFailed));
      setStep('error');
    } finally {
      setIsSpecialistsLoading(false);
    }
  }, [getApiErrorMessage, legacyToken]);

  const loadTokenInfo = useCallback(async () => {
    if (!legacyToken) {
      setError(MISSING_QUEUE_TOKEN_MESSAGE);
      setStep('error');
      setIsSpecialistsLoading(false);
      return;
    }

    try {
      setStep('loading');
      setIsSpecialistsLoading(true);
      const tokenInfoRaw = await fetchQrTokenInfo(legacyToken);
      const tokenInfo = tokenInfoRaw as unknown as QueueJoinPageInfo;
      setQueueInfo(tokenInfo);
      const tokenSpecialists = Array.isArray(tokenInfo.selectable_specialists)
        ? tokenInfo.selectable_specialists
        : [];
      setAvailableSpecialists(tokenSpecialists);

      if (tokenInfo.status === 'before_start_time') {
        setQueueInfo(tokenInfo);
        setStep('waiting');
        setIsSpecialistsLoading(false);
        return;
      }

      if (!tokenInfo.queue_active || tokenInfo.allowed === false) {
        setError(tokenInfo.message || QUEUE_JOIN_MESSAGES.registrationUnavailable);
        setStep('error');
        setIsSpecialistsLoading(false);
        return;
      }

      await startJoinSession();

    } catch (error: unknown) {
      setAvailableSpecialists([]);
      setIsSpecialistsLoading(false);
      setError(getApiErrorMessage(error, QUEUE_JOIN_MESSAGES.qrTokenUnavailable));
      setStep('error');
    }
  }, [getApiErrorMessage, startJoinSession, legacyToken]);

  // Загрузка информации о токене при монтировании
  useEffect(() => {
    // RQ-18: the permanent-address route has its own boot below — the legacy
    // QR-token boot must never run in direction mode.
    if (directionMode) {
      return;
    }
    if (!legacyToken) {
      setSessionToken(null);
      setQueueInfo(null);
      setAvailableSpecialists([]);
      setIsSpecialistsLoading(false);
      setError(MISSING_QUEUE_TOKEN_MESSAGE);
      setStep('error');
      return;
    }

    // ✅ Пытаемся восстановить session_token из localStorage
    const savedSessionToken = localStorage.getItem(`queue_session_${legacyToken}`);
    if (savedSessionToken) {
      setSessionToken(savedSessionToken);
    }
    loadTokenInfo();
  }, [legacyToken, loadTokenInfo, directionMode]);

  // RQ-18 (S-15, §8/§10): the ONLY boot of the permanent-address route —
  //   public_code → ONE public start-session → session_token + queue_info
  //   → the EXISTING QueueJoin state machine.
  // Forbidden (and pinned in tests): a second start-session from
  // StrictMode/rerender; the legacy startQueueJoinSession(session_token)
  // mis-call; any clinic-wide QR-token fallback.
  const runDirectionStart = useCallback(async () => {
    if (!directionCode) {
      return;
    }
    // RQ-18 follow-up (P2-2): a code CHANGE inside one route instance must
    // drop the PREVIOUS direction's whole client context — session, result
    // and advisories. The typed form is NOT reset here: each code owns its
    // own draft key, and the guarded load effect (formStorageKey change)
    // swaps in the new code's own draft — wiping here would race the load
    // effect and destroy a just-restored draft on remounts (pinned).
    // A same-code re-entry (StrictMode skip, error-screen retry) keeps the
    // patient's context intact.
    const isNewCode = directionStartRef.current !== directionCode;
    directionStartRef.current = directionCode;
    // RQ-18 follow-up round-2 (P1): this start is bound to its request
    // epoch — a LATE response for a superseded code (/q/A answered after
    // /q/B already booted) is dropped in try/catch/finally and can never
    // overwrite the freshly booted direction.
    const epoch = ++directionEpochRef.current;
    if (isNewCode) {
      setSessionToken(null);
      setQueueInfo(null);
      setDirectionInfo(null);
      setSessionExpiresAt(null);
      setResult(null);
      setSubmitResultUnknown(false);
      setShowSessionConsumedAdvisory(false);
      setSelectedSpecialists([]);
      // RQ-18 follow-up round-3 (P1): a NEW direction is the explicit
      // start-over — the previous code's complete attempt must not
      // forbid B's fresh session lifecycle, and its in-flight/late
      // submit attempt must neither keep B's submit disabled (a hung A
      // must not make B unusable) nor later release B's own lock.
      completeAttemptedRef.current = false;
      submitAttemptRef.current = null;
      setLoading(false);
    }
    setIsSpecialistsLoading(true);
    setDirectionUnavailable(false);
    setError(null);
    setStep('loading');
    try {
      const res = await startPublicDirectionSession(directionCode);
      // Out-of-order responses: A answered after B booted — drop it.
      if (epoch !== directionEpochRef.current || directionCode !== directionStartRef.current) {
        return;
      }
      const nextQueueInfo: QueueJoinPageInfo = (res.queue_info ?? {}) as QueueJoinPageInfo;
      const selectableSpecialists: QueueSpecialist[] = Array.isArray(nextQueueInfo.selectable_specialists)
        ? nextQueueInfo.selectable_specialists
        : [];

      setSessionToken(res.session_token);
      setSessionExpiresAt(res.expires_at ?? null);
      setQueueInfo(nextQueueInfo);
      setAvailableSpecialists(selectableSpecialists);
      setDirectionInfo(res.direction);
      // Direction mode NEVER enters the clinic-wide specialist selector:
      // the session can complete ONLY with the typed profile choice of its
      // own direction (backend pin §3.1(а) RQ-16.d), which is attached at
      // submit time. The info step shows the direction composition.
      setStep('info');
    } catch (error: unknown) {
      // A late failure of a superseded start must not touch B's state either.
      if (epoch !== directionEpochRef.current || directionCode !== directionStartRef.current) {
        return;
      }
      const status = Number((error as HttpApiError | null)?.response?.status ?? 0);
      setAvailableSpecialists([]);
      setSessionToken(null);
      setQueueInfo(null);
      if (status === 404) {
        // §11: ONE anonymous unavailable state — the server detail is already
        // anonymized, and the UI keeps a single readable refusal regardless.
        setDirectionUnavailable(true);
        setError(QUEUE_JOIN_MESSAGES.directionUnavailable);
      } else {
        setError(getApiErrorMessage(error, QUEUE_JOIN_MESSAGES.directionUnavailable));
      }
      setStep('error');
    } finally {
      if (epoch === directionEpochRef.current && directionCode === directionStartRef.current) {
        setIsSpecialistsLoading(false);
      }
    }
  }, [directionCode, getApiErrorMessage]);

  useEffect(() => {
    if (!directionMode) {
      return;
    }
    // RQ-18 follow-up (P2-2): the guard compares CODES. StrictMode's dev
    // double-invoke re-runs this effect with the SAME code → skipped; a
    // changed :publicCode param inside the same route instance re-runs it
    // with the NEW code → the previous direction's session is dropped and
    // B's session starts (no stale A session under a B URL).
    if (directionStartRef.current === directionCode) {
      return;
    }
    void runDirectionStart();
  }, [directionMode, directionCode, runDirectionStart]);

  // Обратный отсчет до открытия очереди
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined;

    if (step === 'waiting' && queueInfo?.minutes_until_open) {
      setCountdown(queueInfo.minutes_until_open * 60); // переводим в секунды

      interval = setInterval(() => {
        setCountdown(prev => {
          if (prev === null || prev <= 1) {
            // Время истекло, перезагружаем информацию
            loadTokenInfo();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }

    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [step, queueInfo?.minutes_until_open, loadTokenInfo]);

  const handleFormSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!String(formData.patientName ?? '').trim() || !String(formData.phone ?? '').trim()) {
      setError(QUEUE_JOIN_MESSAGES.requiredFields);
      return;
    }

    // RQ-18 follow-up round-3 (P1): claim the attempt lock BEFORE any
    // await — `loading` alone cannot protect the submit, because the
    // disabled attribute only flips after a re-render. A second click
    // while the first attempt is in flight returns immediately: one
    // renewal and one complete — never two sessions.
    if (submitAttemptRef.current) {
      return;
    }
    // RQ-18 follow-up round-2 (P1): the complete answer is bound to the
    // request epoch — a LATE complete for a superseded direction must
    // never render A's ticket under B's URL. Captured before any await
    // (the transparent renewal below does NOT move the epoch).
    const submitEpoch = directionEpochRef.current;
    const attempt = { epoch: submitEpoch, code: directionCode };
    submitAttemptRef.current = attempt;
    setLoading(true);

    // ✅ Проверяем наличие session_token
    let currentSessionToken = sessionToken;

    // RQ-18 follow-up (P1-2): client-known expiry — the direction session
    // lives 15 minutes; a token that is ALREADY expired at submit time is
    // renewed transparently BEFORE the first business attempt (a session
    // start duplicates no business action) and the typed form stays
    // exactly as the patient left it. A merely missing token is renewed
    // the same way (§10 safe session-start retry). A token rejected AFTER
    // a complete attempt follows the RQ-10 honesty contract — no automatic
    // renewal there, because the first attempt's result may be unknown.
    const directionSessionKnownExpired = Boolean(
      currentSessionToken &&
        directionMode &&
        sessionExpiresAt &&
        Date.parse(sessionExpiresAt) <= Date.now(),
    );

    // RQ-18 follow-up round-3 (P1): the renewal gate now also checks
    // completeAttemptedRef — once a complete request has been SENT, the
    // first attempt's business result is unknown (the response may have
    // been lost), and minting a fresh session would bypass the one-shot
    // «used session → reconcile» contract and duplicate the attempt.
    if (
      directionMode &&
      !completeAttemptedRef.current &&
      (!currentSessionToken || directionSessionKnownExpired)
    ) {
      // RQ-18 (§10): safe session-start retry — the direction start-session
      // creates a fresh short-lived session (no business action duplicated).
      // Round-2 (P1): bound to the current epoch — if the direction was
      // superseded while the renewal was in flight, the submit aborts
      // silently (the user is already on another direction's flow).
      const renewalEpoch = directionEpochRef.current;
      try {
        const res = await startPublicDirectionSession(directionCode as string);
        if (
          renewalEpoch !== directionEpochRef.current ||
          directionStartRef.current !== directionCode
        ) {
          return;
        }
        currentSessionToken = res.session_token;
        setSessionToken(res.session_token);
        setSessionExpiresAt(res.expires_at ?? null);
        setQueueInfo((res.queue_info ?? {}) as QueueJoinPageInfo);
        setDirectionInfo(res.direction);
        // The renewal is transparent: the patient stays on the form step
        // with their typed context and the submit proceeds below.
      } catch (error: unknown) {
        if (
          renewalEpoch !== directionEpochRef.current ||
          directionStartRef.current !== directionCode
        ) {
          return;
        }
        const status = Number((error as HttpApiError | null)?.response?.status ?? 0);
        if (status === 404) {
          setDirectionUnavailable(true);
          setError(QUEUE_JOIN_MESSAGES.directionUnavailable);
        } else {
          setError(getApiErrorMessage(error, QUEUE_JOIN_MESSAGES.directionUnavailable));
        }
        setStep('error');
        // Round-3 (P1): this attempt is still current — release our lock.
        submitAttemptRef.current = null;
        setLoading(false);
        return;
      }
    }

    if (!currentSessionToken) {
      // Пытаемся восстановить из localStorage
      currentSessionToken = localStorage.getItem(`queue_session_${legacyToken}`);

      if (!currentSessionToken) {
        // Если нет сохраненной сессии, создаем новую
        setError(QUEUE_JOIN_MESSAGES.sessionExpired);
        await startJoinSession();
        currentSessionToken = sessionToken;
        if (!currentSessionToken) {
          setError(QUEUE_JOIN_MESSAGES.sessionCreateFailed);
          // Round-3 (P1): legacy flow — release the lock on failure.
          submitAttemptRef.current = null;
          setLoading(false);
          return;
        }
      } else {
        setSessionToken(currentSessionToken);
      }
    }

    setError(null);

    try {
      // Валидация данных перед отправкой
      const trimmedPatientName = String(formData.patientName ?? '').trim();
      const trimmedPhone = String(formData.phone ?? '').trim();

      if (trimmedPatientName.length < 2) {
        setError(QUEUE_JOIN_MESSAGES.nameTooShort);
        setLoading(false);
        return;
      }

      if (trimmedPatientName.length > 200) {
        setError(QUEUE_JOIN_MESSAGES.nameTooLong);
        setLoading(false);
        return;
      }

      // ✅ ИСПРАВЛЕНО: Валидация узбекского номера (998 + 9 цифр = 12 цифр)
      const cleanPhone = trimmedPhone.replace(/\D/g, '');
      let normalizedPhone = cleanPhone;

      if (normalizedPhone.startsWith('8')) {
        normalizedPhone = '998' + normalizedPhone.slice(1);
      }
      if (!normalizedPhone.startsWith('998') && normalizedPhone.length > 0) {
        if (normalizedPhone.startsWith('9')) {
          normalizedPhone = '998' + normalizedPhone;
        } else {
          normalizedPhone = '998' + normalizedPhone;
        }
      }

      // Узбекский номер должен быть 12 цифр (998 + 9 цифр)
      if (normalizedPhone.length < 12) {
        setError(QUEUE_JOIN_MESSAGES.phoneTooShort);
        setLoading(false);
        return;
      }

      if (normalizedPhone.length > 12) {
        setError(QUEUE_JOIN_MESSAGES.phoneTooLong);
        setLoading(false);
        return;
      }

      if (!currentSessionToken) {
        setError(QUEUE_JOIN_MESSAGES.missingSessionToken);
        setLoading(false);
        return;
      }

      // Подготавливаем данные запроса
      // ✅ ИСПРАВЛЕНО: Используем уже нормализованный номер из валидации
      const requestBody: Record<string, unknown> = {
        session_token: currentSessionToken,
        patient_name: trimmedPatientName,
        phone: normalizedPhone, // ✅ Отправляем нормализованный номер (12 цифр: 998XXXXXXXXX)
        telegram_id: formData.telegramId ? parseInt(String(formData.telegramId ?? '')) : null
      };

      // Если выбраны специалисты (общий QR), добавляем их в запрос
      if (directionMode && directionInfo) {
        // RQ-18 (§8): the direction session completes with the TYPED PROFILE
        // choice of its own direction — the canonical resolver routes it to
        // the right owner (resource surface / least-loaded eligible doctor).
        // Doctor/untyped choices are rejected server-side for qdir sessions.
        requestBody.specialist_ids = [directionInfo.profile_id];
        requestBody.specialist_entity_types = ['profile'];
      } else if (selectedSpecialists && selectedSpecialists.length > 0) {
        requestBody.specialist_ids = selectedSpecialists;
        // RQ-09.b (D-01): тип сущности передаётся явно — тип не выводится
        // на сервере из совпадения числового ID (Doctor.id и QueueProfile.id
        // — разные пространства идентификаторов).
        const entityTypeById = new Map(
          availableSpecialists.map((s) => [String(s.id), s.entity_type ?? 'doctor'])
        );
        requestBody.specialist_entity_types = selectedSpecialists.map(
          (id) => entityTypeById.get(String(id)) ?? 'doctor'
        );
      }

      // RQ-18 follow-up round-2 (P1): bound to the submit epoch (captured
      // above, before the request).
      // RQ-18 follow-up round-3 (P1): the attempt flag goes up BEFORE the
      // request — from this moment the result is unknown, whatever happens
      // to the response (a lost answer must never trigger a renewal).
      completeAttemptedRef.current = true;
      const joinResult = await completeQueueJoinSession(requestBody);
      if (
        directionMode &&
        (submitEpoch !== directionEpochRef.current ||
          directionStartRef.current !== directionCode)
      ) {
        return;
      }
      setResult(joinResult as unknown as QueueJoinResultLocal);
      // ✅ Очищаем session_token из localStorage после успешного присоединения
      localStorage.removeItem(`queue_session_${legacyToken}`);
      if (formStorageKey) {
        draftRemove(formStorageKey);
        setPendingDraft(null);
      }

      // ✅ Отправляем событие обновления очереди для автоматического обновления таблицы
      if (joinResult.success) {
        // Определяем specialty из результата (entries содержит department)
        const firstEntry: QueueJoinResultEntry | undefined = (joinResult as unknown as QueueJoinResultLocal).entries?.[0];
        let specialty: string | null = firstEntry?.department ||
          firstEntry?.specialty ||
          queueInfo?.specialty ||
          null;

        // Нормализуем specialty и определяем departmentKey для соответствия с RegistrarPanel
        let departmentKey: string | null = null;
        if (specialty) {
          const normalized = specialty.toLowerCase();
          if (normalized === 'cardio' || normalized === 'cardiology') {
            specialty = 'cardiology';
            departmentKey = 'cardio';
          } else if (normalized === 'derma' || normalized === 'dermatology') {
            specialty = 'dermatology';
            departmentKey = 'derma';
          } else if (normalized === 'dentist' || normalized === 'dentistry' || normalized === 'stomatology') {
            specialty = 'stomatology';
            departmentKey = 'dental'; // ✅ Вкладка называется 'dental', а не 'stomatology'
          } else if (normalized === 'lab' || normalized === 'laboratory') {
            specialty = 'laboratory';
            departmentKey = 'lab';
          }
        }

        // Отправляем событие для немедленного обновления таблицы
        // Используем refreshAll для гарантированного обновления всех очередей
        const eventDetail = {
          action: 'refreshAll', // Обновляем все очереди
          specialty: specialty,
          departmentKey: departmentKey, // ✅ Добавляем departmentKey для правильной фильтрации
          entry: firstEntry || joinResult,
          timestamp: new Date().toISOString(),
          source: 'queueJoin'
        };

        window.dispatchEvent(new CustomEvent('queueUpdated', {
          detail: eventDetail
        }));

        // Дополнительно отправляем событие entryAdded для логирования
        if (firstEntry) {
          window.dispatchEvent(new CustomEvent('queueUpdated', {
            detail: {
              action: 'entryAdded',
              specialty: specialty,
              entry: firstEntry,
              timestamp: new Date().toISOString(),
              source: 'queueJoin'
            }
          }));
        }

        // ✅ Дополнительно: сохраняем флаг в localStorage для проверки обновления
        localStorage.setItem('lastQueueJoin', JSON.stringify({
          timestamp: new Date().toISOString(),
          specialty: specialty,
          departmentKey: departmentKey, // ✅ Сохраняем departmentKey для fallback механизма
          entry: firstEntry
        }));
      }

      setSubmitResultUnknown(false);
      setShowSessionConsumedAdvisory(false);
      setStep('success');

    } catch (error: unknown) {
      // Round-2 (P1): a late failure of a superseded submit must not paint
      // errors onto the freshly booted direction.
      if (
        directionMode &&
        (submitEpoch !== directionEpochRef.current ||
          directionStartRef.current !== directionCode)
      ) {
        return;
      }
      setError(getApiErrorMessage(error, QUEUE_JOIN_MESSAGES.joinFailed));
      if (isNetworkClassSubmitError(error)) {
        // RQ-10 (S-08): ответ потерян — результат отправки неизвестен.
        setSubmitResultUnknown(true);
      } else if (submitResultUnknown) {
        // Повтор после потери ответа отклонен сервером (сессия уже использована
        // или истекла): запись могла быть создана первой попыткой — показываем
        // честный путь обращения вместо вводящего «сессия не найдена».
        setShowSessionConsumedAdvisory(true);
      }
    } finally {
      // RQ-18 follow-up round-3 (P1): only the CURRENT page's own attempt
      // may release the lock (identity check — the ref is either this
      // attempt's object, a newer attempt's, or null after a code
      // change). A late finally of a superseded direction must never
      // re-enable the new page's submit mid-flight, and a hung attempt's
      // lock is invalidated by the new code's boot instead.
      if (submitAttemptRef.current === attempt) {
        submitAttemptRef.current = null;
        setLoading(false);
      }
    }
  };

  const handleInputChange = (field: string, value: unknown) => {
    if (error) {
      setError(null);
    }
    if (pendingDraft) {
      // Round-2 (P1): typing supersedes the found draft — discard it for
      // good (no silent double-ownership of the device's draft slot).
      setPendingDraft(null);
      if (formStorageKey) {
        draftRemove(formStorageKey);
      }
    }
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  // RQ-18 follow-up round-2 (P1): explicit draft-owner confirmation —
  // restore applies the held draft; discard erases it from the device.
  const restoreFoundDraft = () => {
    if (!pendingDraft) {
      return;
    }
    setFormData({ ...pendingDraft });
    setPendingDraft(null);
  };
  const discardFoundDraft = () => {
    setPendingDraft(null);
    if (formStorageKey) {
      draftRemove(formStorageKey);
    }
    setFormData({ patientName: '', phone: '', telegramId: '' });
  };

  // RQ-18 follow-up round-2 (P1): leaving the route discards the draft —
  // no PHI may survive an intentional exit to the home page.
  const goHome = () => {
    if (directionCode && formStorageKey) {
      draftRemove(formStorageKey);
    }
    setPendingDraft(null);
    navigate('/');
  };

  // ✅ Функция форматирования узбекского номера телефона
  const formatUzbekPhone = (value: string): string => {
    // Удаляем все нецифровые символы
    const numbers = value.replace(/\D/g, '');

    // Если начинается с 8, заменяем на 998
    let cleanNumber = numbers;
    if (cleanNumber.startsWith('8')) {
      cleanNumber = '998' + cleanNumber.slice(1);
    }

    // Если не начинается с 998, добавляем 998
    if (!cleanNumber.startsWith('998') && cleanNumber.length > 0) {
      // Если начинается с 9 (без кода страны), добавляем 998
      if (cleanNumber.startsWith('9')) {
        cleanNumber = '998' + cleanNumber;
      } else {
        cleanNumber = '998' + cleanNumber;
      }
    }

    // Ограничиваем до 12 цифр (998 + 9 цифр)
    cleanNumber = cleanNumber.slice(0, 12);

    // Форматируем в маску +998 XX XXX XX XX
    if (cleanNumber.length === 0) return '';
    if (cleanNumber.length <= 3) return `+${cleanNumber}`;
    if (cleanNumber.length <= 5) return `+998 (${cleanNumber.slice(3)}`;
    if (cleanNumber.length <= 8) return `+998 (${cleanNumber.slice(3, 5)}) ${cleanNumber.slice(5)}`;
    if (cleanNumber.length <= 10) return `+998 (${cleanNumber.slice(3, 5)}) ${cleanNumber.slice(5, 8)}-${cleanNumber.slice(8)}`;
    return `+998 (${cleanNumber.slice(3, 5)}) ${cleanNumber.slice(5, 8)}-${cleanNumber.slice(8, 10)}-${cleanNumber.slice(10)}`;
  };

  // ✅ Обработчик изменения телефона с форматированием
  const handlePhoneChange = (e: ChangeEvent<HTMLInputElement>) => {
    const input = e.target.value;
    const formatted = formatUzbekPhone(input);
    if (error) {
      setError(null);
    }
    if (pendingDraft) {
      // Round-2 (P1): typing supersedes the found draft — discard it.
      setPendingDraft(null);
      if (formStorageKey) {
        draftRemove(formStorageKey);
      }
    }

    // Обновляем состояние с отформатированным значением для отображения
    setFormData(prev => ({
      ...prev,
      phone: formatted
    }));
  };

  const formatWaitTime = (minutes: number): string => {
    if (minutes < 60) {
      return t('misc.qj_wait_minutes', { minutes });
    }
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return t('misc.qj_wait_hours_minutes', { hours, mins });
  };

  const formatCountdown = (seconds: number | null): string => {
    if (!seconds) return '00:00:00';

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0) {
      return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
      return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
  };

  const pageBaseStyle = {
    background: 'var(--mac-gradient-window)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
  };

  const glassCardStyle = {
    background: 'var(--mac-card-bg)',
    borderRadius: 'var(--mac-radius-xl)',
    boxShadow: 'var(--mac-main-shell-shadow)',
    border: '1px solid var(--mac-card-border)',
    padding: 'var(--mac-spacing-8) var(--mac-spacing-6)'
  };

  const titleStyle = {
    fontSize: 'var(--mac-font-size-2xl)',
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-text-primary)',
    marginBottom: 'var(--mac-spacing-2)',
    letterSpacing: '-0.02em'
  };

  const bodyTextStyle = {
    fontSize: 'var(--mac-font-size-lg)',
    color: 'var(--mac-text-secondary)',
    lineHeight: '1.5'
  };

  const mutedCaptionStyle = {
    fontSize: 'var(--mac-font-size-sm)',
    color: 'var(--mac-text-tertiary)',
    fontWeight: 'var(--mac-font-weight-medium)'
  };

  const statusActionStackStyle = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--mac-spacing-3)'
  };

  const recoveryButtonBaseStyle = {
    width: '100%',
    padding: 'var(--mac-spacing-4) var(--mac-spacing-6)',
    borderRadius: 'var(--mac-radius-lg)',
    border: 'none',
    fontSize: 'var(--mac-font-size-xl)',
    fontWeight: 'var(--mac-font-weight-semibold)',
    cursor: 'pointer',
    transition: 'background 0.2s ease, box-shadow 0.2s ease'
  };

  const primaryRecoveryButtonStyle = {
    ...recoveryButtonBaseStyle,
    background: 'var(--mac-accent-blue)',
    color: 'var(--mac-text-on-accent)',
    boxShadow: '0 4px 12px color-mix(in srgb, var(--mac-accent), transparent 70%)'
  };

  const dangerRecoveryButtonStyle = {
    ...recoveryButtonBaseStyle,
    background: 'var(--mac-error)',
    color: 'var(--mac-text-on-accent)',
    boxShadow: '0 4px 12px color-mix(in srgb, var(--mac-error), transparent 70%)'
  };

  const successRecoveryButtonStyle = {
    ...recoveryButtonBaseStyle,
    background: 'var(--mac-success)',
    color: 'var(--mac-text-on-accent)',
    boxShadow: '0 4px 12px color-mix(in srgb, var(--mac-success), transparent 70%)'
  };

  // Компонент загрузки - macOS стиль
  if (step === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 qj-page-base">
        <div className="max-w-md w-full text-center qj-glass-card">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4 qj-spinner"></div>
          <h2 className="qj-title">{t('misc.qj_loading_title')}</h2>
          <p className="qj-body-text">{t('misc.qj_loading_info')}</p>
        </div>
      </div>
    );
  }

  // Компонент ошибки - macOS стиль
  if (step === 'error') {
    return (
      <main className="min-h-screen flex items-center justify-center p-4 qj-page-base" aria-labelledby="queue-join-error-title">
        <div
          className="max-w-md w-full text-center qj-glass-card"
          aria-describedby="queue-join-error-message"
          data-testid={directionUnavailable ? 'qj-direction-unavailable' : undefined}
        >
          <AlertCircle style={{
            width: '64px',
            height: '64px',
            color: 'var(--mac-error)',
            margin: '0 auto 16px'
          }} aria-hidden="true" />
          <h2 id="queue-join-error-title" className="qj-title">{t('common.error')}</h2>
          <p className="qj-body-text-mb6" id="queue-join-error-message" role="alert" aria-live="assertive">{error}</p>
          <div className="qj-action-stack">
            <button
              type="button"
              onClick={() => {
                setError(null);
                if (directionMode) {
                  // safe session-start retry (no business action duplicated)
                  void runDirectionStart();
                } else {
                  loadTokenInfo();
                }
              }}
              className="qj-recovery-btn qj-recovery-btn-primary"
            >
              {t('misc.qj_retry_btn')}
            </button>
            <button
              type="button"
              onClick={goHome}
              className="qj-recovery-btn qj-recovery-btn-danger"
            >
              {t('misc.qj_home_btn')}
            </button>
          </div>
        </div>
      </main>
    );
  }

  // Компонент ожидания открытия очереди - macOS стиль
  if (step === 'waiting') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 qj-page-base">
        <div className="max-w-md w-full text-center qj-glass-card">
          <Clock style={{
            width: '64px',
            height: '64px',
            color: 'var(--mac-warning)',
            margin: '0 auto 20px',
            animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
          }} />
          <h2 style={{
            fontSize: 'var(--mac-font-size-3xl)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-3)',
            letterSpacing: '-0.02em'
          }}>{t('misc.qj_waiting_title')}</h2>
          <p className="qj-body-text-mb6">
            {t('misc.qj_waiting_will_open_at', { time: queueInfo?.start_time })}
          </p>

          {/* Обратный отсчет - macOS стиль */}
          <div className="qj-countdown-box">
            <div style={{
              fontSize: '44px',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-warning)',
              marginBottom: 'var(--mac-spacing-2)',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, "Courier New", monospace',
              letterSpacing: '0.02em'
            }}>
              {formatCountdown(countdown)}
            </div>
            <p className="qj-muted-caption">{t('misc.qj_waiting_until_open')}</p>
          </div>

          {/* Информация о враче и кабинете - macOS стиль */}
          <div className="qj-info-list">
            <div className="qj-info-row">
              <div className="flex items-center">
                <User style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)', marginRight: 'var(--mac-spacing-2)' }} />
                <span className="qj-info-label">{t('misc.qj_label_specialist')}</span>
              </div>
              <span className="qj-info-value">{queueInfo?.specialist_name}</span>
            </div>

            <div className="qj-info-row">
              <div className="flex items-center">
                <MapPin style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)', marginRight: 'var(--mac-spacing-2)' }} />
                <span className="qj-info-label">{t('misc.qj_label_department')}</span>
              </div>
              <span className="qj-info-value">{queueInfo?.department_name}</span>
            </div>

            <div className="qj-info-row-accent">
              <div className="flex items-center">
                <Calendar style={{ width: '18px', height: '18px', color: 'var(--mac-accent-blue)', marginRight: 'var(--mac-spacing-2)' }} />
                <span className="qj-info-label-accent">{t('misc.qj_label_appointment_day')}</span>
              </div>
              <span style={{ fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-accent-blue)' }}>
                {queueInfo?.target_date ? new Date(queueInfo.target_date).toLocaleDateString('ru-RU', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric'
                }) : t('misc.qj_today')}
              </span>
            </div>
          </div>

          <div className="qj-hint">
            <p >{t('misc.qj_waiting_keep_open')}</p>
            <p>{t('misc.qj_waiting_auto_redirect')}</p>
          </div>

          <div className="flex gap-3">
            <button
              onClick={goHome}
              className="qj-btn-secondary"
              onMouseEnter={(e) => e.currentTarget.style.background = 'color-mix(in srgb, var(--mac-text-tertiary), transparent 82%)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'color-mix(in srgb, var(--mac-text-tertiary), transparent 88%)'}
            >
              {t('misc.qj_home_btn')}
            </button>
            <button
              onClick={loadTokenInfo}
              className="qj-btn-primary"
              onMouseEnter={(e) => e.currentTarget.style.background = 'var(--mac-accent-blue-hover)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'var(--mac-accent-blue)'}
            >
              {t('misc.qj_refresh_btn')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Компонент успешного присоединения - macOS стиль
  if (step === 'success') {
    // RQ-10 (S-08): честное разделение успешных талонов и неудачных направлений.
    // Backend complete_join_session_multiple: success = len(entries) > 0,
    // errors — список { specialist_id, error } для неуспешных направлений.
    const hasEntriesShape = Array.isArray(result?.entries);
    const successEntries: QueueJoinResultEntry[] = hasEntriesShape
      ? ((result?.entries ?? []) as QueueJoinResultEntry[])
      : [];
    const failedEntries = result?.errors ?? [];
    // Частичный результат (успех + ошибки) и >1 талона рендерятся списком;
    // одиночный талон без ошибок сохраняет прежний крупный номер.
    const isMultiple = successEntries.length > 1 || failedEntries.length > 0;
    // Одиночный талон из entries: top-level queue_number в multi-ответе
    // отсутствует — берем номер из первой записи.
    const singleEntryNumber =
      result?.queue_number ??
      successEntries[0]?.queue_number ??
      successEntries[0]?.number;

    // RQ-18 follow-up (P2-1): multi-result payload carries the ticket
    // metrics INSIDE entries[0] (top-level queue_length / estimated_wait_time /
    // specialist_name do not exist in that shape) — the single-entry view
    // must fall back to them, otherwise a direction ticket shows a
    // fabricated «−1 впереди» and hides the wait time and owner name.
    const singleEntry = successEntries[0];
    const singleWaitTime =
      result?.estimated_wait_time ?? singleEntry?.estimated_wait_time;
    // RQ-18 follow-up round-2 (P2): «перед вами» = live count of patients
    // ahead (queue_length_before from the backend) — NOT ticket-number − 1.
    // Numbering may start at 100, have gaps, or include served/cancelled
    // patients, so the ticket number and the waiting count are not
    // interchangeable (queue_number=100 with queue_length=0 must show 0).
    const singleQueueLength =
      result?.queue_length ?? singleEntry?.queue_length;
    // RQ-18 follow-up (P1-1/P2-1): in direction mode the ticket belongs to
    // the DIRECTION — label it with the direction title, never the raw
    // internal department code (qdir:*) or the clinic-wide sentinel name.
    const singleSpecialistLabel = directionMode
      ? directionInfo?.title ?? null
      : result?.specialist_name ?? singleEntry?.specialist_name ?? null;

    // Подпись неудачного направления: по выбранному специалисту, иначе по id.
    const failedDirectionLabel = (specialistId: number | string | undefined): string => {
      const match = availableSpecialists.find(
        (s) => s.id !== undefined && Number(s.id) === Number(specialistId)
      );
      if (match) {
        return formatSpecialistLabel(match);
      }
      return t('misc.qj_failed_direction_fallback', { id: String(specialistId ?? '—') });
    };

    // RQ-10 (S-08): 0 успешных записей не называется успехом.
    const successCount = successEntries.length;
    const successTitle =
      successCount === 0
        ? t('misc.qj_join_failed')
        : failedEntries.length > 0
          ? t('misc.qj_success_partial_title')
          : successCount > 1
            ? t('misc.qj_success_multiple_title')
            : t('misc.qj_success_single_title');

    const getDepartmentName = (specialty: string | null | undefined): string => {
      const normalized = (specialty || '').toLowerCase();
      if (normalized === 'cardio' || normalized === 'cardiology') return t('misc.qj_dept_cardiology');
      if (normalized === 'derma' || normalized === 'dermatology') return t('misc.qj_dept_dermatology');
      if (normalized === 'dentist' || normalized === 'dentistry' || normalized === 'stomatology') return t('misc.qj_dept_dentistry');
      if (normalized === 'lab' || normalized === 'laboratory') return t('misc.qj_dept_laboratory');
      return t('misc.qj_dept_default');
    };

    const firstSuccessEntry = result?.entries?.[0];
    // RQ-18 follow-up (P1-1/P2-1): in direction mode the footer names the
    // DIRECTION (getDepartmentName cannot resolve the internal qdir:* code
    // and would fall back to a generic label).
    const departmentName = directionMode
      ? directionInfo?.title ?? ''
      : getDepartmentName(firstSuccessEntry?.department || firstSuccessEntry?.specialty);

    return (
      <main className="min-h-screen flex items-center justify-center p-4 qj-page-base" aria-labelledby="queue-join-success-title">
        <div className="max-w-md w-full text-center qj-glass-card" role="status" aria-live="polite">
          {successCount > 0 ? (
            <CheckCircle style={{
              width: '64px',
              height: '64px',
              color: 'var(--mac-success)',
              margin: '0 auto 20px'
            }} aria-hidden="true" />
          ) : (
            <AlertCircle className="qj-failed-icon" aria-hidden="true" />
          )}
          <h2 id="queue-join-success-title" className="qj-title-success">
            {successTitle}
          </h2>

          {successCount > 0 && isMultiple ? (
            // Множественная регистрация
            <>
              <div className="qj-success-box">
                <p className="qj-success-entries-title">
                  {t('misc.qj_success_registered_in', { count: successCount })}
                </p>
                <div className="qj-success-entries-list">
                  {successEntries.map((entry, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: 'var(--mac-spacing-4)',
                        background: 'color-mix(in srgb, var(--mac-card-bg), transparent 16%)',
                        borderRadius: 'var(--mac-radius-lg)',
                        border: '1px solid color-mix(in srgb, var(--mac-success), transparent 72%)'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-3)' }}>
                        <span style={{ fontSize: 'var(--mac-font-size-3xl)' }}>{entry.icon || null}</span>
                        <div>
                          <div style={{ fontSize: 'var(--mac-font-size-lg)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                            {entry.specialist_name || entry.department || t('misc.qj_specialist_n', { n: idx + 1 })}
                          </div>
                          <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', marginTop: 'var(--mac-spacing-1)' }}>
                            {t('misc.qj_time_value', { value: entry.queue_time ? formatRegistrarTime(entry.queue_time, 'ru-RU') : '—' })}
                          </div>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: 'var(--mac-font-size-3xl)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-success)' }}>№{entry.queue_number || entry.number || '—'}</div>
                        <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)' }}>{t('misc.qj_in_queue')}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            // Одиночная регистрация
            <>
              <div className="qj-success-box-lg">
                <div className="qj-success-number">
                  №{String(singleEntryNumber ?? '')}
                </div>
                <p className="qj-success-label">{t('misc.qj_your_number')}</p>
              </div>

              <div className="qj-info-list">
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                  background: 'var(--mac-bg-secondary)',
                  borderRadius: 'var(--mac-radius-lg)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <Users style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)', marginRight: 'var(--mac-spacing-2)' }} />
                    <span className="qj-info-label">{t('misc.qj_ahead_of_you')}</span>
                  </div>
                  {/* RQ-18 follow-up round-2 (P2): «перед вами» is the
                      backend-provided queue_length (live waiting count),
                      clamped — never derived from the ticket number. */}
                  <span className="qj-info-value">{t('misc.qj_count_short', { count: Math.max(Number(singleQueueLength ?? 0), 0) })}</span>
                </div>

                {singleWaitTime != null && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                    background: 'var(--mac-bg-secondary)',
                    borderRadius: 'var(--mac-radius-lg)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <Timer style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)', marginRight: 'var(--mac-spacing-2)' }} />
                      <span className="qj-info-label">{t('misc.qj_waiting_label')}</span>
                    </div>
                    <span className="qj-info-value">{formatWaitTime(Number(singleWaitTime ?? 0))}</span>
                  </div>
                )}

                {singleSpecialistLabel && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                    background: 'var(--mac-bg-secondary)',
                    borderRadius: 'var(--mac-radius-lg)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <User style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)', marginRight: 'var(--mac-spacing-2)' }} />
                      <span className="qj-info-label">{t('misc.qj_label_specialist')}</span>
                    </div>
                    <span className="qj-info-value">{String(singleSpecialistLabel)}</span>
                  </div>
                )}
              </div>
            </>
          )}

          {successCount > 0 && (
            <div className="qj-success-footer">
              <p>{t('misc.qj_be_ready')}</p>
              <p>{t('misc.qj_we_will_notify')}</p>
              <p style={{ marginTop: 'var(--mac-spacing-3)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-accent-blue)' }}>
                {isMultiple ? t('misc.qj_view_entries_tabs') : t('misc.qj_view_entry_tab', { name: departmentName })}
              </p>
            </div>
          )}

          {failedEntries.length > 0 && (
            // RQ-10 (S-08): неудачные направления — отдельно, с причиной;
            // частичный результат не выглядит полным успехом.
            <div className="qj-failed-box">
              <p className="qj-failed-title">
                {t('misc.qj_partial_failed_title')}
              </p>
              <ul className="qj-failed-list">
                {failedEntries.map((failedEntry, idx) => (
                  <li key={idx} className="qj-failed-item">
                    <div className="qj-failed-direction">
                      {failedDirectionLabel(failedEntry.specialist_id)}
                    </div>
                    {failedEntry.error ? (
                      <div className="qj-failed-reason">
                        {String(failedEntry.error)}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button
            onClick={goHome}
            type="button"
            className="qj-recovery-btn qj-recovery-btn-success"
          >
            {t('misc.qj_ok_btn')}
          </button>
        </div>
      </main>
    );
  }

  // Основной интерфейс (info + form) - macOS стиль
  return (
    <div className="min-h-screen flex items-center justify-center p-4 qj-page-base">
      <div
        aria-live="polite"
        className="qj-sr-only"
      >
        {step === 'select-specialists' && t('misc.qj_sr_select_specialists_step')}
        {step === 'form' && t('misc.qj_sr_form_step')}
        {step === 'info' && t('misc.qj_sr_info_step')}
      </div>
      <div className="max-w-md w-full overflow-hidden qj-glass-card">

        {/* Заголовок с информацией об очереди - macOS стиль с правильным spacing */}
        <div className="text-white qj-main-header">
          <h1 className="qj-main-title">{t('misc.qj_main_title')}</h1>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div className="flex items-center" style={{ opacity: 0.95 }}>
              <MapPin style={{ width: '16px', height: '16px', marginRight: 'var(--mac-spacing-2)', flexShrink: 0 }} />
              {/* RQ-18 follow-up (P1-1): in direction mode the patient must
                  see the DIRECTION they are joining — the display SSOT is
                  the direction object, never the clinic-wide sentinel
                  queue_info fields («Клиника»). */}
              <span style={{ fontSize: 'var(--mac-font-size-base)', lineHeight: '1.4' }}>
                {directionMode
                  ? directionInfo?.title || queueInfo?.department_name || t('misc.qj_general_practice')
                  : queueInfo?.department_name || t('misc.qj_general_practice')}
              </span>
            </div>

            {/* RQ-18 follow-up (P1-1): a direction is not a specialist —
                the clinic-wide sentinel «Все специалисты» row is never
                shown on the permanent-address route. */}
            {!directionMode && (
              <div className="flex items-center" style={{ opacity: 0.9 }}>
                <User style={{ width: '16px', height: '16px', marginRight: 'var(--mac-spacing-2)', flexShrink: 0 }} />
                <span style={{ fontSize: 'var(--mac-font-size-sm)', lineHeight: '1.4' }}>{queueInfo?.specialist_name}</span>
              </div>
            )}

            {queueInfo?.target_date && (
              <div className="flex items-center" style={{
                marginTop: 'var(--mac-spacing-2)',
                paddingTop: '12px',
                borderTop: '1px solid color-mix(in srgb, var(--mac-text-on-accent), transparent 80%)',
                opacity: 0.95
              }}>
                <Calendar style={{ width: '16px', height: '16px', marginRight: 'var(--mac-spacing-2)', flexShrink: 0 }} />
                <span style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: 'var(--mac-font-weight-medium)',
                  lineHeight: '1.4'
                }}>
                  {t('misc.qj_appointment_day_value', { date: new Date(queueInfo.target_date).toLocaleDateString('ru-RU', {
                    day: 'numeric',
                    month: 'long',
                    year: 'numeric'
                  }) })}
                </span>
              </div>
            )}
          </div>
        </div>

        {step === 'select-specialists' && (
          <div className="qj-select-section">
            <div style={{
              marginBottom: 'var(--mac-spacing-6)',
              textAlign: 'center'
            }}>
              <h3 style={{
                fontSize: 'var(--mac-font-size-2xl)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                marginBottom: 'var(--mac-spacing-2)',
                letterSpacing: '-0.02em'
              }}>
                {/* P-024 fix: previously "Мутахассисларни танланг" (UZ) while the
                    rest of the screen is Russian — mixed i18n on a public kiosk flow.
                    Unified to Russian to match the surrounding copy. */}
                {t('misc.qj_select_specialists_title')}
              </h3>
              <p style={{
                color: 'var(--mac-text-secondary)',
                fontSize: 'var(--mac-font-size-lg)',
                lineHeight: '1.5',
                margin: 0
              }}>
                {t('misc.qj_select_specialists_hint')}
              </p>
            </div>

            {/* Чекбоксы специалистов */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--mac-spacing-3)',
              marginBottom: 'var(--mac-spacing-6)'
            }}>
              {isSpecialistsLoading ? (
                <div style={{
                  padding: 'var(--mac-spacing-4)',
                  textAlign: 'center',
                  color: 'var(--mac-text-secondary)',
                  fontSize: 'var(--mac-font-size-lg)'
                }}>
                  {/* UX Audit Registrar #2: унифицирован i18n — был UZ, теперь RU. */}
                  {t('misc.qj_loading_specialists')}
                </div>
              ) : availableSpecialists.length === 0 ? (
                <div style={{
                  padding: '18px 16px',
                  textAlign: 'center',
                  color: 'var(--mac-text-secondary)',
                  fontSize: 'var(--mac-font-size-base)',
                  borderRadius: 'var(--mac-radius-lg)',
                  border: '1px dashed color-mix(in srgb, var(--mac-text-secondary), transparent 72%)',
                  background: 'color-mix(in srgb, var(--mac-bg-secondary), transparent 10%)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px'
                }}>
                  <span> {/* UX Audit Registrar #2: был UZ, теперь RU. */} {t('misc.qj_no_specialists')}</span>
                  <button
                    type="button"
                    onClick={loadTokenInfo}
                    style={{
                      alignSelf: 'center',
                      background: 'var(--mac-accent-blue)',
                      color: 'var(--mac-text-on-accent)',
                      border: 'none',
                      borderRadius: 'var(--mac-radius-md)',
                      padding: '8px 14px',
                      fontSize: 'var(--mac-font-size-sm)',
                      fontWeight: 'var(--mac-font-weight-semibold)',
                      cursor: 'pointer'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'var(--mac-accent-blue-hover)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'var(--mac-accent-blue)';
                    }}
                  >
                    {t('misc.qj_refresh_btn')}
                  </button>
                </div>
              ) : (
                availableSpecialists.map(specialist => {
                  const isSelected = selectedSpecialists.includes(specialist.id);
                  return (
                    <label
                      key={specialist.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        padding: 'var(--mac-spacing-4)',
                        borderRadius: 'var(--mac-radius-lg)',
                        border: `2px solid ${isSelected ? String(specialist.color ?? '') : 'var(--mac-border)'}`,
                        background: isSelected ?
                          `color-mix(in srgb, ${String(specialist.color ?? '')}, transparent 85%)` :
                          'var(--mac-card-bg)',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                        userSelect: 'none'
                      }}
                    >
                      <Checkbox aria-label={`Select specialist: ${formatSpecialistLabel(specialist)}`} checked={isSelected} onChange={() => {
                          if (error) {
                            setError(null);
                          }
                          if (isSelected) {
                            setSelectedSpecialists(prev => prev.filter(id => id !== specialist.id));
                          } else {
                            setSelectedSpecialists(prev => [...prev, specialist.id]);
                          }
                        }}
                        style={{
                          width: '24px',
                          height: '24px',
                          marginRight: 'var(--mac-spacing-3)',
                          accentColor: String(specialist.color ?? ''),
                          cursor: 'pointer'
                        }}
                      />
                      <span style={{ fontSize: 'var(--mac-font-size-3xl)', marginRight: 'var(--mac-spacing-3)' }}>{(specialist.icon as ReactNode) ?? null}</span>
                      <span style={{
                        fontSize: 'var(--mac-font-size-xl)',
                        fontWeight: 'var(--mac-font-weight-semibold)',
                        color: isSelected ? String(specialist.color ?? '') : 'var(--mac-text-primary)'
                      }}>
                        {formatSpecialistLabel(specialist)}
                      </span>
                    </label>
                  );
                })
              )}
            </div>

            {/* Кнопка продолжить */}
            <button
              onClick={() => {
                if (selectedSpecialists.length === 0) {
                  setError(QUEUE_JOIN_MESSAGES.selectSpecialist);
                  setTimeout(() => setError(null), 3000);
                  return;
                }
                setError(null);
                setStep('form');
              }}
              disabled={selectedSpecialists.length === 0}
              style={{
                width: '100%',
                background: selectedSpecialists.length > 0 ? 'var(--mac-accent-blue)' : 'var(--mac-border)',
                color: selectedSpecialists.length > 0 ? 'var(--mac-text-on-accent)' : 'var(--mac-text-tertiary)',
                padding: 'var(--mac-spacing-4) var(--mac-spacing-6)',
                borderRadius: 'var(--mac-radius-lg)',
                border: 'none',
                fontSize: 'var(--mac-font-size-xl)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                cursor: selectedSpecialists.length > 0 ? 'pointer' : 'not-allowed',
                transition: 'all 0.2s ease',
                boxShadow: selectedSpecialists.length > 0 ? '0 4px 12px color-mix(in srgb, var(--mac-accent), transparent 70%)' : 'none'
              }}
              onMouseEnter={(e) => {
                if (selectedSpecialists.length > 0) {
                  e.currentTarget.style.background = 'var(--mac-accent-blue-hover)';
                }
              }}
              onMouseLeave={(e) => {
                if (selectedSpecialists.length > 0) {
                  e.currentTarget.style.background = 'var(--mac-accent-blue)';
                }
              }}
            >
              {t('misc.qj_continue_with_count', { count: selectedSpecialists.length })}
            </button>

            {error && (
              <div className="qj-error-banner" role="alert" aria-live="assertive">
                {error}
              </div>
            )}
          </div>
        )}

        {step === 'info' && (
          <div className="qj-select-section">
            {/* Статус очереди - macOS стиль с правильным spacing */}
            {/* RQ-18 follow-up (P1-1): in direction mode the start response
                carries NO live queue statistics — the clinic-wide builder
                emits sentinel zeros for the minted token, and the follow-up
                endpoint override replaces them with null. A fabricated
                «0 в очереди / ~0 мин» is never shown; the real numbers
                arrive with the ticket result (P2-1 normalization). If a
                future contract delivers honest per-direction stats through
                an explicit field, consuming it is a deliberate follow-up. */}
            {!directionMode && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 'var(--mac-spacing-4)',
              marginBottom: 'var(--mac-spacing-6)'
            }}>
              <div style={{
                background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-accent), transparent 88%) 0%, color-mix(in srgb, var(--mac-accent), transparent 93%) 100%)',
                borderRadius: 'var(--mac-radius-xl)',
                padding: '24px 20px',
                border: '1px solid color-mix(in srgb, var(--mac-accent), transparent 76%)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '140px'
              }}>
                <Users style={{
                  width: '32px',
                  height: '32px',
                  color: 'var(--mac-accent-blue)',
                  marginBottom: 'var(--mac-spacing-3)'
                }} />
                <div style={{
                  fontSize: '36px',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  color: 'var(--mac-accent-blue)',
                  letterSpacing: '-0.02em',
                  lineHeight: '1',
                  marginBottom: 'var(--mac-spacing-2)'
                }}>{queueInfo?.queue_length || 0}</div>
                <div style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-tertiary)',
                  fontWeight: 'var(--mac-font-weight-medium)'
                }}>{t('misc.qj_in_queue')}</div>
              </div>

              <div style={{
                background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-success), transparent 88%) 0%, color-mix(in srgb, var(--mac-success), transparent 93%) 100%)',
                borderRadius: 'var(--mac-radius-xl)',
                padding: '24px 20px',
                border: '1px solid color-mix(in srgb, var(--mac-success), transparent 76%)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '140px'
              }}>
                <Clock style={{
                  width: '32px',
                  height: '32px',
                  color: 'var(--mac-success)',
                  marginBottom: 'var(--mac-spacing-3)'
                }} />
                <div style={{
                  fontSize: '36px',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  color: 'var(--mac-success)',
                  letterSpacing: '-0.02em',
                  lineHeight: '1',
                  marginBottom: 'var(--mac-spacing-2)'
                }}>~{(queueInfo?.queue_length || 0) * 15}</div>
                <div style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-tertiary)',
                  fontWeight: 'var(--mac-font-weight-medium)'
                }}>{t('misc.qj_estimated_wait')}</div>
              </div>
            </div>
            )}

            {/* Текст и кнопка с правильными отступами */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
              gap: 'var(--mac-spacing-5)'
            }}>
              <p style={{
                color: 'var(--mac-text-secondary)',
                fontSize: 'var(--mac-font-size-lg)',
                lineHeight: '1.5',
                margin: 0,
                maxWidth: '320px'
              }}>
                {t('misc.qj_fill_form_hint')}
              </p>
              <button
                onClick={() => setStep('form')}
                style={{
                  width: '100%',
                  background: 'var(--mac-accent-blue)',
                  color: 'var(--mac-text-on-accent)',
                  padding: 'var(--mac-spacing-4) var(--mac-spacing-6)',
                  borderRadius: 'var(--mac-radius-lg)',
                  border: 'none',
                  fontSize: 'var(--mac-font-size-xl)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  boxShadow: '0 4px 12px color-mix(in srgb, var(--mac-accent), transparent 70%)'
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'var(--mac-accent-blue-hover)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'var(--mac-accent-blue)'}
              >
                {t('misc.qj_continue_btn')}
              </button>
            </div>
          </div>
        )}

        {step === 'form' && (
          <div className="qj-select-section">
            <form onSubmit={handleFormSubmit} className="qj-form">
              {/* RQ-18 follow-up round-2 (P1): a found draft is never applied
                  silently — the device may be shared, so its owner must
                  explicitly confirm; the prompt reveals no PHI. */}
              {directionMode && pendingDraft && (
                <div className="qj-draft-confirm" data-testid="qj-draft-confirm" role="status" aria-live="polite">
                  <p className="qj-draft-confirm-text" data-testid="qj-draft-confirm-text">
                    {t('misc.qj_draft_found')}
                  </p>
                  <div className="qj-draft-confirm-actions">
                    <button
                      type="button"
                      className="qj-draft-btn qj-draft-btn-primary"
                      data-testid="qj-draft-restore"
                      onClick={restoreFoundDraft}
                    >
                      {t('misc.qj_draft_restore')}
                    </button>
                    <button
                      type="button"
                      className="qj-draft-btn qj-draft-btn-secondary"
                      data-testid="qj-draft-discard"
                      onClick={discardFoundDraft}
                    >
                      {t('misc.qj_draft_discard')}
                    </button>
                  </div>
                </div>
              )}
              {/* ФИО - macOS стиль */}
              <div>
                <label
                  htmlFor="queue-patient-name"
                  className="qj-form-label"
                >
                  {t('misc.qj_form_label_full_name')}
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5" style={{ color: 'var(--mac-text-tertiary)' }} />
                  <Input
                    id="queue-patient-name"
                    name="patient_name"
                    type="text"
                    aria-label={t('misc.qj_form_aria_full_name')}
                    value={String(formData.patientName ?? '')}
                    onChange={(e) => handleInputChange('patientName', e.target.value)}
                    style={{
                      width: '100%',
                      paddingLeft: '40px',
                      paddingRight: '16px',
                      paddingTop: '12px',
                      paddingBottom: '12px',
                      border: '1px solid color-mix(in srgb, var(--mac-text-secondary), transparent 76%)',
                      borderRadius: 'var(--mac-radius-lg)',
                      fontSize: 'var(--mac-font-size-xl)',
                      fontFamily: 'inherit',
                      background: 'var(--mac-bg-secondary)',
                      transition: 'all 0.2s ease',
                      outline: 'none',
                      color: 'var(--mac-text-primary)'
                    }}
                    onFocus={(e) => {
                      e.currentTarget.style.border = '1px solid var(--mac-accent)';
                      e.currentTarget.style.boxShadow = '0 0 0 3px color-mix(in srgb, var(--mac-accent), transparent 86%)';
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.border = '1px solid color-mix(in srgb, var(--mac-text-secondary), transparent 76%)';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                    placeholder={t('misc.qj_form_placeholder_full_name')}
                    autoComplete="name"
                    autoFocus
                    aria-required="true"
                    aria-invalid={Boolean(error && !String(formData.patientName ?? '').trim())}
                    aria-describedby={error ? 'queue-join-error' : undefined}
                    required
                  />
                </div>
              </div>

              {/* Телефон - macOS стиль с форматированием */}
              <div>
                <label
                  htmlFor="queue-phone"
                  className="qj-form-label"
                >
                  {t('misc.qj_form_label_phone')}
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5" style={{ color: 'var(--mac-text-tertiary)' }} />
                  <Input
                    id="queue-phone"
                    name="phone"
                    type="tel"
                    aria-label={t('misc.qj_form_aria_phone')}
                    value={String(formData.phone ?? '')}
                    onChange={handlePhoneChange}
                    onKeyDown={(e) => {
                      // Разрешаем: цифры, Backspace, Delete, стрелки, Tab, Enter
                      const allowedKeys = [
                        'Backspace', 'Delete', 'ArrowLeft', 'ArrowRight',
                        'ArrowUp', 'ArrowDown', 'Tab', 'Enter', 'Home', 'End'
                      ];

                      if (allowedKeys.includes(e.key) || e.ctrlKey || e.metaKey) {
                        return;
                      }

                      // Разрешаем только цифры и + в начале
                      if (!/\d/.test(e.key) && !(e.key === '+' && e.currentTarget.selectionStart === 0)) {
                        e.preventDefault();
                      }
                    }}
                    onPaste={(e) => {
                      e.preventDefault();
                      if (pendingDraft) {
                        // Round-2 (P1): pasting supersedes the found draft.
                        setPendingDraft(null);
                        if (formStorageKey) {
                          draftRemove(formStorageKey);
                        }
                      }
                      const pastedText = e.clipboardData.getData('text');
                      const formatted = formatUzbekPhone(pastedText);
                      setFormData(prev => ({
                        ...prev,
                        phone: formatted
                      }));
                    }}
                    style={{
                      width: '100%',
                      paddingLeft: '40px',
                      paddingRight: '16px',
                      paddingTop: '12px',
                      paddingBottom: '12px',
                      border: '1px solid color-mix(in srgb, var(--mac-text-secondary), transparent 76%)',
                      borderRadius: 'var(--mac-radius-lg)',
                      fontSize: 'var(--mac-font-size-xl)',
                      fontFamily: 'inherit',
                      background: 'var(--mac-bg-secondary)',
                      transition: 'all 0.2s ease',
                      outline: 'none',
                      color: 'var(--mac-text-primary)'
                    }}
                    onFocus={(e) => {
                      e.currentTarget.style.border = '1px solid var(--mac-accent)';
                      e.currentTarget.style.boxShadow = '0 0 0 3px color-mix(in srgb, var(--mac-accent), transparent 86%)';
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.border = '1px solid color-mix(in srgb, var(--mac-text-secondary), transparent 76%)';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                    placeholder="+998 (90) 123-45-67"
                    autoComplete="tel"
                    inputMode="tel"
                    aria-required="true"
                    aria-invalid={Boolean(error && !String(formData.phone ?? '').trim())}
                    aria-describedby={error ? 'queue-join-error queue-phone-hint' : 'queue-phone-hint'}
                    required
                  />
                </div>
                <div id="queue-phone-hint" style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', marginTop: 'var(--mac-spacing-1)' }}>
                  {t('misc.qj_form_phone_format')}
                </div>
              </div>

              {/* Telegram ID (опционально) - macOS стиль */}
              <div>
                <label
                  htmlFor="queue-telegram-id"
                  className="qj-form-label"
                >
                  {t('misc.qj_form_label_telegram')}
                </label>
                <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', marginBottom: 'var(--mac-spacing-2)' }}>
                  {t('misc.qj_form_hint_telegram')}
                </div>
                <Input
                  id="queue-telegram-id"
                  name="telegram_id"
                  type="number"
                  aria-label={t('misc.qj_form_aria_telegram')}
                  value={String(formData.telegramId ?? '')}
                  onChange={(e) => handleInputChange('telegramId', e.target.value)}
                  style={{
                    width: '100%',
                    padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                    border: '1px solid color-mix(in srgb, var(--mac-text-secondary), transparent 76%)',
                    borderRadius: 'var(--mac-radius-lg)',
                    fontSize: 'var(--mac-font-size-xl)',
                    fontFamily: 'inherit',
                    background: 'var(--mac-bg-secondary)',
                    transition: 'all 0.2s ease',
                    outline: 'none',
                    color: 'var(--mac-text-primary)'
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.border = '1px solid var(--mac-accent)';
                    e.currentTarget.style.boxShadow = '0 0 0 3px color-mix(in srgb, var(--mac-accent), transparent 86%)';
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.border = '1px solid color-mix(in srgb, var(--mac-text-secondary), transparent 76%)';
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                  placeholder={t('misc.qj_form_placeholder_optional')}
                />
              </div>

              {error && (
                <div style={{
                  background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-error), transparent 88%) 0%, color-mix(in srgb, var(--mac-error), transparent 93%) 100%)',
                  border: '1px solid color-mix(in srgb, var(--mac-error), transparent 72%)',
                  borderRadius: 'var(--mac-radius-lg)',
                  padding: 'var(--mac-spacing-3)'
                }} id="queue-join-error" role="alert" aria-live="assertive">
                  <div className="flex items-center">
                    <AlertCircle className="h-5 w-5 mr-2" style={{ color: 'var(--mac-error)' }} />
                    <span style={{ color: 'var(--mac-error)', fontSize: 'var(--mac-font-size-base)' }}>{error}</span>
                  </div>
                  {submitResultUnknown && (
                    // RQ-10 (S-08): ответ потерян — честный статус повтора.
                    <p className="qj-error-hint">
                      {t('misc.qj_result_unknown_hint')}
                    </p>
                  )}
                  {showSessionConsumedAdvisory && (
                    // RQ-10 (S-08): повтор отклонен после потери ответа —
                    // запись могла быть создана первой попыткой.
                    <p className="qj-error-advisory">
                      {t('misc.qj_session_consumed_advisory')}
                    </p>
                  )}
                </div>
              )}

              {/* Кнопки - macOS стиль */}
              <div className="flex" style={{ gap: 'var(--mac-spacing-3)', paddingTop: '16px' }}>
                <button
                  type="button"
                  onClick={() => setStep('info')}
                  style={{
                    flex: 1,
                    background: 'color-mix(in srgb, var(--mac-text-tertiary), transparent 88%)',
                    color: 'var(--mac-accent-blue)',
                    padding: '14px 20px',
                    borderRadius: 'var(--mac-radius-lg)',
                    border: 'none',
                    fontSize: 'var(--mac-font-size-xl)',
                    fontWeight: 'var(--mac-font-weight-semibold)',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'color-mix(in srgb, var(--mac-text-tertiary), transparent 82%)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'color-mix(in srgb, var(--mac-text-tertiary), transparent 88%)'}
                >
                  {t('misc.qj_back_btn')}
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    flex: 1,
                    background: loading ? 'var(--mac-text-tertiary)' : 'var(--mac-accent-blue)',
                    color: 'var(--mac-text-on-accent)',
                    padding: '14px 20px',
                    borderRadius: 'var(--mac-radius-lg)',
                    border: 'none',
                    fontSize: 'var(--mac-font-size-xl)',
                    fontWeight: 'var(--mac-font-weight-semibold)',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    transition: 'all 0.2s ease',
                    boxShadow: loading ? 'none' : '0 4px 12px color-mix(in srgb, var(--mac-accent), transparent 70%)'
                  }}
                  onMouseEnter={(e) => !loading && (e.currentTarget.style.background = 'var(--mac-accent-blue-hover)')}
                  onMouseLeave={(e) => !loading && (e.currentTarget.style.background = 'var(--mac-accent-blue)')}
                >
                  {loading ? t('misc.qj_joining_btn') : t('misc.qj_join_btn')}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};

export default QueueJoin;
