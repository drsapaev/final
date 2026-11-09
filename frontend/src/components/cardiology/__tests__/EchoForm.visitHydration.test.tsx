/**
 * ECHO-FE-001 (audit 3886 round 20) — behavioral contract of the echo form
 * against the canonical EMR:
 *
 * Red-first: on pre-fix source the form hydrated ONLY from an `initialData`
 * prop that no caller passed, and Save unconditionally replaced
 * `specialty_data.echo` with the (blank) local state — an untouched Save
 * could wipe stored EF/EDD/conclusion with a fresh blank EMR revision, and
 * an in-flight hydration for visit A could populate visit B's form.
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

function getEmrArgs(visitId: number) {
  return apiMocks.get.mock.calls.find((call) => call[0] === `/v2/emr/${visitId}`);
}

beforeEach(() => {
  apiMocks.get.mockReset();
  apiMocks.post.mockReset();
});

describe('ECHO-FE-001: hydration from the canonical EMR', () => {
  it('prefills stored echo measurements when mounted without initialData', async () => {
    apiMocks.get.mockResolvedValueOnce({ data: emrWithEcho('58', 'Без патологии') });

    renderWithProviders(<EchoForm visitId={11} patientId={7} />);

    // Left ventricle section is expanded by default — EF input hydrated.
    const efInput = await screen.findByDisplayValue('58');
    expect(efInput).toBeInTheDocument();
    expect(screen.getByDisplayValue('5.0')).toBeInTheDocument(); // EDD
    expect(screen.getByDisplayValue('Без патологии')).toBeInTheDocument(); // conclusion
  });

  it('treats a GET 404 (no EMR yet) as an empty form, not an error', async () => {
    apiMocks.get.mockRejectedValueOnce({ response: { status: 404 } });

    renderWithProviders(<EchoForm visitId={12} patientId={7} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /сохранить/i })).toBeEnabled();
    });
    expect(screen.queryByDisplayValue('58')).toBeNull();
  });
});

describe('ECHO-FE-001: untouched Save never rewrites the stored echo subtree', () => {
  it('skips the POST for a pristine form when the EMR already has echo data', async () => {
    apiMocks.get.mockResolvedValue({ data: emrWithEcho('58', 'Без патологии') });

    renderWithProviders(<EchoForm visitId={11} patientId={7} />);
    await screen.findByDisplayValue('58');

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    });

    // The EMR was re-read at save time (fresh row_version)…
    expect(apiMocks.get).toHaveBeenCalled();
    // …but no POST may follow: nothing changed.
    expect(apiMocks.post).not.toHaveBeenCalled();
    // The no-op is surfaced honestly instead of a fake success toast.
    await waitFor(() => {
      expect(screen.getByText(/не менялись — сохранение не требуется/i)).toBeInTheDocument();
    });
  });

  it('POSTs a dirty save with the hydrated EMR row_version and preserved sections', async () => {
    apiMocks.get.mockResolvedValue({ data: emrWithEcho('58', 'Без патологии', 7) });
    apiMocks.post.mockResolvedValueOnce({ status: 200, data: { data: { specialty_data: { echo: {} } } } });

    renderWithProviders(<EchoForm visitId={11} patientId={7} />);
    await screen.findByDisplayValue('58');

    // The doctor edits EF 58 → 45.
    fireEvent.change(screen.getByDisplayValue('58'), { target: { value: '45' } });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    });

    expect(apiMocks.post).toHaveBeenCalledTimes(1);
    const [url, payload] = apiMocks.post.mock.calls[0];
    expect(url).toBe('/v2/emr/11');
    expect(payload.row_version).toBe(7);
    expect(payload.is_draft).toBe(true);
    expect(payload.data.specialty_data.echo.leftVentricle.ef).toBe('45');
    // Untouched hydrated values ride along unchanged.
    expect(payload.data.specialty_data.echo.leftVentricle.edd).toBe('5.0');
    expect(payload.data.specialty_data.echo.conclusion).toBe('Без патологии');

    await waitFor(() => {
      expect(screen.getByText(/сохранены/i)).toBeInTheDocument();
    });
  });

  it('disables Save while the hydration request is in flight', async () => {
    const gate = deferred<{ data: ReturnType<typeof emrWithEcho> }>();
    apiMocks.get.mockImplementationOnce(() => gate.promise);

    renderWithProviders(<EchoForm visitId={11} patientId={7} />);

    // Hydrating: the button is disabled (a blank unhydrated form must not
    // be able to overwrite the stored echo subtree).
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /загружаем сохранённые/i })).toBeDisabled();
    });

    await act(async () => {
      gate.resolve({ data: emrWithEcho('58', 'Без патологии') });
    });
    await screen.findByDisplayValue('58');
    expect(screen.getByRole('button', { name: /сохранить/i })).toBeEnabled();
  });
});

describe('ECHO-FE-001: visit switch isolation', () => {
  it('resets the form and drops a late hydration from the previous visit', async () => {
    // Visit A hydration hangs.
    const gateA = deferred<{ data: ReturnType<typeof emrWithEcho> }>();
    apiMocks.get.mockImplementationOnce(() => gateA.promise);

    const { rerender } = renderWithProviders(<EchoForm visitId={11} patientId={7} />);

    // Switch the SAME mounted form to visit B before A resolves.
    apiMocks.get.mockResolvedValueOnce({ data: emrWithEcho('33', 'Пациент Б', 2) });
    rerender(<EchoForm visitId={22} patientId={8} />);

    await screen.findByDisplayValue('33');

    // A's late response arrives after B is already displayed.
    await act(async () => {
      gateA.resolve({ data: emrWithEcho('58', 'Пациент А', 9) });
      await Promise.resolve();
    });
    await act(async () => {
      await Promise.resolve();
    });

    // B's values stay; A's late values never appear.
    expect(screen.getByDisplayValue('33')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('58')).toBeNull();
    expect(screen.queryByDisplayValue('Пациент А')).toBeNull();

    // Both visits were requested through the canonical endpoint.
    expect(getEmrArgs(11)).toBeDefined();
    expect(getEmrArgs(22)).toBeDefined();
  });
});
