/**
 * RETRO-3947-01 (consolidated post-merge review of PR 3947, dossier PR 3958) —
 * fail-first.
 *
 * The round-22 fail-closed patch (RETRO-3941-02) blocks Save after a failed
 * canonical hydration, but leaves the inputs editable. A doctor who types
 * measurements into that failed form and then presses «Повторить загрузку»
 * loses everything typed: the retry effect resets dirtyRef at start, a
 * successful retry unconditionally overwrites the form with the stored
 * subtree (deepMerge(DEFAULT_ECHO_DATA, storedEcho)), and even a FAILED
 * retry resets the form to DEFAULT_ECHO_DATA. Both paths silently destroy
 * the unsaved clinical draft.
 *
 * Contract after the fix (no data loss, server authority retained):
 *  - edits typed while the canonical EMR state is unknown (hydration
 *    failed or a retry GET in flight) are tracked as a local draft;
 *  - a successful retry hydrates the stored values and overlays ONLY the
 *    draft's touched fields on top; the form stays dirty and says so;
 *  - a failed retry keeps the draft AND the fail-closed state of
 *    RETRO-3941-02 (Save stays blocked, failure stays visible);
 *  - with no draft, retry-success keeps the round-22 contract exactly
 *    (stored values shown, pristine save is a no-change no-op).
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

const STORED_CONCLUSION = 'Умеренная митральная регургитация';

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

/** The EF input on a blank/unhydrated form is addressable by its ru placeholder. */
const efInput = () => screen.getByPlaceholderText('Норма: 55-75%');

beforeEach(() => {
  apiMocks.get.mockReset();
  apiMocks.post.mockReset();
});

