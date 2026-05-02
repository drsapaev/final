import http from "k6/http";
import { check } from "k6";

const targetRps = Number(__ENV.TARGET_RPS || 30);
const minRps = Math.max(targetRps - 5, 1);
const profileName = __ENV.K6_PROFILE || "core_readiness";

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
    http_reqs: [`rate>${minRps}`],
  },
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
};

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";

const DEFAULT_ENDPOINTS = [
  "/api/v1/status",
  "/api/v1/status",
  "/api/v1/status",
  "/api/v1/health",
];

function parseEndpoints() {
  const raw = __ENV.K6_ENDPOINTS_JSON;
  if (!raw) {
    return DEFAULT_ENDPOINTS;
  }

  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      const clean = parsed
        .filter((endpoint) => typeof endpoint === "string")
        .map((endpoint) => endpoint.trim())
        .filter((endpoint) => endpoint.length > 0);
      if (clean.length > 0) {
        return clean;
      }
    }
  } catch (error) {
    console.error(`Invalid K6_ENDPOINTS_JSON for profile=${profileName}: ${error}`);
  }

  return DEFAULT_ENDPOINTS;
}

const ENDPOINTS = parseEndpoints();

export default function () {
  const endpoint = ENDPOINTS[Math.floor(Math.random() * ENDPOINTS.length)];
  const response = http.get(`${BASE_URL}${endpoint}`, {
    tags: { endpoint, profile: profileName },
  });

  check(response, {
    "status is 2xx": (r) => r.status >= 200 && r.status < 300,
  });
}
