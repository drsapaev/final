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
 * Policy (Phase F4 — accepted-debt lock-in):
 *   - Total `any` casts MUST stay within baseline (default 4).
 *   - EVERY remaining `any` cast MUST have a `TECH-DEBT(...)` comment
 *     within 3 lines above or on the same line. Undocumented casts fail
 *     the gate even if the total is within baseline.
 *   - This locks in accepted debt and prevents silent regressions.
 *
 * Usage:
 *   node scripts/type-debt-check.mjs           # check against baseline
 *   node scripts/type-debt-check.mjs --update   # update baseline
 *
 * Exit codes:
 *   0 — debt is within baseline AND all casts are documented
 *   1 — debt exceeded baseline OR undocumented casts found (CI failure)
 */

import { execSync } from 'child_process';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { readFileSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND_DIR = resolve(__dirname, '..', 'frontend', 'src');

const BASELINE = {
  anyCasts: 0,
  tsIgnore: 0,
  tsNoCheck: 0,
  indexSignatureAny: 0,
};

// How many lines above (and including) the cast line to search for a
// TECH-DEBT(...) marker. 3 lines covers most multi-line comment styles.
const TECH_DEBT_LOOKBACK_LINES = 3;
const TECH_DEBT_PATTERN = /TECH-DEBT\([a-z0-9-]+\)/i;

function runRgCount(pattern, cwd) {
  // rg -c returns `path:count` per file (one line per file with matches).
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

function runRgLines(pattern, cwd) {
  // rg -n returns `path:line:content` per match (one line per match).
  try {
    return execSync(`rg -n '${pattern}' ${cwd} 2>/dev/null || true`, {
      encoding: 'utf-8',
      maxBuffer: 1024 * 1024 * 10,
    });
  } catch {
    return '';
  }
}

function countPattern(pattern, cwd) {
  return runRgCount(pattern, cwd);
}

function countExact(pattern, cwd) {
  return runRgLines(pattern, cwd).trim().split('\n').filter(Boolean).length;
}

/**
 * Find all `any` cast lines and verify each has a TECH-DEBT(...) marker
 * within TECH_DEBT_LOOKBACK_LINES above (or on the same line).
 *
 * Returns array of undocumented cast locations.
 */
function findUndocumentedCasts() {
  // rg -n gives `path:line:content`
  const output = runRgLines('\\bas any\\b|:\\s*any\\b', FRONTEND_DIR);
  const lines = output.trim().split('\n').filter(Boolean);
  const undocumented = [];

  for (const line of lines) {
    // Parse `path:line:content` — but content itself may contain colons,
    // so split on first 2 colons only.
    const firstColon = line.indexOf(':');
    const secondColon = line.indexOf(':', firstColon + 1);
    if (firstColon === -1 || secondColon === -1) continue;
    const filePath = line.slice(0, firstColon);
    const lineNum = parseInt(line.slice(firstColon + 1, secondColon), 10);
    if (isNaN(lineNum)) continue;

    // Read the file and check the lookback window.
    let fileContent;
    try {
      fileContent = readFileSync(filePath, 'utf-8');
    } catch {
      continue;
    }
    const fileLines = fileContent.split('\n');
    const startLine = Math.max(0, lineNum - 1 - TECH_DEBT_LOOKBACK_LINES);
    const endLine = lineNum; // 1-indexed inclusive
    const window = fileLines.slice(startLine, endLine).join('\n');

    if (!TECH_DEBT_PATTERN.test(window)) {
      // Skip JSDoc-only references (e.g. `state?: any` inside @param tags).
      // Those are documentation, not code. We detect them by checking that
      // the matching line is itself a comment line.
      const castLine = fileLines[lineNum - 1] || '';
      const isCommentLine = /^\s*(\*|\/\/|\/\*)/.test(castLine);
      if (isCommentLine) continue;

      undocumented.push({
        file: filePath.replace(FRONTEND_DIR + '/', ''),
        line: lineNum,
        content: castLine.trim(),
      });
    }
  }

  return undocumented;
}

const metrics = {
  // Match common forms of `any` in type positions:
  //   `as any`            — cast
  //   `: any`             — annotation (including `: any)`, `: any,`, `: any>`)
  //   `[key: string]: any`— index signature (counted separately below)
  //
  // Note: `Record<string, any>` (generic args) and `Promise<any>` are NOT
  // matched by this pattern to avoid surfacing 100+ pre-existing debt sites
  // in one go. A future PR can tighten the pattern once those are cleaned up.
  // See ADR-0012 "Future Work" section.
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

// Policy: every remaining `any` cast MUST be documented with TECH-DEBT(...)
const undocumented = findUndocumentedCasts();
if (undocumented.length > 0) {
  console.error(`❌ ${undocumented.length} undocumented \`any\` cast(s) found:`);
  console.error('');
  for (const { file, line, content } of undocumented) {
    console.error(`   ${file}:${line}: ${content}`);
  }
  console.error('');
  console.error('Every remaining `any` cast MUST have a TECH-DEBT(<id>) comment');
  console.error(`within ${TECH_DEBT_LOOKBACK_LINES} lines above it. Add the comment or`);
  console.error('remove the cast. See docs/adr/ADR-0012-typescript-migration.md');
  console.error('for the accepted-debt policy.');
  failed = true;
} else if (metrics.anyCasts > 0) {
  console.log(`✅ All ${metrics.anyCasts} \`any\` cast(s) are documented with TECH-DEBT(...) markers.`);
  console.log('');
} else {
  console.log('✅ Zero `any` casts — fully typed codebase.');
  console.log('');
}

if (failed) {
  console.error('❌ Type debt gate FAILED.');
  console.error('');
  console.error('To fix: reduce the new `any`/`@ts-ignore`/`@ts-nocheck` usage, OR');
  console.error('document the cast with a TECH-DEBT(<id>) comment, OR');
  console.error('update the baseline in scripts/type-debt-check.mjs with justification.');
  process.exit(1);
} else {
  console.log('✅ Type debt is within baseline and all casts are documented.');
  process.exit(0);
}
