import { useState, useEffect, useCallback, useMemo, useRef } from 'react';

import { api } from '../api/client';
import type { Appointment, Doctor } from '../types/domain/clinic';
import type { AsyncState } from '../types/async-state';
import { idleState, loadingState, successState, errorState, getError } from '../types/async-state';
// Wire-up: domain invariant validators (Track 2 + Wire-up).
import { checkAppointmentHasPatient, checkAppointmentPaymentAmount } from '../types/domain/invariants/appointment';

/**
 * Normalized appointment shape — extends the domain Appointment with the
 * fields that `normalizeAppointment` synthesises plus the raw fields that
 * consumers (AdminAppointments) read directly.
 */
interface NormalizedAppointment extends Appointment {
  // Fields synthesised by normalizeAppointment
  patientId?: string | number | null;
  doctorId?: string | number | null;
  patientName?: string;
  doctorName?: string;
  doctorSpecialization?: string;
  appointmentDate?: string;
  appointmentTime?: string;
  reason?: string;
  notes?: string;
  createdAt?: string | null;
  updatedAt?: string | null;
  effectiveCabinet?: string | null;
  queueCabinet?: string | null;
  doctorCabinet?: string | null;
  integrityWarnings?: string[];
  hasIntegrityWarnings?: boolean;
  // Raw fields read directly by consumers
  phone?: string;
  duration?: number;
  doctor?: { active?: boolean; user_active?: boolean; [k: string]: unknown };
}

const normalizeAppointment = (appointment: Appointment): NormalizedAppointment => ({
  ...appointment,
  patientId: (appointment.patientId ?? appointment.patient_id ?? null) as string | number | null,
  doctorId: (appointment.doctorId ?? appointment.doctor_id ?? null) as string | number | null,
  patientName: (appointment.patientName ?? appointment.patient_name ?? 'Пациент') as string,
  doctorName: (appointment.doctorName ?? appointment.doctor_name ?? 'Врач') as string,
  doctorSpecialization: (appointment.doctorSpecialization ??
    appointment.doctor_specialization ??
    appointment.specialization ??
    '') as string,
  appointmentDate: (appointment.appointmentDate ?? appointment.appointment_date ?? '') as string,
  appointmentTime: (appointment.appointmentTime ?? appointment.appointment_time ?? '') as string,
  reason: (appointment.reason ?? appointment.notes ?? '') as string,
  notes: (appointment.notes ?? '') as string,
  createdAt: (appointment.createdAt ?? appointment.created_at ?? null) as string | null,
  updatedAt: (appointment.updatedAt ?? appointment.updated_at ?? null) as string | null,
  effectiveCabinet: (appointment.effectiveCabinet ?? appointment.effective_cabinet ?? null) as string | null,
  queueCabinet: (appointment.queueCabinet ?? appointment.queue_cabinet ?? null) as string | null,
  doctorCabinet: (appointment.doctorCabinet ?? appointment.doctor_cabinet ?? null) as string | null,
  integrityWarnings: (appointment.integrityWarnings ??
    appointment.integrity_warnings ??
    []) as string[],
  hasIntegrityWarnings: (appointment.hasIntegrityWarnings ??
    appointment.has_integrity_warnings ??
    false) as boolean,
} as NormalizedAppointment);

const buildAppointmentPayload = (appointmentData: Record<string, unknown>, doctors: Doctor[] = []) => {
  const selectedDoctor = doctors.find(
    (doctor) => String(doctor.id) === String(appointmentData.doctorId)
  );

  const payload = {
    patient_id: Number(appointmentData.patientId),
    doctor_id: Number(appointmentData.doctorId),
    department: selectedDoctor?.specialty || null,
    appointment_date: appointmentData.appointmentDate,
    appointment_time: appointmentData.appointmentTime,
    notes: String(appointmentData.reason ?? "").trim() || String(appointmentData.notes ?? "").trim() || '',
    services: [],
  };

  if ((appointmentData as Record<string, unknown>).status) {
    (payload as Record<string, unknown>).status = (appointmentData as Record<string, unknown>).status;
  }

  return payload;
};

