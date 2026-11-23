/**
 * ManualEcgForm — CARDIO-FE-001 (audit 3886 round 20).
 *
 * Red-first: on pre-fix source the "Добавить ЭКГ" flow reused
 * <BloodTestsTab showFormOpen />, so this component did not exist — the
 * panel rendered blood-test inputs and POSTed null ECG measurements under
 * the unrelated blood-test `test_date`.
 *
 * Contract:
 *  - the form renders ECG inputs (date, HR, PR, QRS, QT, rhythm, axis,
 *    interpretation) and NO blood-test inputs;
 *  - submit POSTs /cardio/ecg with the entered measurements under the
 *    backend CardioECGRecordCreate DTO keys and source: 'manual';
 *  - a missing date, a missing patient or a fully empty clinical set
 *    never fires the POST;
 *  - the submit button is disabled while the request is in flight.
 */
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, beforeEach, vi } from 'vitest';

const apiPost = vi.fn();
const notifyMocks = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  api: { post: (...args: unknown[]) => apiPost(...args) },
}));

vi.mock('../../../services/notify', () => ({
  default: notifyMocks,
}));

vi.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({
    theme: 'light',
    isDark: false,
    getColor: () => '#111827',
    getSpacing: (size: string) => (size === 'sm' ? '4px' : '8px'),
    getFontSize: () => '14px',
  }),
}));

import ManualEcgForm from '../ManualEcgForm';

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  apiPost.mockReset();
  Object.values(notifyMocks).forEach((m) => m.mockReset());
});

describe('ManualEcgForm — CARDIO-FE-001: dedicated ECG entry form', () => {
  it('renders ECG measurement inputs and no blood-test inputs', () => {
    render(<ManualEcgForm patientId={7} visitId={11} onCancel={vi.fn()} />);

    // ECG fields present (labels from the shared cardio_ecg_* locale keys).
    expect(screen.getByLabelText('Дата ЭКГ')).toBeInTheDocument();
    expect(screen.getByLabelText('ЧСС')).toBeInTheDocument();
    expect(screen.getByLabelText('Интервал PR')).toBeInTheDocument();
    expect(screen.getByLabelText('Интервал QRS')).toBeInTheDocument();
    expect(screen.getByLabelText('Интервал QT')).toBeInTheDocument();
    expect(screen.getByLabelText('Ритм')).toBeInTheDocument();
    expect(screen.getByLabelText('Электрическая ось сердца')).toBeInTheDocument();
    expect(screen.getByLabelText('Заключение')).toBeInTheDocument();

    // Blood-test fields must NOT appear in the ECG form.
    expect(screen.queryByLabelText(/холестерин/i)).toBeNull();
    expect(screen.queryByLabelText(/ЛПНП|LDL/i)).toBeNull();
    expect(screen.queryByLabelText(/триглицерид/i)).toBeNull();
    expect(screen.queryByLabelText(/глюкоз/i)).toBeNull();
    expect(screen.queryByLabelText(/тропонин/i)).toBeNull();
  });

  it('submits the entered measurements under the backend ECG DTO keys', async () => {
    apiPost.mockResolvedValueOnce({ status: 201, data: { id: 99 } });
    const onSaved = vi.fn();
    render(<ManualEcgForm patientId={7} visitId={11} onCancel={vi.fn()} onSaved={onSaved} />);

    fireEvent.change(screen.getByLabelText('ЧСС'), { target: { value: '75' } });
    fireEvent.change(screen.getByLabelText('Интервал PR'), { target: { value: '160' } });
    fireEvent.change(screen.getByLabelText('Интервал QRS'), { target: { value: '90' } });
    fireEvent.change(screen.getByLabelText('Интервал QT'), { target: { value: '400' } });
    fireEvent.change(screen.getByLabelText('Ритм'), { target: { value: 'синусовый' } });
    fireEvent.change(screen.getByLabelText('Электрическая ось сердца'), { target: { value: '+40' } });
    fireEvent.change(screen.getByLabelText('Заключение'), { target: { value: 'Без патологии' } });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Сохранить запись ЭКГ/i }));
    });

    expect(apiPost).toHaveBeenCalledTimes(1);
    const [url, payload] = apiPost.mock.calls[0];
    expect(url).toBe('/cardio/ecg');
    expect(payload).toMatchObject({
      patient_id: 7,
      visit_id: 11,
      file_id: null,
      heart_rate: 75,
      pr_interval: 160,
      qrs_duration: 90,
      qt_interval: 400,
      rhythm: 'синусовый',
      axis: '+40',
      interpretation: 'Без патологии',
      source: 'manual',
    });
    // Date is required by the backend DTO (ecg_date, not test_date).
    expect(typeof payload.ecg_date).toBe('string');
    expect(payload.ecg_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    // parameters carries the ECG form values — not blood-test data.
    expect(payload.parameters).toMatchObject({ heart_rate: 75, entered_manually: true });
    expect(payload.parameters.cholesterol_total).toBeUndefined();

    await waitFor(() => {
      expect(notifyMocks.success).toHaveBeenCalled();
    });
    expect(onSaved).toHaveBeenCalledTimes(1);
  });

  it('never POSTs a fully empty clinical set (no silent empty ECG records)', async () => {
    render(<ManualEcgForm patientId={7} visitId={11} onCancel={vi.fn()} />);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Сохранить запись ЭКГ/i }));
    });

    expect(apiPost).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(/хотя бы один параметр ЭКГ/i);
  });

  it('never POSTs without a selected patient', async () => {
    render(<ManualEcgForm patientId={null} visitId={null} onCancel={vi.fn()} />);

    fireEvent.change(screen.getByLabelText('ЧСС'), { target: { value: '75' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Сохранить запись ЭКГ/i }));
    });

    expect(apiPost).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(/выберите пациента/i);
  });

  it('blocks duplicate submissions while the request is in flight', async () => {
    const gate = deferred<{ status: number }>();
    apiPost.mockImplementation(() => gate.promise);
    render(<ManualEcgForm patientId={7} visitId={11} onCancel={vi.fn()} />);

    fireEvent.change(screen.getByLabelText('ЧСС'), { target: { value: '75' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Сохранить запись ЭКГ/i }));
    });

    // While the first request is pending the button is disabled.
    expect(screen.getByRole('button', { name: /Сохранение…|Сохранить запись ЭКГ/i })).toBeDisabled();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Сохранение…|Сохранить запись ЭКГ/i }));
    });
    await act(async () => {
      gate.resolve({ status: 201 });
      await sleep(0);
    });

    expect(apiPost).toHaveBeenCalledTimes(1);
  });

  it('shows the failure toast and keeps the form open on a rejected save', async () => {
    apiPost.mockRejectedValueOnce(new Error('HTTP 500'));
    const onSaved = vi.fn();
    render(<ManualEcgForm patientId={7} visitId={11} onCancel={vi.fn()} onSaved={onSaved} />);

    fireEvent.change(screen.getByLabelText('ЧСС'), { target: { value: '75' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Сохранить запись ЭКГ/i }));
    });
    await waitFor(() => {
      expect(notifyMocks.error).toHaveBeenCalled();
    });
    expect(onSaved).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /Сохранить запись ЭКГ/i })).toBeEnabled();
  });
});
