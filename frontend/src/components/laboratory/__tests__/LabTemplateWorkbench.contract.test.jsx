import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

// L-H-6 fix: helper-функции вынесены в templateEditor/utils.js.
// Контракт-тест обновлён, чтобы читать оба файла.
const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabTemplateWorkbench.jsx'),
  'utf8'
);

const utilsSource = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/templateEditor/utils.js'),
  'utf8'
);

function blockFromFile(fileContent, startMarker, endMarker) {
  const start = fileContent.indexOf(startMarker);
  expect(start).toBeGreaterThanOrEqual(0);
  const end = fileContent.indexOf(endMarker, start);
  expect(end).toBeGreaterThan(start);
  return fileContent.slice(start, end);
}

describe('LabTemplateWorkbench template version command contract', () => {
  it('uses backend-owned template version actions instead of status for draft creation', () => {
    // helper теперь в utils.js
    const helperBlock = blockFromFile(
      utilsSource,
      'function hasTemplateVersionAction(version, action) {',
      'function parseJsonInput(value) {'
    );
    const ensureDraftBlock = blockFromFile(
      source,
      'async function ensureDraftVersion() {',
      'async function handleSaveTemplate() {'
    );

    expect(helperBlock).toContain('version?.available_actions');
    expect(helperBlock).toContain('TEMPLATE_VERSION_ACTION_CAN_FIELD');
    expect(helperBlock).toContain('return false;');
    expect(ensureDraftBlock).toContain('hasTemplateVersionAction(activeVersion, \'update\')');
    expect(ensureDraftBlock).toContain('hasTemplateVersionAction(activeVersion, \'create_draft\')');
    expect(ensureDraftBlock).toContain('labReportingApi.createTemplateVersion');
    expect(ensureDraftBlock).not.toContain('activeVersion?.status === \'DRAFT\'');
  });
});
