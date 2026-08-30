// PR-UI-15-2: presentation-only view-model filters extracted verbatim from
// pages/DoctorPanel.tsx (registrar/cashier decomposition precedent).
import type { AppointmentDto, PatientRecord } from './doctorStatus';

export const filterPatients = (
  patients: PatientRecord[],
  searchQuery: string,
  filterStatus: string,
): PatientRecord[] => patients.filter((patient) => {
  const patientName = String(patient.name || '');
  const patientPhone = String(patient.phone || '');
  const matchesSearch = patientName.toLowerCase().includes(searchQuery.toLowerCase()) ||
    patientPhone.includes(searchQuery);
  const matchesFilter = filterStatus === 'all' || patient.status === filterStatus;
  return matchesSearch && matchesFilter;
});

export const filterAppointments = (
  appointments: AppointmentDto[],
  searchQuery: string,
  filterStatus: string,
): AppointmentDto[] => appointments.filter((appointment) => {
  const patientName = String(appointment.patientName || '');
  const matchesSearch = patientName.toLowerCase().includes(searchQuery.toLowerCase());
  const matchesFilter = filterStatus === 'all' || appointment.status === filterStatus;
  return matchesSearch && matchesFilter;
});
