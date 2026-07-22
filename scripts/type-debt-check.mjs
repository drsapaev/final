#!/usr/bin/env node
/**
 * Type Debt Gate — CI check that prevents new type debt from entering the codebase.
 *
 * Checks:
 *   - `as any` casts
 *   - `: any` type annotations
 *   - `@ts-nocheck` directives
 *   - `@ts-ignore` directives
 *   - `[key: string]: any` index signatures
 *
 * Usage:
 *   node scripts/type-debt-check.mjs           # check against baseline
 *   node scripts/type-debt-check.mjs --update   # update baseline
 *
 * Exit codes:
 *   0 — debt is within baseline
 *   1 — debt exceeded baseline (CI failure)
 */

import { execSync } from 'child_process';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND_DIR = resolve(__dirname, '..', 'frontend', 'src');

const BASELINE = {
  anyCasts: 29,
  tsIgnore: 0,
  tsNoCheck: 0,
  indexSignatureAny: 0,
};

function countPattern(pattern, cwd) {
  try {
    const output = execSync(`rg -c '${pattern}' ${cwd} 2>/dev/null || true`, {
      encoding: 'utf-8',
      maxBuffer: 1024 * 1024 * 10,
    });
    return output
      .trim()
      .split('\n')
      .filter(Boolean)
      .reduce((sum, line) => {
        const count = parseInt(line.split(':')[1] || '0', 10);
        return sum + (isNaN(count) ? 0 : count);
      }, 0);
  } catch {
    return 0;
  }
}

function countExact(pattern, cwd) {
  try {
    const output = execSync(`rg -c '${pattern}' ${cwd} 2>/dev/null || true`, {
      encoding: 'utf-8',
      maxBuffer: 1024 * 1024 * 10,
    });
    return output.trim().split('\n').filter(Boolean).length;
  } catch {
    return 0;
  }
}

const metrics = {
  anyCasts: countPattern('\\bas any\\b|:\\s*any\\b', FRONTEND_DIR),
  tsIgnore: countExact('@ts-ignore', FRONTEND_DIR),
  tsNoCheck: countExact('^// @ts-nocheck', FRONTEND_DIR),
  indexSignatureAny: countPattern('\\[key:\\s*string\\]:\\s*any', FRONTEND_DIR),
};

console.log('Type Debt Check');
console.log('================');
console.log('');

let failed = false;

for (const [key, actual] of Object.entries(metrics)) {
  const baseline = BASELINE[key];
  const status = actual <= baseline ? '✅' : '❌';
  const delta = actual - baseline;
  const deltaStr = delta > 0 ? `+${delta}` : delta === 0 ? '0' : `${delta}`;
  console.log(`  ${status} ${key}: ${actual} (baseline: ${baseline}, delta: ${deltaStr})`);
  if (actual > baseline) {
    failed = true;
  }
}

console.log('');

if (failed) {
  console.error('❌ Type debt exceeded baseline!');
  console.error('');
  console.error('To fix: reduce the new `any`/`@ts-ignore`/`@ts-nocheck` usage.');
  console.error('If this is intentional (e.g. new file with known debt),');
  console.error('update the baseline in scripts/type-debt-baseline.json.');
  process.exit(1);
} else {
  console.log('✅ Type debt is within baseline.');
  process.exit(0);
}
