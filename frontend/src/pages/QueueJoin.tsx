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

// RQ-18 follow-up round-5 (P1-1): NOTHING about the typed patient is
// persisted under the shared permanent code any more. The round-4 draft +
// phone-tail challenge was reviewed as insufficient: the system contract
// allows several FAMILY MEMBERS to share one phone number, so «re-enter
// the last 4 digits» verifies nothing about ownership (10,000 combos, and
// a family member legitimately knows the tail) — the restore would hand
// the previous patient's full PHI (name + phone + the fact of their
// treatment in this direction) to the next person at the shared device.
// The only fail-closed option on an anonymous surface: no PHI draft at
// all. A reload costs the patient two retyped fields; the reconcile
// attempt-state below stays (it carries no PHI and its replay is
// payload-bound server-side).

// RQ-18 follow-up round-6 (P1-3): the attempt identity must live until the
// END of the TARGET queue-day, not a fixed 24h — a permanent-address session
// started after the cutoff targets TOMORROW, so a fixed 24h TTL expired
// while the target queue-day was still running (the reconcile identity
// disappears → a fresh start can mint a second талон for the next day).
// The server now returns the honest absolute horizon per session
// (``attempt_expires_at`` = end of the target day in the clinic timezone
// + safety grace); the fixed TTL below remains ONLY the fallback for an
// older backend that does not send the horizon.
const ATTEMPT_STATE_TTL_MS = 24 * 60 * 60 * 1000;

const draftPhoneDigits = (phone: unknown): string =>
  String(phone ?? '').replace(/\D/g, '');

// Legacy (per-token) flow only — the direction flow never persists a form.
interface QueueJoinDraftData {
  patientName: string;
  phone: string;
  telegramId: string;
  [key: string]: unknown;
}

interface QueueJoinAttemptState {
  ts: number;
  publicCode: string;
  sessionToken: string;
  profileId: number | null;
  directionTitle: string | null;
  completeAttempted: boolean;
  outcomeUnknown: boolean;
  // Round-6 (P1-3): the server-computed absolute horizon (ISO-8601) of
  // this attempt's identity — end of the TARGET queue-day + grace. The
  // fixed TTL applies only when an older backend sent nothing.
  attemptExpiresAt: string | null;
}

// Round-6 (P1-3): the attempt envelope moved from sessionStorage to
// localStorage. It carries NO PHI (session token + direction metadata
// only — the round-5 review explicitly blessed longer storage for this
// shape), and sessionStorage silently destroyed the UNKNOWN-outcome
// identity on a simple TAB CLOSE — the reconcile panel vanished and a
// fresh start could duplicate the attempt. localStorage survives the
// tab; the horizon decides when the identity finally expires.
const attemptStateStorageGet = (key: string): string | null => {
  try {
    return window.localStorage.getItem(key) ?? window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
};
// Round-9 (review P2-3): the write is VERIFIED, not best-effort — the
// envelope IS the exactly-once guard for the irreversible complete, so
// a silent setItem failure (quota / disabled storage / private mode)
// must be visible to the caller. The read-back check proves the value
// actually landed in the store.
const attemptStateStorageSet = (key: string, value: string): boolean => {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    return false;
  }
  try {
    return window.localStorage.getItem(key) === value;
  } catch {
    return false;
  }
};
const attemptStateStorageRemove = (key: string): void => {
  try {
    window.localStorage.removeItem(key);
    window.sessionStorage.removeItem(key); // legacy round-5 entries
  } catch {
    /* noop */
  }
};

const attemptStateHorizonValid = (state: {
  ts: number;
  attemptExpiresAt: string | null;
}): boolean => {
  if (state.attemptExpiresAt) {
    const horizon = Date.parse(state.attemptExpiresAt);
    if (!Number.isNaN(horizon)) {
      return Date.now() <= horizon;
    }
  }
  return Date.now() - state.ts <= ATTEMPT_STATE_TTL_MS;
};

// RQ-18 follow-up round-4 (P1-2): the complete-attempt state survives a
// reload (round-6: localStorage — it also survives a TAB close; the
// envelope carries no PHI and its replay is payload-bound server-side).
// React refs alone reset on remount — a reload would silently
// mint a NEW session while the previous attempt's business outcome was
// still unknown, and the lowercase/uppercase URL alias of the same
// permanent address would reset the guard too.
//
// Round-9 (review P1-2): the attempt state is addressed PER ATTEMPT —
// key = base + '__' + sessionToken — never as ONE shared slot per
// direction. The old single slot let two tabs of the same /q/<code>
// destroy each other's recovery state (B's setItem overwrote A's
// envelope; B's success removeItem wiped the shared slot entirely, so
// A's lost-response reload lost its attempt identity). Removal deletes
// ONLY the key of the attempt that owns it.
const attemptStateKeyBase = (code: string): string => `queue_join_attempt_qdir_${code}`;
const attemptStateKeyFor = (code: string, sessionToken: string): string =>
  `${attemptStateKeyBase(code)}__${sessionToken}`;
// Round-9 (review P1-2): the per-tab owner marker (sessionStorage —
// survives a reload, dies with the tab) says WHICH outstanding attempt
// this tab adopted. A reloaded tab finds its own attempt; a reopened
// tab adopts the single outstanding one — and never destroys the
// others. Round-10 (review P1): with NO live marker SEVERAL outstanding
// envelopes are ambiguous — nothing is adopted automatically.
const attemptStateOwnerKey = (code: string): string => `queue_join_attempt_owner_qdir_${code}`;

