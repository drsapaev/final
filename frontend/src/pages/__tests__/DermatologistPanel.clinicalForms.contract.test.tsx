import fs from 'fs';
import path from 'path';
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { fileURLToPath } from 'node:url';
import { normalizeSource } from '../../test/contracts/source-contract-helper';
import DermaExamsTab from '../../components/dermatology/DermaExamsTab';

vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock('../../components/ui/macos', () => ({
  Card: ({ children, ...props }: React.HTMLAttributes<HTMLElement>) => React.createElement('section', props, children),
  Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => React.createElement('button', props, children),
  Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => React.createElement('input', props),
  Textarea: (props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => React.createElement('textarea', props),
}));

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');

function source(relativePath: string) {
  return normalizeSource(fs.readFileSync(path.join(ROOT, relativePath), 'utf8'));
}

const panel = source('pages/DermatologistPanelUnified.tsx');
const emr = source('components/emr-v2/EMRContainerV2.tsx');
const dermatologySection = source('components/emr-v2/sections/specialty/DermatologySection.tsx');
const procedureForm = source('components/dermatology/DermaExamsTab.tsx');
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

  it('keeps legacy examinations read-only in patient history', () => {
    expect(panel).not.toContain('api.post(\'/derma/examinations\'');
    expect(historyHook).toContain('api.get(\'/derma/examinations\'');
    expect(historyHook).not.toContain('api.post(\'/derma/examinations\'');
    expect(patientsTab).not.toContain('onOpenExam');
    expect(patientsTab).not.toContain('onOpenProcedure');
  });

  it('renders the clinical cosmetic form only in the active visit and omits price fields', () => {
    const visitStart = panel.indexOf('{activeTab === \'visit\' && currentAppointment &&');
    const visitEnd = panel.indexOf('{/* Прием пациента - простая версия */}', visitStart);
    expect(visitStart).toBeGreaterThanOrEqual(0);
    expect(panel.slice(visitStart, visitEnd)).toContain('<DermaExamsTab');
    expect(panel).not.toContain('activeTab === \'services\'');
    expect(panel).not.toContain('dermaPriceMap');
    expect(panel).not.toContain('doctorPrice');
    expect(procedureForm).not.toContain('total_cost');
    expect(procedureForm).not.toContain('derma_exams_cosmetic_cost');
    expect(historyTab).not.toContain('total_cost');
  });

  it('renders and submits the clinical procedure fields without a price input', () => {
    const onSubmit = vi.fn((event: React.FormEvent<HTMLFormElement>) => event.preventDefault());
    const setCosmeticProcedure = vi.fn();
    render(
      <DermaExamsTab
        cosmeticProcedure={{
          patient_id: '42',
          visit_id: '900',
          procedure_date: '2026-09-25',
          procedure_type: 'SYNTHETIC procedure',
          area_treated: 'SYNTHETIC area',
          products_used: 'SYNTHETIC product',
          results: 'SYNTHETIC result',
          follow_up: '',
        }}
        setCosmeticProcedure={setCosmeticProcedure}
        showCosmeticForm
        onCosmeticSubmit={onSubmit}
        onOpenCosmeticForm={vi.fn()}
        onCancelCosmeticForm={vi.fn()}
      />,
    );

    expect(screen.getByLabelText('derma.derma_exams_cosmetic_date')).toHaveValue('2026-09-25');
    expect(screen.getByLabelText('derma.derma_exams_cosmetic_type')).toHaveValue('SYNTHETIC procedure');
    expect(screen.getByLabelText('derma.derma_exams_cosmetic_area')).toHaveValue('SYNTHETIC area');
    expect(screen.getByLabelText('derma.derma_exams_cosmetic_products')).toHaveValue('SYNTHETIC product');
    expect(screen.getByLabelText('derma.derma_exams_cosmetic_results')).toHaveValue('SYNTHETIC result');
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument();
    expect(screen.queryByText('derma.derma_exams_cosmetic_cost')).not.toBeInTheDocument();

    fireEvent.submit(screen.getByRole('button', { name: 'derma.derma_exams_cosmetic_save' }).closest('form')!);
    expect(onSubmit).toHaveBeenCalledOnce();
  });
});
