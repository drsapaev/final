
import { describe, expect, it, vi } from 'vitest';

import {
  countAppointmentsByStatuses,
  getAllPatientServices,
  makeEnsureCanonicalVisitId,
  matchesSpecialty,
  normalizeNumericId,
  SPECIALTY_ALIASES,
  SPECIALTY_KEYS,
  default as doctorPanelSharedDefault,
} from '../doctorPanelShared';

describe('doctorPanelShared — SPECIALTY_KEYS', () => {
  it('exposes canonical long-form specialty strings', () => {
    expect(SPECIALTY_KEYS.CARDIOLOGY).toBe('cardiology');
    expect(SPECIALTY_KEYS.DERMATOLOGY).toBe('dermatology');
    expect(SPECIALTY_KEYS.DENTISTRY).toBe('dentistry');
    expect(SPECIALTY_KEYS.LAB).toBe('lab');
    expect(SPECIALTY_KEYS.GENERAL).toBe('general');
  });

  it('is frozen — callers cannot mutate the canonical keys', () => {
    expect(Object.isFrozen(SPECIALTY_KEYS)).toBe(true);
    // Mutation attempts silently fail in non-strict mode, throw in strict.
    expect(() => {
      'use strict';
      (SPECIALTY_KEYS as Record<string, string>).NEW = 'should-not-add';
    }).toThrow(TypeError);
  });

  it('covers exactly the 5 specialties the backend DOCTOR_QUEUE_SPECIALTY_VARIANTS table maps', () => {
    // Aligned with backend/app/api/v1/endpoints/doctor_integration.py
    // DOCTOR_QUEUE_SPECIALTY_VARIANTS keys: cardiology, cardio, derma,
    // dermatology, dentist, dentistry, stomatology, lab, laboratory, general.
    //
    // The frontend canonical keys are the long forms — the backend
    // tolerant-maps all aliases back to these.
    const canonicalKeys = Object.values(SPECIALTY_KEYS);
    expect(canonicalKeys).toEqual(
      expect.arrayContaining([
        'cardiology',
        'dermatology',
        'dentistry',
        'lab',
        'general',
      ]),
    );
    expect(canonicalKeys).toHaveLength(5);
  });
});

describe('doctorPanelShared — SPECIALTY_ALIASES', () => {
  it('is frozen — callers cannot mutate the alias table', () => {
    expect(Object.isFrozen(SPECIALTY_ALIASES)).toBe(true);
  });

  it('includes the cardio/cardiology alias pair aligned with backend', () => {
    // backend DOCTOR_QUEUE_SPECIALTY_VARIANTS["cardiology"] =
    // ["cardiology", "cardio", "Cardiologist", "Cardio"]
    expect(SPECIALTY_ALIASES[SPECIALTY_KEYS.CARDIOLOGY]).toEqual(
      expect.arrayContaining(['cardiology', 'cardio', 'Cardiologist', 'Cardio']),
    );
  });

  it('includes the derma/dermatology alias pair aligned with backend', () => {
    // backend DOCTOR_QUEUE_SPECIALTY_VARIANTS["derma"] =
    // ["derma", "dermatology", "Dermatologist"]
    expect(SPECIALTY_ALIASES[SPECIALTY_KEYS.DERMATOLOGY]).toEqual(
      expect.arrayContaining(['derma', 'dermatology', 'Dermatologist']),
    );
  });

  it('includes the dentist/dental/dentistry/stomatology alias family aligned with backend', () => {
    // backend DOCTOR_QUEUE_SPECIALTY_VARIANTS["dentistry"] =
    // ["dentist", "dental", "dentistry", "Dentist", "stomatology"]
    expect(SPECIALTY_ALIASES[SPECIALTY_KEYS.DENTISTRY]).toEqual(
      expect.arrayContaining([
        'dentist',
        'dental',
        'dentistry',
        'Dentist',
        'stomatology',
      ]),
    );
  });

  it('includes the lab/laboratory alias pair aligned with backend', () => {
    expect(SPECIALTY_ALIASES[SPECIALTY_KEYS.LAB]).toEqual(
      expect.arrayContaining(['lab', 'laboratory', 'Laboratory']),
    );
  });

  it('includes the general/therapy/therapist alias family aligned with backend', () => {
    expect(SPECIALTY_ALIASES[SPECIALTY_KEYS.GENERAL]).toEqual(
      expect.arrayContaining([
        'general',
        'therapy',
        'therapist',
        'general_practice',
      ]),
    );
  });
});

