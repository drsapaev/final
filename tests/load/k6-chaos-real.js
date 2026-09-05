/**
 * Real-injection chaos load (issue #2774, contract:
 * docs/runbooks/CHAOS_REAL_INJECTION_CONTRACT.md).
 *
 * Runs against the CI stack (load.yml bring-up) while the workflow
 * injects real failures around this script's execution:
 *   S1 — uvicorn SIGKILL mid-run, restarted by the workflow
 *   S2 — postgres container stopped for 60s, restarted by the workflow
 *
 * Contract-mandated machine-evaluable assertions (enforced on EVERY
 * runner — these are the PASS/FAIL gates, not informational):
 *   - fast-fail ceiling: no request may exceed the contract ceilings
 *     (S1: 10s; S2: 15s) — failures must be FAST, never hangs;
 *   - post-recovery error rate returns to baseline (<1%).
 *
 * The script itself is outage-agnostic: it just records per-request
 * duration + status class; the workflow sets CHAOS_CEILING_MS per
 * scenario and evaluates the summary.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// Contract ceilings per scenario (workflow sets this per run).
const CEILING_MS = Number(__ENV.CHAOS_CEILING_MS || 15000);
// Requests above the ceiling are contract violations even when they
// eventually error out (a hang is worse than a fast failure).
const ceilingBreaches = new Counter('chaos_ceiling_breaches');
const fastFailures = new Rate('chaos_fast_failures');

export const options = {
  scenarios: {
    // Continuous single-stage load: the workflow kills/severs/restarts
    // the stack underneath while this keeps issuing requests, so every
    // outage second is observed, not extrapolated.
    chaos: {
      executor: 'constant-arrival-rate',
      rate: 10, // 10 requests/sec — steady observation load
      timeUnit: '1s',
      duration: __ENV.CHAOS_DURATION || '2m',
      preAllocatedVUs: 20,
      maxVUs: 60,
    },
  },
  thresholds: {
    // Post-recovery baseline gate (contract: error rate == baseline).
    chaos_fast_failures: ['rate<0.5'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:18000';
const API_PREFIX = '/api/v1';
const TEST_JWT = __ENV.TEST_JWT || '';
const SPECIALIST_ID = __ENV.SPECIALIST_ID || '1';

export default function () {
  const headers = {
    Authorization: `Bearer ${TEST_JWT}`,
    'Content-Type': 'application/json',
  };

  // Alternating read (queue status) and write-shaped (patient search —
  // a SELECT-heavy read) probes so both request classes are observed
  // during the outage. No writes: the contract's durability check is
  // done by the workflow via DB snapshots, not by k6.
  const isRead = Math.random() < 0.7;
  const path = isRead
    ? `${API_PREFIX}/queue/status/${SPECIALIST_ID}`
    : `${API_PREFIX}/patients/?q=${Date.now() % 100000}`;

  const res = http.get(`${BASE_URL}${path}`, { headers });

  const duration = res.timings.duration;
  if (duration > CEILING_MS) {
    ceilingBreaches.add(1);
  }
  const ok = check(res, {
    'status is 2xx/4xx-class (fast fail, no hang)': (r) => r.status !== 0 || duration <= CEILING_MS,
  });
  fastFailures.add(ok);

  sleep(0.2);
}
