#!/usr/bin/env node
/**
 * pii-fixture-guard.mjs
 *
 * CI gate that verifies test fixtures do not contain real-looking PII
 * (phone numbers) that violate AGENTS.md PII policy.
 *
 * AGENTS.md L377: "Test fixtures committed to the repo" must not
 * contain plaintext PII.
 * AGENTS.md L451: "Never commit fixtures containing real-looking
 * names + phone numbers."
 *
 * Canonical synthetic phone: +998900000000 (valid Uzbek format,
 * all zeros, clearly non-routable).
 *
 * Modes:
 *   --check-all     Scan ALL files (exit 1 if any violation)
 *   --check-changed Scan only git-changed files (exit 1 if violation in changed file)
 *   default         Scan ALL files, fail only if violations EXCEED baseline
 *
 * Exceptions (files that TEST the PII mechanism itself):
 *   test_validators.py, test_sentry_sanitization.py, test_pii_masker.py,
 *   test_error_logging.py, test_json_log_formatter.py,
 *   test_telegram_notifications_privacy.py, test_pr31_pii_masking.py,
 *   test_telegram_staff_read_only_menu_runtime.py
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const REPO = resolve(__dirname, '..');

const mode = process.argv.includes('--check-all') ? 'strict'
  : process.argv.includes('--check-changed') ? 'changed'
  : 'baseline';

const SCAN_DIRS = ['backend/tests', 'frontend/e2e'];
const EXTS = ['.py', '.ts', '.js'];

const EXEMPT_FILES = new Set([
  'backend/tests/test_validators.py',
  'backend/tests/unit/test_sentry_sanitization.py',
  'backend/tests/unit/test_pii_masker.py',
  'backend/tests/unit/test_error_logging.py',
  'backend/tests/unit/test_json_log_formatter.py',
  'backend/tests/unit/test_telegram_notifications_privacy.py',
  'backend/tests/integration/test_pr31_pii_masking.py',
  'backend/tests/unit/test_telegram_staff_read_only_menu_runtime.py',
]);

const REAL_LOOKING_PHONE = /\+9989\d[1-9]\d{6}/;
const CANONICAL_SYNTHETIC = new Set([
  '+998900000000', '+998900000001', '+998900000002', '+998900000003',
]);

// Baseline: pre-existing violations before this guard was added.
// New violations ABOVE this baseline cause CI failure.
const BASELINE_VIOLATIONS = 127;

let violations = 0;
let filesScanned = 0;
const violationList = [];

function scanFile(filePath, relPath) {
  if (EXEMPT_FILES.has(relPath.replace(/\\/g, '/'))) return;
  let content;
  try { content = readFileSync(filePath, 'utf-8'); } catch { return; }
  const lines = content.split('\n');
  lines.forEach((line, idx) => {
    const trimmed = line.trim();
    if (trimmed.startsWith('#') || trimmed.startsWith('//') || trimmed.startsWith('*')) return;
    const match = line.match(REAL_LOOKING_PHONE);
    if (match && !CANONICAL_SYNTHETIC.has(match[0])) {
      violations++;
      violationList.push({ file: relPath, line: idx + 1, phone: match[0], text: trimmed.substring(0, 120) });
    }
  });
}

function scanDir(dirPath, relDir) {
  let entries;
  try { entries = readdirSync(dirPath); } catch { return; }
  for (const entry of entries) {
    const fullPath = join(dirPath, entry);
    const relPath = join(relDir, entry);
    const stat = statSync(fullPath);
    if (stat.isDirectory()) scanDir(fullPath, relPath);
    else if (EXTS.some((ext) => entry.endsWith(ext))) {
      filesScanned++;
      scanFile(fullPath, relPath);
    }
  }
}

function getChangedFiles() {
  try {
    const output = execSync('git diff --name-only HEAD~1', { cwd: REPO, encoding: 'utf-8' });
    return output.trim().split('\n').filter(Boolean);
  } catch { return []; }
}

console.log('');
console.log('════════════════════════════════════════════════════════════════');
console.log('  PII Fixture Guard — no real-looking phones in test fixtures');
console.log('════════════════════════════════════════════════════════════════');
console.log('');
console.log(`Mode: ${mode}`);
console.log(`Canonical synthetic phone: +998900000000`);
console.log(`Baseline violations: ${BASELINE_VIOLATIONS}`);
console.log('');

if (mode === 'changed') {
  const changed = getChangedFiles();
  console.log(`Changed files: ${changed.length}`);
  for (const file of changed) {
    const fullPath = join(REPO, file);
    try {
      if (statSync(fullPath).isFile() && EXTS.some((ext) => file.endsWith(ext))) {
        filesScanned++;
        scanFile(fullPath, file);
      }
    } catch {}
  }
} else {
  for (const dir of SCAN_DIRS) {
    console.log(`Scanning ${dir}...`);
    scanDir(join(REPO, dir), dir);
  }
}

console.log('');
console.log(`Files scanned: ${filesScanned}`);
console.log(`Violations: ${violations} (baseline: ${BASELINE_VIOLATIONS})`);

if (violationList.length > 0 && violationList.length <= 20) {
  console.log('');
  violationList.forEach((v) => {
    console.log(`  ✗ ${v.file}:${v.line}: ${v.phone}`);
  });
} else if (violationList.length > 20) {
  console.log('');
  console.log(`  (showing first 10 of ${violationList.length} violations)`);
  violationList.slice(0, 10).forEach((v) => {
    console.log(`  ✗ ${v.file}:${v.line}: ${v.phone}`);
  });
  console.log(`  ... and ${violationList.length - 10} more`);
}

console.log('');

if (mode === 'strict') {
  if (violations > 0) {
    console.log('FAIL (strict): Real-looking phone numbers found.');
    process.exit(1);
  }
} else if (mode === 'changed') {
  if (violations > 0) {
    console.log('FAIL: Real-looking phones in CHANGED files.');
    process.exit(1);
  }
} else {
  if (violations > BASELINE_VIOLATIONS) {
    console.log(`FAIL: Violations (${violations}) exceed baseline (${BASELINE_VIOLATIONS}).`);
    process.exit(1);
  } else if (violations < BASELINE_VIOLATIONS) {
    console.log(`✓ Violations decreased (${BASELINE_VIOLATIONS} → ${violations}). Update BASELINE.`);
  } else {
    console.log(`✓ Violations at baseline (${violations}). No new violations.`);
  }
}

if (violations === 0) console.log('✓ No real-looking PII in test fixtures.');
process.exit(0);
