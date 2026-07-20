export const DENTISTRY_SPECIALTIES = [
  'dental',
  'dentist',
  'dentistry',
  'stomatology',
];

export function isDentistrySpecialty(value) {
  if (typeof value !== 'string') {
    return false;
  }

  return DENTISTRY_SPECIALTIES.includes(value.trim().toLowerCase());
}
