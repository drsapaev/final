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
 *  - как только последняя операция завершается (реактивный сигнал
 *    pendingOperationsSignal меняется, а авторитетный аксессор
 *    hasPendingOperations() возвращает false) — onExpired вызывается
 *    ровно один раз и выполняет переход.
 *
 * Паттерн рефов — как везде в этом PR: коллбеки и аксессор обновляются
 * каждый рендер, поэтому 30-секундный опрос useSessionTimeoutWarning и
 * ожидающий эффект всегда видят актуальные замыкания.
 */

import { useEffect, useRef, useState } from 'react';
import useSessionTimeoutWarning from './useSessionTimeoutWarning';

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
  });

  // Ожидание завершения: реактивный сигнал перевыволняет эффект, состав
  // операций читается из авторитетного аксессора (не из сигнала).
  // hasPendingOperations/коллбеки живут в render-time рефах — в deps
  // не нуждаются.
  useEffect(() => {
    if (!redirectPending) return;
    if (hasPendingRef.current()) return;
    setRedirectPending(false);
    onExpiredRef.current();
  }, [redirectPending, pendingOperationsSignal]);

  return redirectPending;
}

export default usePendingAwareSessionExpiry;
