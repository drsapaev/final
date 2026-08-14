#!/usr/bin/env node
/**
 * parse-stryker-score.js
 *
 * Parse mutation score from Stryker JSON output.
 *
 * StrykerJS 9.x emits the "mutation testing metrics" schema (schemaVersion 1.0):
 * { schemaVersion: "1.0", files: { "<path>": { mutants: [ { status, ... } ] } } }
 * with no top-level score — the score must be aggregated from per-mutant statuses,
 * matching Stryker's own reported score:
 *   (Killed + Timeout) / (Killed + Survived + Timeout + NoCoverage)
 * (Ignored and CompileError mutants are excluded).
 *
 * Older reports with a top-level mutationScore field are still supported.
 *
 * Usage:
 *   node scripts/parse-stryker-score.js --output <stryker-report.json> --threshold 70
 *
 * Exit codes:
 *   0 — mutation score >= threshold
 *   1 — mutation score < threshold, or report not parseable
 */

import { readFileSync } from 'fs';

function parseArgs() {
  const args = process.argv.slice(2);
  const outputPath = args[args.indexOf('--output') + 1];
  const thresholdStr = args[args.indexOf('--threshold') + 1];
  const threshold = thresholdStr ? parseInt(thresholdStr, 10) : 70;
  return { outputPath, threshold };
}

function scoreFromSchemaV1(report) {
  if (!report.files || typeof report.files !== 'object') {
    return null;
  }
  const counts = { Killed: 0, Survived: 0, Timeout: 0, NoCoverage: 0 };
  for (const file of Object.values(report.files)) {
    for (const mutant of file.mutants ?? []) {
      if (mutant.status in counts) counts[mutant.status] += 1;
    }
  }
  const total = counts.Killed + counts.Survived + counts.Timeout + counts.NoCoverage;
  if (total === 0) {
    return null;
  }
  return ((counts.Killed + counts.Timeout) / total) * 100;
}

function main() {
  const { outputPath, threshold } = parseArgs();

  if (!outputPath) {
    console.error('Usage: node parse-stryker-score.js --output <path> [--threshold 70]');
    process.exit(1);
  }

  const report = JSON.parse(readFileSync(outputPath, 'utf-8'));

  const score = report.mutationScore ?? report.mutationScoreRounded ?? scoreFromSchemaV1(report);

  if (score == null || Number.isNaN(score)) {
    console.error('Could not derive mutation score from Stryker report');
    process.exit(1);
  }

  console.log(`Mutation score: ${score.toFixed(1)}%`);
  console.log(`Threshold: ${threshold}%`);

  if (score >= threshold) {
    console.log(`✅ PASS — mutation score ${score.toFixed(1)}% >= ${threshold}%`);
    process.exit(0);
  } else {
    console.log(`❌ FAIL — mutation score ${score.toFixed(1)}% < ${threshold}%`);
    process.exit(1);
  }
}

main();
