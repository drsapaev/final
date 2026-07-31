/**
 * k6 load test script for EMR endpoint.
 *
 * Usage:
 *   k6 run tests/load/k6-emr-load.js
 *
 * Metrics:
 *   - p95 latency < 1000ms
 *   - 20 virtual users (doctors)
 *   - memory < 512MB (monitored separately)
 *
 * Requires:
 *   - k6 installed
 *   - Test backend running
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const latencyTrend = new Trend('latency');

export const options = {
  stages: [
    { duration: '30s', target: 20 },  // ramp up to 20 doctors
    { duration: '2m', target: 20 },   // stay at 20 doctors
    { duration: '30s', target: 0 },   // ramp down
  ],
  thresholds: {
    errors: ['rate<0.01'],             // error rate < 1%
    http_req_duration: ['p(95)<1000'], // p95 < 1000ms
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_PREFIX = '/api/v1';

const TEST_PATIENT_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

export default function () {
  const patientId = TEST_PATIENT_IDS[Math.floor(Math.random() * TEST_PATIENT_IDS.length)];
  const headers = {
    'Authorization': `Bearer ${__ENV.TEST_JWT || 'test-token'}`,
    'Content-Type': 'application/json',
  };

  // GET /emr/{patient_id} — main EMR endpoint
  const res = http.get(`${BASE_URL}${API_PREFIX}/emr/${patientId}`, { headers });

  latencyTrend.add(res.timings.duration);

  const success = check(res, {
    'status is 200 or 404': (r) => r.status === 200 || r.status === 404,
    'response time < 1000ms': (r) => r.timings.duration < 1000,
  });

  errorRate.add(!success);

  sleep(0.5); // 500ms between requests per doctor (reading EMR takes time)
}
