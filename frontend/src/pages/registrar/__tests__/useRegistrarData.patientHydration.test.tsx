/**
 * REG-FE-036 (#3819) — registrar patient hydration must not classify legal
 * real patients as demos by an ID threshold.
 *
 * Fail-first contract (issue #3819, registrar audit ledger PR #3803):
 * `useRegistrarData.fetchPatientData` returned null for EVERY patient
 * ID >= 1000 without a backend call («демо-пациент» shortcut), while the
 * backend `Patient.id` is a regular unbounded Integer PK. Real patients
 * with IDs >= 1000 whose appointment rows lack the backend display/gender
 * contract were silently never enriched: no FIO, no gender, no phone in
 * the registrar worklist.
 *
 * Every behavioral test below must FAIL on the unpatched source (RED) and
 * pass after the minimal fix (GREEN): remove the threshold — the demo/real
 * distinction belongs to explicit backend data, not an ID cutoff. Unknown
 * patients (404) and network failures are backend answers/transport states,
 * never a demo classification, and must not overwrite another patient's
 * fields.
 */
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { useRegistrarData } from '../useRegistrarData';
import { getPatient } from '../../../api/patients';
import type { Patient } from '../../../types/domain/clinic';
import type { PatientId } from '../../../types/domain/branded';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const hookSource = fs.readFileSync(
  path.join(__dirname, '../useRegistrarData.ts'),
  'utf8',
);

vi.mock('../../../api/patients', () => ({ getPatient: vi.fn() }));
vi.mock('../../../api/client', () => ({ api: { get: vi.fn() } }));
vi.mock('../../../services/notify', () => ({ default: { error: vi.fn(), success: vi.fn() } }));
vi.mock('../../../utils/logger', () => ({ default: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), log: vi.fn() } }));
vi.mock('../../../utils/tokenManager', () => ({ default: { getAccessToken: () => 'test-token' } }));

const syntheticPatient = (id: number): Patient => ({
  id: String(id) as PatientId,
  last_name: `SYNTHETIC Lastname ${id}`,
  first_name: 'Firstname',
  middle_name: 'Middlename',
  phone: '+998901234567',
  birth_date: '1990-05-01',
  sex: 'М',
  address: 'SYNTHETIC address',
});

describe('useRegistrarData — REG-FE-036 patient hydration for IDs >= 1000', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches and hydrates legal real patients with IDs 1001 and 5000 (no ID-threshold demo shortcut)', async () => {
    vi.mocked(getPatient).mockImplementation(async (patientId: string | number) =>
      syntheticPatient(Number(patientId)));

    const { result } = renderHook(() => useRegistrarData());

    let enriched: Record<string, unknown>[] = [];
    await act(async () => {
      enriched = await result.current.enrichAppointmentsWithPatientData([
        { patient_id: 1001 },
        { patient_id: 5000 },
      ]);
    });

    // The backend was actually asked for both patients...
    expect(getPatient).toHaveBeenCalledTimes(2);
    expect(getPatient).toHaveBeenCalledWith(1001);
    expect(getPatient).toHaveBeenCalledWith(5000);

    // ...and the display contract was hydrated from the backend response.
    expect(enriched[0].patient_fio).toBe('SYNTHETIC Lastname 1001 Firstname Middlename');
    expect(enriched[0].patient_phone).toBe('+998901234567');
    expect(enriched[0].patient_birth_year).toBe(1990);
    expect(enriched[0].patient_gender).toBe('М');
    expect(enriched[0].address).toBe('SYNTHETIC address');
    expect(enriched[1].patient_fio).toBe('SYNTHETIC Lastname 5000 Firstname Middlename');
  });

  it('does not call the backend when the appointment already carries the full display+gender contract', async () => {
    const { result } = renderHook(() => useRegistrarData());

    const backendComplete = {
      patient_id: 1002,
      patient_fio: 'SYNTHETIC Complete FIO',
      patient_phone: '+998909876543',
      patient_birth_year: 1985,
      address: 'SYNTHETIC complete address',
      patient_gender: 'Ж',
      __patient_gender_contract_present: true,
    };

    let enriched: Record<string, unknown>[] = [];
    await act(async () => {
      enriched = await result.current.enrichAppointmentsWithPatientData([backendComplete]);
    });

    expect(getPatient).not.toHaveBeenCalled();
    expect(enriched[0].patient_fio).toBe('SYNTHETIC Complete FIO');
    expect(enriched[0].patient_gender).toBe('Ж');
  });

  it('attempts the backend fetch for a 404 patient instead of silently treating it as a demo', async () => {
    const err404 = Object.assign(new Error('Request failed with status code 404'), {
      response: { status: 404 },
    });
    vi.mocked(getPatient).mockRejectedValue(err404);

    const { result } = renderHook(() => useRegistrarData());

    let enriched: Record<string, unknown>[] = [];
    await act(async () => {
      enriched = await result.current.enrichAppointmentsWithPatientData([
        { patient_id: 1003, patient_fio: 'Original SYNTHETIC FIO' },
      ]);
    });

    // A missing patient is a backend answer, not a demo classification:
    // the fetch must have been attempted.
    expect(getPatient).toHaveBeenCalledTimes(1);
    expect(getPatient).toHaveBeenCalledWith(1003);
    // And the row keeps its own fields — nothing was invented or overwritten.
    expect(enriched[0].patient_fio).toBe('Original SYNTHETIC FIO');
  });

  it('attempts the backend fetch on a network failure and keeps the original row fields', async () => {
    vi.mocked(getPatient).mockRejectedValue(new Error('Network Error'));

    const { result } = renderHook(() => useRegistrarData());

    let enriched: Record<string, unknown>[] = [];
    await act(async () => {
      enriched = await result.current.enrichAppointmentsWithPatientData([
        { patient_id: 1004, patient_fio: 'Original SYNTHETIC FIO 2' },
      ]);
    });

    // A network failure is a transport state, not a demo classification:
    // the fetch must have been attempted.
    expect(getPatient).toHaveBeenCalledTimes(1);
    expect(getPatient).toHaveBeenCalledWith(1004);
    expect(enriched[0].patient_fio).toBe('Original SYNTHETIC FIO 2');
  });

  it('keeps the hydration source free of the ID-threshold demo shortcut (source contract)', () => {
    // The threshold (both the code form and the doc-comment form) must stay
    // removed so a legal real-patient ID is never classified as a demo.
    expect(hookSource).not.toContain('>= 1000');
    expect(hookSource).not.toContain('ID >= 1000');
  });
});
