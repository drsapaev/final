// @vitest-environment node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const scriptPath = path.join(frontendRoot, 'scripts', 'audit-icon-only-controls.mjs');

function runAudit(source: string, extraArgs: string[] = [], extraFiles: Record<string, string> = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'icon-audit-'));

  try {
    fs.writeFileSync(path.join(root, 'Example.tsx'), source);
    for (const [name, content] of Object.entries(extraFiles)) {
      fs.writeFileSync(path.join(root, name), content);
    }

    const result = spawnSync(
      process.execPath,
      [scriptPath, `--root=${root}`, '--format=json', ...extraArgs],
      {
        cwd: frontendRoot,
        encoding: 'utf8',
      },
    );

    if (result.error) {
      throw result.error;
    }

    return {
      status: result.status,
      stderr: result.stderr,
      report: JSON.parse(result.stdout),
      root,
    };
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

function runAuditRoot(root: string, extraArgs: string[] = []) {
  const result = spawnSync(
    process.execPath,
    [scriptPath, `--root=${root}`, '--format=json', ...extraArgs],
    {
      cwd: frontendRoot,
      encoding: 'utf8',
    },
  );

  if (result.error) {
    throw result.error;
  }

  return {
    status: result.status,
    stderr: result.stderr,
    report: JSON.parse(result.stdout),
  };
}

describe('icon-only controls accessibility audit', () => {
  it('flags an icon-only native button without an accessible name', () => {
    const { report } = runAudit(`
      export function Example() {
        return <button type="button"><XIcon /></button>;
      }
    `);

    expect(report.findings).toHaveLength(1);
    expect(report.findings[0]).toMatchObject({
      element: 'button',
      reason: 'missing-accessible-name',
    });
  });

  it('flags title-only icon buttons because title is not a robust control name', () => {
    const { report } = runAudit(`
      export function Example() {
        return <button type="button" title="Close"><XIcon /></button>;
      }
    `);

    expect(report.findings).toHaveLength(1);
    expect(report.findings[0]).toMatchObject({
      reason: 'title-only',
    });
  });

  it('accepts native buttons with aria-label', () => {
    const { report } = runAudit(`
      export function Example() {
        return <button type="button" aria-label="Close"><XIcon /></button>;
      }
    `);

    expect(report.findings).toEqual([]);
  });

  it('accepts native buttons with visible text', () => {
    const { report } = runAudit(`
      export function Example() {
        return <button type="button"><XIcon /> Close</button>;
      }
    `);

    expect(report.findings).toEqual([]);
  });

  it('flags project Button components when explicitly included', () => {
    const { report } = runAudit(
      `
        export function Example() {
          return <Button type="button"><XIcon /></Button>;
        }
      `,
      ['--include-components'],
    );

    expect(report.findings).toHaveLength(1);
    expect(report.findings[0]).toMatchObject({
      element: 'Button',
      reason: 'missing-accessible-name',
    });
  });

  it('accepts project Button components with accessible names when explicitly included', () => {
    const { report } = runAudit(
      `
        export function Example() {
          return <Button type="button" aria-label="Close"><XIcon /></Button>;
        }
      `,
      ['--include-components'],
    );

    expect(report.findings).toEqual([]);
  });

  it('does not flag project Button components unless component mode is enabled', () => {
    const { report } = runAudit(`
      export function Example() {
        return <Button type="button"><XIcon /></Button>;
      }
    `);

    expect(report.findings).toEqual([]);
  });

  it('accepts native buttons with screen-reader-only text components', () => {
    const { report } = runAudit(`
      export function Example() {
        return <button type="button"><XIcon /><VisuallyHidden>Close</VisuallyHidden></button>;
      }
    `);

    expect(report.findings).toEqual([]);
  });

  it('flags interactive role controls without a control name', () => {
    const { report } = runAudit(`
      export function Example() {
        return <div role="button" tabIndex={0}><XIcon /></div>;
      }
    `);

    expect(report.findings).toHaveLength(1);
    expect(report.findings[0]).toMatchObject({
      element: 'div',
      reason: 'missing-accessible-name',
    });
  });

  it('reports only findings not covered by the current baseline', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'icon-audit-'));

    try {
      fs.writeFileSync(
        path.join(root, 'Example.tsx'),
        `
        export function Example() {
          return (
            <>
              <button type="button"><XIcon /></button>
              <button type="button" title="Close"><XIcon /></button>
            </>
          );
        }
      `,
      );
      const first = runAuditRoot(root);
      const baselinePath = path.join(root, 'baseline.json');
      fs.writeFileSync(
        baselinePath,
        JSON.stringify({ entries: [{ signature: first.report.findings[0].signature }] }),
      );

      const second = runAuditRoot(root, [`--baseline=${baselinePath}`]);

      expect(second.report.newFindings).toHaveLength(1);
      expect(second.report.newFindings[0]).toMatchObject({
        reason: 'title-only',
      });
      expect(second.report.staleBaselineEntries).toEqual([]);
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });
});
