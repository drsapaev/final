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
    expect(payload.data.specialty_data.echo.measurement_metadata).not.toHaveProperty('definition_version');

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

describe('Echo save checks the loaded revision of the Echo section', () => {
  it('accepts a new EMR revision with unchanged Echo and retains its explicit definition and unknown fields', async () => {
    const original = emrWithEcho('58', 'Без патологии', 7);
    const originalEcho = {
      ...original.data.specialty_data.echo,
      measurement_metadata: { definition_version: 4, device_key: 'SYNTHETIC-legacy-device' },
      legacy_measurements: { other: 'SYNTHETIC-legacy-measurement' },
    };
    apiMocks.get.mockResolvedValueOnce({ data: {
      ...original,
      data: { specialty_data: { echo: originalEcho } },
    } });
    apiMocks.get.mockResolvedValueOnce({ data: {
      row_version: 8,
      data: {
        complaints: 'SYNTHETIC-updated-other-section',
        specialty_data: {
          echo: {
            legacy_measurements: originalEcho.legacy_measurements,
            conclusion: originalEcho.conclusion,
            measurement_metadata: originalEcho.measurement_metadata,
            leftVentricle: originalEcho.leftVentricle,
          },
          ecg: { conclusion: 'SYNTHETIC-new-ecg' },
        },
      },
    } });
    apiMocks.post.mockResolvedValueOnce({ status: 200 });
    renderWithProviders(<EchoForm visitId={11} patientId={7} />);
    await screen.findByDisplayValue('58');
    fireEvent.change(screen.getByRole('textbox', { name: 'ФВ' }), { target: { value: '45' } });
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Сохранить' })); });

    const [, payload] = apiMocks.post.mock.calls[0];
    expect(payload.row_version).toBe(8);
    expect(payload.data.complaints).toBe('SYNTHETIC-updated-other-section');
    expect(payload.data.specialty_data.ecg).toEqual({ conclusion: 'SYNTHETIC-new-ecg' });
    expect(payload.data.specialty_data.echo.leftVentricle.ef).toBe('45');
    expect(payload.data.specialty_data.echo.legacy_measurements).toEqual(originalEcho.legacy_measurements);
    expect(payload.data.specialty_data.echo.measurement_metadata).toMatchObject(originalEcho.measurement_metadata);
  });

  it('keeps unsaved fields and requires explicit recovery after another writer updates the Echo', async () => {
    const previous = emrWithEcho('58', 'SYNTHETIC-old-conclusion', 7);
    const changed = emrWithEcho('70', 'SYNTHETIC-new-conclusion', 8);
    apiMocks.get.mockResolvedValueOnce({ data: previous }).mockResolvedValue({ data: changed });
    renderWithProviders(<EchoForm visitId={11} patientId={7} />);
    await screen.findByDisplayValue('58');
    const ef = screen.getByRole('textbox', { name: 'ФВ' });
    const save = screen.getByRole('button', { name: 'Сохранить' });
    fireEvent.change(ef, { target: { value: '45' } });
    await act(async () => { fireEvent.click(save); });

    expect(apiMocks.post).not.toHaveBeenCalled();
    expect(ef).toHaveValue('45');
    expect(save).toBeDisabled();
    expect(screen.getByText(/Сохранённая версия ЭМК изменилась/i)).toBeVisible();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Загрузить актуальную версию и применить мои правки/i }));
    });
    expect(ef).toHaveValue('45');
    expect(screen.getByRole('textbox', { name: 'Заключение' })).toHaveValue('SYNTHETIC-new-conclusion');
    expect(screen.getByText(/ещё не записаны/i)).toBeVisible();
    expect(save).toBeEnabled();
    expect(apiMocks.post).not.toHaveBeenCalled();

    apiMocks.post.mockResolvedValueOnce({ status: 200 });
    await act(async () => { fireEvent.click(save); });
    expect(apiMocks.post).toHaveBeenCalledTimes(1);
    const [, payload] = apiMocks.post.mock.calls[0];
    expect(payload.row_version).toBe(8);
    expect(payload.data.specialty_data.echo.leftVentricle.ef).toBe('45');
    expect(payload.data.specialty_data.echo.conclusion).toBe('SYNTHETIC-new-conclusion');
  });

  it('preserves the local draft when the save loses a row-version race after the re-read', async () => {
    apiMocks.get.mockResolvedValue({ data: emrWithEcho('58', 'SYNTHETIC-original', 7) });
    apiMocks.post.mockRejectedValueOnce({ response: { status: 409 } });
    renderWithProviders(<EchoForm visitId={11} patientId={7} />);
    await screen.findByDisplayValue('58');
    const ef = screen.getByRole('textbox', { name: 'ФВ' });
    const save = screen.getByRole('button', { name: 'Сохранить' });
    fireEvent.change(ef, { target: { value: '45' } });
    await act(async () => { fireEvent.click(save); });

    expect(apiMocks.post).toHaveBeenCalledTimes(1);
    expect(ef).toHaveValue('45');
    expect(save).toBeDisabled();
    expect(screen.getByRole('button', { name: /Загрузить актуальную версию/i })).toBeVisible();
  });

  it('blocks a write when the EMR is finalized and exposes readonly comments and disclosure state', async () => {
    const stored = emrWithEcho('58', 'SYNTHETIC-original', 7);
    apiMocks.get.mockResolvedValueOnce({ data: stored });
    apiMocks.get.mockResolvedValueOnce({ data: { ...stored, status: 'signed', row_version: 8 } });
    renderWithProviders(<EchoForm visitId={11} patientId={7} />);
    await screen.findByDisplayValue('58');
    const comments = screen.getByRole('textbox', { name: 'Комментарии' });
    fireEvent.change(comments, { target: { value: 'SYNTHETIC-unsaved-draft' } });
    const save = screen.getByRole('button', { name: 'Сохранить' });
    await act(async () => { fireEvent.click(save); });

    expect(apiMocks.post).not.toHaveBeenCalled();
    expect(save).toBeDisabled();
    expect(comments).toHaveValue('SYNTHETIC-unsaved-draft');
    expect(comments).toHaveAttribute('readonly');
    expect(screen.getByText(/ЭМК закрыта для редактирования/i)).toBeVisible();
    const disclosure = screen.getByRole('button', { name: 'Правый желудочек' });
    expect(disclosure).toHaveAttribute('aria-expanded', 'false');
    fireEvent.keyDown(disclosure, { key: 'Enter' });
    expect(disclosure).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('textbox', { name: 'КДР ПЖ' })).toHaveAttribute('readonly');
    expect(screen.getByLabelText('Метод измерения фракции выброса')).toHaveAttribute('readonly');
    expect(screen.getByLabelText('Дата исследования')).toHaveAttribute('readonly');
  });
});

