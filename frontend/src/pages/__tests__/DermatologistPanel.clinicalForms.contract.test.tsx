import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
import { normalizeSource } from '../../test/contracts/source-contract-helper';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');

function source(relativePath: string) {
  return normalizeSource(fs.readFileSync(path.join(ROOT, relativePath), 'utf8'));
}

const panel = source('pages/DermatologistPanelUnified.tsx');
const emr = source('components/emr-v2/EMRContainerV2.tsx');
const dermatologySection = source('components/emr-v2/sections/specialty/DermatologySection.tsx');
const patientsTab = source('components/dermatology/DermaPatientsTab.tsx');
const historyTab = source('components/dermatology/DermaHistoryTab.tsx');
const historyHook = source('pages/useDermatologyPatientHistory.ts');

describe('dermatologist clinical forms contract', () => {
  it('stores one skin examination in EMR specialty data and leaves diagnosis to the main EMR section', () => {
    for (const field of ['skin_condition', 'localization', 'lesions', 'distribution', 'symptoms', 'treatment_plan']) {
      expect(emr).toContain(`specialty_data?.${field}`);
      expect(dermatologySection).toContain(`'${field}'`);
    }

    expect(emr).toContain('<DiagnosisSection');
    expect(dermatologySection).not.toContain('diagnosis?:');
    expect(dermatologySection).not.toContain('field: \'diagnosis\'');
  });

  it('stores cosmetic procedures in EMR specialty data (P2-4b: single clinical source)', () => {
    expect(emr).toContain('specialty_data?.cosmetic_procedures');
    expect(dermatologySection).toContain('\'cosmetic_procedures\'');
    expect(dermatologySection).toContain('derma_exams_cosmetic_title');

    // The legacy standalone form and its write endpoint are gone (410, P2-4a).
    expect(panel).not.toContain('DermaExamsTab');
    expect(panel).not.toContain('api.post(\'/derma/procedures\'');
    expect(panel).not.toContain('api.post(\'/derma/examinations\'');
    expect(() =>
      fs.accessSync(path.join(ROOT, 'components/dermatology/DermaExamsTab.tsx')),
    ).toThrow();
  });

  it('reads patient history from the server-side EMR+legacy union with exact pagination (P2-4b canonical)', () => {
    // The union is server-side: the hook pages through the derma GETs and
    // must not fetch the EMR v2 endpoints directly (review follow-up on
    // #3490/#3491 — no client-side EMR hydration, no per-source limits).
    expect(historyHook).not.toContain('/v2/emr/patient/');
    expect(historyHook).not.toContain('/v2/emr/');
    expect(historyHook).toContain('\'/derma/examinations\'');
    expect(historyHook).toContain('\'/derma/procedures\'');
    expect(historyHook).toContain('api.get');
    expect(historyHook).toContain('HISTORY_PAGE_SIZE');
    expect(historyHook).toContain('patient_id');
    expect(historyHook).toContain('total');
    expect(historyHook).not.toContain('api.post(\'/derma/examinations\'');
    expect(historyHook).not.toContain('api.post(\'/derma/procedures\'');
    expect(patientsTab).not.toContain('onOpenExam');
    expect(patientsTab).not.toContain('onOpenProcedure');
  });

  it('renders the clinical procedure editor inside the EMR section without price fields', () => {
    const visitStart = panel.indexOf('{activeTab === \'visit\' && currentAppointment &&');
    const visitEnd = panel.indexOf('{/* Прием пациента - простая версия */}', visitStart);
    expect(visitStart).toBeGreaterThanOrEqual(0);
    expect(panel.slice(visitStart, visitEnd)).toContain('<EMRContainerV2');
    expect(panel.slice(visitStart, visitEnd)).not.toContain('DermaExamsTab');
    expect(panel).not.toContain('activeTab === \'services\'');
    expect(panel).not.toContain('dermaPriceMap');
    expect(panel).not.toContain('doctorPrice');
    expect(dermatologySection).not.toContain('total_cost');
    expect(dermatologySection).not.toContain('derma_exams_cosmetic_cost');
    expect(historyTab).not.toContain('total_cost');
  });
});