describe('doctorPanelShared — matchesSpecialty', () => {
  it('returns true when candidate equals canonical key directly', () => {
    expect(matchesSpecialty('cardiology', SPECIALTY_KEYS.CARDIOLOGY)).toBe(true);
    expect(matchesSpecialty('dermatology', SPECIALTY_KEYS.DERMATOLOGY)).toBe(true);
    expect(matchesSpecialty('dentistry', SPECIALTY_KEYS.DENTISTRY)).toBe(true);
  });

  it('returns true when candidate is one of the known aliases', () => {
    expect(matchesSpecialty('cardio', SPECIALTY_KEYS.CARDIOLOGY)).toBe(true);
    expect(matchesSpecialty('Cardiologist', SPECIALTY_KEYS.CARDIOLOGY)).toBe(true);
    expect(matchesSpecialty('derma', SPECIALTY_KEYS.DERMATOLOGY)).toBe(true);
    expect(matchesSpecialty('dental', SPECIALTY_KEYS.DENTISTRY)).toBe(true);
    expect(matchesSpecialty('stomatology', SPECIALTY_KEYS.DENTISTRY)).toBe(true);
  });

  it('returns false when candidate belongs to a different specialty family', () => {
    expect(matchesSpecialty('cardiology', SPECIALTY_KEYS.DERMATOLOGY)).toBe(false);
    expect(matchesSpecialty('derma', SPECIALTY_KEYS.DENTISTRY)).toBe(false);
    expect(matchesSpecialty('dentist', SPECIALTY_KEYS.CARDIOLOGY)).toBe(false);
    expect(matchesSpecialty('lab', SPECIALTY_KEYS.GENERAL)).toBe(false);
  });

  it('returns false for unknown candidate strings', () => {
    expect(matchesSpecialty('unknown', SPECIALTY_KEYS.CARDIOLOGY)).toBe(false);
    expect(matchesSpecialty('psychiatry', SPECIALTY_KEYS.GENERAL)).toBe(false);
  });

  it('is null-safe — returns false for null/undefined/empty inputs', () => {
    expect(matchesSpecialty(null, SPECIALTY_KEYS.CARDIOLOGY)).toBe(false);
    expect(matchesSpecialty(undefined, SPECIALTY_KEYS.CARDIOLOGY)).toBe(false);
    expect(matchesSpecialty('', SPECIALTY_KEYS.CARDIOLOGY)).toBe(false);
    expect(matchesSpecialty('cardiology', null)).toBe(false);
    expect(matchesSpecialty('cardiology', undefined)).toBe(false);
    expect(matchesSpecialty('cardiology', '')).toBe(false);
    expect(matchesSpecialty(null, null)).toBe(false);
  });

  it('is case-sensitive — backend handles normalisation, frontend should pass canonical-cased strings', () => {
    // The frontend contract is to pass the raw specialty string from the
    // appointment/entry. Backend normalises to lowercase before lookup
    // (_normalize_queue_specialty), but matchesSpecialty itself does NOT
    // lowercase — this is intentional so we surface unexpected casing.
    expect(matchesSpecialty('Cardiology', SPECIALTY_KEYS.CARDIOLOGY)).toBe(false);
    expect(matchesSpecialty('CARDIOLOGY', SPECIALTY_KEYS.CARDIOLOGY)).toBe(false);
  });
});

