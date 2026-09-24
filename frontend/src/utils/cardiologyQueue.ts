export interface SpecialistQueueEntry {
  queue: Record<string, unknown>;
  entry: Record<string, unknown>;
}

/** Select registrar entries by their canonical Doctor.id queue owner. */
export function selectEntriesForSpecialist(
  payload: unknown,
  specialistId: string | number | null | undefined,
): SpecialistQueueEntry[] {
  if (specialistId === null || specialistId === undefined || String(specialistId).trim() === '') {
    return [];
  }

  const queues = (payload as { queues?: unknown[] } | null)?.queues;
  if (!Array.isArray(queues)) return [];

  return queues.flatMap((candidate) => {
    if (!candidate || typeof candidate !== 'object') return [];
    const queue = candidate as Record<string, unknown>;
    if (String(queue.specialist_id ?? '') !== String(specialistId)) return [];

    const entries = Array.isArray(queue.entries) ? queue.entries : [];
    return entries.flatMap((item) =>
      item && typeof item === 'object'
        ? [{ queue, entry: item as Record<string, unknown> }]
        : [],
    );
  });
}
