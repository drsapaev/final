import { getApiBaseUrl } from './runtime';
import tokenManager from '../utils/tokenManager';
import { forceRefreshToken } from './client';
import type { LabWorklistPage, LabWorklistQuery } from '../types/features/labWorkspace';

const API_V1_BASE = getApiBaseUrl();
const DRAFT_REQUEST_TIMEOUT_MS = 25_000;

function normalizePatientId(value: unknown) {
  const id = typeof value === 'number' || typeof value === 'string' ? Number(value) : NaN;
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

function isAmbiguousCreationError(error: unknown) {
  if (typeof error === 'object' && error !== null && 'status' in error && typeof error.status === 'number') {
    return error.status >= 500 || (error.status === 409 && 'code' in error
      && (error.code === 'idempotency_uncertain_outcome' || error.code === 'idempotency_in_flight'));
  }
  return error instanceof TypeError || error instanceof SyntaxError || (
    error instanceof DOMException && ['AbortError', 'TimeoutError', 'NetworkError'].includes(error.name)
  );
}

function draftWriteSearch(expectedUpdatedAt: string | null, draftRequestId?: string) {
  const search = new URLSearchParams();
  if (expectedUpdatedAt) search.set('expected_updated_at', expectedUpdatedAt);
  if (draftRequestId) search.set('draft_request_id', draftRequestId);
  const query = search.toString();
  return query ? `?${query}` : '';
}

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
  responseType?: 'blob';
}

/** LABR-FE-001 (audit 3886): true for a rejected 401 from an expired access JWT. */
function isAuthRejected(error: unknown): boolean {
  return (
    error !== null &&
    typeof error === 'object' &&
    (error as { status?: unknown }).status === 401
  );
}

/**
 * LABR-FE-001 (audit 3886): converge the lab transport on the canonical
 * shared expired-JWT refresh. A rejected 401 (the server did NOT execute
 * the command) is safely retried once after a single-flight refresh —
 * including for mutations, which keep their Idempotency-Key. Ambiguous
 * transport errors are handled by the calling operation.
 */
async function withAuthRetry<T>(perform: () => Promise<T>): Promise<T> {
  try {
    return await perform();
  } catch (error) {
    if (!isAuthRejected(error)) {
      throw error;
    }
    const refreshed = await forceRefreshToken();
    if (!refreshed) {
      throw error;
    }
    return perform();
  }
}

async function request(path: string, options: RequestOptions = {}): Promise<unknown> {
  const { responseType, ...requestOptions } = options;
  const run = async (): Promise<unknown> => {
    const token = tokenManager.getAccessToken();
    const headers: Record<string, string> = {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    };

    const fetchInit: RequestInit = {
      ...(requestOptions as Record<string, unknown>),
      headers,
      // UX-AUDIT-FIX12: пробрасываем signal в fetch, если передан.
      // Если signal уже отменён — fetch выбросит AbortError сразу.
      ...(options.signal ? { signal: options.signal } : {})
    };

    const response = await fetch(`${API_V1_BASE}${path}`, fetchInit);

    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      let code: string | undefined;
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
        if (typeof payload.code === 'string') code = payload.code;
      } catch {
        // Ignore JSON parsing failures and use the fallback detail.
      }
      throw Object.assign(new Error(detail), {
        status: response.status,
        ...(code ? { code } : {}),
      });
    }

    if (response.status === 204) {
      return null;
    }
    if (responseType === 'blob') return response.blob();
    return response.json();
  };

  return withAuthRetry(run);
}

export { request as requestLab };