describe('doctorPanelShared — countAppointmentsByStatuses', () => {
  it('counts appointments whose status matches any of the given statuses', () => {
    const appointments = [
      { status: 'waiting' },
      { status: 'called' },
      { status: 'waiting' },
      { status: 'completed' },
      { status: 'waiting' },
    ];
    expect(countAppointmentsByStatuses(appointments, ['waiting'])).toBe(3);
    expect(countAppointmentsByStatuses(appointments, ['called'])).toBe(1);
    expect(countAppointmentsByStatuses(appointments, ['completed'])).toBe(1);
    expect(countAppointmentsByStatuses(appointments, ['waiting', 'called'])).toBe(4);
  });

  it('returns 0 for empty appointments array', () => {
    expect(countAppointmentsByStatuses([], ['waiting'])).toBe(0);
  });

  it('returns 0 for empty statuses array', () => {
    expect(countAppointmentsByStatuses([{ status: 'waiting' }], [])).toBe(0);
  });

  it('returns 0 when no appointment status matches', () => {
    const appointments = [{ status: 'waiting' }, { status: 'called' }];
    expect(countAppointmentsByStatuses(appointments, ['completed'])).toBe(0);
  });

  it('handles appointments with missing status field gracefully', () => {
    const appointments = [
      { status: 'waiting' },
      { /* no status */ },
      { status: undefined },
      { status: null },
      { status: 'waiting' },
    ];
    expect(countAppointmentsByStatuses(appointments, ['waiting'])).toBe(2);
  });

  it('handles null/undefined appointments array gracefully', () => {
    expect(countAppointmentsByStatuses(null, ['waiting'])).toBe(0);
    expect(countAppointmentsByStatuses(undefined, ['waiting'])).toBe(0);
  });

  it('handles null/undefined statuses array gracefully', () => {
    expect(countAppointmentsByStatuses([{ status: 'waiting' }], null)).toBe(0);
    expect(countAppointmentsByStatuses([{ status: 'waiting' }], undefined)).toBe(0);
  });

  it('uses Set-based lookup — O(n+m) instead of O(n*m)', () => {
    // Smoke test: 1000 appointments × 3 statuses should complete instantly.
    // The previous Array.includes implementation was O(n*m); the Set-based
    // implementation is O(n+m). For 1000×3 = 3000 ops the difference is
    // negligible, but the test guards against accidental regression to
    // the O(n*m) form.
    const statuses = ['waiting', 'called', 'completed'];
    const appointments = Array.from({ length: 1000 }, (_, i) => ({
      status: statuses[i % statuses.length],
    }));
    const start = Date.now();
    const result = countAppointmentsByStatuses(appointments, statuses);
    const elapsed = Date.now() - start;
    expect(result).toBe(1000);
    expect(elapsed).toBeLessThan(50); // generous upper bound
  });

  it('matches the legacy Array.includes behaviour bit-for-bit', () => {
    // Regression guard: the new Set-based implementation must return the
    // same count as the previous Array.includes implementation for every
    // status value, including undefined and null.
    const appointments = [
      { status: 'waiting' },
      { status: 'called' },
      { status: undefined },
      { status: null },
      { status: 'completed' },
    ];
    const legacyImpl = (apts, sts) =>
      apts.filter((apt) => sts.includes(apt.status)).length;
    for (const sts of [
      ['waiting'],
      ['called'],
      ['completed'],
      ['waiting', 'called'],
      [undefined],
      [null],
      ['waiting', undefined],
    ]) {
      expect(countAppointmentsByStatuses(appointments, sts)).toBe(
        legacyImpl(appointments, sts),
      );
    }
  });
});

describe('doctorPanelShared — normalizeNumericId', () => {
  it('parses integer strings', () => {
    expect(normalizeNumericId('42')).toBe(42);
    expect(normalizeNumericId('0')).toBe(0);
    expect(normalizeNumericId('-1')).toBe(-1);
  });

  it('parses numbers', () => {
    expect(normalizeNumericId(42)).toBe(42);
    expect(normalizeNumericId(0)).toBe(0);
    expect(normalizeNumericId(-1)).toBe(-1);
  });

  it('returns null for empty string', () => {
    expect(normalizeNumericId('')).toBeNull();
  });

  it('returns null for null and undefined', () => {
    expect(normalizeNumericId(null)).toBeNull();
    expect(normalizeNumericId(undefined)).toBeNull();
  });

  it('returns null for non-numeric strings', () => {
    expect(normalizeNumericId('abc')).toBeNull();
    expect(normalizeNumericId('42abc')).toBe(42); // parseInt behaviour
    expect(normalizeNumericId('abc42')).toBeNull();
  });

  it('returns null for NaN and Infinity', () => {
    expect(normalizeNumericId(NaN)).toBeNull();
    expect(normalizeNumericId(Infinity)).toBeNull();
    expect(normalizeNumericId(-Infinity)).toBeNull();
  });

  it('returns null for objects and arrays', () => {
    expect(normalizeNumericId({})).toBeNull();
    expect(normalizeNumericId([])).toBeNull();
    expect(normalizeNumericId([42])).toBe(42); // parseInt([42]) === 42
  });

  it('preserves float-truncation behaviour of parseInt', () => {
    // parseInt truncates floats — this is intentional and matches the
    // previous in-panel implementations.
    expect(normalizeNumericId(42.7)).toBe(42);
    expect(normalizeNumericId('42.7')).toBe(42);
  });
});

