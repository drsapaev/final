/**
 * PR-UI-15-4 unit contract: useDentistDialogs view-state slice +
 * useDentistVisitProtocols EMR v2 lifecycle boundary (verbatim extraction
 * from DentistPanelUnified — registrar/cashier decomposition precedent).
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it, vi } from 'vitest';

import { useDentistDialogs } from '../useDentistDialogs';

vi.mock('../../../api/client', () => ({
  apiClient: {
    get: vi.fn(async () => ({ status: 200, data: [] })),
    post: vi.fn(async () => ({ status: 200, data: {} })),
  },
}));

import { useDentistVisitProtocols } from '../useDentistVisitProtocols';

const t = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

describe('useDentistDialogs (PR-UI-15-4)', () => {
  it('starts with every dialog closed and no selection state', () => {
    const { result } = renderHook(() => useDentistDialogs());
    const d = result.current;
    expect(d.showDentalChart).toBe(false);
    expect(d.showTreatmentPlanner).toBe(false);
    expect(d.showPatientCard).toBe(false);
    expect(d.showDiagnosisForm).toBe(false);
    expect(d.showVisitProtocol).toBe(false);
    expect(d.showPhotoArchive).toBe(false);
    expect(d.showProtocolTemplates).toBe(false);
    expect(d.showReports).toBe(false);
    expect(d.showPriceManager).toBe(false);
    expect(d.toothModalOpen).toBe(false);
    expect(d.dentalChartData).toBeNull();
    expect(d.selectedServiceForPrice).toBeNull();
    expect(d.selectedTooth).toBeNull();
    expect(d.protocolTemplateDraft).toBeNull();
    expect(d.scheduleNextModal).toEqual({ open: false, patient: null });
  });

  it('setters toggle their own dialog without touching others', () => {
    const { result } = renderHook(() => useDentistDialogs());
    act(() => {
      result.current.setShowVisitProtocol(true);
      result.current.setShowProtocolTemplates(true);
    });
    expect(result.current.showVisitProtocol).toBe(true);
    expect(result.current.showProtocolTemplates).toBe(true);
    expect(result.current.showPatientCard).toBe(false);
    expect(result.current.showPhotoArchive).toBe(false);
  });

  it('scheduleNextModal carries the patient payload (verbatim shape)', () => {
    const { result } = renderHook(() => useDentistDialogs());
    const patient = { id: 7, patient_name: 'SYNTHETIC-Patient-Seven' };
    act(() => {
      result.current.setScheduleNextModal({ open: true, patient });
    });
    expect(result.current.scheduleNextModal).toEqual({ open: true, patient });
    act(() => {
      result.current.setScheduleNextModal({ open: false, patient: null });
    });
    expect(result.current.scheduleNextModal).toEqual({ open: false, patient: null });
  });
});

describe('useDentistVisitProtocols (PR-UI-15-4)', () => {
  const noopDispatch = (() => {}) as unknown as React.Dispatch<React.SetStateAction<null>>;

  it('source boundary: every protocol read/write goes through EMR v2 (AC #4)', () => {
    const source = fs.readFileSync(
      path.resolve(process.cwd(), 'src/pages/dentist/useDentistVisitProtocols.ts'),
      'utf8',
    );
    expect(source).toContain('apiClient.get(`/v2/emr/patient/${patientId}`');
    expect(source).toContain('apiClient.get(`/v2/emr/${summary.visit_id}`');
    expect(source).toContain('apiClient.get(`/v2/emr/${visitId}`');
    expect(source).toContain('apiClient.post(`/v2/emr/${patientRecord.visit_id}`, payload)');
    // No parallel persistence stores: the only fallback is the local documents
    // cache (buildDentistVisitProtocolCard source: 'local_cache').
    expect(source).not.toContain('/api/v1/');
    expect(source).toContain("source: 'local_cache'");
  });

  it('exposes the protocol lifecycle surface (load/persist/reopen)', async () => {
    const setSelectedPatient = vi.fn();
    const setShowVisitProtocol = vi.fn();
    const { result } = renderHook(() =>
      useDentistVisitProtocols({
        tI18n: t,
        selectedPatient: null,
        setSelectedPatient,
        setShowVisitProtocol,
      }),
    );
    expect(typeof result.current.loadDentistVisitProtocolByVisitId).toBe('function');
    expect(typeof result.current.persistVisitProtocol).toBe('function');
    expect(typeof result.current.reopenVisitProtocol).toBe('function');
    expect(Array.isArray(result.current.savedVisitProtocols)).toBe(true);

    // No patient selected → loaders short-circuit / hydrate skips.
    await waitFor(() => expect(result.current.savedVisitProtocols).toEqual([]));
  });

  it('loadDentistVisitProtocolByVisitId returns null for falsy visit ids', async () => {
    const { result } = renderHook(() =>
      useDentistVisitProtocols({
        tI18n: t,
        selectedPatient: null,
        setSelectedPatient: noopDispatch as never,
        setShowVisitProtocol: () => {},
      }),
    );
    await expect(result.current.loadDentistVisitProtocolByVisitId(null)).resolves.toBeNull();
    await expect(result.current.loadDentistVisitProtocolByVisitId(undefined)).resolves.toBeNull();
  });

  it('persistVisitProtocol is a no-op without a visit_id (guard, verbatim)', async () => {
    const { result } = renderHook(() =>
      useDentistVisitProtocols({
        tI18n: t,
        selectedPatient: null,
        setSelectedPatient: noopDispatch as never,
        setShowVisitProtocol: () => {},
      }),
    );
    await expect(result.current.persistVisitProtocol({ patient_id: 1 }, {})).resolves.toBeUndefined();
  });

  it('reopenVisitProtocol notifies protocol_not_found when neither backend nor local data exists', async () => {
    const { apiClient } = await import('../../../api/client');
    (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ status: 404 });
    const notify = (await import('../../../services/notify')).default;
    const notifySpy = vi.spyOn(notify, 'error');

    const setSelectedPatient = vi.fn();
    const setShowVisitProtocol = vi.fn();
    const { result } = renderHook(() =>
      useDentistVisitProtocols({
        tI18n: t,
        selectedPatient: null,
        setSelectedPatient,
        setShowVisitProtocol,
      }),
    );

    await result.current.reopenVisitProtocol({ visit_id: 999, patient_id: 1 });
    expect(notifySpy).toHaveBeenCalledWith('dental.protocol_not_found');
    expect(setShowVisitProtocol).not.toHaveBeenCalled();
    notifySpy.mockRestore();
  });
});
