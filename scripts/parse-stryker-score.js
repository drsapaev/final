#!/usr/bin/env node
/**
 * parse-stryker-score.js
 *
 * Parse mutation score from Stryker JSON output.
 *
 * Usage:
 *   node scripts/parse-stryker-score.js --output <stryker-report.json> --threshold 70
 *
 * Exit codes:
 *   0 — mutation score >= threshold
 *   1 — mutation score < threshold
 */

import { readFileSync } from 'fs';

function parseArgs() {
  const args = process.argv.slice(2);
  const outputPath = args[args.indexOf('--output') + 1];
  const thresholdStr = args[args.indexOf('--threshold') + 1];
  const threshold = thresholdStr ? parseInt(thresholdStr, 10) : 70;
  return { outputPath, threshold };
}

function main() {
  const { outputPath, threshold } = parseArgs();

  if (!outputPath) {
    console.error('Usage: node parse-stryker-score.js --output <path> [--threshold 70]');
    process.exit(1);
  }

  const report = JSON.parse(readFileSync(outputPath, 'utf-8'));

  // Stryker JSON format: { mutationScore: 85.5, ... }
  // Or: { files: { ... }, mutationScore: ... }
  const score = report.mutationScore ?? report.mutationScoreRounded;

  if (score == null) {
    console.error('Could not find mutationScore in Stryker report');
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
