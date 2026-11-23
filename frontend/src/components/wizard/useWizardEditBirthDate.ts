import { useEffect, useRef, useState, type Dispatch, type RefObject, type SetStateAction } from 'react';
import { convertDateFromISO, convertDateToISO, formatBirthDateInput,
  parseWizardBaseline, resolveInitialPatientId, wizardContentSignature } from './wizardUtils';

type PatientId = string | number;
type WizardWithBirthDate = { patient: { id: PatientId | null; birth_date: string } };

interface WizardBirthDateOptions<T extends WizardWithBirthDate> {
  isOpen: boolean;
  editMode: boolean;
  initialData?: Record<string, unknown> | null;
  getPatient: (id: PatientId) => Promise<{ id: PatientId; birth_date?: string | null }>;
  initialContentRef: RefObject<string>;
  setWizardData: Dispatch<SetStateAction<T>>;
}

export function useWizardEditBirthDate<T extends WizardWithBirthDate>({
  isOpen, editMode, initialData, getPatient, initialContentRef, setWizardData,
}: WizardBirthDateOptions<T>) {
  const [formattedBirthDate, setFormattedBirthDate] = useState('');
  const birthDateEditedRef = useRef(false);

  useEffect(() => {
    if (!isOpen || !editMode || initialData?.patient_birth_date) return;
    const patientId = resolveInitialPatientId(initialData);
    if (typeof patientId !== 'number' && typeof patientId !== 'string') return;

    let cancelled = false;
    void getPatient(patientId).then((patient) => {
      const birthDate = patient.birth_date;
      if (cancelled || birthDateEditedRef.current || !birthDate || String(patient.id) !== String(patientId)) return;
      const baseline = parseWizardBaseline(initialContentRef.current);
      if (!baseline || String(baseline.patient.id) !== String(patientId)) return;
      initialContentRef.current = wizardContentSignature({
        patient: { ...baseline.patient, birth_date: birthDate },
        cart: baseline.cart,
      });
      setWizardData((prev) => String(prev.patient.id) === String(patientId)
        ? { ...prev, patient: { ...prev.patient, birth_date: birthDate } }
        : prev);
      setFormattedBirthDate(convertDateFromISO(birthDate));
    }).catch(() => {
      // An unavailable card does not turn the snapshot year into a date.
    });

    return () => { cancelled = true; };
  }, [isOpen, editMode, initialData, getPatient, initialContentRef, setWizardData]);

  const handleBirthDateChange = (value: string) => {
    birthDateEditedRef.current = true;
    const formatted = formatBirthDateInput(value);
    setFormattedBirthDate(formatted);
    setWizardData((prev) => ({
      ...prev,
      patient: { ...prev.patient, birth_date: convertDateToISO(formatted) },
    }));
  };

  return { formattedBirthDate, setFormattedBirthDate, birthDateEditedRef, handleBirthDateChange };
}
