/**
 * Audit 3892 round 3 — fail-first regression for DENTPHI-FE-001:
 * per-patient clinical visit protocols must not persist in unscoped,
 * plaintext localStorage. The legacy dentist_panel_documents_v1 key is
 * purged instead of read, nothing is ever written back, and a fresh mount
 * (another clinician on the same shared browser) starts with no residual
 * protocol data.
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../../api/client';

import { useDentistVisitProtocols } from '../useDentistVisitProtocols';
import { DENTIST_DOCUMENTS_STORAGE_KEY } from '../../../utils/dentistryDocuments';

vi.mock('../../../api/client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
}));
vi.mock('../../../utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock('../../../services/notify', () => ({
  default: { info: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

const t = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

const legacyPayload = JSON.stringify({
  visitProtocols: [{
    visit_id: 41,
    patient_id: 7,
    patient_name: 'SYNTHETIC Patient A',
    visitData: { diagnosis: 'PHI-level clinical detail', recommendations: 'PHI instructions' },
  }],
});

const makeHookArgs = (selectedPatient: Record<string, unknown> | null) => ({
  tI18n: t,
  selectedPatient,
  setSelectedPatient: vi.fn(),
  setShowVisitProtocol: vi.fn(),
});

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  vi.mocked(apiClient.get).mockResolvedValue({ status: 404, data: null } as never);
  vi.mocked(apiClient.post).mockResolvedValue({
    data: { data: {}, visit_id: 41, patient_id: 7, row_version: 2, status: 'draft' },
  } as never);
});

describe('useDentistVisitProtocols PHI storage (DENTPHI-FE-001, audit 3892 round 3)', () => {
  it('the legacy localStorage key is purged instead of hydrated', () => {
    window.localStorage.setItem(DENTIST_DOCUMENTS_STORAGE_KEY, legacyPayload);

    const { result } = renderHook(() => useDentistVisitProtocols(makeHookArgs(null)));

    // Another clinician's identifiable clinical data are not resurrected.
    expect(result.current.savedVisitProtocols).toEqual([]);
    // The at-rest PHI payload is actively removed from the shared browser.
    expect(window.localStorage.getItem(DENTIST_DOCUMENTS_STORAGE_KEY)).toBeNull();
  });

  it('persisting a protocol keeps localStorage empty (memory + EMR only)', async () => {
    const { result } = renderHook(() => useDentistVisitProtocols(makeHookArgs(null)));

    await act(async () => {
      await result.current.persistVisitProtocol(
        { patient_id: 7, visit_id: 41, patient_name: 'SYNTHETIC Patient A' },
        { diagnosis: 'clinical detail', recommendations: 'review in one week' },
      );
    });

    await waitFor(() => expect(result.current.savedVisitProtocols).toHaveLength(1));
    // The EMR remains the source of truth; nothing lands in shared storage.
    expect(apiClient.post).toHaveBeenCalledWith('/v2/emr/41', expect.anything());
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)); });
    expect(window.localStorage.getItem(DENTIST_DOCUMENTS_STORAGE_KEY)).toBeNull();
  });

  it('a local-cache fallback after a failed EMR save also stays out of localStorage', async () => {
    vi.mocked(apiClient.post).mockRejectedValue(new Error('network unavailable') as never);
    const { result } = renderHook(() => useDentistVisitProtocols(makeHookArgs(null)));

    await act(async () => {
      await result.current.persistVisitProtocol(
        { patient_id: 7, visit_id: 41, patient_name: 'SYNTHETIC Patient A' },
        { diagnosis: 'clinical detail' },
      );
    });

    await waitFor(() => expect(result.current.savedVisitProtocols).toHaveLength(1));
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)); });
    expect(window.localStorage.getItem(DENTIST_DOCUMENTS_STORAGE_KEY)).toBeNull();
  });
});
