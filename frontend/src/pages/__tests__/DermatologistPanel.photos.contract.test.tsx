/**
 * Derma audit item 8 — фото через /files: source contract.
 *
 * Пинит границы пункта 8 плана аудита дерматологии:
 * - галерея текущего визита встроена в экран приёма (visit-таб);
 * - /files — единственный источник фото (список + авторизованное превью);
 * - псевдозагрузка File/blob: в JSON ЭМК удалена (DermatologySection без photos);
 * - старые blob: значения не мигрируются и не считаются сохранёнными;
 * - неработающая камера и несохраняемые метаданные удалены вместе с
 *   недостижимой вкладкой photos (legacy-компоненты удалены).
 */
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
const gallery = source('components/dermatology/DermaVisitGallery.tsx');
const dermatologySection = source('components/emr-v2/sections/specialty/DermatologySection.tsx');
const emr = source('components/emr-v2/EMRContainerV2.tsx');

describe('dermatologist visit photos contract (item 8)', () => {
  it('embeds the visit gallery into the active visit screen', () => {
    const visitStart = panel.indexOf('{activeTab === \'visit\' && currentAppointment &&');
    const visitEnd = panel.indexOf('{/* Прием пациента - простая версия */}', visitStart);
    expect(visitStart).toBeGreaterThanOrEqual(0);
    const visitBlock = panel.slice(visitStart, visitEnd);
    expect(visitBlock).toContain('<DermaVisitGallery');
    expect(visitBlock).toContain('patientId={currentAppointment.patient_id}');
    expect(visitBlock).toContain('visitId={currentAppointment.visit_id}');
  });

  it('uses /files as the only photo source with an authorized blob preview', () => {
    const galleryCode = gallery
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    expect(galleryCode).toContain('\'/files/\'');
    expect(galleryCode).toContain('api.get');
    // normalizeSource сворачивает `patient_id: patientId` до shorthand — пиним нормализованную форму
    expect(galleryCode).toContain('params: { patient_id, visit_id, size:');
    expect(galleryCode).toContain('(`/files/${file.id}/preview`');
    expect(galleryCode).toContain('responseType: \'blob\'');
    expect(galleryCode).toContain('api.post(\'/files/upload\'');
    expect(galleryCode).toContain('\'permission\', \'private\'');
    expect(galleryCode).toContain('dermatology,photo,');
    // Никаких альтернативных источников: ЭМК specialty_data и прямые URL не используются
    expect(galleryCode).not.toContain('specialty_data');
    expect(galleryCode).not.toContain('/download');
  });

  it('frees temporary object urls on identity change and unmount', () => {
    expect(gallery).toContain('URL.revokeObjectURL');
    expect(gallery).toContain('releaseObjectUrls');
  });

  it('keeps category tags осмотр/до/после in the existing file tags', () => {
    expect(gallery).toContain('\'examination\'');
    expect(gallery).toContain('\'before\'');
    expect(gallery).toContain('\'after\'');
    expect(gallery).toContain('dermaPhotoCategoryOf');
  });

  it('removes the File/blob: pseudo-upload from EMR specialty data', () => {
    const stripComments = (src: string) => src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    const sectionCode = stripComments(dermatologySection);
    const emrCode = stripComments(emr);
    expect(sectionCode).not.toContain('photos');
    expect(sectionCode).not.toContain('File');
    expect(sectionCode).not.toContain('URL.createObjectURL');
    expect(sectionCode).not.toContain('useEMRAI');
    expect(sectionCode).not.toContain('type="file"');
    expect(emrCode).not.toContain('photos={');
    expect(emrCode).not.toContain('DermatologyPhoto');
    // Старые blob: значения не мигрируются: в секции нет их чтения
    expect(sectionCode).not.toContain('blob:');
  });

  it('retires the unreachable photos tab and legacy photo components', () => {
    expect(panel).not.toContain('activeTab === \'photos\'');
    expect(panel).not.toContain('DermaPhotosTab');
    expect(panel).not.toContain('photoData');
    const retired = [
      'components/dermatology/DermaPhotosTab.tsx',
      'components/dermatology/PhotoUploader.tsx',
      'components/dermatology/SkinAnalysis.tsx',
      'components/dermatology/PhotoComparison.tsx',
    ];
    for (const relative of retired) {
      expect(fs.existsSync(path.join(ROOT, relative))).toBe(false);
    }
  });

  it('does not auto-run AI analysis on upload (item 9 preview: click-only)', () => {
    expect(gallery).not.toContain('/ai/');
    expect(gallery).not.toContain('analyzeSkin');
    expect(gallery).not.toContain('useEMRAI');
  });
});
