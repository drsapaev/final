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

function collectCodeFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];

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

    const offenders = [];

    for (const filePath of collectCodeFiles(ROOT)) {
      const baseName = path.basename(filePath);
      if (baseName === 'noLegacyEmrReferences.test.js' || baseName === 'noLegacyEmrReferences.test.ts') {
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
