/**
 * Sentry initialization for the clinic frontend.
 *
 * Init is a no-op if VITE_SENTRY_DSN is unset — this lets dev/local runs
 * skip Sentry without code changes. In staging/production, set the DSN via
 * Vercel env vars.
 *
 * Trace sample rate is intentionally low (5%) — this is a medical SaaS where
 * patients hit the app from slow mobile networks; 100% sampling would drown
 * the Sentry quota in noise. Errors are always captured (tracesSampleRate
 * only affects performance traces, not errors).
 *
 * Privacy boundary: outgoing events, transactions, and child spans retain
 * only explicitly allowlisted diagnostic structure. Breadcrumbs are dropped,
 * and replay sampling is explicitly zero because replay envelopes do not
 * pass through event callbacks. The exported key scrubber remains a helper
 * for callers/tests; it is not the final Sentry privacy boundary.
 */

import * as Sentry from '@sentry/react';

const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN;
const SENTRY_ENV = import.meta.env.VITE_SENTRY_ENV || 'development';
const SENTRY_TRACES_SAMPLE_RATE = Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || 0.05);

const MEDICAL_PII_KEYS = [
  // Patient identifiers
  'iin', 'passport_number', 'passport_series', 'ssn', 'national_id',
  // Contact info
  'phone', 'phone_number', 'email', 'address', 'street', 'city', 'postal_code',
  // Names (audit/phase-2, BS-57: previously missing — only `patient_name`
  // substring was matched, so standalone `full_name`, `first_name`,
  // `last_name`, `middle_name`, `fio`, `patient_fio` leaked through).
  'full_name', 'firstname', 'first_name', 'lastname', 'last_name',
  'middle_name', 'surname', 'patronymic', 'fio', 'name',
  // Dates of birth (previously missing)
  'birth_date', 'date_of_birth', 'dob', 'patient_birth_date', 'patient_birth_year',
  // Insurance / identity (previously missing)
  'insurance_number', 'card_number', 'cvv', 'payment_method',
  // Medical
  'diagnosis', 'diagnoses', 'icd10', 'icd10_codes', 'complaints', 'complaint',
  'examination', 'prescription', 'medications', 'allergies',
  'medical_history', 'symptoms', 'treatment', 'lab_results', 'blood_type',
  // Visit
  'visit_reason', 'patient_name', 'patient_id', 'doctor_notes',
  // Auth tokens (defence-in-depth: Sentry SDK auto-scrubs these, but the
  // custom scrubber runs first and we want redaction even if SDK behaviour
  // changes in a future release)
  'token', 'access_token', 'refresh_token', 'secret', 'api_key', 'password',
];

