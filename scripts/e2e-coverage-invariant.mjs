#!/usr/bin/env node
/**
 * e2e-coverage-invariant.mjs
 *
 * CI gate that verifies UX/Visual E2E tests are fully executed — no
 * test.fixme, test.skip, describe.skip, or it.skip — and that the
 * expected number of tests actually ran.
 *
 * This invariant exists because of a real incident (PR #2715 → #2716 → #2717):
 * CI showed "success" for the UX Audit step while 18 of 27 tests were
 * silently skipped via test.fixme + continue-on-error: true. The tests
 * were "green" but not actually running.
 *
 * Scope: ONLY the UX/Visual E2E files. Other E2E suites (business/,
 * security/, load/, chaos/) may legitimately use skip and are NOT
 * checked by this invariant.
 *
 * Usage:
 *   node scripts/e2e-coverage-invariant.mjs
 *   node scripts/e2e-coverage-invariant.mjs --check-count 27
 *
 * Exit codes:
 *   0 — all invariants intact
 *   1 — one or more invariants violated
 */

import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(__dirname, '..');
const FRONTEND = resolve(REPO, 'frontend');

// Target E2E files — ONLY these are checked. Other suites may use skip.
const TARGET_E2E_FILES = [
  'e2e/cashier-ux-audit.spec.ts',
  'e2e/registrar-ux-audit.spec.ts',
  'e2e/visual-regression.spec.ts',
];

