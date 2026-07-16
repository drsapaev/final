import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const echoFormPath = path.resolve(__dirname, '../EchoForm.tsx');

const readEchoFormSource = () => fs.readFileSync(echoFormPath, 'utf8');

describe('EchoForm EMR contract', () => {
  it('saves Echo data through the existing EMR v2 draft contract', () => {
    const source = readEchoFormSource();

    expect(source).not.toContain('/cardiology/echo-results');
    expect(source).toContain('api.get(`/v2/emr/${visitId}`)');
    expect(source).toContain('api.post(`/v2/emr/${visitId}`, buildEchoEmrPayload(existingEmr, echoData))');
    expect(source).toContain('specialty_data: {');
    expect(source).toContain('echo: echoData');
  });

  it('preserves backend-owned EMR locking data instead of inventing command state', () => {
    const source = readEchoFormSource();

    expect(source).toContain('row_version: existingEmr?.row_version ?? 0');
    expect(source).toContain('is_draft: true');
    expect(source).not.toContain('available_actions');
    expect(source).not.toContain('can_sign');
    expect(source).not.toContain('can_amend');
  });
});
