/**
 * Stryker mutation testing configuration for frontend TypeScript.
 *
 * Per Phase 4 requirements:
 *   - Stryker on critical TS modules (state machines + mappers)
 *   - mutation score >= 70%
 *
 * Usage:
 *   cd frontend
 *   npx stryker run
 *   npx stryker run --mutator javascript
 *
 * Installation:
 *   npm install --save-dev @stryker-mutator/core @stryker-mutator/vitest-runner
 *
 * This file is the Stryker configuration. Actual mutation runs require
 * @stryker-mutator/core installed.
 */

/**
 * @type {import('@stryker-mutator/core/src/config').StrykerOptions}
 */
export default {
  // Mutate only critical business logic modules
  mutate: [
    'src/types/state-machines/appointment.ts',
    'src/types/state-machines/queue.ts',
    'src/types/state-machines/payment.ts',
    'src/types/state-machines/emr.ts',
    'src/types/domain/invariants/appointment.ts',
    'src/types/domain/invariants/billing.ts',
    'src/types/domain/invariants/queue.ts',
    'src/types/domain/invariants/emr.ts',
    'src/api/mappers/patient.ts',
    'src/api/mappers/appointment.ts',
    'src/api/mappers/billing.ts',
  ],

  // Test runner: vitest
  testRunner: 'vitest',

  // Coverage analysis: speed up mutation testing
  coverageAnalysis: 'perTest',

  // Reporters: console + HTML
  reporters: ['html', 'clear-text', 'progress'],

  // Threshold: mutation score >= 70%
  thresholds: {
    high: 80,
    low: 70,
    break: 70,
  },

  // Timeout: 5 seconds per mutant
  timeoutMS: 5000,

  // Concurrency: use all available cores
  concurrency: 4,

  // Ignore patterns (don't mutate tests, comments, etc.)
  mutator: {
    excludedMutations: [
      'StringLiteral', // Don't mutate string literals (too noisy)
    ],
  },
};
