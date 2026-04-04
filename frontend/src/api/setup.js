import { buildApiUrl } from './runtime';

async function parseJsonResponse(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail = payload?.detail || payload?.message || 'Setup request failed';
    throw new Error(detail);
  }

  return payload;
}

export async function fetchSetupStatus() {
  const response = await fetch(buildApiUrl('/setup/status'));
  return parseJsonResponse(response);
}

export async function initializeSetup(payload) {
  const response = await fetch(buildApiUrl('/setup/initialize'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });

  return parseJsonResponse(response);
}
