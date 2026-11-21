const TELEGRAM_WEB_APP_SDK_URL = 'https://telegram.org/js/telegram-web-app.js?62';
const TELEGRAM_WEB_APP_SDK_TIMEOUT_MS = 10_000;

let pendingLoad: Promise<boolean> | null = null;

/** Load only from a Mini App entrypoint; SDK availability is not authentication. */
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
    script.src = TELEGRAM_WEB_APP_SDK_URL;
    script.async = true;
    script.referrerPolicy = 'no-referrer';
    script.dataset.telegramWebAppSdk = 'true';
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
      document.head.appendChild(script);
    } catch {
      finish(false);
    }
  }).then((available) => {
    // A failed load can be retried by the route's explicit retry action.
    pendingLoad = null;
    return available;
  });

  return pendingLoad;
}
