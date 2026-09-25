export const DERMATOLOGY_PANEL_TABS = ['queue', 'visit', 'patients'] as const;

/** Resolve retired dermatologist tabs while keeping patient/visit query values intact. */
export function getDermatologyTabAliases(search: string): Record<string, string> {
  const searchParams = new URLSearchParams(search);
  const hasVisit = Boolean(searchParams.get('visitId') || searchParams.get('visit_id'));

  return {
    history: 'patients',
    appointments: hasVisit ? 'visit' : 'queue',
    skin: 'visit',
    cosmetic: 'visit',
    photos: 'visit',
    services: 'visit',
    ai: 'visit',
  };
}
