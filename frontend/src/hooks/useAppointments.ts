import { useState, useEffect, useCallback, useMemo } from 'react';

import { api } from '../api/client';

const normalizeAppointment = (appointment) => ({
  ...appointment,
  patientId: appointment.patientId ?? appointment.patient_id ?? null,
  doctorId: appointment.doctorId ?? appointment.doctor_id ?? null,
  patientName: appointment.patientName ?? appointment.patient_name ?? 'Пациент',
  doctorName: appointment.doctorName ?? appointment.doctor_name ?? 'Врач',
  doctorSpecialization:
    appointment.doctorSpecialization ??
    appointment.doctor_specialization ??
    appointment.specialization ??
    '',
  appointmentDate: appointment.appointmentDate ?? appointment.appointment_date ?? '',
  appointmentTime: appointment.appointmentTime ?? appointment.appointment_time ?? '',
  reason: appointment.reason ?? appointment.notes ?? '',
  notes: appointment.notes ?? '',
  createdAt: appointment.createdAt ?? appointment.created_at ?? null,
  updatedAt: appointment.updatedAt ?? appointment.updated_at ?? null,
  effectiveCabinet: appointment.effectiveCabinet ?? appointment.effective_cabinet ?? null,
  queueCabinet: appointment.queueCabinet ?? appointment.queue_cabinet ?? null,
  doctorCabinet: appointment.doctorCabinet ?? appointment.doctor_cabinet ?? null,
  integrityWarnings:
    appointment.integrityWarnings ?? appointment.integrity_warnings ?? [],
  hasIntegrityWarnings:
    appointment.hasIntegrityWarnings ?? appointment.has_integrity_warnings ?? false,
});

const buildAppointmentPayload = (appointmentData: Record<string, unknown>, doctors: unknown[] = []) => {
  const selectedDoctor = doctors.find(
    (doctor) => (doctor as Record<string, unknown>).id === Number((appointmentData as Record<string, unknown>).doctorId)
  );

  const payload = {
    patient_id: Number((appointmentData as Record<string, unknown>).patientId),
    doctor_id: Number((appointmentData as Record<string, unknown>).doctorId),
    department: (selectedDoctor as Record<string, unknown> | null)?.specialty || null,
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

const useAppointments = (doctors: unknown[] = []) => {
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterDate, setFilterDate] = useState('');
  const [filterDoctor, setFilterDoctor] = useState('');

  const loadAppointments = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.get('/admin/appointments');
      const items = Array.isArray(response.data) ? response.data : [];
      setAppointments(items.map(normalizeAppointment));
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const createAppointment = useCallback(
    async (appointmentData) => {
      setLoading(true);
      setError(null);

      try {
        const response = await api.post(
          '/appointments',
          buildAppointmentPayload(appointmentData, doctors)
        );
        await loadAppointments();
        return normalizeAppointment(response.data || {});
      } catch (err) {
        setError(String(err));
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [doctors, loadAppointments]
  );

  const updateAppointment = useCallback(
    async (id, appointmentData) => {
      setLoading(true);
      setError(null);

      try {
        const response = await api.put(
          `/appointments/${id}`,
          buildAppointmentPayload(appointmentData, doctors)
        );
        await loadAppointments();
        return normalizeAppointment(response.data || {});
      } catch (err) {
        setError(String(err));
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [doctors, loadAppointments]
  );

  const deleteAppointment = useCallback(
    async (id) => {
      setLoading(true);
      setError(null);

      try {
        await api.delete(`/appointments/${id}`);
        await loadAppointments();
      } catch (err) {
        setError(String(err));
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [loadAppointments]
  );

  const filteredAppointments = useMemo(
    () =>
      appointments.filter((appointment) => {
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
    const stats = {
      pending: 0,
      confirmed: 0,
      paid: 0,
      in_visit: 0,
      completed: 0,
      cancelled: 0,
      no_show: 0,
    };

    appointments.forEach((appointment) => {
      stats[appointment.status] = (stats[appointment.status] || 0) + 1;
    });

    return stats;
  }, [appointments]);

  const getTodayAppointments = useCallback(() => {
    const today = new Date().toISOString().split('T')[0];
    return appointments.filter((appointment) => appointment.appointmentDate === today);
  }, [appointments]);

  const getTomorrowAppointments = useCallback(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split('T')[0];
    return appointments.filter(
      (appointment) => appointment.appointmentDate === tomorrowStr
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
