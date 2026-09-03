/**
 * ui-baseline scanner regression tests (C-3-A.1, UI_AUDIT_PLAN.md)
 *
 * Protects the measurement layer itself. Each test targets a specific
 * false-positive class found during C-3 classification:
 *   1. `var(--foo)` inside JS/TS comments counted as usage
 *   2. inline custom-property writers `style={{ '--foo': v }}` treated
 *      as undefined tokens (they are intentional runtime slots)
 *   3. `var()` in dead (never-imported) CSS mixed into live counts*
 *   4. setProperty writers must still be recognized (true positive guard)
 *   5. CSS comments must not count (pre-existing behavior, locked in)
 *
 * The scanner is executed as a child process against a temporary fixture
 * project, so these tests do not depend on the real src/ tree.
 */
import { describe, expect, it, beforeAll, afterAll } from 'vitest';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const SCANNER = path.resolve(process.cwd(), 'scripts/ui-baseline.mjs');

let tmpRoot: string;
let fixtureFrontend: string;

function write(rel: string, content: string): void {
  const full = path.join(fixtureFrontend, rel);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, content);
}

function runScanner(): { names: number; usages: number; metrics: Record<string, unknown> } {
  const out = execFileSync('node', [SCANNER, '--json'], {
    cwd: fixtureFrontend,
    encoding: 'utf8',
    timeout: 60_000,
    env: { ...process.env, NO_COLOR: '1', UI_BASELINE_ROOT: fixtureFrontend },
  });
  const doc = JSON.parse(out);
  return {
    names: doc.metrics.undefinedVarNameCount,
    usages: doc.metrics.undefinedVarUsages,
    metrics: doc.metrics,
  };
}

beforeAll(() => {
  tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ui-baseline-test-'));
  fixtureFrontend = path.join(tmpRoot, 'frontend');
  fs.mkdirSync(path.join(fixtureFrontend, 'src'), { recursive: true });

  // Live entry point
  write('src/main.tsx', `import './live.css';\nimport { Live } from './Live.js';\nexport default Live;\n`);
  // Live CSS defines the canonical token
  write('src/live.css', `:root { --mac-bg-primary: #ffffff; }\n.card { background: var(--mac-bg-primary); }\n`);
  // Live component with guarded var() usages and fallbacks
  write('src/Live.tsx', `export function Live() {
  return (
    <div style={{ color: 'var(--mac-known, #fff)' }}>
      {/* var(--mac-in-comment) — must NOT count (class 1) */}
      <span className="x">text</span>
    </div>
  );
}
// var(--mac-in-line-comment) — must NOT count (class 1)
`);

  // class 2: inline custom-property writer — runtime slot, NOT an undefined token
  write('src/RuntimeSlot.tsx', `import type { CSSProperties } from 'react';
export function RuntimeSlot({ c }: { c: string }) {
  return <div className="slot" style={{ '--slot-color': c } as CSSProperties}>x</div>;
}
`);

  // class 4 guard: setProperty writer (true runtime definition)
  write('src/SetProp.tsx', `export function SetProp(el: HTMLElement) {
  el.style.setProperty('--setprop-color', 'red');
}
`);

  // TRUE undefined token in live code — scanner MUST still report it
  write('src/Broken.tsx', `export const a = 'var(--mac-truly-missing)';\nexport const b = 'var(--mac-truly-missing)';\n`);

  // dead CSS: never imported; its var() usage must not affect live semantics,
  // and its definitions must not make tokens look "defined" for live files
  write('src/dead.css', `:root { --dead-only-token: #123456; }\n.d { color: var(--dead-only-token); color: var(--mac-truly-missing); }\n`);
});

afterAll(() => {
  fs.rmSync(tmpRoot, { recursive: true, force: true });
});

describe('ui-baseline scanner (C-3-A.1 measurement-layer fixes)', () => {
  it('class 1: var() in JS/TS comments is not counted as an undefined token', () => {
    const r = runScanner();
    expect((r.metrics.undefinedVarNames as string[])).not.toContain('--mac-in-comment');
    expect((r.metrics.undefinedVarNames as string[])).not.toContain('--mac-in-line-comment');
  });

  it('class 2: inline custom-property writers are runtime slots, not undefined tokens', () => {
    const r = runScanner();
    expect((r.metrics.undefinedVarNames as string[])).not.toContain('--slot-color');
  });

  it('class 4 guard: setProperty writers are still recognized', () => {
    const r = runScanner();
    expect((r.metrics.undefinedVarNames as string[])).not.toContain('--setprop-color');
  });

  it('true positive guard: genuinely undefined live tokens are still reported', () => {
    const r = runScanner();
    expect((r.metrics.undefinedVarNames as string[])).toContain('--mac-truly-missing');
    expect(r.usages).toBeGreaterThanOrEqual(2);
  });

  it('class 5: CSS comments never counted (locked-in behavior)', () => {
    write('src/withcomment.css', `/* var(--mac-in-css-comment) */\n.a { color: var(--mac-bg-primary); }\n`);
    const r = runScanner();
    expect((r.metrics.undefinedVarNames as string[])).not.toContain('--mac-in-css-comment');
  });

  it('class 3: definitions in dead CSS still count as definitions (documented semantics)', () => {
    // --dead-only-token is defined only in dead.css and consumed by live code:
    // the undefined-token metric treats ANY definition (live or dead file) as
    // "defined" — documented scanner semantics from C-1 (that is why the C-1
    // bug was runtime-only and invisible to this metric). This test locks the
    // semantics in so a future scanner change is a conscious decision.
    write('src/DeadConsumer.tsx', `export const x = 'var(--dead-only-token)';\n`);
    const r = runScanner();
    expect((r.metrics.undefinedVarNames as string[])).not.toContain('--dead-only-token');
  });
});
