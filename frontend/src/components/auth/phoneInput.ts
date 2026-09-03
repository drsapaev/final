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
 * The normalizer is idempotent — feeding its own output back is a no-op.
 * Typing always arrives through the '+' prefix, so the first '998' is
 * the country code. A bare paste has no '+': there, a value of exactly
 * 9 digits starting with '998' is an operator-99 LOCAL number
 * (99 + '8…') whose digits belong to the subscriber and must survive
 * (#2801 review follow-up); longer bare values get the code stripped.
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
  const hasPlus = String(raw ?? '').trim().startsWith('+');
  let digits = String(raw ?? '').replace(/\D/g, '');

  // Backspace ate part of the '+998' prefix → snap back to the prefix.
  if (digits.length < 3) {
    return UZ_PHONE_PREFIX;
  }

  // 1) Country code at the start. Typed input always carries it (the
  //    field prefix); a bare paste carries it UNLESS the value is
  //    exactly a 9-digit local — operator-99 locals also start with
  //    '998', and those digits belong to the subscriber.
  if (digits.startsWith('998') && (hasPlus || digits.length !== 9)) {
    digits = digits.slice(3);
  }

  // 2) 8-prefixed RF dialing: 8 + full number (13 digits) or the
  //    legacy local form 8 + 9 digits (10 total).
  if (
    digits.startsWith('8') &&
    (digits.length === 10 || digits.length >= 12)
  ) {
    digits = digits.slice(1);
  }

  // 3) A second code left after RF cleanup (e.g. the fixed prefix
  //    followed by an RF-style paste). Only fires at full length:
  //    a typed subscriber tail is ≤ 9 digits and must keep its own
  //    leading '998' digits.
  if (digits.startsWith('998') && digits.length >= 12) {
    digits = digits.slice(3);
  }

  return UZ_PHONE_PREFIX + digits.slice(0, UZ_SUBSCRIBER_DIGITS);
};
