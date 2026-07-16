import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { API_ENDPOINTS } from '../../api/endpoints.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const printServicePath = path.resolve(__dirname, '../print.ts');

const readPrintServiceSource = () => fs.readFileSync(printServicePath, 'utf8');

describe('print service route contract', () => {
  it('uses the canonical mounted print-template list route', () => {
    const source = readPrintServiceSource();

    expect(source).toContain('api.get(\'/print/templates/templates\'');
    expect(API_ENDPOINTS.PRINT.TEMPLATES).toBe('/print/templates/templates');
  });

  it('does not call the stale print-template list route', () => {
    const source = readPrintServiceSource();

    expect(source).not.toContain('api.get(\'/print/templates\',');
  });
});
