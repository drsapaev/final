/**
 * DERMAHIST-BE-001 (owner registry #4063; fourteenth review group) — the
 * canonical skin-examination history loses lesion localization entirely.
 *
 * Backend part: the history API now carries a schema-safe
 * `localization` field (the projected human-readable description).
 * Frontend part (this file): the history DTO declares the field and the
 * examination card displays it, so a localization-only examination is no
 * longer a blank card.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import DermaHistoryTab from '../DermaHistoryTab';
import type { DermatologySkinExamination } from '../../../pages/useDermatologyPatientHistory';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
vi.mock('../../ui/macos', () => ({
  Badge: ({ children }: { children?: ReactNode }) => <span>{children}</span>,
  Card: ({ children }: { children?: ReactNode }) => <section>{children}</section>,
}));

const baseExam: DermatologySkinExamination = {
  id: 'emr-501',
  examination_date: '2026-11-16',
  skin_type: 'combination',
  skin_condition: 'Чувствительная кожа',
  diagnosis: 'Розацеа',
};

describe('DERMAHIST-BE-001 — localization survives the round-trip into the history UI', () => {
  it('a localization-only examination is displayed, not a blank card', () => {
    render(
      <DermaHistoryTab
        skinExaminations={[
          { ...baseExam, skin_type: undefined, skin_condition: undefined, diagnosis: undefined, localization: 'левая щека' },
        ]}
      />,
    );
    expect(screen.getByText('левая щека')).toBeTruthy();
  });

  it('a full examination shows diagnosis and localization together', () => {
    render(
      <DermaHistoryTab
        skinExaminations={[{ ...baseExam, localization: 'спина' }]}
      />,
    );
    expect(screen.getByText('Розацеа')).toBeTruthy();
    expect(screen.getByText('спина')).toBeTruthy();
  });

  it('rows without localization keep rendering without an empty line', () => {
    render(<DermaHistoryTab skinExaminations={[baseExam]} />);
    expect(screen.getByText('Розацеа')).toBeTruthy();
    expect(screen.queryByText('левая щека')).toBeNull();
    expect(screen.queryByText('спина')).toBeNull();
  });
});
