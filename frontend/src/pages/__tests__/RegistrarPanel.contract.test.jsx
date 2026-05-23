import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const registrarPanelPath = path.resolve(__dirname, '../RegistrarPanel.jsx');

describe('RegistrarPanel command contract', () => {
  it('uses the backend registrar record action endpoint for queue/payment/status commands', () => {
    const source = fs.readFileSync(registrarPanelPath, 'utf8');

    expect(source).toContain("api.post('/registrar/records/actions'");
    expect(source).not.toContain('/registrar/visits/${recordId}/mark-paid');
    expect(source).not.toContain('/registrar/queue/entry/${recordId}/mark-paid');
    expect(source).not.toContain('/appointments/${recordId}/mark-paid');
    expect(source).not.toContain('/registrar/visits/${realId}/complete');
    expect(source).not.toContain('/registrar/queue/${realId}/start-visit');
    expect(source).not.toContain('/online-queue/entries/${targetId}/cancel');
  });
});

