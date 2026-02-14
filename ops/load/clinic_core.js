import http from "k6/http";
import { check } from "k6";

const targetRps = Number(__ENV.TARGET_RPS || 15);

export const options = {
  discardResponseBodies: true,
  scenarios: {
    clinic_core: {
      executor: "constant-arrival-rate",
      rate: targetRps,
      timeUnit: "1s",
      duration: __ENV.K6_DURATION || "2m",
      preAllocatedVUs: Number(__ENV.PREALLOCATED_VUS || 40),
      maxVUs: Number(__ENV.MAX_VUS || 120),
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
    checks: ["rate>0.99"],
  },
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
};

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const ENDPOINTS = [
  "/api/v1/health",
  "/api/v1/status",
  "/api/v1/payments/providers",
];

export default function () {
  const endpoint = ENDPOINTS[Math.floor(Math.random() * ENDPOINTS.length)];
  const response = http.get(`${BASE_URL}${endpoint}`, {
    tags: { endpoint },
  });

  check(response, {
    "status is 2xx": (r) => r.status >= 200 && r.status < 300,
  });
}
