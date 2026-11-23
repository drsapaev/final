const TELEGRAM_WEB_APP_SDK_URL = 'https://telegram.org/js/telegram-web-app.js?65';
const TELEGRAM_WEB_APP_SDK_TIMEOUT_MS = 10_000;

let pendingLoad: Promise<boolean> | null = null;

/** Bootstrap the Mini App SDK. Identity is still verified by the server. */
export function loadTelegramWebApp(): Promise<boolean> {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return Promise.resolve(false);
  }
  if (window.Telegram?.WebApp) {
    return Promise.resolve(true);
  }
  if (pendingLoad) {
    return pendingLoad;
  }

  pendingLoad = new Promise<boolean>((resolve) => {
    const script = document.createElement('script');
    script.crossOrigin = 'anonymous';
    script.async = true;
    script.referrerPolicy = 'no-referrer';

    let settled = false;
    const finish = (available: boolean) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeout);
      script.removeEventListener('load', onLoad);
      script.removeEventListener('error', onError);
      if (!available) script.remove();
      resolve(available);
    };
    const onLoad = () => finish(Boolean(window.Telegram?.WebApp));
    const onError = () => finish(false);
    const timeout = window.setTimeout(onError, TELEGRAM_WEB_APP_SDK_TIMEOUT_MS);
    script.addEventListener('load', onLoad);
    script.addEventListener('error', onError);
    try {
      script.src = TELEGRAM_WEB_APP_SDK_URL;
      document.head.appendChild(script);
    } catch {
      finish(false);
    }
  }).then((available) => {
    pendingLoad = null;
    return available;
  });

  return pendingLoad;
}
