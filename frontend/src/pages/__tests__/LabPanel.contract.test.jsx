import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const labPanelPath = path.resolve(__dirname, '../LabPanel.jsx');

const readLabPanelSource = () => fs.readFileSync(labPanelPath, 'utf8');

const extractBlock = (source, startMarker, endMarker) => {
  const start = source.indexOf(startMarker);
  expect(start).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
  expect(end).toBeGreaterThan(start);
  return source.slice(start, end);
};

describe('LabPanel queue/report status contract', () => {
  it('keeps queue status separate from backend-provided lab report summary', () => {
    const source = readLabPanelSource();
    const formatBlock = extractBlock(
      source,
      'function formatAppointmentEntry(queue, entry) {',
      'function normalizeListPayload(payload) {',
    );

    expect(formatBlock).toContain('const latestLabReport = entry.latest_lab_report || null');
    expect(formatBlock).toContain("status_source: 'queue'");
    expect(formatBlock).toContain('queue_status: entry.status ||');
    expect(formatBlock).toContain('lab_report_status: latestLabReport?.status || null');
    expect(formatBlock).toContain("report_status_source: latestLabReport ? 'lab-report' : null");
    const lines = formatBlock.split('\n').map((line) => line.trim());
    expect(lines).not.toContain('status: latestLabReport?.status || entry.status,');
    expect(lines).not.toContain('status: latestLabReport?.status || null,');
  });

  it('does not add BFF-lite endpoints for the lab queue contract repair', () => {
    const source = readLabPanelSource();

    expect(source).not.toContain('/api/v1/ui/');
    expect(source).not.toContain('/ui/lab');
  });

  it('uses the backend registrar department contract for lab queue rows', () => {
    const source = readLabPanelSource();
    const loadBlock = extractBlock(
      source,
      'const loadLabAppointments = useCallback(async () => {',
      'const loadTemplates = useCallback(async (preferredTemplateId = null) => {',
    );

    expect(loadBlock).toContain("new URLSearchParams({ department: 'lab' })");
    expect(loadBlock).toContain('/registrar/queues/today?${queueParams.toString()}');
    expect(loadBlock).not.toContain(".filter((queue) => ['lab', 'laboratory'].includes(queue.specialty))");
  });

  it('does not fetch report instances by visit_ids to enrich normal queue rows', () => {
    const source = readLabPanelSource();
    const loadBlock = extractBlock(
      source,
      'const loadLabAppointments = useCallback(async () => {',
      'const loadTemplates = useCallback(async (preferredTemplateId = null) => {',
    );

    expect(loadBlock).not.toContain('visit_ids');
    expect(loadBlock).not.toContain('mergeQueueEntriesWithLabInstances');
    expect(source).not.toContain('function mergeQueueEntriesWithLabInstances');
  });
});
