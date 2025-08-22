import React, { useEffect, useMemo, useState } from "react";
import Nav from "../components/Nav.jsx";
import RoleGate from "../components/RoleGate.jsx";
import { api } from "../api/client.js";

function todayStr() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

/**
 * Расписание: просмотр слотов (чтение).
 * Совместимо с GET /schedule?date=YYYY-MM-DD&limit=...
 */
export default function Scheduler() {
  const [page, setPage] = useState("Scheduler");
  const [date, setDate] = useState(todayStr());
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function load() {
    setBusy(true);
    setErr("");
    try {
      // Пытаемся обеими формами параметров: date и d — поддержка разных реализаций.
      let res = await api.get("/schedule", { params: { date, limit: 200 } });
      if (!res || (!Array.isArray(res) && !Array.isArray(res?.items))) {
        res = await api.get("/schedule", { params: { d: date, limit: 200 } });
      }
      const items = Array.isArray(res?.items) ? res.items : Array.isArray(res) ? res : [];
      setRows(items);
    } catch (e) {
      setErr(e?.data?.detail || e?.message || "Ошибка загрузки расписания");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { load(); }, [date]);

  const filtered = useMemo(() => {
    if (!q) return rows;
    const qq = q.toLowerCase();
    return rows.filter(s =>
      String(s.doctor_name || s.doctor || "").toLowerCase().includes(qq) ||
      String(s.room || "").toLowerCase().includes(qq) ||
      String(s.status || "").toLowerCase().includes(qq)
    );
  }, [q, rows]);

  return (
    <div>
      <Nav active={page} onNavigate={setPage} />
      <RoleGate roles={["Admin", "Registrar", "Doctor"]}>
        <div style={{ padding: 16, display: "grid", gap: 12 }}>
          <h2 style={{ margin: 0 }}>Расписание</h2>

          <div style={panel}>
            <label>
              Дата:&nbsp;
              <input type="date" value={date} onChange={(e)=>setDate(e.target.value)} style={inp}/>
            </label>
            <input placeholder="Поиск по врачу/кабинету/статусу" value={q} onChange={(e)=>setQ(e.target.value)} style={{...inp, minWidth: 260}}/>
            <button onClick={load} disabled={busy} style={btn}>{busy ? "Загрузка" : "Обновить"}</button>
          </div>

          {err && <div style={errBox}>{String(err)}</div>}

          <div style={{ overflow: "auto", border: "1px solid #eee", borderRadius: 12, background: "#fff" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={th}>Врач</th>
                  <th style={th}>Кабинет</th>
                  <th style={th}>Время</th>
                  <th style={th}>Статус</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s, i) => (
                  <tr key={s.id || i}>
                    <td style={td}>{s.doctor_name || s.doctor || "—"}</td>
                    <td style={td}>{s.room || "—"}</td>
                    <td style={td}>
                      {(s.time || s.slot || s.start_time) ? (s.time || s.slot || s.start_time) : "—"}
                      {(s.end_time ? ` — ${s.end_time}` : "")}
                    </td>
                    <td style={td}>{s.status || (s.available ? "available" : "—")}</td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr><td style={td} colSpan={4}>Нет записей</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </RoleGate>
    </div>
  );
}

const panel = { display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", border: "1px solid #eee", borderRadius: 12, padding: 12, background: "#fff" };
const inp = { padding: "6px 10px", border: "1px solid #ddd", borderRadius: 8, background: "#fff" };
const btn = { padding: "6px 10px", borderRadius: 8, border: "1px solid #ddd", background: "#fff", cursor: "pointer" };
const th = { textAlign: "left", padding: 10, borderBottom: "1px solid #eee", fontWeight: 700, whiteSpace: "nowrap" };
const td = { padding: 10, borderBottom: "1px solid #f3f4f6", verticalAlign: "top" };
const errBox = { color: "#7f1d1d", background: "#fee2e2", border: "1px solid #fecaca", borderRadius: 8, padding: 8 };