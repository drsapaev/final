/** Match Python's Unicode code point length for the recovery API minimum. */
export function hasRecoveryPasswordMinimum(password: string): boolean {
  return Array.from(password).length >= 8;
}