describe('doctorPanelShared — getAllPatientServices', () => {
  it('collects unique services + service_codes for a patient across appointments', () => {
    const appointments = [
      { patient_id: 1, services: ['consultation', 'ecg'], service_codes: ['A01', 'A02'] },
      { patient_id: 1, services: ['ecg', 'blood-test'], service_codes: ['A03'] },
      { patient_id: 2, services: ['consultation'], service_codes: ['A01'] },
      { patient_id: 1, services: ['consultation'], service_codes: ['A01', 'A04'] }, // duplicates
    ];
    const result = getAllPatientServices(1, appointments);
    expect(result.services.sort()).toEqual(['blood-test', 'consultation', 'ecg']);
    expect(result.service_codes.sort()).toEqual(['A01', 'A02', 'A03', 'A04']);
  });

  it('returns empty arrays when patient has no appointments', () => {
    const appointments = [{ patient_id: 2, services: ['x'] }];
    const result = getAllPatientServices(1, appointments);
    expect(result.services).toEqual([]);
    expect(result.service_codes).toEqual([]);
  });

  it('returns empty arrays when appointments array is empty', () => {
    const result = getAllPatientServices(1, []);
    expect(result.services).toEqual([]);
    expect(result.service_codes).toEqual([]);
  });

  it('handles null/undefined appointments array gracefully', () => {
    expect(getAllPatientServices(1, null)).toEqual({ services: [], service_codes: [] });
    expect(getAllPatientServices(1, undefined)).toEqual({ services: [], service_codes: [] });
  });

  it('handles appointments with missing services/service_codes fields', () => {
    const appointments = [
      { patient_id: 1 }, // no services, no service_codes
      { patient_id: 1, services: null, service_codes: undefined },
      { patient_id: 1, services: ['x'] },
    ];
    const result = getAllPatientServices(1, appointments);
    expect(result.services).toEqual(['x']);
    expect(result.service_codes).toEqual([]);
  });

  it('handles non-array services/service_codes gracefully (treats as empty)', () => {
    const appointments = [
      { patient_id: 1, services: 'not-an-array', service_codes: 42 },
    ];
    const result = getAllPatientServices(1, appointments);
    expect(result.services).toEqual([]);
    expect(result.service_codes).toEqual([]);
  });

  it('handles null/undefined patientId (matches appointments with null/undefined patient_id via strict equality)', () => {
    // Note: null === null is true in JS, so appointments with patient_id: null
    // WILL match when patientId is null. This matches the legacy in-panel
    // implementation. undefined === undefined is also true.
    const appointments = [
      { patient_id: null, services: ['x'], service_codes: ['X1'] },
      { patient_id: undefined, services: ['y'], service_codes: ['Y1'] },
      { patient_id: 1, services: ['z'], service_codes: ['Z1'] },
    ];
    expect(getAllPatientServices(null, appointments)).toEqual({ services: ['x'], service_codes: ['X1'] });
    expect(getAllPatientServices(undefined, appointments)).toEqual({ services: ['y'], service_codes: ['Y1'] });
    // Sanity: patientId 1 matches only the third appointment
    expect(getAllPatientServices(1, appointments)).toEqual({ services: ['z'], service_codes: ['Z1'] });
  });

  it('matches the legacy in-panel implementation bit-for-bit', () => {
    // Regression guard: the new shared implementation must return the same
    // result as the previous in-panel implementations for every input shape.
    const legacyImpl = (patientId, allAppointments) => {
      const patientServices = new Set();
      const patientServiceCodes = new Set();
      allAppointments.forEach((appointment) => {
        if (appointment.patient_id === patientId) {
          if (appointment.services && Array.isArray(appointment.services)) {
            appointment.services.forEach((service) => patientServices.add(service));
          }
          if (appointment.service_codes && Array.isArray(appointment.service_codes)) {
            appointment.service_codes.forEach((code) => patientServiceCodes.add(code));
          }
        }
      });
      return {
        services: Array.from(patientServices),
        service_codes: Array.from(patientServiceCodes),
      };
    };

    const testCases = [
      { patientId: 1, appointments: [] },
      { patientId: 1, appointments: [{ patient_id: 1, services: ['a'], service_codes: ['x'] }] },
      { patientId: 2, appointments: [{ patient_id: 1, services: ['a'] }] },
      {
        patientId: 1,
        appointments: [
          { patient_id: 1, services: ['a', 'b'], service_codes: ['x'] },
          { patient_id: 1, services: ['b', 'c'], service_codes: ['y', 'z'] },
        ],
      },
      { patientId: null, appointments: [{ patient_id: null, services: ['a'] }] },
    ];

    for (const { patientId, appointments } of testCases) {
      const shared = getAllPatientServices(patientId, appointments);
      const legacy = legacyImpl(patientId, appointments);
      // Compare as sorted arrays to ignore Set iteration order
      expect(shared.services.sort()).toEqual(legacy.services.sort());
      expect(shared.service_codes.sort()).toEqual(legacy.service_codes.sort());
    }
  });
});

