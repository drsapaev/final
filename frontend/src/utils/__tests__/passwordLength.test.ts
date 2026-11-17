import { describe, expect, it } from 'vitest';
import { hasRecoveryPasswordMinimum } from '../passwordLength';

describe('recovery password length', () => {
  it.each([
    ['1234567', false],
    ['12345678', true],
    ['😀😀😀😀', false],
    ['😀😀😀😀😀😀😀😀', true],
    ['😀abc123', false],
    ['😀abc1234', true],
  ])('matches the backend code point floor for %s', (password, expected) => {
    expect(hasRecoveryPasswordMinimum(password)).toBe(expected);
  });
});
