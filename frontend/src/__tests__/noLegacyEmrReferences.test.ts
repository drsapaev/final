import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd(), 'src');
const CODE_EXTENSIONS = new Set(['.js', '.jsx', '.ts', '.tsx']);
const FORBIDDEN_PATTERNS = [
  'SingleSheetEMR',
  'components/emr/',
  'from ../../emr/',
  'from ../emr/',
];

function collectCodeFiles(dir: string) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectCodeFiles(fullPath));
      continue;
    }

    if (CODE_EXTENSIONS.has(path.extname(entry.name))) {
      files.push(fullPath);
    }
  }

  return files;
}

describe('legacy EMR references', () => {
  it('does not keep runtime references to old EMR paths', () => {
    const legacyDir = path.resolve(ROOT, 'components/emr');
    expect(fs.existsSync(legacyDir)).toBe(false);

    const offenders: string[] = [];

    for (const filePath of collectCodeFiles(ROOT)) {
      // Skip this test file itself — it contains the forbidden patterns as
      // string literals (in FORBIDDEN_PATTERNS and the offenders list). The
      // original skip check matched only the `.js` extension, but the file is
      // `.ts`. Match both to be resilient to future extension changes.
      const basename = path.basename(filePath);
      if (basename === 'noLegacyEmrReferences.test.js' ||
          basename === 'noLegacyEmrReferences.test.ts') {
        continue;
      }

      const source = fs.readFileSync(filePath, 'utf8');
      for (const pattern of FORBIDDEN_PATTERNS) {
        if (source.includes(pattern)) {
          offenders.push(`${path.relative(ROOT, filePath)} :: ${pattern}`);
        }
      }
    }

    expect(offenders).toEqual([]);
  });
});
