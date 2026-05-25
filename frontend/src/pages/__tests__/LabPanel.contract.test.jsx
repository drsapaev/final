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
  it('keeps queue status separate from lab report status when merging report instances', () => {
    const source = readLabPanelSource();
    const mergeBlock = extractBlock(
      source,
      'function mergeQueueEntriesWithLabInstances(queueEntries, labInstances) {',
      'function buildTemplateResolutionPayload(appointment) {',
    );

    expect(mergeBlock).toContain('status: appointment.status');
    expect(mergeBlock).toContain('queue_status: appointment.queue_status || appointment.status');
    expect(mergeBlock).toContain("status_source: 'queue'");
    expect(mergeBlock).toContain('lab_report_status: linkedInstance.status || null');
    expect(mergeBlock).toContain("report_status_source: 'lab-report'");
    expect(mergeBlock).not.toContain('status: linkedInstance.status || appointment.status');
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
});
