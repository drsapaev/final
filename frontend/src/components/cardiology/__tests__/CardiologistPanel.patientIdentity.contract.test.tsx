/**
 * CARDPAT-FE-001/002/003, CARDVISIT-FE-001, CARDAPPT-FE-001 (audit 3886
 * round 24) — fail-first, panel source contract.
 *
 * The 2100+ line panel is covered by the repo-precedent source-contract
 * pattern (see CardiologistPanel.phase1.contract.test.tsx and
 * CardiologistPanel.retro3941.contract.test.tsx):
 *
 *  - CARDPAT-FE-001: fetchPatientData must not classify legal patients as
 *    demos by an ID threshold (REG-FE-036 precedent); the backend is the
 *    only authority on patient existence.
 *  - CARDPAT-FE-002: a fully hydrated patient's FIO and exact birth date
 *    must survive panel → EditPatientModal → AppointmentWizardV2 via the
 *    flat edit contract (patient_fio / patient_birth_date /
 *    patient_birth_year); the legacy camelCase shape was never read.
 *  - CARDPAT-FE-003: a late patient fetch may not overwrite a newer edit
 *    modal or reopen a closed one (edit epoch).
 *  - CARDVISIT-FE-001: the latest navigation intent wins the canonical
 *    visit resolution; a delayed lookup for patient A cannot switch the
 *    selected patient/EMR/tab after the doctor moved to B.
 *  - CARDAPPT-FE-001: one queueUpdated burst triggers one debounced,
 *    cancellable refresh; stale appointments snapshots cannot commit.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '../../..');

const readSource = (relPath: string) =>
  fs.readFileSync(path.join(ROOT, relPath), 'utf8').replace(/\r\n/g, '\n');

const panel = readSource('pages/CardiologistPanelUnified.tsx');
const editModal = readSource('components/common/EditPatientModal.tsx');

describe('CARDPAT-FE-001: no ID-threshold demo shortcut in patient hydration', () => {
  it('fetchPatientData has no ">= 1000" demo cutoff (REG-FE-036 precedent)', () => {
    expect(panel).not.toContain('Number(patientId) >= 1000');
    expect(panel).not.toContain('демо-пациентом');
    expect(panel).not.toContain('ID >= 1000');
  });

  it('still fetches the canonical patient endpoint with the requested id (control)', () => {
    // Control assertion — green before AND after the fix.
    expect(panel).toContain('`${API_V1_BASE}/patients/${patientId}`');
  });
});

describe('CARDPAT-FE-002: hydrated FIO and birth date survive panel → modal → wizard', () => {
  it('transformPatientData emits the flat edit contract', () => {
    const fn = panel.slice(
      panel.indexOf('const transformPatientData'),
      panel.indexOf('const createPartialPatientFromRow'),
    );
    expect(fn).toContain('patient_fio:');
    expect(fn).toContain('patient_birth_date:');
    expect(fn).toContain('patient_birth_year:');
    expect(fn).toContain('patient_id:');
    // FIO is composed from the authoritative backend name parts.
    expect(fn).toContain('last_name');
    expect(fn).toContain('first_name');
    expect(fn).toContain('middle_name');
    // The dead camelCase-only shape must not come back as the ONLY shape.
    expect(fn).not.toContain('birthDate: apiPatient.birth_date');
  });

  it('EditPatientModal passes the flat contract at the top level of initialData', () => {
    const block = editModal.slice(
      editModal.indexOf('const initialData'),
      editModal.indexOf('const handleComplete'),
    );
    expect(block).toContain('patient_fio:');
    expect(block).toContain('patient_birth_date:');
    expect(block).toContain('patient_birth_year:');
    // nested mapping retained (wizard fallback chain)
    expect(block).toContain('patient: {');
  });
});

describe('CARDPAT-FE-003: late edit fetch cannot overwrite or reopen the edit modal', () => {
  it('handleEditPatient takes an epoch ticket and rechecks after the await', () => {
    const fn = panel.slice(
      panel.indexOf('const handleEditPatient'),
      panel.indexOf('// Обработчики для таблицы записей'),
    );
    expect(fn).toContain('const epoch = ++editPatientEpochRef.current');
    expect((fn.match(/epoch !== editPatientEpochRef\.current/g) ?? []).length).toBeGreaterThanOrEqual(2);
  });

  it('closing the modal invalidates pending edit resolutions', () => {
    expect(panel).toContain('const closeEditPatientModal');
    expect(panel).toContain('editPatientEpochRef.current += 1');
    expect(panel).toContain('onClose={closeEditPatientModal}');
  });
});

describe('CARDVISIT-FE-001: latest navigation intent wins the visit selection', () => {
  it('every ensureCanonicalVisitId entry path captures and rechecks a navigation epoch', () => {
    expect((panel.match(/\+\+navigationEpochRef\.current/g) ?? []).length).toBe(3);
    expect((panel.match(/epoch !== navigationEpochRef\.current/g) ?? []).length).toBe(3);
  });

  it('row-click branch rechecks before touching selection/EMR/tab', () => {
    const fn = panel.slice(
      panel.indexOf('const handleAppointmentRowClick'),
      panel.indexOf('// C-3 fix'),
    );
    const awaitIdx = fn.indexOf('await ensureCanonicalVisitId(row)');
    const guardIdx = fn.indexOf('epoch !== navigationEpochRef.current');
    expect(awaitIdx).toBeGreaterThan(-1);
    expect(guardIdx).toBeGreaterThan(awaitIdx);
    expect(fn.indexOf('setSelectedPatient(patientData)')).toBeGreaterThan(guardIdx);
  });

  it('view_emr branch rechecks before selecting/loading EMR', () => {
    const fn = panel.slice(
      panel.indexOf("case 'view_emr':"),
      panel.indexOf("case 'call':"),
    );
    const awaitIdx = fn.indexOf('await ensureCanonicalVisitId(row)');
    const guardIdx = fn.indexOf('epoch !== navigationEpochRef.current');
    expect(awaitIdx).toBeGreaterThan(-1);
    expect(guardIdx).toBeGreaterThan(awaitIdx);
    expect(fn.indexOf('setSelectedPatient(patientData)')).toBeGreaterThan(guardIdx);
  });

  it('complete branch rechecks before selecting/loading EMR', () => {
    const fn = panel.slice(
      panel.indexOf("case 'complete':"),
      panel.indexOf("case 'edit':"),
    );
    const awaitIdx = fn.indexOf('await ensureCanonicalVisitId(row)');
    const guardIdx = fn.indexOf('epoch !== navigationEpochRef.current');
    expect(awaitIdx).toBeGreaterThan(-1);
    expect(guardIdx).toBeGreaterThan(awaitIdx);
    expect(fn.indexOf('setSelectedPatient(patient)')).toBeGreaterThan(guardIdx);
  });
});

describe('CARDAPPT-FE-001: one coalesced, cancellable queueUpdated refresh', () => {
  it('the appointments loader is sequence-guarded', () => {
    const fn = panel.slice(
      panel.indexOf('const loadMacOSCardiologyAppointments'),
      panel.indexOf('// Загружаем записи при переключении на вкладку'),
    );
    expect(fn).toContain('const epoch = ++appointmentsEpochRef.current');
    expect(fn).toContain('epoch !== appointmentsEpochRef.current');
    expect(fn).toContain('if (epoch === appointmentsEpochRef.current) setAppointmentsError(true)');
    expect(fn).toContain('if (epoch === appointmentsEpochRef.current) setAppointmentsLoading(false)');
  });

  it('queueUpdated is debounced once per burst, not immediate + delayed', () => {
    const handler = panel.slice(
      panel.indexOf('Слушаем глобальные события обновления очереди'),
      panel.indexOf("window.addEventListener('queueUpdated'"),
    );
    expect(handler).toContain('scheduleAppointmentsRefresh()');
    expect(handler).not.toContain('loadMacOSCardiologyAppointments();');
  });

  it('the debounce replaces a pending timer and the effect cleanup cancels it', () => {
    const schedStart = panel.indexOf('const scheduleAppointmentsRefresh');
    expect(schedStart).toBeGreaterThan(-1);
    const sched = panel.slice(schedStart, panel.indexOf('useEffect', schedStart));
    expect(sched).toContain('window.clearTimeout(appointmentsRefreshTimerRef.current)');

    const effectStart = panel.indexOf('Слушаем глобальные события обновления очереди');
    const cleanup = panel.slice(
      panel.indexOf('return () => {', effectStart),
      panel.indexOf('}, [activeTab,'),
    );
    expect(cleanup).toContain('window.clearTimeout(appointmentsRefreshTimerRef.current)');
  });
});
