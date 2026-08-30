/**
 * QueueTable sticky-header wiring contract tests (PR-UI-12-4).
 *
 * Plan reference: `docs/UI_REMEDIATION_PLAN.md` §PR-UI-12 item 4 —
 * "Все таблицы — sticky header при скролле" (Queue surface). The Queue surface
 * renders QueueTable (canonical DataTable since 09c-2); this file locks the
 * sticky-header wiring so the queue table keeps a visible header while its
 * bounded viewport scrolls.
 *
 * The wiring contract has two halves:
 *   1. the rendered `.mac-table-scroll-wrapper` viewport is bounded
 *      (overflow-y auto + max-height) and the header row is sticky —
 *      render-level assertions (ThemeProvider required by the macos Icon);
 *   2. QueueTable passes `stickyHeader` + `maxHeight` to the canonical
 *      DataTable by NAME — source-level assertion (the repo's established
 *      source-contract pattern, e.g. QueueManager.contract.test.tsx), so a
 *      future refactor cannot silently drop the flags while the DOM keeps
 *      accidentally passing via some other mechanism.
 */

import React from 'react';
import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

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

describe('QueueTable — sticky header wiring (PR-UI-12-4)', () => {
  it('queue table viewport is bounded and the header row is sticky', () => {
    const { container } = render(
      <ThemeProvider>
        <QueueTable queueData={makeQueueData(12)} effectiveDoctor={doctor} loading={false} t={{}} />
      </ThemeProvider>
    );

    // 12 entries exceed the 480px viewport bound (~9 rows) → the wrapper
    // carries the bounded-viewport styles the sticky header sticks against.
    const wrapper = container.querySelector('.mac-table-scroll-wrapper') as HTMLElement;
    expect(wrapper).not.toBeNull();
    expect(wrapper.style.overflowY).toBe('auto');
    expect(wrapper.style.maxHeight).toBe('480px');

    // Header cells are sticky against that viewport.
    const headerTh = screen.getByText('Пациент').closest('th') as HTMLElement;
    expect(headerTh.style.position).toBe('sticky');
    expect(headerTh.style.top).toBe('0px');
  });

  it('queue table that fits the bound renders with no internal scrollbar geometry change', () => {
    // 3 entries fit inside 480px — the viewport styles are still applied
    // (they are inert without overflow: no scrollbar, pixel-identical table).
    const { container } = render(
      <ThemeProvider>
        <QueueTable queueData={makeQueueData(3)} effectiveDoctor={doctor} loading={false} t={{}} />
      </ThemeProvider>
    );

    const wrapper = container.querySelector('.mac-table-scroll-wrapper') as HTMLElement;
    expect(wrapper).not.toBeNull();
    expect(wrapper.style.maxHeight).toBe('480px');
    // All 3 queue rows render — the bound does not virtualize or truncate.
    expect(screen.getByText('Patient 1')).toBeInTheDocument();
    expect(screen.getByText('Patient 3')).toBeInTheDocument();
  });

  it('source contract: QueueTable passes stickyHeader + maxHeight to the canonical DataTable', () => {
    const sourcePath = resolve(dirname(fileURLToPath(import.meta.url)), '../QueueTable.tsx');
    const source = readFileSync(sourcePath, 'utf8');

    // The sticky-header flags are wired on the DataTable invocation.
    expect(source).toMatch(/<DataTable[\s\S]*?stickyHeader\s*\n\s*maxHeight=\{QUEUE_TABLE_VIEWPORT_MAX_HEIGHT\}/);
    // The viewport bound is a named, documented constant — not a magic number
    // inline in JSX (per the PR-UI-12-4 "no hardcoded sticky geometry" rule;
    // sticky OFFSETS are measured by the kit, the bound is a layout param).
    expect(source).toMatch(/const QUEUE_TABLE_VIEWPORT_MAX_HEIGHT = 480;/);
  });
});
