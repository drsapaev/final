import '@testing-library/jest-dom';
import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { usePendingAwareSessionExpiry } from '../usePendingAwareSessionExpiry';

/**
 * PR 3351 (review round 6, P1): pending-aware session expiry.
 *
 * Прежний контракт LabPanel: onExpired опроса токена сразу делал
 * window.location.href = '/login' — полная перезагрузка документа ПОВЕРХ
 * висящей неидемпотентной мутации (clone без Idempotency-Key,
 * finalize/print). Обёртка откладывает переход до завершения последней
 * операции и вызывает onExpired ровно один раз.
 *
 * Тесты работают на реальных таймерах: useSessionTimeoutWarning выполняет
 * первую проверку СРАЗУ на монтировании (check() перед setInterval), поэтому
 * токен с exp в прошлом воспроизводит истечение без продвижения часов.
 */

function installToken(expiresAtMs: number) {
  const payload = { sub: '7', role: 'Lab', exp: Math.floor(expiresAtMs / 1000) };
  // Минимальная беззнаковая форма: UI декодирует claims только на клиенте,
  // подпись нерелевантна. Части собираются в рантайме (как в
  // lab-dirty-guard.spec.ts) — единый JWT-подобный литерал в исходнике
  // триггерит secret-сканер CI (generic high entropy).
  const token = [
    'eyJhbGciOiJIUzI1NiJ9',
    window.btoa(JSON.stringify(payload)),
    'sig',
  ].join('.');
  window.sessionStorage.setItem('auth_token', token);
}

describe('usePendingAwareSessionExpiry (PR 3351, review round 6)', () => {
  afterEach(() => {
    window.sessionStorage.removeItem('auth_token');
    vi.restoreAllMocks();
  });

  it('fires onExpired immediately when the session expires with no pending operations', () => {
    installToken(Date.now() - 60_000);
    const onWarning = vi.fn();
    const onExpired = vi.fn();

    const { result } = renderHook(() => usePendingAwareSessionExpiry({
      hasPendingOperations: () => false,
      pendingOperationsSignal: false,
      onWarning,
      onExpired,
    }));

    // Чистое состояние — прежнее поведение: переход без откладывания.
    expect(onExpired).toHaveBeenCalledTimes(1);
    expect(onWarning).not.toHaveBeenCalled();
    expect(result.current).toBe(false);
  });

  it('passes the pre-expiry warning through untouched', () => {
    // Внутри 5-минутного порога, но ещё не истёк.
    installToken(Date.now() + 60_000);
    const onWarning = vi.fn();
    const onExpired = vi.fn();

    const { result } = renderHook(() => usePendingAwareSessionExpiry({
      hasPendingOperations: () => false,
      pendingOperationsSignal: false,
      onWarning,
      onExpired,
    }));

    expect(onWarning).toHaveBeenCalledTimes(1);
    expect(onExpired).not.toHaveBeenCalled();
    expect(result.current).toBe(false);
  });

  it('defers the redirect while an operation is pending and fires it exactly once after completion', () => {
    installToken(Date.now() - 60_000);
    const onWarning = vi.fn();
    const onExpired = vi.fn();
    let pending = true;

    const { result, rerender } = renderHook(
      ({ signal }: { signal: number }) => usePendingAwareSessionExpiry({
        hasPendingOperations: () => pending,
        pendingOperationsSignal: signal,
        onWarning,
        onExpired,
      }),
      { initialProps: { signal: 0 } },
    );

    // Истечение поверх pending-операции: переход ЗАПРЕЩЁН, ждём завершения.
    expect(onExpired).not.toHaveBeenCalled();
    expect(result.current).toBe(true);

    // Сигнал изменился (pending-источники пересобрались), но операция ещё
    // висит — ждём дальше, onExpired не вызывается.
    rerender({ signal: 1 });
    expect(onExpired).not.toHaveBeenCalled();
    expect(result.current).toBe(true);

    // Последняя операция завершена: переход выполняется ровно один раз.
    pending = false;
    rerender({ signal: 2 });
    expect(onExpired).toHaveBeenCalledTimes(1);
    expect(result.current).toBe(false);
  });

  it('keeps the redirect deferred while the pending signal keeps changing with operations still in flight', () => {
    installToken(Date.now() - 60_000);
    const onExpired = vi.fn();
    let pending = true;

    const { result, rerender } = renderHook(
      ({ signal }: { signal: number }) => usePendingAwareSessionExpiry({
        hasPendingOperations: () => pending,
        pendingOperationsSignal: signal,
        onWarning: () => {},
        onExpired,
      }),
      { initialProps: { signal: 0 } },
    );

    rerender({ signal: 1 });
    rerender({ signal: 2 });
    rerender({ signal: 3 });
    expect(onExpired).not.toHaveBeenCalled();
    expect(result.current).toBe(true);

    // Завершение ПОСЛЕ серии пересборок источников всё ещё срабатывает.
    pending = false;
    rerender({ signal: 4 });
    expect(onExpired).toHaveBeenCalledTimes(1);
    expect(result.current).toBe(false);
  });
});

