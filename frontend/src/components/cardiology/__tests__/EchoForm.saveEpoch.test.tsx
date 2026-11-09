/**
 * RETRO-3941-03 (consolidated post-merge review of #3941, PR #3944) —
 * fail-first.
 *
 * On the merged round-20 source handleSave disabled only the Save button:
 * the input/conclusion handlers stayed active while the GET+POST were in
 * flight, and the request persisted the closure snapshot taken when Save
 * was clicked. If the doctor edited measurement B while the request for
 * snapshot A was in flight, the POST persisted A but the UI kept showing
 * B — and on 200 dirtyRef was cleared unconditionally, so the form claimed
 * everything was saved and a later pristine click was skipped. Potential
 * clinical data loss / false-success path.
 *
 * Contract after the fix (edit-epoch tracking):
 *  - the POST persists the snapshot submitted (correct atomic behavior);
 *  - if edits happened after submission started, the form does NOT claim
 *    the displayed values are saved: the stale-edit notice is shown, the
 *    dirty flag is preserved, and a follow-up Save persists the latest
 *    values instead of being skipped as "no changes".
 */
import React from 'react';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, beforeEach, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  api: {
    get: (...args: unknown[]) => apiMocks.get(...args),
    post: (...args: unknown[]) => apiMocks.post(...args),
  },
  apiClient: {
    get: (...args: unknown[]) => apiMocks.get(...args),
    post: (...args: unknown[]) => apiMocks.post(...args),
  },
  setSessionInvalidationListener: vi.fn(),
}));

import EchoForm from '../EchoForm';
import { renderWithProviders } from '../../../test/renderWithProviders';

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function emrWithEcho(ef: string, conclusion: string, rowVersion = 3) {
  return {
    data: {
      row_version: rowVersion,
      specialty_data: {
        echo: {
          leftVentricle: { edd: '5.0', esd: '3.2', ef, fs: '36', ivs: '1.0', pw: '0.9' },
          conclusion,
        },
      },
    },
    row_version: rowVersion,
  };
}

beforeEach(() => {
  apiMocks.get.mockReset();
  apiMocks.post.mockReset();
});

describe('RETRO-3941-03: edits made while Save is in flight are never treated as persisted', () => {
  it('an edit between submission start and ACK keeps the form dirty and requires a follow-up save', async () => {
    // Hydration returns the stored echo (ef 58, row_version 7).
    apiMocks.get.mockResolvedValueOnce({ data: emrWithEcho('58', 'Без патологии', 7) });

    renderWithProviders(<EchoForm visitId={41} patientId={7} />);
    await screen.findByDisplayValue('58');

    // Doctor edits EF 58 → 45 and clicks Save.
    fireEvent.change(screen.getByDisplayValue('58'), { target: { value: '45' } });

    // The save's re-read of the canonical EMR hangs while in flight…
    const gateGet = deferred<{ data: ReturnType<typeof emrWithEcho> }>();
    apiMocks.get.mockImplementationOnce(() => gateGet.promise);
    // …and so does the POST.
    const gatePost = deferred<{ status: number; data: unknown }>();
    apiMocks.post.mockImplementationOnce(() => gatePost.promise);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    });

    // While the request is in flight the doctor edits EF 45 → 52.
    fireEvent.change(screen.getByDisplayValue('45'), { target: { value: '52' } });

    // The in-flight sequence completes with success.
    await act(async () => {
      gateGet.resolve({ data: emrWithEcho('58', 'Без патологии', 7) });
      await Promise.resolve();
    });
    await act(async () => {
      gatePost.resolve({ status: 200, data: { data: { specialty_data: { echo: {} } } } });
      await Promise.resolve();
    });

    // The POST persisted the SUBMITTED snapshot (45) — that stays atomic…
    expect(apiMocks.post).toHaveBeenCalledTimes(1);
    expect(apiMocks.post.mock.calls[0][1].data.specialty_data.echo.leftVentricle.ef).toBe('45');

    // …but the displayed value (52) must NOT be claimed as saved: the form
    // reports the newer edits as unsaved instead of a success toast.
    expect(screen.getByDisplayValue('52')).toBeInTheDocument();
    await waitForStaleNotice();

    // The dirty flag survived, so the follow-up Save must NOT be skipped
    // as "no changes" — it POSTs again and persists the latest value (52).
    apiMocks.get.mockResolvedValueOnce({ data: emrWithEcho('45', 'Без патологии', 8) });
    apiMocks.post.mockResolvedValueOnce({ status: 200, data: { data: { specialty_data: { echo: {} } } } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    });

    expect(apiMocks.post).toHaveBeenCalledTimes(2);
    expect(apiMocks.post.mock.calls[1][1].data.specialty_data.echo.leftVentricle.ef).toBe('52');
  });

  it('a save without in-flight edits still shows the plain success notice', async () => {
    apiMocks.get.mockResolvedValueOnce({ data: emrWithEcho('58', 'Без патологии', 7) });
    renderWithProviders(<EchoForm visitId={42} patientId={7} />);
    await screen.findByDisplayValue('58');

    fireEvent.change(screen.getByDisplayValue('58'), { target: { value: '45' } });

    apiMocks.get.mockResolvedValueOnce({ data: emrWithEcho('58', 'Без патологии', 7) });
    apiMocks.post.mockResolvedValueOnce({ status: 200, data: { data: { specialty_data: { echo: {} } } } });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    });

    // No edits during the flight: the honest success notice appears.
    await waitFor(() => {
      expect(screen.getByText(/Результаты ЭхоКГ сохранены успешно/i)).toBeInTheDocument();
    });
    // …and no stale-edit notice.
    expect(screen.queryByText(/ещё не сохранены/i)).toBeNull();
  });

  it('the conclusion textarea counts as an edit while Save is in flight', async () => {
    apiMocks.get.mockResolvedValueOnce({ data: emrWithEcho('58', 'Старое заключение', 7) });
    renderWithProviders(<EchoForm visitId={43} patientId={7} />);
    await screen.findByDisplayValue('58');

    fireEvent.change(screen.getByDisplayValue('58'), { target: { value: '45' } });

    const gateGet = deferred<{ data: ReturnType<typeof emrWithEcho> }>();
    apiMocks.get.mockImplementationOnce(() => gateGet.promise);
    const gatePost = deferred<{ status: number; data: unknown }>();
    apiMocks.post.mockImplementationOnce(() => gatePost.promise);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    });

    // Conclusion edited while the request is in flight.
    fireEvent.change(screen.getByDisplayValue('Старое заключение'), { target: { value: 'Новое заключение' } });

    await act(async () => {
      gateGet.resolve({ data: emrWithEcho('58', 'Старое заключение', 7) });
      await Promise.resolve();
    });
    await act(async () => {
      gatePost.resolve({ status: 200, data: { data: { specialty_data: { echo: {} } } } });
      await Promise.resolve();
    });

    await waitForStaleNotice();
  });
});

/** Wait for the localized stale-edit notice (RETRO-3941-03). */
async function waitForStaleNotice() {
  await waitFor(() => {
    expect(screen.getByText(/правки, сделанные во время сохранения, ещё не сохранены/i)).toBeInTheDocument();
  });
  // And NOT the plain success notice for the displayed values.
  expect(screen.queryByText(/Результаты ЭхоКГ сохранены успешно/i)).toBeNull();
}