// AI content can include clinical notes and tool arguments under generic keys.
const AI_CONTENT_KEYS = [
  'system_prompt', 'systemprompt', 'system_instructions', 'provider_response',
  'providerresponse', 'user_input', 'patient_input', 'input_text', 'output_text',
  'prompt', 'prompts', 'input', 'output', 'response', 'responses', 'content',
  'completion', 'completions', 'messages', 'arguments', 'tool_args', 'tool_arguments',
];
const SAFE_DIAGNOSTIC_SUFFIXES = [
  'status_code', 'body_size', 'input_tokens', 'output_tokens', 'total_tokens',
];
const SAFE_AI_DIAGNOSTIC_CODES = new Set([
  'ai_gateway_unexpected_error', 'ai_gateway_stream_error', 'ai_provider_failure',
]);
const SAFE_AI_PROVIDERS = new Set(['openai', 'gemini', 'deepseek', 'grok', 'mock', 'none']);
const SAFE_ALERT_TYPES = new Set([
  'payment_failure', 'database_error', 'auth_failure', 'queue_error',
  'high_error_rate', 'external_service', 'security_incident', 'system_resource',
]);
const SAFE_ALERT_SEVERITIES = new Set(['info', 'warning', 'error', 'critical']);
const SAFE_HTTP_METHODS = new Set(['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']);
const SAFE_SPAN_OPS = new Set([
  'http.client', 'http.server', 'db', 'db.query', 'db.sql.query',
  'cache.get', 'cache.put', 'function', 'task', 'queue.process',
  'ui.load', 'ui.click', 'navigation', 'resource.fetch',
  'ai.completion', 'gen_ai.request',
]);
const SAFE_DB_SYSTEMS = new Set(['postgresql', 'postgres', 'redis', 'mysql']);
const SAFE_DB_OPERATIONS = new Set(['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'BEGIN', 'COMMIT', 'ROLLBACK']);
const SAFE_MEASUREMENTS = new Set([
  'lcp', 'cls', 'fcp', 'ttfb', 'inp', 'fp', 'tbt', 'frames', 'frames_slow', 'frames_frozen',
]);
const SAFE_EVENT_FIELDS = new Set([
  'event_id', 'timestamp', 'start_timestamp', 'platform', 'level', 'environment',
  'release', 'dist', 'sdk', 'type', 'exception', 'threads', 'request', 'contexts',
  'extra', 'tags', 'fingerprint', 'transaction', 'transaction_info', 'spans',
  'measurements', 'trace', 'message', 'logentry',
]);
const SAFE_SPAN_DATA_FIELDS = new Set([
  'http.response.status_code', 'http.request.method', 'http.response.body.size',
  'gen_ai.usage.input_tokens', 'gen_ai.usage.output_tokens', 'gen_ai.usage.total_tokens',
  'db.system', 'db.operation',
]);

type MutableSentryEvent = Record<string, unknown> & {
  breadcrumbs?: Array<Record<string, unknown>>;
  contexts?: Record<string, unknown>;
  exception?: { values?: Array<Record<string, unknown>> };
  extra?: Record<string, unknown>;
  logentry?: Record<string, unknown>;
  request?: Record<string, unknown>;
  spans?: Array<Record<string, unknown>>;
  tags?: Record<string, unknown>;
  threads?: { values?: Array<Record<string, unknown>> };
  trace?: Record<string, unknown>;
  user?: Record<string, unknown>;
};

// Credential keys redacted INSIDE URL-shaped strings (owner round-12 P1):
// request.url, breadcrumb from/to, Referer headers and pageload/http-span
// descriptions carry the URL as a plain string, so the key-based scrubber
// above never sees the "token" key. Deliberately narrower than
// MEDICAL_PII_KEYS — non-credential params (sort, q, lang, name…) must
// stay readable for debugging.
const CREDENTIAL_QUERY_KEYS = [
  'token', // also matches *_token via the suffix rule (access_token, refresh_token, activation_token, …)
  'apikey', 'api_key', 'secret', 'password', 'sig', 'signature', 'authorization',
];

/**
 * Redact credential query/fragment params inside a URL-ish string while
 * preserving everything else. Matches `?key=`, `&key=`, `#key=` and a bare
 * leading `key=` (separately-transmitted query_string fields); keys are
 * percent-decoded first, mirroring URLSearchParams so an obfuscated
 * %74oken= is caught too. Generic over the string-ish input so callers
 * keep their precise type (string | undefined for event.transaction, etc.).
 */
export function redactCredentialQueryParams<T extends string | undefined | null>(value: T): T {
  if (typeof value !== 'string' || !value) {
    return value;
  }
  const scrubbed = value.replace(
    /(^|[?&#])([A-Za-z0-9_%.-]+)=([^&#]*)/g,
    (match, sep: string, key: string) => {
      let lowerKey = key.toLowerCase();
      try {
        lowerKey = decodeURIComponent(lowerKey);
      } catch {
        // Malformed percent-encoding — match on the raw key.
      }
      const isCredential = CREDENTIAL_QUERY_KEYS.some(
        (k) => lowerKey === k || lowerKey.endsWith(`_${k}`)
      );
      return isCredential ? `${sep}${key}=[REDACTED]` : match;
    }
  );
  return scrubbed as T;
}

/**
 * Key-based PII scrubbing PLUS credential-query redaction inside string
 * values (owner round-12 P1): URL-valued telemetry fields (request.url,
 * breadcrumb from/to, Referer) hold the URL as a plain string — the
 * key-based loop below cannot catch a `?token=` embedded in it. Exported
 * for unit tests (scrubbing contract is security-relevant).
 */
export function scrubPIIFromObject(obj: unknown, parentKey = ''): unknown {
  if (typeof obj === 'string') {
    return redactCredentialQueryParams(obj);
  }
  if (!obj || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map((item) => scrubPIIFromObject(item, parentKey));

  const cleaned: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const lowerKey = key.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase().replace(/-/g, '_');
    const isHttpResponseContext = parentKey === 'contexts' && lowerKey === 'response';
    if (isHttpResponseContext) {
      (cleaned as Record<string, unknown>)[key] = scrubHttpResponseContext(value);
      continue;
    }
    const leafKey = lowerKey.split('.').pop() || lowerKey;
    const isDiagnosticField = SAFE_DIAGNOSTIC_SUFFIXES.includes(leafKey) || leafKey.endsWith('_tokens');
    const isSafeDiagnostic = leafKey === 'model'
      ? typeof value === 'string' && /^[A-Za-z0-9_.:/-]{1,80}$/.test(value)
      : isDiagnosticField && typeof value === 'number' && Number.isFinite(value);
    if (isDiagnosticField) {
      (cleaned as Record<string, unknown>)[key] = isSafeDiagnostic ? value : '[REDACTED]';
      continue;
    }
    const containsAiContent =
      !isSafeDiagnostic && AI_CONTENT_KEYS.some((contentKey) => lowerKey.includes(contentKey));
    if (
      containsAiContent ||
      (!isSafeDiagnostic && MEDICAL_PII_KEYS.some((pii) => lowerKey.includes(pii)))
    ) {
      (cleaned as Record<string, unknown>)[key] = '[REDACTED]';
    } else {
      (cleaned as Record<string, unknown>)[key] = scrubPIIFromObject(value, lowerKey);
    }
  }
  return cleaned;
}

function scrubHttpResponseContext(value: unknown): Record<string, number> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const source = value as Record<string, unknown>;
  const safe: Record<string, number> = {};
  const status = boundedInteger(source.status_code, 100, 599);
  const bodySize = boundedInteger(source.body_size, 0, 1_000_000_000);
  if (status !== undefined) safe.status_code = status;
  if (bodySize !== undefined) safe.body_size = bodySize;
  return safe;
}

function boundedInteger(value: unknown, minimum: number, maximum: number): number | undefined {
  return typeof value === 'number' && Number.isInteger(value) && Number.isFinite(value)
    && value >= minimum && value <= maximum
    ? value
    : undefined;
}

function safeText(value: unknown, pattern: RegExp, maximumLength = 128): string | undefined {
  return typeof value === 'string' && value.length <= maximumLength && pattern.test(value)
    ? value
    : undefined;
}

function safeTraceContext(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const source = value as Record<string, unknown>;
  const safe: Record<string, unknown> = {};
  for (const field of ['trace_id', 'span_id', 'parent_span_id', 'segment_id']) {
    const id = safeText(source[field], /^(?:[0-9a-f]{16}|[0-9a-f]{32})$/i, 32);
    if (id) safe[field] = id;
  }
  if (typeof source.sampled === 'boolean') safe.sampled = source.sampled;
  if (typeof source.op === 'string' && SAFE_SPAN_OPS.has(source.op)) safe.op = source.op;
  if (typeof source.status === 'string' && ['ok', 'error', 'cancelled'].includes(source.status)) {
    safe.status = source.status;
  }
  return safe;
}

function safeContexts(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const source = value as Record<string, unknown>;
  const safe: Record<string, unknown> = {};
  const response = scrubHttpResponseContext(source.response);
  if (Object.keys(response).length) safe.response = response;
  const trace = safeTraceContext(source.trace);
  if (Object.keys(trace).length) safe.trace = trace;

  const contextNameAllowlist: Record<string, Set<string>> = {
    runtime: new Set(['python', 'cpython', 'node', 'javascript', 'v8', 'deno']),
    browser: new Set(['chrome', 'chromium', 'firefox', 'safari', 'edge', 'opera']),
    os: new Set(['windows', 'windows server', 'linux', 'ubuntu', 'debian', 'macos', 'mac os x', 'ios', 'android', 'darwin']),
  };
  for (const [contextName, allowedNames] of Object.entries(contextNameAllowlist)) {
    const context = source[contextName];
    if (!context || typeof context !== 'object' || Array.isArray(context)) continue;
    const fields = context as Record<string, unknown>;
    const contextSafe: Record<string, unknown> = {};
    if (typeof fields.name === 'string' && allowedNames.has(fields.name.toLowerCase())) {
      contextSafe.name = fields.name;
    }
    const version = safeText(fields.version, /^\d{1,3}(?:\.\d{1,4}){0,3}$/, 32);
    if (version) contextSafe.version = version;
    if (Object.keys(contextSafe).length) safe[contextName] = contextSafe;
  }
  return safe;
}

function safeExtra(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const source = value as Record<string, unknown>;
  const safe: Record<string, unknown> = {};
  if (typeof source.diagnostic_code === 'string' && SAFE_AI_DIAGNOSTIC_CODES.has(source.diagnostic_code)) {
    safe.diagnostic_code = source.diagnostic_code;
  }
  if (typeof source.provider === 'string' && SAFE_AI_PROVIDERS.has(source.provider)) {
    safe.provider = source.provider;
  }
  const errorType = safeText(source.error_type, /^[A-Z][A-Za-z0-9]*(?:Error|Exception|Fault|Timeout)$/, 128);
  if (errorType) safe.error_type = errorType;
  for (const [field, minimum, maximum] of [
    ['status_code', 100, 599],
    ['body_size', 0, 1_000_000_000],
    ['input_tokens', 0, 1_000_000_000],
    ['output_tokens', 0, 1_000_000_000],
    ['total_tokens', 0, 1_000_000_000],
  ] as const) {
    const number = boundedInteger(source[field], minimum, maximum);
    if (number !== undefined) safe[field] = number;
  }
  return safe;
}

function safeTags(value: unknown): Record<string, string> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const source = value as Record<string, unknown>;
  const safe: Record<string, string> = {};
  if (typeof source.alert_type === 'string' && SAFE_ALERT_TYPES.has(source.alert_type)) {
    safe.alert_type = source.alert_type;
  }
  if (typeof source.severity === 'string' && SAFE_ALERT_SEVERITIES.has(source.severity)) {
    safe.severity = source.severity;
  }
  return safe;
}

function safeSpanData(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const source = value as Record<string, unknown>;
  const safe: Record<string, unknown> = {};
  for (const field of SAFE_SPAN_DATA_FIELDS) {
    const candidate = source[field];
    if (field === 'http.response.status_code') {
      const status = boundedInteger(candidate, 100, 599);
      if (status !== undefined) safe[field] = status;
    } else if ([
      'http.response.body.size', 'gen_ai.usage.input_tokens',
      'gen_ai.usage.output_tokens', 'gen_ai.usage.total_tokens',
    ].includes(field)) {
      const number = boundedInteger(candidate, 0, 1_000_000_000);
      if (number !== undefined) safe[field] = number;
    } else if (field === 'http.request.method' && typeof candidate === 'string' && SAFE_HTTP_METHODS.has(candidate)) {
      safe[field] = candidate;
    } else if (field === 'db.system' && typeof candidate === 'string' && SAFE_DB_SYSTEMS.has(candidate)) {
      safe[field] = candidate;
    } else if (field === 'db.operation' && typeof candidate === 'string' && SAFE_DB_OPERATIONS.has(candidate)) {
      safe[field] = candidate;
    }
  }
  return safe;
}

function safeSpan(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const source = value as Record<string, unknown>;
  const safe: Record<string, unknown> = {};
  for (const field of ['trace_id', 'span_id', 'parent_span_id']) {
    const id = safeText(source[field], /^(?:[0-9a-f]{16}|[0-9a-f]{32})$/i, 32);
    if (id) safe[field] = id;
  }
  for (const field of ['start_timestamp', 'timestamp']) {
    const timestamp = source[field];
    if (typeof timestamp === 'number' && Number.isFinite(timestamp) && timestamp >= 0 && timestamp <= 4_102_444_800) {
      safe[field] = timestamp;
    }
  }
  if (typeof source.op === 'string' && SAFE_SPAN_OPS.has(source.op)) safe.op = source.op;
  if (typeof source.status === 'string' && ['ok', 'error', 'cancelled'].includes(source.status)) {
    safe.status = source.status;
  }
  const data = safeSpanData(source.data);
  if (Object.keys(data).length) safe.data = data;
  return Object.keys(safe).length ? safe : null;
}

function safeStacktrace(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined;
  const stacktrace = value as { frames?: unknown };
  if (!Array.isArray(stacktrace.frames)) return undefined;
  const frames = stacktrace.frames.flatMap((candidate) => {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) return [];
    const frame = candidate as Record<string, unknown>;
    const safe: Record<string, unknown> = {};
    for (const field of ['lineno', 'colno']) {
      const line = boundedInteger(frame[field], 0, 10_000_000);
      if (line !== undefined) safe[field] = line;
    }
    const fn = safeText(frame.function, /^[A-Za-z_$][A-Za-z0-9_.$<>:-]*$/, 128);
    if (fn) safe.function = fn;
    const module = safeText(frame.module, /^[A-Za-z_][A-Za-z0-9_.]*$/, 128);
    if (module) safe.module = module;
    if (typeof frame.filename === 'string') {
      const filename = frame.filename.split(/[?#]/, 1)[0].split(/[\\/]/).pop() || '';
      const safeFilename = safeText(filename, /^[A-Za-z0-9_.-]+$/, 128);
      if (safeFilename) safe.filename = safeFilename;
    }
    if (typeof frame.in_app === 'boolean') safe.in_app = frame.in_app;
    return Object.keys(safe).length ? [safe] : [];
  });
  return frames.length ? { frames } : undefined;
}

function safeException(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined;
  const source = value as { values?: unknown };
  if (!Array.isArray(source.values)) return undefined;
  const values = source.values.flatMap((candidate) => {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) return [];
    const exception = candidate as Record<string, unknown>;
    const safe: Record<string, unknown> = { value: '[REDACTED]' };
    const type = safeText(exception.type, /^[A-Z][A-Za-z0-9]*(?:Error|Exception|Fault|Timeout)$/, 128);
    if (type) safe.type = type;
    const stacktrace = safeStacktrace(exception.stacktrace);
    if (stacktrace) safe.stacktrace = stacktrace;
    if (exception.mechanism && typeof exception.mechanism === 'object' && !Array.isArray(exception.mechanism)) {
      const mechanism = exception.mechanism as Record<string, unknown>;
      const safeMechanism: Record<string, unknown> = {};
      const mechanismType = safeText(mechanism.type, /^[A-Za-z0-9_.-]+$/, 64);
      if (mechanismType) safeMechanism.type = mechanismType;
      for (const field of ['handled', 'synthetic']) {
        if (typeof mechanism[field] === 'boolean') safeMechanism[field] = mechanism[field];
      }
      if (Object.keys(safeMechanism).length) safe.mechanism = safeMechanism;
    }
    return [safe];
  });
  return values.length ? { values } : undefined;
}

function safeThreads(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined;
  const source = value as { values?: unknown };
  if (!Array.isArray(source.values)) return undefined;
  const values = source.values.flatMap((candidate) => {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) return [];
    const thread = candidate as Record<string, unknown>;
    const safe: Record<string, unknown> = {};
    for (const field of ['current', 'crashed']) {
      if (typeof thread[field] === 'boolean') safe[field] = thread[field];
    }
    const stacktrace = safeStacktrace(thread.stacktrace);
    if (stacktrace) safe.stacktrace = stacktrace;
    return Object.keys(safe).length ? [safe] : [];
  });
  return values.length ? { values } : undefined;
}

function safeMeasurements(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const source = value as Record<string, unknown>;
  const safe: Record<string, unknown> = {};
  for (const field of SAFE_MEASUREMENTS) {
    const candidate = source[field];
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) continue;
    const measurement = candidate as Record<string, unknown>;
    const number = measurement.value;
    if (typeof number !== 'number' || !Number.isFinite(number) || number < 0 || number > 1_000_000_000) continue;
    const safeMeasurement: Record<string, unknown> = { value: number };
    if (['millisecond', 'second', 'none', 'byte', 'ratio', 'hertz'].includes(String(measurement.unit))) {
      safeMeasurement.unit = measurement.unit;
    }
    safe[field] = safeMeasurement;
  }
  return safe;
}