describe('usePendingAwareSessionExpiry (PR 3351, review round 7 — JWT refresh during deferred wait)', () => {
  afterEach(() => {
    window.sessionStorage.removeItem('auth_token');
    vi.restoreAllMocks();
  });

  it('cancels the delayed redirect when the token was refreshed to a valid JWT while operations were pending', () => {
    // PR 3351 (review round 7, P2): истечение → redirectPending →
    // параллельный single-flight refresh обновил auth_token на JWT с
    // будущим exp → последняя операция завершена → onExpired НЕ
    // вызывается, redirectPending=false — восстановленная сессия не
    // прерывается ложным logout.
    installToken(Date.now() - 60_000);
    const onExpired = vi.fn();
    let pending = true;

    const { result, rerender } = renderHook(
      ({ signal }: { signal: number }) => usePendingAwareSessionExpiry({
        hasPendingOperations: () => pending,
        pendingOperationsSignal: signal,
        onWarning: () => {},
        onExpired,
      }),
      { initialProps: { signal: 0 } },
    );

    expect(onExpired).not.toHaveBeenCalled();
    expect(result.current).toBe(true);

    // Токен обновили (например, фоновый API-запрос сделал single-flight
    // refresh) — новый JWT действует ещё час.
    installToken(Date.now() + 60 * 60_000);

    pending = false;
    rerender({ signal: 1 });

    expect(onExpired).not.toHaveBeenCalled();
    expect(result.current).toBe(false);
  });

  it('still fires onExpired once when the token was never refreshed after expiry', () => {
    // Комплемент предыдущего теста: refresh не случился — отложенный
    // переход выполняется ровно один раз (прежний контракт round 6).
    installToken(Date.now() - 60_000);
    const onExpired = vi.fn();
    let pending = true;

    const { result, rerender } = renderHook(
      ({ signal }: { signal: number }) => usePendingAwareSessionExpiry({
        hasPendingOperations: () => pending,
        pendingOperationsSignal: signal,
        onWarning: () => {},
        onExpired,
      }),
      { initialProps: { signal: 0 } },
    );

    expect(result.current).toBe(true);

    pending = false;
    rerender({ signal: 1 });

    expect(onExpired).toHaveBeenCalledTimes(1);
    expect(result.current).toBe(false);
  });

  it('fires onExpired when the token disappeared entirely while waiting', () => {
    // Токен удалён (разлогин в другой вкладке / storage очищен) —
    // сессии нет, redirect выполняется после завершения операций.
    installToken(Date.now() - 60_000);
    const onExpired = vi.fn();
    let pending = true;

    const { result, rerender } = renderHook(
      ({ signal }: { signal: number }) => usePendingAwareSessionExpiry({
        hasPendingOperations: () => pending,
        pendingOperationsSignal: signal,
        onWarning: () => {},
        onExpired,
      }),
      { initialProps: { signal: 0 } },
    );

    expect(result.current).toBe(true);
    window.sessionStorage.removeItem('auth_token');

    pending = false;
    rerender({ signal: 1 });

    expect(onExpired).toHaveBeenCalledTimes(1);
    expect(result.current).toBe(false);
  });
});

