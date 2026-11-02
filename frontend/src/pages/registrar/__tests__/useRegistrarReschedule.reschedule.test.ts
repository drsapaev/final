/**
 * REG-FE-041 (#3820, registrar audit ledger PR #3803) — fail-first:
 * grouped-row reschedule must address exactly ONE explicit visit.
 *
 * The registrar worklist can hold an aggregated row with several visits
 * (`visit_ids`, built after a multi-service wizard booking). The old
 * `resolveRescheduleVisitId` silently picked `visit_ids[0]` while
 * `removeRescheduledAppointmentFromView` optimistically removed the WHOLE
 * group row from the view — implying the entire group moved although the
 * backend reschedule command addresses a single visit id.
 *
 * Contract (issue #3820):
 * - `getRescheduleVisitIds` exposes the full ordered visit list so the
 *   dialog can require an explicit target-visit choice.
 * - After a successful move of visit 101 from `visit_ids=[101,102]`, the
 *   group row (visit 102) must REMAIN visible; the backend read model owns
 *   the grouping and the caller refreshes from it.
 * - Single-visit rows keep the existing removal behavior.
 * - Unrelated rows are never removed.
 */
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useRegistrarReschedule } from '../useRegistrarReschedule';

type Row = Record<string, unknown>;

const makeHook = () => {
  let appointments: Row[] = [];
  const setAppointments = vi.fn((updater: (prev: Row[]) => Row[]) => {
    appointments = updater(appointments);
  });
  const hook = renderHook(() => useRegistrarReschedule({ setAppointments }));
  return {
    hook,
    setAppointments,
    state: () => appointments,
    seed: (rows: Row[]) => { appointments = rows; },
  };
};

describe('useRegistrarReschedule — REG-FE-041 grouped reschedule (fail-first)', () => {
  it('exposes the full visit-id list of an aggregated row (getRescheduleVisitIds)', () => {
    const { hook } = makeHook();
    const ids = hook.result.current.getRescheduleVisitIds({
      id: 101, visit_id: 101, visit_ids: [101, 102],
    });
    expect(ids).toEqual([101, 102]);
  });

  it('returns a single-element list for plain visit rows', () => {
    const { hook } = makeHook();
    expect(hook.result.current.getRescheduleVisitIds({ id: 201, visit_id: 201 })).toEqual([201]);
    expect(hook.result.current.getRescheduleVisitIds({ id: 202, visitId: 202 })).toEqual([202]);
    expect(hook.result.current.getRescheduleVisitIds({ id: 203 })).toEqual([]);
  });

  it('keeps the remaining grouped visits visible after ONE visit was rescheduled', () => {
    const ctx = makeHook();
    const groupRow: Row = {
      id: 101,
      visit_id: 101,
      visit_ids: [101, 102],
      grouped_record_refs: [
        { record_kind: 'visit', record_id: 101 },
        { record_kind: 'visit', record_id: 102 },
      ],
    };
    const unrelatedRow: Row = { id: 55, visit_id: 55 };
    ctx.seed([groupRow, unrelatedRow]);

    // Visit 101 was rescheduled; visit 102 must stay on screen. The group
    // row is NOT optimistically removed: only one visit moved, the backend
    // read model owns the grouping, and the caller's loadAppointments
    // refresh is the verified truth.
    ctx.hook.result.current.removeRescheduledAppointmentFromView(groupRow, 101);

    const remainingIds = ctx.state().map((row) => row.id);
    expect(remainingIds).toContain(101); // the group row (visit 102) stays
    expect(remainingIds).toContain(55); // unrelated row untouched
  });

  it('still removes a single-visit row after its visit was rescheduled', () => {
    const ctx = makeHook();
    const soloRow: Row = { id: 201, visit_id: 201 };
    const otherRow: Row = { id: 66, visit_id: 66 };
    ctx.seed([soloRow, otherRow]);

    ctx.hook.result.current.removeRescheduledAppointmentFromView(soloRow, 201);

    const remainingIds = ctx.state().map((row) => row.id);
    expect(remainingIds).not.toContain(201);
    expect(remainingIds).toContain(66);
  });

  it('resolveRescheduleVisitId keeps its single-visit contract (regression pin)', () => {
    const { hook } = makeHook();
    expect(hook.result.current.resolveRescheduleVisitId({ visit_ids: [7], visit_id: 7 })).toBe(7);
    expect(hook.result.current.resolveRescheduleVisitId({ visit_id: 8 })).toBe(8);
    expect(hook.result.current.resolveRescheduleVisitId({ visitId: 9 })).toBe(9);
    expect(hook.result.current.resolveRescheduleVisitId({})).toBeNull();
  });
});
