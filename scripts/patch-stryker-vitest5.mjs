// Patch @stryker-mutator/vitest-runner 10.0.0 for vitest 5.
//
// Vitest 5 changed testNamePattern matching: the pattern is matched against
// the full suite chain joined with " > " (task-utils createTaskName), while
// StrykerJS 10.0.0 joins the chain with a plain space. Every per-mutant test
// filter therefore matched zero tests, no scoped mutant was ever executed and
// the whole score collapsed to its static mutants only (frontend nightly:
// 70%+ -> 8.6% on 2026-10-08..23). Upstream fix: stryker-js#6210 / PR #6214
// (Stryker 10.1.0) — not on npm yet, so this applies the same change locally.
//
// collectTestName exists in TWO dist files with distinct roles (filter/test
// ids in test-helpers.js, per-test coverage keys in stryker-setup.js); both
// must be patched or coverage mapping breaks (see stryker-js#6210 comments).
//
// Idempotent: skips files already patched; exits non-zero only if the
// expected code is missing entirely (upstream layout changed — re-evaluate
// the patch instead of silently running unpatched).
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
  'frontend',
);
const runnerRoot = path.join(
  frontendRoot,
  'node_modules',
  '@stryker-mutator',
  'vitest-runner',
  'dist',
  'src',
);

const ORIGINAL = "return nameParts.join(' ').trim();";
const PATCHED = "return nameParts.filter((part) => part !== '').join(' > ').trim();";

const targets = ['test-helpers.js', 'stryker-setup.js'].map((name) => path.join(runnerRoot, name));

for (const file of targets) {
  let source;
  try {
    source = readFileSync(file, 'utf8');
  } catch (error) {
    console.error(
      `[patch-stryker-vitest5] Cannot read ${file}. Install @stryker-mutator/vitest-runner first.`,
    );
    process.exit(1);
  }
  if (source.includes(PATCHED)) {
    console.log(`[patch-stryker-vitest5] Already patched: ${path.basename(file)}`);
    continue;
  }
  if (!source.includes(ORIGINAL)) {
    console.error(
      `[patch-stryker-vitest5] Expected collectTestName body not found in ${path.basename(file)} — ` +
        'the runner layout changed; re-check stryker-js#6210 before forcing this patch.',
    );
    process.exit(1);
  }
  writeFileSync(file, source.replace(ORIGINAL, PATCHED));
  console.log(`[patch-stryker-vitest5] Patched: ${path.basename(file)}`);
}