function safeSdk(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined;
  const source = value as Record<string, unknown>;
  const safe: Record<string, unknown> = {};
  const name = safeText(source.name, /^sentry\.[A-Za-z0-9_.-]+$/, 128);
  if (name) safe.name = name;
  const version = safeText(source.version, /^\d{1,3}(?:\.\d{1,4}){0,3}(?:[-+][A-Za-z0-9.-]+)?$/, 64);
  if (version) safe.version = version;
  if (Array.isArray(source.packages)) {
    const packages = source.packages.flatMap((candidate) => {
      if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) return [];
      const pkg = candidate as Record<string, unknown>;
      const packageName = safeText(pkg.name, /^@?sentry\/[A-Za-z0-9_.-]+$/, 128);
      const packageVersion = safeText(pkg.version, /^\d{1,3}(?:\.\d{1,4}){0,3}(?:[-+][A-Za-z0-9.-]+)?$/, 64);
      return packageName && packageVersion ? [{ name: packageName, version: packageVersion }] : [];
    });
    if (packages.length) safe.packages = packages;
  }
  return Object.keys(safe).length ? safe : undefined;
}

function safeRouteTransaction(value: unknown, source: unknown): string | undefined {
  if (source !== 'route' || typeof value !== 'string') return undefined;
  const segment = String.raw`(?:[A-Za-z0-9_.-]+|\{[A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)?\})`;
  return new RegExp(`^(?:[A-Z]+ )?/(?:${segment}(?:/${segment})*)?$`).test(value)
    ? value
    : undefined;
}

