export type DermatologyVisitId = string | number | null | undefined;

export interface DermatologyVisitContext {
  appointmentId: DermatologyVisitId;
  patientId: DermatologyVisitId;
  visitId: DermatologyVisitId;
  queueEntryId: DermatologyVisitId;
}

function normalizedId(value: DermatologyVisitId): string | null {
  if (value === null || value === undefined) return null;
  const normalized = String(value).trim();
  return normalized.length > 0 ? normalized : null;
}

export function isSameDermatologyVisit(
  expected: DermatologyVisitContext,
  current: DermatologyVisitContext,
): boolean {
  return (
    normalizedId(expected.appointmentId) === normalizedId(current.appointmentId) &&
    normalizedId(expected.patientId) === normalizedId(current.patientId) &&
    normalizedId(expected.visitId) === normalizedId(current.visitId) &&
    normalizedId(expected.queueEntryId) === normalizedId(current.queueEntryId)
  );
}

export function canCompleteDermatologyVisit(
  queueCanComplete: boolean,
  appointmentId: DermatologyVisitId,
  appointmentCanComplete: boolean,
): boolean {
  return queueCanComplete && (normalizedId(appointmentId) === null || appointmentCanComplete);
}

function positiveInteger(value: unknown): number | null {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object'
    ? value as Record<string, unknown>
    : {};
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

export function toPrescriptionSystemRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const source = value as Record<string, unknown>;
  const medications = Array.isArray(source.medications)
    ? source.medications.map((rawMedication, index) => {
        const medication = record(rawMedication);
        return {
          ...medication,
          id: positiveInteger(medication.id) ?? index + 1,
          name: text(medication.name),
          dosage: text(medication.dosage),
          frequency: text(medication.frequency),
          duration: text(medication.duration),
          instructions: text(medication.instructions),
          quantity: positiveInteger(medication.quantity) ?? 1,
        };
      })
    : [];

  return {
    ...source,
    medications,
    instructions: text(source.instructions),
    doctorNotes: text(source.doctorNotes ?? source.doctor_notes),
    isDraft: source.isDraft === false || source.is_draft === false ? false : true,
    createdAt: source.createdAt ?? source.created_at ?? null,
    printedAt: source.printedAt ?? source.printed_at ?? null,
  };
}

export async function postDermatologyPrescription(
  payload: PrescriptionCreatePayload,
  post: (appointmentId: number, payload: PrescriptionCreatePayload) => Promise<{
    status: number;
    data: unknown;
  }>,
): Promise<Record<string, unknown>> {
  try {
    const response = await post(payload.appointment_id, payload);
    if (response.status < 200 || response.status >= 300) {
      throw Object.assign(new Error('Prescription save failed'), {
        response: { status: response.status },
      });
    }
    const savedPrescription = toPrescriptionSystemRecord(response.data);
    if (
      !savedPrescription ||
      positiveInteger(savedPrescription.id) === null ||
      savedPrescription.isDraft !== false
    ) {
      throw Object.assign(new Error('Prescription save failed'), {
        response: { status: response.status },
      });
    }
    return savedPrescription;
  } catch (error: unknown) {
    const response = record(record(error).response);
    const status = typeof response.status === 'number' ? response.status : undefined;
    throw Object.assign(new Error('Prescription save failed'), {
      ...(status === undefined ? {} : { response: { status } }),
    });
  }
}

export interface PrescriptionCreatePayload {
  appointment_id: number;
  visit_id: number | null;
  emr_id: number | null;
  medications: Array<{
    name: string;
    dosage: string;
    frequency: string;
    duration: string;
    instructions: string | null;
    quantity: number;
  }>;
  instructions: string | null;
  doctor_notes: string | null;
  is_draft: false;
}

export function toPrescriptionCreatePayload(
  value: unknown,
  ids: { appointmentId: DermatologyVisitId; visitId: DermatologyVisitId; emrId: unknown },
): PrescriptionCreatePayload {
  const appointmentId = positiveInteger(ids.appointmentId);
  if (appointmentId === null) {
    throw new Error('Prescription requires an appointment ID');
  }

  const source = record(value);
  const sourceMedications = Array.isArray(source.medications) ? source.medications : [];

  return {
    appointment_id: appointmentId,
    visit_id: positiveInteger(ids.visitId),
    emr_id: positiveInteger(ids.emrId),
    medications: sourceMedications.map((rawMedication) => {
      const medication = record(rawMedication);
      const parsedQuantity = Number(medication.quantity);
      return {
        name: text(medication.name),
        dosage: text(medication.dosage),
        frequency: text(medication.frequency),
        duration: text(medication.duration),
        instructions: text(medication.instructions) || null,
        quantity: Number.isSafeInteger(parsedQuantity) && parsedQuantity > 0 ? parsedQuantity : 1,
      };
    }),
    instructions: text(source.instructions) || null,
    doctor_notes: text(source.doctor_notes ?? source.doctorNotes) || null,
    is_draft: false,
  };
}
