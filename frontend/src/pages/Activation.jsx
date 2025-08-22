import React, { useEffect, useMemo, useState } from "react";
import Nav from "../components/Nav.jsx";
import RoleGate from "../components/RoleGate.jsx";
import { api } from "../api/client.js";

/**
 * Admin панель активаций:
 *  - /activation/status
 *  - /activation/list?status=&key_like=&machine_hash=&limit=&offset=
 *  - /activation/issue {days,status,meta}
 *  - /activation/revoke {key}
 *  - /activation/extend {key,days}
 */
export default function Activation() {
  const [page, setPage] = useState("Activation");
  const [status, setStatus] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [issueDays, setIssueDays] = useState(365);
  const [issueType, setIssueType] = useState("active");
  const [issueMeta, setIssueMeta] = useState("");
  const [busyKey, setBusyKey] = useState("");

  async function loadAll() {
    setLoading(true);
    try {
      const [st, lst] = await Promise.all([
        api.get("/activation/status"),
        api.get("/activation/list", { params: { status: filterStatus || undefined, limit: 200 } }),
      ]);
      setStatus(st || null);
      setRows((lst && lst.items) || []);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadAll(); }, [filterStatus]);

  const filtered = useMemo(() => {
    if (!q) return rows;
    const qq = q.toLowerCase();
    return rows.filter(r =>
      (r.key || "").toLowerCase().includes(qq) ||
      (r.machine_hash || "").toLowerCase().includes(qq) ||
      (r.status || "").toLowerCase().includes(qq)
    );
  }, [q, rows]);

  async function issue() {
    const body = { days: Number(issueDays) || 365, status: issueType, meta: issueMeta || undefined };
    await api.post("/activation/issue", { body });
    setIssueMeta("");
    await loadAll();
  }

  async function revoke(key) {
    if (!confirm(`Отозвать ключ ${key}?`)) return;
    setBusyKey(key);
    try {
      await api.post("/activation/revoke", { body: { key } });
      await loadAll();
    } finally {
      setBusyKey("");
    }
  }

  async function extend(key) {
    const v = prompt("На сколько дней продлить?", "365");
    if (!v) return;
    const days = Number(v);
    if (!days || days <= 0) return;
    setBusyKey(key);
    try {
      await api.post("/activation/extend", { body: { key, days } });
      await loadAll();
    } finally {
      setBusyKey("");
    }
  }

  return (
    <div>
      <Nav active={page} onNavigate={setPage} />
      <RoleGate roles={["Admin"]}>
        <div style={{ padding: 16, display: "grid", gap: 12 }}>
          <h2 style={{ margin: 0 }}>Activation (Admin)</h2>

          <div style={{ display: "grid", gap: 8, border: "1px solid #eee", borderRadius: 12, padding: 12, background: "#fff" }}>
            <div>Состояние сервера:{" "}
              {status ? (
                <b style={{ color: status.ok ? "#065f46" : "#7f1d1d" }}>
                  {status.ok ? "Активирован" : `Нет активации (${status.reason || "—"})`}
                </b>
              ) : "…"}
            </div>
            <div style={{ fontSize: 12, opacity: .75 }}>
              Machine hash: <code>{status?.machine_hash || "—"}</code>
            </div>
          </div>

          <div style={{ display: "grid", gap: 8, border: "1px solid #eee", borderRadius: 12, padding: 12, background: "#fff" }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Выдать ключ</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <label>Тип{" "}
                <select value={issueType} onChange={(e)=>setIssueType(e.target.value)} style={inp}>
                  <option value="active">active</option>
                  <option value="trial">trial</option>
                  <option value="issued">issued</option>
                </select>
              </label>
              <label>Срок (дней){" "}
                <input type="number" min={1} max={3650} value={issueDays} onChange={(e)=>setIssueDays(e.target.value)} style={inp} />
              </label>
              <input placeholder="meta (опционально)" value={issueMeta} onChange={(e)=>setIssueMeta(e.target.value)} style={{ ...inp, minWidth: 260 }} />
              <button onClick={issue} style={btn}>Выдать</button>
            </div>
          </div>

          <div style={{ display: "grid", gap: 8 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input placeholder="Поиск по key/hash/status…" value={q} onChange={(e)=>setQ(e.target.value)} style={{ ...inp, minWidth: 280 }} />
              <select value={filterStatus} onChange={(e)=>setFilterStatus(e.target.value)} style={inp}>
                <option value="">все</option>
                <option value="active">active</option>
                <option value="trial">trial</option>
                <option value="issued">issued</option>
                <option value="expired">expired</option>
                <option value="revoked">revoked</option>
              </select>
              <button onClick={loadAll} style={btn}>Обновить</button>
              {loading && <span style={{ opacity: .6 }}>Загрузка…</span>}
            </div>

            <div style={{ display: "grid", gap: 8 }}>
              {filtered.map((r) => (
                <div key={r.key} style={rowBox}>
                  <div style={{ display: "grid", gap: 2 }}>
                    <div style={{ fontWeight: 700 }}>{r.key}</div>
                    <div style={{ fontSize: 12, opacity: .75 }}>hash: <code>{r.machine_hash || "—"}</code></div>
                  </div>
                  <div style={{ opacity: .8 }}>
                    {r.status} · до {r.expiry_date || "—"}
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button disabled={busyKey===r.key} onClick={()=>extend(r.key)} style={btn}>Продлить</button>
                    <button disabled={busyKey===r.key} onClick={()=>revoke(r.key)} style={btnDanger}>Отозвать</button>
                  </div>
                </div>
              ))}
              {!loading && filtered.length === 0 && <div style={{ opacity: .7 }}>Нет записей</div>}
            </div>
          </div>
        </div>
      </RoleGate>
    </div>
  );
}

const inp = { padding: "6px 10px", border: "1px solid #ddd", borderRadius: 8, background: "#fff" };
const btn = { padding: "6px 10px", borderRadius: 8, border: "1px solid #ddd", background: "#fff", cursor: "pointer" };
const btnDanger = { ...btn, borderColor: "#fecaca", background: "#fee2e2" };
const rowBox = { display: "grid", gridTemplateColumns: "2fr 1fr auto", gap: 8, padding: 10, border: "1px solid #eee", borderRadius: 10, background: "#fff" };