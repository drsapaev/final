/**
 * k6 load test script for Queue endpoint.
 *
 * Usage:
 *   k6 run tests/load/k6-queue-load.js
 *
 * Metrics:
 *   - p95 latency < 500ms
 *   - error rate < 1%
 *   - 50 virtual users
 *
 * Requires:
 *   - k6 installed (https://k6.io/docs/getting-started/installation/)
 *   - Test backend running (docker-compose up)
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const latencyTrend = new Trend('latency');

export const options = {
  stages: [
    { duration: '30s', target: 50 },  // ramp up to 50 users
    { duration: '1m', target: 50 },   // stay at 50 users
    { duration: '30s', target: 0 },   // ramp down
  ],
  thresholds: {
    errors: ['rate<0.01'],            // error rate < 1%
    http_req_duration: ['p(95)<500'], // p95 < 500ms
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_PREFIX = '/api/v1';

export default function () {
  // Authenticate (mock — in real test, use test JWT)
  const headers = {
    'Authorization': `Bearer ${__ENV.TEST_JWT || 'test-token'}`,
    'Content-Type': 'application/json',
  };

  // GET /queue — main queue endpoint
  const res = http.get(`${BASE_URL}${API_PREFIX}/queue/today`, { headers });

  latencyTrend.add(res.timings.duration);

  const success = check(res, {
    'status is 200': (r) => r.status === 200,
    'response has body': (r) => r.body && r.body.length > 0,
  });

  errorRate.add(!success);

  sleep(0.1); // 100ms between requests per user
}
