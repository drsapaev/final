import { describe, expect, it } from 'vitest';
import { adaptQueueEntry } from '../../../pages/registrar/registrarQueueAdapter';

import {
  addServiceToWizardCart,
  buildCartQuoteRequest,
  buildEditDeltaTargetItems,
  buildEditOriginalServiceIdentity,
  repeatPreviewCandidateKey,
  resolveQrLockedDoctorId,
} from '../wizardUtils';

const service = {
  id: 10,
  name: 'Консультация',
  price: 50000,
  service_code: 'K10',
  doctor_selection_required: true,
};
const ivanov = { id: 7, user: { full_name: 'Иванов Иван' } };
const petrov = { id: 8, user: { full_name: 'Петров Пётр' } };

describe('wizard doctor and service cart identity', () => {
  it('adds the same service for two doctors as two rows and increments only the clicked pair', () => {
    const first = addServiceToWizardCart([], service, ivanov, 'item-1', '2026-09-25');
    const second = addServiceToWizardCart(first, service, petrov, 'item-2', '2026-09-25');
    const repeated = addServiceToWizardCart(second, service, ivanov, 'unused', '2026-09-25');

    expect(repeated).toHaveLength(2);
    expect(repeated.map((item) => [item.id, item.service_id, item.doctor_id, item.doctor_name, item.quantity])).toEqual([
      ['item-1', 10, 7, 'Иванов Иван', 2],
      ['item-2', 10, 8, 'Петров Пётр', 1],
    ]);
    expect(repeated.every((item) => item._new_for_wizard === true)).toBe(true);
  });

  it('mirrors both doctor identities into separate quote rows', () => {
    const items = addServiceToWizardCart(
      addServiceToWizardCart([], service, ivanov, 'item-1', '2026-09-25'),
      service, petrov, 'item-2', '2026-09-25',
    );
    expect(buildCartQuoteRequest({ items })?.items).toEqual([
      { service_id: 10, quantity: 1, specialist_id: 7 },
      { service_id: 10, quantity: 1, specialist_id: 8 },
    ]);
  });

  it('keeps a newly added second-doctor row distinct from the original row in edit-delta', () => {
    const identity = buildEditOriginalServiceIdentity(
      true,
      { source: 'desk', service_details: [{ service_id: 10, service_code: 'K10', quantity: 1, queue_entry_id: 42 }] },
      [service],
    );
    const original = {
      id: 'original', service_id: 10, doctor_id: 7, quantity: 1,
      original_queue_id: 42, service_name: 'Консультация',
    };
    const cart = addServiceToWizardCart([original], service, petrov, 'new-pair', '2026-09-25');
    const delta = buildEditDeltaTargetItems(cart, [service], identity);

    expect(delta.items).toEqual([{ service_id: 10, quantity: 1, specialist_id: 8 }]);
    expect(delta.hasNew).toBe(true);
    expect(delta.unroutable).toEqual([]);
  });

  it('keeps the new string cart ID as the repeat preview response key', () => {
    const [item] = addServiceToWizardCart([], service, ivanov, 'cart-unique-1', '2026-09-25');
    expect(repeatPreviewCandidateKey(item.id)).toBe('cart-unique-1');
    expect(repeatPreviewCandidateKey(42)).toBe('42');
    expect(repeatPreviewCandidateKey(undefined)).toBeNull();
  });

  it('refuses to add an unbookable doctor consultation even if invoked directly', () => {
    expect(addServiceToWizardCart([], { ...service, doctor_booking_available: false }, ivanov,
      'unbookable', '2026-09-25')).toEqual([]);
  });

  it('locks QR edits to the adapted entry owner, never to the specialty bucket doctor', () => {
    const bucket = { queue_tag: 'cardiology', specialist_id: 99 };
    const data = { date: '2026-09-25' };
    const doctorRow = adaptQueueEntry(
      { id: 40, record_kind: 'online_queue', source_kind: 'online', queue_entry_id: 40,
        queue_owner_kind: 'doctor', queue_owner_id: 7, service_details: [{ service_id: 10 }] },
      bucket, data, '2026-09-25', 'Пациент',
    );
    const resourceRow = adaptQueueEntry(
      { id: 41, record_kind: 'online_queue', source_kind: 'online', queue_entry_id: 41,
        queue_owner_kind: 'resource', queue_owner_id: 99, service_details: [{ service_id: 10 }] },
      bucket, data, '2026-09-25', 'Пациент',
    );

    expect(resolveQrLockedDoctorId(true, doctorRow)).toBe(7);
    expect(resolveQrLockedDoctorId(true, resourceRow)).toBeNull();
    expect(resolveQrLockedDoctorId(true, { ...doctorRow, queue_owner_id: null, doctor_id: 99 })).toBeNull();
    expect(resolveQrLockedDoctorId(false, doctorRow)).toBeUndefined();
  });
});
