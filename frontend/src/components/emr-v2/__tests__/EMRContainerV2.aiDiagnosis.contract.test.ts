/**
 * EMRAI-FE-001 + EMRPROGRESS-FE-001 (audit 3886, round 27) — fail-first,
 * source-contract style (precedent: EMRContainerV2.lifecycle.contract.test.ts).
 *
 * EMRAI-FE-001: buildAiCacheKey called `(data?.diagnosis || '').trim()` —
 * but the canonical new-record draft seeds the STRUCTURED diagnosis object
 * {main, icd10_code, secondary[]}. Calling .trim() on it throws TypeError
 * BEFORE handleRequestAI's try block, so every AI suggestion request for a
 * new EMR crashed before the network call. The ICD-10 request body also
 * passed the raw object (or `data?.diagnosis || ''`) instead of the
 * normalized diagnosis text.
 *
 * EMRPROGRESS-FE-001: the seven-step progress banner used
 * `!!(data?.x || fieldText(data?.x))` — a truthy EMPTY diagnosis object
 * ({main:''}) reported «Диагноз» as filled (1/7 with no diagnosis), and
 * whitespace-only strings passed the raw truthiness check.
 *
 * Contract after the fix: the AI key builder and every AI request body route
 * through the canonical emrTextValue selector (already unit-tested in
 * emrCompletion.test.ts); the progress rows count only trimmed, meaningful
 * clinical text.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.join(__dirname, '../EMRContainerV2.tsx'), 'utf8');
const diagnosisSectionSource = fs.readFileSync(path.join(__dirname, '../sections/DiagnosisSection.tsx'), 'utf8');

describe('EMRAI-FE-001: structured diagnosis never crashes the AI request path', () => {
    it('R26: no raw string-method call on data.diagnosis / data.complaints remains in the AI path', () => {
        expect(source).not.toMatch(/\(data\?\.(diagnosis|complaints) \|\| ''\)\.trim\(\)/);
        expect(source).not.toMatch(/data\?\.(diagnosis|complaints)\.substring/);
    });

    it('R27: buildAiCacheKey normalizes both clinical texts through emrTextValue', () => {
        const m = source.match(/const buildAiCacheKey = useCallback\(\(fieldName: string\) => \{[\s\S]*?\n {4}\}, \[/);
        expect(m).not.toBeNull();
        expect(m![0]).toContain('emrTextValue(data?.complaints)');
        expect(m![0]).toContain('emrTextValue(data?.diagnosis)');
    });

    it('R28: the ICD-10 request body sends the normalized diagnosis text, never the object', () => {
        const m = source.match(/mcpAPI\.suggestICD10\(\{[\s\S]*?\}, requestOptions\)/);
        expect(m).not.toBeNull();
        // the diagnosis text is produced by the canonical selector…
        const icdCase = source.match(/case 'diagnosis': \{[\s\S]*?break;/);
        expect(icdCase).not.toBeNull();
        expect(icdCase![0]).toContain('emrTextValue(data?.diagnosis)');
        expect(icdCase![0]).toContain('emrTextValue(data?.complaints)');
        // …and the request body carries that text, not the raw object
        expect(m![0]).toMatch(/diagnosis: (diagnosisText|emrTextValue\(data\?\.diagnosis\))/);
        expect(m![0]).not.toContain('diagnosis: data?.diagnosis || \'\'');
        expect(m![0]).not.toContain('symptoms: data?.complaints ? [data?.complaints]');
    });

    it('R29: the complaint-analysis request body sends the normalized complaint text', () => {
        const m = source.match(/mcpAPI\.analyzeComplaint\(\{[\s\S]*?\}, requestOptions\)/);
        expect(m).not.toBeNull();
        expect(m![0]).not.toContain('complaint: data?.complaints');
        expect(m![0]).toMatch(/complaint: (complaintsText|emrTextValue\(data\?\.complaints\))/);
    });

    it('C30 (control): the cache key still folds specialty, age and gender', () => {
        const m = source.match(/const buildAiCacheKey = useCallback\(\(fieldName: string\) => \{[\s\S]*?\n {4}\}, \[/);
        expect(m![0]).toContain("data?.specialty || 'general'"); // eslint-disable-line quotes
        expect(m![0]).toContain('patientAge');
        expect(m![0]).toContain('patientGender');
    });
});

describe('EMRPROGRESS-FE-001: progress counts only meaningful clinical text', () => {
    it('R31: no generic JSON-object truthiness remains in the progress rows', () => {
        expect(source).not.toMatch(/filled: !!\(data\?\.\w+ \|\| fieldText\(data\?\.\w+\)\)\)/);
        expect(source).not.toContain('function fieldText');
    });

    it('R32: all seven progress rows use the trimmed canonical text selector', () => {
        const rows = source.match(/filled: emrTextValue\(data\?\.\w+\)\.trim\(\) !== ''/g);
        expect(rows).not.toBeNull();
        expect(rows!.length).toBe(7);
    });
});

describe('shared selector wiring (single canonical selector, per the repair direction)', () => {
    it('R33: DiagnosisSection reads the same canonical selector instead of a private copy', () => {
        expect(diagnosisSectionSource).toContain('emrTextValue');
        expect(diagnosisSectionSource).not.toContain('function normalizeTextValue');
    });
});
