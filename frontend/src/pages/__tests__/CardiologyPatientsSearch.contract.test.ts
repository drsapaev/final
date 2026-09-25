/**
 * Cardioplan slice 4 contract: "Пациенты и AI".
 *
 * Pins the panel-level wiring:
 *  - the Patients section renders the doctor-scoped patient search and the
 *    picked patient selects the panel context (source 'patient_search');
 *  - the visit history query is doctor-owned (/visits/visits with the
 *    canonical Doctor.id — the backend rejects foreign doctor_id for doctor
 *    roles);
 *  - the AI tab is read-only: no apply action, no local-state suggestion
 *    handler; applying stays inside the EMR editor.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const panelSource = fs.readFileSync(
  path.join(__dirname, '../CardiologistPanelUnified.tsx'),
  'utf8',
);
const aiTabSource = fs.readFileSync(
  path.join(__dirname, '../../components/cardiology/AiTab.tsx'),
  'utf8',
);
const patientSearchSource = fs.readFileSync(
  path.join(__dirname, '../../components/cardiology/PatientSearch.tsx'),
  'utf8',
);

describe('Cardiology Patients & AI contract', () => {
  it('renders the patient search in the Patients section', () => {
    expect(panelSource).toContain('<PatientSearch');
    expect(panelSource).toContain('onPick={handlePatientSearchPick}');
    expect(panelSource).toContain('selectedPatientId={(selectedPatient?.patient_id ?? selectedPatient?.id ?? null)');
  });

  it('selects the picked patient for the panel without visit or queue context', () => {
    expect(panelSource).toContain("source: 'patient_search'");
    const pickHandler = panelSource.match(/const handlePatientSearchPick = [\s\S]*?\n  };/);
    expect(pickHandler).not.toBeNull();
    expect(pickHandler?.[0]).toContain('visit_id: null');
    expect(pickHandler?.[0]).not.toContain('doctor_queue_entry_id');
  });

  it('loads visit history through the doctor-owned visits endpoint', () => {
    expect(panelSource).toContain("apiClient.get('/visits/visits'");
    const visitsCall = panelSource.match(/apiClient\.get\('\/visits\/visits'[\s\S]*?\}\)/);
    expect(visitsCall).not.toBeNull();
    expect(visitsCall?.[0]).toContain('patient_id: patientId');
    expect(visitsCall?.[0]).toContain('doctor_id: historyDoctorId');
  });

  it('keeps the AI tab read-only with no local-state apply handler', () => {
    expect(panelSource).toContain('<AiTab />');
    expect(panelSource).not.toContain('<AiTab onSuggestionSelect');
    expect(panelSource).not.toContain('const handleAISuggestion');
    // The shared AIAssistant keeps its apply behavior for other panels; the
    // cardiology tab simply stops passing the callback.
    expect(aiTabSource).not.toContain('onSuggestionSelect=');
    expect(aiTabSource).toContain('<AIAssistant specialty="cardiology" />');
  });

  it('guards the search query on the client at 2 characters', () => {
    expect(patientSearchSource).toContain('PATIENT_SEARCH_MIN_CHARS = 2');
    expect(patientSearchSource).toContain("trimmed.length < PATIENT_SEARCH_MIN_CHARS");
  });
});
