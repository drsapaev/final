/**
 * PR-UI-15-3 unit contract: dentistContracts pure helpers + the worklist
 * data lifecycle hook boundary (verbatim extraction from
 * DentistPanelUnified — registrar/cashier decomposition precedent).
 */
import { describe, expect, it, vi } from 'vitest';

import type { Appointment } from '../../../types/domain/clinic';
import {
  DENTISTRY_CALLED_STATUSES,
  DENTISTRY_COMPLETED_STATUSES,
  DENTISTRY_WAITING_STATUSES,
  buildPatientsFromAppointments,
  invalidateDentistPanelCaches,
  resolveDoctorQueueEntryId,
} from '../dentistContracts';

const t = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

describe('dentistContracts (PR-UI-15-3)', () => {
  it('dentistry status groups stay verbatim (waiting/called/completed)', () => {
    expect(DENTISTRY_WAITING_STATUSES).toEqual(['waiting', 'confirmed', 'pending']);
    expect(DENTISTRY_CALLED_STATUSES).toEqual(['called', 'in_progress']);
    expect(DENTISTRY_COMPLETED_STATUSES).toEqual(['completed', 'done']);
  });

  it('resolveDoctorQueueEntryId prefers doctor_queue_entry_id then queue_entry_id, else null', () => {
    expect(resolveDoctorQueueEntryId({ doctor_queue_entry_id: 11, queue_entry_id: 22 })).toBe(11);
    expect(resolveDoctorQueueEntryId({ queue_entry_id: 22 })).toBe(22);
    expect(resolveDoctorQueueEntryId({ id: 33 })).toBeNull();
    expect(resolveDoctorQueueEntryId(null)).toBeNull();
    expect(resolveDoctorQueueEntryId(undefined)).toBeNull();
  });

  it('buildPatientsFromAppointments dedupes by patient_id and keeps name fallbacks', () => {
    const appointments = [
      { id: 1, patient_id: 100, patient_fio: 'SYNTHETIC-Patient-One', patient_phone: 'SYNTHETIC-PHONE-1' },
      { id: 2, patient_id: 100, patient_fio: 'SYNTHETIC-Patient-One-Dup' },
      { id: 3, patient_id: 200, patient_name: 'SYNTHETIC-Patient-Two' },
      { id: 4, patient_id: 300, name: 'SYNTHETIC-Patient-Three' },
    ] as unknown as Appointment[];

    const patients = buildPatientsFromAppointments(appointments, t);
    expect(patients).toHaveLength(3);
    expect(patients[0]).toMatchObject({
      id: 100,
      patient_id: 100,
      name: 'SYNTHETIC-Patient-One',
      phone: 'SYNTHETIC-PHONE-1',
      specialty: 'dentistry',
      source: 'appointments',
    });
    // Name fallback order: patient_fio > patient_name > name > t(default).
    expect(patients[1].name).toBe('SYNTHETIC-Patient-Two');
    expect(patients[2].name).toBe('SYNTHETIC-Patient-Three');
  });

  it('buildPatientsFromAppointments falls back to the i18n default label', () => {
    const patients = buildPatientsFromAppointments(
      [{ id: 9, patient_id: 900 } as unknown as Appointment],
      t,
    );
    expect(patients[0].name).toBe('dental.dental_panel_patient_default');
  });

  it('invalidateDentistPanelCaches clears caches without throwing (BS-42)', () => {
    expect(() => invalidateDentistPanelCaches()).not.toThrow();
    // Idempotent on repeat calls.
    invalidateDentistPanelCaches();
    invalidateDentistPanelCaches();
  });
});

describe('useDentistWorklistData (PR-UI-15-3)', () => {
  it('is exported as a named hook taking { tI18n, activeTab }', async () => {
    const mod = await import('../useDentistWorklistData');
    expect(typeof mod.useDentistWorklistData).toBe('function');
    // Source-level boundary: the SSOT queue DTO mapping lives in the hook
    // (DoctorPanels.contract.test.tsx pins the field patterns).
    const fs = await import('node:fs');
    const path = await import('node:path');
    const source = fs.readFileSync(
      path.resolve(process.cwd(), 'src/pages/dentist/useDentistWorklistData.ts'),
      'utf8',
    );
    expect(source).toContain("/registrar/queues/today");
    expect(source).toContain("doctor_queue_entry_id: doctorQueueEntryId");
    expect(source).toContain("can_start_visit: Boolean(entry.can_start_visit) && doctorQueueEntryId !== null");
    expect(source).toContain("isDentistrySpecialty(apt.specialty)");
    // P0-14: single loadPatients call in the Promise.all.
    const stripped = source
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    const promiseAllBlocks = stripped.match(/Promise\.all\(\s*\[[^\]]+\]/g) || [];
    for (const block of promiseAllBlocks) {
      expect((block.match(/loadPatients\(\)/g) || []).length).toBeLessThanOrEqual(1);
    }
  });

  it('module boundary: no BFF-lite endpoints introduced', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const source = fs.readFileSync(
      path.resolve(process.cwd(), 'src/pages/dentist/useDentistWorklistData.ts'),
      'utf8',
    );
    expect(source).not.toContain('/api/v1/ui/');
    expect(source).not.toContain('/ui/doctor');
    expect(source).not.toContain('/ui/registrar');
    expect(source).not.toContain('/registrar/all-appointments');
  });

  it('vi import guard (lint contract): the hook file has no test-only imports', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const source = fs.readFileSync(
      path.resolve(process.cwd(), 'src/pages/dentist/useDentistWorklistData.ts'),
      'utf8',
    );
    expect(source).not.toContain("from 'vitest'");
    void vi;
  });
});
