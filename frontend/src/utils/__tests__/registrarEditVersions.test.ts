import { describe, expect, it, vi } from 'vitest';

import { buildEditOriginalServiceIdentity } from '../../components/wizard/wizardUtils';
import { aggregatePatientsForAllDepartments } from '../registrarAggregation';

vi.mock('../logger', () => ({ default: { log: vi.fn(), warn: vi.fn(), error: vi.fn() } }));

const firstVersion = '2026-01-01T10:00:00.123456Z';
const secondVersion = '2026-01-01T10:00:00.623456Z';
const row = (id: number, updatedAt: string | null, detail: Record<string, unknown> = {}) => ({
  id,
  patient_id: 1,
  patient_fio: 'SYNTHETIC-Version',
  queue_entry_id: id,
  record_kind: 'online_queue',
  record_type: 'online_queue',
  source: 'desk',
  updated_at: updatedAt,
  service_details: [{ service_id: id + 100, quantity: 1, ...detail }],
});

describe('queue versions survive worklist aggregation and wizard extraction', () => {
  it('keeps each original server timestamp, including all fractional digits', () => {
    const rows = [row(11, firstVersion), row(12, secondVersion)];
    const [group] = aggregatePatientsForAllDepartments(rows);
    const identity = buildEditOriginalServiceIdentity(true, group, []);
    expect(identity.entryUpdatedAtMap).toEqual({ 11: firstVersion, 12: secondVersion });
    expect(rows[0].service_details[0]).not.toHaveProperty('updated_at');
  });

  it('preserves a detail-specific version over the containing row version', () => {
    const [group] = aggregatePatientsForAllDepartments([
      row(11, secondVersion, { queue_entry_id: 11, updated_at: firstVersion }),
    ]);
    expect(buildEditOriginalServiceIdentity(true, group, []).entryUpdatedAtMap)
      .toEqual({ 11: firstVersion });
  });

  it('inherits a row version when the detail already names that same entry', () => {
    const [group] = aggregatePatientsForAllDepartments([
      row(11, firstVersion, { queue_entry_id: 11 }), row(12, secondVersion),
    ]);
    expect(buildEditOriginalServiceIdentity(true, group, []).entryUpdatedAtMap)
      .toEqual({ 11: firstVersion, 12: secondVersion });
  });

  it('does not borrow the group version for an entry without a server version', () => {
    const [group] = aggregatePatientsForAllDepartments([
      row(11, null), row(12, secondVersion),
    ]);
    expect(buildEditOriginalServiceIdentity(true, group, []).entryUpdatedAtMap)
      .toEqual({ 12: secondVersion });
  });

  it('does not attach a parent timestamp to a detail identifying another entry', () => {
    const [group] = aggregatePatientsForAllDepartments([
      row(11, firstVersion, { queue_entry_id: 99 }),
    ]);
    expect(buildEditOriginalServiceIdentity(true, group, []).entryUpdatedAtMap).toEqual({});
  });

  it('keeps the ungrouped row fallback for its own explicitly identified entry', () => {
    const initial = row(11, firstVersion, { queue_entry_id: 11 });
    expect(buildEditOriginalServiceIdentity(true, initial, []).entryUpdatedAtMap)
      .toEqual({ 11: firstVersion });
  });
});
