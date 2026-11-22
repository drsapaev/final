/**
 * CARDIO-FE-002 (audit 3886 round 20) — source contract for
 * CardiologistPanelUnified's cross-patient data stores.
 *
 * Red-first: on pre-fix source loadPatientData fetched ECG, blood tests,
 * files and visit history sequentially with no request-generation guard,
 * so a late response for patient A could overwrite the visible panels of
 * patient B after a selection change.
 *
 * Also pins the CARDIO-FE-001 wiring: the "Добавить ЭКГ" flow must render
 * the dedicated ManualEcgForm — never the blood-test form — and must not
 * read ECG measurements from bloodTestForm state.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const readSource = (relative: string) =>
  fs.readFileSync(path.join(__dirname, relative), 'utf8');

describe('CARDIO-FE-002 — patient-scoped data ownership (source contract)', () => {
  const source = readSource('../CardiologistPanelUnified.tsx');
  const loadHandler = source.match(/const loadPatientData = useCallback\(async[\s\S]*?\n {2}\}, \[/)?.[0] ?? '';

  it('pins the loader block that owns the four cross-patient data stores', () => {
    expect(loadHandler).not.toBe('');
    expect(loadHandler).toContain('setEcgResults');
    expect(loadHandler).toContain('setBloodTests');
    expect(loadHandler).toContain('setPatientFiles');
    expect(loadHandler).toContain('setVisitHistory');
  });

  it('takes a request-generation ticket and guards every store write', () => {
    // The generation ticket…
    expect(loadHandler).toMatch(/const epoch = \+\+patientDataEpochRef\.current/);
    expect(loadHandler).toMatch(/const isStale = \(\) => epoch !== patientDataEpochRef\.current/);
    // …checked after every await boundary, before each cross-patient write.
    const staleGuards = loadHandler.match(/if \(isStale\(\)\) return;|if \(epoch === patientDataEpochRef\.current\)/g) ?? [];
    expect(staleGuards.length).toBeGreaterThanOrEqual(8);
  });

  it('invalidates in-flight loads when the selection changes and clears the four stores', () => {
    const selectionEffect =
      source.match(/\/\/ ✅ Очистка EMR и visitData при смене пациента[\s\S]*?\n {2}\}, \[selectedPatient, loadPatientData, authRefreshTick\]\);/)?.[0] ?? '';
    expect(selectionEffect).not.toBe('');
    expect(selectionEffect).toContain('patientDataEpochRef.current += 1');
    expect(selectionEffect).toContain('setEcgResults([])');
    expect(selectionEffect).toContain('setBloodTests([])');
    expect(selectionEffect).toContain('setPatientFiles([])');
    expect(selectionEffect).toContain('setVisitHistory([])');
  });

  it('invalidates pending loads on unmount', () => {
    expect(source).toMatch(/useEffect\(\(\) => \(\) => \{\s*\n\s*patientDataEpochRef\.current \+= 1;/);
  });
});

describe('CARDIO-FE-001 — dedicated manual ECG entry (source contract)', () => {
  const source = readSource('../CardiologistPanelUnified.tsx');
  const manualFormSource = readSource('../../components/cardiology/ManualEcgForm.tsx');

  it('the ECG add flow renders ManualEcgForm, not the blood-test form', () => {
    const ecgBlock =
      source.match(/\{showForm\.open && showForm\.type === 'ecg' && \([\s\S]*?\n {10}\)\}/)?.[0] ?? '';
    expect(ecgBlock).not.toBe('');
    expect(ecgBlock).toContain('<ManualEcgForm');
    expect(ecgBlock).not.toContain('BloodTestsTab');
  });

  it('the panel no longer reads ECG measurements from blood-test state', () => {
    // The pre-fix payload read heart_rate/pr_interval/… from bloodTestForm.
    expect(source).not.toContain('bloodTestForm?.heart_rate');
    expect(source).not.toContain('bloodTestForm?.pr_interval');
    expect(source).not.toContain('bloodTestForm?.qrs_duration');
  });

  it('ManualEcgForm posts the backend ECG DTO with source manual', () => {
    expect(manualFormSource).toContain('api.post(\'/cardio/ecg\'');
    expect(manualFormSource).toContain('source: \'manual\'');
    expect(manualFormSource).toContain('file_id: null');
    // Empty clinical sets are never persisted.
    expect(manualFormSource).toContain('cardio.cardio_manual_ecg_empty_clinical');
  });

  it('EcgTab keys the viewer and echo form per patient/visit context', () => {
    const ecgTabSource = readSource('../../components/cardiology/EcgTab.tsx');
    expect(ecgTabSource).toContain('key={`ecg-viewer-${ownerKey}`}');
    expect(ecgTabSource).toContain('key={`echo-form-${ownerKey}`}');
  });

  it('ECGViewer uploads a real File part and parses by extension', () => {
    const viewerSource = readSource('../../components/cardiology/ECGViewer.tsx');
    // ECGVIEW-FE-001: the real binary part, not String(file).
    expect(viewerSource).toContain('formData.append(\'file\', file, file.name)');
    expect(viewerSource).not.toContain('formData.append(\'file\', String(file))');
    // ECGVIEW-FE-003: extension-driven parse dispatch.
    expect(viewerSource).toMatch(/name\.endsWith\('\.xml'\) \|\| .*\.endsWith\('\.scp'\)/);
    // ECGVIEW-FE-002: owner-epoch guard for async commits.
    expect(viewerSource).toContain('const isStaleContext = (epochAtStart: number)');
  });

  it('EchoForm hydrates from the canonical EMR and skips pristine saves', () => {
    const echoSource = readSource('../../components/cardiology/EchoForm.tsx');
    // Hydration on visit change…
    expect(echoSource).toMatch(/loadExistingEmrDraft\(visitId\)/);
    // …dirty tracking…
    expect(echoSource).toContain('dirtyRef.current = false');
    expect(echoSource).toContain('dirtyRef.current = true');
    // …the pristine no-op guard…
    expect(echoSource).toContain('cardio.cardio_echo_no_changes');
    // …and the save gate while hydration is in flight.
    expect(echoSource).toContain('cardio.cardio_echo_loading_existing');
  });
});
