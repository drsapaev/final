import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// PR-UI-15 (plan §7): machine-checked AC guards for the DoctorPanel
// decomposition — same pattern as the RegistrarPanel (13-5) and
// CashierPanel (14-6) contract tests.
const doctorPanelPath = path.resolve(__dirname, '../DoctorPanel.tsx');

const readDoctorPanelSource = () => fs.readFileSync(doctorPanelPath, 'utf8');

describe('DoctorPanel plan §PR-UI-15 AC guards', () => {
  it('stays within the plan §PR-UI-15 size budget (≤500 LOC)', () => {
    const source = readDoctorPanelSource();
    const loc = source.split('\n').length;
    expect(loc).toBeLessThanOrEqual(500);
  });

  it('renders behind the local ErrorBoundary (plan item 5), reset per tab (Codex P2 #2926)', () => {
    const source = readDoctorPanelSource();
    // key={activeTab} — boundary resets when switching tabs so one crashed
    // tab does not poison the others (Codex review #2926).
    expect(source).toContain('<ErrorBoundary key={activeTab}>');
  });

  it('keeps the slim-orchestrator decomposition: no inline tab tables/stat grids', () => {
    // The heavy tab JSX lives in ./doctor/views/* — the orchestrator must
    // delegate instead of re-inlining (anti-FooWrapper guard).
    const source = readDoctorPanelSource();
    expect(source).toContain("from './doctor/views/DoctorPatientsTab'");
    expect(source).toContain("from './doctor/views/DoctorAppointmentsTab'");
    expect(source).toContain("from './doctor/views/DoctorDashboardTab'");
    expect(source).toContain("from './doctor/views/DoctorTabsNav'");
    expect(source).toContain("from './doctor/views/DoctorDialogsLayer'");
    expect(source).not.toContain('renderEmptyState');
    expect(source).not.toContain('doctor-th">');
  });

  it('keeps the canCallNext queue SSOT wiring (DoctorPanels.contract)', () => {
    const source = readDoctorPanelSource();
    expect(source).toContain('canCallNext');
  });
});
