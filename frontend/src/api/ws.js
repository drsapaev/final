// Helper для WS с прокси. Управление — VITE_ENABLE_WS=0/1
function wsEnabled() {
  const v = (import.meta?.env?.VITE_ENABLE_WS ?? '0').toString().trim();
  return v === '1' || v.toLowerCase() === 'true';
}

function buildWsBase() {
  const raw = (import.meta?.env?.VITE_WS_BASE ?? '/ws').toString().trim();
  if (/^wss?:\/\//i.test(raw)) return raw.replace(/\/+$/, '');
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = location.host;
  const suffix = raw.startsWith('/') ? raw : `/${raw}`;
  return `${proto}//${host}${suffix}`.replace(/\/+$/, '');
}

/**
 * Открыть WS очереди. onMessage получает уже распарсенный объект.
 * Возвращает функцию close().
 */
export function openQueueWS(department, dateStr, onMessage) {
  if (!wsEnabled()) return () => {};
  let ws = null;

  try {
    const base = buildWsBase();
    const url = `${base}/queue?department=${encodeURIComponent(department)}&date_str=${encodeURIComponent(dateStr)}`;
    ws = new WebSocket(url);
    ws.onmessage = (ev) => {
      try {
        const obj = JSON.parse(ev.data);
        onMessage && onMessage(obj);
      } catch {
        // ignore
      }
    };
    ws.onerror = () => {};
    ws.onclose = () => {};
  } catch {
    // ignore
  }

  return function close() {
    try {
      ws && ws.close(1000, 'bye');
    } catch {
      // Игнорируем ошибки закрытия WebSocket
    }
    ws = null;
  };
}