// Round-10 (review P1): the ambiguity list labels an outstanding attempt
// by its direction and LOCAL wall-clock time — the envelope carries no
// PHI, so the label never reveals who attempted what.
const attemptTimeLabel = (ts: number): string => {
  const date = new Date(ts);
  const pad = (value: number): string => String(value).padStart(2, '0');
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const attemptStateParse = (raw: string | null): QueueJoinAttemptState | null => {
  if (!raw) return null;
  try {
    const parsed = safeJsonParse(raw) as Partial<QueueJoinAttemptState> | null;
    if (
      parsed &&
      typeof parsed === 'object' &&
      typeof parsed.ts === 'number' &&
      typeof parsed.publicCode === 'string' &&
      typeof parsed.sessionToken === 'string' &&
      attemptStateHorizonValid({
        ts: parsed.ts,
        attemptExpiresAt:
          typeof parsed.attemptExpiresAt === 'string' ? parsed.attemptExpiresAt : null,
      })
    ) {
      return {
        ts: parsed.ts,
        publicCode: parsed.publicCode,
        sessionToken: parsed.sessionToken,
        profileId: typeof parsed.profileId === 'number' ? parsed.profileId : null,
        directionTitle:
          typeof parsed.directionTitle === 'string' ? parsed.directionTitle : null,
        completeAttempted: parsed.completeAttempted === true,
        outcomeUnknown: parsed.outcomeUnknown === true,
        attemptExpiresAt:
          typeof parsed.attemptExpiresAt === 'string' ? parsed.attemptExpiresAt : null,
      };
    }
    return null;
  } catch {
    return null;
  }
};

// Round-9 (review P1-2): ONE attempt's own envelope — read / verified
// write / own-key-only removal.
const attemptStateReadFor = (
  code: string,
  sessionToken: string | null | undefined,
): QueueJoinAttemptState | null => {
  if (!code || !sessionToken) return null;
  return attemptStateParse(attemptStateStorageGet(attemptStateKeyFor(code, sessionToken)));
};
const attemptStateWriteFor = (
  code: string,
  state: QueueJoinAttemptState,
): boolean => {
  if (!code || !state.sessionToken) return false;
  return attemptStateStorageSet(
    attemptStateKeyFor(code, state.sessionToken),
    JSON.stringify(state),
  );
};
const attemptStateRemoveFor = (
  code: string,
  sessionToken: string | null | undefined,
): void => {
  if (!code || !sessionToken) return;
  attemptStateStorageRemove(attemptStateKeyFor(code, sessionToken));
};

const attemptStateOwnerGet = (code: string): string | null => {
  if (!code) return null;
  try {
    return window.sessionStorage.getItem(attemptStateOwnerKey(code));
  } catch {
    return null;
  }
};
const attemptStateOwnerSet = (code: string, sessionToken: string): void => {
  if (!code || !sessionToken) return;
  try {
    window.sessionStorage.setItem(attemptStateOwnerKey(code), sessionToken);
  } catch {
    /* best-effort — the per-tab identity marker */
  }
};
const attemptStateOwnerClear = (code: string): void => {
  if (!code) return;
  try {
    window.sessionStorage.removeItem(attemptStateOwnerKey(code));
  } catch {
    /* noop */
  }
};

// Round-9 (review P1-2): ALL outstanding attempts of a direction — the
// per-attempt keys plus the LEGACY single-slot envelope an older build
// may have left (migrated by the boot). Invalid / horizon-dead entries
// are self-healed away; the legacy VALID slot is returned as a
// candidate and re-homed by the boot only after its per-attempt write
// is verified.
const attemptStateScan = (code: string): QueueJoinAttemptState[] => {
  if (!code) return [];
  const found: QueueJoinAttemptState[] = [];
  const prefix = `${attemptStateKeyBase(code)}__`;
  const legacyKey = attemptStateKeyBase(code);
  const collect = (store: Storage, key: string) => {
    const raw = store.getItem(key);
    if (raw === null) return;
    const parsed = attemptStateParse(raw);
    if (
      parsed &&
      parsed.publicCode === code &&
      !found.some((candidate) => candidate.sessionToken === parsed.sessionToken)
    ) {
      found.push(parsed);
    } else if (!parsed) {
      // unparseable or horizon-dead — self-heal (the old
      // attemptStateRead removed exactly these on sight)
      store.removeItem(key);
    }
  };
  try {
    const storage = window.localStorage;
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index);
      if (key && (key.startsWith(prefix) || key === legacyKey)) {
        collect(storage, key);
      }
    }
    // round-5 fallback slot (sessionStorage, single-slot shape)
    collect(window.sessionStorage, legacyKey);
  } catch {
    /* storage unavailable */
  }
  return found.sort((a, b) => b.ts - a.ts);
};

// RQ-18 follow-up round-4 (P2-1): the backend now refuses an unclaimable
// join session with a machine-readable reason instead of the masked
// generic 400. Only these two reasons PROVE that nothing was created —
// only they allow the explicit start-over offer. Network-class errors
// stay an UNKNOWN outcome (no recovery that could duplicate a ticket).
const JOIN_PRE_EXECUTION_REASONS = new Set([
  'join_session_not_found',
  'join_session_expired',
  // Round-6 (P2-1): the backend PROVED the rollback — zero tickets were
  // created. The honest start-over replaces the UNKNOWN loop.
  'join_session_not_executed',
]);

const getJoinRefusalReason = (err: unknown): string | null => {
  const detail = (err as HttpApiError | null)?.response?.data?.detail;
  if (
    detail &&
    typeof detail === 'object' &&
    !Array.isArray(detail) &&
    typeof (detail as { reason?: unknown }).reason === 'string'
  ) {
    return (detail as { reason: string }).reason;
  }
  return null;
};

// Round-9 (review P2-2): the server's own SAFE domain message from a
// structured refusal ({detail: {reason, message}}) — the
// join_session_not_executed class (rollback-proven, e.g. «Очередь
// заполнена») must reach the patient verbatim instead of being
// flattened into the generic «сессия истекла» recovery text.
const getJoinRefusalMessage = (err: unknown): string | null => {
  const detail = (err as HttpApiError | null)?.response?.data?.detail;
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === 'string' && message.trim()) {
      return message;
    }
  }
  return null;
};

