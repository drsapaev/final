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

  it('passes through registrar queue patient display fields before legacy patient fetch fallback', () => {
    const source = fs.readFileSync(registrarPanelPath, 'utf8');

    expect(source).toContain('if (apt.patient_id && !hasBackendPatientDisplayContract(apt))');
    expect(source).toContain('patient_fio: fullEntry.patient_fio ?? fullEntry.patient_name');
    expect(source).toContain('patient_birth_year: fullEntry.patient_birth_year ?? fullEntry.birth_year');
    expect(source).toContain('patient_phone: fullEntry.patient_phone ?? fullEntry.phone');
    expect(source).toContain('address: fullEntry.address ?? entry.address');
  });
});

