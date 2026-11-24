/** Privacy boundary for verification proofs, SMS text and inbox references. */

const VERIFICATION_PATH = /(?:^|\/)(?:phone-verification|2fa)(?:\/|$)|(?:^|\/)password-reset\/verify-phone(?:\/|$)|(?:^|\/)patient-access\/(?:verify-otp|activate\/confirm)(?:\/|$)/i;
const NAMED_PROOF_ASSIGNMENT = /(?:^|[\s{,('"?&])["']?(?:verification[\s_-]?code|otp[\s_-]?code|totp[\s_-]?code|backup[\s_-]?code|otp|totp)["']?\s*[:=]/i;
const INVITATION_REFERENCE = /\/(?:api\/v1\/)?notifications\/visit-invitation-(?:tasks|recoveries)\/|(?:^|[?&#])invitation(?:_recovery)?=/i;

/** Only recognize complete route segments; an unrelated `code` may be ICD. */
export function isSensitiveVerificationUrl(value: unknown): boolean {
  if (typeof value !== 'string' || !value) return false;
  let path = value.split(/[?#]/, 1)[0];
  try {
    path = decodeURIComponent(path);
  } catch {
    // Decode valid byte escapes even when an unrelated escape is malformed.
    path = path.replace(/%([0-9a-f]{2})/gi, (_, hex: string) => String.fromCharCode(parseInt(hex, 16)));
  }
  return VERIFICATION_PATH.test(path.replace(/\/+$/, ''));
}

/** Avoid logging raw JSON/form/repr strings containing a named proof. */
export function redactVerificationString(value: string): string {
  if (isSensitiveVerificationUrl(value)) {
    return '[REDACTED VERIFICATION]';
  }
  const decoded = value.replace(/%([0-9a-f]{2})/gi, (_, hex: string) => String.fromCharCode(parseInt(hex, 16)));
  if (INVITATION_REFERENCE.test(decoded)) return '[REDACTED INVITATION]';
  return NAMED_PROOF_ASSIGNMENT.test(value) || NAMED_PROOF_ASSIGNMENT.test(decoded)
    ? '[REDACTED VERIFICATION]'
    : value;
}
