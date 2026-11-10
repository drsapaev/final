/**
 * RETRO-3966-01 (post-merge code review PR 3968 of round-26 PR #3966) —
 * fail-first regression at the DentalVisitScreen wiring level.
 *
 * A signed/locked record opened the tooth modal in its fully editable form
 * (the modal received no readOnly input and its Save POSTs /v2/emr). The
 * screen must pass the read-only clinical contract down to the modal
 * explicitly: locked record → inspection-only modal, editable record →
 * editing modal.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../../api/client';
import DentalVisitScreen from '../DentalVisitScreen';

vi.mock('../../../api/client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
}));
vi.mock('../../../services/notify', () => ({
  default: { info: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));
vi.mock('../../../utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock('../../../i18n/useTranslation', () => {
  return {
    useTranslation: () => ({ t: (key: string) => key }),
    TranslationProvider: ({ children }: { children: unknown }) => children,
  };
});
vi.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({}),
}));

// TeethChart stand-in: one button that reproduces the chart's read-only
// inspection routing (onInspect) — the real chart never calls onToothClick
// while readOnly.
vi.mock('../TeethChart', () => ({
  default: ({ onInspect }: { onInspect?: (n: number, d: Record<string, unknown>) => void }) => (
    <button type="button" onClick={() => onInspect?.(16, { status: 'filled' })}>mock-teeth-chart</button>
  ),
}));

// ToothModal stand-in: capture every prop the screen hands to the modal so
// the test can assert the inspection-only contract without mounting the real
// dialog tree.
const toothModalSpy = vi.hoisted(() => ({
  props: undefined as Record<string, unknown> | undefined,
}));
vi.mock('../ToothModal', () => ({
  default: (props: Record<string, unknown>) => {
    toothModalSpy.props = props;
    return <div>mock-tooth-modal</div>;
  },
}));

vi.mock('../../ai/AIAssistant', () => ({ default: () => null }));

const patient = (visitId: number, patientId: number) => ({ visit_id: visitId, patient_id: patientId });

const loadedEMR = (
  data: Record<string, unknown> = {},
  rowVersion = 1,
  recordStatus?: string,
): { status: number; data: Record<string, unknown> } => ({
  status: 200,
  data: {
    data,
    row_version: rowVersion,
    patient_id: 7,
    visit_id: 41,
    ...(recordStatus ? { status: recordStatus } : {}),
  },
});

const TEXTAREA_NAME = 'dental.dental_dvs_anamnesis_aria';

beforeEach(() => {
  vi.clearAllMocks();
  toothModalSpy.props = undefined;
  vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
    url.includes('/patient/')
      ? { status: 404, data: null }
      : loadedEMR({ anamnesis_morbi: 'SYNTHETIC draft' }),
  ) as never);
  vi.mocked(apiClient.post).mockResolvedValue({ data: { row_version: 2 } } as never);
});

describe('DentalVisitScreen tooth inspection routing (RETRO-3966-01)', () => {
  it('a signed record opens the tooth modal in inspection-only mode', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
      url.includes('/patient/')
        ? { status: 404, data: null }
        : loadedEMR({ anamnesis_morbi: 'SYNTHETIC signed draft' }, 1, 'signed'),
    ) as never);

    render(<DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={vi.fn()} />);
    const textarea = await waitFor(() => screen.getByRole('textbox', { name: TEXTAREA_NAME }));
    await waitFor(() => expect(textarea).toHaveProperty('value', 'SYNTHETIC signed draft'));

    // Locked-record tooth click → the modal contract handed down by the
    // screen must be inspection-only.
    fireEvent.click(screen.getByText('mock-teeth-chart'));

    expect(screen.getByText('mock-tooth-modal')).toBeDefined();
    expect(toothModalSpy.props).toBeDefined();
    expect(toothModalSpy.props!.readOnly).toBe(true);
  }, 10000);

  it('control: an unsigned record still opens the editable tooth modal', async () => {
    render(<DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={vi.fn()} />);
    const textarea = await waitFor(() => screen.getByRole('textbox', { name: TEXTAREA_NAME }));
    await waitFor(() => expect(textarea).toHaveProperty('value', 'SYNTHETIC draft'));

    fireEvent.click(screen.getByText('mock-teeth-chart'));

    expect(screen.getByText('mock-tooth-modal')).toBeDefined();
    expect(toothModalSpy.props).toBeDefined();
    expect(toothModalSpy.props!.readOnly).toBe(false);
  }, 10000);
});
