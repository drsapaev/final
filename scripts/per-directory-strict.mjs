#!/usr/bin/env node
/**
 * Per-directory strict-mode error count.
 *
 * Runs `tsc --noEmit` with strict flags enabled on a SINGLE directory
 * at a time, so we can see which directories are ready for strict: true
 * and which still have debt.
 *
 * Usage:
 *   node scripts/per-directory-strict.mjs              # check all directories
 *   node scripts/per-directory-strict.mjs src/api      # check one directory
 *
 * Output: per-directory error count + total.
 */

import { execSync } from 'child_process';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { readFileSync, writeFileSync, existsSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND_DIR = resolve(__dirname, '..', 'frontend');
const TSCONFIG_PATH = resolve(FRONTEND_DIR, 'tsconfig.json');

const DIRECTORIES = [
  'src/api/mappers',
  'src/api',
  'src/types/domain',
  'src/types',
  'src/hooks',
  'src/stores',
  'src/utils',
  'src/contexts',
  'src/components/ui',
  'src/components/common',
  'src/components',
  'src/pages',
  'src/routing',
  'src/services',
];

function countStrictErrorsForDir(dir) {
  const originalConfig = readFileSync(TSCONFIG_PATH, 'utf-8');
  try {
    // Create a temporary tsconfig that:
    // 1. Enables strict: true (which enables noImplicitAny, strictNullChecks, etc.)
    // 2. Includes ONLY the target directory
    const strictConfig = {
      extends: './tsconfig.json',
      compilerOptions: {
        strict: true,
        noImplicitAny: true,
        strictNullChecks: true,
      },
      include: [`${dir}/**/*.ts`, `${dir}/**/*.tsx`],
      exclude: ['node_modules', 'dist', 'e2e'],
    };

    const strictConfigPath = resolve(FRONTEND_DIR, 'tsconfig.strict-tmp.json');
    writeFileSync(strictConfigPath, JSON.stringify(strictConfig, null, 2));

    try {
      const output = execSync(
        `npx tsc --noEmit --pretty false -p tsconfig.strict-tmp.json 2>&1`,
        {
          cwd: FRONTEND_DIR,
          encoding: 'utf-8',
          maxBuffer: 1024 * 1024 * 20,
          stdio: ['pipe', 'pipe', 'pipe'],
        }
      );
      return { errors: 0, output: '' };
    } catch (e) {
      const output = e.stdout?.toString() || e.stderr?.toString() || '';
      const errorLines = output.split('\n').filter(l => l.includes('error TS'));
      return { errors: errorLines.length, output };
    } finally {
      // Clean up temp config
      if (existsSync(strictConfigPath)) {
        try { require('fs').unlinkSync(strictConfigPath); } catch {}
      }
    }
  } finally {
    writeFileSync(TSCONFIG_PATH, originalConfig);
  }
}

// Hack: use fs.unlinkSync directly (the `require` above doesn't work in ESM)
import { unlinkSync } from 'fs';

const targetDir = process.argv[2];
const dirs = targetDir ? [targetDir] : DIRECTORIES;

console.log('Per-directory strict-mode error count');
console.log('======================================');
console.log('');
console.log('  Directory                       Errors    Status');
console.log('  -----------------------------------------------------');

let total = 0;
const results = [];
for (const dir of dirs) {
  const { errors } = countStrictErrorsForDir(dir);
  const status = errors === 0 ? '✅ READY' : errors < 20 ? '🟡 CLOSE' : '❌ DEBT';
  console.log(`  ${dir.padEnd(32)} ${String(errors).padStart(6)}    ${status}`);
  total += errors;
  results.push({ dir, errors });
}

console.log('  -----------------------------------------------------');
console.log(`  ${'TOTAL'.padEnd(32)} ${String(total).padStart(6)}`);
console.log('');

const ready = results.filter(r => r.errors === 0);
const close = results.filter(r => r.errors > 0 && r.errors < 20);
const debt = results.filter(r => r.errors >= 20);

console.log(`Ready for strict (0 errors): ${ready.length}/${results.length}`);
for (const r of ready) console.log(`  ✅ ${r.dir}`);
console.log('');
console.log(`Close (<20 errors): ${close.length}/${results.length}`);
for (const r of close) console.log(`  🟡 ${r.dir} (${r.errors} errors)`);
console.log('');
console.log(`Debt (>=20 errors): ${debt.length}/${results.length}`);
for (const r of debt) console.log(`  ❌ ${r.dir} (${r.errors} errors)`);
