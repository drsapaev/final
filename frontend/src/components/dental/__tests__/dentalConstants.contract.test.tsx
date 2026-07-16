import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');

const readSource = (fileName) =>
  fs.readFileSync(path.join(ROOT, fileName), 'utf8').replace(/\r\n/g, '\n');

describe('dental SSOT contract (dentalConstants.ts)', () => {
  it('exposes the canonical TOOTH_STATUS values that persist into EMR JSONB', () => {
    const source = readSource('dentalConstants.ts');

    // These values are stored in specialty_data.tooth_status[toothNumber].status
    // in the EMR v2 JSONB field. Changing any of them is a breaking backend
    // change — must be coordinated with a migration.
    expect(source).toContain('HEALTHY: \'healthy\'');
    expect(source).toContain('CARIES: \'caries\'');
    expect(source).toContain('FILLED: \'filled\'');
    expect(source).toContain('CROWN: \'crown\'');
    expect(source).toContain('IMPLANT: \'implant\'');
    expect(source).toContain('MISSING: \'missing\'');
    expect(source).toContain('ROOT: \'root\'');
    expect(source).toContain('BRIDGE: \'bridge\'');
  });

  it('exposes the canonical TOOTH_PROCEDURES ids that persist into EMR JSONB', () => {
    const source = readSource('dentalConstants.ts');

    // Procedure ids are stored in tooth_status[toothNumber].procedures[].id
    expect(source).toContain('id: \'examination\'');
    expect(source).toContain('id: \'cleaning\'');
    expect(source).toContain('id: \'filling\'');
    expect(source).toContain('id: \'root_canal\'');
    expect(source).toContain('id: \'crown\'');
    expect(source).toContain('id: \'extraction\'');
    expect(source).toContain('id: \'implant\'');
    expect(source).toContain('id: \'bridge\'');
    expect(source).toContain('id: \'veneer\'');
  });

  it('marks prosthetic procedures with isProsthetic flag for UI branching', () => {
    const source = readSource('dentalConstants.ts');

    // Prosthetic procedures trigger the extra fields UI (shade/fit_quality/
    // warranty_period) in ToothModal. Non-prosthetic must NOT have the flag.
    expect(source).toContain('{ id: \'crown\',       name: \'Коронка\', price: 500000, isProsthetic: true }');
    expect(source).toContain('{ id: \'implant\',     name: \'Имплантация\', price: 1500000, isProsthetic: true }');
    expect(source).toContain('{ id: \'bridge\',      name: \'Мостовидный протез\', price: 800000, isProsthetic: true }');
    expect(source).toContain('{ id: \'veneer\',      name: \'Винир\', price: 600000, isProsthetic: true }');

    // Examination / cleaning / filling / root_canal / extraction must be false.
    expect(source).toContain('{ id: \'examination\', name: \'Осмотр\', price: 20000, isProsthetic: false }');
    expect(source).toContain('{ id: \'cleaning\',    name: \'Чистка\', price: 50000, isProsthetic: false }');
    expect(source).toContain('{ id: \'filling\',     name: \'Пломба\', price: 150000, isProsthetic: false }');
    expect(source).toContain('{ id: \'root_canal\',  name: \'Лечение каналов\', price: 300000, isProsthetic: false }');
    expect(source).toContain('{ id: \'extraction\',  name: \'Удаление\', price: 100000, isProsthetic: false }');
  });

  it('exposes MATERIALS ids that persist into EMR JSONB', () => {
    const source = readSource('dentalConstants.ts');

    expect(source).toContain('id: \'composite\'');
    expect(source).toContain('id: \'ceramic\'');
    expect(source).toContain('id: \'metal_ceramic\'');
    expect(source).toContain('id: \'zirconia\'');
    expect(source).toContain('id: \'gold\'');
  });

  it('exposes FDI adult and deciduous teeth numbering', () => {
    const source = readSource('dentalConstants.ts');

    // FDI numbering is international standard — must not drift.
    expect(source).toContain('upperRight: [18, 17, 16, 15, 14, 13, 12, 11]');
    expect(source).toContain('upperLeft:  [21, 22, 23, 24, 25, 26, 27, 28]');
    expect(source).toContain('lowerLeft:  [38, 37, 36, 35, 34, 33, 32, 31]');
    expect(source).toContain('lowerRight: [41, 42, 43, 44, 45, 46, 47, 48]');

    expect(source).toContain('upperRight: [55, 54, 53, 52, 51]');
    expect(source).toContain('upperLeft:  [61, 62, 63, 64, 65]');
    expect(source).toContain('lowerLeft:  [75, 74, 73, 72, 71]');
    expect(source).toContain('lowerRight: [81, 82, 83, 84, 85]');
  });

  it('TeethChart.jsx imports constants from dentalConstants (no local redefinition)', () => {
    const source = readSource('TeethChart.tsx');

    expect(source).toContain('from \'./dentalConstants\'');
    expect(source).toContain('TOOTH_STATUS');
    expect(source).toContain('TOOTH_STATUS_COLORS as STATUS_COLORS');
    expect(source).toContain('TOOTH_STATUS_LABELS as STATUS_NAMES');
    expect(source).toContain('ADULT_TEETH as TEETH_NUMBERS');

    // Must NOT redefine these locally — that's the whole point of SSOT.
    expect(source).not.toContain('const TOOTH_STATUS = {');
    expect(source).not.toContain('const STATUS_COLORS = {');
    expect(source).not.toContain('const STATUS_NAMES = {');
    expect(source).not.toContain('const TEETH_NUMBERS = {');
  });

  it('ToothModal.jsx imports procedures/materials from dentalConstants (no local redefinition)', () => {
    const source = readSource('ToothModal.tsx');

    expect(source).toContain('from \'./dentalConstants\'');
    expect(source).toContain('TOOTH_PROCEDURES');
    expect(source).toContain('MATERIALS');
    expect(source).toContain('getToothName as ssotGetToothName');

    // Must NOT redefine these locally — that's the whole point of SSOT.
    expect(source).not.toContain('const TOOTH_PROCEDURES = {');
    expect(source).not.toContain('const MATERIALS = {');

    // Must NOT redefine the tooth-names map locally — SSOT owns it.
    expect(source).not.toContain('11: \'Центральный резец\'');
    expect(source).not.toContain('18: \'Третий моляр (зуб мудрости)\'');
  });
});
