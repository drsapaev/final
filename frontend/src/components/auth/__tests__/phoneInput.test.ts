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