const QueueJoin = () => {
  const { token: paramToken } = useParams();
  // RQ-18 (S-15): public permanent-address route /q/:publicCode renders the
  // SAME QueueJoin experience. Direction mode is detected purely from the
  // route params — no second registration UI, no props plumbing.
  // RQ-18 follow-up round-4 (P1-2): the backend resolves the public code
  // as ``value.strip().lower()`` — /q/ABCD1234EFGH and /q/abcd1234efgh
  // are THE SAME permanent address server-side. The client therefore uses
  // ONE canonical identity for the storage keys, the start call and the
  // attempt state, and replaces a non-canonical URL with the lowercase
  // variant — an uppercase alias must never look like a «new code» that
  // resets the complete-attempt guard.
  const { publicCode: rawPublicCode } = useParams();
  const directionCode = rawPublicCode ? rawPublicCode.trim().toLowerCase() : null;
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
    // Round-9 (review P2-3): the verified-envelope gate — shown when the
    // browser refused to persist the recovery guard and the business
    // attempt was therefore NOT sent.
    attemptGuardUnavailable: t('misc.qj_attempt_guard_unavailable'),
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
  // RQ-18 follow-up round-4 (P1-2): the attempt-state is addressed PER
  // ATTEMPT (round-8: base + '__' + sessionToken — no shared per-direction
  // slot), still under the CANONICAL code so both case variants of the
  // URL share one attempt identity.
  // RQ-18 follow-up round-4 (P1-2): a hydrated attempt whose business
  // outcome is UNKNOWN — the mount must NOT mint a new session; the
  // patient gets the reconcile/start-over panel instead.
  const [reconcile, setReconcile] = useState<{
    sessionToken: string;
    profileId: number | null;
    directionTitle: string | null;
  } | null>(null);
  // The direction title for a reconcile-booted success screen (the
  // directionInfo object does not survive a reload — the envelope does).
  const [reconcileDirectionTitle, setReconcileDirectionTitle] = useState<
    string | null
  >(null);
  // RQ-18 follow-up round-4 (P2-1): a CONFIRMED pre-execution refusal
  // (machine reason from the backend) — the honest explicit recovery:
  // «Сессия истекла до отправки. Начать заново» with a real button, not
  // a blind retry loop against the same dead token.
  const [preExecRefusal, setPreExecRefusal] = useState(false);
  // Round-9 (review P2-2): WHICH pre-execution refusal fired and the
  // server's own safe domain message — the rollback-proven
  // join_session_not_executed class (e.g. «Очередь заполнена») must be
  // shown verbatim, not flattened into the «сессия истекла» text.
  const [preExecRefusalReason, setPreExecRefusalReason] = useState<string | null>(null);
  const [preExecRefusalMessage, setPreExecRefusalMessage] = useState<string | null>(null);
  // RQ-18 follow-up round-5 (P1-3): the server refused the reconcile with
  // join_session_payload_mismatch — the attempt belongs to a DIFFERENT
  // immutable payload. Decisive (the session is provably joined): the
  // panel swaps to an honest conflict message with the explicit
  // start-over (safe for a different identity — the queue duplicate guard
  // reuses the same ticket for the same person).
  const [payloadMismatch, setPayloadMismatch] = useState(false);
  // Round-10 (review P1): fail-closed ambiguity — the boot found SEVERAL
  // outstanding attempt envelopes with NO live owner marker (every tab
  // closed: sessionStorage died, localStorage survived). The old boot
  // adopted the «newest» arbitrarily — on a shared device that adopts
  // ANOTHER patient's attempt, and the payload-mismatch path then
  // DELETED that foreign envelope: the true owner lost their UNKNOWN
  // recovery (a committed talon replay) and this patient was pushed into
  // an unchecked fresh start. Now nothing is auto-adopted, fresh start
  // stays locked, and the ambiguity resolves ONLY by explicitly checking
  // each attempt with the patient's own identity.
  const [attemptAmbiguity, setAttemptAmbiguity] = useState<
    QueueJoinAttemptState[] | null
  >(null);
  // Round-10 (review P1): candidates already checked from the ambiguity
  // list and PROVEN bound to a different payload — marked in the list,
  // never deleted (the mismatch proves non-ownership, not death).
  const [ambiguousCheckedTokens, setAmbiguousCheckedTokens] = useState<
    string[]
  >([]);
  // Round-10 (review P1): the ambiguity list while ONE claimed candidate
  // is being checked — a mismatch restores the list from here without a
  // re-scan (the claimed envelope must survive the check untouched).
  const ambiguityCandidatesRef = useRef<QueueJoinAttemptState[] | null>(null);
  // Round-9 (review P2-2): the recovery text is chosen BY REASON — the
  // expired/not_found class keeps the «сессия истекла» wording, while
  // join_session_not_executed shows the server's own safe domain
  // message (with a typed fallback when the server sent none).
  const preExecRefusalText =
    preExecRefusalReason === 'join_session_not_executed'
      ? preExecRefusalMessage || t('misc.qj_preexec_not_executed')
      : t('misc.qj_preexec_refusal');

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
  // Round-6 (P1-3): the server-computed horizon of the CURRENT session's
  // attempt identity (end of the target queue-day + grace). Captured from
  // every start/renewal response and persisted with the attempt envelope.
  const [attemptExpiresAt, setAttemptExpiresAt] = useState<string | null>(null);
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
    // Round-9 (review P2-2): a structured refusal detail ({reason, message})
    // is an OBJECT — extract its message instead of discarding it (the
    // backend's promised «real domain reason» used to fall through to the
    // generic fallback whenever detail was an object).
    if (
      responseData?.detail &&
      typeof responseData.detail === 'object' &&
      !Array.isArray(responseData.detail)
    ) {
      const detailMessage = (responseData.detail as { message?: unknown }).message;
      if (typeof detailMessage === 'string' && detailMessage.trim()) {
        return detailMessage;
      }
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
    // RQ-18 follow-up round-5 (P1-1): in direction mode NOTHING about the
    // typed patient is persisted any more — the shared permanent code is
    // the wrong place for PHI on an anonymous device (the round-4
    // phone-tail challenge verified nothing for families sharing one
    // number). The legacy per-token flow keeps its own draft.
    if (directionMode) {
      return;
    }
    if (!formData.patientName && !formData.phone && !formData.telegramId) {
      draftRemove(formStorageKey);
      return;
    }
    draftSet(formStorageKey, JSON.stringify(formData));
  }, [formData, formStorageKey, formDraftHydrated, directionMode, draftSet, draftRemove]);

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
    // RQ-18 follow-up round-5 (P1-1): in direction mode there is no draft
    // to hydrate — no PHI is stored under the shared permanent code, so a
    // reload (or the next person at the device) always finds an EMPTY
    // form. Nothing to verify, nothing to leak.
    if (!directionMode) {
      try {
        const parsed = saved ? safeJsonParse(saved) : null;
        if (parsed && typeof parsed === 'object') {
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
    } else if (saved) {
      // A stale direction-mode draft from an OLDER build must not linger.
      draftRemove(formStorageKey);
    }
    setPendingDraft(null);
    setFormData(restored ?? { patientName: '', phone: '', telegramId: '' });
    setFormDraftHydrated(true);
  }, [formStorageKey, directionMode, draftGet, draftRemove]);

  // RQ-18 follow-up round-4 (P1-2): the URL must carry the SAME canonical
  // lowercase code the backend resolves by. A non-canonical variant is
  // replaced (no history entry) — the alias never becomes a second
  // identity for the attempt guard.
  useEffect(() => {
    if (!rawPublicCode || !directionMode) {
      return;
    }
    const canonical = rawPublicCode.trim().toLowerCase();
    if (rawPublicCode !== canonical) {
      navigate(`/q/${canonical}`, { replace: true });
    }
  }, [rawPublicCode, directionMode, navigate]);

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
  // Round-8 (P1-2): the per-direction context claim (ref swap + epoch bump
  // + full state reset on a code change) is EXTRACTED from
  // runDirectionStart so the boot effect's UNKNOWN-recovery branch goes
  // through the SAME swap before its early return. Previously that branch
  // returned WITHOUT claiming: directionStartRef/epoch still belonged to
  // the PREVIOUS direction, so a late in-flight complete of the old code
  // passed BOTH stale guards (same epoch, same code ref) and rendered the
  // OLD talon under the NEW URL — while the old hung submit lock kept
  // blocking the new direction's reconcile check.
  const claimDirectionContext = useCallback((code: string | null): boolean => {
    if (!code) {
      return false;
    }
    // RQ-18 follow-up (P2-2): a code CHANGE inside one route instance must
    // drop the PREVIOUS direction's whole client context — session, result
    // and advisories. The typed form is NOT reset here: each code owns its
    // own draft key, and the guarded load effect (formStorageKey change)
    // swaps in the new code's own draft — wiping here would race the load
    // effect and destroy a just-restored draft on remounts (pinned).
    // A same-code re-entry (StrictMode skip, error-screen retry) keeps the
    // patient's context intact — and re-claims nothing (no epoch bump).
    const isNewCode = directionStartRef.current !== code;
    if (!isNewCode) {
      return false;
    }
    directionStartRef.current = code;
    // RQ-18 follow-up round-2 (P1): the claim takes a FRESH request epoch
    // — a LATE response for a superseded code (/q/A answered after /q/B
    // already booted) is dropped in try/catch/finally and can never
    // overwrite the freshly claimed direction.
    directionEpochRef.current += 1;
    setSessionToken(null);
    setQueueInfo(null);
    setDirectionInfo(null);
    setSessionExpiresAt(null);
    setAttemptExpiresAt(null);
    setResult(null);
    setSubmitResultUnknown(false);
    setShowSessionConsumedAdvisory(false);
    setSelectedSpecialists([]);
    // RQ-18 follow-up round-4 (P1-2/P2-1): a NEW direction boot is the
    // explicit start-over — the reconcile panel and the confirmed
    // pre-execution refusal belong to the PREVIOUS lifecycle.
    setReconcile(null);
    setReconcileDirectionTitle(null);
    setPreExecRefusal(false);
    // Round-9 (review P2-2): the refusal reason/message belong to the
    // PREVIOUS lifecycle too.
    setPreExecRefusalReason(null);
    setPreExecRefusalMessage(null);
    setPayloadMismatch(false);
    // Round-10 (review P1): the ambiguity panel and its checked marks
    // belong to the PREVIOUS lifecycle too.
    ambiguityCandidatesRef.current = null;
    setAttemptAmbiguity(null);
    setAmbiguousCheckedTokens([]);
    // RQ-18 follow-up round-3 (P1): a NEW direction is the explicit
    // start-over — the previous code's complete attempt must not
    // forbid B's fresh session lifecycle, and its in-flight/late
    // submit attempt must neither keep B's submit disabled (a hung A
    // must not make B unusable) nor later release B's own lock.
    completeAttemptedRef.current = false;
    submitAttemptRef.current = null;
    setLoading(false);
    return true;
  }, []);

  const runDirectionStart = useCallback(async () => {
    if (!directionCode) {
      return;
    }
    // Round-8 (P1-2): claim FIRST (reset-on-new-code + epoch bump) — the
    // exact same swap the boot effect's recovery branch performs. A
    // same-code re-entry (error retry, start-over) keeps the context but
    // still gets a fresh epoch below, so the previous attempt's late
    // response cannot land either. The claim already bumped the epoch for
    // a new code; the increment below is the unconditional per-START bump
    // (retry of the same code) — double-bumping a fresh claim is harmless:
    // epochs are only ever COMPARED, never enumerated.
    claimDirectionContext(directionCode);
    const epoch = ++directionEpochRef.current;
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
      // Round-9 (review P1-2): this tab now owns the freshly minted
      // attempt identity — the per-tab owner marker pins the envelope
      // this tab will write at submit time.
      attemptStateOwnerSet(directionCode, res.session_token);
      setSessionExpiresAt(res.expires_at ?? null);
      // Round-6 (P1-3): the honest attempt-identity horizon of THIS
      // session (end of the target queue-day + grace) travels with the
      // start response and is persisted with the attempt envelope.
      setAttemptExpiresAt(res.attempt_expires_at ?? null);
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
    if (!directionMode || !directionCode) {
      return;
    }
    // RQ-18 follow-up round-4 (P1-2): the attempt-state survives the
    // reload. A hydrated attempt whose outcome is UNKNOWN (a complete
    // request was sent, the response never arrived) FORBIDS the automatic
    // session start on this mount — the patient gets the reconcile /
    // start-over panel and the ORIGINAL attempt identity (session token)
    // is preserved for the reconcile retry. A confirmed no-business-op
    // outcome (machine reason) is removed — a fresh session duplicates
    // nothing.
    // Round-9 (review P1-2): the discovery is PER ATTEMPT — resolve this
    // tab's own attempt via the sessionStorage owner marker first, then
    // the single outstanding one. Other tabs' envelopes are never adopted
    // away nor destroyed; the adopted legacy single-slot envelope is
    // re-homed to its per-attempt key.
    // Round-10 (review P1): WITHOUT a live owner marker only a SINGLE
    // outstanding envelope is unambiguous (the common reopen case).
    // SEVERAL outstanding envelopes with no owner marker mean every tab
    // was closed — the «newest» may belong to ANOTHER patient of this
    // shared device, so nothing is auto-adopted and the boot fails
    // closed into the explicit ambiguity resolution.
    const candidates = attemptStateScan(directionCode);
    const ownerToken = attemptStateOwnerGet(directionCode);
    const ownedAttempt = ownerToken
      ? candidates.find((candidate) => candidate.sessionToken === ownerToken) ?? null
      : null;
    const attempt = ownedAttempt ?? (candidates.length === 1 ? candidates[0] : null);
    const attemptAmbiguous = ownedAttempt === null && candidates.length > 1;
    // Round-8 (P1-2): claim the direction context BEFORE any branching —
    // the UNKNOWN-recovery branch below early-returns, and WITHOUT the
    // claim its refs/epoch stayed those of the PREVIOUS direction (the
    // stale-guard hole described at claimDirectionContext). The claim is
    // a no-op (no epoch bump, no reset) when the code did not change, so
    // same-code effect reruns stay inert.
    const claimed = claimDirectionContext(directionCode);
    if (attemptAmbiguous) {
      // Round-10 (review P1): fail-closed. No auto-adopt (the old boot
      // took candidates[0] — another patient's envelope on a shared
      // device), no auto-start, no start-over. Every outstanding envelope
      // stays EXACTLY as it is; the patient resolves the ambiguity via
      // the explicit per-attempt checks (handleAmbiguityCheck) and the
      // fresh start unlocks only when every candidate is proven foreign.
      setReconcile(null);
      setReconcileDirectionTitle(null);
      setPreExecRefusal(false);
      setPreExecRefusalReason(null);
      setPreExecRefusalMessage(null);
      setPayloadMismatch(false);
      setSubmitResultUnknown(false);
      setShowSessionConsumedAdvisory(false);
      setError(null);
      setAttemptAmbiguity(candidates);
      setAmbiguousCheckedTokens([]);
      setStep('form');
      return;
    }
    if (attempt && attempt.publicCode === directionCode) {
      // Adopt: the owner marker keeps this tab's identity stable across
      // further reloads.
      attemptStateOwnerSet(directionCode, attempt.sessionToken);
      if (
        attemptStateWriteFor(directionCode, attempt) &&
        attemptStateParse(attemptStateStorageGet(attemptStateKeyBase(directionCode)))?.sessionToken ===
          attempt.sessionToken
      ) {
        // The verified per-attempt re-home succeeded — the legacy
        // single-slot envelope of THIS attempt can go.
        attemptStateStorageRemove(attemptStateKeyBase(directionCode));
      }
      if (attempt.completeAttempted && attempt.outcomeUnknown) {
        completeAttemptedRef.current = true;
        setReconcile({
          sessionToken: attempt.sessionToken,
          profileId: attempt.profileId,
          directionTitle: attempt.directionTitle,
        });
        setReconcileDirectionTitle(attempt.directionTitle);
        setStep('form');
        return;
      }
      if (attempt.completeAttempted && !attempt.outcomeUnknown) {
        attemptStateRemoveFor(directionCode, attempt.sessionToken);
        attemptStateOwnerClear(directionCode);
      }
    }
    // RQ-18 follow-up (P2-2): only a FRESH claim (a new code inside this
    // route instance) starts a session. StrictMode's dev double-invoke
    // re-runs this effect with the SAME code → already claimed → skipped;
    // a changed :publicCode param re-claims with the NEW code → the
    // previous direction's whole context was dropped above and B's
    // session starts (no stale A session under a B URL, no stale A
    // guards for A's late responses to pass).
    if (!claimed) {
      return;
    }
    void runDirectionStart();
  }, [directionMode, directionCode, runDirectionStart, claimDirectionContext]);

  // RQ-18 follow-up round-4 (P2-1): the EXPLICIT start-over — the only
  // action that may mint a new session after a complete attempt (a
  // confirmed pre-execution refusal or an unknown outcome). The typed
  // form/draft is the patient's own context and is kept.
  const handleStartOver = () => {
    // Round-9 (review P1-2): remove ONLY this attempt's envelope (the
    // adopted/owned one) — another tab's outstanding attempt for the same
    // /q/<code> must survive the start-over untouched.
    // Round-10 (review P1): the payload-mismatch panel and the resolved
    // ambiguity list prove NOTHING about the envelopes' death — a
    // mismatch only says the TYPED data does not own the attempt. The
    // old code reached the mismatch panel's start-over right after
    // deleting the foreign envelope: the true owner lost their UNKNOWN
    // recovery while this patient got an unchecked fresh start. Both
    // contexts keep every envelope intact; only the new session is
    // minted.
    const keepEnvelopes = payloadMismatch || attemptAmbiguity !== null;
    if (directionCode) {
      if (!keepEnvelopes) {
        const ownToken = reconcile?.sessionToken ?? attemptStateOwnerGet(directionCode);
        attemptStateRemoveFor(directionCode, ownToken);
      }
      attemptStateOwnerClear(directionCode);
    }
    ambiguityCandidatesRef.current = null;
    setAttemptAmbiguity(null);
    setAmbiguousCheckedTokens([]);
    completeAttemptedRef.current = false;
    setReconcile(null);
    setPreExecRefusal(false);
    setPreExecRefusalReason(null);
    setPreExecRefusalMessage(null);
    setPayloadMismatch(false);
    setSubmitResultUnknown(false);
    setShowSessionConsumedAdvisory(false);
    setError(null);
    // Force the fresh public start (a new session, no business action).
    directionStartRef.current = null;
    void runDirectionStart();
  };

  // Round-10 (review P1): the EXPLICIT resolution of the ownerless
  // ambiguity — the patient picks ONE outstanding attempt and checks it
  // with their own identity (the same server-verdict check as the
  // reconcile retry). The claimed candidate becomes this tab's reconcile
  // identity; the OTHER envelopes stay untouched. The verdict routes the
  // flow: a mismatch returns to the list with the candidate marked (its
  // envelope survives), a proven-dead/used verdict removes only THAT
  // envelope, a success consumes the claimed attempt normally — and the
  // fresh start unlocks only when every candidate is resolved.
  const handleAmbiguityCheck = (candidate: QueueJoinAttemptState) => {
    if (!directionCode || !attemptAmbiguity || submitAttemptRef.current) {
      return;
    }
    ambiguityCandidatesRef.current = attemptAmbiguity;
    setAttemptAmbiguity(null);
    // Claim the candidate as this tab's identity — a reload continues
    // the same check instead of re-gating the ambiguity.
    attemptStateOwnerSet(directionCode, candidate.sessionToken);
    setReconcile({
      sessionToken: candidate.sessionToken,
      profileId: candidate.profileId,
      directionTitle: candidate.directionTitle,
    });
    setReconcileDirectionTitle(candidate.directionTitle);
    setPreExecRefusal(false);
    setPreExecRefusalReason(null);
    setPreExecRefusalMessage(null);
    setPayloadMismatch(false);
    setSubmitResultUnknown(false);
    setShowSessionConsumedAdvisory(false);
    setError(null);
  };

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

    // Round-10 (review P1): the ambiguity resolution and the reconcile
    // mode gate the plain submit — no session exists on this mount until
    // the ambiguity is resolved (or the server verdict unlocks the
    // start-over). An Enter-key submit must not even hit the guard path.
    if (directionMode && (reconcile || attemptAmbiguity)) {
      return;
    }

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
    // Round-8 (P2-4): the attempt-identity horizon that the persist below
    // writes must be the horizon of the session that ACTUALLY executes the
    // complete. `attemptExpiresAt` here is a closure snapshot taken at
    // render time: when the transparent renewal below mints a session for
    // the NEXT queue-day (a post-09:00-cutoff renewal), the React setter
    // updates the state but NOT this running closure — persisting the
    // stale snapshot wrote a NEW token together with the OLD (already
    // expired) horizon, so attemptStateHorizonValid deleted the UNKNOWN
    // protection envelope while the new session was still live. This local
    // travels with the renewal response into the same call's persist.
    let currentAttemptExpiresAt = attemptExpiresAt;

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
        // Round-6 (P1-3): the renewal's own horizon replaces the previous
        // one — the envelope written at submit below carries it.
        // Round-8 (P2-4): the LOCAL mirror is updated too — the closure
        // variable is what the persist below actually reads; the React
        // state alone never reaches this running handler.
        setAttemptExpiresAt(res.attempt_expires_at ?? null);
        currentAttemptExpiresAt = res.attempt_expires_at ?? null;
        // Round-9 (review P1-2): the renewed identity replaces the owned
        // one — the envelope written below carries THIS token.
        if (directionCode) {
          attemptStateOwnerSet(directionCode, res.session_token);
        }
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
      // RQ-18 follow-up round-4 (P1-2): the attempt state ALSO persists
      // (per canonical code) — a reload or a closed tab must not reset
      // the guard and silently mint a new session while this attempt's
      // business outcome is still unknown. Round-5 (P1-4): no 15-minute
      // auto-drop. Round-6 (P1-3): localStorage + the server horizon —
      // the identity lives until the end of the TARGET queue-day.
      // Round-9 (review P2-3): the envelope IS the exactly-once guard for
      // the irreversible complete — write it FIRST, to THIS attempt's own
      // per-attempt key (review P1-2), and VERIFY the store really
      // persisted it. If the browser refuses (quota / disabled storage /
      // private mode), the business attempt is NOT sent: a lost response
      // with no envelope would leave the recovery guard on this mount
      // only, and a reload would silently mint a second attempt.
      if (directionMode && directionCode) {
        const persisted = attemptStateWriteFor(directionCode, {
          ts: Date.now(),
          publicCode: directionCode,
          sessionToken: String(currentSessionToken ?? ''),
          profileId: directionInfo?.profile_id ?? null,
          directionTitle: directionInfo?.title ?? null,
          completeAttempted: true,
          outcomeUnknown: true,
          // Round-6 (P1-3): the server-computed horizon — the envelope
          // survives the tab (localStorage) and never expires before the
          // end of the TARGET queue-day (the 24h TTL is only the fallback
          // for an older backend without the horizon).
          // Round-8 (P2-4): the LOCAL renewal mirror, not the stale render
          // closure — after a post-cutoff renewal the envelope must carry
          // the NEW session's horizon, or the UNKNOWN protection dies
          // while the new session is still live.
          attemptExpiresAt: currentAttemptExpiresAt,
        });
        if (!persisted) {
          setError(QUEUE_JOIN_MESSAGES.attemptGuardUnavailable);
          // Nothing was sent — the submit lock is released by the finally
          // below and the session stays pending (no UNKNOWN to reconcile).
          return;
        }
      }
      // Round-9 (review P2-3): only AFTER the verified envelope persist —
      // from this moment the result is unknown, whatever happens to the
      // response (a lost answer must never trigger a renewal).
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
      // RQ-18 follow-up round-4 (P1-2): the attempt's outcome is KNOWN
      // (success) — the persisted attempt state is no longer needed.
      // Round-9 (review P1-2): removal touches ONLY this attempt's own
      // per-attempt key — a parallel tab's outstanding envelope survives.
      if (directionCode) {
        attemptStateRemoveFor(directionCode, currentSessionToken);
        attemptStateOwnerClear(directionCode);
      }
      setReconcile(null);

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
      setPayloadMismatch(false);
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
      const refusalReason = getJoinRefusalReason(error);
      // Round-5 (P1-4) fail-closed protocol: outcomeUnknown=false ONLY for
      // a decisive server verdict — a success replay (used/known), a
      // proven pre-execution refusal (not_found / expired), or a proven
      // payload conflict (mismatch ⇒ the session is joined, just not for
      // the typed payload). Everything else — join_session_processing,
      // any 5xx after the business commit, and ANY undescribed response —
      // stays UNKNOWN: the attempt may already be durably committed, and
      // a fresh session could duplicate the ticket.
      const markOutcomeKnown = () => {
        // Round-9 (review P1-2): rewrite ONLY this attempt's own envelope
        // (the token that actually performed the attempt).
        if (directionCode) {
          const attempt = attemptStateReadFor(directionCode, currentSessionToken);
          if (attempt) {
            attemptStateWriteFor(directionCode, {
              ...attempt,
              outcomeUnknown: false,
            });
          }
        }
      };
      if (isNetworkClassSubmitError(error)) {
        // RQ-10 (S-08): ответ потерян — результат отправки неизвестен.
        // The persisted attempt state keeps outcomeUnknown=true — a reload
        // engages the reconcile panel with the ORIGINAL attempt identity
        // instead of minting a new session.
        setSubmitResultUnknown(true);
      } else if (
        refusalReason !== null &&
        JOIN_PRE_EXECUTION_REASONS.has(refusalReason)
      ) {
        // RQ-18 follow-up round-4 (P2-1): a CONFIRMED pre-execution
        // refusal (the backend proved nothing was created) — offer the
        // honest explicit start-over instead of a blind retry loop
        // against the same dead token.
        // Round-9 (review P2-2): keep WHICH refusal fired and the
        // server's own safe domain message — the recovery text is
        // selected by reason (not_executed ≠ «сессия истекла»). Also
        // surface the message in the generic error line.
        setPreExecRefusal(true);
        setPreExecRefusalReason(refusalReason);
        setPreExecRefusalMessage(getJoinRefusalMessage(error));
        markOutcomeKnown();
      } else if (refusalReason === 'join_session_payload_mismatch') {
        // Round-5 (P1-3): decisive conflict — the attempt is bound to a
        // different immutable payload. The current form does not own it.
        setPayloadMismatch(true);
        markOutcomeKnown();
      } else if (refusalReason === 'join_session_used') {
        setShowSessionConsumedAdvisory(true);
        markOutcomeKnown();
      } else if (submitResultUnknown) {
        // Повтор после потери ответа отклонен сервером без machine reason:
        // запись могла быть создана первой попыткой — показываем честный
        // путь обращения вместо вводящего «сессия не найдена».
        setShowSessionConsumedAdvisory(true);
      } else {
        // Round-5 (P1-4): a non-network refusal WITHOUT a decisive reason
        // (join_session_processing, a masked generic 400, a 500 after the
        // business commit, anything undescribed) stays UNKNOWN.
        setSubmitResultUnknown(true);
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

  // RQ-18 follow-up round-4 (P1-2): the reconcile retry — the patient
  // re-checks the UNKNOWN attempt with its ORIGINAL identity (the same
  // session token) instead of minting a new session. The backend answers
  // decisively either way: a joined session replays its saved ticket, a
  // still-pending session executes this same logical attempt, a proven
  // dead session offers the explicit start-over.
  const handleReconcileSubmit = async () => {
    if (!reconcile || submitAttemptRef.current) {
      return;
    }
    // The same validation the normal submit applies — the reconcile retry
    // may EXECUTE the pending session, so the payload must be complete.
    const trimmedPatientName = String(formData.patientName ?? '').trim();
    const trimmedPhone = String(formData.phone ?? '').trim();
    const cleanPhone = draftPhoneDigits(trimmedPhone);
    if (trimmedPatientName.length < 2 || trimmedPatientName.length > 200) {
      setError(
        trimmedPatientName.length < 2
          ? QUEUE_JOIN_MESSAGES.nameTooShort
          : QUEUE_JOIN_MESSAGES.nameTooLong,
      );
      return;
    }
    if (cleanPhone.length !== 12) {
      setError(QUEUE_JOIN_MESSAGES.phoneTooShort);
      return;
    }
    const attempt = {
      epoch: directionEpochRef.current,
      code: directionCode,
    };
    submitAttemptRef.current = attempt;
    setLoading(true);
    setError(null);
    const requestBody: Record<string, unknown> = {
      session_token: reconcile.sessionToken,
      patient_name: trimmedPatientName,
      phone: cleanPhone,
      telegram_id: formData.telegramId ? parseInt(String(formData.telegramId ?? '')) : null,
    };
    if (reconcile.profileId != null) {
      requestBody.specialist_ids = [reconcile.profileId];
      requestBody.specialist_entity_types = ['profile'];
    }
    try {
      const joinResult = await completeQueueJoinSession(requestBody);
      if (
        directionMode &&
        (attempt.epoch !== directionEpochRef.current ||
          attempt.code !== directionCode)
      ) {
        return;
      }
      setResult(joinResult as unknown as QueueJoinResultLocal);
      // The attempt's outcome is KNOWN — the persisted attempt state and
      // the reconcile panel are no longer needed. Round-9 (review P1-2):
      // removal touches ONLY this attempt's own per-attempt key.
      if (directionCode) {
        attemptStateRemoveFor(directionCode, reconcile.sessionToken);
        attemptStateOwnerClear(directionCode);
      }
      // Round-10 (review P1): a claimed ambiguity candidate resolved
      // successfully — the ambiguity lifecycle is over for this mount.
      ambiguityCandidatesRef.current = null;
      setAttemptAmbiguity(null);
      setAmbiguousCheckedTokens([]);
      setReconcile(null);
      if (formStorageKey) {
        draftRemove(formStorageKey);
        setPendingDraft(null);
      }
      setSubmitResultUnknown(false);
      setShowSessionConsumedAdvisory(false);
      setPayloadMismatch(false);
      setStep('success');
    } catch (err: unknown) {
      if (
        directionMode &&
        (attempt.epoch !== directionEpochRef.current ||
          attempt.code !== directionCode)
      ) {
        return;
      }
      setError(getApiErrorMessage(err, QUEUE_JOIN_MESSAGES.joinFailed));
      const refusalReason = getJoinRefusalReason(err);
      if (refusalReason !== null && JOIN_PRE_EXECUTION_REASONS.has(refusalReason)) {
        // Proven: the original attempt produced NOTHING — the honest
        // explicit start-over replaces the reconcile panel.
        // Round-9 (review P2-2): keep the refusal reason + the server's
        // safe domain message for the reason-specific recovery text.
        setPreExecRefusal(true);
        setPreExecRefusalReason(refusalReason);
        setPreExecRefusalMessage(getJoinRefusalMessage(err));
        if (directionCode) {
          attemptStateRemoveFor(directionCode, reconcile.sessionToken);
          attemptStateOwnerClear(directionCode);
        }
        // Round-10 (review P1): a proven-dead candidate checked from the
        // ambiguity list — its envelope guards nothing anymore (the
        // backend proved nothing was created), so ONLY that envelope is
        // dropped. The remaining outstanding ones still gate the fresh
        // start — the start-over panel is replaced by the ambiguity list
        // until every candidate is resolved.
        if (directionCode && ambiguityCandidatesRef.current !== null) {
          ambiguityCandidatesRef.current = null;
          setPreExecRefusal(false);
          setPreExecRefusalReason(null);
          setPreExecRefusalMessage(null);
          const rest = attemptStateScan(directionCode);
          setAmbiguousCheckedTokens([]);
          if (rest.length > 1) {
            setReconcile(null);
            setAttemptAmbiguity(rest);
          } else if (rest.length === 1) {
            // The last remaining outstanding attempt re-adopts exactly
            // like the boot's single-candidate case.
            attemptStateOwnerSet(directionCode, rest[0].sessionToken);
            setReconcile({
              sessionToken: rest[0].sessionToken,
              profileId: rest[0].profileId,
              directionTitle: rest[0].directionTitle,
            });
            setReconcileDirectionTitle(rest[0].directionTitle);
          } else {
            setReconcile(null);
          }
        }
      } else if (refusalReason === 'join_session_payload_mismatch') {
        // Round-5 (P1-3): decisive conflict — the attempt is bound to a
        // DIFFERENT immutable payload (the review's wrong-patient hole:
        // «Replay Patient» must never re-use «Boundary Patient»'s
        // session). The typed form does not own this attempt; the panel
        // swaps to the honest conflict message with the start-over.
        // Round-10 (review P1): the mismatch proves NON-OWNERSHIP for the
        // typed payload — it says NOTHING about the attempt being dead.
        // The envelope MUST SURVIVE: on a shared device it likely belongs
        // to ANOTHER patient whose UNKNOWN recovery (a committed talon
        // replay) the old code destroyed here, and even its true owner
        // may have mistyped — the retry with the exact original identity
        // needs the envelope alive. Deleting it also unlocked an
        // UNCHECKED fresh start while the patient's own outstanding
        // attempt was never looked at.
        if (
          directionCode &&
          ambiguityCandidatesRef.current !== null &&
          ambiguityCandidatesRef.current.some(
            (candidate) => candidate.sessionToken === reconcile.sessionToken,
          )
        ) {
          // A claimed ambiguity candidate is proven not ours — back to
          // the list, marked; NO envelope is destroyed; the fresh start
          // stays locked until every outstanding attempt is resolved.
          const list = ambiguityCandidatesRef.current;
          ambiguityCandidatesRef.current = null;
          attemptStateOwnerClear(directionCode);
          setReconcile(null);
          setPayloadMismatch(false);
          setSubmitResultUnknown(false);
          setShowSessionConsumedAdvisory(false);
          setAttemptAmbiguity(list);
          setAmbiguousCheckedTokens((prev) =>
            prev.includes(reconcile.sessionToken)
              ? prev
              : [...prev, reconcile.sessionToken],
          );
        } else {
          setPayloadMismatch(true);
          // Round-10 (review P1): the envelope and the owner marker
          // survive in the single-candidate flow too — a reload re-adopts
          // THIS attempt and the patient can retry with the exact
          // original identity (the old code deleted the envelope here).
        }
      } else if (refusalReason === 'join_session_used') {
        setShowSessionConsumedAdvisory(true);
        if (directionCode) {
          attemptStateRemoveFor(directionCode, reconcile.sessionToken);
          attemptStateOwnerClear(directionCode);
        }
        // Round-10 (review P1): the used verdict means the attempt's
        // outcome is KNOWN (committed) — its envelope guards nothing
        // further, so ONLY that envelope is dropped; the remaining
        // outstanding ones keep gating the fresh start.
        if (directionCode && ambiguityCandidatesRef.current !== null) {
          ambiguityCandidatesRef.current = null;
          const rest = attemptStateScan(directionCode);
          setAmbiguousCheckedTokens([]);
          if (rest.length > 1) {
            setReconcile(null);
            setShowSessionConsumedAdvisory(false);
            setAttemptAmbiguity(rest);
          } else if (rest.length === 1) {
            setShowSessionConsumedAdvisory(false);
            attemptStateOwnerSet(directionCode, rest[0].sessionToken);
            setReconcile({
              sessionToken: rest[0].sessionToken,
              profileId: rest[0].profileId,
              directionTitle: rest[0].directionTitle,
            });
            setReconcileDirectionTitle(rest[0].directionTitle);
          } else {
            setReconcile(null);
          }
        } else {
          setReconcile(null);
        }
      } else {
        // Round-5 (P1-4) fail-closed: network-class, an in-flight
        // processing claim, a 5xx after the business commit, or ANY
        // undescribed response — the outcome stays honestly UNKNOWN and
        // the reconcile panel remains available. No start-over here.
        setSubmitResultUnknown(true);
      }
    } finally {
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

  // RQ-18 follow-up round-5 (P1-1): the draft challenge machinery is gone
  // together with the direction-mode draft itself — there is nothing left
  // to verify ownership of. (The round-4 phone-tail challenge verified
  // nothing for families sharing one number.)

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
    // Round-4 (P1-2): a reconcile-booted success keeps the direction title
    // from the persisted attempt envelope (directionInfo does not survive
    // a reload).
    const singleSpecialistLabel = directionMode
      ? directionInfo?.title ?? reconcileDirectionTitle ?? null
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
    // and would fall back to a generic label); round-4: the reconcile
    // envelope's direction title is the fallback after a reload.
    const departmentName = directionMode
      ? directionInfo?.title ?? reconcileDirectionTitle ?? ''
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
              {/* RQ-18 follow-up round-4/5 (P1-2/P1-4): the reconcile panel —
                  the previous attempt's outcome is UNKNOWN, so this mount
                  never mints a new session. The ONLY action here is the
                  server-verdict check («Проверить попытку»): the round-5
                  fail-closed rule keeps UNKNOWN until the server answers
                  decisively, so the unsafe «Начать заново» escape is gone
                  from this panel — it remains available only on the PROVEN
                  panels below (pre-execution refusal / payload conflict). */}
              {directionMode && attemptAmbiguity && (
                /* Round-10 (review P1): fail-closed ambiguity — several
                   outstanding attempts, no live owner marker. Nothing is
                   auto-adopted or destroyed; the patient resolves the
                   ambiguity by checking each attempt with their own
                   identity; the fresh start unlocks only when every
                   outstanding envelope is proven foreign. */
                <div className="qj-reconcile" data-testid="qj-attempt-ambiguity" role="alert">
                  <p className="qj-reconcile-text" data-testid="qj-attempt-ambiguity-text">
                    {t('misc.qj_attempt_ambiguity_title')}
                  </p>
                  <p className="qj-reconcile-hint">{t('misc.qj_attempt_ambiguity_hint')}</p>
                  <ul className="qj-ambiguity-list">
                    {attemptAmbiguity.map((candidate) => {
                      const checked = ambiguousCheckedTokens.includes(candidate.sessionToken);
                      return (
                        <li key={candidate.sessionToken} className="qj-ambiguity-item">
                          <span className="qj-ambiguity-item-label">
                            {candidate.directionTitle ? `${candidate.directionTitle} · ` : ''}
                            {t('misc.qj_attempt_ambiguity_item', {
                              time: attemptTimeLabel(candidate.ts),
                            })}
                          </span>
                          {checked ? (
                            <span
                              className="qj-ambiguity-item-checked"
                              data-testid={`qj-ambiguity-checked-${candidate.sessionToken}`}
                            >
                              {t('misc.qj_attempt_ambiguity_not_mine')}
                            </span>
                          ) : (
                            <button
                              type="button"
                              className="qj-draft-btn qj-draft-btn-primary"
                              data-testid={`qj-ambiguity-check-${candidate.sessionToken}`}
                              disabled={loading}
                              onClick={() => handleAmbiguityCheck(candidate)}
                            >
                              {t('misc.qj_reconcile_check')}
                            </button>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                  {attemptAmbiguity.length > 0 &&
                    attemptAmbiguity.every((candidate) =>
                      ambiguousCheckedTokens.includes(candidate.sessionToken),
                    ) && (
                      <div className="qj-reconcile-actions">
                        <p className="qj-reconcile-hint">
                          {t('misc.qj_attempt_ambiguity_resolved_hint')}
                        </p>
                        <button
                          type="button"
                          className="qj-draft-btn qj-draft-btn-primary"
                          data-testid="qj-ambiguity-start-over"
                          onClick={handleStartOver}
                        >
                          {t('misc.qj_reconcile_start_over')}
                        </button>
                      </div>
                    )}
                </div>
              )}
              {directionMode && reconcile && !preExecRefusal && !payloadMismatch && (
                <div className="qj-reconcile" data-testid="qj-reconcile-banner" role="alert">
                  <p className="qj-reconcile-text" data-testid="qj-reconcile-text">
                    {t('misc.qj_reconcile_title')}
                  </p>
                  <p className="qj-reconcile-hint">{t('misc.qj_reconcile_hint')}</p>
                  <div className="qj-reconcile-actions">
                    <button
                      type="button"
                      className="qj-draft-btn qj-draft-btn-primary"
                      data-testid="qj-reconcile-check"
                      disabled={loading}
                      onClick={() => {
                        void handleReconcileSubmit();
                      }}
                    >
                      {t('misc.qj_reconcile_check')}
                    </button>
                  </div>
                </div>
              )}
              {directionMode && reconcile && preExecRefusal && (
                <div className="qj-reconcile" data-testid="qj-reconcile-banner" role="alert">
                  <p className="qj-reconcile-text" data-testid="qj-preexec-refusal">
                    {preExecRefusalText}
                  </p>
                  <div className="qj-reconcile-actions">
                    <button
                      type="button"
                      className="qj-draft-btn qj-draft-btn-primary"
                      data-testid="qj-reconcile-start-over"
                      onClick={handleStartOver}
                    >
                      {t('misc.qj_reconcile_start_over')}
                    </button>
                  </div>
                </div>
              )}
              {directionMode && reconcile && payloadMismatch && (
                <div className="qj-reconcile" data-testid="qj-reconcile-banner" role="alert">
                  <p className="qj-reconcile-text" data-testid="qj-payload-mismatch">
                    {t('misc.qj_payload_mismatch')}
                  </p>
                  <div className="qj-reconcile-actions">
                    <button
                      type="button"
                      className="qj-draft-btn qj-draft-btn-primary"
                      data-testid="qj-reconcile-start-over"
                      onClick={handleStartOver}
                    >
                      {t('misc.qj_reconcile_start_over')}
                    </button>
                  </div>
                </div>
              )}
              {/* RQ-18 follow-up round-5 (P1-1): the direction-mode draft
                  confirmation is GONE — the shared permanent code no longer
                  stores any PHI, so there is nothing to confirm or leak. */}
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
                  {payloadMismatch && !reconcile && (
                    // Round-5 (P1-3): the decisive payload conflict on a
                    // plain submit (no reconcile panel on this mount) —
                    // the same honest conflict message with the explicit
                    // start-over.
                    <div className="qj-preexec-recovery">
                      <p className="qj-error-advisory" data-testid="qj-payload-mismatch">
                        {t('misc.qj_payload_mismatch')}
                      </p>
                      <button
                        type="button"
                        className="qj-draft-btn qj-draft-btn-primary"
                        data-testid="qj-start-over"
                        onClick={handleStartOver}
                      >
                        {t('misc.qj_reconcile_start_over')}
                      </button>
                    </div>
                  )}
                  {preExecRefusal && (
                    // RQ-18 follow-up round-4 (P2-1): a CONFIRMED
                    // pre-execution refusal — nothing was created, the
                    // backend proved it. The honest recovery is the EXPLICIT
                    // start-over (a new session only after this deliberate
                    // action), never an automatic renewal.
                    <div className="qj-preexec-recovery">
                      <p className="qj-error-advisory" data-testid="qj-preexec-refusal">
                        {preExecRefusalText}
                      </p>
                      <button
                        type="button"
                        className="qj-draft-btn qj-draft-btn-primary"
                        data-testid="qj-start-over"
                        onClick={handleStartOver}
                      >
                        {t('misc.qj_reconcile_start_over')}
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Кнопки - macOS стиль. Round-4 (P1-2): in reconcile mode the
                  normal submit is replaced by the reconcile panel's actions —
                  a plain submit here would hit the attempt guard (no
                  auto-renewal) or send the UNKNOWN attempt again blindly.
                  Round-10 (review P1): the ambiguity resolution gates the
                  plain submit the same way — no session exists until the
                  ambiguity is resolved (or a fresh start is unlocked). */}
              {!(directionMode && (reconcile || attemptAmbiguity)) && (
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
              )}
            </form>
          </div>
        )}
      </div>
    </div>
  );
};

export default QueueJoin;
