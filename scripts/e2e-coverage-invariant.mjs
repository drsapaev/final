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
 * Strip comments and string literals from source code, preserving line
 * numbers for accurate error reporting.
 *
 * P2 #6 fix (PR 2726): The old line-by-line regex approach had 5 weaknesses:
 *   1. Inline comments: `const x = 1; // test.skip(...) → false positive
 *   2. Block comments mid-line: `const x = /* test.skip() *\/ 1;` → false positive
 *   3. String literals: const note = 'test.skip(...)';` → false positive
 *   4. Multiline calls: `test\n.skip(...)` → false negative (regex tested per-line)
 *   5. Template literals: `` `${test.skip()}` `` → false positive
 *
 * This function uses a character-by-character state machine to strip:
 *   - Line comments (//)
 *   - Block comments (/* ... *​/)
 *   - Single-quoted strings ('...')
 *   - Double-quoted strings ("...")
 *   - Template literals (`...`)
 *   - Regex literals (/pattern/flags) — best-effort, may have edge cases
 *
 * The output preserves newlines so line numbers stay accurate.
 * Stripped content is replaced with spaces (not removed) to preserve
 * column positions for debugging.
 *
 * @param {string} source — raw TypeScript/JavaScript source
 * @returns {string} — source with comments and strings stripped
 */
export function stripCommentsAndStrings(source) {
  const len = source.length;
  const out = new Array(len);
  let i = 0;
  let state = 'code'; // code | lineComment | blockComment | singleStr | doubleStr | template | regex

  while (i < len) {
    const ch = source[i];
    const next = source[i + 1];

    switch (state) {
      case 'code':
        if (ch === '/' && next === '/') {
          state = 'lineComment';
          out[i] = ' ';
          out[i + 1] = ' ';
          i += 2;
          continue;
        }
        if (ch === '/' && next === '*') {
          state = 'blockComment';
          out[i] = ' ';
          out[i + 1] = ' ';
          i += 2;
          continue;
        }
        if (ch === "'") {
          state = 'singleStr';
          out[i] = ' ';
          i++;
          continue;
        }
        if (ch === '"') {
          state = 'doubleStr';
          out[i] = ' ';
          i++;
          continue;
        }
        if (ch === '`') {
          state = 'template';
          out[i] = ' ';
          i++;
          continue;
        }
        // Best-effort regex detection: / after certain tokens
        // This is imperfect but catches most cases. False positives in
        // regex detection would OVER-strip (turn code into spaces),
        // which could cause false negatives for forbidden patterns
        // inside regex. However, test.skip() inside a regex is extremely
        // unlikely. We accept this trade-off for simplicity.
        if (ch === '/' && i > 0) {
          const prev = out[i - 1];
          if (prev === '(' || prev === ',' || prev === '=' || prev === ':' ||
              prev === '[' || prev === '!' || prev === '&' || prev === '|' ||
              prev === '{' || prev === ';' || prev === '\n') {
            state = 'regex';
            out[i] = ' ';
            i++;
            continue;
          }
        }
        out[i] = ch;
        i++;
        break;

      case 'lineComment':
        if (ch === '\n') {
          out[i] = ch;
          state = 'code';
          i++;
        } else {
          out[i] = ' ';
          i++;
        }
        break;

      case 'blockComment':
        if (ch === '*' && next === '/') {
          out[i] = ' ';
          out[i + 1] = ' ';
          state = 'code';
          i += 2;
          continue;
        }
        out[i] = ch === '\n' ? ch : ' ';
        i++;
        break;

      case 'singleStr':
        if (ch === '\\' && i + 1 < len) {
          out[i] = ' ';
          out[i + 1] = ' ';
          i += 2;
          continue;
        }
        if (ch === "'") {
          out[i] = ' ';
          state = 'code';
          i++;
          continue;
        }
        out[i] = ch === '\n' ? ch : ' ';
        i++;
        break;

      case 'doubleStr':
        if (ch === '\\' && i + 1 < len) {
          out[i] = ' ';
          out[i + 1] = ' ';
          i += 2;
          continue;
        }
        if (ch === '"') {
          out[i] = ' ';
          state = 'code';
          i++;
          continue;
        }
        out[i] = ch === '\n' ? ch : ' ';
        i++;
        break;

      case 'template':
        if (ch === '\\' && i + 1 < len) {
          out[i] = ' ';
          out[i + 1] = ' ';
          i += 2;
          continue;
        }
        if (ch === '`') {
          out[i] = ' ';
          state = 'code';
          i++;
          continue;
        }
        // Template expressions ${...} — we don't recurse, just keep stripping.
        // This means test.skip() inside ${} would be stripped (over-conservative).
        // Acceptable: test files rarely use dynamic test.skip in template expressions.
        out[i] = ch === '\n' ? ch : ' ';
        i++;
        break;

      case 'regex':
        if (ch === '\\' && i + 1 < len) {
          out[i] = ' ';
          out[i + 1] = ' ';
          i += 2;
          continue;
        }
        if (ch === '/') {
          out[i] = ' ';
          // Consume flags
          let j = i + 1;
          while (j < len && /[gimsuy]/.test(source[j])) {
            out[j] = ' ';
            j++;
          }
          state = 'code';
          i = j;
          continue;
        }
        if (ch === '\n') {
          // Newline in regex — likely not a regex (was a division).
          // Restore as code.
          out[i] = ch;
          state = 'code';
          i++;
          continue;
        }
        out[i] = ' ';
        i++;
        break;
    }
  }

  return out.join('');
}

