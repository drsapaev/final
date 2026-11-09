/**
 * RETRO-3941-02 (consolidated post-merge review of #3941, PR #3944) —
 * fail-first.
 *
 * On the merged round-20 source a hydration failure of the canonical EMR
 * (any non-404 GET error, e.g. a transient 500) silently left a BLANK form
 * with Save enabled and dirty tracking reset. The doctor edited only EF,
 * Save's second loadExistingEmrDraft succeeded and returned the stored
 * EDD/valve/conclusion — but buildEchoEmrPayload assigned
 * specialty_data.echo = local blank state wholesale, so the untouched blank
 * fields OVERWROTE the stored echo subtree while the changed EF saved fine.
 *
 * Contract after the fix: hydration failures fail CLOSED —
 *  - Save stays disabled and the failure is surfaced (no silent blank form);
 *  - a Retry re-runs the canonical load;
 *  - after a successful retry the stored values are shown and Save re-enables;
 *  - no destructive POST can ever leave a form that never hydrated.
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

describe('RETRO-3941-02: hydration failure fails closed (no destructive save)', () => {
  it('a non-404 hydration error keeps Save disabled and surfaces the failure', async () => {
    apiMocks.get.mockRejectedValueOnce({ response: { status: 500 } });

    renderWithProviders(<EchoForm visitId={31} patientId={7} />);

    // The failure must be VISIBLE — not a silently blank editable form.
    await waitFor(() => {
      expect(screen.getByText(/Не удалось загрузить сохранённые показатели ЭхоКГ/i)).toBeInTheDocument();
    });

    // Save stays blocked: an unhydrated form must never be able to
    // overwrite the stored echo subtree (which we could not read).
    const saveButton = screen.getByRole('button', { name: /сохранить/i });
    expect(saveButton).toBeDisabled();
  });

  it('the destructive path is closed: failed hydration → attempted edit → no POST', async () => {
    // GET #1 (hydration) fails with a transient 500.
    apiMocks.get.mockRejectedValueOnce({ response: { status: 500 } });

    renderWithProviders(<EchoForm visitId={31} patientId={7} />);
    await waitFor(() => {
      expect(screen.getByText(/Не удалось загрузить сохранённые показатели ЭхоКГ/i)).toBeInTheDocument();
    });

    // Pre-fix, the form stayed editable: the doctor types EF on a blank
    // form and clicks Save. Post-fix, Save is disabled — the click is a
    // no-op. Either way, no POST may follow while the canonical state is
    // unknown.
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    });
    expect(apiMocks.post).not.toHaveBeenCalled();
  });

  it('Retry re-runs the canonical load; after success the stored values appear and Save re-enables', async () => {
    // GET #1 fails, GET #2 (retry) returns the stored echo subtree.
    apiMocks.get.mockRejectedValueOnce({ response: { status: 503 } });
    apiMocks.get.mockResolvedValueOnce({ data: emrWithEcho('58', 'Умеренная митральная регургитация', 4) });

    renderWithProviders(<EchoForm visitId={31} patientId={7} />);
    await waitFor(() => {
      expect(screen.getByText(/Не удалось загрузить сохранённые показатели ЭхоКГ/i)).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Повторить загрузку/i }));
    });

    // The retry hydrates the stored values and clears the failure.
    await screen.findByDisplayValue('58');
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /сохранить/i })).toBeEnabled();
    });
    expect(screen.getByDisplayValue('Умеренная митральная регургитация')).toBeInTheDocument();
    expect(screen.queryByText(/Не удалось загрузить сохранённые показатели ЭхоКГ/i)).toBeNull();
  });

  it('after a successful retry, a dirty save preserves the stored untouched fields', async () => {
    apiMocks.get.mockRejectedValueOnce({ response: { status: 500 } });
    apiMocks.get.mockResolvedValue({ data: emrWithEcho('58', 'Умеренная митральная регургитация', 4) });
    apiMocks.post.mockResolvedValueOnce({ status: 200, data: { data: { specialty_data: { echo: {} } } } });

    renderWithProviders(<EchoForm visitId={31} patientId={7} />);
    await waitFor(() => {
      expect(screen.getByText(/Не удалось загрузить сохранённые показатели ЭхоКГ/i)).toBeInTheDocument();
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Повторить загрузку/i }));
    });
    await screen.findByDisplayValue('58');

    // Doctor edits EF 58 → 45 and saves: untouched stored values ride along.
    fireEvent.change(screen.getByDisplayValue('58'), { target: { value: '45' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    });

    expect(apiMocks.post).toHaveBeenCalledTimes(1);
    const [url, payload] = apiMocks.post.mock.calls[0];
    expect(url).toBe('/v2/emr/31');
    expect(payload.data.specialty_data.echo.leftVentricle.ef).toBe('45');
    expect(payload.data.specialty_data.echo.leftVentricle.edd).toBe('5.0');
    expect(payload.data.specialty_data.echo.conclusion).toBe('Умеренная митральная регургитация');
  });
});
