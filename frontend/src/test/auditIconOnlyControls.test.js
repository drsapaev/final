import { describe, expect, it } from 'vitest';

import {
  applyBaseline,
  auditCode,
  findingSignature,
} from '../../scripts/audit-icon-only-controls.mjs';

describe('icon-only controls accessibility audit', () => {
  it('flags an icon-only native button without an accessible name', () => {
    const findings = auditCode(
      `
        export function Example() {
          return <button type="button"><XIcon /></button>;
        }
      `,
      'Example.jsx',
    );

    expect(findings).toHaveLength(1);
    expect(findings[0]).toMatchObject({
      element: 'button',
      reason: 'missing-accessible-name',
    });
  });

  it('flags title-only icon buttons because title is not a robust control name', () => {
    const findings = auditCode(
      `
        export function Example() {
          return <button type="button" title="Close"><XIcon /></button>;
        }
      `,
      'Example.jsx',
    );

    expect(findings).toHaveLength(1);
    expect(findings[0]).toMatchObject({
      reason: 'title-only',
    });
  });

  it('accepts native buttons with aria-label', () => {
    const findings = auditCode(
      `
        export function Example() {
          return <button type="button" aria-label="Close"><XIcon /></button>;
        }
      `,
      'Example.jsx',
    );

    expect(findings).toEqual([]);
  });

  it('accepts native buttons with visible text', () => {
    const findings = auditCode(
      `
        export function Example() {
          return <button type="button"><XIcon /> Close</button>;
        }
      `,
      'Example.jsx',
    );

    expect(findings).toEqual([]);
  });

  it('accepts native buttons with screen-reader-only text components', () => {
    const findings = auditCode(
      `
        export function Example() {
          return <button type="button"><XIcon /><VisuallyHidden>Close</VisuallyHidden></button>;
        }
      `,
      'Example.jsx',
    );

    expect(findings).toEqual([]);
  });

  it('flags interactive role controls without a control name', () => {
    const findings = auditCode(
      `
        export function Example() {
          return <div role="button" tabIndex={0}><XIcon /></div>;
        }
      `,
      'Example.jsx',
    );

    expect(findings).toHaveLength(1);
    expect(findings[0]).toMatchObject({
      element: 'div',
      reason: 'missing-accessible-name',
    });
  });

  it('reports only findings not covered by the current baseline', () => {
    const findings = [
      {
        file: 'src/Example.jsx',
        line: 1,
        column: 1,
        element: 'button',
        reason: 'missing-accessible-name',
      },
      {
        file: 'src/Example.jsx',
        line: 2,
        column: 1,
        element: 'button',
        reason: 'title-only',
      },
    ];
    const result = {
      filesScanned: 1,
      findings: findings.map((finding) => ({
        ...finding,
        signature: findingSignature(finding),
      })),
      parseErrors: [],
    };

    const gated = applyBaseline(result, [result.findings[0].signature]);

    expect(gated.newFindings).toEqual([result.findings[1]]);
    expect(gated.staleBaselineEntries).toEqual([]);
  });
});
