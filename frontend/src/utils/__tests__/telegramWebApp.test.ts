import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const sdkSelector = 'script[data-telegram-web-app-sdk="true"]';

function installWebApp() {
  (window as unknown as { Telegram?: unknown }).Telegram = {
    WebApp: { initData: 'synthetic-init-data' },
  };
}

describe('route-scoped Telegram WebApp SDK loader', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.useFakeTimers();
    delete window.Telegram;
  });

  afterEach(() => {
    document.querySelectorAll(sdkSelector).forEach((script) => script.remove());
    delete window.Telegram;
    vi.useRealTimers();
  });

  it('does not load a third-party script until explicitly called', async () => {
    await import('../telegramWebApp');
    expect(document.querySelector(sdkSelector)).toBeNull();
  });

  it('preserves an already initialized WebApp without another script', async () => {
    installWebApp();
    const { loadTelegramWebApp } = await import('../telegramWebApp');
    await expect(loadTelegramWebApp()).resolves.toBe(true);
    expect(document.querySelector(sdkSelector)).toBeNull();
  });

  it('shares one pending official HTTPS load and waits for WebApp initialization', async () => {
    const { loadTelegramWebApp } = await import('../telegramWebApp');
    const first = loadTelegramWebApp();
    const second = loadTelegramWebApp();
    expect(first).toBe(second);
    const scripts = document.querySelectorAll<HTMLScriptElement>(sdkSelector);
    expect(scripts).toHaveLength(1);
    expect(scripts[0].src).toBe('https://telegram.org/js/telegram-web-app.js?62');
    expect(scripts[0].crossOrigin).toBe('anonymous');
    expect(scripts[0].referrerPolicy).toBe('no-referrer');
    expect(scripts[0].async).toBe(true);
    installWebApp();
    scripts[0].dispatchEvent(new Event('load'));
    await expect(first).resolves.toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('allows an explicit retry after a network failure', async () => {
    const { loadTelegramWebApp } = await import('../telegramWebApp');
    const failed = loadTelegramWebApp();
    const firstScript = document.querySelector(sdkSelector)!;
    firstScript.dispatchEvent(new Event('error'));
    await expect(failed).resolves.toBe(false);
    expect(firstScript.isConnected).toBe(false);
    const retry = loadTelegramWebApp();
    const retryScript = document.querySelector(sdkSelector)!;
    expect(retryScript).not.toBe(firstScript);
    installWebApp();
    retryScript.dispatchEvent(new Event('load'));
    await expect(retry).resolves.toBe(true);
  });

  it('bounds a stalled load and ignores its late event before retry', async () => {
    const { loadTelegramWebApp } = await import('../telegramWebApp');
    const failed = loadTelegramWebApp();
    const firstScript = document.querySelector(sdkSelector)!;
    await vi.advanceTimersByTimeAsync(10_000);
    await expect(failed).resolves.toBe(false);
    expect(firstScript.isConnected).toBe(false);
    firstScript.dispatchEvent(new Event('load'));
    const retry = loadTelegramWebApp();
    const retryScript = document.querySelector(sdkSelector)!;
    installWebApp();
    retryScript.dispatchEvent(new Event('load'));
    await expect(retry).resolves.toBe(true);
  });

  it('does not treat a script load without WebApp as authentication or success', async () => {
    const { loadTelegramWebApp } = await import('../telegramWebApp');
    const pending = loadTelegramWebApp();
    document.querySelector(sdkSelector)!.dispatchEvent(new Event('load'));
    await expect(pending).resolves.toBe(false);
    expect(window.Telegram).toBeUndefined();
    expect(document.querySelector(sdkSelector)).toBeNull();
  });
});
