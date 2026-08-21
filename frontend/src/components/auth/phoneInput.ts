/**
 * Phone input normalization for the auth forms (UZ numbers).
 *
 * The field shows a FIXED '+998' prefix — the user types only the 9
 * subscriber digits. This removes the fundamental ambiguity of the old
 * formatter: a local number starting with 99/98 followed by '8' begins
 * with '998…', which the old stateless formatter mistook for the country
 * code on every keystroke, prepending another '+998' each time. After the
 * third digit the composed value hit the 12-digit cap and the field
 * silently stopped accepting input (reproduced character-by-character).
 *
 * The normalizer is idempotent — feeding its own output back is a no-op —
 * which makes character typing, paste, and autofill all behave the same.
 */

export const UZ_PHONE_PREFIX = '+998';
export const UZ_SUBSCRIBER_DIGITS = 9;

export const validatePhone = (phone: string): boolean =>
  /^\+998\d{9}$/.test(phone);

/**
 * Accepts anything the input element can produce (typing, paste, autofill,
 * programmatic set) and returns the canonical field value:
 * '+998' + 0..9 subscriber digits. Backspacing into the prefix snaps back
 * to the bare prefix instead of leaking prefix digits into the number.
 */
export const normalizePhoneInput = (raw: string): string => {
  let digits = String(raw ?? '').replace(/\D/g, '');

  // Backspace ate part of the '+998' prefix → snap back to the prefix.
  if (digits.length < 3) {
    return UZ_PHONE_PREFIX;
  }

  // 8-prefixed RF-style paste: 8 + 998 + 9 digits (13 total).
  if (digits.startsWith('8') && digits.length >= 12) {
    digits = digits.slice(1);
  }

  // Full number with the country code (pasted, autofilled, or the field's
  // own prefix) — strip the code so the prefix is never duplicated.
  if (digits.startsWith('998')) {
    digits = digits.slice(3);
  }

  return UZ_PHONE_PREFIX + digits.slice(0, UZ_SUBSCRIBER_DIGITS);
};
