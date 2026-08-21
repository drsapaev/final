import { describe, expect, it } from 'vitest';
import { normalizePhoneInput, validatePhone } from '../phoneInput';

/** Replay real keystrokes the way the controlled input produces them:
 *  every keypress feeds the previous field value + one character. */
function type(chars: string): string {
  let v = '+998';
  for (const ch of chars) v = normalizePhoneInput(v + ch);
  return v;
}

describe('normalizePhoneInput (UZ mask with fixed +998 prefix)', () => {
  it('empty input keeps the bare prefix', () => {
    expect(normalizePhoneInput('')).toBe('+998');
    expect(normalizePhoneInput('+')).toBe('+998');
  });

  it('regression: typing a local number that starts with 998 must not cascade', () => {
    // Old bug: '998…' prefix of a local number was treated as the country
    // code on every keystroke, prepending extra '+998' until the field
    // froze at 12 digits and swallowed all further keystrokes.
    expect(type('9989998998')).toBe('+998998999899');
  });

  it('typing a regular local number accumulates subscriber digits', () => {
    expect(type('901234567')).toBe('+998901234567');
    expect(type('998999899')).toBe('+998998999899');
  });

  it('caps subscriber part at 9 digits', () => {
    expect(type('9989998998')).toBe('+998998999899'); // 10th digit dropped
    expect(type('99899989982')).toBe('+998998999899');
  });

  it('paste with full international number is stripped to the subscriber part', () => {
    expect(normalizePhoneInput('+9989989998998')).toBe('+998998999899');
    expect(normalizePhoneInput('9989989998998')).toBe('+998998999899');
    expect(normalizePhoneInput('+998 99 899 98 99')).toBe('+998998999899');
  });

  it('paste in 8-prefixed RF style is normalized', () => {
    const rfPaste = '8' + '998' + '998999899'; // 13 digits
    expect(rfPaste).toHaveLength(13);
    expect(normalizePhoneInput(rfPaste)).toBe('+998' + '998999899');
  });

  it('is idempotent for its own output', () => {
    const once = normalizePhoneInput('+998998998998998');
    expect(normalizePhoneInput(once)).toBe(once);
  });

  it('backspace cannot delete the +998 prefix', () => {
    expect(normalizePhoneInput('+99899899989')).toBe('+99899899989');
    expect(normalizePhoneInput('+99')).toBe('+998');
  });
});

describe('validatePhone', () => {
  it('accepts exactly +998 plus 9 digits', () => {
    expect(validatePhone('+998998999899')).toBe(true);
    expect(validatePhone('+9989989998998')).toBe(false);
    expect(validatePhone('+99899899989')).toBe(false);
    expect(validatePhone('998998999899')).toBe(false);
  });
});

describe('bare paste vs typed input (#2801 review follow-up)', () => {
  it('keeps all digits of a bare 9-digit local paste starting with 998', () => {
    // Operator-99 number whose subscriber begins with '8' — the leading
    // '998' is NOT the country code here. Old code ate three real digits.
    expect(normalizePhoneInput('998901234')).toBe('+998' + '998901234');
    expect(validatePhone(normalizePhoneInput('998901234'))).toBe(true);
  });

  it('still strips the code from longer bare international pastes', () => {
    expect(normalizePhoneInput('998998901234')).toBe('+998' + '998901234'); // 12
    expect(normalizePhoneInput('9989989012349')).toBe('+998' + '998901234'); // 13, capped
  });

  it('normalizes the legacy RF local paste 8 + 9 digits (10 total)', () => {
    expect(normalizePhoneInput('8' + '998901234')).toBe('+998' + '998901234');
    expect(normalizePhoneInput('8' + '901234567')).toBe('+998' + '901234567');
  });

  it('merge-paste after the fixed prefix resolves to the same subscriber', () => {
    // Cursor at the end of '+998', local digits pasted without selection:
    // the DOM value is prefix + pasted text.
    expect(normalizePhoneInput('+998' + '998901234')).toBe('+998' + '998901234');
    // RF-style paste merged after the prefix also collapses correctly.
    expect(normalizePhoneInput('+998' + '8998998901234')).toBe(
      '+998' + '998901234',
    );
  });

  it('a bare 9-digit local starting with 8 is a subscriber, not RF dialing', () => {
    expect(normalizePhoneInput('890123456')).toBe('+998' + '890123456');
  });

  it('typing a subscriber that starts with 998 keeps every digit', () => {
    // Regression guard for the paste fix: rule 3 must never eat the
    // typed tail's own leading '998'.
    let v = '+998';
    for (const ch of '998901234') v = normalizePhoneInput(v + ch);
    expect(v).toBe('+998' + '998901234');
  });
});
