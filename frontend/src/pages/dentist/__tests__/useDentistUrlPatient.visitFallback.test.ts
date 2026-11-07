/**
 * Audit 3892 round 1 — fail-first regression for DENTURL-FE-001:
 * a visitId-only deep link must not fabricate `patient_id` from the visit id.
 * The fallback resolves the authoritative patient/visit relationship through
 * an authorized EMR read; an unmatched or unauthorized visit fails closed
 * (no patient selection, no invented identity).
 */
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../../api/client';
import logger from '../../../utils/logger';

import { useDentistUrlPatient } from '../useDentistUrlPatient';

vi.mock('../../../api/client', () => ({
  apiClient: { get: vi.fn() },
}));
vi.mock('../../../utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

const t = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

const makeHookArgs = (overrides: Record<string, unknown> = {}) => ({
  locationSearch: '?visitId=77',
  patientIdFromUrl: null as number | null,
  visitIdFromUrl: 77 as number | null,
  selectedPatient: null,
  appointmentsTableData: [] as never[],
  loadDentistryAppointments: vi.fn(async () => []),
  setSelectedPatient: vi.fn(),
  handleTabChange: vi.fn(),
  tI18n: t,
  ...overrides,
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(apiClient.get).mockResolvedValue({ status: 200, data: { row_version: 1, patient_id: 23, visit_id: 77, data: {} } } as never);
});

describe('useDentistUrlPatient visit-only deep link (DENTURL-FE-001, audit 3892 round 1)', () => {
  it('resolves the authoritative patient_id from the authorized visit read', async () => {
    const args = makeHookArgs();
    renderHook(() => useDentistUrlPatient(args));

    await waitFor(() => expect(args.setSelectedPatient).toHaveBeenCalledTimes(1));
    expect(args.setSelectedPatient).toHaveBeenCalledWith(expect.objectContaining({
      patient_id: 23,
      visit_id: 77,
      source: 'url',
    }));
    expect(args.handleTabChange).toHaveBeenCalledWith('visit');
    expect(apiClient.get).toHaveBeenCalledWith('/v2/emr/77', expect.anything());
  });

  it('fails closed when the visit read is unauthorized or missing', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ status: 404, data: null } as never);
    const args = makeHookArgs();
    renderHook(() => useDentistUrlPatient(args));

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(args.setSelectedPatient).not.toHaveBeenCalled();
    expect(args.handleTabChange).not.toHaveBeenCalled();
  });

  it('fails closed when the visit read errors', async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error('network unavailable') as never);
    const args = makeHookArgs();
    renderHook(() => useDentistUrlPatient(args));

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(args.setSelectedPatient).not.toHaveBeenCalled();
    expect(logger.error).toHaveBeenCalled();
  });

  it('keeps the patient-scoped fallback behavior when patientIdFromUrl is present', async () => {
    const args = makeHookArgs({
      locationSearch: '?patientId=23',
      patientIdFromUrl: 23,
      visitIdFromUrl: null,
    });
    renderHook(() => useDentistUrlPatient(args));

    await waitFor(() => expect(args.setSelectedPatient).toHaveBeenCalledWith(expect.objectContaining({
      patient_id: 23,
      source: 'url',
    })));
    // No visit-scoped EMR read is needed when the patient id is explicit.
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});
