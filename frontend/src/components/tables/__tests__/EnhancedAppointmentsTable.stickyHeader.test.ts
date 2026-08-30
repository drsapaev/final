/**
 * EnhancedAppointmentsTable (EAT) sticky-header wiring source contract
 * (PR-UI-12-4).
 *
 * Plan reference: `docs/UI_REMEDIATION_PLAN.md` §PR-UI-12 item 4 —
 * "Все таблицы — sticky header при скролле" (Appointments surface; EAT is the
 * appointments table used by /clinical/appointments, registrar WelcomeView
 * and the doctor panels).
 *
 * EAT is a 2000+ LOC container with a heavyweight data/queue contract —
 * mounting it in jsdom would mock most of the panel, so this file uses the
 * repo's established SOURCE-CONTRACT pattern (see QueueManager.contract.test
 * .tsx and EMRSectionSkeleton.test.tsx) to lock the sticky-header wiring by
 * name. The kit-level behavior (bounded viewport + sticky header + measured
 * filter offset) is covered by DataTable tests DT-45..47; the render-level
 * proof on a real browser is the PR-UI-12-4 visual-regression spec
 * (e2e/visual-regression.spec.ts, "PR-UI-12-4 five clinical screens").
 */

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const sourcePath = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../EnhancedAppointmentsTable.tsx'
);
const source = readFileSync(sourcePath, 'utf8');

describe('EnhancedAppointmentsTable — sticky header wiring source contract (PR-UI-12-4)', () => {
  it('EAT passes stickyHeader + maxHeight to the canonical DataTable', () => {
    // The DataTable invocation inside .eat-table-scroll carries both flags.
    expect(source).toMatch(
      /<DataTable[\s\S]*?stickyHeader\s*\n\s*maxHeight=\{EAT_TABLE_VIEWPORT_MAX_HEIGHT\}/
    );
  });

  it('the viewport bound is a named, documented constant (no magic number in JSX)', () => {
    expect(source).toMatch(/const EAT_TABLE_VIEWPORT_MAX_HEIGHT = 560;/);
    // The constant's doc block explains it is a LAYOUT parameter, not a
    // sticky offset — the kit measures the sticky offsets itself.
    expect(source).toMatch(/NOT a sticky offset/);
  });

  it('the wiring comment references the plan item (traceability)', () => {
    expect(source).toMatch(/PR-UI-12-4 \(plan §PR-UI-12 item 4/);
  });
});
