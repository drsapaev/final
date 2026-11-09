/**
 * RETRO-3941-01 (post-merge review #3944) — ManualEcgForm owner identity.
 *
 * Red-first: on pre-fix source the form kept its local `form` state across a
 * patient/visit prop change (the panel mounted it without an identity key and
 * never closed it on a selection switch), so measurements typed for patient A
 * could be POSTed under patient B's id after the context switched.
 *
 * Contract (defense-in-depth component guard):
 *  - a submit is REFUSED when the patientId prop no longer matches the owner
 *    captured at mount (A → B switch without remount);
 *  - a submit is REFUSED when only the visitId changed;
 *  - the refused submit never fires POST /cardio/ecg and surfaces the
 *    context-changed validation message.
 */
import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
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

beforeEach(() => {
  apiPost.mockReset();
  Object.values(notifyMocks).forEach((m) => m.mockReset());
});

describe('RETRO-3941-01: ManualEcgForm refuses cross-patient submissions', () => {
  it('never POSTs A\u2019s measurements under B\u2019s patient id after a context switch', async () => {
    const { rerender } = render(<ManualEcgForm patientId={7} visitId={11} onCancel={vi.fn()} />);

    // Doctor types patient A's ECG measurements.
    fireEvent.change(screen.getByLabelText('ЧСС'), { target: { value: '75' } });
    fireEvent.change(screen.getByLabelText('Ритм'), { target: { value: 'синусовый' } });

    // The selection switches to patient B while the form stays mounted
    // (a parent that forgot the identity key).
    rerender(<ManualEcgForm patientId={8} visitId={22} onCancel={vi.fn()} />);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Сохранить запись ЭКГ/i }));
    });

    expect(apiPost).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(/изменились после открытия формы|другого пациента/i);
    expect(notifyMocks.success).not.toHaveBeenCalled();
  });

  it('never POSTs when only the visit changed (same patient, other encounter)', async () => {
    const { rerender } = render(<ManualEcgForm patientId={7} visitId={11} onCancel={vi.fn()} />);

    fireEvent.change(screen.getByLabelText('ЧСС'), { target: { value: '75' } });
    rerender(<ManualEcgForm patientId={7} visitId={99} onCancel={vi.fn()} />);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Сохранить запись ЭКГ/i }));
    });

    expect(apiPost).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(/изменились после открытия формы|другого пациента/i);
  });

  it('still submits when the owner context is unchanged', async () => {
    apiPost.mockResolvedValueOnce({ status: 201, data: { id: 99 } });
    render(<ManualEcgForm patientId={7} visitId={11} onCancel={vi.fn()} />);

    fireEvent.change(screen.getByLabelText('ЧСС'), { target: { value: '75' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Сохранить запись ЭКГ/i }));
    });

    expect(apiPost).toHaveBeenCalledTimes(1);
    const [url, payload] = apiPost.mock.calls[0];
    expect(url).toBe('/cardio/ecg');
    expect(payload.patient_id).toBe(7);
    expect(payload.visit_id).toBe(11);
  });
});
