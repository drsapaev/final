/**
 * EnhancedAppointmentsTable (EAT) decomposition source contract
 * (PR-UI-09e-2 — plan §PR-UI-09 AC2).
 *
 * Machine-checked acceptance guard, same pattern as the RegistrarPanel
 * (PR-UI-13-5) and CashierPanel (PR-UI-14-6) LOC/useState AC tests:
 * the orchestrator must stay ≤ 400 LOC, the public contract (default
 * export + AppointmentRow re-export) must be preserved for all 6
 * consumers, and the implementation must live in the extracted modules.
 */

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const readSrc = (rel: string) =>
  readFileSync(resolve(here, rel), 'utf8');

const source = readSrc('../EnhancedAppointmentsTable.tsx');

describe('EnhancedAppointmentsTable — PR-UI-09e-2 decomposition AC guard', () => {
  it('plan §PR-UI-09 AC2: the orchestrator is ≤ 400 LOC (machine-checked)', () => {
    const loc = source.split('\n').filter((l) => l.trim() !== '').length;
    // Physical line count including blanks is the metric used by the plan
    // (2 026 → target ≤ 400); count both ways so either reading passes only
    // when the file is genuinely small.
    const physical = source.split('\n').length;
    expect(loc).toBeLessThanOrEqual(400);
    expect(physical).toBeLessThanOrEqual(400);
  });

  it('public contract: default export + AppointmentRow re-export stay on the orchestrator', () => {
    expect(source).toContain('export default EnhancedAppointmentsTable;');
    expect(source).toMatch(/export type \{ AppointmentRow \}/);
  });

  it('implementation delegated to the extracted modules (wiring present)', () => {
    expect(source).toContain("import { useAppointmentsTableState } from './useAppointmentsTableState'");
    expect(source).toMatch(/import \{ useAppointmentsTableRenderers, buildAppointmentsTableColumns \} from '\.\/appointmentsTableColumns'/);
    expect(source).toContain('useAppointmentsTableState({ data, externalSelectedRows, onRowSelect })');
    expect(source).toContain('useAppointmentsTableRenderers({ t, services, data })');
    expect(source).toMatch(/buildAppointmentsTableColumns\(\{/);
  });

  it('renderer bodies and column config no longer live in the orchestrator', () => {
    expect(source).not.toContain('const renderStatus = useCallback');
    expect(source).not.toContain('const renderQueueNumbers = useCallback');
    expect(source).not.toContain('const renderServices = useCallback');
    expect(source).not.toContain('columns.push({');
    expect(source).not.toContain('getBackendActionAvailability');
  });

  it('sticky-header wiring (PR-UI-12-4) survived the decomposition verbatim', () => {
    expect(source).toMatch(/stickyHeader\s*\n\s*maxHeight=\{EAT_TABLE_VIEWPORT_MAX_HEIGHT\}/);
    expect(source).toContain('const EAT_TABLE_VIEWPORT_MAX_HEIGHT = 560;');
  });

  it('extracted modules exist and are non-trivial', () => {
    for (const rel of [
      '../appointmentsTableContracts.ts',
      '../useAppointmentsTableState.ts',
      '../appointmentsTableColumns.tsx',
    ]) {
      const content = readSrc(rel);
      expect(content.split('\n').length).toBeGreaterThan(100);
    }
  });
});
