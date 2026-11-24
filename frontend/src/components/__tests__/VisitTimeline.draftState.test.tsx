/**
 * DERMATIMELINE-FE-001 (owner registry #4063; review-group audit comment
 * 6690449597) — the EMR draft is reported as completed due to a
 * snake_case vs camelCase mismatch.
 *
 * The parent dermatology panel feeds `VisitTimeline` the raw EMR status
 * payload whose canonical fields are snake_case (`is_draft`, `saved_at`,
 * per backend/app/schemas/emr.py — the panel even normalizes its own
 * state to `is_draft`), but `VisitTimelineRecord` only declares
 * camelCase (`isDraft`, `savedAt`). `emr && !emr.isDraft` is therefore
 * true for every backend payload: a TRUE draft (is_draft: true, unsaved/
 * unsigned) is rendered as "Completed/Готово" on the timeline, and the
 * saved_at timestamp never shows.
 *
 * Contract after the repair: a typed adapter at the component boundary
 * normalizes the canonical snake_case fields (camelCase aliases stay
 * accepted for legacy callers) — a true draft is rendered
 * current/unfinished with the save-EMR hint, a saved EMR is completed
 * with its saved_at timestamp; no truthiness fallback on a wrong-cased
 * field.
 *
 * Red-first: on the pre-fix source the snake_case cases fail (the draft
 * step reads «Готово», the hint and the timestamp are missing) while the
 * camelCase legacy control and the no-EMR control pass on both.
 * Step-scoped assertions: every timeline has several «Готово» badges
 * (appointment, payment, EMR), so each check is pinned to the EMR step.
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

const IN_VISIT_APPOINTMENT = {
  created_at: '2026-11-24T09:00:00Z',
  status: 'in_visit',
};

// The EMR step wrapper (div.relative around the h4 title + its badge).
function emrStep(): HTMLElement {
  return screen.getByText('final.timeline_emr').closest('div.relative') as HTMLElement;
}

describe('DERMATIMELINE-FE-001 — a true EMR draft is never reported as completed', () => {
  it('a snake_case draft (is_draft: true) renders current/unfinished with the save hint', () => {
    render(<VisitTimeline appointment={IN_VISIT_APPOINTMENT} emr={{ is_draft: true }} />);

    const step = emrStep();
    expect(step.textContent).toContain('misc.vt_v_protsesse');
    expect(step.textContent).not.toContain('misc.vt_gotovo');
    // The next-step hint tells the clinician to save the EMR first.
    expect(screen.getByText('misc.vt_sohranite_emk_dlya_zavershen')).toBeTruthy();
  });

  it('a snake_case saved EMR (is_draft: false) renders completed with its saved_at timestamp', () => {
    render(
      <VisitTimeline
        appointment={IN_VISIT_APPOINTMENT}
        emr={{ is_draft: false, saved_at: '2026-11-24T10:00:00Z' }}
      />,
    );

    const step = emrStep();
    expect(step.textContent).toContain('misc.vt_gotovo');
    expect(step.textContent).not.toContain('misc.vt_v_protsesse');
    expect(step.textContent).toContain('Завершено:');
    expect(step.textContent).toContain('2026');
  });

  it('legacy camelCase aliases keep working (positive control)', () => {
    render(<VisitTimeline appointment={IN_VISIT_APPOINTMENT} emr={{ isDraft: true }} />);

    const step = emrStep();
    expect(step.textContent).toContain('misc.vt_v_protsesse');
    expect(step.textContent).not.toContain('misc.vt_gotovo');
    expect(screen.getByText('misc.vt_sohranite_emk_dlya_zavershen')).toBeTruthy();
  });

  it('no EMR at all stays pending (positive control)', () => {
    render(<VisitTimeline appointment={IN_VISIT_APPOINTMENT} emr={null} />);

    const step = emrStep();
    expect(step.textContent).toContain('misc.vt_ozhidanie');
    expect(step.textContent).not.toContain('misc.vt_gotovo');
  });
});