function safeSentrySpan(span: unknown): Record<string, unknown> | null {
  return safeSpan(span);
}

function scrubSentryEvent(event: MutableSentryEvent): MutableSentryEvent {
  const safe = Object.fromEntries(
    Object.entries(event).filter(([key]) => SAFE_EVENT_FIELDS.has(key))
  ) as MutableSentryEvent;

  if (typeof safe.event_id !== 'string' || !/^[0-9a-f]{32}$/i.test(safe.event_id)) delete safe.event_id;
  for (const field of ['timestamp', 'start_timestamp'] as const) {
    const value = safe[field];
    if (value !== undefined && (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 4_102_444_800)) {
      delete safe[field];
    }
  }
  if (!['python', 'javascript', 'native', 'other'].includes(String(safe.platform))) delete safe.platform;
  if (!['fatal', 'error', 'warning', 'log', 'info', 'debug'].includes(String(safe.level))) delete safe.level;
  if (safe.type !== 'transaction') delete safe.type;
  for (const field of ['environment', 'release', 'dist'] as const) {
    if (safe[field] !== undefined) {
      const label = safeText(safe[field], /^[A-Za-z0-9_.+:-]+$/, 128);
      if (label) safe[field] = label;
      else delete safe[field];
    }
  }

  const sdk = safeSdk(safe.sdk);
  if (sdk) safe.sdk = sdk;
  else delete safe.sdk;

  if (safe.request && typeof safe.request === 'object' && !Array.isArray(safe.request)) {
    const method = (safe.request as Record<string, unknown>).method;
    safe.request = typeof method === 'string' && SAFE_HTTP_METHODS.has(method) ? { method } : undefined;
    if (!safe.request) delete safe.request;
  } else delete safe.request;

  const contexts = safeContexts(safe.contexts);
  if (Object.keys(contexts).length) safe.contexts = contexts;
  else delete safe.contexts;
  const trace = safeTraceContext(safe.trace);
  if (Object.keys(trace).length) safe.trace = trace;
  else delete safe.trace;

  const extra = safeExtra(safe.extra);
  if (Object.keys(extra).length) safe.extra = extra;
  else delete safe.extra;
  const tags = safeTags(safe.tags);
  if (Object.keys(tags).length) safe.tags = tags;
  else delete safe.tags;

  const exception = safeException(safe.exception);
  if (exception) safe.exception = exception;
  else delete safe.exception;
  const threads = safeThreads(safe.threads);
  if (threads) safe.threads = threads;
  else delete safe.threads;

  if (Array.isArray(safe.spans)) {
    safe.spans = safe.spans.flatMap((span) => {
      const cleanSpan = safeSentrySpan(span);
      return cleanSpan ? [cleanSpan] : [];
    });
  } else delete safe.spans;
  const measurements = safeMeasurements(safe.measurements);
  if (Object.keys(measurements).length) safe.measurements = measurements;
  else delete safe.measurements;

  if (safe.transaction_info && typeof safe.transaction_info === 'object' && !Array.isArray(safe.transaction_info)) {
    const source = (safe.transaction_info as Record<string, unknown>).source;
    if (typeof source === 'string' && ['route', 'url', 'custom', 'task', 'component', 'view'].includes(source)) {
      safe.transaction_info = { source };
    } else delete safe.transaction_info;
  } else delete safe.transaction_info;

  if (typeof safe.message === 'string') safe.message = '[REDACTED]';
  if (safe.logentry) safe.logentry = { message: '[REDACTED]' };
  if (typeof safe.transaction === 'string') {
    const source = (safe.transaction_info as Record<string, unknown> | undefined)?.source;
    safe.transaction = safeRouteTransaction(safe.transaction, source) || '[REDACTED TRANSACTION]';
  }
  delete safe.fingerprint;
  const diagnosticCode = extra.diagnostic_code;
  if (typeof diagnosticCode === 'string' && SAFE_AI_DIAGNOSTIC_CODES.has(diagnosticCode)) {
    const fingerprint = ['{{ default }}', diagnosticCode];
    for (const key of ['provider', 'error_type'] as const) {
      const value = extra[key];
      if (typeof value === 'string') fingerprint.push(value);
    }
    safe.fingerprint = fingerprint;
  }

  // `breadcrumbs` and `user` are deliberately excluded by the top-level
  // allowlist. Both are independent event payload channels.
  return safe;
}

