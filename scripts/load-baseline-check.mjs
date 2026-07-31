#!/usr/bin/env node
/**
 * load-baseline-check.mjs
 *
 * Compares k6 load test results against baseline values.
 * Fails if p95 latency exceeds baseline × 1.15 (15% degradation threshold).
 *
 * Usage:
 *   node scripts/load-baseline-check.mjs --results <k6-results.json> --baseline e2e/k6/baseline.json
 *
 * Exit codes:
 *   0 — all metrics within threshold
 *   1 — one or more metrics exceeded threshold
 */

import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

function parseArgs() {
  const args = process.argv.slice(2);
  const resultsPath = args[args.indexOf('--results') + 1];
  const baselinePath = args[args.indexOf('--baseline') + 1] || resolve(__dirname, '..', 'e2e', 'k6', 'baseline.json');
  return { resultsPath, baselinePath };
}

function main() {
  const { resultsPath, baselinePath } = parseArgs();

  if (!resultsPath) {
    console.error('Usage: node load-baseline-check.mjs --results <path> [--baseline <path>]');
    process.exit(1);
  }

  const baseline = JSON.parse(readFileSync(baselinePath, 'utf-8'));
  const results = JSON.parse(readFileSync(resultsPath, 'utf-8'));

  const multiplier = baseline.threshold_multiplier || 1.15;
  let allPassed = true;

  console.log('Load Baseline Check');
  console.log('===================');
  console.log(`Threshold multiplier: ${multiplier}x (allows ${(multiplier - 1) * 100}% degradation)`);
  console.log();

  for (const [endpoint, config] of Object.entries(baseline)) {
    if (endpoint === 'threshold_multiplier' || endpoint === 'notes') continue;

    const baselineP95 = config.p95_ms;
    const threshold = Math.round(baselineP95 * multiplier);
    const measuredP95 = results[endpoint]?.p95_ms;

    if (measuredP95 == null) {
      console.log(`⚠️  ${endpoint}: no measurement found in results (skipped)`);
      continue;
    }

    const passed = measuredP95 <= threshold;
    const status = passed ? '✅ PASS' : '❌ FAIL';
    const degradation = ((measuredP95 - baselineP95) / baselineP95 * 100).toFixed(1);

    console.log(`${status} ${endpoint}: baseline=${baselineP95}ms, threshold=${threshold}ms, measured=${measuredP95}ms (${degradation}%)`);

    if (!passed) {
      allPassed = false;
    }
  }

  console.log();
  if (allPassed) {
    console.log('✅ All metrics within threshold.');
    process.exit(0);
  } else {
    console.log('❌ One or more metrics exceeded threshold. Release blocked.');
    process.exit(1);
  }
}

main();
