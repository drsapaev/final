import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const PANEL_PATH = path.resolve(__dirname, '../../../pages/DentistPanelUnified.tsx');

const readSource = (fileName: string) =>
  fs.readFileSync(path.join(ROOT, fileName), 'utf8').replace(/\r\n/g, '\n');

const readPanel = () =>
  fs.readFileSync(PANEL_PATH, 'utf8').replace(/\r\n/g, '\n');

// PR-UI-15-6: the renderVisits JSX moved verbatim to
// pages/dentist/views/DentistVisitsView.tsx — the panel contract surface is
// the union of the panel and its extracted dentist modules (same pattern as
// DentistPanel safety/i18n contracts and DoctorPanels.contract).
const readDentistModules = () => {
  const dentistDir = path.resolve(__dirname, '../../../pages/dentist');
  const parts: string[] = [];
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === '__tests__') continue;
        walk(full);
      } else if (/\.tsx?$/.test(entry.name)) {
        parts.push(fs.readFileSync(full, 'utf8'));
      }
    }
  };
  if (fs.existsSync(dentistDir)) walk(dentistDir);
  return parts.join('\n');
};

const readPanelUnion = () => `${readPanel()}\n${readDentistModules()}`;

describe('DentalVisitScreen contract (Phase 4+ minimalist visit screen)', () => {
  it('imports SSOT constants from dentalConstants (no local redefinition)', () => {
    const source = readSource('DentalVisitScreen.tsx');

    expect(source).toContain('from \'../dental/dentalConstants\'');
    expect(source).toContain('TOOTH_STATUS_LABELS');
    expect(source).toContain('TOOTH_STATUS_COLORS');
    expect(source).toContain('getToothName');
  });

  it('uses TeethChart + ToothModal for the chart workflow', () => {
    const source = readSource('DentalVisitScreen.tsx');

    expect(source).toContain('import TeethChart from \'../dental/TeethChart\'');
    expect(source).toContain('import ToothModal from \'../dental/ToothModal\'');
    expect(source).toContain('<TeethChart');
    expect(source).toContain('<ToothModal');
  });

  it('integrates AIAssistant inline (not as a separate tab) for ICD-10 suggestions', () => {
    const source = readSource('DentalVisitScreen.tsx');

    // AI must be embedded in the visit screen, not a separate tab.
    expect(source).toContain('import AIAssistant from \'../ai/AIAssistant\'');
    expect(source).toContain('<AIAssistant');
    expect(source).toContain('analysisType="icd10"');

    // AI suggestions must be wired to the icd10_code field via onSuggestionSelect.
    expect(source).toContain('onSuggestionSelect');
    expect(source).toContain('applyAISuggestion');
    expect(source).toContain('updateField(\'icd10_code\'');

    // Must NOT just log the suggestion — must actually apply it.
    expect(source).not.toContain('logger.info(\'[Dentistry] AI suggestion\'');
  });

  it('auto-saves EMR draft through POST /v2/emr/{visitId}', () => {
    const source = readSource('DentalVisitScreen.tsx');

    expect(source).toContain('saveEMR');
    expect(source).toContain('scheduleAutosave');
    expect(source).toContain('apiClient.post(`/v2/emr/${visitId}`');
    expect(source).toContain('is_draft: isDraft');
    expect(source).toContain('row_version');
  });

  it('loads existing EMR on mount via GET /v2/emr/{visitId}', () => {
    const source = readSource('DentalVisitScreen.tsx');

    expect(source).toContain('loadExistingEMR');
    expect(source).toContain('apiClient.get(`/v2/emr/${visitId}`');
  });

  it('loads patient visit history via GET /v2/emr/patient/{patientId}', () => {
    const source = readSource('DentalVisitScreen.tsx');

    expect(source).toContain('loadHistory');
    expect(source).toContain('apiClient.get(`/v2/emr/patient/${patientId}`');
    expect(source).toContain('VisitHistory');
  });

  it('renders the minimalist layout: header + anamnesis + chart + extras + history', () => {
    const source = readSource('DentalVisitScreen.tsx');

    expect(source).toContain('PatientHeader');
    expect(source).toContain('AnamnesisSection');
    expect(source).toContain('ToothSummary');
    expect(source).toContain('CollapsibleExtras');
    expect(source).toContain('VisitHistory');

    // Anamnesis must be a Textarea (1-2 строки), not a heavy form.
    expect(source).toContain('<Textarea');

    // "Дополнительно" section must be collapsible (closed by default).
    expect(source).toContain('ChevronDown');
    expect(source).toContain('ChevronUp');
    expect(source).toContain('useState(false)');
  });

  it('passes onCompleteVisit through to PatientHeader (wired to C-1/C-3 confirm)', () => {
    const source = readSource('DentalVisitScreen.tsx');

    // Strict:true migration added `|| (() => {})` fallback so the prop is
    // always a function (PatientHeader propTypes mark it as isRequired).
    expect(source).toContain('onCompleteVisit={onCompleteVisit || (() => {})}');
    expect(source).toContain('Завершить визит');
  });

  it('DentistPanelUnified uses DentalVisitScreen in renderVisits when patient is selected', () => {
    const source = readPanelUnion();

    // PR-UI-15-6: the import + JSX live in views/DentistVisitsView now.
    expect(source).toContain('import DentalVisitScreen from \'../../../components/dental/DentalVisitScreen\'');
    expect(source).toContain('<DentalVisitScreen');
    // The panel wires the completion flow into the view.
    expect(readPanel()).toContain('onCompleteVisit={handleCompleteVisit}');

    // Must NOT use the old EMRContainerV2 for selectedPatient visits
    // (EMRContainerV2 may still be imported for other uses, but not in renderVisits).
    const renderVisitsBlock = source.slice(
      source.indexOf('const renderVisits = () =>'),
      source.indexOf('const renderPhotos = () =>'),
    );
    expect(renderVisitsBlock).not.toContain('<EMRContainerV2');
    const visitsViewBlock = source.slice(
      source.indexOf('export default function DentistVisitsView'),
      source.indexOf('export default function DentistPhotosView'),
    );
    expect(visitsViewBlock).not.toContain('<EMRContainerV2');
  });
});