export const labReportingApi = {
  listWorklist(query: LabWorklistQuery, options: { cursor?: string; signal?: AbortSignal } = {}) {
    return request('/lab/worklist/search', {
      method: 'POST',
      body: JSON.stringify({
        view: query.view,
        sort: query.sort,
        limit: 50,
        q: query.q.trim() || undefined,
        barcode: query.barcode,
        from_date: query.fromDate,
        to_date: query.toDate,
        cursor: options.cursor,
      }),
      signal: options.signal,
    }) as Promise<LabWorklistPage>;
  },

  cancelOrderedTest(visitId: number, visitServiceId: number, orderId: number | null, reason: string) {
    return request(`/lab/visits/${visitId}/tests/${visitServiceId}/cancel`, {
      method: 'POST', body: JSON.stringify({ order_id: orderId, reason }),
    });
  },
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

  getTemplate(templateId: string | number) {
    return request(`/lab/templates/${templateId}`);
  },

  resolveTemplateOptions(payload: Record<string, unknown>) {
    return request('/lab/template-resolutions/resolve', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  createTemplate(payload: Record<string, unknown>) {
    return request('/lab/templates', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  createTemplateVersion(templateId: string | number, sourceVersionId: string | number | null = null) {
    return request(`/lab/templates/${templateId}/versions`, {
      method: 'POST',
      body: JSON.stringify({ source_version_id: sourceVersionId })
    });
  },

  updateTemplateVersion(versionId: string | number, payload: Record<string, unknown>) {
    return request(`/lab/template-versions/${versionId}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },

  publishTemplateVersion(versionId: string | number) {
    return request(`/lab/template-versions/${versionId}/publish`, {
      method: 'POST'
    });
  },

  archiveTemplateVersion(versionId: string | number) {
    return request(`/lab/template-versions/${versionId}/archive`, {
      method: 'POST'
    });
  },

  cloneTemplate(templateId: string | number) {
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

  getInstance(instanceId: string | number, options?: Pick<RequestOptions, 'signal'>) {
    return request(`/lab/report-instances/${instanceId}`, options);
  },

  async createInstance(
    payload: Record<string, unknown>,
    options: { idempotencyKey?: string } = {},
  ) {
    const { idempotencyKey } = options;
    const body = JSON.stringify(payload);
    try {
      return await request('/lab/report-instances', {
        method: 'POST',
        body,
        ...(idempotencyKey ? { headers: { 'Idempotency-Key': idempotencyKey } } : {}),
      });
    } catch (error) {
      if (!idempotencyKey || !isAmbiguousCreationError(error)) throw error;
      // Recover only from a committed receipt for the original serialized request.
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), DRAFT_REQUEST_TIMEOUT_MS);
      try {
        const originalRequest = JSON.parse(body) as Record<string, unknown>;
        const patientId = normalizePatientId(originalRequest?.patient_id);
        const recovered = await request('/lab/report-instances/creation-result', {
          method: 'POST',
          body: JSON.stringify({ idempotency_key: idempotencyKey, request: originalRequest }),
          signal: controller.signal,
        });
        if (typeof recovered === 'object' && recovered !== null && 'id' in recovered
          && typeof recovered.id === 'number' && Number.isSafeInteger(recovered.id) && recovered.id > 0
          && patientId !== null && 'patient_id' in recovered && normalizePatientId(recovered.patient_id) === patientId
          && 'updated_at' in recovered && typeof recovered.updated_at === 'string' && recovered.updated_at.trim()
          && 'sections' in recovered && Array.isArray(recovered.sections)) return recovered;
      } catch {
        // Preserve the original creation error when reconciliation is unavailable.
      } finally {
        clearTimeout(timeout);
      }
      throw error;
    }
  },

  // P1 fix: doctor-initiated lab order — creates a LabReportInstance in DRAFT
  // status linked to the visit, so the lab technician sees it in their queue.
  createOrder(payload: Record<string, unknown>) {
    return request('/lab/orders', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  // WF-06 fix: expectedUpdatedAt — optimistic locking via updated_at.
  // Если backend обнаружит, что бланк был изменён после этого timestamp,
  // вернёт 409 Conflict. Frontend показывает dialog "обновите страницу".
  updateInstance(
    instanceId: string | number,
    payload: Record<string, unknown>,
    expectedUpdatedAt: string | null = null,
    draftRequestId?: string,
  ) {
    const search = draftWriteSearch(expectedUpdatedAt, draftRequestId);
    return request(`/lab/report-instances/${instanceId}${search}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout?.(DRAFT_REQUEST_TIMEOUT_MS),
    });
  },

  bulkSaveValues(
    instanceId: string | number,
    payload: Array<Record<string, unknown>>,
    expectedUpdatedAt: string | null = null,
    draftRequestId?: string,
  ) {
    const search = draftWriteSearch(expectedUpdatedAt, draftRequestId);
    return request(`/lab/report-instances/${instanceId}/bulk-values${search}`, {
      method: 'POST',
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout?.(DRAFT_REQUEST_TIMEOUT_MS),
    });
  },

  // L-H-2 fix: markReady endpoint удалён как мёртвый код.
  // WF-round5 убрал UI-кнопку (действие было функционально пустой операцией —
  // backend разрешал одинаковые действия для DRAFT/IN_PROGRESS/READY).
  // Если backend endpoint потребуется снова — добавлять вместе с UI-кнопкой.

  finalize(instanceId: string | number, expectedUpdatedAt?: string) {
    return request(`/lab/report-instances/${instanceId}/finalize`, {
      method: 'POST',
      ...(expectedUpdatedAt ? { body: JSON.stringify({ expected_updated_at: expectedUpdatedAt }) } : {}),
    });
  },

  revise(instanceId: string | number, payload?: { expected_updated_at?: string; reason: string }) {
    return request(`/lab/report-instances/${instanceId}/revise`, {
      method: 'POST',
      ...(payload ? { body: JSON.stringify(payload) } : {}),
    });
  },

  submitReview(instanceId: string | number, expectedUpdatedAt: string) {
    return request(`/lab/report-instances/${instanceId}/submit-review`, {
      method: 'POST', body: JSON.stringify({ expected_updated_at: expectedUpdatedAt }),
    });
  },

  review(instanceId: string | number, expectedUpdatedAt: string) {
    return request(`/lab/report-instances/${instanceId}/review`, {
      method: 'POST', body: JSON.stringify({ expected_updated_at: expectedUpdatedAt }),
    });
  },

  returnToDraft(instanceId: string | number, payload: { expected_updated_at: string; reason: string }) {
    return request(`/lab/report-instances/${instanceId}/return-to-draft`, {
      method: 'POST', body: JSON.stringify(payload),
    });
  },

  recordQC(instanceId: string | number, payload: {
    expected_updated_at: string;
    status: 'accepted' | 'rejected' | 'not_applicable';
    reason?: string;
    method?: string;
    instrument_ref?: string;
    series_ref?: string;
  }) {
    return request(`/lab/report-instances/${instanceId}/qc`, {
      method: 'POST', body: JSON.stringify(payload),
    });
  },

  markPrinted(instanceId: string | number) {
    return request(`/lab/report-instances/${instanceId}/mark-printed`, {
      method: 'POST'
    });
  },

  async downloadPdf(instanceId: string | number) {
    const run = async (): Promise<Blob> => {
      const token = tokenManager.getAccessToken();
      const response = await fetch(`${API_V1_BASE}/lab/report-instances/${instanceId}/pdf`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (!response.ok) {
        throw Object.assign(new Error(`Не удалось сформировать PDF: ${response.status}`), { status: response.status });
      }
      return response.blob();
    };
    return withAuthRetry(run);
  },

  // PR8 (codex-lab-workflow-hardening-plan): серверный A4-preview того же
  // движка, что финальный PDF, ДО утверждения. Никаких побочных эффектов:
  // без mark-printed/уведомлений/финализации — просто blob для просмотра.
  // Рендерятся сохранённые значения (Save Draft до preview).
  async previewInstancePdf(instanceId: string | number) {
    const run = async (): Promise<Blob> => {
      const token = tokenManager.getAccessToken();
      const response = await fetch(`${API_V1_BASE}/lab/report-instances/${instanceId}/preview`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (!response.ok) {
        throw Object.assign(new Error(`Не удалось сформировать предпросмотр: ${response.status}`), { status: response.status });
      }
      return response.blob();
    };
    return withAuthRetry(run);
  },

  // PR8: template preview — рендер СОХРАНЁННОЙ версии шаблона со
  // синтетическими placeholder-значениями (без данных пациентов).
  async previewTemplateVersionPdf(versionId: string | number) {
    const run = async (): Promise<Blob> => {
      const token = tokenManager.getAccessToken();
      const response = await fetch(`${API_V1_BASE}/lab/template-versions/${versionId}/preview`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (!response.ok) {
        throw Object.assign(new Error(`Не удалось сформировать предпросмотр шаблона: ${response.status}`), { status: response.status });
      }
      return response.blob();
    };
    return withAuthRetry(run);
  }
};
