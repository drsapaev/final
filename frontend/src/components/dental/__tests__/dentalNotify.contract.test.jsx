import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd(), 'src/components/dental');

const readSource = (fileName) =>
  fs.readFileSync(path.join(ROOT, fileName), 'utf8').replace(/\r\n/g, '\n');

// H8 fix: all dental components that handle user-facing errors must use
// the shared notify service (not react-toastify toast, not bare logger.error
// without UI feedback).
const FILES_WITH_USER_FACING_ERRORS = [
  'DiagnosisForm.jsx',
  'ExaminationForm.jsx',
  'PatientCard.jsx',
  'PhotoArchive.jsx',
  'ToothModal.jsx',
  'TreatmentPlanner.jsx',
  'VisitProtocol.jsx',
  'DentalPriceManager.jsx',
  'DentalVisitScreen.jsx',
];

describe('dental notify unification contract (H8)', () => {
  for (const fileName of FILES_WITH_USER_FACING_ERRORS) {
    it(`${fileName} imports the shared notify service`, () => {
      const source = readSource(fileName);
      expect(source).toContain('from \'../../services/notify\'');
    });

    it(`${fileName} does NOT use react-toastify toast directly`, () => {
      const source = readSource(fileName);
      expect(source).not.toContain('from \'react-toastify\'');
      expect(source).not.toContain('from "react-toastify"');
      expect(source).not.toMatch(/toast\.(success|error|info|warning)\(/);
    });

    it(`${fileName} has at least one notify.error call for user-facing errors`, () => {
      const source = readSource(fileName);
      expect(source).toMatch(/notify\.error\(/);
    });
  }

  it('every logger.error in save/submit catch blocks is paired with a notify.error', () => {
    // Only check logger.error calls that are in save/submit/delete action
    // catch blocks (user-facing failures). Background loading errors may
    // silently log without notifying — that's acceptable.
    for (const fileName of FILES_WITH_USER_FACING_ERRORS) {
      const source = readSource(fileName);
      const lines = source.split('\n');

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (!line.includes('logger.error(')) continue;

        // Look backwards to find the try block start — if it contains
        // a save/submit/delete/post/put action, notify.error is required.
        let tryStart = i;
        for (let j = i; j >= Math.max(0, i - 30); j--) {
          if (lines[j].includes('try {') || lines[j].includes('try{')) {
            tryStart = j;
            break;
          }
        }
        const tryBlock = lines.slice(tryStart, i).join('\n').toLowerCase();
        const isUserAction =
          tryBlock.includes('post(') ||
          tryBlock.includes('put(') ||
          tryBlock.includes('.save(') ||
          tryBlock.includes('handlesave') ||
          tryBlock.includes('onsubmit') ||
          tryBlock.includes('formdata') ||
          tryBlock.includes('api.post') ||
          tryBlock.includes('api.put');

        if (isUserAction) {
          const nextLines = lines.slice(i, i + 4).join('\n');
          expect(
            nextLines,
            `${fileName} line ${i + 1}: logger.error in save/submit catch without notify.error`,
          ).toContain('notify.error(');
        }
      }
    }
  });
});
