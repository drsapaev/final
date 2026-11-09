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

describe('RETRO-3941-02: hydration of the canonical EMR fails closed', () => {
  it('a transient GET 500 blocks Save, surfaces the failure with a retry, and never POSTs', async () => {
    // GET#1 — unexpected server error (not the expected 404).
    apiMocks.get.mockRejectedValueOnce({ response: { status: 500 } });

    renderWithProviders(<EchoForm visitId={11} patientId={7} />);

    // Fail closed: the failure is visible…
    await waitFor(() => {
      expect(screen.getByTestId('echo-hydration-failure')).toBeInTheDocument();
    });
    // …and Save stays disabled while the stored echo state is unknown.
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /загружаем сохранённые/i })).toBeDisabled();
    });

    // Even an attempted click on the disabled button must not POST.
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /загружаем сохранённые/i }));
    });
    expect(apiMocks.post).not.toHaveBeenCalled();

    // GET#2 — the retry succeeds and returns the full stored echo subtree.
    apiMocks.get.mockResolvedValueOnce({ data: emrWithEcho('58', 'Без патологии') });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /повторить загрузку/i }));
    });

    // Canonical values are hydrated…
    expect(await screen.findByDisplayValue('58')).toBeInTheDocument();
    expect(screen.getByDisplayValue('5.0')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Без патологии')).toBeInTheDocument();
    // …the failure cleared…
    await waitFor(() => {
      expect(screen.queryByTestId('echo-hydration-failure')).toBeNull();
    });
    // …Save is enabled again…
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /сохранить/i })).toBeEnabled();
    });
    // …and no destructive POST ever happened on the failure path.
    expect(apiMocks.post).not.toHaveBeenCalled();
  });

  it('the destructive overwrite path is dead: blank form + failed hydration + successful re-read never POSTs', async () => {
    // The pre-fix scenario from the audit: GET#1 500 blanks the form; the
    // doctor edits EF; a later Save re-reads the full stored EMR (GET#2 200)
    // and used to overwrite EDD/conclusion with blanks. Now Save is blocked
    // from the very start.
    apiMocks.get.mockRejectedValueOnce({ response: { status: 500 } });

    renderWithProviders(<EchoForm visitId={11} patientId={7} />);
    await waitFor(() => {
      expect(screen.getByTestId('echo-hydration-failure')).toBeInTheDocument();
    });

    // Any number of GET successes afterwards cannot resurrect a save:
    // the form only leaves the failed state through its own retry.
    apiMocks.get.mockResolvedValue({ data: emrWithEcho('58', 'Без патологии') });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /повторить загрузку/i }));
    });
    expect(await screen.findByDisplayValue('58')).toBeInTheDocument();

    // Pristine after a successful canonical retry → no-op save, no POST.
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    });
    expect(apiMocks.post).not.toHaveBeenCalled();
  });
});

describe('RETRO-3941-03: edits during an in-flight save are never reported as persisted', () => {
  it('disables every editor input while the save GET+POST is in flight', async () => {
    apiMocks.get.mockResolvedValue({ data: emrWithEcho('58', 'Без патологии') });
    const postGate = deferred<{ status: number; data?: unknown }>();
    apiMocks.post.mockImplementationOnce(() => postGate.promise);

    renderWithProviders(<EchoForm visitId={11} patientId={7} />);
    await screen.findByDisplayValue('58');

    fireEvent.change(screen.getByDisplayValue('58'), { target: { value: '45' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    });

    // While the save (GET re-read + POST) is pending, the editor inputs are
    // disabled: the latest displayed value cannot diverge from the submitted
    // snapshot.
    await waitFor(() => {
      expect(screen.getByDisplayValue('45')).toBeDisabled();
    });
    expect(screen.getByDisplayValue('Без патологии')).toBeDisabled();

    await act(async () => {
      postGate.resolve({ status: 200, data: { data: { specialty_data: { echo: {} } } } });
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(screen.getByDisplayValue('45')).toBeEnabled();
    });
  });

  it('an edit that lands mid-flight keeps the form dirty: honest info instead of success, follow-up save POSTs', async () => {
    apiMocks.get.mockResolvedValue({ data: emrWithEcho('58', 'Без патологии') });
    const postGate = deferred<{ status: number; data?: unknown }>();
    apiMocks.post.mockImplementationOnce(() => postGate.promise);

    renderWithProviders(<EchoForm visitId={11} patientId={7} />);
    await screen.findByDisplayValue('58');

    fireEvent.change(screen.getByDisplayValue('58'), { target: { value: '45' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    });

    // An edit sneaks past the disabled inputs (programmatic race/autofill):
    // the conclusion changes while the POST for the EF=45 snapshot flies.
    await act(async () => {
      fireEvent.change(screen.getByDisplayValue('Без патологии'), { target: { value: 'Новые данные' } });
    });

    await act(async () => {
      postGate.resolve({ status: 200, data: { data: { specialty_data: { echo: {} } } } });
      await Promise.resolve();
    });

    // The ACK proves only the EF=45 snapshot: the latest displayed value is
    // NOT treated as persisted — no success message, an honest follow-up
    // notice instead.
    await waitFor(() => {
      expect(screen.getByText(/ещё не сохранена|Сохранить» ещё раз/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/сохранены успешно/i)).toBeNull();

    // The follow-up save persists the newer value on top of the saved snapshot.
    apiMocks.post.mockResolvedValueOnce({ status: 200, data: { data: { specialty_data: { echo: {} } } } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    });
    expect(apiMocks.post).toHaveBeenCalledTimes(2);
    const [, payload] = apiMocks.post.mock.calls[1];
    expect(payload.data.specialty_data.echo.conclusion).toBe('Новые данные');
    expect(payload.data.specialty_data.echo.leftVentricle.ef).toBe('45');
  });
});