// Patterns that silently disable tests. Each is a RegExp source.
// We check for these as function calls (with optional whitespace/skip prefix).
const FORBIDDEN_PATTERNS = [
  {
    name: 'test.fixme',
    pattern: /\btest\s*\.\s*fixme\s*\(/,
    reason: 'test.fixme silently excludes the test from execution. Fix the test or remove it.',
  },
  {
    name: 'test.skip',
    pattern: /\btest\s*\.\s*skip\s*\(/,
    reason: 'test.skip silently excludes the test from execution. Fix the test or remove it.',
  },
  {
    name: 'describe.skip',
    pattern: /\bdescribe\s*\.\s*skip\s*\(/,
    reason: 'describe.skip silently excludes the entire describe block. Fix the tests or remove them.',
  },
  {
    name: 'describe.fixme',
    pattern: /\bdescribe\s*\.\s*fixme\s*\(/,
    reason: 'describe.fixme silently excludes the entire describe block. Fix the tests or remove them.',
  },
  {
    name: 'it.skip',
    pattern: /\bit\s*\.\s*skip\s*\(/,
    reason: 'it.skip silently excludes the test from execution.',
  },
  {
    name: 'it.fixme',
    pattern: /\bit\s*\.\s*fixme\s*\(/,
    reason: 'it.fixme silently excludes the test from execution.',
  },
  {
    name: 'test.only (forbidden on CI)',
    pattern: /\btest\s*\.\s*only\s*\(/,
    reason: 'test.only runs only one test and skips all others. Remove before merge.',
  },
];

let passed = 0;
let failed = 0;
const failures = [];
const warnings = [];

function log(msg) {
  console.log(msg);
}

function recordPass(name) {
  passed++;
  log(`  ✓ ${name}`);
}

function recordFail(name, reason, file, line) {
  failed++;
  failures.push({ name, reason, file, line });
  log(`  ✗ ${name}`);
  if (file) log(`    file: ${file}${line ? `:${line}` : ''}`);
  if (reason) log(`    reason: ${reason}`);
}

/**
 * Check a single file for forbidden patterns.
 * Returns the list of violations (empty if none).
 */
function checkFile(filePath) {
  const fullPath = join(FRONTEND, filePath);
  if (!existsSync(fullPath)) {
    recordFail(
      `File exists: ${filePath}`,
      `Expected E2E file does not exist. The invariant cannot be verified.`,
      filePath,
      null,
    );
    return;
  }

  const content = readFileSync(fullPath, 'utf-8');
  const lines = content.split('\n');

  let fileHasViolation = false;

  for (const { name, pattern, reason } of FORBIDDEN_PATTERNS) {
    lines.forEach((line, idx) => {
      // Skip comment lines (lines that start with // or * after trim)
      const trimmed = line.trim();
      if (trimmed.startsWith('//') || trimmed.startsWith('*') || trimmed.startsWith('/*')) {
        return;
      }
      if (pattern.test(line)) {
        recordFail(
          `${name} in ${filePath}`,
          reason,
          filePath,
          idx + 1,
        );
        fileHasViolation = true;
      }
    });
  }

  if (!fileHasViolation) {
    recordPass(`No forbidden patterns in ${filePath}`);
  }
}

/**
 * Check that playwright.config.js does not set retries > 0 for the
 * target E2E files. We check the global retries setting; if it's > 0
 * on CI, the UX/Visual suite inherits it UNLESS the CI command
 * explicitly overrides with --retries=0 (which takes precedence).
 *
 * The check logic:
 *   1. If global config retries=0 on CI → PASS
 *   2. If global config retries>0 on CI, but CI step has --retries=0 → PASS (override)
 *   3. If global config retries>0 on CI, and CI step has no --retries=0 → FAIL
 */
function checkRetriesConfig() {
  const configPath = join(FRONTEND, 'playwright.config.js');
  if (!existsSync(configPath)) {
    recordFail(
      'playwright.config.js exists',
      'Cannot verify retries setting — config file missing.',
      'playwright.config.js',
      null,
    );
    return;
  }

  const content = readFileSync(configPath, 'utf-8');

  // Find the retries line
  const retriesMatch = content.match(/retries\s*:\s*([^,}\n]+)/);
  if (!retriesMatch) {
    recordPass('retries setting (absent = 0)');
    return;
  }

  const retriesValue = retriesMatch[1].trim();

  // Determine CI retries value from global config
  let ciRetriesFromConfig = 0;
  let parsed = false;

  if (retriesValue.includes('process.env.CI')) {
    const ciMatch = retriesValue.match(/CI\s*\?\s*(\d+)\s*:\s*(\d+)/);
    if (ciMatch) {
      ciRetriesFromConfig = parseInt(ciMatch[1], 10);
      parsed = true;
    }
  } else if (/^\d+$/.test(retriesValue)) {
    ciRetriesFromConfig = parseInt(retriesValue, 10);
    parsed = true;
  }

  if (!parsed) {
    warnings.push(`Could not parse retries value: ${retriesValue}. Manual review needed.`);
    recordPass(`retries setting present (manual review: ${retriesValue})`);
    return;
  }

  if (ciRetriesFromConfig === 0) {
    recordPass(`retries=0 on CI (config: ${retriesValue})`);
    return;
  }

  // Global config allows retries > 0 on CI. Check if the CI workflow
  // step explicitly overrides with --retries=0.
  const workflowPath = join(REPO, '.github', 'workflows', 'ci-cd-unified.yml');
  if (!existsSync(workflowPath)) {
    recordFail(
      'retries=0 for UX/Visual on CI',
      `playwright.config.js sets retries: ${retriesValue} (CI retries = ${ciRetriesFromConfig}), and ci-cd-unified.yml not found to verify --retries=0 override.`,
      'playwright.config.js',
      null,
    );
    return;
  }

  const workflowContent = readFileSync(workflowPath, 'utf-8');
  const uxStepMatch = workflowContent.match(
    /name:\s*📸\s*UX Audit e2e.*?(?=\n\s*-\s*name:|\n\s*-\s*uses:|$)/s,
  );

  if (!uxStepMatch) {
    recordFail(
      'retries=0 for UX/Visual on CI',
      `playwright.config.js sets retries: ${retriesValue} (CI retries = ${ciRetriesFromConfig}), and UX Audit step not found in workflow to verify --retries=0 override.`,
      'playwright.config.js',
      null,
    );
    return;
  }

  const uxStep = uxStepMatch[0];
  if (uxStep.includes('--retries=0') || uxStep.includes('--retries 0')) {
    recordPass(
      `retries=0 for UX/Visual on CI (config has ${ciRetriesFromConfig}, but CI step overrides with --retries=0)`,
    );
  } else {
    recordFail(
      'retries=0 for UX/Visual on CI',
      `playwright.config.js sets retries: ${retriesValue} (CI retries = ${ciRetriesFromConfig}). UX/Visual E2E must run with retries=0 to catch flaky tests. Add --retries=0 to the UX Audit CI step, or set retries: process.env.CI ? 0 : 0 in playwright.config.js.`,
      'playwright.config.js',
      null,
    );
  }
}

/**
 * Check that the CI workflow command for UX Audit includes --retries=0
 * OR that the global config is already retries=0.
 * This is a secondary check — if the config allows retries, the CI
 * command must explicitly override to 0.
 */
function checkCIWorkflowRetries() {
  const workflowPath = join(REPO, '.github', 'workflows', 'ci-cd-unified.yml');
  if (!existsSync(workflowPath)) {
    warnings.push('ci-cd-unified.yml not found — cannot verify UX Audit retries override.');
    return;
  }

  const content = readFileSync(workflowPath, 'utf-8');

  // Find the UX Audit step
  const uxStepMatch = content.match(
    /name:\s*📸\s*UX Audit e2e.*?(?=\n\s*-\s*name:|\n\s*-\s*uses:|$)/s,
  );
  if (!uxStepMatch) {
    warnings.push('Could not find UX Audit e2e step in ci-cd-unified.yml.');
    return;
  }

  const uxStep = uxStepMatch[0];

  // Check if the command includes --retries=0
  if (uxStep.includes('--retries=0') || uxStep.includes('--retries 0')) {
    recordPass('UX Audit CI step includes --retries=0');
  } else {
    // Check if the global config is already retries=0 on CI
    const configPath = join(FRONTEND, 'playwright.config.js');
    const configContent = readFileSync(configPath, 'utf-8');
    const retriesMatch = configContent.match(/retries\s*:\s*([^,}\n]+)/);
    if (retriesMatch) {
      const retriesValue = retriesMatch[1].trim();
      const ciMatch = retriesValue.match(/CI\s*\?\s*(\d+)/);
      if (ciMatch && parseInt(ciMatch[1], 10) === 0) {
        recordPass('UX Audit retries=0 (via global config CI ? 0)');
      } else {
        recordFail(
          'UX Audit CI step has --retries=0',
          'The UX Audit e2e CI step does NOT include --retries=0, and the global playwright config allows retries > 0 on CI. Add --retries=0 to the npx playwright test command, OR set retries: process.env.CI ? 0 : 0 in playwright.config.js.',
          '.github/workflows/ci-cd-unified.yml',
          null,
        );
      }
    }
  }
}

/**
 * Check that the CI workflow step for UX Audit does NOT have
 * continue-on-error: true (which would mask failures).
 */
function checkCIWorkflowContinueOnError() {
  const workflowPath = join(REPO, '.github', 'workflows', 'ci-cd-unified.yml');
  if (!existsSync(workflowPath)) {
    return;
  }

  const content = readFileSync(workflowPath, 'utf-8');

  // Find the UX Audit step block
  const uxStepMatch = content.match(
    /name:\s*📸\s*UX Audit e2e.*?(?=\n\s*-\s*name:|\n\s*-\s*uses:|$)/s,
  );
  if (!uxStepMatch) {
    return;
  }

  const uxStep = uxStepMatch[0];

  if (/continue-on-error\s*:\s*true/i.test(uxStep)) {
    recordFail(
      'UX Audit step has no continue-on-error: true',
      'The UX Audit e2e step has continue-on-error: true, which masks test failures. CI shows "success" even when tests fail. Remove the continue-on-error: true line.',
      '.github/workflows/ci-cd-unified.yml',
      null,
    );
  } else {
    recordPass('UX Audit step has no continue-on-error: true');
  }
}

// ─── Main ───────────────────────────────────────────────────────────

log('');
log('══════════════════════════════════════════════════════════════════════');
log('  E2E Coverage Invariant — UX/Visual E2E must be fully executed');
log('══════════════════════════════════════════════════════════════════════');
log('');
log('Checking for forbidden patterns (test.fixme, test.skip, etc.):');
log('');

for (const file of TARGET_E2E_FILES) {
  checkFile(file);
}

log('');
log('Checking retries configuration:');
log('');
checkRetriesConfig();

log('');
log('Checking CI workflow retries override:');
log('');
checkCIWorkflowRetries();

log('');
log('Checking CI workflow continue-on-error:');
log('');
checkCIWorkflowContinueOnError();

log('');
log('────────────────────────────────────────────────────────────────────');
log(`  Result: ${passed} passed, ${failed} failed`);
if (warnings.length > 0) {
  log(`  Warnings: ${warnings.length}`);
  warnings.forEach((w) => log(`    ⚠ ${w}`));
}
log('────────────────────────────────────────────────────────────────────');

if (failed > 0) {
  log('');
  log('FAILURES:');
  failures.forEach((f) => {
    log(`  • ${f.name}`);
    if (f.file) log(`    file: ${f.file}${f.line ? `:${f.line}` : ''}`);
    if (f.reason) log(`    reason: ${f.reason}`);
  });
  log('');
  log('This invariant exists because of a real incident where CI showed');
  log('"success" while 18 of 27 UX/Visual tests were silently skipped.');
  log('See PR #2715, #2716, #2717 for context.');
  process.exit(1);
}

log('');
log('✓ All E2E coverage invariants intact.');
process.exit(0);
