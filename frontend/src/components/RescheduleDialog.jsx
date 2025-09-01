import React, { useEffect, useState } from 'react';
import { rescheduleVisit, rescheduleTomorrow } from '../api/visits';

/**
 * Диалог переноса визита.
 * Props:
 *  - open: boolean
 *  - onClose: () => void
 *  - visit: { id, scheduled_at, ... }
 *  - onRescheduled?: (updated) => void
 */
export default function RescheduleDialog({ open, onClose, visit, onRescheduled }) {
  const [d, setD] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (!open) return;
    setErr('');
    // Проставим текущее время визита, если есть
    if (visit?.planned_date) {
      try {
        const dt = new Date(visit.planned_date);
        const pad = (n) => String(n).padStart(2, '0');
        const value = `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`;
        setD(value);
      } catch {
        setD('');
      }
    } else {
      setD('');
    }
  }, [open, visit]);

  if (!open) return null;

  async function doReschedule() {
    if (!visit?.id) return;
    setBusy(true);
    setErr('');
    try {
      if (!d) throw new Error('Укажите дату');
      const updated = await rescheduleVisit(visit.id, d);
      onRescheduled?.(updated || null);
      onClose?.();
    } catch (e) {
      setErr(e?.data?.detail || e?.message || 'Не удалось перенести визит');
    } finally {
      setBusy(false);
    }
  }

  async function doTomorrow() {
    if (!visit?.id) return;
    setBusy(true);
    setErr('');
    try {
      const updated = await rescheduleTomorrow(visit.id);
      onRescheduled?.(updated || null);
      onClose?.();
    } catch (e) {
      setErr(e?.data?.detail || e?.message || 'Не удалось перенести на завтра');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={backdrop} onClick={(e) => e.target === e.currentTarget && !busy && onClose?.()}>
      <div style={modal}>
        <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>Перенос визита</h3>

        <div style={{ marginTop: 12, display: 'grid', gap: 8 }}>
          <label style={{ display: 'grid', gap: 6 }}>
            <span>Новая дата</span>
            <input
              type="date"
              value={d}
              onChange={(e) => setD(e.target.value)}
              style={input}
              disabled={busy}
            />
          </label>

          {err ? (
            <div style={errBox}>{err}</div>
          ) : (
            <div style={{ fontSize: 12, color: '#6b7280' }}>
              Визит: <b>#{visit?.id ?? '—'}</b>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 14, justifyContent: 'flex-end' }}>
          <button onClick={onClose} disabled={busy} style={btn}>
            Отмена
          </button>
          <button onClick={doTomorrow} disabled={busy} style={{ ...btn, borderColor: '#16a34a' }}>
            На завтра
          </button>
          <button onClick={doReschedule} disabled={busy} style={{ ...btn, background: '#111', color: '#fff' }}>
            Перенести
          </button>
        </div>
      </div>
    </div>
  );
}

/* styles */
const backdrop = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,.3)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
};
const modal = {
  width: 'min(560px, 92vw)',
  background: '#fff',
  border: '1px solid #e5e7eb',
  borderRadius: 12,
  boxShadow: '0 10px 30px rgba(0,0,0,.08)',
  padding: 16,
};
const input = {
  padding: '8px 10px',
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  outline: 'none',
};
const btn = {
  padding: '8px 12px',
  borderRadius: 10,
  border: '1px solid #d1d5db',
  background: '#fff',
  cursor: 'pointer',
};

