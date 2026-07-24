#!/usr/bin/env node
/**
 * G7 Strict Gate — prevents strict-ready directories from regressing.
 *
 * Runs `tsc --noEmit -p tsconfig.strict.json` and fails if there are any
 * errors. This is the CI gate for Wave G7: directories listed in
 * tsconfig.strict.json must stay strict-clean.
 *
 * Usage:
 *   node scripts/strict-gate.mjs
 *
 * Exit codes:
 *   0 — strict-ready directories are clean
 *   1 — regression detected (new strict errors in ready directories)
 */

import { execSync } from 'child_process';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND_DIR = resolve(__dirname, '..', 'frontend');

console.log('G7 Strict Gate');
console.log('==============');
console.log('');
console.log('Checking directories in tsconfig.strict.json...');
console.log('');

try {
  const output = execSync(
    'npx tsc --noEmit --pretty false -p tsconfig.strict.json 2>&1',
    {
      cwd: FRONTEND_DIR,
      encoding: 'utf-8',
      maxBuffer: 1024 * 1024 * 20,
      stdio: ['pipe', 'pipe', 'pipe'],
    }
  );
  console.log('✅ Strict-ready directories are clean (0 errors).');
  console.log('');
  console.log('Directories currently under strict gate:');
  console.log('  - src/api/mappers/');
  console.log('  - src/types/domain/');
  console.log('  - src/types/              (G7-A: api-constants.ts typed)');
  console.log('  - src/api/client.ts       (G7-B: 7 strict fixes)');
  console.log('  - src/stores/             (G7-B: unblocked by client.ts)');
  console.log('  - src/api/labReporting.ts (G7-C: 20 params typed)');
  console.log('  - src/api/registrarBatch.ts (G7-C: 21 params + interfaces typed)');
  console.log('');
  console.log('To add a new directory: edit tsconfig.strict.json `include` array,');
  console.log('verify with `npx tsc --noEmit -p tsconfig.strict.json`, then commit.');
  process.exit(0);
} catch (e) {
  const output = e.stdout?.toString() || e.stderr?.toString() || '';
  const errorLines = output.split('\n').filter(l => l.includes('error TS'));
  console.log(`❌ ${errorLines.length} strict errors detected in ready directories!`);
  console.log('');
  console.log('This is a regression — the directories listed in tsconfig.strict.json');
  console.log('were previously strict-clean. Either fix the errors or remove the');
  console.log('offending file from tsconfig.strict.json `include`.');
  console.log('');
  console.log('First 10 errors:');
  for (const line of errorLines.slice(0, 10)) {
    console.log(`  ${line}`);
  }
  if (errorLines.length > 10) {
    console.log(`  ... and ${errorLines.length - 10} more`);
  }
  process.exit(1);
}