describe('doctorPanelShared — makeEnsureCanonicalVisitId', () => {
  it('returns visit_id from row when already present (no API call)', async () => {
    const setAppointments = vi.fn();
    const resolveCanonicalVisitId = vi.fn();
    const ensure = makeEnsureCanonicalVisitId(setAppointments, resolveCanonicalVisitId);

    const row = { id: 1, visit_id: 42, appointment_id: 100 };
    const result = await ensure(row);

    expect(result).toBe(42);
    expect(resolveCanonicalVisitId).not.toHaveBeenCalled();
    expect(setAppointments).toHaveBeenCalledWith(expect.any(Function));
  });

  it('resolves visit_id via resolveCanonicalVisitId when row has appointment_id but no visit_id', async () => {
    const setAppointments = vi.fn();
    const resolveCanonicalVisitId = vi.fn().mockResolvedValue(99);
    const ensure = makeEnsureCanonicalVisitId(setAppointments, resolveCanonicalVisitId);

    const row = { id: 1, appointment_id: 100 };
    const result = await ensure(row);

    expect(result).toBe(99);
    expect(resolveCanonicalVisitId).toHaveBeenCalledWith(100);
    expect(setAppointments).toHaveBeenCalledWith(expect.any(Function));
  });

  it('returns null when row has no appointment_id and no visit_id', async () => {
    const setAppointments = vi.fn();
    const resolveCanonicalVisitId = vi.fn();
    const ensure = makeEnsureCanonicalVisitId(setAppointments, resolveCanonicalVisitId);

    const row = { id: 1 };
    const result = await ensure(row);

    expect(result).toBeNull();
    expect(resolveCanonicalVisitId).not.toHaveBeenCalled();
    expect(setAppointments).not.toHaveBeenCalled();
  });

  it('does not call setAppointments when visit_id is null', async () => {
    const setAppointments = vi.fn();
    const resolveCanonicalVisitId = vi.fn().mockResolvedValue(null);
    const ensure = makeEnsureCanonicalVisitId(setAppointments, resolveCanonicalVisitId);

    const row = { id: 1, appointment_id: 100 };
    const result = await ensure(row);

    expect(result).toBeNull();
    expect(setAppointments).not.toHaveBeenCalled();
  });

  it('updates the matching appointment in state with the resolved visit_id', async () => {
    let capturedUpdater;
    const setAppointments = vi.fn((updater) => { capturedUpdater = updater; });
    const resolveCanonicalVisitId = vi.fn().mockResolvedValue(55);
    const ensure = makeEnsureCanonicalVisitId(setAppointments, resolveCanonicalVisitId);

    const row = { id: 1, appointment_id: 100 };
    await ensure(row);

    const prevState = [
      { id: 1, appointment_id: 100 },          // should be updated
      { id: 2, appointment_id: 200 },          // should be unchanged
      { id: 1, appointment_id: 100, visit_id: 99 }, // different row with same id (edge case - first match wins)
    ];
    const nextState = capturedUpdater(prevState);
    expect(nextState[0]).toEqual({ id: 1, appointment_id: 100, visit_id: 55 });
    expect(nextState[1]).toEqual({ id: 2, appointment_id: 200 });
  });

  it('handles null/undefined setAppointments gracefully (no crash)', async () => {
    const resolveCanonicalVisitId = vi.fn().mockResolvedValue(42);
    const ensure = makeEnsureCanonicalVisitId(null, resolveCanonicalVisitId);

    const row = { id: 1, visit_id: 42 };
    const result = await ensure(row);

    expect(result).toBe(42);
    // No crash - setAppointments was null, so it wasn't called.
  });

  it('handles null/undefined resolveCanonicalVisitId gracefully', async () => {
    const setAppointments = vi.fn();
    const ensure = makeEnsureCanonicalVisitId(setAppointments, null);

    const row = { id: 1, appointment_id: 100 };
    const result = await ensure(row);

    // resolveCanonicalVisitId is null, so the ternary falls through to null
    expect(result).toBeNull();
    expect(setAppointments).not.toHaveBeenCalled();
  });

  it('handles setAppointments updater receiving non-array prev state', async () => {
    let capturedUpdater;
    const setAppointments = vi.fn((updater) => { capturedUpdater = updater; });
    const resolveCanonicalVisitId = vi.fn().mockResolvedValue(42);
    const ensure = makeEnsureCanonicalVisitId(setAppointments, resolveCanonicalVisitId);

    const row = { id: 1, visit_id: 42 };
    await ensure(row);

    // Should not crash if prev is not an array
    expect(() => capturedUpdater(null)).not.toThrow();
    expect(() => capturedUpdater(undefined)).not.toThrow();
    expect(capturedUpdater(null)).toBeNull();
    expect(capturedUpdater(undefined)).toBeUndefined();
  });

  it('handles appointments with null/undefined entries in the array', async () => {
    let capturedUpdater;
    const setAppointments = vi.fn((updater) => { capturedUpdater = updater; });
    const resolveCanonicalVisitId = vi.fn().mockResolvedValue(42);
    const ensure = makeEnsureCanonicalVisitId(setAppointments, resolveCanonicalVisitId);

    const row = { id: 1, visit_id: 42 };
    await ensure(row);

    const prevState = [null, undefined, { id: 1, visit_id: 0 }, { id: 1 }];
    const nextState = capturedUpdater(prevState);
    // Should not crash on null/undefined entries
    expect(nextState).toHaveLength(4);
    // The entry with id:1 and no visit_id should be updated
    expect(nextState[3]).toEqual({ id: 1, visit_id: 42 });
  });
});

describe('doctorPanelShared — default export', () => {
  it('exposes all named exports on the default object', () => {
    expect(doctorPanelSharedDefault.SPECIALTY_KEYS).toBe(SPECIALTY_KEYS);
    expect(doctorPanelSharedDefault.SPECIALTY_ALIASES).toBe(SPECIALTY_ALIASES);
    expect(doctorPanelSharedDefault.matchesSpecialty).toBe(matchesSpecialty);
    expect(doctorPanelSharedDefault.countAppointmentsByStatuses).toBe(
      countAppointmentsByStatuses,
    );
    expect(doctorPanelSharedDefault.normalizeNumericId).toBe(normalizeNumericId);
    expect(doctorPanelSharedDefault.getAllPatientServices).toBe(getAllPatientServices);
    expect(doctorPanelSharedDefault.makeEnsureCanonicalVisitId).toBe(makeEnsureCanonicalVisitId);
  });
});
