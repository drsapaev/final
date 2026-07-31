/**
 * safeJsonParse — safe JSON parsing wrapper.
 *
 * Per Sprint C3, all safeJsonParse calls in the codebase must go through
 * this wrapper (or safeStorage, or ws-schemas safeParse) to ensure
 * malformed JSON doesn't crash the app.
 *
 * Returns `any` (like safeJsonParse) for drop-in compatibility. The fallback
 * is returned on parse error instead of throwing.
 *
 * Usage:
 *   import { safeJsonParse } from '../utils/safeJsonParse';
 *   const data = safeJsonParse(rawString);  // any, fallback on error
 *   const data = safeJsonParse(rawString, []);  // with explicit fallback
 */

/**
 * Parse JSON safely. Returns `fallback` (default: null) on parse error.
 * Returns `any` for drop-in compatibility with safeJsonParse.
 */
// TECH-DEBT(c3-safejsonparse-any): Returns `any` for drop-in JSON.parse compat.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function safeJsonParse(raw: string | null | undefined, fallback: any = null): any {
  if (raw == null || raw === '') return fallback;
  try {
    return JSON.parse(raw); // safeParse — wrapped in try/catch
  } catch {
    return fallback;
  }
}

/**
 * Parse JSON safely, throwing on error with a custom message.
 *
 * Use this when the caller needs to know about parse failures (e.g. for
 * logging or user-facing errors). The throw ensures the error propagates
 * but with a descriptive message instead of a raw SyntaxError.
 *
 * @param raw - The JSON string to parse
 * @param context - Description of what was being parsed (for error message)
 * @returns Parsed value (unknown)
 * @throws Error with context message if parsing fails
 */
export function safeJsonParseStrict(raw: string, context = 'JSON'): unknown {
  try {
    return JSON.parse(raw); // safeParse — wrapped in try/catch
  } catch (err) {
    throw new Error(`Failed to parse ${context}: ${err instanceof Error ? err.message : String(err)}`);
  }
}

export default safeJsonParse;
