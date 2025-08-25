import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import PropTypes from "prop-types";
import { getVisit, rescheduleVisit } from "../api";
import RescheduleDialog from "../components/RescheduleDialog";

/**
 * VisitDetails page
 * - Shows visit information
 * - Allows opening RescheduleDialog
 * - Quick actions: reschedule to tomorrow (one-click)
 *
 * Route: /visits/:id
 */
function VisitDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [visit, setVisit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    if (!id) return;
    let mounted = true;
    setLoading(true);
    setError("");
    getVisit(id)
      .then((data) => {
        if (!mounted) return;
        setVisit(data || null);
      })
      .catch((err) => {
        console.error("getVisit error:", err);
        setError((err && err.data && (err.data.detail || err.data.message)) || err.message || "Ошибка загрузки приёма");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [id]);

  const handleRescheduled = (updated) => {
    // updated may include new fields from backend
    setVisit((prev) => ({ ...(prev || {}), ...(updated || {}) }));
  };

  const rescheduleTomorrow = async () => {
    if (!visit) return;
    setLoading(true);
    setError("");
    try {
      const baseDate = visit.scheduled_at ? new Date(visit.scheduled_at) : new Date();
      const tomorrow = new Date(baseDate);
      tomorrow.setDate(baseDate.getDate() + 1);
      const iso = tomorrow.toISOString();
      const res = await rescheduleVisit(visit.id, iso);
      setVisit((prev) => ({ ...(prev || {}), scheduled_at: iso, ...(res || {}) }));
    } catch (err) {
      console.error("rescheduleTomorrow error:", err);
      setError((err && err.data && (err.data.detail || err.data.message)) || err.message || "Ошибка переноса");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6">
        <div>Загрузка приёма...</div>
      </div>
    );
  }

  if (!visit) {
    return (
      <div className="p-6">
        <div className="text-red-600 mb-4">{error || "Приём не найден."}</div>
        <Link to="/" className="text-blue-600 underline">Вернуться на главную</Link>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Детали приёма #{visit.id}</h1>
        <div className="space-x-2">
          <button
            onClick={() => setDialogOpen(true)}
            className="px-3 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600"
          >
            Перенести
          </button>
          <button
            onClick={rescheduleTomorrow}
            className="px-3 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700"
            disabled={loading}
          >
            На завтра
          </button>
        </div>
      </div>

      <div className="bg-white shadow rounded p-4 mb-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-sm text-gray-500">Пациент</div>
            <div className="font-medium">{visit.patient?.full_name || visit.patient_name || "—"}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Статус</div>
            <div className="font-medium">{visit.status || "—"}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Запланировано</div>
            <div className="font-medium">{visit.scheduled_at ? new Date(visit.scheduled_at).toLocaleString() : "—"}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Врач / кабинет</div>
            <div className="font-medium">{visit.doctor?.name || visit.room || "—"}</div>
          </div>
        </div>

        {visit.notes && (
          <div className="mt-4">
            <div className="text-sm text-gray-500">Примечание</div>
            <div className="mt-1">{visit.notes}</div>
          </div>
        )}
      </div>

      <div className="flex items-center space-x-2">
        <button
          onClick={() => navigate(-1)}
          className="px-3 py-2 border rounded bg-white hover:bg-gray-50"
        >
          Назад
        </button>
        <Link to="/visits" className="px-3 py-2 border rounded bg-white hover:bg-gray-50">Список приёмов</Link>
      </div>

      <RescheduleDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        visit={visit}
        onRescheduled={(u) => { handleRescheduled(u); setDialogOpen(false); }}
      />
    </div>
  );
}

VisitDetails.propTypes = {
  // routed component — no props expected
};

export default VisitDetails;

