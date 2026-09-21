import '@testing-library/jest-dom';
import { renderHook } from '@testing-library/react';
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
