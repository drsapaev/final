import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const qrTokenManagerPath = path.resolve(__dirname, '../QRTokenManager.jsx');

const readSource = () => fs.readFileSync(qrTokenManagerPath, 'utf8');

describe('QRTokenManager API contract', () => {
  it('uses the canonical QR queue admin paths mounted under /queue', () => {
    const source = readSource();

    expect(source).toContain("fetch('/api/v1/queue/admin/qr-tokens/active'");
    expect(source).toContain("fetch('/api/v1/queue/admin/qr-tokens/generate'");
    expect(source).toContain('fetch(`/api/v1/queue/admin/qr-tokens/${token}`');
  });

  it('does not call the stale admin QR token path', () => {
    const source = readSource();

    expect(source).not.toContain('/api/v1/admin/qr-tokens');
  });
});
