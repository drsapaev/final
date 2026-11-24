/**
 * DERMATIMELINE-FE-002 (owner registry #4063; review-group audit comment
 * 6690449597) — queue-only records are shown with 0%/unknown visit
 * progress.
 *
 * A queue-only visit feeds `VisitTimeline` the raw queue-entry status
 * (the parent assigns row.status into currentAppointment.status, and for
 * a visit without an appointment id refreshCanonicalStatus only touches
 * the EMR status, never appointment.status). `VisitTimeline` and
 * `getProgress` recognize exclusively the canonical appointment pipeline
 * (pending/paid/in_visit/completed) — queue statuses such as
 * `waiting`/`called`/`in_service`/`in_cabinet` fall outside it, so an
 * ACTIVE queue-only clinical visit renders 0% progress and an
 * "Unknown" stage.
 *
 * Contract after the repair (per the red-first: normalized status
 * projection with an explicit source-kind and SSOT-based stage):
 * - The canonical SSOT queue state machine
 *   (types/state-machines/queue.ts: waiting → called → in_service →
 *   in_cabinet → served → completed) is projected onto the appointment
 *   stages it represents: called/in_service/in_cabinet → in_visit,
 *   served → completed, waiting → pending, skipped/cancelled → the
 *   matching non-flow appointment statuses. An active queue visit then
 *   shows the correct stage/progress instead of a false 0%.
 * - A genuinely unknown status never claims 0% — the progress is
 *   explicitly shown as unknown («—») next to the existing Unknown label.
 * - Canonical appointment statuses behave exactly as before (controls).
 * - A truthful 0% stays truthful: queue `waiting` legitimately shows 0%
 *   (the visit has not started).
 *
 * Red-first: on the pre-fix source the queue-only cases fail (in_service
 * shows 0%/Unknown with a pending visit step; served shows 0% with
 * pending steps; unknown shows a false 0%) while both controls pass on
 * main.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import VisitTimeline from '../VisitTimeline';

vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
vi.mock('../ui/macos', () => ({
  Badge: ({ children }: { children?: ReactNode }) => <span>{children}</span>,
  Card: ({ children }: { children?: ReactNode }) => <section>{children}</section>,
}));

// Queue-row shape: no appointment id/paid_at, raw queue status.
const QUEUE_ONLY_BASE = { queue_id: 77 };

function visitStep(): HTMLElement {
  return screen.getByText('final.timeline_doctor_visit').closest('div.relative') as HTMLElement;
}

describe('DERMATIMELINE-FE-002 — queue-only visits are never a false 0% while active', () => {
  it('an active queue visit (in_service) renders the in-visit stage with real progress', () => {
    render(
      <VisitTimeline
        appointment={{ ...QUEUE_ONLY_BASE, status: 'in_service' }}
        emr={{ is_draft: false, saved_at: '2026-11-24T10:00:00Z' }}
      />,
    );

    // The visit step is CURRENT for an actively served patient.
    expect(visitStep().textContent).toContain('misc.vt_v_protsesse');
    expect(visitStep().textContent).not.toContain('misc.vt_ozhidanie');
    // Progress reflects the canonical in-visit stage (2 of 3 transitions).
    expect(screen.getByText('67%')).toBeTruthy();
    // The stage label is the canonical in-visit label, not "Unknown".
    expect(screen.getAllByText('На приеме').length).toBeGreaterThan(0);
  });

  it('a fully served queue visit (served) renders the completed stage at 100%', () => {
    render(
      <VisitTimeline
        appointment={{ ...QUEUE_ONLY_BASE, status: 'served' }}
        emr={{ is_draft: false, saved_at: '2026-11-24T10:00:00Z' }}
      />,
    );

    expect(visitStep().textContent).toContain('misc.vt_gotovo');
    expect(screen.getByText('100%')).toBeTruthy();
  });

  it('a genuinely unknown status never claims 0% — the progress is explicitly unknown', () => {
    render(<VisitTimeline appointment={{ ...QUEUE_ONLY_BASE, status: 'mystery_status' }} emr={null} />);

    expect(screen.queryByText('0%')).toBeNull();
    expect(screen.getByText('—')).toBeTruthy();
    expect(screen.getAllByText('misc.vt_neizvestno').length).toBeGreaterThan(0);
  });

  it('control: canonical appointment statuses behave exactly as before', () => {
    render(
      <VisitTimeline
        appointment={{ created_at: '2026-11-24T09:00:00Z', status: 'in_visit' }}
        emr={{ is_draft: false, saved_at: '2026-11-24T10:00:00Z' }}
      />,
    );

    expect(visitStep().textContent).toContain('misc.vt_v_protsesse');
    expect(screen.getByText('67%')).toBeTruthy();
    expect(screen.getAllByText('На приеме').length).toBeGreaterThan(0);
  });

  it('control: queue waiting legitimately shows 0% (the visit has not started)', () => {
    render(<VisitTimeline appointment={{ ...QUEUE_ONLY_BASE, status: 'waiting' }} emr={null} />);

    expect(screen.getByText('0%')).toBeTruthy();
    expect(visitStep().textContent).toContain('misc.vt_ozhidanie');
  });
});
