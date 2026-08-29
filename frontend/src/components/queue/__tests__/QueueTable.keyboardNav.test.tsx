/**
 * QueueTable keyboard-navigation contract tests (PR-UI-12-2).
 *
 * Plan reference: `docs/UI_REMEDIATION_PLAN.md` §PR-UI-12 item 2 —
 * "QueueTable — keyboard nav". Supersedes the plan's original "Enter для
 * вызова пациента" wording per the repo invariant in
 * QueueManager.contract.test.tsx ("call-next is a backend-owned command,
 * not a row command"): rows expose ROVING FOCUS only (ArrowUp/ArrowDown/
 * Home/End), no row-level call actions.
 */

import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import QueueTable from '../QueueTable';

const makeQueueData = (count: number) => ({
  is_open: true,
  entries: Array.from({ length: count }, (_, i) => ({
    id: `q${i + 1}`,
    patient_name: `Patient ${i + 1}`,
    patient_phone: `+7 700 000 00 0${i + 1}`,
    queue_number: i + 1,
    queue_time: `2026-08-29T09:0${i}:00Z`,
    status: i === 0 ? 'called' : 'waiting',
    source: i % 2 === 0 ? 'online' : 'desk'
  }))
});

const doctor = { id: 'd1', full_name: 'Dr. Test', specialty: 'Cardiology' };

const getRowByPatient = (name: string): HTMLTableRowElement =>
  screen.getByText(name).closest('tr') as HTMLTableRowElement;

describe('QueueTable — keyboard navigation (PR-UI-12-2)', () => {
  it('queue rows carry a roving tabindex (active row 0, others -1)', () => {
    render(
      <ThemeProvider>
        <QueueTable queueData={makeQueueData(3)} effectiveDoctor={doctor} loading={false} t={{}} />
      </ThemeProvider>
    );

    expect(getRowByPatient('Patient 1')).toHaveAttribute('tabIndex', '0');
    expect(getRowByPatient('Patient 2')).toHaveAttribute('tabIndex', '-1');
    expect(getRowByPatient('Patient 3')).toHaveAttribute('tabIndex', '-1');
    // Focus-targeting attribute present for the roving implementation.
    expect(getRowByPatient('Patient 1')).toHaveAttribute('data-row-index', '0');
  });

  it('ArrowDown moves focus to the next queue row; ArrowUp clamps at the first', async () => {
    render(
      <ThemeProvider>
        <QueueTable queueData={makeQueueData(3)} effectiveDoctor={doctor} loading={false} t={{}} />
      </ThemeProvider>
    );

    const first = getRowByPatient('Patient 1');
    first.focus();
    fireEvent.keyDown(first, { key: 'ArrowDown' });
    await waitFor(() => expect(getRowByPatient('Patient 2')).toHaveFocus());
    expect(getRowByPatient('Patient 1')).toHaveAttribute('tabIndex', '-1');
    expect(getRowByPatient('Patient 2')).toHaveAttribute('tabIndex', '0');

    // Clamped at the first row — no navigation above the queue head.
    fireEvent.keyDown(getRowByPatient('Patient 2'), { key: 'ArrowUp' });
    await waitFor(() => expect(getRowByPatient('Patient 1')).toHaveFocus());
    expect(getRowByPatient('Patient 1')).toHaveAttribute('tabIndex', '0');
    fireEvent.keyDown(getRowByPatient('Patient 1'), { key: 'ArrowUp' });
    expect(getRowByPatient('Patient 1')).toHaveAttribute('tabIndex', '0');
  });

  it('Enter/Space on a row performs NO action (call-next stays a manager command)', () => {
    // No onRowClick is wired and no row-level call API exists — pressing
    // Enter on a focused row must not mutate anything (the contract test
    // forbids row commands; the manager's call-next button remains the only
    // calling path).
    render(
      <ThemeProvider>
        <QueueTable queueData={makeQueueData(2)} effectiveDoctor={doctor} loading={false} t={{}} />
      </ThemeProvider>
    );

    const first = getRowByPatient('Patient 1');
    first.focus();
    expect(() => {
      fireEvent.keyDown(first, { key: 'Enter' });
      fireEvent.keyDown(first, { key: ' ' });
    }).not.toThrow();
    // Row still focused — Enter did not activate a row action.
    expect(first).toHaveFocus();
  });

  it('early-return states (no doctor / loading / empty) render no keyboard table', () => {
    const { rerender } = render(
      <ThemeProvider>
        <QueueTable queueData={null} effectiveDoctor={null} loading={false} t={{}} />
      </ThemeProvider>
    );
    expect(screen.getByText('Выберите специалиста')).toBeInTheDocument();

    rerender(
      <ThemeProvider>
        <QueueTable queueData={null} effectiveDoctor={doctor} loading={true} t={{}} />
      </ThemeProvider>
    );
    expect(screen.getByText('Загрузка очереди...')).toBeInTheDocument();

    rerender(
      <ThemeProvider>
        <QueueTable queueData={{ is_open: true, entries: [] }} effectiveDoctor={doctor} loading={false} t={{}} />
      </ThemeProvider>
    );
    expect(screen.getByText('Очередь пуста')).toBeInTheDocument();
  });

  it('does not violate the queue command contract (source-level, mirrors QueueManager.contract.test.tsx)', () => {
    const fs = require('node:fs') as typeof import('node:fs');
    const path = require('node:path') as typeof import('node:path');
    const src = fs.readFileSync(
      path.join(process.cwd(), 'src/components/queue/QueueTable.tsx'),
      'utf-8'
    );
    // The exact invariants the machine-checked contract asserts.
    expect(src).not.toContain('Button');
    expect(src).not.toContain('onCallPatient(entry)');
    expect(src).not.toContain('entry.status === \'waiting\' && (');
    // Keyboard navigation is wired through the canonical DataTable flag only.
    expect(src).toContain('keyboardNavigation');
  });
});
