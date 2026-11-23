/**
 * Review 3903 — write-integrity regressions for DentalVisitScreen.
 *
 * Covers the five race conditions the published review (5809118095) asked to
 * fix before merge:
 *  - P1 (DentalVisitScreen.tsx:1250): a ToothModal POST that resolves after a
 *    patient switch must not inject patient A's tooth into patient B's draft.
 *  - P1 (DentalVisitScreen.tsx:903): the visit-change flush must be serialized
 *    behind the pending autosave and reuse the row_version that autosave
 *    returned (no concurrent double POST with a stale version).
 *  - P1 (DentalVisitScreen.tsx:1060): the acknowledgement of an older autosave
 *    must not clear the dirty flag for a newer unsaved edit.
 *  - Recovery: a failed visit-change flush is surfaced and its snapshot
 *    restored when the same visit is reopened and the server has not advanced.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../../api/client';
import notify from '../../../services/notify';
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

// TeethChart stand-in: one button that opens the tooth modal for tooth 16.
vi.mock('../TeethChart', () => ({
  default: ({ onToothClick }: { onToothClick?: (n: number, d: Record<string, unknown>) => void }) => (
    <button type="button" onClick={() => onToothClick?.(16, { status: 'filled' })}>mock-teeth-chart</button>
  ),
}));

// ToothModal stand-in: the Save click only CAPTURES the onSave callback, the
// test invokes it later — modelling the modal's own POST resolving late.
const toothModalCapture = vi.hoisted(() => ({
  onSave: undefined as ((data: unknown, rowVersion?: number) => void) | undefined,
}));
vi.mock('../ToothModal', () => ({
  default: ({ onSave }: { onSave?: (data: unknown, rowVersion?: number) => void }) => (
    <button
      type="button"
      onClick={() => { toothModalCapture.onSave = onSave; }}
    >
      mock-tooth-save
    </button>
  ),
}));

vi.mock('../../ai/AIAssistant', () => ({ default: () => null }));

type EmrResponse = { status: number; data: Record<string, unknown> };
type SaveResponse = { data: { row_version: number } };

const patient = (visitId: number, patientId: number) => ({ visit_id: visitId, patient_id: patientId });

const loadedEMR = (
  data: Record<string, unknown> = {},
  rowVersion = 1,
  identity: { patient_id?: number | string; visit_id?: number | string } = { patient_id: 7, visit_id: 41 },
): EmrResponse => ({
  status: 200,
  data: { data, row_version: rowVersion, patient_id: identity.patient_id, visit_id: identity.visit_id },
});

const TEXTAREA_NAME = 'dental.dental_dvs_anamnesis_aria';
const COMPLETE_BUTTON_NAME = 'dental.dental_dvs_aria_complete';
const getTextarea = () => screen.getByRole('textbox', { name: TEXTAREA_NAME });

beforeEach(() => {
  vi.clearAllMocks();
  toothModalCapture.onSave = undefined;
  vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
    url.includes('/patient/')
      ? { status: 404, data: null }
      : loadedEMR(),
  ) as never);
  vi.mocked(apiClient.post).mockResolvedValue({ data: { row_version: 2 } } as never);
});

describe('DentalVisitScreen write integrity (review 3903)', () => {
  it('P1 stale tooth save: a late ToothModal callback cannot write patient A\'s tooth into patient B\'s draft', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
      url.includes('/patient/')
        ? { status: 404, data: null }
        : url.endsWith('/41')
          ? loadedEMR({ anamnesis_morbi: 'patient A draft' }, 1, { patient_id: 7, visit_id: 41 })
          : loadedEMR({ anamnesis_morbi: 'patient B draft' }, 5, { patient_id: 8, visit_id: 42 }),
    ) as never);
    const onCompleteVisit = vi.fn();
    const view = render(<DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={onCompleteVisit} />);
    await waitFor(() => expect(getTextarea()).toHaveProperty('value', 'patient A draft'));

    // Open A's tooth modal and press Save — the modal's own POST stays pending
    // while the clinician switches to patient B.
    fireEvent.click(screen.getByText('mock-teeth-chart'));
    fireEvent.click(screen.getByText('mock-tooth-save'));
    expect(toothModalCapture.onSave).toBeDefined();

    view.rerender(<DentalVisitScreen patient={patient(42, 8)} onCompleteVisit={onCompleteVisit} />);
    await waitFor(() => expect(getTextarea()).toHaveProperty('value', 'patient B draft'));

    // The modal's POST for A resolves only now and fires its captured onSave.
    await act(async () => {
      toothModalCapture.onSave?.({ status: 'filled', procedures: [{ id: 'p1', name: 'SYNTHETIC-A-filling', price: 1000 }] }, 2);
    });

    // A's tooth was dropped: no success toast, and B's saved draft carries no
    // tooth contamination.
    expect(notify.success).not.toHaveBeenCalledWith('dental.dental_dvs_tooth_saved', expect.anything());
    fireEvent.click(screen.getByRole('button', { name: COMPLETE_BUTTON_NAME }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith('/v2/emr/42', expect.objectContaining({
      row_version: 5,
      data: expect.objectContaining({
        anamnesis_morbi: 'patient B draft',
        specialty_data: expect.objectContaining({ tooth_status: {} }),
      }),
    })));
  }, 10000);

  it('P1 serialized flush: the visit-change flush waits for the in-flight autosave and reuses the version it returned', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
      url.includes('/patient/')
        ? { status: 404, data: null }
        : url.endsWith('/41')
          ? loadedEMR({ anamnesis_morbi: 'patient A draft' }, 1, { patient_id: 7, visit_id: 41 })
          : loadedEMR({ anamnesis_morbi: 'patient B draft' }, 5, { patient_id: 8, visit_id: 42 }),
    ) as never);
    let resolveAutosave: ((response: SaveResponse) => void) | undefined;
    let resolveFlush: ((response: SaveResponse) => void) | undefined;
    vi.mocked(apiClient.post).mockImplementation((url: string) => {
      const postsToA = vi.mocked(apiClient.post).mock.calls.filter(([u]) => u === '/v2/emr/41').length;
      if (url === '/v2/emr/41' && postsToA === 1) {
        return new Promise((resolve) => { resolveAutosave = resolve; }) as never;
      }
      if (url === '/v2/emr/41') {
        return new Promise((resolve) => { resolveFlush = resolve; }) as never;
      }
      return Promise.resolve({ data: { row_version: 9 } }) as never;
    });

    const view = render(<DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={vi.fn()} />);
    const textarea = await waitFor(() => getTextarea());
    await waitFor(() => expect(textarea).toHaveProperty('value', 'patient A draft'));

    // A's debounce fires; the autosave POST stays in flight.
    fireEvent.change(textarea, { target: { value: 'unsaved patient A edit' } });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 1600)); });
    expect(vi.mocked(apiClient.post).mock.calls.filter(([u]) => u === '/v2/emr/41')).toHaveLength(1);

    // Switch to B while A's autosave is still pending.
    view.rerender(<DentalVisitScreen patient={patient(42, 8)} onCompleteVisit={vi.fn()} />);

    // The flush is serialized behind the autosave — no concurrent second POST
    // reusing row_version 1.
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)); });
    expect(vi.mocked(apiClient.post).mock.calls.filter(([u]) => u === '/v2/emr/41')).toHaveLength(1);

    // The autosave acknowledgement advances the version to 2; only then may
    // the flush post, and it must carry version 2 and the newest snapshot.
    await act(async () => { resolveAutosave?.({ data: { row_version: 2 } }); });
    await waitFor(() => expect(vi.mocked(apiClient.post).mock.calls.filter(([u]) => u === '/v2/emr/41')).toHaveLength(2));
    expect(apiClient.post).toHaveBeenLastCalledWith('/v2/emr/41', expect.objectContaining({
      row_version: 2,
      is_draft: true,
      data: expect.objectContaining({ anamnesis_morbi: 'unsaved patient A edit' }),
    }));
    await act(async () => { resolveFlush?.({ data: { row_version: 3 } }); });

    // B loads only after the flush settled.
    await waitFor(() => expect(getTextarea()).toHaveProperty('value', 'patient B draft'));
  }, 10000);

  it('P1 stale autosave ack: an older acknowledgement does not clear the dirty flag of a newer edit', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
      url.includes('/patient/')
        ? { status: 404, data: null }
        : url.endsWith('/41')
          ? loadedEMR({ anamnesis_morbi: 'patient A draft' }, 1, { patient_id: 7, visit_id: 41 })
          : loadedEMR({ anamnesis_morbi: 'patient B draft' }, 5, { patient_id: 8, visit_id: 42 }),
    ) as never);
    let resolveAutosave: ((response: SaveResponse) => void) | undefined;
    let resolveFlush: ((response: SaveResponse) => void) | undefined;
    vi.mocked(apiClient.post).mockImplementation((url: string) => {
      const postsToA = vi.mocked(apiClient.post).mock.calls.filter(([u]) => u === '/v2/emr/41').length;
      if (url === '/v2/emr/41' && postsToA === 1) {
        return new Promise((resolve) => { resolveAutosave = resolve; }) as never;
      }
      if (url === '/v2/emr/41') {
        return new Promise((resolve) => { resolveFlush = resolve; }) as never;
      }
      return Promise.resolve({ data: { row_version: 9 } }) as never;
    });

    const view = render(<DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={vi.fn()} />);
    const textarea = await waitFor(() => getTextarea());
    await waitFor(() => expect(textarea).toHaveProperty('value', 'patient A draft'));

    // Edit A1 fires the debounced autosave with snapshot A1.
    fireEvent.change(textarea, { target: { value: 'first edit' } });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 1600)); });
    expect(vi.mocked(apiClient.post).mock.calls.filter(([u]) => u === '/v2/emr/41')).toHaveLength(1);

    // Edit A2 lands while A1's POST is in flight.
    fireEvent.change(getTextarea(), { target: { value: 'second edit' } });

    // A1's acknowledgement arrives: it must NOT clear the dirty flag of A2.
    await act(async () => { resolveAutosave?.({ data: { row_version: 2 } }); });

    // Switch before A2's debounce fires: the flush must still carry A2 with
    // the version A1's acknowledgement returned.
    view.rerender(<DentalVisitScreen patient={patient(42, 8)} onCompleteVisit={vi.fn()} />);
    await waitFor(() => expect(vi.mocked(apiClient.post).mock.calls.filter(([u]) => u === '/v2/emr/41')).toHaveLength(2));
    expect(apiClient.post).toHaveBeenLastCalledWith('/v2/emr/41', expect.objectContaining({
      row_version: 2,
      is_draft: true,
      data: expect.objectContaining({ anamnesis_morbi: 'second edit' }),
    }));
    await act(async () => { resolveFlush?.({ data: { row_version: 3 } }); });
    await waitFor(() => expect(getTextarea()).toHaveProperty('value', 'patient B draft'));
  }, 10000);

  it('recovery: a failed visit-change flush is surfaced and restored when the visit is reopened', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => Promise.resolve(
      url.includes('/patient/')
        ? { status: 404, data: null }
        : url.endsWith('/41')
          ? loadedEMR({ anamnesis_morbi: 'patient A draft' }, 1, { patient_id: 7, visit_id: 41 })
          : loadedEMR({ anamnesis_morbi: 'patient B draft' }, 5, { patient_id: 8, visit_id: 42 }),
    ) as never);
    // The flush POST for A fails; every later save succeeds.
    vi.mocked(apiClient.post).mockImplementation((url: string) => (
      url === '/v2/emr/41' ? Promise.reject({ response: { status: 503 } }) : Promise.resolve({ data: { row_version: 9 } })
    ) as never);

    const onCompleteVisit = vi.fn();
    const view = render(<DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={onCompleteVisit} />);
    const textarea = await waitFor(() => getTextarea());
    await waitFor(() => expect(textarea).toHaveProperty('value', 'patient A draft'));

    fireEvent.change(getTextarea(), { target: { value: 'recoverable patient A edit' } });

    // The switch happens while A's draft is still dirty; the flush fails.
    view.rerender(<DentalVisitScreen patient={patient(42, 8)} onCompleteVisit={onCompleteVisit} />);
    await waitFor(() => expect(getTextarea()).toHaveProperty('value', 'patient B draft'));
    await waitFor(() => expect(notify.error).toHaveBeenCalledWith('dental2.visit_protocol_save_failed'));

    // Reopening A (server row_version unchanged since the failure) restores
    // the stashed draft instead of silently dropping the edit.
    vi.mocked(apiClient.post).mockResolvedValue({ data: { row_version: 2 } } as never);
    view.rerender(<DentalVisitScreen patient={patient(41, 7)} onCompleteVisit={onCompleteVisit} />);
    await waitFor(() => expect(getTextarea()).toHaveProperty('value', 'recoverable patient A edit'));

    // The recovered draft is a live draft again: completing the visit saves it.
    fireEvent.click(screen.getByRole('button', { name: COMPLETE_BUTTON_NAME }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith('/v2/emr/41', expect.objectContaining({
      row_version: 1,
      is_draft: true,
      data: expect.objectContaining({ anamnesis_morbi: 'recoverable patient A edit' }),
    })));
    await waitFor(() => expect(onCompleteVisit).toHaveBeenCalledWith(
      expect.objectContaining({ anamnesis_morbi: 'recoverable patient A edit' }),
    ));
  }, 10000);
});
