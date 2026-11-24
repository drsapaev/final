/**
 * DERMAHIST-FE-004 (owner registry #4063; fourteenth review group) —
 * history entries carry detailed clinical findings that the only
 * reachable history UI never shows or links to.
 *
 * The backend union already sends the detail fields (lesions,
 * distribution, symptoms, treatment_plan for examinations; products_used,
 * results, follow_up for procedures) plus the emr/legacy source marker
 * and the visit identity — but the frontend DTOs drop those fields and
 * the cards render only the compact summary (date, skin type/condition,
 * diagnosis; date, type, area) with no detail action/link at all: a
 * clinician reviewing the longitudinal history cannot inspect the
 * findings despite receiving them in the response.
 *
 * Contract after the repair: each card keeps its compact summary and
 * gains a native <details>/<summary> disclosure (keyboard-accessible by
 * specification, read-only) exposing exactly the record's own detail
 * values with their labels, the source label and the visit identity —
 * no cross-record leakage, no divergent client-side persistence (the
 * history stays backend SSOT). Cards without detail fields stay compact
 * with no toggle.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import DermaHistoryTab from '../DermaHistoryTab';
import type {
  DermatologyCosmeticProcedure,
  DermatologySkinExamination,
} from '../../../pages/useDermatologyPatientHistory';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
vi.mock('../../ui/macos', () => ({
  Badge: ({ children }: { children?: ReactNode }) => <span>{children}</span>,
  Card: ({ children }: { children?: ReactNode }) => <section>{children}</section>,
}));

const richExam: DermatologySkinExamination = {
  id: 'emr-501',
  examination_date: '2026-11-16',
  skin_type: 'combination',
  skin_condition: 'Чувствительная кожа',
  diagnosis: 'Розацеа',
  source: 'emr',
  visit_id: 42,
  lesions: 'papules on both cheeks',
  distribution: 'symmetric facial',
  symptoms: 'itching, flushing',
  treatment_plan: 'topical azelaic acid BID',
};

const richProcedure: DermatologyCosmeticProcedure = {
  id: 7,
  procedure_date: '2026-11-10',
  procedure_type: 'chemical peel',
  area_treated: 'face',
  source: 'legacy',
  products_used: 'glycolic acid 30%',
  results: 'mild erythema, resolved',
  follow_up: 'repeat in 4 weeks',
};

// A legacy row with none of the detail fields — the card must stay
// compact (summary only, no disclosure toggle).
const sparseExam: DermatologySkinExamination = {
  id: 12,
  examination_date: '2026-10-01',
  skin_type: 'oily',
  source: 'legacy',
};

function detailsFor(container: HTMLElement, needle: string): HTMLElement | null {
  return Array.from(container.querySelectorAll('details')).find(
    (node) => node.textContent?.includes(needle),
  ) ?? null;
}

describe('DERMAHIST-FE-004 — history details are reachable, identified and read-only', () => {
  it('an examination card exposes its own findings behind a native disclosure', () => {
    const { container } = render(
      <DermaHistoryTab skinExaminations={[richExam]} cosmeticProcedures={[]} />,
    );

    const examDetails = detailsFor(container, 'papules on both cheeks');
    expect(examDetails).not.toBeNull();
    // Native <summary> is keyboard-operable by specification.
    expect(examDetails!.querySelector('summary')?.tagName).toBe('SUMMARY');
    // The record's own values, labels, source and visit identity — no leakage.
    for (const needle of [
      'derma.derma_history_details_summary',
      'derma.derma_history_field_lesions',
      'papules on both cheeks',
      'derma.derma_history_field_distribution',
      'symmetric facial',
      'derma.derma_history_field_symptoms',
      'itching, flushing',
      'derma.derma_history_field_treatment_plan',
      'topical azelaic acid BID',
      'derma.derma_history_source_emr',
      'derma.derma_history_field_visit',
      '42',
    ]) {
      expect(examDetails!.textContent).toContain(needle);
    }
  });

  it('a procedure card exposes products, results and follow-up with its source label', () => {
    const { container } = render(
      <DermaHistoryTab skinExaminations={[]} cosmeticProcedures={[richProcedure]} />,
    );

    const procedureDetails = detailsFor(container, 'glycolic acid 30%');
    expect(procedureDetails).not.toBeNull();
    expect(procedureDetails!.querySelector('summary')?.tagName).toBe('SUMMARY');
    for (const needle of [
      'derma.derma_history_field_products_used',
      'glycolic acid 30%',
      'derma.derma_history_field_results',
      'mild erythema, resolved',
      'derma.derma_history_field_follow_up',
      'repeat in 4 weeks',
      'derma.derma_history_source_legacy',
    ]) {
      expect(procedureDetails!.textContent).toContain(needle);
    }
  });

  it('a card without detail fields stays compact with no disclosure toggle', () => {
    const { container } = render(
      <DermaHistoryTab skinExaminations={[sparseExam]} cosmeticProcedures={[]} />,
    );

    expect(container.querySelectorAll('details')).toHaveLength(0);
    expect(container.textContent).toContain('2026-10-01');
    expect(container.textContent).toContain('oily');
  });

  it('the disclosure region is strictly read-only (no editable controls)', () => {
    const { container } = render(
      <DermaHistoryTab skinExaminations={[richExam]} cosmeticProcedures={[richProcedure]} />,
    );

    expect(container.querySelector('input, textarea, select, [contenteditable="true"]')).toBeNull();
    // The compact summary rows remain visible outside the disclosures.
    expect(screen.getByText('Розацеа')).toBeTruthy();
    expect(screen.getByText('chemical peel · face')).toBeTruthy();
  });
});
