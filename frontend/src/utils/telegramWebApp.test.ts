import { afterEach, describe, expect, it, vi } from 'vitest';
import { loadTelegramWebApp } from './telegramWebApp';

const SDK_URL = 'https://telegram.org/js/telegram-web-app.js?65';
const selector = `script[src="${SDK_URL}"]`;

function getSdkScript() {
  const script = document.head.querySelector<HTMLScriptElement>(selector);
  if (!script) throw new Error('Expected the Telegram SDK script');
  return script;
}

describe('loadTelegramWebApp', () => {
  afterEach(() => {
    document.head.querySelectorAll(selector).forEach((script) => script.remove());
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('reuses the WebApp already provided by Telegram', async () => {
    vi.stubGlobal('Telegram', { WebApp: { initData: '', initDataUnsafe: {} } });

    await expect(loadTelegramWebApp()).resolves.toBe(true);
    expect(document.head.querySelector(selector)).toBeNull();
  });

  it('pools concurrent loads and waits for the WebApp to become available', async () => {
    const first = loadTelegramWebApp();
    const second = loadTelegramWebApp();
    const script = getSdkScript();

    expect(second).toBe(first);
    expect(document.head.querySelectorAll(selector)).toHaveLength(1);
    expect(script.crossOrigin).toBe('anonymous');
    expect(script.referrerPolicy).toBe('no-referrer');

    vi.stubGlobal('Telegram', { WebApp: { initData: '', initDataUnsafe: {} } });
    script.dispatchEvent(new Event('load'));

    await expect(first).resolves.toBe(true);
  });

  it('cleans up a failed script and permits a later attempt', async () => {
    const first = loadTelegramWebApp();
    const failedScript = getSdkScript();
    failedScript.dispatchEvent(new Event('error'));

    await expect(first).resolves.toBe(false);
    expect(failedScript.isConnected).toBe(false);

    const retry = loadTelegramWebApp();
    const retryScript = getSdkScript();
    expect(retryScript).not.toBe(failedScript);
    retryScript.dispatchEvent(new Event('load'));

    await expect(retry).resolves.toBe(false);
  });

  it('settles when a blocked request emits no event', async () => {
    vi.useFakeTimers();
    const load = loadTelegramWebApp();
    const script = getSdkScript();
    await vi.advanceTimersByTimeAsync(10_000);

    await expect(load).resolves.toBe(false);
    expect(script.isConnected).toBe(false);
  });

  it('settles during server rendering', async () => {
    vi.stubGlobal('window', undefined);

    await expect(loadTelegramWebApp()).resolves.toBe(false);
  });
});
