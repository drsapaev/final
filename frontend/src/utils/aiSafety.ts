/**
 * Trust only the server's explicit safety contract before publishing medical
 * AI content. Legacy top-level flags are not a substitute for this envelope.
 */
export function hasMedicalAiSafety(value: unknown): boolean {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const metadata = (value as Record<string, unknown>).ai_safety_meta;
  return metadata !== null && typeof metadata === 'object' && !Array.isArray(metadata)
    && (metadata as Record<string, unknown>).requires_doctor_confirmation === true;
}

export function assertMedicalAiSafety(value: unknown): void {
  if (!hasMedicalAiSafety(value)) {
    throw new Error('AI response is missing the required safety confirmation');
  }
}