describe('RETRO-3947-01: a typed draft survives the Echo Retry', () => {
  it('a successful Retry overlays the typed draft on the stored values (no silent loss, dirty kept)', async () => {
    // GET #1 (hydration) fails with a transient 500.
    apiMocks.get.mockRejectedValueOnce({ response: { status: 500 } });
    // GET #2 (retry) returns the stored echo subtree with EF=55.
    apiMocks.get.mockResolvedValueOnce({ data: emrWithEcho('55', STORED_CONCLUSION, 4) });

    renderWithProviders(<EchoForm visitId={31} patientId={7} />);
    await waitFor(() => {
      expect(screen.getByText(/Не удалось загрузить сохранённые показатели ЭхоКГ/i)).toBeInTheDocument();
    });

    // The doctor types EF=45 into the failed form (inputs stay editable).
    fireEvent.change(efInput(), { target: { value: '45' } });
    expect(efInput()).toHaveValue('45');

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Повторить загрузку/i }));
    });

    // RED on pre-fix source: the form showed the stored EF=55 instead,
    // silently discarding the typed 45.
    await waitFor(() => {
      expect(efInput()).toHaveValue('45');
    });
    // The canonical values the doctor did NOT touch are hydrated too.
    expect(screen.getByDisplayValue('5.0')).toBeInTheDocument();
    expect(screen.getByDisplayValue(STORED_CONCLUSION)).toBeInTheDocument();
    // The failure is cleared and the honest "draft preserved, still
    // unsaved" notice is shown instead of a bare success.
    expect(screen.queryByText(/Не удалось загрузить сохранённые показатели ЭхоКГ/i)).toBeNull();
    await waitFor(() => {
      expect(screen.getByText(/ещё не записаны/i)).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /сохранить/i })).toBeEnabled();
    });

    // Saving persists the doctor's 45 AND the untouched stored fields.
    apiMocks.get.mockResolvedValueOnce({ data: emrWithEcho('55', STORED_CONCLUSION, 4) });
    apiMocks.post.mockResolvedValueOnce({ status: 200, data: { data: { specialty_data: { echo: {} } } } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    });
    expect(apiMocks.post).toHaveBeenCalledTimes(1);
    const [url, payload] = apiMocks.post.mock.calls[0];
    expect(url).toBe('/v2/emr/31');
    expect(payload.data.specialty_data.echo.leftVentricle.ef).toBe('45');
    expect(payload.data.specialty_data.echo.leftVentricle.edd).toBe('5.0');
    expect(payload.data.specialty_data.echo.conclusion).toBe(STORED_CONCLUSION);
  });

  it('a FAILED Retry keeps the typed draft and the fail-closed state (no reset to blank)', async () => {
    apiMocks.get.mockRejectedValueOnce({ response: { status: 500 } });
    apiMocks.get.mockRejectedValueOnce({ response: { status: 503 } });

    renderWithProviders(<EchoForm visitId={31} patientId={7} />);
    await waitFor(() => {
      expect(screen.getByText(/Не удалось загрузить сохранённые показатели ЭхоКГ/i)).toBeInTheDocument();
    });

    fireEvent.change(efInput(), { target: { value: '45' } });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Повторить загрузку/i }));
    });

    // RED on pre-fix source: the catch reset the form to DEFAULT_ECHO_DATA,
    // destroying the typed 45. The draft must survive a failed retry too.
    await waitFor(() => {
      expect(screen.getByText(/Не удалось загрузить сохранённые показатели ЭхоКГ/i)).toBeInTheDocument();
    });
    expect(efInput()).toHaveValue('45');

    // RETRO-3941-02 contract unchanged: Save stays blocked while the
    // canonical state is unknown, so no destructive POST can leave.
    const saveButton = screen.getByRole('button', { name: /сохранить/i });
    expect(saveButton).toBeDisabled();
    await act(async () => {
      fireEvent.click(saveButton);
    });
    expect(apiMocks.post).not.toHaveBeenCalled();
  });

  it('edits typed while the retry GET is still in flight are preserved too', async () => {
    apiMocks.get.mockRejectedValueOnce({ response: { status: 500 } });
    let resolveRetry!: (value: { data: unknown }) => void;
    apiMocks.get.mockImplementationOnce(
      () => new Promise((resolve) => { resolveRetry = resolve; })
    );

    renderWithProviders(<EchoForm visitId={31} patientId={7} />);
    await waitFor(() => {
      expect(screen.getByText(/Не удалось загрузить сохранённые показатели ЭхоКГ/i)).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Повторить загрузку/i }));
    });

    // The doctor keeps typing while the retry request is pending.
    fireEvent.change(efInput(), { target: { value: '45' } });
    expect(efInput()).toHaveValue('45');

    // The retry now resolves with the stored EF=55.
    await act(async () => {
      resolveRetry({ data: emrWithEcho('55', STORED_CONCLUSION, 4) });
    });

    // RED on pre-fix source: the success handler overwrote the in-flight
    // edit with the stored 55.
    await waitFor(() => {
      expect(efInput()).toHaveValue('45');
    });
    expect(screen.getByDisplayValue('5.0')).toBeInTheDocument();
    expect(screen.getByDisplayValue(STORED_CONCLUSION)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /сохранить/i })).toBeEnabled();
    });
  });

  it('control: with no draft typed, Retry success keeps the round-22 contract (stored values, pristine no-change save)', async () => {
    apiMocks.get.mockRejectedValueOnce({ response: { status: 500 } });
    apiMocks.get.mockResolvedValueOnce({ data: emrWithEcho('58', STORED_CONCLUSION, 4) });

    renderWithProviders(<EchoForm visitId={31} patientId={7} />);
    await waitFor(() => {
      expect(screen.getByText(/Не удалось загрузить сохранённые показатели ЭхоКГ/i)).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Повторить загрузку/i }));
    });

    await screen.findByDisplayValue('58');
    expect(screen.getByDisplayValue(STORED_CONCLUSION)).toBeInTheDocument();
    // No draft notice for a pristine retry.
    expect(screen.queryByText(/ещё не записаны/i)).toBeNull();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /сохранить/i })).toBeEnabled();
    });

    // Pristine form + existing echo → Save is an honest no-change no-op.
    apiMocks.get.mockResolvedValueOnce({ data: emrWithEcho('58', STORED_CONCLUSION, 4) });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    });
    expect(apiMocks.post).not.toHaveBeenCalled();
    expect(screen.getByText(/не менялись/i)).toBeInTheDocument();
  });
});
