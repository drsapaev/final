// src/utils/phoneUtils.ts
// Phase 1 — migrated from .js. Pure functions; types added.

const UZBEKISTAN_PHONE_DIGITS = 12;

function extractDigits(value: unknown): string {
  return String(value ?? '').replace(/\D/g, '');
}

export function normalizeUzbekPhoneForApi(value: unknown): string {
  const digits = extractDigits(value);

  if (!digits) {
    return '';
  }

  if (digits.startsWith('998')) {
    return `+${digits.slice(0, UZBEKISTAN_PHONE_DIGITS)}`;
  }

  if (digits.length >= 9) {
    return `+998${digits.slice(-9)}`;
  }

  return `+${digits}`;
}

export function formatUzbekPhoneDisplay(value: unknown): string {
  const normalized = normalizeUzbekPhoneForApi(value);
  const digits = extractDigits(normalized);

  if (!digits) {
    return '';
  }

  if (digits.length <= 3) {
    return `+${digits}`;
  }

  if (digits.length <= 5) {
    return `+${digits.slice(0, 3)} ${digits.slice(3)}`;
  }

  if (digits.length <= 8) {
    return `+${digits.slice(0, 3)} ${digits.slice(3, 5)} ${digits.slice(5)}`;
  }

  if (digits.length <= 10) {
    return `+${digits.slice(0, 3)} ${digits.slice(3, 5)} ${digits.slice(5, 8)} ${digits.slice(8)}`;
  }

  return `+${digits.slice(0, 3)} ${digits.slice(3, 5)} ${digits.slice(5, 8)} ${digits.slice(8, 10)} ${digits.slice(10)}`;
}

export function isValidUzbekPhone(value: unknown): boolean {
  const digits = extractDigits(normalizeUzbekPhoneForApi(value));
  return digits.length === UZBEKISTAN_PHONE_DIGITS && digits.startsWith('998');
}