export function createSentryPrivacyCallbacks(): Pick<
  NonNullable<Parameters<typeof Sentry.init>[0]>,
  'beforeBreadcrumb' | 'beforeSend' | 'beforeSendSpan' | 'beforeSendTransaction'
> {
  return {
    beforeBreadcrumb() {
      // Breadcrumbs can retain arbitrary logs, URLs, and form values until a
      // later event. Do not buffer them for this medical application.
      return null;
    },
    beforeSend(event) {
      try {
        return scrubSentryEvent(event as unknown as MutableSentryEvent) as unknown as typeof event;
      } catch {
        // Drop an event if its privacy scrubber fails; never send it raw.
        return null;
      }
    },
    beforeSendTransaction(event) {
      try {
        return scrubSentryEvent(event as unknown as MutableSentryEvent) as unknown as typeof event;
      } catch {
        return null;
      }
    },
    beforeSendSpan(span) {
      try {
        return safeSentrySpan(span) as typeof span | null;
      } catch {
        return null;
      }
    },
  };
}

let isInitialized = false;

export function initSentry() {
  if (isInitialized) return;
  if (!SENTRY_DSN) {
    // eslint-disable-next-line no-console
    console.info('[sentry] VITE_SENTRY_DSN not set — Sentry disabled.');
    return;
  }

  Sentry.init({
    dsn: SENTRY_DSN,
    environment: SENTRY_ENV,
    release: import.meta.env.VITE_APP_VERSION || 'unknown',
    tracesSampleRate: SENTRY_TRACES_SAMPLE_RATE,
    sendDefaultPii: false,
    // Drop errors from browser extensions / preview bots.
    denyUrls: [
      /extensions\//i,
      /^chrome:\/\//i,
      /^moz-extension:\/\//i,
    ],
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({
        // Disable session replay by default — replays can capture form
        // inputs which is a PII risk for a medical app. Enable only after
        // legal review and only for admin role.
        maskAllText: true,
        blockAllMedia: true,
      }),
    ],
    // Replays use a separate envelope path and do not pass through the event
    // callbacks below. Keep both recording modes explicitly disabled.
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
    // Owner round-12 P1: pageload/navigation traces are NOT routed through
    // beforeSend — request.url carries the full URL (legacy ?token= handout
    // form) and http spans repeat it in span.description. Scrub the same
    // way regardless of trace sampling (errors are always sent, traces are
    // sampled — both must be credential-free).
    // The installed Sentry JS 8.x SDK sends child spans through this callback
    // separately from beforeSendTransaction. Strip their descriptions and
    // retain only explicitly safe timing/status attributes.
    ...createSentryPrivacyCallbacks(),
  });

  isInitialized = true;
}

export function captureException(error: unknown, context: Record<string, unknown>): void {
  if (!isInitialized) {
    // eslint-disable-next-line no-console
    console.error('[sentry-disabled]', error, context);
    return;
  }
  Sentry.captureException(error, { extra: context });
}

export function captureMessage(message: string, level: 'info' | 'warning' | 'error' | 'fatal' | 'debug' | 'log' = 'info'): void {
  if (!isInitialized) return;
  Sentry.captureMessage(message, level);
}

export { Sentry };
