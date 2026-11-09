/**
 * RETRO-3941-01 (consolidated post-merge review of #3941, PR #3944) —
 * fail-first, component level.
 *
 * On the merged round-20 source ManualEcgForm kept its local useState(form)
 * content when the parent swapped the patientId/visitId props without
 * unmounting the form (the panel renders it outside the ECG tab and did not
 * close it on selection change): typed ECG measurements of patient A stayed
 * editable under patient B's identity props, and clicking Save POSTed A's
 * values under B's patient_id — clinical cross-patient misattribution.
 *
 * Contract after the fix (defense in depth; the panel additionally keys the
 * mount by canonical patient+visit and closes the form on owner change):
 *  - an identity prop change resets the local form: A's typed content never
 *    survives into B's context;
 *  - a submit whose identity changed while the request was in flight does
 *    not report success for the CURRENT patient (the write itself keeps the
 *    submit-time identity it was POSTed under).
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

describe('RETRO-3941-01: identity switch resets the typed content', () => {
  it('clears patient A measurements when the props switch to patient B', async () => {
    const { rerender } = render(
      <ManualEcgForm patientId={101} visitId={201} onCancel={vi.fn()} onSaved={vi.fn()} />,
    );

    // Doctor types A's ECG measurements.
    fireEvent.change(screen.getByLabelText('ЧСС'), { target: { value: '75' } });
    fireEvent.change(screen.getByLabelText('Ритм'), { target: { value: 'синусовый' } });
    fireEvent.change(screen.getByLabelText('Заключение'), { target: { value: 'Пациент А: патологии нет' } });
    // ЧСС is a number input: the DOM reports its value as a number.
    expect(screen.getByLabelText('ЧСС')).toHaveValue(75);

    // The parent swaps the identity props without unmounting the form.
    rerender(
      <ManualEcgForm patientId={202} visitId={302} onCancel={vi.fn()} onSaved={vi.fn()} />,
    );

    // A's typed content must not survive into B's form. (An empty
    // <input type="number"> reports its value as null.)
    await waitFor(() => {
      expect(screen.getByLabelText('ЧСС')).toHaveValue(null);
    });
    expect(screen.getByLabelText('Ритм')).toHaveValue('');
    expect(screen.getByLabelText('Заключение')).toHaveValue('');

    // And an immediate submit under B carries no A content: the empty
    // clinical set guard blocks the POST entirely.
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Сохранить запись ЭКГ/i }));
    });
    expect(apiPost).not.toHaveBeenCalled();
  });

  it('a submit whose identity changed mid-flight does not claim success for the new patient', async () => {
    const gate = deferred<{ status: number; data: { id: number } }>();
    apiPost.mockImplementation(() => gate.promise);

    const { rerender } = render(
      <ManualEcgForm patientId={101} visitId={201} onCancel={vi.fn()} onSaved={vi.fn()} />,
    );

    fireEvent.change(screen.getByLabelText('ЧСС'), { target: { value: '75' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Сохранить запись ЭКГ/i }));
    });

    // The POST for A (patient_id 101) is in flight when the selection
    // switches to B. The write keeps A's identity — that is correct — but
    // the UI must not report "ЭКГ добавлена" for B's context.
    rerender(
      <ManualEcgForm patientId={202} visitId={302} onCancel={vi.fn()} onSaved={vi.fn()} />,
    );

    await act(async () => {
      gate.resolve({ status: 201, data: { id: 99 } });
      await Promise.resolve();
    });

    // The write went out under the submit-time identity (A).
    expect(apiPost).toHaveBeenCalledTimes(1);
    expect(apiPost.mock.calls[0][1].patient_id).toBe(101);
    // No success toast / onSaved for the NEW patient's context.
    expect(notifyMocks.success).not.toHaveBeenCalled();
  });
});
