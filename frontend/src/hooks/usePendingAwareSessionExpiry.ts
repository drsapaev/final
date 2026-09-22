/**
 * usePendingAwareSessionExpiry — PR 3351 (review round 6, P1).
 *
 * Оборачивает useSessionTimeoutWarning и устраняет штатный обход
 * pending-контракта: истечение JWT больше не выполняет hard navigation
 * (window.location.href = '/login') ПОВЕРХ незавершённой мутации.
 *
 * Проблема: LabPanel на onExpired сразу делал window.location.href =
 * '/login'. Это полная перезагрузка документа — она не проходит через
 * guardRouteLeave и раньше не имела native-подсказки при чистых черновиках
 * (beforeunload ставился только по dirty-state). Pending-only операция
 * (clone чистого шаблона — неидемпотентный POST без Idempotency-Key)
 * обрывалась: сервер мог создать копию, но браузер терял ответ и обновление
 * списка; после повторного входа оператор повторял clone и получал вторую
 * копию.
 *
 * Контракт:
 *  - истечение БЕЗ незавершённых операций — onExpired вызывается сразу
 *    (прежнее поведение: тост + redirect на /login);
 *  - истечение ПОВЕРХ pending-операции — переводит панель в
 *    контролируемое состояние (возвращаемый флаг redirectPending=true
 *    рендерит не-dismissable диалог «операция завершается, затем будет
 *    переход»), hard navigation НЕ выполняется;
 *  - PR 3351 (review round 9, P2): валидное НОВОЕ поколение токена,
 *    обнаруженное опросом, снимает redirectPending НЕМЕДЛЕННО — не
 *    дожидаясь завершения операций: overlay лгал бы восстановленной
 *    сессии, а зависший POST держал бы его бессрочно;
 *  - как только последняя операция завершается (реактивный сигнал
 *    pendingOperationsSignal меняется, а авторитетный аксессор
 *    hasPendingOperations() возвращает false) — ПОВТОРНО проверяется
 *    актуальный access token: за время ожидания его мог обновить
 *    single-flight refresh в API-клиенте. Валидный токен отменяет
 *    redirect (redirectPending=false, onExpired НЕ вызывается —
 *    восстановленная сессия не прерывается ложным logout); истёкший —
 *    onExpired вызывается ровно один раз и выполняет переход.
 *
 * Паттерн рефов — как везде в этом PR: коллбеки и аксессор обновляются
 * каждый рендер, поэтому 30-секундный опрос useSessionTimeoutWarning и
 * ожидающий эффект всегда видят актуальные замыкания.
 */

import { useEffect, useRef, useState } from 'react';
import useSessionTimeoutWarning, { getTokenExpiryMs } from './useSessionTimeoutWarning';

export interface UsePendingAwareSessionExpiryOptions {
  /**
   * Авторитетный источник: есть ли незавершённые операции ПРЯМО СЕЙЧАС.
   * Вызывается в момент истечения и на каждом изменении реактивного
   * сигнала — читает живое состояние (ref-семантика), не замыкание
   * рендера.
   */
  hasPendingOperations: () => boolean;
  /**
   * Реактивный сигнал (например, счётчик pending-источников): его
   * изменение перевыполняет ожидающий эффект и перепроверяет, завершились
   * ли операции.
   */
  pendingOperationsSignal: unknown;
  /** Показ 5-минутного предупреждения (пробрасывается в хук опроса). */
  onWarning: () => void;
  /**
   * Подтверждение истечения: выполняется ОДИН раз — сразу, если операций
   * нет, или после завершения последней. Вызывающий код показывает тост
   * и выполняет logout/redirect.
   */
  onExpired: () => void;
  /**
   * PR 3351 (review round 8, P2): сессия ВОССТАНОВЛЕНА после истечения —
   * single-flight refresh в API-клиенте заменил истёкший JWT новым
   * поколением. Вызывается в двух точках: (1) смена поколения токена в
   * опросе — вместе с НЕМЕДЛЕННЫМ снятием redirectPending (round 9: и
   * warning-overlay, и deferred-redirect-overlay обязаны уйти, не
   * дожидаясь завершения pending-операций); (2) отложенный redirect
   * отменён валидным токеном на завершении операций.
   * Вызывающий код снимает оба overlay: сообщения об истечении лгали бы
   * уже восстановленной сессии.
   */
  onSessionRecovered?: () => void;
}