describe('usePendingAwareSessionExpiry (PR 3351, review round 8 — token generation recovery)', () => {
  afterEach(() => {
    window.sessionStorage.removeItem('auth_token');
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('notifies onSessionRecovered and immediately clears redirectPending when the poll sees a NEW valid token generation while operations are still pending (review round 9)', async () => {
    // PR 3351 (review round 8, P2): gen N истёк поверх pending-операции →
    // redirectPending=true; API-клиент выполнил single-flight refresh →
    // gen N+1 в sessionStorage. Следующий тик опроса видит смену ЗНАЧЕНИЯ
    // токена: warningFired/expiredFired сбрасываются, onSessionRecovered
    // снимает висящее предупреждение НЕ ДОЖИДАЯСЬ завершения операций —
    // диалог «Сессия скоро истечёт» лгал бы уже восстановленной сессии.
    // PR 3351 (review round 9, P2): валидное поколение снимает и
    // redirectPending НЕМЕДЛЕННО — overlay «сессия истекла, ожидаем
    // операцию» лгал бы живой сессии, а зависший без ответа POST держал
    // бы его бессрочно. Pending-операция остаётся защищённой pending-
    // реестрами провайдера — ложный session-expiry overlay не нужен.
    vi.useFakeTimers();
    installToken(Date.now() - 60_000);
    const onExpired = vi.fn();
    const onSessionRecovered = vi.fn();
    let pending = true;

    const { result, rerender } = renderHook(
      ({ signal }: { signal: number }) => usePendingAwareSessionExpiry({
        hasPendingOperations: () => pending,
        pendingOperationsSignal: signal,
        onWarning: () => {},
        onExpired,
        onSessionRecovered,
      }),
      { initialProps: { signal: 0 } },
    );

    // Истечение поверх pending: redirect отложен, восстановления ещё нет.
    expect(result.current).toBe(true);
    expect(onSessionRecovered).not.toHaveBeenCalled();

    // Refresh: gen N+1 (другое значение, валидный exp) — в хранилище.
    installToken(Date.now() + 60 * 60_000);
    await act(async () => {
      vi.advanceTimersByTime(30_000);
    });

    // Смена поколения оповещена; logout НЕ выполнен; redirectPending
    // снят НЕМЕДЛЕННО — операция ещё висит, но overlay об истечении
    // больше не лжёт восстановленной сессии.
    expect(onSessionRecovered).toHaveBeenCalledTimes(1);
    expect(onExpired).not.toHaveBeenCalled();
    expect(result.current).toBe(false);

    // Операция завершена (сигнал сменился): redirect уже отменён —
    // ожидающий эффект не активен, второго восстановления нет, ложного
    // logout тоже нет.
    pending = false;
    await act(async () => {
      rerender({ signal: 1 });
    });
    expect(onSessionRecovered).toHaveBeenCalledTimes(1);
    expect(onExpired).not.toHaveBeenCalled();
    expect(result.current).toBe(false);
  });

  it('recovers when the refresh lands between polls: the pending-completion branch re-checks the token', () => {
    // PR 3351 (review round 8, P2): refresh произошёл за мгновение ДО
    // завершения операций — тик опроса ещё не видел gen N+1. Отложенный
    // redirect всё равно отменён: ветка завершения перечитывает токен и
    // оповещает onSessionRecovered (без ложного logout).
    installToken(Date.now() - 60_000);
    const onExpired = vi.fn();
    const onSessionRecovered = vi.fn();
    let pending = true;

    const { result, rerender } = renderHook(
      ({ signal }: { signal: number }) => usePendingAwareSessionExpiry({
        hasPendingOperations: () => pending,
        pendingOperationsSignal: signal,
        onWarning: () => {},
        onExpired,
        onSessionRecovered,
      }),
      { initialProps: { signal: 0 } },
    );

    expect(result.current).toBe(true);

    // Refresh есть в хранилище, но опрос его ещё НЕ тикал.
    installToken(Date.now() + 60 * 60_000);
    pending = false;
    rerender({ signal: 1 });

    expect(onSessionRecovered).toHaveBeenCalledTimes(1);
    expect(onExpired).not.toHaveBeenCalled();
    expect(result.current).toBe(false);
  });

  it('warns again for a short-lived refreshed token: the generation change resets the fired flags', async () => {
    // PR 3351 (review round 8, P2): прежний сброс fired-флагов жил только в
    // else-ветке (remaining > threshold) и пропускал короткоживущие
    // обновления: gen N истёк (expiredFired=true) → refresh → gen N+1 с
    // remaining ≤ 5-мин порога → warningFired оставался true —
    // предупреждение для N+1 не срабатывало, а его истечение молча не
    // вызывало onExpired. Смена ЗНАЧЕНИЯ сбрасывает оба флага: новый токен
    // получает собственный жизненный цикл предупреждения.
    vi.useFakeTimers();
    installToken(Date.now() - 60_000);
    const onWarning = vi.fn();
    const onExpired = vi.fn();
    const onSessionRecovered = vi.fn();
    // В этом сценарии состав операций не меняется — сигнал не дергается.
    const pending = true;

    renderHook(
      ({ signal }: { signal: number }) => usePendingAwareSessionExpiry({
        hasPendingOperations: () => pending,
        pendingOperationsSignal: signal,
        onWarning,
        onExpired,
        onSessionRecovered,
      }),
      { initialProps: { signal: 0 } },
    );

    // gen N+1: короткоживущий — 60 секунд (внутри warning-порога).
    installToken(Date.now() + 60_000);
    await act(async () => {
      vi.advanceTimersByTime(30_000);
    });

    // Поколение сменилось → флаги сброшены → предупреждение для gen N+1
    // срабатывает (раньше молчало), восстановление оповещено.
    expect(onWarning).toHaveBeenCalledTimes(1);
    expect(onSessionRecovered).toHaveBeenCalledTimes(1);
    expect(onExpired).not.toHaveBeenCalled();
  });

  it('does not report recovery when the token was removed (logout in another tab)', async () => {
    // Снятие токена — не восстановление: onTokenChanged не вызывается,
    // ложного onSessionRecovered нет; после завершения операций —
    // штатный onExpired (комплемент round-7 «token disappeared»).
    vi.useFakeTimers();
    installToken(Date.now() - 60_000);
    const onExpired = vi.fn();
    const onSessionRecovered = vi.fn();
    let pending = true;

    const { result, rerender } = renderHook(
      ({ signal }: { signal: number }) => usePendingAwareSessionExpiry({
        hasPendingOperations: () => pending,
        pendingOperationsSignal: signal,
        onWarning: () => {},
        onExpired,
        onSessionRecovered,
      }),
      { initialProps: { signal: 0 } },
    );

    expect(result.current).toBe(true);

    window.sessionStorage.removeItem('auth_token');
    await act(async () => {
      vi.advanceTimersByTime(30_000);
    });
    expect(onSessionRecovered).not.toHaveBeenCalled();

    pending = false;
    await act(async () => {
      rerender({ signal: 1 });
    });
    expect(onExpired).toHaveBeenCalledTimes(1);
    expect(onSessionRecovered).not.toHaveBeenCalled();
    expect(result.current).toBe(false);
  });
});
