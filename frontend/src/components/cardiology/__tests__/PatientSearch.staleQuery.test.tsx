/**
 * CARDSEARCH-FE-001 (audit 3886 round 20): search results for query A must
 * not remain clickable under a new query B.
 *
 * Red-first: on pre-fix source the results list was neither cleared nor
 * invalidated when a new valid query replaced the old one — A's rows stayed
 * rendered (and clickable) under the "results for B" label through the whole
 * 300-ms debounce, and an A response finishing during B's debounce was
 * still accepted.
 */
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, beforeEach, vi } from 'vitest';

const apiClientGet = vi.fn();

vi.mock('../../../api/client', () => ({
  apiClient: {
    get: (...args: unknown[]) => apiClientGet(...args),
  },
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

import PatientSearch from '../PatientSearch';

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

const patientA = { id: 1, full_name: 'Алиев Али Алиевич', phone: '+998901112233', birth_date: '1980-01-01' };
const patientB = { id: 2, full_name: 'Беков Бек Бекович', phone: '+998903334455', birth_date: '1975-02-02' };

beforeEach(() => {
  apiClientGet.mockReset();
});

describe('CARDSEARCH-FE-001: query A results are invalidated when query B is typed', () => {
  it('A rows stop rendering immediately after the input changes to B', async () => {
    apiClientGet.mockResolvedValueOnce({ data: [patientA] });
    render(<PatientSearch onPick={vi.fn()} />);

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Ал' } });
    await waitFor(() => {
      expect(screen.getByText('Алиев Али Алиевич')).toBeInTheDocument();
    });

    // Type the next query — the previous rows must disappear IMMEDIATELY
    // (during the debounce window), not stay clickable under B's label.
    fireEvent.change(input, { target: { value: 'Бе' } });

    expect(screen.queryByRole('button', { name: /Алиев Али Алиевич/ })).toBeNull();
    // The label already claims results for B — B's rows may be the only ones.
    expect(screen.getByText(/результаты для «Бе»|Бе/i)).toBeInTheDocument();
  });

  it('an A response that finishes after B was typed is dropped', async () => {
    const gateA = deferred<{ data: unknown[] }>();
    apiClientGet.mockImplementationOnce(() => gateA.promise);

    render(<PatientSearch onPick={vi.fn()} />);
    const input = screen.getByRole('textbox');

    // Query A fires and hangs.
    fireEvent.change(input, { target: { value: 'Ал' } });
    await sleep(350);
    expect(apiClientGet).toHaveBeenCalledTimes(1);

    // The doctor retypes B before A resolves.
    apiClientGet.mockResolvedValueOnce({ data: [patientB] });
    fireEvent.change(input, { target: { value: 'Бе' } });
    await sleep(400);

    // A's late response arrives now — it must be discarded.
    await act(async () => {
      gateA.resolve({ data: [patientA] });
      await Promise.resolve();
    });
    await sleep(50);

    expect(screen.getByText('Беков Бек Бекович')).toBeInTheDocument();
    expect(screen.queryByText('Алиев Али Алиевич')).toBeNull();
    expect(apiClientGet).toHaveBeenCalledTimes(2);
  });

  it('picking still works for the CURRENT query results', async () => {
    apiClientGet.mockResolvedValueOnce({ data: [patientB] });
    const onPick = vi.fn();
    render(<PatientSearch onPick={onPick} />);

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Бе' } });
    await waitFor(() => {
      expect(screen.getByText('Беков Бек Бекович')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Беков Бек Бекович/ }));
    expect(onPick).toHaveBeenCalledWith(
      expect.objectContaining({ id: 2, full_name: 'Беков Бек Бекович' }),
    );
  });
});
