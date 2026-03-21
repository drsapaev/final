import { getApiBaseUrl } from './runtime';
import tokenManager from '../utils/tokenManager';

const API_V1_BASE = getApiBaseUrl();

async function request(path, options = {}) {
  const token = tokenManager.getAccessToken();
  const headers = {
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };

  const response = await fetch(`${API_V1_BASE}${path}`, {
    ...options,
    headers
  });

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
  listOrders(params = {}) {
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

  listInstances(params = {}) {
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

  updateInstance(instanceId, payload) {
    return request(`/lab/report-instances/${instanceId}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },

  bulkSaveValues(instanceId, payload) {
    return request(`/lab/report-instances/${instanceId}/bulk-values`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  markReady(instanceId) {
    return request(`/lab/report-instances/${instanceId}/mark-ready`, {
      method: 'POST'
    });
  },

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
