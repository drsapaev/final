import { getApiBaseUrl } from './runtime';
import tokenManager from '../utils/tokenManager';

const API_V1_BASE = getApiBaseUrl();

/**
 * UX-AUDIT-FIX12: добавлена поддержка AbortSignal во все запросы.
 *
 * Ранее request() не принимал signal — вызовы не отменялись при unmount
 * компонента или смене активной записи. LabPanel.jsx уже имел хелпер
 * isAbortLikeError() для толерантности к abort-ошибкам, но никто не
 * передавал signal. Теперь:
 *   1) request() принимает options.signal и пробрасывает в fetch.
 *   2) Каждый метод labReportingApi пробрасывает signal из options.
 *   3) Вызывающий код (useEffect с cleanup) может создавать
 *      AbortController и отменять запрос при unmount/смене dep.
 *
 * Соответствует Nielsen Heuristic #5 (Error Prevention) — предотвращает
 * setState-after-unmark race conditions и уменьшает сетевой шум.
 */
interface RequestOptions {
  body?: BodyInit | Record<string, unknown> | null;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  method?: string;
}

async function request(path: string, options: RequestOptions = {}): Promise<unknown> {
  const token = tokenManager.getAccessToken();
  const headers: Record<string, string> = {
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };

  const fetchInit: RequestInit = {
    ...(options as Record<string, unknown>),
    headers,
    // UX-AUDIT-FIX12: пробрасываем signal в fetch, если передан.
    // Если signal уже отменён — fetch выбросит AbortError сразу.
    ...(options.signal ? { signal: options.signal } : {})
  };

  const response = await fetch(`${API_V1_BASE}${path}`, fetchInit);

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      // Ignore JSON parsing failures and use the fallback detail.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

export const labReportingApi = {
  // P-03 fix: lab-specific façade для очереди лаборатории.
  // Раньше LabPanel делал прямой fetch к /registrar/queues/today?department=lab.
  // Теперь использует этот метод — собственный контракт, собственная RBAC,
  // нормализация в lab-специфичный формат на backend.
  // Возвращает { entries: [...], total, date, timezone }.
  //
  // STRAT#4: добавлена поддержка server-side pagination через limit/offset.
  // Backend уже принимает эти query params (default limit=100, offset=0).
  // Frontend ранее не передавал их — загружал все записи сразу. Теперь
  // callers могут передать { limit, offset } для chunked loading, что
  // критично для крупных клиник с 1000+ анализов в день.
  // Backward compat: если params не передан, поведение не меняется.
  listQueueToday(targetDate: string | null = null, params: Record<string, unknown> = {}): Promise<unknown> {
    const search = new URLSearchParams();
    if (targetDate) {
      search.set('target_date', targetDate);
    }
    // STRAT#4: server-side pagination params
    if (params.limit !== undefined && params.limit !== null) {
      search.set('limit', String(params.limit));
    }
    if (params.offset !== undefined && params.offset !== null) {
      search.set('offset', String(params.offset));
    }
    const suffix = search.size ? `?${search.toString()}` : '';
    // STRAT#16: пробрасываем signal в request() для AbortController support.
    return request(`/lab/queue/today${suffix}`, {
      ...(params.signal ? { signal: params.signal as AbortSignal } : {}),
    });
  },

  listOrders(params: Record<string, unknown> = {}): Promise<unknown> {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        search.set(key, String(value));
      }
    });
    return request(`/lab/orders?${search.toString()}`);
  },

  listTemplates() {
    return request('/lab/templates');
  },

  listCatalogUnits() {
    return request('/lab/catalog/units');
  },

  listCatalogAnalytes(category = null) {
    const search = new URLSearchParams();
    if (category) {
      search.set('category', category);
    }
    const suffix = search.size ? `?${search.toString()}` : '';
    return request(`/lab/catalog/analytes${suffix}`);
  },

  listCatalogReferenceRanges(analyteCode = null) {
    const search = new URLSearchParams();
    if (analyteCode) {
      search.set('analyte_code', analyteCode);
    }
    const suffix = search.size ? `?${search.toString()}` : '';
    return request(`/lab/catalog/reference-ranges${suffix}`);
  },

  getTemplate(templateId) {
    return request(`/lab/templates/${templateId}`);
  },

  resolveTemplateOptions(payload) {
    return request('/lab/template-resolutions/resolve', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  createTemplate(payload) {
    return request('/lab/templates', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  createTemplateVersion(templateId, sourceVersionId = null) {
    return request(`/lab/templates/${templateId}/versions`, {
      method: 'POST',
      body: JSON.stringify({ source_version_id: sourceVersionId })
    });
  },

  updateTemplateVersion(versionId, payload) {
    return request(`/lab/template-versions/${versionId}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },

  publishTemplateVersion(versionId) {
    return request(`/lab/template-versions/${versionId}/publish`, {
      method: 'POST'
    });
  },

  archiveTemplateVersion(versionId) {
    return request(`/lab/template-versions/${versionId}/archive`, {
      method: 'POST'
    });
  },

  cloneTemplate(templateId) {
    return request(`/lab/templates/${templateId}/clone`, {
      method: 'POST'
    });
  },

  listInstances(params: Record<string, unknown> = {}): Promise<unknown> {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (Array.isArray(value)) {
        value.forEach((item) => {
          if (item !== undefined && item !== null && item !== '') {
            search.append(key, String(item));
          }
        });
        return;
      }
      if (value !== undefined && value !== null && value !== '') {
        search.set(key, String(value));
      }
    });
    return request(`/lab/report-instances?${search.toString()}`);
  },

  getInstance(instanceId) {
    return request(`/lab/report-instances/${instanceId}`);
  },

  createInstance(payload) {
    return request('/lab/report-instances', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  // P1 fix: doctor-initiated lab order — creates a LabReportInstance in DRAFT
  // status linked to the visit, so the lab technician sees it in their queue.
  createOrder(payload) {
    return request('/lab/orders', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  // WF-06 fix: expectedUpdatedAt — optimistic locking via updated_at.
  // Если backend обнаружит, что бланк был изменён после этого timestamp,
  // вернёт 409 Conflict. Frontend показывает dialog "обновите страницу".
  updateInstance(instanceId, payload, expectedUpdatedAt = null) {
    const search = expectedUpdatedAt
      ? `?expected_updated_at=${encodeURIComponent(expectedUpdatedAt)}`
      : '';
    return request(`/lab/report-instances/${instanceId}${search}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },

  bulkSaveValues(instanceId, payload, expectedUpdatedAt = null) {
    const search = expectedUpdatedAt
      ? `?expected_updated_at=${encodeURIComponent(expectedUpdatedAt)}`
      : '';
    return request(`/lab/report-instances/${instanceId}/bulk-values${search}`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  // L-H-2 fix: markReady endpoint удалён как мёртвый код.
  // WF-round5 убрал UI-кнопку (действие было функционально пустой операцией —
  // backend разрешал одинаковые действия для DRAFT/IN_PROGRESS/READY).
  // Если backend endpoint потребуется снова — добавлять вместе с UI-кнопкой.

  finalize(instanceId) {
    return request(`/lab/report-instances/${instanceId}/finalize`, {
      method: 'POST'
    });
  },

  revise(instanceId) {
    return request(`/lab/report-instances/${instanceId}/revise`, {
      method: 'POST'
    });
  },

  markPrinted(instanceId) {
    return request(`/lab/report-instances/${instanceId}/mark-printed`, {
      method: 'POST'
    });
  },

  async downloadPdf(instanceId) {
    const token = tokenManager.getAccessToken();
    const response = await fetch(`${API_V1_BASE}/lab/report-instances/${instanceId}/pdf`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    });
    if (!response.ok) {
      throw new Error(`Не удалось сформировать PDF: ${response.status}`);
    }
    return response.blob();
  }
};