/**
 * PR 3351 (review round 7, P2): повторная проверка АКТУАЛЬНОГО токена.
 *
 * За время ожидания (истечение → pending-операции → завершение) access
 * token мог быть обновлён: общий API-клиент делает single-flight refresh
 * перед запросами (в т.ч. фоновыми), а useSessionTimeoutWarning при виде
 * токена с достаточным сроком жизни сбрасывает свои
 * warningFiredRef/expiredFiredRef и продолжает штатный цикл. Без
 * перепроверки обёртка выполняла отложенный onExpired вслепую — ложный
 * logout и потеря рабочего контекста при уже восстановленной сессии.
 *
 * false (переход выполняется): токена нет / exp в прошлом / не парсится —
 * на момент откладывания опрос УЖЕ видел истёкший JWT, поэтому «не
 * парсится» трактуется как «сессия не восстановлена».
 */
function hasValidAccessTokenNow(): boolean {
  try {
    const token = window.sessionStorage.getItem('auth_token');
    if (!token) return false;
    const expiresAt = getTokenExpiryMs(token);
    return expiresAt != null && expiresAt > Date.now();
  } catch {
    return false;
  }
}

/**
 * @returns redirectPending — контролируемое состояние «сессия истекла,
 * ожидаем завершения операций» (для не-dismissable диалога).
 */
export function usePendingAwareSessionExpiry({
  hasPendingOperations,
  pendingOperationsSignal,
  onWarning,
  onExpired,
  onSessionRecovered,
}: UsePendingAwareSessionExpiryOptions): boolean {
  const [redirectPending, setRedirectPending] = useState(false);

  // Render-time присваивание (тот же паттерн, что hasDirtyRef в
  // LabLeaveRouteGuard): коллбеки опроса всегда актуальны.
  const hasPendingRef = useRef(hasPendingOperations);
  hasPendingRef.current = hasPendingOperations;
  const onWarningRef = useRef(onWarning);
  onWarningRef.current = onWarning;
  const onExpiredRef = useRef(onExpired);
  onExpiredRef.current = onExpired;
  const onSessionRecoveredRef = useRef(onSessionRecovered);
  onSessionRecoveredRef.current = onSessionRecovered;

  useSessionTimeoutWarning({
    onWarning: () => onWarningRef.current(),
    onExpired: () => {
      if (hasPendingRef.current()) {
        // PR 3351 (review round 6, P1): hard navigation поверх
        // незавершённой мутации запрещена — ждём завершения операций.
        setRedirectPending(true);
        return;
      }
      onExpiredRef.current();
    },
    // PR 3351 (review round 8, P2): смена ПОКОЛЕНИЯ токена (истёкший JWT
    // заменён refresh-ом) — восстановление сессии. warningFired/expiredFired
    // опроса сбрасываются самим хуком, а владелец (LabPanel) получает
    // onSessionRecovered и снимает висящее предупреждение — не дожидаясь
    // завершения pending-операций: диалог лгал бы уже живой сессии.
    // PR 3351 (review round 9, P2): валидное поколение снимает и
    // redirectPending НЕМЕДЛЕННО — overlay «сессия истекла, ожидаем
    // завершения операции» лгал бы восстановленной сессии, а зависший
    // без ответа POST держал бы его бессрочно. Сначала проверяется exp
    // нового токена; pending-операция продолжает блокировать разрушительные
    // переходы через существующие pending-реестры — ложный session-expiry
    // overlay для этой защиты больше не нужен.
    onTokenChanged: () => {
      if (!hasValidAccessTokenNow()) return;
      setRedirectPending(false);
      onSessionRecoveredRef.current?.();
    },
  });

  // Ожидание завершения: реактивный сигнал перевыволняет эффект, состав
  // операций читается из авторитетного аксессора (не из сигнала).
  // hasPendingOperations/коллбеки живут в render-time рефах — в deps
  // не нуждаются.
  // PR 3351 (review round 7, P2): перед отложенным onExpired — повторная
  // проверка токена. JWT истёк во время pending clone/finalize/create →
  // redirectPending=true → параллельный запрос выполнил single-flight
  // refresh → новый JWT валиден → операция завершена → redirectPending
  // снимается БЕЗ onExpired: сессия восстановлена, ложный logout не
  // выполняется. Токен по-прежнему истёк — прежнее поведение: переход
  // ровно один раз после завершения последней операции.
  // PR 3351 (review round 8, P2): восстановление также оповещает
  // onSessionRecovered — вместе с redirectPending-диалогом обязан уйти и
  // warning-overlay (обе накладки исчезают, LabPanel снимает sessionWarning).
  useEffect(() => {
    if (!redirectPending) return;
    if (hasPendingRef.current()) return;
    setRedirectPending(false);
    if (hasValidAccessTokenNow()) {
      onSessionRecoveredRef.current?.();
      return;
    }
    onExpiredRef.current();
  }, [redirectPending, pendingOperationsSignal]);

  return redirectPending;
}

export default usePendingAwareSessionExpiry;
