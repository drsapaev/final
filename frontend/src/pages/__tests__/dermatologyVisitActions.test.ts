import { describe, expect, it, vi } from 'vitest';
import {
  canCompleteDermatologyVisit,
  isSameDermatologyVisit,
  postDermatologyPrescription,
  toPrescriptionCreatePayload,
  toPrescriptionSystemRecord,
} from '../dermatologyVisitActions';

describe('dermatology visit actions', () => {
  it('builds the exact snake_case PrescriptionCreate payload', () => {
    expect(toPrescriptionCreatePayload({
      medications: [{
        id: 17,
        name: 'Topical medicine',
        dosage: '1%',
        frequency: 'twice daily',
        duration: '7 days',
        instructions: 'Apply to the affected area',
        quantity: 1,
      }],
      instructions: 'Follow up in one week',
      doctorNotes: 'Keep the area dry',
      isDraft: false,
      savedAt: 'not part of the API contract',
      appointmentId: 999,
    }, { appointmentId: '42', visitId: '73', emrId: 81 })).toEqual({
      appointment_id: 42,
      visit_id: 73,
      emr_id: 81,
      medications: [{
        name: 'Topical medicine',
        dosage: '1%',
        frequency: 'twice daily',
        duration: '7 days',
        instructions: 'Apply to the affected area',
        quantity: 1,
      }],
      instructions: 'Follow up in one week',
      doctor_notes: 'Keep the area dry',
      is_draft: false,
    });
  });

  it('rejects a prescription without a valid appointment ID', () => {
    expect(() => toPrescriptionCreatePayload({}, {
      appointmentId: null,
      visitId: 73,
      emrId: null,
    })).toThrow('Prescription requires an appointment ID');
  });

  it('requires the queue flag and, when present, appointment status to permit completion', () => {
    expect(canCompleteDermatologyVisit(true, null, false)).toBe(true);
    expect(canCompleteDermatologyVisit(false, null, true)).toBe(false);
    expect(canCompleteDermatologyVisit(true, 42, true)).toBe(true);
    expect(canCompleteDermatologyVisit(true, 42, false)).toBe(false);
  });

  it('maps the server prescription record to the form shape and keeps it saved', () => {
    expect(toPrescriptionSystemRecord({
      id: 7,
      is_draft: false,
      doctor_notes: 'Take after meals',
      created_at: '2026-09-25T10:00:00Z',
      medications: [{ name: 'Cream', dosage: '1%', quantity: 2 }],
    })).toMatchObject({
      id: 7,
      isDraft: false,
      doctorNotes: 'Take after meals',
      createdAt: '2026-09-25T10:00:00Z',
      medications: [{ id: 1, name: 'Cream', dosage: '1%', quantity: 2 }],
    });
  });

  it('returns a server-confirmed saved prescription after a successful POST', async () => {
    const payload = toPrescriptionCreatePayload({}, {
      appointmentId: 5,
      visitId: 8,
      emrId: 13,
    });
    const post = vi.fn(async () => ({ status: 201, data: { id: 21, is_draft: false } }));

    await expect(postDermatologyPrescription(payload, post)).resolves.toMatchObject({
      id: 21,
      isDraft: false,
    });
    expect(post).toHaveBeenCalledWith(5, payload);
  });

  it.each([
    ['422', async () => ({ status: 422, data: { detail: 'validation failed' } })],
    ['network', async () => { throw new Error('network details'); }],
  ])('does not report a saved prescription after a %s failure', async (_caseName, post) => {
    const payload = toPrescriptionCreatePayload({}, {
      appointmentId: 5,
      visitId: 8,
      emrId: null,
    });

    await expect(postDermatologyPrescription(payload, post)).rejects.toMatchObject({
      message: 'Prescription save failed',
      ...(_caseName === '422' ? { response: { status: 422 } } : {}),
    });
  });

  it('rejects status results for a previously selected patient or visit', () => {
    const selected = {
      appointmentId: 42,
      patientId: 7,
      visitId: 73,
      queueEntryId: 12,
    };

    expect(isSameDermatologyVisit(selected, { ...selected })).toBe(true);
    expect(isSameDermatologyVisit(selected, { ...selected, patientId: 8 })).toBe(false);
    expect(isSameDermatologyVisit(selected, { ...selected, visitId: 74 })).toBe(false);
    expect(isSameDermatologyVisit(selected, { ...selected, queueEntryId: 13 })).toBe(false);
  });
});
