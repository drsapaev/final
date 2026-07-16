import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const readSource = (relPath) =>
  fs.readFileSync(path.join(ROOT, relPath), 'utf8').replace(/\r\n/g, '\n');

describe('CardiologistPanel Phase 1 safety contract (C-1 through C-7 + H-1)', () => {
  it('C-1: ECGParser parseSCPFile does NOT return hardcoded fake parameters', () => {
    const source = readSource('components/cardiology/ECGParser.jsx');

    // Extract only the parseSCPFile function body (not comments).
    const scpBlock = source.slice(
      source.indexOf('export const parseSCPFile'),
      source.indexOf('export const parseXMLFile'),
    );

    // Must NOT contain hardcoded fake values in the function body.
    expect(scpBlock).not.toContain('heartRate: 75');
    expect(scpBlock).not.toContain('prInterval: 160');
    expect(scpBlock).not.toContain('qrsInterval: 90');
    expect(scpBlock).not.toContain('qtInterval: 400');

    // Must return success: false when SCP parsing is not implemented.
    expect(scpBlock).toContain('success: false');
    // i18n-unification: hardcoded Russian replaced with i18n key
    expect(scpBlock).toContain("cardio_parser_scp_not_implemented");
  });

  it('C-2: ECGParser has no void artifacts', () => {
    const source = readSource('components/cardiology/ECGParser.jsx');

    // The void artifact was: `void view.getUint16(0, true);void`
    expect(source).not.toContain('void view.getUint16');
    expect(source).not.toContain('void\n  view.getUint32');
  });

  it('C-3: cancel action is wired to handleCancelAppointment (not a no-op stub)', () => {
    const source = readSource('pages/CardiologistPanelUnified.jsx');

    // Must NOT contain the old no-op stub.
    expect(source).not.toContain('// Логика отмены записи\n        break;');

    // Must call handleCancelAppointment.
    expect(source).toContain('handleCancelAppointment');
    expect(source).toContain('await handleCancelAppointment(row)');

    // handleCancelAppointment must use confirm dialog + backend cancel call.
    expect(source).toContain('const handleCancelAppointment = async (row) => {');
    expect(source).toContain('await confirm(');
    expect(source).toContain('/cancel');
    expect(source).toContain('notify.success');
    expect(source).toContain('notify.error');
  });

  it('C-4: Добавить ЭКГ button renders a form when showForm.type === ecg', () => {
    const source = readSource('pages/CardiologistPanelUnified.jsx');

    // Must render UI when type === 'ecg'.
    expect(source).toContain('showForm.type === \'ecg\'');
    // i18n-unification: hardcoded Russian replaced with i18n key
    expect(source).toContain('cardio_panel_add_ecg_title');

    // Must persist to /cardio/ecg endpoint.
    expect(source).toContain('/cardio/ecg');
    expect(source).toContain('source: \'manual\'');
  });

  it('C-5: ECGViewer onDrop catch has notify.error', () => {
    const source = readSource('components/cardiology/ECGViewer.jsx');

    // i18n-unification: hardcoded Russian replaced with i18n key
    expect(source).toContain('cardio_ecg_upload_failed');
  });

  it('C-6: ECGViewer downloadFile catch has notify.error', () => {
    const source = readSource('components/cardiology/ECGViewer.jsx');

    // i18n-unification: t() replaced with tI18n() (reactive)
    expect(source).toContain("tI18n('final.ecg_download_failed')");
  });

  it('C-7: ECGViewer deleteFile catch has notify.error', () => {
    const source = readSource('components/cardiology/ECGViewer.jsx');

    // i18n-unification: t() replaced with tI18n() (reactive)
    expect(source).toContain("tI18n('final.ecg_delete_failed')");
  });

  it('H-1: ECGViewer parseECGFileData catch has notify.warning', () => {
    const source = readSource('components/cardiology/ECGViewer.jsx');

    // i18n-unification: t() replaced with tI18n() (reactive)
    expect(source).toContain("tI18n('final.ecg_parse_warning')");
  });

  it('ECGViewer imports notify + getErrorMessage', () => {
    const source = readSource('components/cardiology/ECGViewer.jsx');

    expect(source).toContain('from \'../../services/notify\'');
    expect(source).toContain('from \'../../utils/errorHandler\'');
  });
});
