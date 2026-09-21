/**
 * NURSE-V2 N2-5 — source-level contracts for the tablet slice.
 *
 * - Generated types only: the tablet consumes the openapi-generated DTOs
 *   re-exported via `@/types/api` / `@/api/nurseServing` — no handwritten
 *   duplicate of a NurseServing* shape may appear in the page sources.
 * - PHI hygiene (§11): no console logging in the nurse serving sources —
 *   names/phones/reasons never reach the browser console; no client-side
 *   audit (the server UserAuditLog is the SSOT).
 * - No Visit-close semantics (§5): the tablet completes ServiceExecutions;
 *   nothing may close a Visit.
 */

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

const SOURCES = [
  'src/pages/nurse/NurseTabletPage.tsx',
  'src/pages/nurse/NurseStationBoard.tsx',
  'src/pages/nurse/NurseServiceList.tsx',
  'src/pages/nurse/NurseWorkplacePicker.tsx',
  'src/pages/nurse/NurseReasonForm.tsx',
  'src/pages/nurse/useNurseServingBoard.ts',
  'src/api/nurseServing.ts',
  'src/hooks/useNurseServingApi.ts',
];

const read = (path: string) => readFileSync(path, 'utf-8');

describe('NURSE-V2 N2-5 tablet — source contracts', () => {
  it('consumes generated DTOs — no handwritten NurseServing duplicates', () => {
    for (const source of SOURCES) {
      const code = read(source);
      // A handwritten duplicate would redeclare the transport shape.
      expect(
        code,
        `${source} must not hand-declare a NurseServing transport shape`,
      ).not.toMatch(
        /(?:interface|type)\s+(?:NurseServingWorkplace|NurseServingStation|NurseServingEntry|NurseServingExecution|NurseServingCallNext|NurseServingStart|NurseServingDraining)\w*(?:\s*=\s*\{|\s*\{)/,
      );
    }
    // The API module is the typed boundary over the generated schemas.
    const apiModule = read('src/api/nurseServing.ts');
    const typesApiMarker = 'from \'@/types/api\'';
    expect(apiModule).toContain(typesApiMarker);
    expect(apiModule).toMatch(/NurseServingWorkplaceDto/);
    // The generated file carries the draining contract (N2-3 follow-up).
    const generated = read('src/types/generated/api.ts');
    expect(generated).toContain('NurseServingDrainingExecutionItem:');
    expect(generated).toContain('NurseServingStationServiceState:');
  });

  it('keeps PHI out of the browser console (§11)', () => {
    for (const source of SOURCES) {
      const code = read(source);
      expect(code, `${source} must not console.log`).not.toMatch(
        /\bconsole\.(log|info|debug|warn|error|trace)\s*\(/,
      );
    }
  });

  it('adds no client-side audit surface (§11 — server UserAuditLog is SSOT)', () => {
    for (const source of SOURCES) {
      const code = read(source);
      expect(code, `${source} must not audit client-side`).not.toMatch(
        /\b(?:auditLog|logAudit|trackEvent|analytics)\w*\s*\(/i,
      );
    }
  });

  it('closes no Visit anywhere (§5 — executions complete, visits stay open)', () => {
    for (const source of SOURCES) {
      const code = read(source);
      expect(code, `${source} must not close visits`).not.toMatch(
        /close[_ ]?visit|visit[_ ]?close|завершить\s+визит/i,
      );
      // §3: only the nurse-serving endpoints are called — no EMR/patient
      // fetches for a richer UI.
      expect(code).not.toMatch(/\/emr\/|\/patients\/|\/admin\//);
    }
    const apiModule = read('src/api/nurseServing.ts');
    // every URL is under /nurse/serving (the §3 allow-list: 10 operations)
    const urls = (apiModule.match(/['`](\/nurse\/serving[^'`]*)['`]/g) ?? []).map(
      (quoted) => quoted.slice(1, -1),
    );
    expect(urls.length).toBe(10);
    expect(urls.every((url) => url.startsWith('/nurse/serving'))).toBe(true);
  });
});
