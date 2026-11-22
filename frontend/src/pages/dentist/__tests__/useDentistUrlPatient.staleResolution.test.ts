/**
 * Audit 3892 round 3 — fail-first regression for DENTURL-FE-002:
 * a stale async URL hydration must never overwrite a newer patient/visit
 * selection. Each URL load binds to the normalized URL target and the
 * selection state at resolution time; a manual navigation to another
 * patient, a URL change, or an unmount revokes the stale resolution.
 */
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../../api/client';

import { useDentistUrlPatient } from '../useDentistUrlPatient';
import type { SelectedPatient } from '../dentistContracts';

vi.mock('../../../api/client', () => ({
  apiClient: { get: vi.fn() },
}));
vi.mock('../../../utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

const t = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

type HookArgs = Parameters<typeof useDentistUrlPatient>[0];

const makeArgs = (overrides: Partial<HookArgs> = {}): HookArgs => ({
  locationSearch: '?patientId=7',
  patientIdFromUrl: 7,
  visitIdFromUrl: null as number | null,
  selectedPatient: null,
  appointmentsTableData: [] as never[],
  loadDentistryAppointments: vi.fn(async () => []),
  setSelectedPatient: vi.fn(),
  handleTabChange: vi.fn(),
  tI18n: t,
  ...overrides,
});

const appointmentFor = (patientId: number, visitId: number) => ({
  id: patientId * 10,
  patient_id: patientId,
  visit_id: visitId,
  patient_fio: `SYNTHETIC Patient ${patientId}`,
  patient_name: `SYNTHETIC Patient ${patientId}`,
  appointment_id: null,
  patient_phone: '',
  specialty: 'dentistry',
  source: 'appointments',
}) as never;

const selected = (patientId: number, visitId: number): SelectedPatient =>
  ({ id: patientId, patient_id: patientId, visit_id: visitId, source: 'queue' }) as SelectedPatient;

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => { resolve = res; });
  return { promise, resolve };
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useDentistUrlPatient stale resolution (DENTURL-FE-002, audit 3892 round 3)', () => {
  it('a URL change revokes the pending older URL resolution', async () => {
    const a = deferred<never[]>();
    const argsA = makeArgs({
      locationSearch: '?patientId=7',
      patientIdFromUrl: 7,
      loadDentistryAppointments: vi.fn(() => a.promise),
    });
    const argsB = makeArgs({
      locationSearch: '?patientId=9',
      patientIdFromUrl: 9,
      loadDentistryAppointments: vi.fn(async () => [appointmentFor(9, 42)]),
    });

    const { rerender } = renderHook((props: HookArgs) => useDentistUrlPatient(props), {
      initialProps: argsA,
    });

    // The URL moves from patient 7 to patient 9 while A's queue load is pending.
    rerender(argsB);
    await waitFor(() => expect(argsB.setSelectedPatient).toHaveBeenCalledWith(
      expect.objectContaining({ patient_id: 9 }),
    ));

    // The stale A load resolves afterwards — it must not reset the selection.
    a.resolve([appointmentFor(7, 41)]);
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(argsA.setSelectedPatient).not.toHaveBeenCalled();
    expect(argsA.handleTabChange).not.toHaveBeenCalled();
    expect(argsB.setSelectedPatient).toHaveBeenCalledTimes(1);
  });

  it('a manual selection made while the URL load is pending wins over the stale URL resolution', async () => {
    const a = deferred<never[]>();
    const base = makeArgs({
      patientIdFromUrl: 7,
      loadDentistryAppointments: vi.fn(() => a.promise),
    });

    const { rerender } = renderHook((props: HookArgs) => useDentistUrlPatient(props), {
      initialProps: base,
    });

    // The doctor manually opens patient 9 / visit 42 while the URL load for
    // patient 7 is still in flight (the URL itself did not change).
    rerender({ ...base, selectedPatient: selected(9, 42) });

    a.resolve([appointmentFor(7, 41)]);
    await new Promise((resolve) => setTimeout(resolve, 30));

    expect(base.setSelectedPatient).not.toHaveBeenCalled();
    expect(base.handleTabChange).not.toHaveBeenCalled();
  });

  it('a resolution matching the current selection target may still commit (idempotent)', async () => {
    const a = deferred<never[]>();
    const base = makeArgs({
      patientIdFromUrl: 7,
      loadDentistryAppointments: vi.fn(() => a.promise),
    });

    const { rerender } = renderHook((props: HookArgs) => useDentistUrlPatient(props), {
      initialProps: base,
    });

    // The doctor manually opens the SAME patient the URL targets.
    rerender({ ...base, selectedPatient: selected(7, 41) });

    a.resolve([appointmentFor(7, 41)]);
    await waitFor(() => expect(base.setSelectedPatient).toHaveBeenCalledWith(
      expect.objectContaining({ patient_id: 7 }),
    ));
  });

  it('an unmount revokes the pending URL resolution', async () => {
    const a = deferred<never[]>();
    const base = makeArgs({
      patientIdFromUrl: 7,
      loadDentistryAppointments: vi.fn(() => a.promise),
    });

    const { unmount } = renderHook((props: HookArgs) => useDentistUrlPatient(props), {
      initialProps: base,
    });
    unmount();

    a.resolve([appointmentFor(7, 41)]);
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(base.setSelectedPatient).not.toHaveBeenCalled();
    expect(base.handleTabChange).not.toHaveBeenCalled();
  });

  it('a failed queue load never selects a patient (control)', async () => {
    const args = makeArgs({
      patientIdFromUrl: 7,
      loadDentistryAppointments: vi.fn(async () => {
        throw new Error('network unavailable');
      }),
    });
    renderHook(() => useDentistUrlPatient(args));

    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(args.setSelectedPatient).not.toHaveBeenCalled();
  });

  it('a visit-only deep link keeps the fail-closed contract under the generation guard', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ status: 404, data: null } as never);
    const args = makeArgs({
      locationSearch: '?visitId=77',
      patientIdFromUrl: null as number | null,
      visitIdFromUrl: 77,
    });
    renderHook(() => useDentistUrlPatient(args));

    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(args.setSelectedPatient).not.toHaveBeenCalled();
    expect(args.handleTabChange).not.toHaveBeenCalled();
  });
});
