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
 * Лаборатория: список направлений/заказов за день (чтение).
 * Совместимо с GET /lab или /lab?d=YYYY-MM-DD&limit=...
 */
export default function Lab() {
  const [page, setPage] = useState("Lab");
  const [date, setDate] = useState(todayStr());
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function load() {
    setBusy(true);
    setErr("");
    try {
      const res = await api.get("/lab", { params: { d: date, limit: 100 } });
      const items = Array.isArray(res?.items) ? res.items : Array.isArray(res) ? res : [];
      setRows(items);
    } catch (e) {
      setErr(e?.data?.detail || e?.message || "Ошибка загрузки лабораторных заказов");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { load(); }, [date]);

  const filtered = useMemo(() => {
    if (!q) return rows;
    const qq = q.toLowerCase();
    return rows.filter(r =>
      String(r.patient_name || r.patient?.full_name || "").toLowerCase().includes(qq) ||
      String(r.id || "").toLowerCase().includes(qq) ||
      String(r.status || "").toLowerCase().includes(qq)
    );
  }, [q, rows]);

  return (
    <div>
      <Nav active={page} onNavigate={setPage} />
      <RoleGate roles={["Admin", "Lab"]}>
        <div style={{ padding: 16, display: "grid", gap: 12 }}>
          <h2 style={{ margin: 0 }}>Лаборатория</h2>

          <div style={panel}>
            <label>
              Дата:&nbsp;
              <input type="date" value={date} onChange={(e)=>setDate(e.target.value)} style={inp}/>
            </label>
            <input placeholder="Поиск по пациенту/статусу/ID" value={q} onChange={(e)=>setQ(e.target.value)} style={{...inp, minWidth: 240}}/>
            <button onClick={load} disabled={busy} style={btn}>
              {busy ? "Загрузка" : "Обновить"}
            </button>
          </div>

          {err && <div style={errBox}>{String(err)}</div>}

          <div style={{ overflow: "auto", border: "1px solid #eee", borderRadius: 12, background: "#fff" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={th}>ID</th>
                  <th style={th}>Пациент</th>
                  <th style={th}>Тесты</th>
                  <th style={th}>Статус</th>
                  <th style={th}>Создано</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(o => (
                  <tr key={o.id}>
                    <td style={td}>{o.id}</td>
                    <td style={td}>{o.patient_name || o.patient?.full_name || "—"}</td>
                    <td style={td}>
                      {(o.tests || o.items || []).map((t, i) => (
                        <span key={t.id || i}>
                          {t.name || t.code || "тест"}{i < (o.tests||o.items||[]).length-1 ? ", " : ""}
                        </span>
                      ))}
                    </td>
                    <td style={td}>{o.status || "—"}</td>
                    <td style={td}>{o.created_at || "—"}</td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr><td style={td} colSpan={5}>Нет записей</td></tr>
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