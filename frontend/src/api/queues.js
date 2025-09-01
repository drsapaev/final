import { apiRequest } from './client';

/**
 * Open online queue for a department on a date.
 * We always include start_number=0 to avoid server 422 when start_number is required.
 * Params:
 *  - department (string)
 *  - date_str (YYYY-MM-DD)
 *  - start_number (optional) -> we set default 0
 */
export function openOnlineQueue(department, dateStr, startNumber = 0) {
  // open endpoint expects query parameters (per openapi), so using GET or POST depending on backend;
  // original backend defines POST /online-queue/open?department=...&date_str=...&start_number=...
  return apiRequest('post', '/online-queue/open', {
    params: { department, date_str: dateStr, start_number: startNumber },
    data: {}, // body empty but use POST as backend expects
  });
}

export function getOnlineQueueStats(department, dateStr) {
  return apiRequest('get', '/online-queue/stats', {
    params: { department, d: dateStr },
  });
}

export function getOnlineQueueQrcode(department, dateStr) {
  return apiRequest('get', '/online-queue/qrcode', {
    params: { department, d: dateStr },
  });
}