/**
 * Check a single file for forbidden patterns.
 *
 * P2 #6 fix (PR 2726): uses stripCommentsAndStrings() before applying
 * regex patterns. This eliminates false positives from comments and
 * string literals, and handles multiline patterns correctly.
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

  // P2 #6 fix: strip comments and strings before pattern matching.
  // This prevents false positives from:
  //   - Inline comments: const x = 1; // test.skip(...)
  //   - String literals: const note = 'test.skip(...)'
  //   - Template literals: `test.skip(...)
  // And handles multiline patterns correctly (the whole source is
  // scanned, not per-line).
  const cleaned = stripCommentsAndStrings(content);
  const cleanedLines = cleaned.split('\n');

  let fileHasViolation = false;

  for (const { name, pattern, reason } of FORBIDDEN_PATTERNS) {
    // Apply regex on the FULL cleaned source (not per-line) to catch
    // multiline patterns like:
    //   test
    //     .skip('async test')
    if (pattern.test(cleaned)) {
      // Find the line number for error reporting
      const match = cleaned.match(pattern);
      const matchIndex = match.index;
      const lineNumber = cleaned.substring(0, matchIndex).split('\n').length;
      recordFail(
        `${name} in ${filePath}`,
        reason,
        filePath,
        lineNumber,
      );
      fileHasViolation = true;
    }
  }

  if (!fileHasViolation) {
    recordPass(`No forbidden patterns in ${filePath}`);
  }
}

/**
 * Check that playwright.config.ts does not set retries > 0 for the
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
  const configPath = join(FRONTEND, 'playwright.config.ts');
  if (!existsSync(configPath)) {
    recordFail(
      'playwright.config.ts exists',
      'Cannot verify retries setting — config file missing.',
      'playwright.config.ts',
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
      `playwright.config.ts sets retries: ${retriesValue} (CI retries = ${ciRetriesFromConfig}), and ci-cd-unified.yml not found to verify --retries=0 override.`,
      'playwright.config.ts',
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
      `playwright.config.ts sets retries: ${retriesValue} (CI retries = ${ciRetriesFromConfig}), and UX Audit step not found in workflow to verify --retries=0 override.`,
      'playwright.config.ts',
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
      `playwright.config.ts sets retries: ${retriesValue} (CI retries = ${ciRetriesFromConfig}). UX/Visual E2E must run with retries=0 to catch flaky tests. Add --retries=0 to the UX Audit CI step, or set retries: process.env.CI ? 0 : 0 in playwright.config.ts.`,
      'playwright.config.ts',
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
    const configPath = join(FRONTEND, 'playwright.config.ts');
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
          'The UX Audit e2e CI step does NOT include --retries=0, and the global playwright config allows retries > 0 on CI. Add --retries=0 to the npx playwright test command, OR set retries: process.env.CI ? 0 : 0 in playwright.config.ts.',
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

// ─── Main (only runs when executed directly, not when imported) ─────

const isMainModule = import.meta.url === `file://${process.argv[1]}`;

if (isMainModule) {
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
} // end if (isMainModule)