const useAppointments = (doctors: Doctor[] = []) => {
  const [appointments, setAppointments] = useState<NormalizedAppointment[]>([]);
  const [requestState, setRequestState] = useState<AsyncState<unknown>>(idleState<unknown>());
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterDate, setFilterDate] = useState('');
  const [filterDoctor, setFilterDoctor] = useState('');

  const loading = requestState.status === 'loading';
  const error = getError(requestState);

  // audit/phase-8, BS-22: request-ID guard against overlapping loads.
  // Each create/update/delete calls `await loadAppointments()`; if the user
  // triggers two mutations quickly, two loads are in flight and the later-
  // started one might resolve first, then the earlier overwrites with stale
  // data. The ref tracks the latest request; stale responses are discarded.
  const loadAppointmentsRequestIdRef = useRef(0);

  const loadAppointments = useCallback(async () => {
    const requestId = ++loadAppointmentsRequestIdRef.current;
    setRequestState(loadingState<unknown>());

    try {
      const response = await api.get('/admin/appointments');
      if (requestId !== loadAppointmentsRequestIdRef.current) return;
      const items = Array.isArray(response.data) ? response.data : [];
      setAppointments(items.map(normalizeAppointment));
      setRequestState(successState<unknown>(null));
    } catch (err) {
      if (requestId !== loadAppointmentsRequestIdRef.current) return;
      setRequestState(errorState<unknown>(String(err)));
    }
  }, []);

  const createAppointment = useCallback(
    async (appointmentData: Record<string, unknown>) => {
      // Wire-up: validate business invariants before API call.
      const patientCheck = checkAppointmentHasPatient({
        patient_id: appointmentData.patient_id as string | number | null,
      });
      if (!patientCheck.ok) {
        setRequestState(errorState<unknown>(patientCheck.message));
        throw new Error(patientCheck.message);
      }
      const amountCheck = checkAppointmentPaymentAmount({
        payment_amount: appointmentData.payment_amount as number | undefined,
      });
      if (!amountCheck.ok) {
        setRequestState(errorState<unknown>(amountCheck.message));
        throw new Error(amountCheck.message);
      }

      setRequestState(loadingState<unknown>());

      try {
        const response = await api.post(
          '/appointments',
          buildAppointmentPayload(appointmentData, doctors)
        );
        await loadAppointments();
        return normalizeAppointment(response.data || {});
      } catch (err) {
        setRequestState(errorState<unknown>(String(err)));
        throw err;
      }
    },
    [doctors, loadAppointments]
  );

  const updateAppointment = useCallback(
    async (id: string | number, appointmentData: Record<string, unknown>) => {
      setRequestState(loadingState<unknown>());

      try {
        const response = await api.put(
          `/appointments/${id}`,
          buildAppointmentPayload(appointmentData, doctors)
        );
        await loadAppointments();
        return normalizeAppointment(response.data || {});
      } catch (err) {
        setRequestState(errorState<unknown>(String(err)));
        throw err;
      }
    },
    [doctors, loadAppointments]
  );

  const deleteAppointment = useCallback(
    async (id: string | number) => {
      setRequestState(loadingState<unknown>());

      try {
        await api.delete(`/appointments/${id}`);
        await loadAppointments();
      } catch (err) {
        setRequestState(errorState<unknown>(String(err)));
        throw err;
      }
    },
    [loadAppointments]
  );

  const filteredAppointments = useMemo(
    () =>
      appointments.filter((appointment: NormalizedAppointment) => {
        const haystack = [
          appointment.patientName,
          appointment.doctorName,
          appointment.reason,
          appointment.phone,
          appointment.effectiveCabinet,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();

        const matchesSearch =
          !searchTerm || haystack.includes(searchTerm.toLowerCase());
        const matchesStatus =
          !filterStatus || appointment.status === filterStatus;
        const matchesDate =
          !filterDate || appointment.appointmentDate === filterDate;
        const matchesDoctor =
          !filterDoctor || appointment.doctorId === Number(filterDoctor);

        return matchesSearch && matchesStatus && matchesDate && matchesDoctor;
      }),
    [appointments, filterDate, filterDoctor, filterStatus, searchTerm]
  );

  const getStatusStats = useCallback(() => {
    const stats: Record<string, number> = {
      pending: 0,
      confirmed: 0,
      paid: 0,
      in_visit: 0,
      completed: 0,
      cancelled: 0,
      no_show: 0,
    };

    appointments.forEach((appointment: NormalizedAppointment) => {
      const status = appointment.status as string | undefined;
      if (status) {
        stats[status] = (stats[status] || 0) + 1;
      }
    });

    return stats;
  }, [appointments]);

  const getTodayAppointments = useCallback(() => {
    const today = new Date().toISOString().split('T')[0];
    return appointments.filter((appointment: NormalizedAppointment) => appointment.appointmentDate === today);
  }, [appointments]);

  const getTomorrowAppointments = useCallback(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split('T')[0];
    return appointments.filter(
      (appointment: NormalizedAppointment) => appointment.appointmentDate === tomorrowStr
    );
  }, [appointments]);

  useEffect(() => {
    void loadAppointments();
  }, [loadAppointments]);

  return {
    appointments: filteredAppointments,
    allAppointments: appointments,
    loading,
    error,
    searchTerm,
    setSearchTerm,
    filterStatus,
    setFilterStatus,
    filterDate,
    setFilterDate,
    filterDoctor,
    setFilterDoctor,
    createAppointment,
    updateAppointment,
    deleteAppointment,
    refresh: loadAppointments,
    getStatusStats,
    getTodayAppointments,
    getTomorrowAppointments,
  };
};

export default useAppointments;