describe('Adult transthoracic echocardiography definition', () => {
  it('captures explicitly entered decimal values, measurement units, date and method in a fresh cardiology draft', async () => {
    const empty = { row_version: 3, data: { specialty: 'cardiology', specialty_data: { echo: {} } } };
    apiMocks.get.mockResolvedValue({ data: empty });
    apiMocks.post.mockResolvedValueOnce({ status: 200 });
    renderWithProviders(<EchoForm visitId={11} patientId={7} />);
    const save = await screen.findByRole('button', { name: 'Сохранить' });
    const ef = screen.getByRole('textbox', { name: 'Фракция выброса ЛЖ (%)' });
    expect(screen.queryByText('Ранее сохранённые измерения')).toBeNull();
    fireEvent.change(ef, { target: { value: '58,5' } });
    fireEvent.change(screen.getByRole('textbox', { name: 'Конечный диастолический объём ЛЖ (mL)' }), { target: { value: '114' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Метод определения ФВ ЛЖ' }), { target: { value: 'biplane_simpson_2d' } });
    fireEvent.change(screen.getByLabelText('Дата трансторакального исследования'), { target: { value: '2026-11-23' } });
    fireEvent.click(screen.getByText('Расширенные измерения'));
    fireEvent.change(screen.getByLabelText('TAPSE (M-режим) (cm)'), { target: { value: '2,15' } });

    await act(async () => { fireEvent.click(save); });
    expect(apiMocks.post).toHaveBeenCalledTimes(1);
    const [, payload] = apiMocks.post.mock.calls[0];
    expect(payload.row_version).toBe(3);
    expect(payload.data.specialty_data.echo).toEqual({
      adult_tte: {
        version: 2,
        measurements: {
          lvef: { value: 58.5, unit: '%' },
          lvedv: { value: 114, unit: 'mL' },
          tapse: { value: 2.15, unit: 'cm' },
        },
        ef_method: 'biplane_simpson_2d',
        measured_at: '2026-11-23',
        recorded_at: expect.any(String),
        source_visit_id: 11,
      },
    });
  });

  it('keeps prior measurements intact and authors a new one without guessing a method', async () => {
    const stored = emrWithEcho('58', 'SYNTHETIC-result', 7);
    const legacyEcho = {
      ...stored.data.specialty_data.echo,
      measurement_metadata: { definition_version: 1, ef_method: 'SYNTHETIC-method', measured_at: '2025-10-12' },
    };
    stored.data.specialty_data.echo = legacyEcho;
    apiMocks.get.mockResolvedValue({ data: stored });
    apiMocks.post.mockResolvedValueOnce({ status: 200 });
    renderWithProviders(<EchoForm visitId={11} patientId={7} />);
    const save = await screen.findByRole('button', { name: 'Сохранить' });
    expect(screen.getByRole('textbox', { name: 'ФВ' })).toHaveValue('58');
    const ef = screen.getByRole('textbox', { name: 'Фракция выброса ЛЖ (%)' });
    expect(ef).toHaveValue('');
    expect(screen.getByRole('combobox', { name: 'Метод определения ФВ ЛЖ' })).toHaveValue('');
    fireEvent.change(ef, { target: { value: '63' } });

    await act(async () => { fireEvent.click(save); });
    const [, payload] = apiMocks.post.mock.calls[0];
    expect(payload.data.specialty_data.echo).toEqual({
      ...legacyEcho,
      adult_tte: {
        version: 2,
        measurements: { lvef: { value: 63, unit: '%' } },
        recorded_at: expect.any(String),
        source_visit_id: 11,
      },
    });
  });

  it('never saves invalid input and clears only the selected structured fact', async () => {
    const adultTte = {
      version: 2,
      measurements: { lvef: { value: 63, unit: '%' }, lavi: { value: 36, unit: 'mL/m²' } },
      ef_method: 'visual_estimate',
    };
    const stored = { row_version: 7, data: { specialty_data: { echo: { adult_tte: adultTte } } } };
    apiMocks.get.mockResolvedValue({ data: stored });
    apiMocks.post.mockResolvedValueOnce({ status: 200 });
    renderWithProviders(<EchoForm visitId={11} patientId={7} />);
    const ef = await screen.findByDisplayValue('63');
    const save = screen.getByRole('button', { name: 'Сохранить' });
    fireEvent.change(ef, { target: { value: '63%' } });
    expect(ef).toHaveAttribute('aria-invalid', 'true');
    expect(save).toBeDisabled();
    expect(apiMocks.post).not.toHaveBeenCalled();

    fireEvent.change(ef, { target: { value: '' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Метод определения ФВ ЛЖ' }), { target: { value: '' } });
    await act(async () => { fireEvent.click(save); });
    const [, payload] = apiMocks.post.mock.calls[0];
    expect(payload.data.specialty_data.echo.adult_tte).toEqual({
      version: 2,
      measurements: { lavi: { value: 36, unit: 'mL/m²' } },
      recorded_at: expect.any(String),
      source_visit_id: 11,
    });
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
