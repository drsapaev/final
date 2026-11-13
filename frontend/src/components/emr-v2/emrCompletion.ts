export type EMRCompletionBlockReason = 'save_failed' | 'conflict' | 'access_denied' | 'read_failed' | 'not_ready';

export class EMRCompletionBlockedError extends Error {
  readonly reason: EMRCompletionBlockReason;

  constructor(reason: EMRCompletionBlockReason) {
    super(`Visit completion blocked: ${reason}`);
    this.name = 'EMRCompletionBlockedError';
    this.reason = reason;
  }
}

type EMRRecord = Record<string, unknown> & {
  id: string | number;
  data: Record<string, unknown>;
  status?: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function isPersistedEMR(value: unknown): value is EMRRecord {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  return (typeof value.id === 'number' && Number.isFinite(value.id) && value.id > 0)
    || (typeof value.id === 'string' && value.id.trim().length > 0);
}

function hasCompletionReadyStatus(value: unknown): value is EMRRecord {
  return isPersistedEMR(value)
    && typeof value.status === 'string'
    && value.status.trim().length > 0
    && value.status.trim().toLowerCase() !== 'draft';
}

/** Return only a persisted server snapshot suitable for visit-completion checks. */
export async function readSavedEMRForCompletion({
  shouldSave,
  save,
  reload,
}: {
  shouldSave: boolean;
  save: () => Promise<unknown>;
  reload: () => Promise<unknown>;
}): Promise<Record<string, unknown>> {
  if (shouldSave) {
    let saveResult: unknown;
    try {
      saveResult = await save();
    } catch {
      throw new EMRCompletionBlockedError('save_failed');
    }

    if (isRecord(saveResult) && saveResult.accessDenied) {
      throw new EMRCompletionBlockedError('access_denied');
    }
    if (isRecord(saveResult) && saveResult.conflict) {
      throw new EMRCompletionBlockedError('conflict');
    }
    if (!isPersistedEMR(saveResult)) {
      throw new EMRCompletionBlockedError('save_failed');
    }
  }

  let latestEMR: unknown;
  try {
    latestEMR = await reload();
  } catch {
    throw new EMRCompletionBlockedError('read_failed');
  }

  if (isRecord(latestEMR) && latestEMR.accessDenied) {
    throw new EMRCompletionBlockedError('access_denied');
  }
  if (!isPersistedEMR(latestEMR)) {
    throw new EMRCompletionBlockedError('read_failed');
  }
  if (!hasCompletionReadyStatus(latestEMR)) {
    throw new EMRCompletionBlockedError('not_ready');
  }

  return latestEMR.data;
}

export function emrTextValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (isRecord(value)) {
    for (const key of ['main', 'primary', 'text', 'value', 'description']) {
      if (typeof value[key] === 'string' && value[key]) return value[key] as string;
    }
  }
  return '';
}

/**
 * EMRTREAT-FE-001 (audit 3886): canonical treatment text — mirrors the
 * backend's `get_emr_text_field(data, "treatment")` chain
 * (backend/app/services/emr_contract.py): the narrative `treatment` field
 * first, then `medications.text` (the field the visible TreatmentSection
 * editor is bound to), then the legacy `plan.treatment`. The completeness
 * indicator must count the text the doctor actually entered in the
 * visible editor, not only the top-level legacy key — a genuine treatment
 * plan typed into the editor must not leave «Лечение» listed as missing.
 */
export function emrTreatmentText(data: Record<string, unknown> | null | undefined): string {
  const direct = emrTextValue((data as { treatment?: unknown } | null | undefined)?.treatment).trim();
  if (direct) return direct;

  const medications = (data as { medications?: unknown } | null | undefined)?.medications;
  if (isRecord(medications)) {
    const medicationText = emrTextValue(medications.text).trim();
    if (medicationText) return medicationText;
  }

  const plan = (data as { plan?: unknown } | null | undefined)?.plan;
  if (isRecord(plan)) {
    const planTreatment = emrTextValue(plan.treatment).trim();
    if (planTreatment) return planTreatment;
  }

  return '';
}
