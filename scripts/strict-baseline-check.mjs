#!/usr/bin/env node
/**
 * Strict Baseline Check — prevents strict-mode error regression.
 *
 * Runs `tsc --noEmit` with `noImplicitAny: true` and `strictNullChecks: true`
 * (temporarily, via tsconfig override) and verifies the error count does not
 * exceed the baseline in `scripts/strict-baseline.json`.
 *
 * This allows incremental strict-mode migration (Phase G) without blocking
 * development: existing errors are grandfathered, but new errors fail CI.
 *
 * Usage:
 *   node scripts/strict-baseline-check.mjs           # check against baseline
 *   node scripts/strict-baseline-check.mjs --update   # update baseline
 *
 * Exit codes:
 *   0 — error counts within baseline
 *   1 — error count exceeded baseline (CI failure)
 */

import { execSync } from 'child_process';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { readFileSync, writeFileSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND_DIR = resolve(__dirname, '..', 'frontend');
const TSCONFIG_PATH = resolve(FRONTEND_DIR, 'tsconfig.json');
const BASELINE_PATH = resolve(__dirname, 'strict-baseline.json');

const baseline = JSON.parse(readFileSync(BASELINE_PATH, 'utf-8'));

function countErrorsWithFlag(flag) {
  // Read original tsconfig, temporarily inject the flag, run tsc, restore.
  const originalConfig = readFileSync(TSCONFIG_PATH, 'utf-8');
  try {
    // Inject the flag right after "strict": false
    let modified = originalConfig.replace(
      /"strict":\s*false,/,
      `"strict": false,\n    "${flag}": true,`
    );
    // Remove noImplicitAny: false if present (it conflicts)
    modified = modified.replace(/"noImplicitAny":\s*false,\n?/, '');
    writeFileSync(TSCONFIG_PATH, modified);

    // Run tsc and count errors
    const output = execSync('npx tsc --noEmit --pretty false 2>&1', {
      cwd: FRONTEND_DIR,
      encoding: 'utf-8',
      maxBuffer: 1024 * 1024 * 20,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    const errorLines = output.split('\n').filter(l => l.includes('error TS'));
    return errorLines.length;
  } catch (e) {
    // tsc exits with code 1 when there are errors — that's expected
    const output = e.stdout?.toString() || e.stderr?.toString() || '';
    const errorLines = output.split('\n').filter(l => l.includes('error TS'));
    return errorLines.length;
  } finally {
    // Always restore original tsconfig
    writeFileSync(TSCONFIG_PATH, originalConfig);
  }
}

const isUpdate = process.argv.includes('--update');

console.log('Strict Baseline Check');
console.log('======================');
console.log('');

let failed = false;

for (const flag of ['noImplicitAny', 'strictNullChecks']) {
  const baselineCount = baseline.flags[flag]?.totalErrors ?? 0;
  console.log(`Checking ${flag}...`);
  const actualCount = countErrorsWithFlag(flag);
  const status = actualCount <= baselineCount ? '✅' : '❌';
  const delta = actualCount - baselineCount;
  const deltaStr = delta > 0 ? `+${delta}` : delta === 0 ? '0' : `${delta}`;
  console.log(`  ${status} ${flag}: ${actualCount} errors (baseline: ${baselineCount}, delta: ${deltaStr})`);

  if (isUpdate) {
    baseline.flags[flag].totalErrors = actualCount;
  } else if (actualCount > baselineCount) {
    failed = true;
  }
}

console.log('');

if (isUpdate) {
  baseline.generatedAt = new Date().toISOString().split('T')[0];
  writeFileSync(BASELINE_PATH, JSON.stringify(baseline, null, 2) + '\n');
  console.log('✅ Baseline updated in scripts/strict-baseline.json');
  process.exit(0);
}

if (failed) {
  console.error('❌ Strict baseline exceeded!');
  console.error('');
  console.error('To fix: reduce the new strict-mode errors in your changed files.');
  console.error('If this is intentional, update the baseline:');
  console.error('  node scripts/strict-baseline-check.mjs --update');
  process.exit(1);
} else {
  console.log('✅ Strict baseline is within tolerance.');
  console.log('');
  console.log('Note: These errors are grandfathered implicit-any / null-safety debt.');
  console.log('Phase G (see ADR-0012) will address them incrementally.');
  process.exit(0);
}
